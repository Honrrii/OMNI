from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path
import json
import sys


@dataclass
class KnowledgeGateIssue:
    rule_id: str
    severity: str
    message: str
    file: str | None = None


def read_text_files(root: Path) -> dict[str, str]:
    allowed_suffixes = {
        ".py",
        ".xml",
        ".urdf",
        ".xacro",
        ".yaml",
        ".yml",
        ".launch",
        ".txt",
        ".md",
    }

    files: dict[str, str] = {}

    for path in root.rglob("*"):
        if path.is_file() and path.suffix.lower() in allowed_suffixes:
            try:
                files[str(path)] = path.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue

    return files


def contains_any(text: str, keywords: list[str]) -> bool:
    lowered = text.lower()
    return any(keyword.lower() in lowered for keyword in keywords)


def validate_ros2_file_structure(root: Path, files: dict[str, str]) -> list[KnowledgeGateIssue]:
    issues: list[KnowledgeGateIssue] = []

    file_names = [Path(path).name for path in files.keys()]
    file_paths = list(files.keys())

    if "package.xml" not in file_names:
        issues.append(
            KnowledgeGateIssue(
                rule_id="ROS2.FS.001",
                severity="blocker",
                message="ROS2 package is missing package.xml.",
            )
        )

    if "setup.py" not in file_names and "CMakeLists.txt" not in file_names:
        issues.append(
            KnowledgeGateIssue(
                rule_id="ROS2.FS.002",
                severity="blocker",
                message="ROS2 package is missing setup.py or CMakeLists.txt.",
            )
        )

    if not any("/launch/" in path or "\\launch\\" in path for path in file_paths):
        issues.append(
            KnowledgeGateIssue(
                rule_id="ROS2.FS.003",
                severity="warning",
                message="No launch folder/files detected.",
            )
        )

    if not any(("/urdf/" in path or "\\urdf\\" in path or path.endswith(".urdf") or path.endswith(".xacro")) for path in file_paths):
        issues.append(
            KnowledgeGateIssue(
                rule_id="ROS2.FS.004",
                severity="warning",
                message="No URDF/Xacro robot description files detected.",
            )
        )

    return issues


def validate_urdf_xacro(files: dict[str, str]) -> list[KnowledgeGateIssue]:
    issues: list[KnowledgeGateIssue] = []

    urdf_files = {
        path: text
        for path, text in files.items()
        if path.endswith(".urdf") or path.endswith(".xacro") or "<robot" in text
    }

    if not urdf_files:
        issues.append(
            KnowledgeGateIssue(
                rule_id="URDF.000",
                severity="warning",
                message="No URDF/Xacro robot model was found.",
            )
        )
        return issues

    combined = "\n".join(urdf_files.values())

    if "<robot" not in combined:
        issues.append(
            KnowledgeGateIssue(
                rule_id="URDF.001",
                severity="blocker",
                message="URDF/Xacro content is missing a <robot> root element.",
            )
        )

    if "base_link" not in combined and "base_footprint" not in combined:
        issues.append(
            KnowledgeGateIssue(
                rule_id="URDF.002",
                severity="blocker",
                message="Robot description is missing base_link or base_footprint.",
            )
        )

    if "<link" not in combined:
        issues.append(
            KnowledgeGateIssue(
                rule_id="URDF.003",
                severity="blocker",
                message="Robot description has no <link> elements.",
            )
        )

    if "<joint" not in combined:
        issues.append(
            KnowledgeGateIssue(
                rule_id="URDF.004",
                severity="warning",
                message="Robot description has no <joint> elements.",
            )
        )

    if "<visual" not in combined:
        issues.append(
            KnowledgeGateIssue(
                rule_id="URDF.005",
                severity="warning",
                message="URDF links should include visual geometry for RViz.",
            )
        )

    if "<collision" not in combined:
        issues.append(
            KnowledgeGateIssue(
                rule_id="URDF.006",
                severity="warning",
                message="URDF links should include collision geometry for Gazebo.",
            )
        )

    if "<inertial" not in combined:
        issues.append(
            KnowledgeGateIssue(
                rule_id="URDF.007",
                severity="warning",
                message="URDF links should include inertial properties for Gazebo physics.",
            )
        )

    if "<parent" in combined and "<child" not in combined:
        issues.append(
            KnowledgeGateIssue(
                rule_id="URDF.008",
                severity="blocker",
                message="Joint definitions include parent links but missing child links.",
            )
        )

    if "<child" in combined and "<parent" not in combined:
        issues.append(
            KnowledgeGateIssue(
                rule_id="URDF.009",
                severity="blocker",
                message="Joint definitions include child links but missing parent links.",
            )
        )

    return issues


