import csv
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from backend.app.generators.ros2_package_generator import generate_ros2_package
from backend.app.generators.fusion360_script_generator import (
    generate_fusion360_export,
    should_generate_fusion360_script,
)
from backend.app.generators.kicad_project_generator import KiCadProjectGenerator
from backend.app.generators.mission_report_generator import generate_mission_report
from backend.app.validators.ros2_build_validator import validate_ros2_package
from backend.app.omni_core.formatters import safe_folder_name, sanitize_payload


OUTPUT_ROOT = Path("outputs") / "omni_missions"


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(str(content or ""), encoding="utf-8")


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False, default=str),
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


def as_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> List[Any]:
    return value if isinstance(value, list) else []


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


def should_generate_kicad_package(mission_result: Dict[str, Any]) -> bool:
    """
    Decide whether OMNI should generate a starter KiCAD electronics package.

    This scans the full mission result because electronics-related language may
    appear in mission text, agent outputs, artifacts, validation, or reports.
    """
    if not isinstance(mission_result, dict):
        return False

    text_blob = json.dumps(mission_result, default=str).lower()

    keywords = [
        "kicad",
        "pcb",
        "electronics",
        "electrical",
        "circuit",
        "schematic",
        "battery",
        "sensor",
        "sensors",
        "motor driver",
        "controller board",
        "power budget",
        "connector",
        "connectors",
        "imu",
        "microcontroller",
        "raspberry pi",
        "esp32",
        "stm32",
        "rp2040",
    ]

    return any(keyword in text_blob for keyword in keywords)


def build_starter_electronics_plan(mission_result: Dict[str, Any]) -> Dict[str, Any]:
    """
    Build a conservative starter electronics plan for KiCAD export.

    This creates useful electronics artifacts but does not claim the design is
    fabrication-ready. It should be reviewed and refined before real PCB work.
    """
    mission_text = (
        mission_result.get("mission")
        or mission_result.get("mission_text")
        or mission_result.get("user_prompt")
        or mission_result.get("summary")
        or "OMNI mission"
    )

    artifacts = as_dict(mission_result.get("artifacts", {}))

    hardware_architecture = artifacts.get("hardware_architecture", [])
    component_tree = artifacts.get("component_tree", [])
    ros2_node_graph = artifacts.get("ros2_node_graph", {})
    blueprint_plan = artifacts.get("blueprint_plan", [])

    return {
        "summary": f"Starter electronics package generated from mission: {mission_text}",
        "source_context": {
            "hardware_architecture": hardware_architecture,
            "component_tree": component_tree,
            "ros2_node_graph": ros2_node_graph,
            "blueprint_plan": blueprint_plan,
        },
        "power_budget": {
            "battery": "TBD",
            "logic_voltage": "3.3V",
            "actuator_voltage": "TBD",
            "estimated_peak_current_a": "TBD",
            "notes": [
                "This is a starter electronics package.",
                "Battery chemistry, regulator sizing, and peak current must be validated before fabrication.",
                "Actuator stall current must be checked before selecting connectors and trace widths.",
                "PCB dimensions should be checked against the CAD electronics bay before layout.",
            ],
        },
        "connector_map": {
            "J1": "Battery or external power input",
            "J2": "Programming/debug header",
            "J3": "Primary sensor header",
            "J4": "Secondary sensor/I2C/SPI header",
            "J5": "Actuator or motor driver connector bank",
        },
        "bom": [
            {
                "reference": "U1",
                "quantity": 1,
                "component": "Main controller",
                "value": "TBD microcontroller or companion computer",
                "footprint": "TBD",
                "notes": "Select based on required I/O, compute, ROS2 bridge needs, and power budget.",
            },
            {
                "reference": "U2",
                "quantity": 1,
                "component": "Voltage regulator",
                "value": "5V or 3.3V TBD",
                "footprint": "TBD",
                "notes": "Must be sized against sensor, logic, and actuator current loads.",
            },
            {
                "reference": "J1",
                "quantity": 1,
                "component": "Power input connector",
                "value": "TBD",
                "footprint": "TBD",
                "notes": "Add fuse, reverse-polarity protection, and power switch before fabrication.",
            },
            {
                "reference": "J2",
                "quantity": 1,
                "component": "Programming/debug header",
                "value": "SWD/UART/USB TBD",
                "footprint": "TBD",
                "notes": "Depends on selected controller.",
            },
            {
                "reference": "J3",
                "quantity": 1,
                "component": "Sensor connector",
                "value": "I2C/SPI/UART TBD",
                "footprint": "TBD",
                "notes": "Map to mission-specific sensors after component selection.",
            },
            {
                "reference": "J5",
                "quantity": 1,
                "component": "Actuator connector bank",
                "value": "Motor/servo outputs TBD",
                "footprint": "TBD",
                "notes": "Connector current rating must match actuator peak current.",
            },
        ],
    }


