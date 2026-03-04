import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image
from std_msgs.msg import String
from cv_bridge import CvBridge
import cv2
from ultralytics import YOLO

class NodoDetectorObjetos(Node):
    def __init__(self):
        super().__init__('object_detector_node')

        self.puente_cv = CvBridge()
        self.modelo = YOLO('yolov8n.pt')
        self.detecciones = []

        self.create_subscription(Image, '/oakd/rgb/preview/image_raw', self.cb_imagen, 10)
        self.create_subscription(String, '/voice_command', self.cb_comando, 10)

        self.pub_imagen = self.create_publisher(Image, '/yolo_image_raw', 10)
        self.pub_objetos = self.create_publisher(String, '/detected_objects', 10)

        self.get_logger().info('Detector de objetos iniciado.')

    def cb_imagen(self, msg):
        try:
            imagen_cv = self.puente_cv.imgmsg_to_cv2(msg, desired_encoding='bgr8')
            self.ejecutar_deteccion(imagen_cv)
        except Exception as e:
            self.get_logger().error(f'Error al convertir imagen: {e}')

    def ejecutar_deteccion(self, frame):
        resultados = self.modelo.predict(source=frame, conf=0.5, verbose=False)[0]

        etiquetas_detectadas = []
        frame_anotado = frame.copy()

        for caja in resultados.boxes:
            clase = int(caja.cls[0])
            etiqueta = self.modelo.names[clase]
            confianza = float(caja.conf[0])
            etiquetas_detectadas.append(etiqueta)

            # Dibujar bounding box
            x1, y1, x2, y2 = map(int, caja.xyxy[0])
            cv2.rectangle(frame_anotado, (x1, y1), (x2, y2), (0, 255, 0), 2)
            texto = f'{etiqueta} {confianza:.2f}'
            cv2.putText(frame_anotado, texto, (x1, y1 - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

        self.detecciones = list(set(etiquetas_detectadas))

        # Publicar imagen anotada
        try:
            msg_yolo = self.puente_cv.cv2_to_imgmsg(frame_anotado, encoding='bgr8')
            self.pub_imagen.publish(msg_yolo)
        except Exception as e:
            self.get_logger().error(f'Error al publicar imagen YOLO: {e}')

        # Publicar objetos detectados
        mensaje = f'Veo: {", ".join(self.detecciones)}' if self.detecciones else 'No veo nada.'
        msg_objetos = String()
        msg_objetos.data = mensaje
        self.pub_objetos.publish(msg_objetos)

    def cb_comando(self, msg):
        if msg.data == 'what_do_you_see':
            if self.detecciones:
                self.get_logger().info(f'Veo: {", ".join(self.detecciones)}')
            else:
                self.get_logger().info('No veo nada.')


def main(args=None):
    rclpy.init(args=args)
    nodo = NodoDetectorObjetos()
    rclpy.spin(nodo)
    nodo.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()
