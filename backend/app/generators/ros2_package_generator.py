from pathlib import Path
from typing import Any, Dict, List
import re


# ---------------------------------------------------------
# Naming Helpers
# ---------------------------------------------------------
def safe_name(value: Any, fallback: str = "omni_robot") -> str:
    text = str(value or fallback).lower().strip()
    text = re.sub(r"[^a-z0-9_]+", "_", text)
    text = re.sub(r"_+", "_", text).strip("_")

    if not text:
        return fallback

    if text[0].isdigit():
        text = f"pkg_{text}"

    return text


def safe_node_name(value: Any, fallback: str = "omni_node") -> str:
    name = safe_name(value, fallback)

    if not name.endswith("_node"):
        name = f"{name}_node"

    return name


def infer_python_class_name(node_name: str) -> str:
    parts = safe_name(node_name).replace("_node", "").split("_")
    class_name = "".join(part.capitalize() for part in parts if part)

    if not class_name:
        class_name = "Omni"

    return f"{class_name}Node"


def normalize_list(value: Any) -> List[Any]:
    if isinstance(value, list):
        return value

    if value is None:
        return []

    return [value]


def clean_parameters(parameters: Any) -> List[str]:
    blocked = {
        "",
        "none",
        "null",
        "unknown",
        "n/a",
        "na",
        "tbd",
        "todo",
        "not specified",
        "not_defined",
    }

    cleaned = []

    for parameter in normalize_list(parameters):
        name = str(parameter or "").strip()

        if name.lower() in blocked:
            continue

        cleaned.append(safe_name(name, "parameter"))

    return cleaned



# ---------------------------------------------------------
# Morphology helpers
# ---------------------------------------------------------


def extract_morphology_plan(mission_result: Dict[str, Any]) -> Dict[str, Any]:
    artifacts = mission_result.get("artifacts", {}) or {}

    if not isinstance(artifacts, dict):
        return {}

    morphology_plan = artifacts.get("morphology_plan", {})
    return morphology_plan if isinstance(morphology_plan, dict) else {}


def morphology_ros2_intent(morphology_plan: Dict[str, Any]) -> Dict[str, Any]:
    ros2_intent = morphology_plan.get("ros2_intent", {})

    if not isinstance(ros2_intent, dict):
        return {}

    return ros2_intent


def append_unique_dict_by_name(
    items: List[Dict[str, Any]],
    new_item: Dict[str, Any],
) -> None:
    new_name = str(new_item.get("name", "")).strip()

    if not new_name:
        return

    for item in items:
        if str(item.get("name", "")).strip() == new_name:
            return

    items.append(new_item)


def ensure_node_parameter(node: Dict[str, Any], parameter: str) -> None:
    parameters = clean_parameters(node.get("parameters"))

    if parameter not in parameters:
        parameters.append(parameter)

    node["parameters"] = parameters


def add_morphology_ros2_nodes_and_topics(
    cleaned_nodes: List[Dict[str, Any]],
    cleaned_topics: List[Dict[str, Any]],
    morphology_plan: Dict[str, Any],
) -> None:
    ros2_intent = morphology_ros2_intent(morphology_plan)

    if not ros2_intent:
        return

    recommended_nodes = normalize_list(ros2_intent.get("recommended_nodes"))
    recommended_topics = normalize_list(ros2_intent.get("recommended_topics"))

    topic_type_hints = {
        "/cmd_vel": "geometry_msgs/Twist",
        "/odom": "nav_msgs/Odometry",
        "/imu/data": "sensor_msgs/Imu",
        "/battery_state": "sensor_msgs/BatteryState",
        "/head_camera/image_raw": "sensor_msgs/Image",
        "/camera/image_raw": "sensor_msgs/Image",
        "/scan": "sensor_msgs/LaserScan",
        "/appendage/joint_states": "sensor_msgs/JointState",
        "/appendage/joint_commands": "trajectory_msgs/JointTrajectory",
    }

    for topic_name in recommended_topics:
        topic_name = str(topic_name).strip()

        if not topic_name:
            continue

        append_unique_dict_by_name(
            cleaned_topics,
            {
                "name": topic_name,
                "message_type": topic_type_hints.get(topic_name, "std_msgs/String"),
                "purpose": "Topic recommended by morphology_plan.ros2_intent.",
            },
        )

    for node_name in recommended_nodes:
        node_name = safe_node_name(node_name)

        publishes: List[str] = []
        subscribes: List[str] = []

        if "camera" in node_name:
            publishes.append("/head_camera/image_raw")
        elif "imu" in node_name:
            publishes.append("/imu/data")
        elif "battery" in node_name:
            publishes.append("/battery_state")
        elif "appendage" in node_name:
            publishes.append("/appendage/joint_states")
            subscribes.append("/appendage/joint_commands")
        elif "locomotion" in node_name or "controller" in node_name:
            subscribes.append("/cmd_vel")
        elif "fusion" in node_name:
            subscribes.extend(["/imu/data", "/head_camera/image_raw"])

        node = {
            "name": node_name,
            "language": "python",
            "purpose": "Node recommended by morphology_plan.ros2_intent.",
            "publishes": publishes,
            "subscribes": subscribes,
            "parameters": ["use_sim_time"],
        }

        append_unique_dict_by_name(cleaned_nodes, node)

    for node in cleaned_nodes:
        ensure_node_parameter(node, "use_sim_time")


