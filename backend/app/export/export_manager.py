import csv
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from backend.app.generators.ros2_package_generator import generate_ros2_package


OUTPUT_ROOT = Path("outputs") / "omni_missions"


def safe_folder_name(text: str) -> str:
    value = str(text or "omni_mission").lower()
    value = value.replace("/", "_").replace("\\", "_").replace(" ", "_")
    value = "".join(ch for ch in value if ch.isalnum() or ch in ["_", "-"])
    value = "_".join(part for part in value.split("_") if part)
    return value[:90] or "omni_mission"


def write_text(path: Path, content: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(str(content or ""), encoding="utf-8")


def write_json(path: Path, data: Any):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def write_csv(path: Path, rows: List[Dict[str, Any]]):
    path.parent.mkdir(parents=True, exist_ok=True)

    if not rows:
        path.write_text("", encoding="utf-8")
        return

    clean_rows = [
        row for row in rows
        if isinstance(row, dict)
    ]

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


def export_mission_files(mission_result: Dict[str, Any]) -> Dict[str, Any]:
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

    def record(path: Path):
        relative_path = str(path.relative_to(export_dir))

        if relative_path not in written_files:
            written_files.append(relative_path)

    def record_generated_file(relative_path: str):
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
    # Generated ROS2 package scaffold
    # ---------------------------------------------------------
    ros2_generation = None

    if should_generate_ros2_package(artifacts):
        try:
            ros2_generation = generate_ros2_package(mission_result, export_dir)

            path = artifact_dir / "ros2_generation_summary.json"
            write_json(path, ros2_generation)
            record(path)

            for generated_file in ros2_generation.get("files", []):
                record_generated_file(generated_file)

        except Exception as error:
            ros2_generation = {
                "status": "failed",
                "error": str(error),
            }

            path = artifact_dir / "ros2_generation_summary.json"
            write_json(path, ros2_generation)
            record(path)

    # ---------------------------------------------------------
    # Human-readable README
    # ---------------------------------------------------------
    validation = mission_result.get("validation", {}) or {}

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
- Status: {ros2_generation.get("status", "not_generated") if isinstance(ros2_generation, dict) else "not_generated"}
- Package: {ros2_generation.get("package_name", "none") if isinstance(ros2_generation, dict) else "none"}

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
    }