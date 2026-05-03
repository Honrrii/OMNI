import subprocess
from datetime import datetime
from typing import Any, Dict, List


ROS_SETUP_COMMAND = """
if [ -f /opt/ros/humble/setup.bash ]; then
  source /opt/ros/humble/setup.bash
fi

if [ -f ~/ros2_ws/install/setup.bash ]; then
  source ~/ros2_ws/install/setup.bash
fi
"""


def get_ros_status() -> Dict[str, Any]:
    """
    Read-only ROS2 status service for OMNI Simulation Level 1.

    This does not move robots.
    This does not launch Gazebo.
    This does not control physical hardware.
    """

    ros2_available = _check_ros2_available()

    nodes: List[str] = []
    topics: List[str] = []
    node_error = None
    topic_error = None

    if ros2_available:
        node_result = _run_ros_command("ros2 node list")
        topic_result = _run_ros_command("ros2 topic list")

        if node_result["ok"]:
            nodes = _clean_lines(node_result["stdout"])
        else:
            node_error = node_result["stderr"] or node_result["stdout"]

        if topic_result["ok"]:
            topics = _clean_lines(topic_result["stdout"])
        else:
            topic_error = topic_result["stderr"] or topic_result["stdout"]

    process_status = _detect_visualization_processes()

    simulation_state = "offline"
    if process_status["gazebo_detected"]:
        simulation_state = "gazebo_detected"
    elif process_status["rviz_detected"]:
        simulation_state = "rviz_detected"
    elif ros2_available:
        simulation_state = "ros2_available"

    return {
        "status": "success",
        "timestamp": datetime.now().isoformat(),
        "ros_available": ros2_available,
        "simulation_state": simulation_state,
        "physical_robot_control": False,
        "safety_note": "Read-only ROS2 status check. No robot, printer, actuator, or simulation control was executed.",
        "nodes": nodes,
        "topics": topics,
        "node_count": len(nodes),
        "topic_count": len(topics),
        "errors": {
            "node_error": node_error,
            "topic_error": topic_error,
        },
        "processes": process_status,
        "recommended_next_steps": [
            "Start ROS2 nodes or a Gazebo simulation if no nodes are listed.",
            "Use this panel as a read-only dashboard before adding controls.",
            "Add rosbridge or Foxglove bridge later for live WebSocket telemetry.",
            "Keep physical robot control disabled until explicit safety gates exist.",
        ],
    }


def _check_ros2_available() -> bool:
    result = _run_bash_command("command -v ros2")
    return result["ok"] and bool(result["stdout"].strip())


def _run_ros_command(command: str, timeout_seconds: int = 6) -> Dict[str, Any]:
    return _run_bash_command(command, timeout_seconds=timeout_seconds)


def _run_bash_command(command: str, timeout_seconds: int = 6) -> Dict[str, Any]:
    full_command = f"{ROS_SETUP_COMMAND}\n{command}"

    try:
        completed = subprocess.run(
            ["bash", "-lc", full_command],
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )

        return {
            "ok": completed.returncode == 0,
            "return_code": completed.returncode,
            "stdout": completed.stdout,
            "stderr": completed.stderr,
        }

    except subprocess.TimeoutExpired as error:
        return {
            "ok": False,
            "return_code": None,
            "stdout": error.stdout or "",
            "stderr": f"Command timed out after {timeout_seconds} seconds.",
        }

    except Exception as error:
        return {
            "ok": False,
            "return_code": None,
            "stdout": "",
            "stderr": str(error),
        }


def _detect_visualization_processes() -> Dict[str, Any]:
    result = _run_bash_command(
        "pgrep -af 'rviz2|gazebo|gz sim|rosbridge|foxglove_bridge' || true",
        timeout_seconds=4,
    )

    lines = _clean_lines(result["stdout"])

    return {
        "rviz_detected": any("rviz2" in line for line in lines),
        "gazebo_detected": any("gazebo" in line or "gz sim" in line for line in lines),
        "rosbridge_detected": any("rosbridge" in line for line in lines),
        "foxglove_bridge_detected": any("foxglove_bridge" in line for line in lines),
        "matching_processes": lines,
    }


def _clean_lines(text: str) -> List[str]:
    return [
        line.strip()
        for line in text.splitlines()
        if line.strip()
    ]