# ---------------------------------------------------------
# ROS2 Plan Normalization
# ---------------------------------------------------------
def normalize_ros2_plan(mission_result: Dict[str, Any]) -> Dict[str, Any]:
    artifacts = mission_result.get("artifacts", {}) or {}
    plan = artifacts.get("ros2_package_plan", {}) or {}
    graph = artifacts.get("ros2_node_graph", {}) or {}
    morphology_plan = extract_morphology_plan(mission_result)

    if not isinstance(plan, dict):
        plan = {}

    if not isinstance(graph, dict):
        graph = {}

    package_name = safe_name(plan.get("package_name"), "omni_robot")

    nodes = normalize_list(plan.get("nodes"))
    topics = normalize_list(plan.get("topics"))
    launch_files = normalize_list(plan.get("launch_files"))

    cleaned_nodes = []

    for node in nodes:
        if not isinstance(node, dict):
            continue

        cleaned_nodes.append(
            {
                "name": safe_node_name(node.get("name")),
                "language": node.get("language", "python"),
                "purpose": node.get("purpose", "Generated OMNI ROS2 node."),
                "publishes": normalize_list(node.get("publishes")),
                "subscribes": normalize_list(node.get("subscribes")),
                "parameters": clean_parameters(node.get("parameters")),
            }
        )

    if not cleaned_nodes:
        graph_nodes = graph.get("nodes", []) or []

        for item in graph_nodes:
            if not isinstance(item, dict):
                continue

            cleaned_nodes.append(
                {
                    "name": safe_node_name(item.get("label") or item.get("id")),
                    "language": "python",
                    "purpose": item.get("description", "Generated ROS2 node."),
                    "publishes": [],
                    "subscribes": [],
                    "parameters": [],
                }
            )

    if not cleaned_nodes:
        cleaned_nodes = [
            {
                "name": "omni_supervisor_node",
                "language": "python",
                "purpose": "Starter OMNI ROS2 supervisor node.",
                "publishes": ["/omni/status"],
                "subscribes": [],
                "parameters": ["use_sim_time"],
            }
        ]

    cleaned_topics = []

    for topic in topics:
        if not isinstance(topic, dict):
            continue

        topic_name = topic.get("name")

        if not topic_name:
            continue

        cleaned_topics.append(
            {
                "name": str(topic_name),
                "message_type": normalize_message_type(topic.get("message_type")),
                "purpose": topic.get("purpose", "Generated ROS2 topic."),
            }
        )

    if not cleaned_topics:
        graph_edges = graph.get("edges", []) or []
        seen = set()

        for edge in graph_edges:
            if not isinstance(edge, dict):
                continue

            topic = edge.get("topic")

            if not topic or topic in seen:
                continue

            seen.add(topic)

            cleaned_topics.append(
                {
                    "name": str(topic),
                    "message_type": normalize_message_type(edge.get("message_type")),
                    "purpose": (
                        f"Topic inferred from ROS2 graph edge "
                        f"{edge.get('source')} to {edge.get('target')}."
                    ),
                }
            )

    if not cleaned_topics:
        cleaned_topics = [
            {
                "name": "/omni/status",
                "message_type": "std_msgs/String",
                "purpose": "Publishes starter OMNI system status.",
            }
        ]

    add_morphology_ros2_nodes_and_topics(
        cleaned_nodes=cleaned_nodes,
        cleaned_topics=cleaned_topics,
        morphology_plan=morphology_plan,
    )

    cleaned_launch_files = []

    for launch_file in launch_files:
        if not isinstance(launch_file, dict):
            continue

        name = launch_file.get("name") or f"{package_name}_launch.py"

        cleaned_launch_files.append(
            {
                "name": str(name),
                "purpose": launch_file.get(
                    "purpose",
                    "Launches generated OMNI ROS2 nodes.",
                ),
                "nodes_started": normalize_list(
                    launch_file.get(
                        "nodes_started",
                        [node["name"] for node in cleaned_nodes],
                    )
                ),
            }
        )

    if not cleaned_launch_files:
        cleaned_launch_files = [
            {
                "name": f"{package_name}_launch.py",
                "purpose": "Launches generated OMNI ROS2 nodes.",
                "nodes_started": [node["name"] for node in cleaned_nodes],
            }
        ]

    return {
        "package_name": package_name,
        "nodes": cleaned_nodes,
        "topics": cleaned_topics,
        "launch_files": cleaned_launch_files,
        "morphology_plan": morphology_plan,
    }


