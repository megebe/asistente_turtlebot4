from launch import LaunchDescription
from launch_ros.actions import Node

def generate_launch_description():

    nodos = [
        Node(package='voice_controlled_turtlebot', executable='mic_listener_node',
             name='mic_listener_node', output='screen'),
        Node(package='voice_controlled_turtlebot', executable='command_parser_node',
             name='command_parser_node', output='screen'),
        Node(package='voice_controlled_turtlebot', executable='movement_controller_node',
             name='movement_controller_node', output='screen'),
        Node(package='voice_controlled_turtlebot', executable='object_detector_node',
             name='object_detector_node', output='screen'),
        Node(package='voice_controlled_turtlebot', executable='nodo_dialogo_node',
             name='nodo_dialogo_node', output='screen'),
        Node(package='prueba_nav', executable='nodo_navegacion',
             name='nodo_navegacion', output='screen'),
    ]

    return LaunchDescription(nodos)
