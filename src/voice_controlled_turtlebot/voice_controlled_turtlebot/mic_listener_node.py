import rclpy
from rclpy.node import Node
from std_msgs.msg import String
import subprocess

class NodoEscuchaMic(Node):
    def __init__(self):
        super().__init__('mic_listener_node')

        self.pub_texto_voz = self.create_publisher(String, '/voice_text', 10)

        self.ruta_whisper = '/home/m/voice_controlled_turtlebot/whisper.cpp'
        self.archivo_modelo = f'{self.ruta_whisper}/models/ggml-base.bin'
        self.archivo_wav_temp = '/tmp/mic_temp.wav'

        # Cambiar si el micrófono no responde
        self.dispositivo_mic = 'plughw:0,1'

        self.periodo_timer = 5.0  # segundos entre grabaciones
        self.create_timer(self.periodo_timer, self.escuchar_y_transcribir)

        self.get_logger().info(f'Escucha mic iniciada (dispositivo: {self.dispositivo_mic})')

    def escuchar_y_transcribir(self):
        self.get_logger().info(f'Grabando desde {self.dispositivo_mic}...')
        try:
            # Grabar 4 segundos de audio
            subprocess.run([
                'arecord',
                '-D', self.dispositivo_mic,
                '-f', 'S16_LE',
                '-r', '16000',
                '-c', '1',
                '-t', 'wav',
                '-d', '4',
                self.archivo_wav_temp
            ], check=True)

            # Transcribir con whisper-cli
            resultado = subprocess.run([
                f'{self.ruta_whisper}/build/bin/whisper-cli',
                '-m', self.archivo_modelo,
                '-f', self.archivo_wav_temp,
                '--output-txt'
            ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

            texto_salida = resultado.stdout.strip()

            if resultado.returncode != 0:
                self.get_logger().error(f'Error whisper: {resultado.stderr}')

            if texto_salida:
                self.get_logger().info(f'Transcripcion: {texto_salida}')
                msg = String()
                msg.data = texto_salida.lower()
                self.pub_texto_voz.publish(msg)
            else:
                self.get_logger().warn('Sin transcripcion detectada.')

        except Exception as e:
            self.get_logger().error(f'Error: {e}')


def main(args=None):
    rclpy.init(args=args)
    nodo = NodoEscuchaMic()
    rclpy.spin(nodo)
    nodo.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()