# ---------------------------------------------------------
# ROS2 Message Type Helpers
# ---------------------------------------------------------
def normalize_message_type(message_type: Any) -> str:
    value = str(message_type or "std_msgs/String").strip()

    if not value or value.lower() in {"unknown", "none", "null", "tbd"}:
        return "std_msgs/String"

    aliases = {
        "String": "std_msgs/String",
        "Float32": "std_msgs/Float32",
        "Bool": "std_msgs/Bool",
        "Twist": "geometry_msgs/Twist",
        "Imu": "sensor_msgs/Imu",
        "Image": "sensor_msgs/Image",
        "BatteryState": "sensor_msgs/BatteryState",
        "CameraData": "sensor_msgs/Image",
        "MotorCommand": "geometry_msgs/Twist",
        "ObstacleData": "std_msgs/String",
        "NavigationData": "std_msgs/String",
        "DistanceData": "std_msgs/String",
    }

    return aliases.get(value, value)


def message_type_to_import(message_type: str) -> str:
    message_type = normalize_message_type(message_type)

    known = {
        "std_msgs/String": "from std_msgs.msg import String",
        "std_msgs/Float32": "from std_msgs.msg import Float32",
        "std_msgs/Bool": "from std_msgs.msg import Bool",
        "geometry_msgs/Twist": "from geometry_msgs.msg import Twist",
        "sensor_msgs/Imu": "from sensor_msgs.msg import Imu",
        "sensor_msgs/Image": "from sensor_msgs.msg import Image",
        "sensor_msgs/BatteryState": "from sensor_msgs.msg import BatteryState",
    }

    return known.get(message_type, "from std_msgs.msg import String")


def message_type_to_class(message_type: str) -> str:
    message_type = normalize_message_type(message_type)

    known = {
        "std_msgs/String": "String",
        "std_msgs/Float32": "Float32",
        "std_msgs/Bool": "Bool",
        "geometry_msgs/Twist": "Twist",
        "sensor_msgs/Imu": "Imu",
        "sensor_msgs/Image": "Image",
        "sensor_msgs/BatteryState": "BatteryState",
    }

    return known.get(message_type, "String")


def topic_message_map(topics: List[Dict[str, Any]]) -> Dict[str, str]:
    mapping = {}

    for topic in topics:
        if not isinstance(topic, dict):
            continue

        name = topic.get("name")

        if not name:
            continue

        mapping[str(name)] = normalize_message_type(topic.get("message_type"))

    return mapping


