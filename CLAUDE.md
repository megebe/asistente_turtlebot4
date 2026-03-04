# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Comandos principales

```bash
# Compilar el paquete (desde la raíz del workspace)
colcon build --packages-select voice_controlled_turtlebot

# Cargar el entorno tras compilar
source install/setup.bash

# Lanzar todos los nodos
ros2 launch voice_controlled_turtlebot voice_controlled_turtlebot.launch.py

# Ejecutar un nodo individualmente
ros2 run voice_controlled_turtlebot mic_listener_node
ros2 run voice_controlled_turtlebot command_parser_node
ros2 run voice_controlled_turtlebot movement_controller_node
ros2 run voice_controlled_turtlebot object_detector_node
ros2 run voice_controlled_turtlebot gui_dashboard_node

# Tests (ament: copyright, flake8, pep257)
colcon test --packages-select voice_controlled_turtlebot
colcon test-result --verbose
```

## Arquitectura

Pipeline de nodos ROS2 Humble en cadena lineal:

```
Micrófono → mic_listener_node → /voice_text → command_parser_node → /voice_command → movement_controller_node
                                                                                    ↑
                                              object_detector_node ────────────────┘
                                              gui_dashboard_node (opcional, solo con DISPLAY)
```

**`mic_listener_node`** — graba 4 segundos con `arecord` y transcribe usando `whisper-cli` (whisper.cpp en `/home/m/voice_controlled_turtlebot/whisper.cpp`). Publica texto en `/voice_text`. Período configurable en `self.periodo_timer`.

**`command_parser_node`** — suscribe `/voice_text`, busca palabras clave en `self.comandos_validos` (de más larga a más corta para evitar falsos positivos) y publica el comando en `/voice_command` repetidamente durante 5 segundos a 0.5 s de intervalo.

**`movement_controller_node`** — suscribe `/voice_command` y traduce a `Twist` en `/rpi_13/cmd_vel`. Gestiona acciones de acople/desacople (`/rpi_13/dock`, `/rpi_13/undock`) y foto desde la cámara OAK-D (`/oakd/rgb/preview/image_raw`). El timer a 0.1 s publica continuamente mientras `self.en_movimiento` sea `True`.

**`object_detector_node`** — suscribe la cámara OAK-D, corre YOLOv8n (`yolov8n.pt` en la raíz) en cada frame y publica imagen anotada en `/yolo_image_raw` y lista de objetos en `/detected_objects`.

**`gui_dashboard_node`** — dashboard PyQt6. ROS2 corre en hilo separado (`MultiThreadedExecutor`); la comunicación con Qt es mediante señales PyQt6 a través del objeto global `puente` (`PuenteSeñales`). Solo se lanza si `$DISPLAY` o `$WAYLAND_DISPLAY` están definidos.

## Dependencias externas clave

- **whisper.cpp** — clonado en `whisper.cpp/`, el binario debe estar en `whisper.cpp/build/bin/whisper-cli` y el modelo en `whisper.cpp/models/ggml-base.bin`.
- **YOLOv8n** — modelo `yolov8n.pt` en la raíz del workspace (descargado automáticamente por `ultralytics` la primera vez).
- **irobot_create_msgs** — mensajes propietarios del TurtleBot4 (no en `package.xml`, deben instalarse aparte).
- **PyQt6** — para el dashboard; no disponible headless.

## Configuración del hardware

- Robot identificado como `/rpi_13` (prefijo de todos sus topics: `/rpi_13/cmd_vel`, `/rpi_13/dock`, etc.).
- Micrófono: `plughw:0,1` — cambiar `self.dispositivo_mic` en `mic_listener_node.py` si es necesario.
- Cámara: OAK-D en `/oakd/rgb/preview/image_raw`.