def compact_validation_result(
    validation_report: Optional[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    """
    Return a compact frontend/API-friendly summary of the full ROS2 validation report.

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
                "missing_expected_topics": launch_check.get(
                    "missing_expected_topics",
                    [],
                ),
            },
        },
    }


def run_ros2_validation(
    export_dir: Path,
    ros2_generation: Dict[str, Any],
    run_launch_check: bool = True,
) -> Dict[str, Any]:
    """
    Validate the generated ROS2 package after export.

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
    Write a completed OMNI mission result into an export folder.

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
    If CAD/Fusion content is detected, this can generate a Fusion 360 Python script.
    If electronics/PCB content is detected, this can generate a starter KiCAD package.
    """
    if not isinstance(mission_result, dict):
        raise ValueError("mission_result must be a dictionary.")

    # Centralized cleanup: remove legacy names before writing mission exports.
    mission_result = sanitize_payload(mission_result)

    mission = (
        mission_result.get("mission")
        or mission_result.get("mission_text")
        or mission_result.get("user_prompt")
        or "omni_mission"
    )

    result_id = mission_result.get("result_id") or datetime.now().isoformat().replace(
        ":",
        "-",
    )

    folder_name = safe_folder_name(f"{mission}_{result_id}")

    export_dir = OUTPUT_ROOT / folder_name
    agent_dir = export_dir / "agent_reports"
    artifact_dir = export_dir / "artifacts"

    agents = as_dict(mission_result.get("agents", {}))
    artifacts = as_dict(mission_result.get("artifacts", {}))

    written_files: List[str] = []

    def record(path: Path) -> None:
        """
        Record a written file path relative to export_dir whenever possible.

        If a generator returns an absolute path outside export_dir, fall back to
        recording the string path instead of crashing.
        """
        try:
            path = Path(path)
            relative_path = str(path.relative_to(export_dir))
        except Exception:
            relative_path = str(path)

        if relative_path not in written_files:
            written_files.append(relative_path)

    def record_generated_file(path_value: Any) -> None:
        if not path_value:
            return

        try:
            generated_path = Path(str(path_value))

            if generated_path.exists():
                record(generated_path)
            else:
                path_string = str(path_value)
                if path_string not in written_files:
                    written_files.append(path_string)

        except Exception:
            path_string = str(path_value)
            if path_string not in written_files:
                written_files.append(path_string)

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
    write_csv(path, as_list(artifacts.get("risk_matrix", [])))
    record(path)

    path = artifact_dir / "test_checklist.md"
    write_text(
        path,
        markdown_list("Test Checklist", as_list(artifacts.get("test_checklist", []))),
    )
    record(path)

    path = artifact_dir / "approval_gates.md"
    write_text(
        path,
        markdown_list("Approval Gates", as_list(artifacts.get("approval_gates", []))),
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

                report_paths = (
                    ros2_validation.get("report_paths", {})
                    if isinstance(ros2_validation, dict)
                    else {}
                )

                for report_path in report_paths.values():
                    record_generated_file(report_path)

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
    # Generated Fusion 360 concept script
    # ---------------------------------------------------------
    fusion360_generation = None

    if should_generate_fusion360_script(mission_result):
        try:
            fusion360_generation = generate_fusion360_export(
                mission_result=mission_result,
                output_root=export_dir,
            )

            path = artifact_dir / "fusion360_generation_summary.json"
            write_json(path, fusion360_generation)
            record(path)

            for generated_file in fusion360_generation.get("files", []):
                record_generated_file(generated_file)

        except Exception as error:
            fusion360_generation = {
                "status": "failed",
                "error": str(error),
            }

            path = artifact_dir / "fusion360_generation_summary.json"
            write_json(path, fusion360_generation)
            record(path)

    # ---------------------------------------------------------
    # Generated KiCAD electronics package
    # ---------------------------------------------------------
    kicad_generation = None

    if should_generate_kicad_package(mission_result):
        try:
            electronics_plan = build_starter_electronics_plan(mission_result)

            kicad_files = KiCadProjectGenerator(
                output_root=export_dir.parent,
            ).generate(
                mission_slug=export_dir.name,
                electronics_plan=electronics_plan,
            )

            kicad_generation = {
                "status": "generated",
                "package_type": "starter_kicad_electronics_package",
                "files": list(kicad_files.values()),
                "file_map": kicad_files,
            }

            path = artifact_dir / "kicad_generation_summary.json"
            write_json(path, kicad_generation)
            record(path)

            for generated_file in kicad_generation.get("files", []):
                record_generated_file(generated_file)

        except Exception as error:
            kicad_generation = {
                "status": "failed",
                "error": str(error),
            }

            path = artifact_dir / "kicad_generation_summary.json"
            write_json(path, kicad_generation)
            record(path)

    # ---------------------------------------------------------
    # Human-readable README values
    # ---------------------------------------------------------
    validation = as_dict(mission_result.get("validation", {}))

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

    fusion360_generation_status = (
        fusion360_generation.get("status", "not_generated")
        if isinstance(fusion360_generation, dict)
        else "not_generated"
    )
    fusion360_project_type = (
        fusion360_generation.get("project_type", "none")
        if isinstance(fusion360_generation, dict)
        else "none"
    )
    fusion360_model_name = (
        fusion360_generation.get("model_name", "none")
        if isinstance(fusion360_generation, dict)
        else "none"
    )

    kicad_generation_status = (
        kicad_generation.get("status", "not_generated")
        if isinstance(kicad_generation, dict)
        else "not_generated"
    )
    kicad_package_type = (
        kicad_generation.get("package_type", "none")
        if isinstance(kicad_generation, dict)
        else "none"
    )

    # ---------------------------------------------------------
    # OMNI Mission Report / Engineering Provenance Dossier
    # ---------------------------------------------------------
    mission_report = None

    try:
        report_validation = {
            "status": validation.get(
                "verdict",
                mission_result.get("status", "unknown"),
            ),
            "summary": (
                "Mission export completed with generated artifacts, validation data, "
                "and engineering review notes."
            ),
            "validation": validation,
            "ros2_validation": ros2_validation,
            "fusion360_generation": fusion360_generation,
            "kicad_generation": kicad_generation,
        }

        mission_report = generate_mission_report(
            mission_text=mission,
            mission_result=mission_result,
            validation_result=report_validation,
            output_root=OUTPUT_ROOT,
            mission_slug=folder_name,
        )

        for report_key in ["report_file", "artifact_manifest", "provenance_record"]:
            report_path_value = mission_report.get(report_key)

            if report_path_value:
                record_generated_file(report_path_value)

    except Exception as error:
        mission_report = {
            "status": "failed",
            "error": str(error),
        }

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

## Fusion 360 CAD Generation
- Status: {fusion360_generation_status}
- Project Type: {fusion360_project_type}
- Model Name: {fusion360_model_name}

## KiCAD Electronics Package
- Status: {kicad_generation_status}
- Package Type: {kicad_package_type}

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
        "fusion360_generation": fusion360_generation,
        "kicad_generation": kicad_generation,
        "mission_report": mission_report,
    }