# ---------------------------------------------------------
# Generated Node File
# ---------------------------------------------------------
def generate_node_file(
    package_name: str,
    node: Dict[str, Any],
    topics: List[Dict[str, Any]],
) -> str:
    node_name = safe_node_name(node.get("name"))
    class_name = infer_python_class_name(node_name)
    purpose = node.get("purpose", "Generated OMNI ROS2 node.")

    publishes = [str(item) for item in normalize_list(node.get("publishes")) if item]
    subscribes = [str(item) for item in normalize_list(node.get("subscribes")) if item]
    parameters = clean_parameters(node.get("parameters"))

    topic_map = topic_message_map(topics)
    used_message_types = set()

    for topic in publishes + subscribes:
        used_message_types.add(topic_map.get(topic, "std_msgs/String"))

    if not used_message_types:
        used_message_types.add("std_msgs/String")

    imports = sorted({message_type_to_import(msg) for msg in used_message_types})

    parameter_lines = []
    publisher_lines = []
    subscriber_lines = []
    timer_lines = []
    methods = []

    for parameter in parameters:
        parameter_lines.append(f'        self.declare_parameter("{parameter}", None)')

    for topic in publishes:
        msg_type = topic_map.get(topic, "std_msgs/String")
        msg_class = message_type_to_class(msg_type)
        attr = safe_name(topic, "topic")

        publisher_lines.append(
            f'        self.{attr}_publisher = self.create_publisher({msg_class}, "{topic}", 10)'
        )
        timer_lines.append(f"        self.create_timer(1.0, self.publish_{attr})")

        if msg_class == "String":
            method_body = [
                "        msg = String()",
                f'        msg.data = "{node_name} heartbeat"',
                f"        self.{attr}_publisher.publish(msg)",
                f'        self.get_logger().info("Published on {topic}: " + msg.data)',
            ]
        elif msg_class == "Float32":
            method_body = [
                "        msg = Float32()",
                "        msg.data = 0.0",
                f"        self.{attr}_publisher.publish(msg)",
                f'        self.get_logger().info("Published Float32 on {topic}")',
            ]
        elif msg_class == "Bool":
            method_body = [
                "        msg = Bool()",
                "        msg.data = True",
                f"        self.{attr}_publisher.publish(msg)",
                f'        self.get_logger().info("Published Bool on {topic}")',
            ]
        else:
            method_body = [
                f"        msg = {msg_class}()",
                f"        self.{attr}_publisher.publish(msg)",
                f'        self.get_logger().info("Published {msg_class} on {topic}")',
            ]

        methods.append(
            "\n".join(
                [
                    f"    def publish_{attr}(self):",
                    *method_body,
                    "",
                ]
            )
        )

    for topic in subscribes:
        msg_type = topic_map.get(topic, "std_msgs/String")
        msg_class = message_type_to_class(msg_type)
        attr = safe_name(topic, "topic")

        subscriber_lines.append(
            f'        self.{attr}_subscription = self.create_subscription({msg_class}, "{topic}", self.handle_{attr}, 10)'
        )

        methods.append(
            "\n".join(
                [
                    f"    def handle_{attr}(self, msg):",
                    f'        self.get_logger().info("Received message on {topic}")',
                    "",
                ]
            )
        )

    if not methods:
        timer_lines.append("        self.create_timer(1.0, self.heartbeat)")
        methods.append(
            "\n".join(
                [
                    "    def heartbeat(self):",
                    f'        self.get_logger().info("{node_name} is running.")',
                    "",
                ]
            )
        )

    parameter_block = "\n".join(parameter_lines) or "        # No parameters declared yet."
    publisher_block = "\n".join(publisher_lines) or "        # No publishers configured yet."
    subscriber_block = "\n".join(subscriber_lines) or "        # No subscribers configured yet."
    timer_block = "\n".join(timer_lines) or "        # No timers configured yet."
    methods_block = "\n".join(methods)

    return f'''"""
Generated by OMNI Command.

Package: {package_name}
Node: {node_name}
Purpose: {purpose}
"""

import rclpy
from rclpy.node import Node
{chr(10).join(imports)}


class {class_name}(Node):
    def __init__(self):
        super().__init__("{node_name}")

{parameter_block}

{publisher_block}

{subscriber_block}

{timer_block}

        self.get_logger().info("{node_name} started.")

{methods_block}

def main(args=None):
    rclpy.init(args=args)

    node = {class_name}()

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
'''


