from setuptools import find_packages, setup

nombre_paquete = 'voice_controlled_turtlebot'

setup(
    name=nombre_paquete,
    version='0.0.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + nombre_paquete]),
        ('share/' + nombre_paquete, ['package.xml']),
        ('share/voice_controlled_turtlebot/launch', ['launch/voice_controlled_turtlebot.launch.py']),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='m',
    maintainer_email='todo@udc.es',
    description='Asistente robótico autónomo con interacción afectiva — TFM UDC',
    license='Apache-2.0',
    entry_points={
        'console_scripts': [
            'mic_listener_node = voice_controlled_turtlebot.mic_listener_node:main',
            'command_parser_node = voice_controlled_turtlebot.command_parser_node:main',
            'movement_controller_node = voice_controlled_turtlebot.movement_controller_node:main',
            'object_detector_node = voice_controlled_turtlebot.object_detector_node:main',
            'gui_dashboard_node = voice_controlled_turtlebot.gui_dashboard_node:main',
            'nodo_dialogo_node = voice_controlled_turtlebot.nodo_dialogo_node:main',
        ],
    },
)
