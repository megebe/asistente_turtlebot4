import rclpy
from rclpy.node import Node
from std_msgs.msg import String

class NodoAnalizadorComandos(Node):
    def __init__(self):
        super().__init__('command_parser_node')

        self.create_subscription(String, '/voice_text', self.cb_voz, 10)
        self.pub_comando = self.create_publisher(String, '/voice_command', 10)

        self.comandos_validos = [
            # Movimiento
            'adelante', 'atrás', 'izquierda', 'derecha', 'parar',
            # Objetos
            'buscar objeto', 'ir al objeto', 'volver a base',
            # Acciones
            'escanear', 'repetir', 'acoplar', 'desacoplar', 'girar', 'sacudir', 'tomar foto'
        ]

        self.comando_actual = None
        self.timer_publicacion = None
        self.tiempo_transcurrido = 0.0

        self.get_logger().info('Analizador de comandos iniciado.')

    def cb_voz(self, msg):
        texto = msg.data.lower()
        self.get_logger().info(f'Texto recibido: {texto}')

        comando_encontrado = None
        # Buscar primero los comandos más largos para evitar falsos positivos
        for palabra in sorted(self.comandos_validos, key=lambda k: -len(k)):
            if palabra.replace('_', ' ') in texto:
                comando_encontrado = palabra
                break

        if comando_encontrado:
            self.get_logger().info(f'Comando detectado: {comando_encontrado}')
            self.iniciar_publicacion(comando_encontrado)
        else:
            self.get_logger().info('Ningun comando valido detectado.')

    def iniciar_publicacion(self, comando):
        self.comando_actual = comando
        self.tiempo_transcurrido = 0.0

        if self.timer_publicacion:
            self.timer_publicacion.cancel()
        self.timer_publicacion = self.create_timer(0.5, self.publicar_comando)

    def publicar_comando(self):
        # Publicar durante 5 segundos y luego parar
        if self.tiempo_transcurrido >= 5.0:
            self.get_logger().info('Publicacion de comando finalizada.')
            if self.timer_publicacion:
                self.timer_publicacion.cancel()
                self.timer_publicacion = None
            self.comando_actual = None
            return

        if self.comando_actual:
            msg = String()
            msg.data = self.comando_actual
            self.pub_comando.publish(msg)

        self.tiempo_transcurrido += 0.5


def main(args=None):
    rclpy.init(args=args)
    nodo = NodoAnalizadorComandos()
    rclpy.spin(nodo)
    nodo.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()