# ---------------------------------------------------------
# Generated ROS2 Package Files
# ---------------------------------------------------------
def generate_launch_file(
    package_name: str,
    nodes: List[Dict[str, Any]],
    morphology_plan: Dict[str, Any] | None = None,
) -> str:
    node_entries: List[str] = []

    for node in nodes:
        node_name = safe_node_name(node.get("name"))

        node_entries.append(
            "\n".join(
                [
                    "        Node(",
                    f'            package="{package_name}",',
                    f'            executable="{node_name}",',
                    f'            name="{node_name}",',
                    '            output="screen",',
                    '            parameters=[params_file, {"use_sim_time": use_sim_time}],',
                    "        ),",
                ]
            )
        )

    node_block = "\n".join(node_entries)

    lines = [
        '"""',
        "Generated OMNI ROS2 launch file.",
        "",
        "This launch file starts generated nodes, publishes robot_description through",
        "robot_state_publisher, and loads the installed parameter file.",
        '"""',
        "",
        "from pathlib import Path",
        "",
        "from launch import LaunchDescription",
        "from launch.actions import DeclareLaunchArgument",
        "from launch.substitutions import Command, LaunchConfiguration",
        "from launch_ros.actions import Node",
        "from ament_index_python.packages import get_package_share_directory",
        "",
        "",
        "def generate_launch_description():",
        f'    package_share = Path(get_package_share_directory("{package_name}"))',
        '    params_file = str(package_share / "config" / "omni_params.yaml")',
        f'    urdf_file = str(package_share / "urdf" / "{package_name}.urdf.xacro")',
        '    use_sim_time = LaunchConfiguration("use_sim_time")',
        "",
        "    robot_description = {",
        '        "robot_description": Command(["xacro ", urdf_file])',
        "    }",
        "",
        "    return LaunchDescription([",
        "        DeclareLaunchArgument(",
        '            "use_sim_time",',
        '            default_value="false",',
        '            description="Use simulation time if true.",',
        "        ),",
        "        Node(",
        '            package="robot_state_publisher",',
        '            executable="robot_state_publisher",',
        '            name="robot_state_publisher",',
        '            output="screen",',
        "            parameters=[",
        "                robot_description,",
        '                {"use_sim_time": use_sim_time},',
        "            ],",
        "        ),",
        node_block,
        "    ])",
        "",
    ]

    return "\n".join(lines)


def generate_setup_py(package_name: str, nodes: List[Dict[str, Any]]) -> str:
    console_scripts = []

    for node in nodes:
        node_name = safe_node_name(node.get("name"))
        console_scripts.append(
            f'            "{node_name} = {package_name}.{node_name}:main",'
        )

    console_block = "\n".join(console_scripts)

    return f'''from glob import glob
from setuptools import setup

package_name = "{package_name}"

setup(
    name=package_name,
    version="0.0.1",
    packages=[package_name],
    data_files=[
        ("share/ament_index/resource_index/packages", ["resource/" + package_name]),
        ("share/" + package_name, ["package.xml", "README.md"]),
        ("share/" + package_name + "/launch", glob("launch/*.py")),
        ("share/" + package_name + "/config", glob("config/*.yaml")),
        ("share/" + package_name + "/docs", glob("docs/*.md")),
        ("share/" + package_name + "/scripts", glob("scripts/*.sh")),
        ("share/" + package_name + "/urdf", glob("urdf/*.xacro") + glob("urdf/*.urdf")),
        ("share/" + package_name + "/rviz", glob("rviz/*.rviz")),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="Henry Valladares",
    maintainer_email="henry@example.com",
    description="Generated ROS2 package scaffold from OMNI Command.",
    license="MIT",
    tests_require=["pytest"],
    entry_points={{
        "console_scripts": [
{console_block}
        ],
    }},
)
'''


def generate_setup_cfg(package_name: str) -> str:
    return f"""[develop]
script_dir=$base/lib/{package_name}

[install]
install_scripts=$base/lib/{package_name}
"""


def generate_package_xml(package_name: str) -> str:
    return f'''<?xml version="1.0"?>
<package format="3">
  <name>{package_name}</name>
  <version>0.0.1</version>
  <description>Generated ROS2 package scaffold from OMNI Command.</description>

  <maintainer email="henry@example.com">Henry Valladares</maintainer>
  <license>MIT</license>

  <buildtool_depend>ament_python</buildtool_depend>

  <depend>rclpy</depend>
  <depend>std_msgs</depend>
  <depend>geometry_msgs</depend>
  <depend>sensor_msgs</depend>
  <depend>launch</depend>
  <depend>launch_ros</depend>\n  <depend>trajectory_msgs</depend>\n  <depend>nav_msgs</depend>
  <depend>ament_index_python</depend>
  <depend>robot_state_publisher</depend>
  <depend>xacro</depend>
  <depend>rviz2</depend>

  <test_depend>ament_copyright</test_depend>
  <test_depend>ament_flake8</test_depend>
  <test_depend>ament_pep257</test_depend>
  <test_depend>python3-pytest</test_depend>

  <export>
    <build_type>ament_python</build_type>
  </export>
</package>
'''


