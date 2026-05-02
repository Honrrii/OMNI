from setuptools import setup

package_name = "omni_rover"

setup(
    name=package_name,
    version="0.0.1",
    packages=[package_name],
    data_files=[
        ("share/ament_index/resource_index/packages", ["resource/" + package_name]),
        ("share/" + package_name, ["package.xml"]),
        ("share/" + package_name + "/launch", ["launch/omni_rover_launch.py"]),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="Henry Valladares",
    maintainer_email="henry@example.com",
    description="Generated ROS2 package scaffold from OMNI Command.",
    license="MIT",
    tests_require=["pytest"],
    entry_points={
        "console_scripts": [
            "motor_control_node = omni_rover.motor_control_node:main",
            "distance_sensor_node = omni_rover.distance_sensor_node:main",
            "imu_node = omni_rover.imu_node:main",
            "camera_node = omni_rover.camera_node:main",
            "navigation_node = omni_rover.navigation_node:main",
        ],
    },
)
