"""
command_parser_node — detecta la wake word "ana" y extrae comandos.

Solo actúa si el texto contiene "ana". Parsea el texto DESPUÉS de "ana"
para buscar comandos. Publica UNA VEZ en /voice_command (sin timer repetitivo).
"""

import rclpy
from rclpy.node import Node
from std_msgs.msg import String

WAKE_WORD = 'ana'


class NodoAnalizadorComandos(Node):
    def __init__(self):
        super().__init__('command_parser_node')

        self.create_subscription(String, '/voice_text', self.cb_voz, 10)
        self.pub_comando = self.create_publisher(String, '/voice_command', 10)

        self.mapa_comandos = {
            'volver a base':  'volver_a_base',
            'buscar objeto':  'buscar_objeto',
            'ir al objeto':   'ir_al_objeto',
            'tomar foto':     'tomar_foto',
            'desacoplar':     'desacoplar',
            'qué ves':        'ver',
            'que ves':        'ver',
            'qué hay':        'ver',
            'que hay':        'ver',
            'mira ahí':       'ver',
            'adelante':       'adelante',
            'acoplar':        'acoplar',
            'escanear':       'ver',
            'repetir':        'repetir',
            'sacudir':        'sacudir',
            'atrás':          'atras',
            'izquierda':      'izquierda',
            'derecha':        'derecha',
            'girar':          'girar',
            'parar':          'parar',
            'mira':           'ver',
        }

        self.get_logger().info(f'Analizador iniciado (wake word: "{WAKE_WORD}").')

    def cb_voz(self, msg):
        texto = msg.data.lower().strip()
        self.get_logger().info(f'Texto recibido: {texto}')

        if WAKE_WORD not in texto:
            self.get_logger().info('Sin wake word, ignorando.')
            return

        # Extraer la parte después de la wake word
        idx = texto.index(WAKE_WORD) + len(WAKE_WORD)
        texto_comando = texto[idx:].strip()
        self.get_logger().info(f'Wake word detectada. Comando: "{texto_comando}"')

        if not texto_comando:
            # Solo dijo "ana" sin nada más — publicar wake sin comando
            # para que el diálogo pueda responder "¿Sí? Dime."
            msg_cmd = String()
            msg_cmd.data = 'wake'
            self.pub_comando.publish(msg_cmd)
            return

        # Buscar comando (frases largas primero)
        comando = None
        for clave in sorted(self.mapa_comandos, key=lambda k: -len(k)):
            if clave in texto_comando:
                comando = self.mapa_comandos[clave]
                break

        if comando:
            self.get_logger().info(f'Comando: {comando}')
            msg_cmd = String()
            msg_cmd.data = comando
            self.pub_comando.publish(msg_cmd)
        else:
            # No es un comando conocido — publicar 'pregunta_libre'
            # con el texto para que el diálogo lo procese con LLM
            self.get_logger().info('No es comando, pasando a diálogo.')
            msg_cmd = String()
            msg_cmd.data = f'pregunta:{texto_comando}'
            self.pub_comando.publish(msg_cmd)


def main(args=None):
    rclpy.init(args=args)
    nodo = NodoAnalizadorComandos()
    rclpy.spin(nodo)
    nodo.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()
