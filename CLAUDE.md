# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Comandos principales

```bash
# Compilar (usar --symlink-install para que cambios Python no requieran rebuild)
colcon build --packages-select voice_controlled_turtlebot --symlink-install

# Cargar entorno tras compilar
source install/setup.bash

# Lanzar todos los nodos (5 nodos, sin GUI)
ros2 launch voice_controlled_turtlebot voice_controlled_turtlebot.launch.py

# Ejecutar un nodo individualmente
ros2 run voice_controlled_turtlebot mic_listener_node
ros2 run voice_controlled_turtlebot command_parser_node
ros2 run voice_controlled_turtlebot movement_controller_node
ros2 run voice_controlled_turtlebot object_detector_node
ros2 run voice_controlled_turtlebot nodo_dialogo_node
ros2 run voice_controlled_turtlebot gui_dashboard_node  # solo con DISPLAY

# Tests (ament: copyright, flake8, pep257)
colcon test --packages-select voice_controlled_turtlebot
colcon test-result --verbose

# Diagnóstico whisper independiente (sin ROS2)
python3 test_whisper.py
```

## Arquitectura

Pipeline ROS2 Humble con wake word **"ana"**:

```
Micrófono → mic_listener_node → /voice_text → command_parser_node
                                                 ↓ (solo si contiene "ana")
                                              /voice_command
                                     ┌───────────┼───────────────┐
                          movement_controller  object_detector  nodo_dialogo
                          (/cmd_vel)           (/detected_objects) (/robot_respuesta)
```

### Nodos

**`mic_listener_node`** — Hilo dedicado con `arecord` raw streaming. VAD por RMS cada 0.5s; graba cuando RMS ≥ 90. Acumula chunks hasta silencio (1s) o tope (4s). Transcripción in-process con `faster-whisper` (modelo tiny, int8, cargado una vez en RAM; ~2s por clip vs 13s con whisper-cli). Sin subprocess, sin file I/O — audio pasa como numpy array directo. Se pausa durante TTS: mata arecord, espera, reinicia. Auto-detecta micrófono.

**`command_parser_node`** — Requiere wake word **"ana"** en el texto. Normaliza acentos con `unicodedata` (qué→que, atrás→atras) y quita puntuación antes de buscar en el mapa de comandos (frases largas primero). Publica una sola vez. Si no es comando conocido, publica `pregunta:<texto>` para el LLM. Se pausa durante TTS (`/tts_activo`).

**`nodo_dialogo_node`** — Solo escucha `/voice_command` y `/detected_objects`. **Fast path** (<5ms): respuestas canned para comandos conocidos. **LLM path**: `pregunta:...` → Qwen2.5-0.5B-Instruct (Q5_K_M, `n_ctx=128`, `max_tokens=15`, n_threads=2, temperature=0.1). LLM ejecuta en hilo separado. **Detección**: escucha `/detected_objects` y habla el resultado directamente sin LLM ("Veo: persona, silla"). Rechaza comandos mientras `_hablando=True`. **TTS**: offline via `pyttsx3` (rate=180). Publica `/tts_activo` para pausar todos los nodos.

**`movement_controller_node`** — Traduce comandos a `Twist` en `/cmd_vel` (10 Hz). Gestiona acople/desacople via ActionClient (`/dock`, `/undock`). Ignora mensajes `pregunta:` y `wake`. Se pausa durante TTS (`/tts_activo`).

**`object_detector_node`** — YOLO dormido por defecto (0% CPU). Solo ejecuta inferencia YOLOv8n al recibir comando `ver`. Traduce etiquetas YOLO al español con diccionario `YOLO_ES` (80 clases). Guarda último frame de cámara en memoria. Publica en `/detected_objects` y `/yolo_image_raw`. Se pausa durante TTS (`/tts_activo`).

**`gui_dashboard_node`** — Dashboard PyQt6 (excluido del launch para ahorrar CPU). ROS2 en hilo separado con `MultiThreadedExecutor`; señales Qt via `PuenteSignales`. Muestra batería, IMU, láser, cámara, voz, objetos, respuestas y estado emocional.

## Topics principales