def generate_config_yaml(package_name: str, nodes: List[Dict[str, Any]]) -> str:
    blocks = []

    for node in nodes:
        node_name = safe_node_name(node.get("name"))
        parameters = clean_parameters(node.get("parameters"))

        if not parameters:
            parameters = ["use_sim_time"]

        lines = [f"{node_name}:", "  ros__parameters:"]

        for parameter in parameters:
            if parameter == "use_sim_time":
                lines.append("    use_sim_time: false")
            else:
                lines.append(f"    {parameter}: null")

        blocks.append("\n".join(lines))

    return f"""# Generated OMNI ROS2 parameter file.
# Review placeholder values before simulation or hardware testing.
# Package: {package_name}

{chr(10).join(blocks)}
"""


def generate_topic_contracts_md(
    topics: List[Dict[str, Any]],
    nodes: List[Dict[str, Any]],
) -> str:
    lines = [
        "# Topic Contracts",
        "",
        "Generated by OMNI Command.",
        "",
        "Confirm real message types, units, QoS settings, frame IDs, and expected rates before hardware testing.",
        "",
        "| Topic | Message Type | Publishers | Subscribers | Purpose |",
        "|---|---|---|---|---|",
    ]

    for topic in topics:
        topic_name = str(topic.get("name", "/unknown"))
        message_type = normalize_message_type(topic.get("message_type"))
        purpose = str(topic.get("purpose", "Generated ROS2 topic."))

        publishers = []
        subscribers = []

        for node in nodes:
            node_name = safe_node_name(node.get("name"))

            if topic_name in normalize_list(node.get("publishes")):
                publishers.append(node_name)

            if topic_name in normalize_list(node.get("subscribes")):
                subscribers.append(node_name)

        lines.append(
            f"| `{topic_name}` | `{message_type}` | "
            f"{', '.join(publishers) or 'TBD'} | "
            f"{', '.join(subscribers) or 'TBD'} | {purpose} |"
        )

    return "\n".join(lines) + "\n"


def generate_node_graph_md(
    topics: List[Dict[str, Any]],
    nodes: List[Dict[str, Any]],
) -> str:
    lines = [
        "# ROS2 Node Graph",
        "",
        "Generated by OMNI Command.",
        "",
        "```text",
    ]

    for node in nodes:
        node_name = safe_node_name(node.get("name"))
        lines.append(node_name)

        publishes = normalize_list(node.get("publishes"))
        subscribes = normalize_list(node.get("subscribes"))

        if publishes:
            for topic in publishes:
                lines.append(f"  publishes  -> {topic}")

        if subscribes:
            for topic in subscribes:
                lines.append(f"  subscribes <- {topic}")

        if not publishes and not subscribes:
            lines.append("  no topics configured yet")

    lines.extend(
        [
            "```",
            "",
            "## Inspection Commands",
            "",
            "```bash",
            "ros2 node list",
            "ros2 topic list",
            "rqt_graph",
            "```",
            "",
        ]
    )

    return "\n".join(lines)


def generate_test_topics_script(package_name: str, topics: List[Dict[str, Any]]) -> str:
    topic_lines = "\n".join(
        f'echo "  - {topic.get("name", "/unknown")}"'
        for topic in topics
    )

    return f'''#!/usr/bin/env bash
set -e

echo "OMNI ROS2 topic smoke test"
echo "Package: {package_name}"
echo ""

echo "Expected topics:"
{topic_lines}

echo ""
echo "Current ROS2 nodes:"
ros2 node list || true

echo ""
echo "Current ROS2 topics:"
ros2 topic list || true

echo ""
echo "Tip: launch the package first:"
echo "  ros2 launch {package_name} {package_name}_launch.py"
'''


