import os
from launch import LaunchDescription
from launch_ros.actions import Node

def generate_launch_description():
    hay_pantalla = (
        os.environ.get('DISPLAY') is not None or
        os.environ.get('WAYLAND_DISPLAY') is not None
    )

    nodos = [
        Node(package='voice_controlled_turtlebot', executable='mic_listener_node',
             name='mic_listener_node', output='screen'),
        Node(package='voice_controlled_turtlebot', executable='command_parser_node',
             name='command_parser_node', output='screen'),
        Node(package='voice_controlled_turtlebot', executable='movement_controller_node',
             name='movement_controller_node', output='screen'),
        Node(package='voice_controlled_turtlebot', executable='object_detector_node',
             name='object_detector_node', output='screen'),
    ]

    if hay_pantalla:
        nodos.append(Node(
            package='voice_controlled_turtlebot', executable='gui_dashboard_node',
            name='gui_dashboard_node', output='screen'
        ))
    else:
        print('[INFO] Sin pantalla detectada, omitiendo gui_dashboard_node.')

    return LaunchDescription(nodos)
