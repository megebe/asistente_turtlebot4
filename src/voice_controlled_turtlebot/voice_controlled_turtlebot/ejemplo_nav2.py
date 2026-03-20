import rclpy
from rclpy.node import Node
from geometry_msgs.msg import PoseStamped
from nav2_simple_commander.robot_navigator import BasicNavigator
import math

class NodoDestinoNombrado(Node):
    def __init__(self):
        super().__init__('nodo_destino')
        self.navigator = BasicNavigator()
        self.navigator.waitUntilNav2Active()
        # Definir puntos de interés en coordenadas (x, y, yaw)
        self.puntos = {
            "salon": (1.0,  2.5, 0.0),
            "cocina": (4.0, -1.0, math.pi/2)
        }
        # Aquí se puede crear un servicio o suscriptor para recibir el destino

    def ir_a_destino(self, nombre: str):
        if nombre in self.puntos:
            x, y, yaw = self.puntos[nombre]
            goal = PoseStamped()
            goal.header.frame_id = "map"
            goal.pose.position.x = x
            goal.pose.position.y = y
            # Convertir yaw a quaternion (solo orientación en Z)
            qz = math.sin(yaw/2.0)
            qw = math.cos(yaw/2.0)
            goal.pose.orientation.z = qz
            goal.pose.orientation.w = qw
            self.get_logger().info(f"Enviando objetivo a {nombre}: x={x:.2f}, y={y:.2f}")
            self.navigator.goToPose(goal)
        else:
            self.get_logger().error(f"Punto desconocido: {nombre}")

def main(args=None):
    rclpy.init(args=args)
    nodo = NodoDestinoNombrado()
    # Ejemplo: navegar al salón
    nodo.ir_a_destino("salon")
    rclpy.spin(nodo)
    nodo.destroy_node()
    rclpy.shutdown()
