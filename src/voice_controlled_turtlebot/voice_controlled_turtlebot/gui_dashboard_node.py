import sys
import threading
import time
import rclpy
from rclpy.node import Node
from rclpy.executors import MultiThreadedExecutor
from rclpy.qos import qos_profile_sensor_data

from sensor_msgs.msg import Image, Imu, LaserScan, BatteryState
from diagnostic_msgs.msg import DiagnosticArray
from std_msgs.msg import String
from irobot_create_msgs.msg import DockStatus
from cv_bridge import CvBridge

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QTextEdit
)
from PyQt6.QtGui import QImage, QPixmap, QFont, QColor, QPainter
from PyQt6.QtCore import Qt, pyqtSignal, QObject

# Puente de señales thread-safe entre ROS2 y Qt
class PuenteSignales(QObject):
    senal_bateria = pyqtSignal(str)
    senal_temperatura = pyqtSignal(str)
    senal_acople = pyqtSignal(str)
    senal_camara = pyqtSignal(QImage)
    senal_texto_voz = pyqtSignal(str)
    senal_comando_voz = pyqtSignal(str)
    senal_objetos = pyqtSignal(str)
    senal_laser = pyqtSignal(str)
    senal_imu = pyqtSignal(str)

puente = PuenteSignales()


class NodoDashboard(Node):
    def __init__(self):
        super().__init__('turtlebot_gui_dashboard_node')
        self.puente_cv = CvBridge()
        self.cnt_imu = 0
        self.cnt_laser = 0
        self.cnt_camara = 0

        qos_sensor = qos_profile_sensor_data

        # Suscripciones a sensores del robot
        self.create_subscription(BatteryState, '/battery_state', self.cb_bateria, qos_sensor)
        self.create_subscription(DockStatus, '/dock_status', self.cb_acople, qos_sensor)
        self.create_subscription(Imu, '/imu', self.cb_imu, qos_sensor)
        self.create_subscription(LaserScan, '/scan', self.cb_laser, qos_sensor)
        self.create_subscription(Image, '/oakd/rgb/preview/image_raw', self.cb_camara, qos_sensor)
        self.create_subscription(DiagnosticArray, '/diagnostics', self.cb_diagnosticos, qos_sensor)
        self.create_subscription(String, '/voice_text', self.cb_texto_voz, 10)
        self.create_subscription(String, '/voice_command', self.cb_comando_voz, 10)
        self.create_subscription(String, '/detected_objects', self.cb_objetos, 10)

        self.get_logger().info('Dashboard iniciado.')

    def cb_bateria(self, msg):
        porcentaje = int(msg.percentage * 100)
        puente.senal_bateria.emit(f'{porcentaje}%')

    def cb_acople(self, msg):
        estado = 'Acoplado' if msg.is_docked else 'Desacoplado'
        puente.senal_acople.emit(estado)

    def cb_imu(self, msg):
        self.cnt_imu += 1
        info = (f'Acel: ({msg.linear_acceleration.x:.2f}, '
                f'{msg.linear_acceleration.y:.2f}, '
                f'{msg.linear_acceleration.z:.2f})')
        if self.cnt_imu % 10 == 0:
            self.get_logger().debug(f'IMU: {info}')
        puente.senal_imu.emit(info)

    def cb_laser(self, msg):
        self.cnt_laser += 1
        info = f'Rayos: {len(msg.ranges)}, Min: {msg.angle_min:.2f}, Max: {msg.angle_max:.2f}'
        if self.cnt_laser % 5 == 0:
            self.get_logger().debug(f'Laser: {info}')
        puente.senal_laser.emit(info)

    def cb_camara(self, msg):
        try:
            self.cnt_camara += 1
            imagen_cv = self.puente_cv.imgmsg_to_cv2(msg, desired_encoding='rgb8')
            h, w, _ = imagen_cv.shape
            qt_imagen = QImage(imagen_cv.data, w, h, 3 * w, QImage.Format.Format_RGB888)
            if self.cnt_camara % 10 == 0:
                self.get_logger().info(f'Camara: frame {self.cnt_camara} ({w}x{h})')
            puente.senal_camara.emit(qt_imagen)
        except Exception as e:
            self.get_logger().error(f'Error camara: {e}')

    def cb_diagnosticos(self, msg):
        for estado in msg.status:
            if 'temperature' in estado.name.lower():
                for valor in estado.values:
                    if 'temperature' in valor.key.lower():
                        puente.senal_temperatura.emit(f'{valor.value}°C')
                        return

    def cb_texto_voz(self, msg):
        puente.senal_texto_voz.emit(msg.data)

    def cb_comando_voz(self, msg):
        puente.senal_comando_voz.emit(msg.data)

    def cb_objetos(self, msg):
        puente.senal_objetos.emit(msg.data)