def validate_launch_files(files: dict[str, str]) -> list[KnowledgeGateIssue]:
    issues: list[KnowledgeGateIssue] = []

    launch_files = {
        path: text
        for path, text in files.items()
        if "launch" in Path(path).name.lower() or "/launch/" in path or "\\launch\\" in path
    }

    if not launch_files:
        issues.append(
            KnowledgeGateIssue(
                rule_id="LAUNCH.000",
                severity="warning",
                message="No ROS2 launch files were found.",
            )
        )
        return issues

    combined = "\n".join(launch_files.values())

    if "robot_state_publisher" not in combined:
        issues.append(
            KnowledgeGateIssue(
                rule_id="LAUNCH.001",
                severity="blocker",
                message="Launch files should start robot_state_publisher for URDF/TF publishing.",
            )
        )

    if "robot_description" not in combined:
        issues.append(
            KnowledgeGateIssue(
                rule_id="LAUNCH.002",
                severity="blocker",
                message="Launch files should pass the robot_description parameter.",
            )
        )

    if "use_sim_time" not in combined:
        issues.append(
            KnowledgeGateIssue(
                rule_id="LAUNCH.003",
                severity="warning",
                message="Simulation launch files should include use_sim_time.",
            )
        )

    if "rviz" not in combined.lower():
        issues.append(
            KnowledgeGateIssue(
                rule_id="LAUNCH.004",
                severity="info",
                message="No RViz launch integration detected.",
            )
        )

    return issues


def validate_gazebo_simulation(files: dict[str, str]) -> list[KnowledgeGateIssue]:
    issues: list[KnowledgeGateIssue] = []

    combined = "\n".join(files.values()).lower()

    has_gazebo_reference = contains_any(
        combined,
        [
            "gazebo",
            "gz_sim",
            "ros_gz",
            "spawn_entity",
            "create",
            "gazebo_ros",
        ],
    )

    if not has_gazebo_reference:
        issues.append(
            KnowledgeGateIssue(
                rule_id="GAZEBO.000",
                severity="info",
                message="No Gazebo simulation integration detected.",
            )
        )
        return issues

    if not contains_any(combined, ["spawn_entity", "ros_gz_sim", "create"]):
        issues.append(
            KnowledgeGateIssue(
                rule_id="GAZEBO.001",
                severity="warning",
                message="Gazebo integration should include a robot spawn/create action.",
            )
        )

    if "use_sim_time" not in combined:
        issues.append(
            KnowledgeGateIssue(
                rule_id="GAZEBO.002",
                severity="warning",
                message="Gazebo launch should use simulation time.",
            )
        )

    if "<inertial" not in combined:
        issues.append(
            KnowledgeGateIssue(
                rule_id="GAZEBO.003",
                severity="warning",
                message="Gazebo physics works best when URDF links include inertial tags.",
            )
        )

    if "<collision" not in combined:
        issues.append(
            KnowledgeGateIssue(
                rule_id="GAZEBO.004",
                severity="warning",
                message="Gazebo simulation needs collision geometry for physical interaction.",
            )
        )

    return issues


def validate_artifact_directory(root_path: str | Path) -> dict:
    root = Path(root_path).resolve()

    if not root.exists():
        return {
            "root": str(root),
            "status": "error",
            "issues": [
                asdict(
                    KnowledgeGateIssue(
                        rule_id="PATH.000",
                        severity="blocker",
                        message=f"Path does not exist: {root}",
                    )
                )
            ],
        }

    files = read_text_files(root)

    issues: list[KnowledgeGateIssue] = []
    issues.extend(validate_ros2_file_structure(root, files))
    issues.extend(validate_urdf_xacro(files))
    issues.extend(validate_launch_files(files))
    issues.extend(validate_gazebo_simulation(files))

    blocker_count = sum(1 for issue in issues if issue.severity == "blocker")
    warning_count = sum(1 for issue in issues if issue.severity == "warning")
    info_count = sum(1 for issue in issues if issue.severity == "info")

    if blocker_count > 0:
        status = "failed"
    elif warning_count > 0:
        status = "passed_with_warnings"
    else:
        status = "passed"

    return {
        "root": str(root),
        "status": status,
        "summary": {
            "files_scanned": len(files),
            "blockers": blocker_count,
            "warnings": warning_count,
            "info": info_count,
        },
        "issues": [asdict(issue) for issue in issues],
    }


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python -m backend.app.engineering.knowledge_gate_validator <artifact_directory>")
        raise SystemExit(1)

    result = validate_artifact_directory(sys.argv[1])
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()