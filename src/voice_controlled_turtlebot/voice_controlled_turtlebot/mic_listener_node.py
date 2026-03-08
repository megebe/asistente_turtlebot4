"""
mic_listener_node — escucha continua con faster-whisper in-process.

Modelo cargado UNA VEZ en RAM (~1.4s). Transcripción ~2s por clip.
VAD por energía RMS. Se pausa durante TTS.
"""

import math
import re
import struct
import subprocess
import threading
import time

import numpy as np
import rclpy
from rclpy.node import Node
from std_msgs.msg import String, Bool

TASA = 16000
UMBRAL_RMS = 90
CHUNK_SEG = 0.5
CHUNK_BYTES = int(TASA * CHUNK_SEG) * 2   # 16-bit mono
SILENCIO_FIN = 2                           # 1 segundo de silencio para cortar
MAX_GRABACION_SEG = 5                      # máximo 5s de grabación
COOLDOWN_TTS = 0.3                         # pausa post-TTS


class NodoEscuchaMic(Node):
    def __init__(self):
        super().__init__('mic_listener_node')

        self.pub_texto = self.create_publisher(String, '/voice_text', 10)

        self.dispositivo_mic = self._detectar_dispositivo()
        self._tts_activo = False

        self.create_subscription(Bool, '/tts_activo', self._cb_tts, 10)

        # Cargar modelo whisper UNA VEZ en RAM
        self._whisper = None
        threading.Thread(target=self._cargar_whisper, daemon=True).start()

        # Hilo dedicado para el bucle de audio (NO timer, no bloquea executor)
        threading.Thread(target=self._bucle_escucha, daemon=True).start()

    def _cargar_whisper(self):
        try:
            from faster_whisper import WhisperModel
            self._whisper = WhisperModel('tiny', device='cpu', compute_type='int8')
            self.get_logger().info('Whisper cargado en RAM.')
        except Exception as e:
            self.get_logger().error(f'Error cargando whisper: {e}')

    def _detectar_dispositivo(self):
        try:
            salida = subprocess.run(
                ['arecord', '-l'], capture_output=True, text=True
            ).stdout
        except FileNotFoundError:
            return 'default'

        candidatos = ['default']
        for m in re.finditer(r'card (\d+).*?device (\d+)', salida):
            candidatos.append(f'plughw:{m.group(1)},{m.group(2)}')

        for disp in candidatos:
            r = subprocess.run(
                ['arecord', '-D', disp, '-f', 'S16_LE', '-r', '16000',
                 '-c', '1', '-t', 'wav', '-d', '1', '/tmp/_probe.wav'],
                capture_output=True
            )
            if r.returncode == 0:
                self.get_logger().info(f'Mic: {disp}')
                return disp
        return 'default'

    def _cb_tts(self, msg):
        self._tts_activo = msg.data

    # ------------------------------------------------------------------
    # Bucle principal en hilo dedicado (NO bloquea el executor ROS2)
    # ------------------------------------------------------------------

    def _bucle_escucha(self):
        # Esperar a que whisper cargue
        while self._whisper is None and rclpy.ok():
            time.sleep(0.1)

        self.get_logger().info('Escucha iniciada.')

        while rclpy.ok():
            # Dormir mientras TTS habla
            while self._tts_activo and rclpy.ok():
                time.sleep(0.05)
            if not rclpy.ok():
                break

            time.sleep(COOLDOWN_TTS)

            try:
                proc = subprocess.Popen([
                    'arecord', '-D', self.dispositivo_mic,
                    '-f', 'S16_LE', '-r', str(TASA), '-c', '1', '-t', 'raw',
                ], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)

                self._stream_vad(proc)
            except Exception as e:
                self.get_logger().error(f'arecord: {e}')
            finally:
                proc.terminate()
                proc.wait()

    def _stream_vad(self, proc):
        chunks = []
        grabando = False
        n_silencio = 0
        max_chunks = int(MAX_GRABACION_SEG / CHUNK_SEG)

        while rclpy.ok():
            if self._tts_activo:
                break

            data = proc.stdout.read(CHUNK_BYTES)
            if not data or len(data) < CHUNK_BYTES:
                break

            rms = self._rms(data)

            if not grabando:
                if rms >= UMBRAL_RMS:
                    grabando = True
                    chunks = [data]
                    n_silencio = 0
            else:
                chunks.append(data)
                if rms < UMBRAL_RMS:
                    n_silencio += 1
                    if n_silencio >= SILENCIO_FIN:
                        self._transcribir(chunks)
                        grabando = False
                        chunks = []
                else:
                    n_silencio = 0

                if len(chunks) >= max_chunks:
                    self._transcribir(chunks)
                    grabando = False
                    chunks = []

    def _rms(self, data):
        n = len(data) // 2
        if n == 0:
            return 0.0
        muestras = struct.unpack(f'{n}h', data)
        return math.sqrt(sum(s * s for s in muestras) / n)

    # ------------------------------------------------------------------
    # Transcripción in-process (sin subprocess, sin file I/O)
    # ------------------------------------------------------------------

    def _transcribir(self, chunks):
        if self._whisper is None:
            return

        audio = np.frombuffer(b''.join(chunks), dtype=np.int16).astype(np.float32) / 32768.0

        try:
            segments, _ = self._whisper.transcribe(
                audio, language='es', beam_size=1, best_of=1,
                vad_filter=True,
            )
            texto = ' '.join(s.text.strip() for s in segments).strip()
        except Exception as e:
            self.get_logger().error(f'Whisper: {e}')
            return

        if not texto or '[' in texto:
            return

        self.get_logger().info(f'"{texto}"')
        msg = String()
        msg.data = texto.lower()
        self.pub_texto.publish(msg)


def main(args=None):
    rclpy.init(args=args)
    nodo = NodoEscuchaMic()
    rclpy.spin(nodo)
    nodo.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()