class VentanaDashboard(QMainWindow):
    @staticmethod
    def _placeholder(ancho=400, alto=400):
        """Imagen de espera para la camara"""
        px = QPixmap(ancho, alto)
        px.fill(QColor('#0a1a2f'))
        p = QPainter(px)
        p.setPen(QColor('#555'))
        p.setFont(QFont('Arial', 10))
        p.drawText(px.rect(), Qt.AlignmentFlag.AlignCenter, 'Esperando camara...')
        p.end()
        return px

    def __init__(self):
        super().__init__()
        self.setWindowTitle('TurtleBot4 Dashboard')
        self.setGeometry(100, 100, 1200, 800)
        self.setStyleSheet("""
            QMainWindow { background-color: #060e1a; }
            QLabel { color: white; }
            QTextEdit { background-color: #1c2e44; color: white; border: 1px solid #444; }
        """)

        widget_central = QWidget()
        self.setCentralWidget(widget_central)
        layout_principal = QVBoxLayout(widget_central)

        # Barra de estado superior
        layout_estado = QHBoxLayout()
        self.etiq_bateria = QLabel('Bateria: --')
        self.etiq_acople = QLabel('Acople: --')
        self.etiq_imu = QLabel('IMU: --')
        self.etiq_laser = QLabel('Laser: --')
        for etiq in [self.etiq_bateria, self.etiq_acople, self.etiq_imu, self.etiq_laser]:
            etiq.setFont(QFont('Arial', 10))
            layout_estado.addWidget(etiq)
        layout_principal.addLayout(layout_estado)

        # Panel principal: camara + textos
        layout_contenido = QHBoxLayout()

        # Columna izquierda: camara
        layout_izq = QVBoxLayout()
        etiq_camara_titulo = QLabel('Camara')
        etiq_camara_titulo.setFont(QFont('Arial', 12, QFont.Weight.Bold))
        etiq_camara_titulo.setStyleSheet('color: #4ade80;')
        layout_izq.addWidget(etiq_camara_titulo)

        self.pantalla_camara = QLabel()
        self.pantalla_camara.setFixedSize(400, 400)
        self.pantalla_camara.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.pantalla_camara.setPixmap(self._placeholder())
        layout_izq.addWidget(self.pantalla_camara)
        layout_izq.addStretch()

        # Columna central: voz y objetos
        layout_centro = QVBoxLayout()
        for titulo, attr in [('Texto de voz', 'texto_voz'),
                              ('Comando detectado', 'texto_comando'),
                              ('Objetos detectados', 'texto_objetos')]:
            etiq = QLabel(titulo)
            etiq.setFont(QFont('Arial', 12, QFont.Weight.Bold))
            etiq.setStyleSheet('color: #4ade80;')
            layout_centro.addWidget(etiq)
            widget_texto = QTextEdit()
            widget_texto.setReadOnly(True)
            widget_texto.setMaximumHeight(120)
            setattr(self, attr, widget_texto)
            layout_centro.addWidget(widget_texto)
        layout_centro.addStretch()

        layout_contenido.addLayout(layout_izq, 2)
        layout_contenido.addLayout(layout_centro, 2)
        layout_principal.addLayout(layout_contenido)

        # Conectar señales
        puente.senal_bateria.connect(lambda v: self.etiq_bateria.setText(f'Bateria: {v}'))
        puente.senal_acople.connect(lambda v: self.etiq_acople.setText(f'Acople: {v}'))
        puente.senal_imu.connect(lambda v: self.etiq_imu.setText(f'IMU: {v[:35]}...'))
        puente.senal_laser.connect(lambda v: self.etiq_laser.setText(f'Laser: {v[:35]}...'))
        puente.senal_camara.connect(self._actualizar_camara)
        puente.senal_texto_voz.connect(self.texto_voz.setText)
        puente.senal_comando_voz.connect(self.texto_comando.setText)
        puente.senal_objetos.connect(self.texto_objetos.setText)

    def _actualizar_camara(self, qt_imagen):
        pixmap = QPixmap.fromImage(qt_imagen)
        self.pantalla_camara.setPixmap(
            pixmap.scaledToWidth(400, Qt.TransformationMode.SmoothTransformation))


def main(args=None):
    rclpy.init(args=args)
    nodo_ros = NodoDashboard()

    executor = MultiThreadedExecutor(num_threads=4)
    executor.add_node(nodo_ros)

    # ROS2 corre en hilo separado para no bloquear Qt
    hilo_ros = threading.Thread(target=executor.spin, daemon=False)
    hilo_ros.start()

    time.sleep(0.5)

    app = QApplication(sys.argv)
    ventana = VentanaDashboard()
    ventana.show()

    codigo_salida = app.exec()

    executor.shutdown()
    hilo_ros.join(timeout=5)
    rclpy.shutdown()

    sys.exit(codigo_salida)

if __name__ == '__main__':
    main()
