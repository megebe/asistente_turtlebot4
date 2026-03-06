"""
nodo_dialogo_node — cerebro conversacional de Turty.

Escucha /voice_command (ya filtrado por wake word "ana"):
  • Comandos conocidos → respuesta instantánea (<5 ms)
  • 'wake' (solo dijo "ana") → "¿Sí? Dime."
  • 'pregunta:...' → LLM en hilo separado
  • 'ver' → respuesta basada en objetos detectados
"""

import threading
import time

import rclpy
from rclpy.node import Node
from std_msgs.msg import String
from sensor_msgs.msg import BatteryState

RUTA_MODELO = '/home/m/voice_controlled_turtlebot/models/tinyllama-1.1b-chat-v1.0.Q4_K_M.gguf'

SYSTEM_PROMPT = (
    'Eres Turty, un robot asistente amable. '
    'Responde SIEMPRE con UNA frase muy corta en español. '
    'Estado: {estado_emocional}. Veo: {objetos_detectados}.'
)

RESPUESTAS_RAPIDAS = {
    'adelante':      '¡Voy hacia adelante!',
    'atras':         'Marcha atrás.',
    'izquierda':     'Girando a la izquierda.',
    'derecha':       'Girando a la derecha.',
    'parar':         'Me detengo.',
    'girar':         'Giro sobre mí mismo.',
    'acoplar':       'Voy a acoplarme.',
    'desacoplar':    'Me desacoplo.',
    'tomar_foto':    'Foto tomada.',
    'volver_a_base': 'Volviendo a la base.',
    'buscar_objeto': 'Iniciando búsqueda.',
    'repetir':       'Repitiendo.',
    'sacudir':       '¡Sacudiéndome!',
    'wake':          '¿Sí? Dime.',
}

DURACION_ACTIVO = 10.0
BATERIA_BAJA    = 0.20
MAX_TURNOS      = 2


class NodoDialogo(Node):
    def __init__(self):
        super().__init__('nodo_dialogo_node')

        self.estado_emocional   = 'neutral'
        self._t_activo          = 0.0
        self._bateria_baja      = False
        self._persona_detectada = False
        self.objetos_detectados = 'nada en particular'
        self.historial          = []
        self._inferencia_activa = False

        self.llm = None
        threading.Thread(target=self._cargar_modelo, daemon=True).start()

        self.pub_respuesta = self.create_publisher(String, '/robot_respuesta', 10)
        self.pub_estado    = self.create_publisher(String, '/estado_emocional', 10)

        self.create_subscription(String,       '/voice_command',    self.cb_comando, 10)
        self.create_subscription(String,       '/detected_objects', self.cb_objetos, 10)
        self.create_subscription(BatteryState, '/battery_state',    self.cb_bateria, 10)

        self.create_timer(1.0, self._tick_estado)

        self.get_logger().info('NodoDialogo iniciado.')

    def _cargar_modelo(self):
        try:
            from llama_cpp import Llama
            self.llm = Llama(
                model_path=RUTA_MODELO,
                n_ctx=256,
                n_threads=4,
                verbose=False,
            )
            self.get_logger().info('LLM cargado.')
        except Exception as e:
            self.get_logger().error(f'No se pudo cargar LLM: {e}')

    # ------------------------------------------------------------------
    # Único callback: todo llega por /voice_command (ya filtrado por wake word)
    # ------------------------------------------------------------------

    def cb_comando(self, msg):
        dato = msg.data.strip()
        if not dato:
            return

        self._t_activo = time.monotonic()
        self._actualizar_estado('activo')

        # Pregunta libre → LLM
        if dato.startswith('pregunta:'):
            pregunta = dato[len('pregunta:'):].strip()
            if pregunta and not self._inferencia_activa:
                threading.Thread(
                    target=self._inferir, args=(pregunta,), daemon=True).start()
            elif self._inferencia_activa:
                self.get_logger().warn('LLM ocupado.')
            return

        # Comando 'ver' → respuesta basada en visión
        if dato == 'ver':
            self._publicar_respuesta(f'{self.objetos_detectados}.')
            self.get_logger().info(f'[FAST] ver → {self.objetos_detectados}')
            return

        # Comando conocido → respuesta instantánea
        if dato in RESPUESTAS_RAPIDAS:
            respuesta = RESPUESTAS_RAPIDAS[dato]
            self._publicar_respuesta(respuesta)
            self.get_logger().info(f'[FAST] {dato} → {respuesta}')
            return

        self.get_logger().warn(f'Comando desconocido: {dato}')

    # ------------------------------------------------------------------
    # Contexto
    # ------------------------------------------------------------------

    def cb_objetos(self, msg):
        objetos = msg.data.strip()
        if objetos:
            self.objetos_detectados = objetos
            self._persona_detectada = 'persona' in objetos.lower()
        else:
            self.objetos_detectados = 'nada en particular'
            self._persona_detectada = False

    def cb_bateria(self, msg):
        self._bateria_baja = msg.percentage < BATERIA_BAJA

    # ------------------------------------------------------------------
    # Estado emocional
    # ------------------------------------------------------------------

    def _tick_estado(self):
        if self._bateria_baja:
            nuevo = 'bajo'
        elif self.estado_emocional == 'activo' and \
                time.monotonic() - self._t_activo < DURACION_ACTIVO:
            nuevo = 'activo'
        elif self._persona_detectada:
            nuevo = 'atento'
        else:
            nuevo = 'neutral'
        self._actualizar_estado(nuevo)

    def _actualizar_estado(self, nuevo):
        if self.estado_emocional != nuevo:
            self.estado_emocional = nuevo
            self.get_logger().info(f'Estado: {nuevo}')
        msg = String()
        msg.data = self.estado_emocional
        self.pub_estado.publish(msg)

    # ------------------------------------------------------------------
    # LLM (solo para preguntas libres)
    # ------------------------------------------------------------------

    def _inferir(self, texto):
        if self.llm is None:
            self._publicar_respuesta('Aún estoy cargando mi cerebro, espera un momento.')
            return

        self._inferencia_activa = True
        try:
            system_content = SYSTEM_PROMPT.format(
                estado_emocional=self.estado_emocional,
                objetos_detectados=self.objetos_detectados,
            )
            mensajes = [{'role': 'system', 'content': system_content}]
            mensajes.extend(self.historial)
            mensajes.append({'role': 'user', 'content': texto})

            salida = self.llm.create_chat_completion(
                messages=mensajes,
                max_tokens=30,
                stop=['\n'],
                temperature=0.5,
            )
            respuesta = salida['choices'][0]['message']['content'].strip()
            if not respuesta:
                respuesta = 'Entendido.'
            if respuesta[-1] not in '.!?':
                respuesta += '.'

            self.historial.append({'role': 'user',      'content': texto})
            self.historial.append({'role': 'assistant', 'content': respuesta})
            if len(self.historial) > MAX_TURNOS * 2:
                self.historial = self.historial[-(MAX_TURNOS * 2):]

            self._publicar_respuesta(respuesta)
            self.get_logger().info(f'[LLM] {respuesta}')

        except Exception as e:
            self.get_logger().error(f'Error LLM: {e}')
        finally:
            self._inferencia_activa = False

    def _publicar_respuesta(self, texto):
        msg = String()
        msg.data = texto
        self.pub_respuesta.publish(msg)


def main(args=None):
    rclpy.init(args=args)
    nodo = NodoDialogo()
    try:
        rclpy.spin(nodo)
    except KeyboardInterrupt:
        pass
    finally:
        nodo.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
