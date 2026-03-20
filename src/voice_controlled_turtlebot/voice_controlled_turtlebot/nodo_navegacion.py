#!/usr/bin/env python3
import rclpy
import math
from geometry_msgs.msg import PoseStamped
from nav2_simple_commander.robot_navigator import BasicNavigator, TaskResult

POSES = {
    "entrada": ( 0.217, -0.669,  1.620),
    "salon"  : ( 2.692,  7.044, -1.533),
    "cocina" : (-0.629,  9.574, -1.476),
}

def make_pose(navigator, x, y, yaw):
    p = PoseStamped()
    p.header.frame_id = "map"
    p.header.stamp = navigator.get_clock().now().to_msg()
    p.pose.position.x = x
    p.pose.position.y = y
    p.pose.orientation.z = math.sin(yaw / 2)
    p.pose.orientation.w = math.cos(yaw / 2)
    return p

def main():
    rclpy.init()
    navigator = BasicNavigator()

    current = "entrada"
    x, y, yaw = POSES[current]
    print(f"[INFO] Estableciendo pose inicial: {current}")
    navigator.setInitialPose(make_pose(navigator, x, y, yaw))
    navigator.waitUntilNav2Active()
    print("[INFO] Nav2 activo.\n")

    destinos = [d for d in POSES if d != current]
    print(f"Destinos disponibles: {destinos}")

    while True:
        try:
            dest = input("\n¿A dónde vamos? (salon / cocina / salir): ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            break

        if dest == "salir":
            break

        if dest not in POSES:
            print(f"[ERROR] '{dest}' no existe. Opciones: {list(POSES.keys())}")
            continue

        if dest == current:
            print(f"[INFO] Ya estás en {dest}.")
            continue

        x, y, yaw = POSES[dest]
        print(f"[INFO] Navegando a {dest}...")
        navigator.goToPose(make_pose(navigator, x, y, yaw))

        while not navigator.isTaskComplete():
            feedback = navigator.getFeedback()
            if feedback:
                print(f"  Distancia restante: {feedback.distance_remaining:.2f} m", end="\r")

        result = navigator.getResult()
        if result == TaskResult.SUCCEEDED:
            current = dest
            print(f"\n[OK] Llegado a {current}. Nueva pose inicial guardada.")
        elif result == TaskResult.CANCELED:
            print("\n[WARN] Navegación cancelada.")
        else:
            print("\n[ERROR] Navegación fallida.")

    navigator.lifecycleShutdown()
    rclpy.shutdown()

if __name__ == "__main__":
    main()