def generate_urdf_xacro(
    package_name: str,
    morphology_plan: Dict[str, Any] | None = None,
) -> str:
    robot_name = safe_name(package_name, "omni_robot")
    morphology_plan = morphology_plan or {}

    ros2_intent = morphology_ros2_intent(morphology_plan)
    body_plan = morphology_plan.get("body_plan", {})

    if not isinstance(body_plan, dict):
        body_plan = {}

    recommended_frames = normalize_list(ros2_intent.get("recommended_frames"))
    body_segments = normalize_list(body_plan.get("segments"))
    mounting_points = normalize_list(body_plan.get("mounting_points"))

    if not recommended_frames:
        recommended_frames = ["base_link", "camera_link"]

    if "base_link" not in recommended_frames:
        recommended_frames.insert(0, "base_link")

    child_frames = [frame for frame in recommended_frames if frame != "base_link"]

    lines = [
        '<?xml version="1.0"?>',
        f'<robot name="{robot_name}" xmlns:xacro="http://www.ros.org/wiki/xacro">',
        "",
        "  <!--",
        "    Generated starter URDF/Xacro by OMNI Command.",
        "",
        "    Morphology-aware URDF scaffold.",
        "    Replace placeholder dimensions, masses, inertias, joint locations,",
        "    sensor frames, materials, and collision geometry before simulation",
        "    or hardware testing.",
        "",
        f'    Morphology ID: {morphology_plan.get("morphology_id", "")}',
        f'    Project family: {morphology_plan.get("project_family", "")}',
        f"    Body segments: {body_segments}",
        f"    Mounting points: {mounting_points}",
        f"    Recommended frames: {recommended_frames}",
        "  -->",
        "",
        '  <link name="base_link">',
        "    <inertial>",
        '      <mass value="1.0"/>',
        '      <origin xyz="0 0 0" rpy="0 0 0"/>',
        '      <inertia ixx="0.01" ixy="0" ixz="0" iyy="0.01" iyz="0" izz="0.01"/>',
        "    </inertial>",
        "    <visual>",
        "      <geometry>",
        '        <box size="0.30 0.20 0.08"/>',
        "      </geometry>",
        '      <material name="omni_dark">',
        '        <color rgba="0.05 0.05 0.07 1.0"/>',
        "      </material>",
        "    </visual>",
        "    <collision>",
        "      <geometry>",
        '        <box size="0.30 0.20 0.08"/>',
        "      </geometry>",
        "    </collision>",
        "  </link>",
        "",
    ]

    for index, frame in enumerate(child_frames, start=1):
        safe_frame = safe_name(frame, f"morphology_link_{index}")

        x = 0.04 * index
        y = 0.0
        z = 0.04 + 0.01 * (index % 3)

        if "head" in safe_frame:
            x = 0.14
            z = 0.08
        elif "thorax" in safe_frame:
            x = 0.00
            z = 0.07
        elif "abdomen" in safe_frame:
            x = -0.12
            z = 0.07
        elif "left" in safe_frame:
            y = 0.10
            z = 0.03
        elif "right" in safe_frame:
            y = -0.10
            z = 0.03

        lines.extend(
            [
                f'  <link name="{safe_frame}">',
                "    <inertial>",
                '      <mass value="0.1"/>',
                '      <origin xyz="0 0 0" rpy="0 0 0"/>',
                '      <inertia ixx="0.001" ixy="0" ixz="0" iyy="0.001" iyz="0" izz="0.001"/>',
                "    </inertial>",
                "    <visual>",
                "      <geometry>",
                '        <box size="0.05 0.03 0.03"/>',
                "      </geometry>",
                '      <material name="morphology_blue">',
                '        <color rgba="0.1 0.4 1.0 1.0"/>',
                "      </material>",
                "    </visual>",
                "    <collision>",
                "      <geometry>",
                '        <box size="0.05 0.03 0.03"/>',
                "      </geometry>",
                "    </collision>",
                "  </link>",
                "",
                f'  <joint name="{safe_frame}_joint" type="fixed">',
                '    <parent link="base_link"/>',
                f'    <child link="{safe_frame}"/>',
                f'    <origin xyz="{x:.2f} {y:.2f} {z:.2f}" rpy="0 0 0"/>',
                "  </joint>",
                "",
            ]
        )

    lines.append("</robot>")
    lines.append("")

    return "\n".join(lines)


def generate_rviz_config(package_name: str) -> str:
    return f"""Panels:
  - Class: rviz_common/Displays
    Name: Displays
Visualization Manager:
  Class: ""
  Displays:
    - Class: rviz_default_plugins/Grid
      Enabled: true
      Name: Grid
    - Class: rviz_default_plugins/RobotModel
      Enabled: true
      Name: RobotModel
      Robot Description: robot_description
  Enabled: true
  Global Options:
    Fixed Frame: base_link
  Name: root
"""


def generate_readme(
    mission_result: Dict[str, Any],
    package_name: str,
    nodes: List[Dict[str, Any]],
) -> str:
    mission = mission_result.get("mission", "OMNI generated ROS2 mission.")

    node_list = "\n".join(
        f"- `{safe_node_name(node.get('name'))}`: {node.get('purpose', 'Generated node.')}"
        for node in nodes
    )

    return f"""# {package_name}

Generated by OMNI Command.

## Mission

{mission}

## Nodes

{node_list}

## Build

```bash
colcon build --packages-select {package_name}
source install/setup.bash
```

## Launch

```bash
ros2 launch {package_name} {package_name}_launch.py
```

## Inspect

```bash
ros2 node list
ros2 topic list
rqt_graph
```

## Topic Smoke Test

After building and sourcing the workspace:

```bash
bash install/{package_name}/share/{package_name}/scripts/test_topics.sh
```

## Generated Structure

```text
{package_name}/
  package.xml
  setup.py
  setup.cfg
  README.md
  launch/
  config/
  docs/
  scripts/
  urdf/
  rviz/
  resource/
  test/
  {package_name}/
```

## Important Notes

This package is a starter scaffold. Confirm real hardware drivers, topic names,
message types, safety gates, power limits, physical dimensions, URDF measurements,
and simulation targets before physical testing.
"""