| Topic | Tipo | Productor | Consumidores |
|---|---|---|---|
| `/voice_text` | String | mic_listener | command_parser |
| `/voice_command` | String | command_parser | movement_controller, object_detector, nodo_dialogo |
| `/detected_objects` | String | object_detector | nodo_dialogo |
| `/tts_activo` | Bool | nodo_dialogo | mic_listener, command_parser, movement_controller, object_detector |
| `/cmd_vel` | Twist | movement_controller | robot (Create 3) |

## Dependencias externas

- **faster-whisper** — modelo `tiny` con CTranslate2 (int8). Cargado UNA VEZ en RAM al arrancar (~1.4s). Transcripción ~2s por clip directamente desde numpy array (sin file I/O, sin subprocess). Reemplaza whisper.cpp/whisper-cli que tardaba 13s por clip (carga modelo cada vez).
- **Qwen2.5-0.5B-Instruct** — modelo GGUF en `models/qwen2.5-0.5b-instruct-q5_k_m.gguf` (522 MB). Inferencia via `llama-cpp-python`. Reemplaza TinyLlama 1.1B (saturaba CPU) y SmolLM-360M (demasiado débil).
- **YOLOv8n** — `yolov8n.pt` en raíz (6.5 MB, descargado automáticamente por `ultralytics`). Etiquetas traducidas al español.
- **irobot_create_msgs** — mensajes del TurtleBot4 (no en `package.xml`, instalar aparte).
- **pyttsx3** — TTS offline para nodo_dialogo_node (`pip3 install pyttsx3`).
- **PyQt6** — solo para gui_dashboard_node.

## Hardware

- Robot: TurtleBot4 (Create 3), topics sin namespace (antes usaba `/rpi_13` pero no aplica).
- Micrófono: auto-detectado (`default` → `plughw:X,Y`).
- Cámara: OAK-D en `/oakd/rgb/preview/image_raw`.

## Recompilar whisper.cpp

Si cambia la CPU o hay SIGILL:
```bash
cd whisper.cpp
cmake -B build -DGGML_NATIVE=OFF -DGGML_AVX=OFF -DGGML_AVX2=OFF -DGGML_F16C=OFF -DGGML_FMA=OFF
cmake --build build -j$(nproc)
cmake --install build --prefix ../install/whisper.cpp
```

## Cambios 2026-03-08

### LLM: TinyLlama → SmolLM-360M → Qwen2.5-0.5B-Instruct
- TinyLlama 1.1B saturaba CPU. SmolLM-360M (386 MB) demasiado débil (respondía en inglés, repetía preguntas).
- **Qwen2.5-0.5B-Instruct** Q5_K_M (522 MB): buen equilibrio rendimiento/calidad, sigue instrucciones en español.
- n_ctx=128, max_tokens=15, n_threads=2, system prompt: "Eres Ana, un robot asistente. Responde SOLO en español, maximo 5 palabras."

### Normalización de acentos en command_parser
- Whisper transcribe con tildes ("qué ves") pero el mapa de comandos no las tenía → no matcheaba.
- Añadido `unicodedata.normalize('NFKD')` para quitar acentos antes de buscar.
- Añadida limpieza de puntuación suelta (¿, ?, ¡, !, ., ,).
- Nuevas frases de detección: "que estas viendo", "a tu alrededor", "que es lo que ves" → `ver`.

### Todos los nodos se pausan durante TTS
- `command_parser_node`, `movement_controller_node` y `object_detector_node` ahora escuchan `/tts_activo`.
- Descartan comandos mientras el robot habla. Barrera principal en command_parser (ni publica a /voice_command).

### Detección de objetos habla resultado
- `nodo_dialogo_node` suscrito a `/detected_objects` → habla directamente ("Veo: persona, silla") sin LLM.
- Diccionario `YOLO_ES` con 80 clases YOLOv8n traducidas al español.

### Topics corregidos (sin namespace /rpi_13)
- `/rpi_13/cmd_vel` → `/cmd_vel`
- `/rpi_13/dock` → `/dock`, `/rpi_13/undock` → `/undock`
- `/rpi_13/dock_status` → `/dock_status`
- Verificado con `ros2 topic list`: robot publica sin namespace.

### Fix SyntaxError en object_detector_node
- `)` suelto en línea 15 eliminado.

### Logging mejorado
- command_parser: muestra texto original y comando parseado.
- nodo_dialogo: muestra comandos canned y respuestas LLM con pregunta→respuesta.
- movement_controller: muestra comando recibido.
