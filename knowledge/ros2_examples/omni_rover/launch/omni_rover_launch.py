"""
Generated OMNI ROS2 launch file.
"""

from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():
    return LaunchDescription([
        Node(
            package="omni_rover",
            executable="motor_control_node",
            name="motor_control_node",
            output="screen",
        ),
        Node(
            package="omni_rover",
            executable="distance_sensor_node",
            name="distance_sensor_node",
            output="screen",
        ),
        Node(
            package="omni_rover",
            executable="imu_node",
            name="imu_node",
            output="screen",
        ),
        Node(
            package="omni_rover",
            executable="camera_node",
            name="camera_node",
            output="screen",
        ),
        Node(
            package="omni_rover",
            executable="navigation_node",
            name="navigation_node",
            output="screen",
        ),
    ])
