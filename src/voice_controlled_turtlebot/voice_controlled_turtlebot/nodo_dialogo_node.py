"""
nodo_dialogo_node — respuestas de voz.
Respuestas canned para comandos, LLM para preguntas libres.
_hablar() SIEMPRE en thread para no bloquear el executor.
"""

import threading

import pyttsx3
import rclpy
from rclpy.node import Node
from std_msgs.msg import String, Bool

SYSTEM_PROMPT = 'Eres Ana, un robot asistente. Responde SOLO en español, maximo 5 palabras.'

RESPUESTAS_RAPIDAS = {
    'adelante': 'Adelante.',
    'atras': 'Atras.',
    'izquierda': 'Izquierda.',
    'derecha': 'Derecha.',
    'parar': 'Parado.',
    'girar': 'Giro.',
    'acoplar': 'Acoplando.',
    'desacoplar': 'Desacoplando.',
    'tomar_foto': 'Foto.',
    'volver_a_base': 'Base.',
    'buscar_objeto': 'Buscando.',
    'repetir': 'Repito.',
    'sacudir': 'Sacudida.',
    'wake': 'Dime.',
    'ver': 'Mirando.',
}


class NodoDialogo(Node):
    def __init__(self):
        super().__init__('nodo_dialogo_node')

        self.llm = None
        self._hablando = False
        self._lock_tts = threading.Lock()

        threading.Thread(target=self._cargar_modelo, daemon=True).start()

        # TTS — inicializar en hilo de TTS para evitar problemas de threading
        self._tts = None
        self._tts_listo = threading.Event()
        threading.Thread(target=self._init_tts, daemon=True).start()

        self.pub_tts_activo = self.create_publisher(Bool, '/tts_activo', 10)
        self.create_subscription(String, '/voice_command', self.cb_comando, 10)
        self.create_subscription(String, '/detected_objects', self.cb_objetos, 10)

        self.get_logger().info('Dialogo listo.')

    def _init_tts(self):
        self._tts = pyttsx3.init()
        self._tts.setProperty('rate', 180)
        voces = self._tts.getProperty('voices')
        for v in voces:
            if 'spanish' in v.name.lower() or 'espa' in v.name.lower():
                self._tts.setProperty('voice', v.id)
                break
        self._tts_listo.set()

    def _cargar_modelo(self):
        try:
            from llama_cpp import Llama
            self.llm = Llama(
                model_path='/home/m/voice_controlled_turtlebot/models/qwen2.5-0.5b-instruct-q5_k_m.gguf',
                n_ctx=128,
                n_threads=2,
                verbose=False,
            )
            self.get_logger().info('LLM cargado.')
        except Exception as e:
            self.get_logger().error(f'LLM: {e}')

    # ------------------------------------------------------------------
    # Callback — NUNCA bloquea (todo se lanza en thread)
    # ------------------------------------------------------------------

    def cb_objetos(self, msg):
        """Resultado del detector — hablar directamente sin LLM."""
        texto = msg.data.strip()
        if texto:
            self.get_logger().info(f'Objetos: "{texto}"')
            threading.Thread(
                target=self._hablar, args=(texto,),
                daemon=True).start()

    def cb_comando(self, msg):
        dato = msg.data.strip().lower()
        if not dato or self._hablando:
            return

        if dato in RESPUESTAS_RAPIDAS:
            self.get_logger().info(f'Comando: {dato} → "{RESPUESTAS_RAPIDAS[dato]}"')
            threading.Thread(
                target=self._hablar, args=(RESPUESTAS_RAPIDAS[dato],),
                daemon=True).start()
            return

        if dato.startswith('pregunta:'):
            pregunta = dato[len('pregunta:'):].strip()
            if pregunta:
                threading.Thread(
                    target=self._llm_responder, args=(pregunta,),
                    daemon=True).start()
            else:
                threading.Thread(
                    target=self._hablar, args=('Dime.',),
                    daemon=True).start()
            return

    def _llm_responder(self, pregunta):
        if self.llm is None:
            self._hablar('Cargando.')
            return

        try:
            salida = self.llm.create_chat_completion(
                messages=[
                    {'role': 'system', 'content': SYSTEM_PROMPT},
                    {'role': 'user', 'content': pregunta},
                ],
                max_tokens=15,
                temperature=0.1,
            )
            respuesta = salida['choices'][0]['message']['content'].strip()
            if not respuesta:
                respuesta = 'Entendido.'
            if respuesta[-1] not in '.!?':
                respuesta += '.'
            self.get_logger().info(f'LLM: "{pregunta}" → "{respuesta}"')
            self._hablar(respuesta)
        except Exception as e:
            self.get_logger().error(f'LLM: {e}')

    # ------------------------------------------------------------------
    # TTS — siempre en thread, serializado con lock
    # ------------------------------------------------------------------

    def _hablar(self, texto):
        with self._lock_tts:
            self._hablando = True
            activo = Bool()
            activo.data = True
            self.pub_tts_activo.publish(activo)

            self._tts_listo.wait()
            try:
                self._tts.say(texto)
                self._tts.runAndWait()
            except Exception as e:
                self.get_logger().error(f'TTS: {e}')
            finally:
                self._hablando = False
                activo.data = False
                self.pub_tts_activo.publish(activo)


def main(args=None):
    rclpy.init(args=args)
    nodo = NodoDialogo()
    rclpy.spin(nodo)
    nodo.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()