def generate_test_file(package_name: str) -> str:
    return f'''def test_generated_package_name():
    assert "{package_name}"
'''


# ---------------------------------------------------------
# Main Generator
# ---------------------------------------------------------
def generate_ros2_package(
    mission_result: Dict[str, Any],
    output_root: Path,
) -> Dict[str, Any]:
    """
    Creates a ROS2 Python package scaffold from OMNI artifacts.

    Expected output:
    generated_ros2/<package_name>/
      package.xml
      setup.py
      setup.cfg
      README.md
      launch/<package_name>_launch.py
      config/omni_params.yaml
      docs/topic_contracts.md
      docs/node_graph.md
      scripts/test_topics.sh
      urdf/<package_name>.urdf.xacro
      rviz/<package_name>.rviz
      resource/<package_name>
      test/test_generated_package.py
      <package_name>/__init__.py
      <package_name>/<node_name>.py
    """
    if not isinstance(mission_result, dict):
        raise ValueError("mission_result must be a dictionary.")

    output_root = Path(output_root)

    plan = normalize_ros2_plan(mission_result)
    package_name = plan["package_name"]
    nodes = plan["nodes"]
    topics = plan["topics"]
    morphology_plan = plan.get("morphology_plan", {})

    package_dir = output_root / "generated_ros2" / package_name
    module_dir = package_dir / package_name
    launch_dir = package_dir / "launch"
    config_dir = package_dir / "config"
    docs_dir = package_dir / "docs"
    scripts_dir = package_dir / "scripts"
    urdf_dir = package_dir / "urdf"
    rviz_dir = package_dir / "rviz"
    resource_dir = package_dir / "resource"
    test_dir = package_dir / "test"

    for directory in [
        module_dir,
        launch_dir,
        config_dir,
        docs_dir,
        scripts_dir,
        urdf_dir,
        rviz_dir,
        resource_dir,
        test_dir,
    ]:
        directory.mkdir(parents=True, exist_ok=True)

    generated_files = []

    def write_file(path: Path, content: str, executable: bool = False) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

        if executable:
            path.chmod(0o755)

        generated_files.append(str(path.relative_to(output_root)))

    write_file(module_dir / "__init__.py", "")
    write_file(resource_dir / package_name, "")

    write_file(package_dir / "package.xml", generate_package_xml(package_name))
    write_file(package_dir / "setup.py", generate_setup_py(package_name, nodes))
    write_file(package_dir / "setup.cfg", generate_setup_cfg(package_name))
    write_file(package_dir / "README.md", generate_readme(mission_result, package_name, nodes))

    write_file(
        launch_dir / f"{package_name}_launch.py",
        generate_launch_file(package_name, nodes, morphology_plan),
    )

    write_file(config_dir / "omni_params.yaml", generate_config_yaml(package_name, nodes))
    write_file(docs_dir / "topic_contracts.md", generate_topic_contracts_md(topics, nodes))
    write_file(docs_dir / "node_graph.md", generate_node_graph_md(topics, nodes))
    write_file(
        scripts_dir / "test_topics.sh",
        generate_test_topics_script(package_name, topics),
        executable=True,
    )
    write_file(
        urdf_dir / f"{package_name}.urdf.xacro",
        generate_urdf_xacro(package_name, morphology_plan),
    )
    write_file(rviz_dir / f"{package_name}.rviz", generate_rviz_config(package_name))

    for node in nodes:
        node_name = safe_node_name(node.get("name"))

        write_file(
            module_dir / f"{node_name}.py",
            generate_node_file(package_name, node, topics),
        )

    write_file(test_dir / "test_generated_package.py", generate_test_file(package_name))

    return {
        "status": "generated",
        "package_name": package_name,
        "package_dir": str(package_dir),
        "files": generated_files,
        "file_count": len(generated_files),
    }