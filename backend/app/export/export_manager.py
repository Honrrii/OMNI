import csv
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from backend.app.generators.ros2_package_generator import generate_ros2_package
from backend.app.validators.ros2_build_validator import validate_ros2_package


OUTPUT_ROOT = Path("outputs") / "omni_missions"


def safe_folder_name(text: str) -> str:
    value = str(text or "omni_mission").lower()
    value = value.replace("/", "_").replace("\\", "_").replace(" ", "_")
    value = "".join(ch for ch in value if ch.isalnum() or ch in ["_", "-"])
    value = "_".join(part for part in value.split("_") if part)
    return value[:90] or "omni_mission"


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(str(content or ""), encoding="utf-8")


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def write_csv(path: Path, rows: List[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    if not rows:
        path.write_text("", encoding="utf-8")
        return

    clean_rows = [row for row in rows if isinstance(row, dict)]

    if not clean_rows:
        path.write_text("", encoding="utf-8")
        return

    fieldnames = sorted({key for row in clean_rows for key in row.keys()})

    with open(path, "w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(clean_rows)


def markdown_list(title: str, items: List[Any]) -> str:
    lines = [f"# {title}", ""]

    if not items:
        lines.append("No items returned.")
        return "\n".join(lines)

    for item in items:
        if isinstance(item, dict):
            heading = (
                item.get("gate")
                or item.get("subsystem")
                or item.get("name")
                or item.get("risk")
                or "Item"
            )

            lines.append(f"## {heading}")

            for key, value in item.items():
                lines.append(f"- **{key}:** {value}")

            lines.append("")
        else:
            lines.append(f"- {item}")

    return "\n".join(lines)


def should_generate_ros2_package(artifacts: Dict[str, Any]) -> bool:
    if not isinstance(artifacts, dict):
        return False

    ros2_plan = artifacts.get("ros2_package_plan", {})
    ros2_graph = artifacts.get("ros2_node_graph", {})

    if isinstance(ros2_plan, dict) and ros2_plan:
        return True

    if isinstance(ros2_graph, dict):
        nodes = ros2_graph.get("nodes", [])
        edges = ros2_graph.get("edges", [])

        if nodes or edges:
            return True

    return False


def compact_validation_result(validation_report: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """
    Returns a compact frontend/API-friendly summary of the full ROS2 validation report.
    The full report is still written into the generated package build_reports folder.
    """
    if not isinstance(validation_report, dict):
        return None

    checks = validation_report.get("checks", {}) or {}

    expected_files = checks.get("expected_files", {}) or {}
    colcon_build = checks.get("colcon_build", {}) or {}
    installed_files = checks.get("installed_files", {}) or {}
    smoke_script = checks.get("smoke_script", {}) or {}
    launch_check = checks.get("launch_check", {}) or {}

    return {
        "status": "validated",
        "passed": bool(validation_report.get("passed", False)),
        "package_name": validation_report.get("package_name"),
        "workspace_dir": validation_report.get("workspace_dir"),
        "validated_at": validation_report.get("validated_at"),
        "report_paths": validation_report.get("report_paths", {}),
        "checks": {
            "expected_files": {
                "passed": bool(expected_files.get("passed", False)),
                "missing_files": expected_files.get("missing_files", []),
                "node_file_count": expected_files.get("node_file_count", 0),
            },
            "colcon_build": {
                "passed": bool(colcon_build.get("passed", False)),
                "returncode": colcon_build.get("returncode"),
                "timeout": bool(colcon_build.get("timeout", False)),
            },
            "installed_files": {
                "passed": bool(installed_files.get("passed", False)),
                "missing_files": installed_files.get("missing_files", []),
            },
            "smoke_script": {
                "passed": bool(smoke_script.get("passed", False)),
                "returncode": smoke_script.get("returncode"),
                "timeout": bool(smoke_script.get("timeout", False)),
            },
            "launch_check": {
                "passed": bool(launch_check.get("passed", False)),
                "nodes": launch_check.get("nodes", []),
                "topics": launch_check.get("topics", []),
                "expected_topics": launch_check.get("expected_topics", []),
                "missing_expected_topics": launch_check.get("missing_expected_topics", []),
            },
        },
    }


def run_ros2_validation(
    export_dir: Path,
    ros2_generation: Dict[str, Any],
    run_launch_check: bool = True,
) -> Dict[str, Any]:
    """
    Validates the generated ROS2 package after export.

    This runs:
    - expected file check
    - colcon build
    - installed share file check
    - smoke script
    - optional launch/node/topic check
    """
    if not isinstance(ros2_generation, dict):
        return {
            "status": "skipped",
            "passed": False,
            "reason": "ros2_generation was not a dictionary.",
        }

    if ros2_generation.get("status") != "generated":
        return {
            "status": "skipped",
            "passed": False,
            "reason": "ROS2 package was not generated successfully.",
            "ros2_generation_status": ros2_generation.get("status"),
        }

    package_name = ros2_generation.get("package_name")

    if not package_name:
        return {
            "status": "failed",
            "passed": False,
            "error": "ROS2 generation did not return a package_name.",
        }

    workspace_dir = export_dir / "generated_ros2"

    if not workspace_dir.exists():
        return {
            "status": "failed",
            "passed": False,
            "error": f"Generated ROS2 workspace does not exist: {workspace_dir}",
        }

    try:
        report = validate_ros2_package(
            workspace_dir=workspace_dir,
            package_name=package_name,
            run_launch_check=run_launch_check,
            clean_build=True,
        )

        return compact_validation_result(report) or {
            "status": "validated",
            "passed": bool(report.get("passed", False)),
            "package_name": package_name,
            "report_paths": report.get("report_paths", {}),
        }

    except Exception as error:
        return {
            "status": "failed",
            "passed": False,
            "package_name": package_name,
            "workspace_dir": str(workspace_dir),
            "error": str(error),
        }


def export_mission_files(
    mission_result: Dict[str, Any],
    validate_ros2: bool = True,
    ros2_launch_check: bool = True,
) -> Dict[str, Any]:
    """
    Writes a completed OMNI mission result into an export folder.

    Expected mission_result fields:
    - mission
    - result_id
    - final_report
    - agents
    - artifacts
    - validation
    - critique
    - revision

    If a ROS2 package is generated, this can also auto-run the ROS2 build validator.
    """

    if not isinstance(mission_result, dict):
        raise ValueError("mission_result must be a dictionary.")

    mission = mission_result.get("mission", "omni_mission")
    result_id = mission_result.get("result_id") or datetime.now().isoformat().replace(":", "-")
    folder_name = safe_folder_name(f"{mission}_{result_id}")

    export_dir = OUTPUT_ROOT / folder_name
    agent_dir = export_dir / "agent_reports"
    artifact_dir = export_dir / "artifacts"

    agents = mission_result.get("agents", {}) or {}
    artifacts = mission_result.get("artifacts", {}) or {}

    if not isinstance(agents, dict):
        agents = {}

    if not isinstance(artifacts, dict):
        artifacts = {}

    written_files = []

    def record(path: Path) -> None:
        relative_path = str(path.relative_to(export_dir))

        if relative_path not in written_files:
            written_files.append(relative_path)

    def record_generated_file(relative_path: str) -> None:
        if relative_path and relative_path not in written_files:
            written_files.append(relative_path)

    # ---------------------------------------------------------
    # Core mission files
    # ---------------------------------------------------------
    path = export_dir / "mission.json"
    write_json(path, mission_result)
    record(path)

    path = export_dir / "mission_report.md"
    write_text(
        path,
        mission_result.get("final_report")
        or mission_result.get("final_synthesis")
        or "",
    )
    record(path)

    path = export_dir / "final_blueprint.md"
    write_text(
        path,
        mission_result.get("final_decision")
        or mission_result.get("final_synthesis")
        or "",
    )
    record(path)

    path = export_dir / "critique.json"
    write_json(path, mission_result.get("critique", {}))
    record(path)

    path = export_dir / "revision.json"
    write_json(path, mission_result.get("revision", {}))
    record(path)

    path = export_dir / "validation.json"
    write_json(path, mission_result.get("validation", {}))
    record(path)

    # ---------------------------------------------------------
    # Agent reports
    # ---------------------------------------------------------
    for agent_name in ["omni", "sky", "korva", "isy", "oli", "pluto", "qaz"]:
        path = agent_dir / f"{agent_name}.md"
        write_text(path, agents.get(agent_name, f"No {agent_name} report returned."))
        record(path)

    # ---------------------------------------------------------
    # Structured artifacts
    # ---------------------------------------------------------
    artifact_json_files = {
        "ros2_node_graph.json": artifacts.get("ros2_node_graph", {}),
        "component_tree.json": artifacts.get("component_tree", []),
        "blueprint_plan.json": artifacts.get("blueprint_plan", []),
        "hardware_architecture.json": artifacts.get("hardware_architecture", []),
        "fusion360_concept.json": artifacts.get("fusion360_concept", {}),
        "ros2_package_plan.json": artifacts.get("ros2_package_plan", {}),
        "export_files.json": artifacts.get("export_files", []),
        "next_artifacts.json": artifacts.get("next_artifacts", []),
    }

    for filename, data in artifact_json_files.items():
        path = artifact_dir / filename
        write_json(path, data)
        record(path)

    # ---------------------------------------------------------
    # CSV / Markdown artifacts
    # ---------------------------------------------------------
    path = artifact_dir / "risk_matrix.csv"
    write_csv(path, artifacts.get("risk_matrix", []))
    record(path)

    path = artifact_dir / "test_checklist.md"
    write_text(
        path,
        markdown_list("Test Checklist", artifacts.get("test_checklist", [])),
    )
    record(path)

    path = artifact_dir / "approval_gates.md"
    write_text(
        path,
        markdown_list("Approval Gates", artifacts.get("approval_gates", [])),
    )
    record(path)

    # ---------------------------------------------------------
    # Generated ROS2 package scaffold + validation
    # ---------------------------------------------------------
    ros2_generation = None
    ros2_validation = None

    if should_generate_ros2_package(artifacts):
        try:
            ros2_generation = generate_ros2_package(mission_result, export_dir)

            path = artifact_dir / "ros2_generation_summary.json"
            write_json(path, ros2_generation)
            record(path)

            for generated_file in ros2_generation.get("files", []):
                record_generated_file(generated_file)

            if validate_ros2:
                ros2_validation = run_ros2_validation(
                    export_dir=export_dir,
                    ros2_generation=ros2_generation,
                    run_launch_check=ros2_launch_check,
                )

                path = artifact_dir / "ros2_validation_summary.json"
                write_json(path, ros2_validation)
                record(path)

                report_paths = ros2_validation.get("report_paths", {}) if isinstance(ros2_validation, dict) else {}

                for report_path in report_paths.values():
                    try:
                        report_file = Path(report_path)
                        if report_file.exists():
                            record(report_file)
                    except Exception:
                        pass

        except Exception as error:
            ros2_generation = {
                "status": "failed",
                "error": str(error),
            }

            path = artifact_dir / "ros2_generation_summary.json"
            write_json(path, ros2_generation)
            record(path)

            ros2_validation = {
                "status": "skipped",
                "passed": False,
                "reason": "ROS2 generation failed, so validation was skipped.",
            }

            path = artifact_dir / "ros2_validation_summary.json"
            write_json(path, ros2_validation)
            record(path)

    # ---------------------------------------------------------
    # Human-readable README
    # ---------------------------------------------------------
    validation = mission_result.get("validation", {}) or {}

    ros2_generation_status = (
        ros2_generation.get("status", "not_generated")
        if isinstance(ros2_generation, dict)
        else "not_generated"
    )
    ros2_package_name = (
        ros2_generation.get("package_name", "none")
        if isinstance(ros2_generation, dict)
        else "none"
    )
    ros2_validation_status = (
        ros2_validation.get("status", "not_run")
        if isinstance(ros2_validation, dict)
        else "not_run"
    )
    ros2_validation_passed = (
        ros2_validation.get("passed", False)
        if isinstance(ros2_validation, dict)
        else False
    )

    readme = f"""# OMNI Mission Export

## Mission
{mission}

## Result ID
{result_id}

## Status
{mission_result.get("status", "unknown")}

## Validation
- Verdict: {validation.get("verdict", "unknown")}
- Score: {validation.get("score", "unknown")}

## ROS2 Package Generation
- Status: {ros2_generation_status}
- Package: {ros2_package_name}

## ROS2 Build Verification
- Status: {ros2_validation_status}
- Passed: {ros2_validation_passed}

## Files
{chr(10).join(f"- {file}" for file in written_files)}
"""

    path = export_dir / "README.md"
    write_text(path, readme)
    record(path)

    return {
        "status": "exported",
        "folder_name": folder_name,
        "export_dir": str(export_dir),
        "files": written_files,
        "file_count": len(written_files),
        "ros2_generation": ros2_generation,
        "ros2_validation": ros2_validation,
    }