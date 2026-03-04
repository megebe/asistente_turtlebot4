import rclpy
from rclpy.node import Node
from std_msgs.msg import String
from geometry_msgs.msg import Twist
from rclpy.action import ActionClient
from irobot_create_msgs.action import Dock, Undock
from irobot_create_msgs.msg import DockStatus
from sensor_msgs.msg import Image
from cv_bridge import CvBridge
import cv2
import os

class NodoControlMovimiento(Node):
    def __init__(self):
        super().__init__('movement_controller_node')

        self.create_subscription(String, '/voice_command', self.cb_comando, 10)

        self.pub_cmd_vel = self.create_publisher(Twist, '/rpi_13/cmd_vel', 10)

        self.cliente_acoplar = ActionClient(self, Dock, '/rpi_13/dock')
        self.cliente_desacoplar = ActionClient(self, Undock, '/rpi_13/undock')

        self.esta_acoplado = None
        self.create_subscription(DockStatus, '/rpi_13/dock_status', self.cb_estado_acople, 10)

        self.acoplando = False
        self.desacoplando = False
        self.ultimo_objetivo = None  # 'acoplar', 'desacoplar' o None

        self.create_subscription(Image, '/oakd/rgb/preview/image_raw', self.cb_imagen, 10)
        self.puente_cv = CvBridge()
        self.ultima_imagen = None

        self.twist_actual = Twist()
        self.en_movimiento = False
        self.create_timer(0.1, self.publicar_movimiento)

        self.get_logger().info('Control de movimiento iniciado.')

    def cb_estado_acople(self, msg):
        self.esta_acoplado = msg.is_docked

    def cb_imagen(self, msg):
        self.ultima_imagen = self.puente_cv.imgmsg_to_cv2(msg, desired_encoding='bgr8')

    def cb_comando(self, msg):
        comando = msg.data.lower()
        self.twist_actual = Twist()
        self.en_movimiento = False

        if comando == 'move_forward':
            self.twist_actual.linear.x = 0.1
            self.en_movimiento = True
        elif comando == 'move_backward':
            self.twist_actual.linear.x = -0.1
            self.en_movimiento = True
        elif comando == 'turn_left':
            self.twist_actual.angular.z = 0.33
            self.en_movimiento = True
        elif comando == 'turn_right':
            self.twist_actual.angular.z = -0.33
            self.en_movimiento = True
        elif comando == 'spin':
            self.twist_actual.angular.z = 1.0
            self.en_movimiento = True
        elif comando == 'shake':
            self.iniciar_sacudida()
        elif comando == 'stop':
            self.detener_robot()
        elif comando == 'dock':
            self.enviar_objetivo_acoplar()
        elif comando == 'undock':
            self.enviar_objetivo_desacoplar()
        elif comando == 'take_a_picture':
            self.guardar_foto()
        elif comando in ['look_for_object', 'go_to_object', 'return_to_base', 'scan']:
            self.get_logger().info(f'Comando no manejado aqui: {comando}')
        else:
            self.get_logger().info(f'Comando desconocido: {comando}')

    def publicar_movimiento(self):
        if self.en_movimiento:
            self.pub_cmd_vel.publish(self.twist_actual)

    def detener_robot(self):
        self.en_movimiento = False
        self.pub_cmd_vel.publish(Twist())
        self.get_logger().info('Robot detenido.')

    def iniciar_sacudida(self):
        self.get_logger().info('Iniciando sacudida.')
        self.secuencia_sacudida = [(-1.0, 5), (1.0, 5), (-1.0, 5), (1.0, 5)]
        self.indice_sacudida = 0
        self.timer_sacudida = self.create_timer(0.5, self.paso_sacudida)

    def paso_sacudida(self):
        if self.indice_sacudida < len(self.secuencia_sacudida):
            vel_angular, _ = self.secuencia_sacudida[self.indice_sacudida]
            self.twist_actual = Twist()
            self.twist_actual.angular.z = vel_angular
            self.pub_cmd_vel.publish(self.twist_actual)
            self.indice_sacudida += 1
        else:
            self.timer_sacudida.cancel()
            self.detener_robot()

    def enviar_objetivo_acoplar(self):
        if self.ultimo_objetivo == 'acoplar':
            self.get_logger().warn('Acople ya enviado.')
            return
        if self.esta_acoplado is True:
            self.get_logger().warn('Ya esta acoplado.')
            return
        if self.acoplando:
            self.get_logger().warn('Acoplando en progreso.')
            return

        if not self.cliente_acoplar.wait_for_server(timeout_sec=2.0):
            self.get_logger().error('Servidor de acople no disponible.')
            return

        self.get_logger().info('Enviando objetivo: acoplar.')
        self.acoplando = True
        self.ultimo_objetivo = 'acoplar'
        futuro = self.cliente_acoplar.send_goal_async(Dock.Goal())
        futuro.add_done_callback(self.manejar_resultado_acople)

    def manejar_resultado_acople(self, futuro):
        manejador = futuro.result()
        if not manejador.accepted:
            self.get_logger().warn('Objetivo de acople rechazado.')
            self.acoplando = False
            return
        self.get_logger().info('Objetivo de acople aceptado.')
        manejador.get_result_async().add_done_callback(lambda f: self.finalizar_acople())

    def finalizar_acople(self):
        self.get_logger().info('Acople completado.')
        self.acoplando = False

    def enviar_objetivo_desacoplar(self):
        if self.ultimo_objetivo == 'desacoplar':
            self.get_logger().warn('Desacople ya enviado.')
            return
        if self.esta_acoplado is False:
            self.get_logger().warn('Ya esta desacoplado.')
            return
        if self.desacoplando:
            self.get_logger().warn('Desacoplando en progreso.')
            return

        if not self.cliente_desacoplar.wait_for_server(timeout_sec=2.0):
            self.get_logger().error('Servidor de desacople no disponible.')
            return

        self.get_logger().info('Enviando objetivo: desacoplar.')
        self.desacoplando = True
        self.ultimo_objetivo = 'desacoplar'
        futuro = self.cliente_desacoplar.send_goal_async(Undock.Goal())
        futuro.add_done_callback(self.manejar_resultado_desacople)

    def manejar_resultado_desacople(self, futuro):
        manejador = futuro.result()
        if not manejador.accepted:
            self.get_logger().warn('Objetivo de desacople rechazado.')
            self.desacoplando = False
            return
        self.get_logger().info('Objetivo de desacople aceptado.')
        manejador.get_result_async().add_done_callback(lambda f: self.finalizar_desacople())

    def finalizar_desacople(self):
        self.get_logger().info('Desacople completado.')
        self.desacoplando = False

    def guardar_foto(self):
        if self.ultima_imagen is not None:
            ruta = os.path.expanduser('~/voice_controlled_turtlebot/src/snapshot.png')
            cv2.imwrite(ruta, self.ultima_imagen)
            self.get_logger().info(f'Foto guardada: {ruta}')
        else:
            self.get_logger().warn('Aun no se ha recibido imagen.')


def main(args=None):
    rclpy.init(args=args)
    nodo = NodoControlMovimiento()
    rclpy.spin(nodo)
    nodo.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()
