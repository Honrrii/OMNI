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
# ROS2 Plan Normalization
# ---------------------------------------------------------
def normalize_ros2_plan(mission_result: Dict[str, Any]) -> Dict[str, Any]:
    artifacts = mission_result.get("artifacts", {}) or {}
    plan = artifacts.get("ros2_package_plan", {}) or {}
    graph = artifacts.get("ros2_node_graph", {}) or {}

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
def generate_launch_file(package_name: str, nodes: List[Dict[str, Any]]) -> str:
    node_entries = []

    for node in nodes:
        node_name = safe_node_name(node.get("name"))

        node_entries.append(
            f'''        Node(
            package="{package_name}",
            executable="{node_name}",
            name="{node_name}",
            output="screen",
            parameters=[params_file],
        ),'''
        )

    node_block = "\n".join(node_entries)

    return f'''"""
Generated OMNI ROS2 launch file.

This launch file starts generated nodes and loads the installed parameter file.
"""

from launch import LaunchDescription
from launch_ros.actions import Node
from ament_index_python.packages import get_package_share_directory
from pathlib import Path


def generate_launch_description():
    package_share = Path(get_package_share_directory("{package_name}"))
    params_file = str(package_share / "config" / "omni_params.yaml")

    return LaunchDescription([
{node_block}
    ])
'''


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
  <depend>launch_ros</depend>
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


def generate_urdf_xacro(package_name: str) -> str:
    robot_name = safe_name(package_name, "omni_robot")

    return f'''<?xml version="1.0"?>
<robot name="{robot_name}" xmlns:xacro="http://www.ros.org/wiki/xacro">

  <!--
    Generated starter URDF/Xacro by OMNI Command.

    Replace placeholder dimensions, masses, inertias, wheel placement,
    sensor frames, materials, and collision geometry before simulation
    or hardware testing.
  -->

  <xacro:property name="base_length" value="0.30"/>
  <xacro:property name="base_width" value="0.20"/>
  <xacro:property name="base_height" value="0.08"/>

  <link name="base_link">
    <visual>
      <geometry>
        <box size="${{base_length}} ${{base_width}} ${{base_height}}"/>
      </geometry>
      <material name="omni_dark">
        <color rgba="0.05 0.05 0.07 1.0"/>
      </material>
    </visual>
    <collision>
      <geometry>
        <box size="${{base_length}} ${{base_width}} ${{base_height}}"/>
      </geometry>
    </collision>
  </link>

  <link name="camera_link">
    <visual>
      <geometry>
        <box size="0.04 0.03 0.03"/>
      </geometry>
      <material name="camera_green">
        <color rgba="0.1 1.0 0.6 1.0"/>
      </material>
    </visual>
  </link>

  <joint name="camera_joint" type="fixed">
    <parent link="base_link"/>
    <child link="camera_link"/>
    <origin xyz="0.12 0 0.08" rpy="0 0 0"/>
  </joint>

</robot>
'''


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
        generate_launch_file(package_name, nodes),
    )

    write_file(config_dir / "omni_params.yaml", generate_config_yaml(package_name, nodes))
    write_file(docs_dir / "topic_contracts.md", generate_topic_contracts_md(topics, nodes))
    write_file(docs_dir / "node_graph.md", generate_node_graph_md(topics, nodes))
    write_file(
        scripts_dir / "test_topics.sh",
        generate_test_topics_script(package_name, topics),
        executable=True,
    )
    write_file(urdf_dir / f"{package_name}.urdf.xacro", generate_urdf_xacro(package_name))
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