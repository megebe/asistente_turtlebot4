"""
command_parser_node — detecta wake word "ana" y extrae comandos.
"""

import unicodedata

import rclpy
from rclpy.node import Node
from std_msgs.msg import String, Bool

WAKE_WORD = 'ana'


class NodoAnalizadorComandos(Node):
    def __init__(self):
        super().__init__('command_parser_node')

        self._tts_activo = False
        self.create_subscription(Bool, '/tts_activo', self._cb_tts, 10)
        self.create_subscription(String, '/voice_text', self.cb_voz, 10)
        self.pub_comando = self.create_publisher(String, '/voice_command', 10)

        # Precompilar mapa ordenado (frases largas primero)
        self._mapa = [
            ('volver a base', 'volver_a_base'),
            ('buscar objeto', 'buscar_objeto'),
            ('ir al objeto', 'ir_al_objeto'),
            ('tomar foto', 'tomar_foto'),
            ('desacoplar', 'desacoplar'),
            ('que estas viendo', 'ver'),
            ('a tu alrededor', 'ver'),
            ('que ves', 'ver'),
            ('que hay', 'ver'),
            ('que es lo que ves', 'ver'),
            ('mira ahi', 'ver'),
            ('adelante', 'adelante'),
            ('acoplar', 'acoplar'),
            ('escanear', 'ver'),
            ('repetir', 'repetir'),
            ('sacudir', 'sacudir'),
            ('atras', 'atras'),
            ('izquierda', 'izquierda'),
            ('derecha', 'derecha'),
            ('girar', 'girar'),
            ('parar', 'parar'),
            ('mira', 'ver'),
        ]

        self.get_logger().info('Parser listo.')

    @staticmethod
    def _quitar_acentos(texto):
        """á→a, é→e, í→i, ó→o, ú→u, ñ se preserva."""
        nfkd = unicodedata.normalize('NFKD', texto)
        return ''.join(c for c in nfkd if unicodedata.category(c) != 'Mn')

    def _cb_tts(self, msg):
        self._tts_activo = msg.data

    def cb_voz(self, msg):
        if self._tts_activo:
            return
        texto = self._quitar_acentos(msg.data.lower().strip())

        if WAKE_WORD not in texto:
            return

        idx = texto.index(WAKE_WORD) + len(WAKE_WORD)
        resto = texto[idx:].strip()
        # Quitar puntuación suelta
        resto = resto.strip('.,;:¿?¡! ')

        msg_cmd = String()

        if not resto:
            msg_cmd.data = 'wake'
        else:
            comando = None
            for frase, cmd in self._mapa:
                if frase in resto:
                    comando = cmd
                    break

            msg_cmd.data = comando if comando else f'pregunta:{resto}'

        self.get_logger().info(f'"{msg.data}" → {msg_cmd.data}')
        self.pub_comando.publish(msg_cmd)


def main(args=None):
    rclpy.init(args=args)
    nodo = NodoAnalizadorComandos()
    rclpy.spin(nodo)
    nodo.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()
