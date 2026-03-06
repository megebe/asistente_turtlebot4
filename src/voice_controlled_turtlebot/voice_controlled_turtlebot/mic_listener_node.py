"""
mic_listener_node — grabación continua con transcripción Whisper.

Graba en ping-pong (wav_A / wav_B) sin parar.
Logea SIEMPRE el RMS y la transcripción de cada ventana.
Solo publica en /voice_text si RMS > UMBRAL_RMS.
"""

import math
import re
import struct
import subprocess
import threading
import wave

import rclpy
from rclpy.node import Node
from std_msgs.msg import String

RUTA_WHISPER  = '/home/m/voice_controlled_turtlebot/whisper.cpp'
MODELO        = f'{RUTA_WHISPER}/models/ggml-tiny.bin'
BINARIO       = f'{RUTA_WHISPER}/build/bin/whisper-cli'
WAV_A         = '/tmp/mic_a.wav'
WAV_B         = '/tmp/mic_b.wav'

DURACION_SEG  = 3
UMBRAL_RMS    = 90


class NodoEscuchaMic(Node):
    def __init__(self):
        super().__init__('mic_listener_node')

        self.pub_texto_voz = self.create_publisher(String, '/voice_text', 10)
        self.dispositivo_mic = self._detectar_dispositivo()
        self._wav_escritura = WAV_A
        self._transcribiendo = False
        self._parar = False

        hilo = threading.Thread(target=self._bucle_grabacion, daemon=True)
        hilo.start()

        self.get_logger().info(f'Mic iniciado (dispositivo: {self.dispositivo_mic}, umbral: {UMBRAL_RMS})')

    def _detectar_dispositivo(self):
        try:
            salida = subprocess.run(
                ['arecord', '-l'], capture_output=True, text=True
            ).stdout
        except FileNotFoundError:
            self.get_logger().error('arecord no encontrado.')
            return 'default'

        candidatos = ['default']
        for m in re.finditer(r'card (\d+).*?device (\d+)', salida):
            candidatos.append(f'plughw:{m.group(1)},{m.group(2)}')

        for disp in candidatos:
            r = subprocess.run(
                ['arecord', '-D', disp, '-f', 'S16_LE', '-r', '16000',
                 '-c', '1', '-t', 'wav', '-d', '1', '/tmp/_probe.wav'],
                capture_output=True)
            if r.returncode == 0:
                self.get_logger().info(f'Micrófono seleccionado: {disp}')
                return disp

        return 'default'

    def _bucle_grabacion(self):
        while not self._parar:
            wav = self._wav_escritura
            self._wav_escritura = WAV_B if wav == WAV_A else WAV_A

            r = subprocess.run([
                'arecord', '-D', self.dispositivo_mic,
                '-f', 'S16_LE', '-r', '16000', '-c', '1',
                '-t', 'wav', '-d', str(DURACION_SEG), wav
            ], capture_output=True)

            if r.returncode != 0:
                self.get_logger().error('Error en arecord.')
                continue

            rms = self._calcular_rms(wav)
            self.get_logger().info(f'RMS: {rms:.0f}')

            if rms < UMBRAL_RMS:
                continue

            if self._transcribiendo:
                self.get_logger().warn(f'Whisper ocupado, descartando (RMS {rms:.0f}).')
                continue

            hilo = threading.Thread(
                target=self._transcribir, args=(wav,), daemon=True)
            hilo.start()

    def _calcular_rms(self, archivo_wav):
        try:
            with wave.open(archivo_wav, 'r') as f:
                frames = f.readframes(f.getnframes())
            if not frames:
                return 0.0
            muestras = struct.unpack(f'{len(frames) // 2}h', frames)
            return math.sqrt(sum(s * s for s in muestras) / len(muestras))
        except Exception:
            return 0.0

    def _transcribir(self, archivo_wav):
        self._transcribiendo = True
        try:
            resultado = subprocess.run([
                BINARIO, '-m', MODELO, '-f', archivo_wav,
                '-l', 'es', '--no-gpu', '--no-flash-attn',
                '--beam-size', '1', '--best-of', '1', '-t', '4',
            ], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)

            fragmentos = []
            for linea in resultado.stdout.splitlines():
                if '-->' in linea and ']' in linea:
                    texto = linea.split(']', 1)[-1].strip()
                    if texto:
                        fragmentos.append(texto)

            texto_salida = ' '.join(fragmentos)

            if not texto_salida or '[blank_audio]' in texto_salida.lower():
                self.get_logger().info('Whisper: (silencio)')
                return

            self.get_logger().info(f'Whisper: "{texto_salida}"')
            msg = String()
            msg.data = texto_salida.lower()
            self.pub_texto_voz.publish(msg)

        except Exception as e:
            self.get_logger().error(f'Error transcripción: {e}')
        finally:
            self._transcribiendo = False

    def destroy_node(self):
        self._parar = True
        super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    nodo = NodoEscuchaMic()
    try:
        rclpy.spin(nodo)
    except (KeyboardInterrupt, rclpy.executors.ExternalShutdownException):
        pass
    finally:
        nodo.destroy_node()
        rclpy.try_shutdown()


if __name__ == '__main__':
    main()
