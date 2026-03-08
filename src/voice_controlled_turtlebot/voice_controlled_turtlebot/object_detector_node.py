"""
object_detector_node — YOLO solo cuando se pide por voz ("ana mira", "ana que ves").

En reposo: 0% CPU de inferencia. Solo guarda el último frame de la cámara.
Al recibir 'ver' en /voice_command: ejecuta YOLO una vez y publica resultado.
"""

import threading

import rclpy
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import Image
from std_msgs.msg import String, Bool
from cv_bridge import CvBridge
import cv2
from ultralytics import YOLO


YOLO_ES = {
    'person': 'persona', 'bicycle': 'bicicleta', 'car': 'coche', 'motorcycle': 'moto',
    'airplane': 'avión', 'bus': 'autobús', 'train': 'tren', 'truck': 'camión',
    'boat': 'barco', 'traffic light': 'semáforo', 'fire hydrant': 'hidrante',
    'stop sign': 'señal de stop', 'parking meter': 'parquímetro', 'bench': 'banco',
    'bird': 'pájaro', 'cat': 'gato', 'dog': 'perro', 'horse': 'caballo',
    'sheep': 'oveja', 'cow': 'vaca', 'elephant': 'elefante', 'bear': 'oso',
    'zebra': 'cebra', 'giraffe': 'jirafa', 'backpack': 'mochila', 'umbrella': 'paraguas',
    'handbag': 'bolso', 'tie': 'corbata', 'suitcase': 'maleta', 'frisbee': 'frisbee',
    'skis': 'esquís', 'snowboard': 'snowboard', 'sports ball': 'pelota',
    'kite': 'cometa', 'baseball bat': 'bate', 'baseball glove': 'guante',
    'skateboard': 'monopatín', 'surfboard': 'tabla de surf', 'tennis racket': 'raqueta',
    'bottle': 'botella', 'wine glass': 'copa', 'cup': 'taza', 'fork': 'tenedor',
    'knife': 'cuchillo', 'spoon': 'cuchara', 'bowl': 'cuenco', 'banana': 'plátano',
    'apple': 'manzana', 'sandwich': 'sándwich', 'orange': 'naranja', 'broccoli': 'brócoli',
    'carrot': 'zanahoria', 'hot dog': 'perrito caliente', 'pizza': 'pizza',
    'donut': 'donut', 'cake': 'pastel', 'chair': 'silla', 'couch': 'sofá',
    'potted plant': 'planta', 'bed': 'cama', 'dining table': 'mesa',
    'toilet': 'inodoro', 'tv': 'televisor', 'laptop': 'portátil', 'mouse': 'ratón',
    'remote': 'mando', 'keyboard': 'teclado', 'cell phone': 'móvil',
    'microwave': 'microondas', 'oven': 'horno', 'toaster': 'tostadora',
    'sink': 'fregadero', 'refrigerator': 'nevera', 'book': 'libro',
    'clock': 'reloj', 'vase': 'jarrón', 'scissors': 'tijeras',
    'teddy bear': 'peluche', 'hair drier': 'secador', 'toothbrush': 'cepillo de dientes',
}


class NodoDetectorObjetos(Node):
    def __init__(self):
        super().__init__('object_detector_node')

        self.puente_cv = CvBridge()
        self.modelo = YOLO('yolov8n.pt')

        self._ultimo_frame = None
        self._inferencia_en_curso = False
        self._lock = threading.Lock()

        self.create_subscription(
            Image, '/oakd/rgb/preview/image_raw',
            self.cb_imagen, qos_profile_sensor_data)
        self._tts_activo = False
        self.create_subscription(Bool, '/tts_activo', self._cb_tts, 10)
        self.create_subscription(
            String, '/voice_command', self.cb_comando, 10)

        self.pub_imagen  = self.create_publisher(Image,  '/yolo_image_raw', qos_profile_sensor_data)
        self.pub_objetos = self.create_publisher(String, '/detected_objects', 10)

        self.get_logger().info('Detector iniciado (solo por voz).')

    def cb_imagen(self, msg):
        try:
            frame = self.puente_cv.imgmsg_to_cv2(msg, desired_encoding='bgr8')
            with self._lock:
                self._ultimo_frame = frame
        except Exception as e:
            self.get_logger().error(f'Error imagen: {e}')

    def _cb_tts(self, msg):
        self._tts_activo = msg.data

    def cb_comando(self, msg):
        if self._tts_activo:
            return
        if msg.data.strip() != 'ver':
            return
        if self._inferencia_en_curso:
            return

        with self._lock:
            frame = self._ultimo_frame

        if frame is None:
            return

        threading.Thread(
            target=self._ejecutar_deteccion, args=(frame,), daemon=True).start()

    def _ejecutar_deteccion(self, frame):
        self._inferencia_en_curso = True
        try:
            resultados = self.modelo.predict(source=frame, conf=0.5, verbose=False)[0]

            etiquetas = []
            frame_anotado = frame.copy()

            for caja in resultados.boxes:
                clase    = int(caja.cls[0])
                etiqueta_en = self.modelo.names[clase]
                etiqueta = YOLO_ES.get(etiqueta_en, etiqueta_en)
                conf     = float(caja.conf[0])
                etiquetas.append(etiqueta)

                x1, y1, x2, y2 = map(int, caja.xyxy[0])
                cv2.rectangle(frame_anotado, (x1, y1), (x2, y2), (0, 255, 0), 2)
                cv2.putText(frame_anotado, f'{etiqueta} {conf:.2f}',
                            (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX,
                            0.5, (0, 255, 0), 2)

            texto = (f'Veo: {", ".join(set(etiquetas))}'
                     if etiquetas else 'No veo nada.')

            try:
                self.pub_imagen.publish(
                    self.puente_cv.cv2_to_imgmsg(frame_anotado, encoding='bgr8'))
            except Exception as e:
                self.get_logger().error(f'Error publicando imagen: {e}')

            msg = String()
            msg.data = texto
            self.pub_objetos.publish(msg)
            self.get_logger().info(texto)

        except Exception as e:
            self.get_logger().error(f'Error detección: {e}')
        finally:
            self._inferencia_en_curso = False


def main(args=None):
    rclpy.init(args=args)
    nodo = NodoDetectorObjetos()
    rclpy.spin(nodo)
    nodo.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()
