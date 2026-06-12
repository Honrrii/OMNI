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
from backend.app.engineering.kicad_knowledge_gate_validator import validate_kicad_package
from backend.app.engineering.morphology_planner import plan_morphology_dict
from backend.app.engineering.morphology_gate_validator import validate_morphology_export


OUTPUT_ROOT = Path("outputs") / "omni_missions"

# -------------------------------------------------------------------------
# Visual Bay delivery bounds
# -------------------------------------------------------------------------

MAX_VISUAL_BAY_PREVIEW_ASSETS = 25
MAX_VISUAL_BAY_PATH_CHARS     = 240
MAX_VISUAL_BAY_NOTE_CHARS     = 180
MAX_VISUAL_BAY_NOTES          = 3

_PREVIEW_ASSET_ALLOWLIST: frozenset = frozenset({
    "path",
    "kind",
    "browser_preview_ready",
    "browser_preview_candidate",
    "engineering_only",
    "execution_blocked",
    "requires_conversion",
    "requires_external_tool",
    "notes",
})


def _sanitize_preview_assets(
    assets: List[Dict[str, Any]],
    export_dir: Optional[Path] = None,
    mission_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Bound and sanitize preview_assets before delivering them in the API summary.

    - Caps list to MAX_VISUAL_BAY_PREVIEW_ASSETS.
    - Strips fields not in the allowlist.
    - Ensures path is relative; absolute paths are rebased or replaced with filename.
    - Truncates paths longer than MAX_VISUAL_BAY_PATH_CHARS.
    - Caps notes to MAX_VISUAL_BAY_NOTES entries, each truncated to MAX_VISUAL_BAY_NOTE_CHARS.
    - Adds asset_url for servable (non-execution-blocked, allowed-extension) assets when
      mission_id is provided; omits asset_url for blocked/script assets.
    """
    if not isinstance(assets, list):
        return []

    # Import asset service once; skip silently if unavailable.
    _svc = None
    if mission_id:
        try:
            from backend.app.visual_bay import asset_service as _svc  # type: ignore[assignment]
        except Exception:
            pass

    result: List[Dict[str, Any]] = []
    for asset in assets[:MAX_VISUAL_BAY_PREVIEW_ASSETS]:
        if not isinstance(asset, dict):
            continue

        clean: Dict[str, Any] = {
            field: asset[field]
            for field in _PREVIEW_ASSET_ALLOWLIST
            if field in asset
        }

        raw_path = str(clean.get("path", ""))
        if raw_path:
            p = Path(raw_path)
            if p.is_absolute():
                if export_dir is not None:
                    try:
                        raw_path = str(p.relative_to(export_dir))
                    except ValueError:
                        raw_path = p.name
                else:
                    raw_path = p.name
            if len(raw_path) > MAX_VISUAL_BAY_PATH_CHARS:
                raw_path = raw_path[:MAX_VISUAL_BAY_PATH_CHARS]
            clean["path"] = raw_path

        notes = clean.get("notes")
        if isinstance(notes, list):
            bounded: List[str] = []
            for note in notes[:MAX_VISUAL_BAY_NOTES]:
                s = str(note)
                bounded.append(s[:MAX_VISUAL_BAY_NOTE_CHARS] if len(s) > MAX_VISUAL_BAY_NOTE_CHARS else s)
            clean["notes"] = bounded
        else:
            clean["notes"] = []

        # Attach asset_url only for servable, non-execution-blocked assets.
        if _svc is not None and mission_id and clean.get("path"):
            try:
                if _svc.is_visual_bay_asset_servable(clean):
                    clean["asset_url"] = _svc.build_visual_bay_asset_url(
                        mission_id, clean["path"]
                    )
            except Exception:
                pass

        result.append(clean)

    return result


# -------------------------------------------------------------------------
# Basic file writers
# -------------------------------------------------------------------------


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

    with path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(clean_rows)


# -------------------------------------------------------------------------
# Small helpers
# -------------------------------------------------------------------------


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


def append_unique(target: List[Any], values: List[Any]) -> List[Any]:
    existing = {str(item) for item in target}

    for value in values:
        if value is None:
            continue

        value_text = str(value).strip()
        if not value_text or value_text in existing:
            continue

        target.append(value)
        existing.add(value_text)

    return target


def extract_mission_text(mission_result: Dict[str, Any]) -> str:
    """
    Pull the best available mission/prompt text from an OMNI mission result.

    This is used by export generators so downstream modules can detect whether
    a mission needs ROS2, Fusion, KiCad, CAD context, electronics context, etc.
    """
    if not isinstance(mission_result, dict):
        return "omni_mission"

    return str(
        mission_result.get("mission")
        or mission_result.get("mission_text")
        or mission_result.get("prompt")
        or mission_result.get("user_prompt")
        or mission_result.get("title")
        or mission_result.get("summary")
        or "omni_mission"
    )


# -------------------------------------------------------------------------
# Export trigger logic
# -------------------------------------------------------------------------


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
    Decide whether OMNI should generate a starter KiCad electronics package.

    This scans the full mission result because electronics-related language may
    appear in mission text, agent outputs, artifacts, validation, or reports.
    """
    if not isinstance(mission_result, dict):
        return False

    text_blob = json.dumps(mission_result, default=str).lower()

    keywords = [
        "kicad",
        "pcb",
        "printed circuit board",
        "electronics",
        "electrical",
        "circuit",
        "schematic",
        "battery",
        "battery input",
        "voltage regulator",
        "power regulator",
        "power budget",
        "power distribution",
        "sensor",
        "sensors",
        "imu",
        "camera connector",
        "motor driver",
        "servo connector",
        "actuator connector",
        "controller board",
        "connector",
        "connectors",
        "microcontroller",
        "raspberry pi",
        "esp32",
        "stm32",
        "rp2040",
        "footprint",
        "symbol",
        "bom",
        "gerber",
        "drill file",
    ]

    return any(keyword in text_blob for keyword in keywords)


# -------------------------------------------------------------------------
# Starter KiCad electronics planning
# -------------------------------------------------------------------------


def build_starter_electronics_plan(
    mission_result: Dict[str, Any],
    morphology_plan: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Build a conservative starter electronics plan for KiCad export.

    This creates useful electronics artifacts but does not claim the design is
    fabrication-ready. It should be reviewed and refined before real PCB work.

    When morphology_plan is present, electronics placement, battery placement,
    connector intent, and power rails are aligned to the physical body plan.
    """
    mission_text = extract_mission_text(mission_result)
    artifacts = as_dict(mission_result.get("artifacts", {}))

    morphology_plan = as_dict(morphology_plan or artifacts.get("morphology_plan", {}))
    body_plan = as_dict(morphology_plan.get("body_plan", {}))
    electronics_intent = as_dict(morphology_plan.get("electronics_intent", {}))

    morphology_id = morphology_plan.get("morphology_id", "")
    project_family = morphology_plan.get("project_family", "")
    body_segments = as_list(body_plan.get("segments", []))
    required_features = as_list(body_plan.get("required_features", []))
    mounting_points = as_list(body_plan.get("mounting_points", []))

    primary_pcb_location = electronics_intent.get("primary_pcb_location", "")
    battery_location = electronics_intent.get("battery_location", "")
    sensor_connectors = as_list(electronics_intent.get("sensor_connectors", []))
    actuator_connectors = as_list(electronics_intent.get("actuator_connectors", []))
    power_rails = as_list(electronics_intent.get("power_rails", []))

    hardware_architecture = artifacts.get("hardware_architecture", [])
    component_tree = artifacts.get("component_tree", [])
    ros2_node_graph = artifacts.get("ros2_node_graph", {})
    blueprint_plan = artifacts.get("blueprint_plan", [])

    sensor_interfaces = [
        "I2C sensor header",
        "SPI/UART sensor header",
        "Camera or perception connector if mission requires vision",
    ]
    append_unique(sensor_interfaces, sensor_connectors)

    actuator_interfaces = [
        "Motor driver connector bank",
        "Servo connector bank",
        "PWM/control outputs",
    ]
    append_unique(actuator_interfaces, actuator_connectors)

    power_notes = [
        "This is a starter electronics package.",
        "Battery chemistry, regulator sizing, and peak current must be validated before fabrication.",
        "Actuator stall current must be checked before selecting connectors and trace widths.",
        "PCB dimensions should be checked against the CAD electronics bay before layout.",
        "Power traces must be wider than signal traces.",
        "Add input protection, fuse/protection stage, and reverse-polarity protection before fabrication.",
    ]

    if primary_pcb_location:
        power_notes.append(
            f"Morphology-aware PCB placement target: {primary_pcb_location}."
        )

    if battery_location:
        power_notes.append(
            f"Morphology-aware battery placement target: {battery_location}."
        )

    if power_rails:
        power_notes.append(
            "Morphology-requested rails: " + ", ".join(str(item) for item in power_rails)
        )

    connector_map = {
        "J1": "Battery or external power input",
        "J2": "Programming/debug header",
        "J3": "Primary sensor header",
        "J4": "Secondary sensor/I2C/SPI/UART header",
        "J5": "Actuator or motor driver connector bank",
        "J6": "Optional camera/perception connector",
    }

    if primary_pcb_location:
        connector_map["MORPH_PCB_LOCATION"] = primary_pcb_location

    if battery_location:
        connector_map["MORPH_BATTERY_LOCATION"] = battery_location

    for index, connector in enumerate(sensor_connectors, start=1):
        connector_map[f"MORPH_SENSOR_{index}"] = connector

    for index, connector in enumerate(actuator_connectors, start=1):
        connector_map[f"MORPH_ACTUATOR_{index}"] = connector

    bom = [
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
            "reference": "U3",
            "quantity": 1,
            "component": "Motor driver or actuator driver",
            "value": "TBD",
            "footprint": "TBD",
            "notes": "Select after actuator voltage, stall current, and channel count are known.",
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
        {
            "reference": "C1-C4",
            "quantity": 4,
            "component": "Decoupling capacitors",
            "value": "100nF typical",
            "footprint": "TBD",
            "notes": "Place close to IC power pins after actual IC selection.",
        },
    ]

    for index, connector in enumerate(sensor_connectors, start=1):
        bom.append(
            {
                "reference": f"MS{index}",
                "quantity": 1,
                "component": "Morphology sensor connector",
                "value": connector,
                "footprint": "TBD",
                "notes": "Required by morphology_plan electronics_intent.sensor_connectors.",
            }
        )

    for index, connector in enumerate(actuator_connectors, start=1):
        bom.append(
            {
                "reference": f"MA{index}",
                "quantity": 1,
                "component": "Morphology actuator connector",
                "value": connector,
                "footprint": "TBD",
                "notes": "Required by morphology_plan electronics_intent.actuator_connectors.",
            }
        )

    if primary_pcb_location:
        bom.append(
            {
                "reference": "MP1",
                "quantity": 1,
                "component": "Main PCB placement zone",
                "value": primary_pcb_location,
                "footprint": "Mechanical/placement TBD",
                "notes": "Placement target from morphology_plan electronics_intent.primary_pcb_location.",
            }
        )

    if battery_location:
        bom.append(
            {
                "reference": "MB1",
                "quantity": 1,
                "component": "Battery placement zone",
                "value": battery_location,
                "footprint": "Mechanical/placement TBD",
                "notes": "Placement target from morphology_plan electronics_intent.battery_location.",
            }
        )

    return {
        "summary": f"Starter electronics package generated from mission: {mission_text}",
        "source_context": {
            "mission_text": mission_text,
            "hardware_architecture": hardware_architecture,
            "component_tree": component_tree,
            "ros2_node_graph": ros2_node_graph,
            "blueprint_plan": blueprint_plan,
            "morphology_plan": morphology_plan,
        },
        "morphology_electronics_context": {
            "morphology_id": morphology_id,
            "project_family": project_family,
            "body_segments": body_segments,
            "required_features": required_features,
            "mounting_points": mounting_points,
            "primary_pcb_location": primary_pcb_location,
            "battery_location": battery_location,
            "sensor_connectors": sensor_connectors,
            "actuator_connectors": actuator_connectors,
            "power_rails": power_rails,
        },
        "electronics_architecture": {
            "controller": "TBD microcontroller, companion computer, or ROS2 bridge device",
            "power_input": "TBD battery or external regulated input",
            "logic_power": "3.3V and/or 5V regulated logic rail",
            "actuator_power": "TBD motor/servo voltage rail",
            "sensor_interfaces": sensor_interfaces,
            "actuator_interfaces": actuator_interfaces,
            "debug_interfaces": [
                "Programming/debug header",
                "UART or USB debug path",
            ],
            "morphology_id": morphology_id,
            "project_family": project_family,
            "body_segments": body_segments,
            "primary_pcb_location": primary_pcb_location,
            "battery_location": battery_location,
            "morphology_power_rails": power_rails,
        },
        "power_budget": {
            "battery": "TBD",
            "logic_voltage": "3.3V",
            "actuator_voltage": "TBD",
            "estimated_peak_current_a": "TBD",
            "morphology_primary_pcb_location": primary_pcb_location,
            "morphology_battery_location": battery_location,
            "morphology_power_rails": power_rails,
            "notes": power_notes,
        },
        "connector_map": connector_map,
        "bom": bom,
    }


# -------------------------------------------------------------------------
# ROS2 validation helpers
# -------------------------------------------------------------------------


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


# -------------------------------------------------------------------------
# KiCad validation helper
# -------------------------------------------------------------------------


def run_kicad_knowledge_gate(export_dir: Path) -> Dict[str, Any]:
    """
    Validate the generated KiCad starter package.

    This checks the generated_kicad folder for required project files, support
    artifacts, placeholder warnings, manufacturing-readiness notes, and the
    KiCad knowledge context file.
    """
    try:
        return validate_kicad_package(export_dir)
    except Exception as error:
        return {
            "validator": "kicad_knowledge_gate_validator",
            "status": "failed",
            "summary": {
                "blockers": 1,
                "warnings": 0,
                "info": 0,
                "total_issues": 1,
            },
            "issues": [
                {
                    "rule_id": "KICAD.VALIDATOR.001",
                    "severity": "blocker",
                    "message": f"KiCad knowledge gate validator failed: {error}",
                    "file": None,
                }
            ],
        }


# -------------------------------------------------------------------------
# Morphology validation helper
# -------------------------------------------------------------------------


def run_morphology_gate(export_dir: Path) -> Dict[str, Any]:
    """
    Validate whether generated artifacts obey artifacts/morphology_plan.json.

    This checks morphology identity, Fusion PROJECT_TYPE/MODEL_NAME/MORPHOLOGY_ID,
    required body terms, morphology leakage, and light KiCad/ROS2 morphology intent.
    """
    try:
        return validate_morphology_export(export_dir)
    except Exception as error:
        return {
            "validator": "morphology_gate_validator",
            "status": "failed",
            "summary": {
                "blockers": 1,
                "warnings": 0,
                "info": 0,
                "total_issues": 1,
            },
            "issues": [
                {
                    "rule_id": "MORPH.VALIDATOR.001",
                    "severity": "blocker",
                    "message": f"Morphology Gate validator failed: {error}",
                    "file": None,
                }
            ],
        }


# -------------------------------------------------------------------------
# Mission Knowledge Graph + Review helper
# -------------------------------------------------------------------------


def _write_graph_review(export_dir: Path) -> Dict[str, Any]:
    """
    Build a MissionKnowledgeGraph from export_dir/mission.json, run the
    deterministic reviewer, and write both output files into export_dir.

    Assumes mission.json already exists in export_dir (written by
    export_mission_files before this is called).  May raise; callers are
    responsible for catching errors.
    """
    from backend.app.mission_graph.builder import build_graph
    from backend.app.mission_graph.finding_projection import project_review_findings
    from backend.app.mission_graph.reviewer import review_graph

    graph = build_graph(export_dir)
    review = review_graph(graph)

    graph_path = export_dir / "mission_graph.json"
    write_json(graph_path, graph.model_dump(mode="json"))

    # Additive findings projection: a normalized, read-only view of the
    # review's issues + consistency_warnings. Does not change the
    # MissionGraphReview model or any existing exported field.
    review_data = review.model_dump(mode="json")
    projection_items = project_review_findings(review)
    review_data["findings_projection"] = {
        "schema": "omni.mission_graph.findings_projection.v1",
        "source": "mission_graph_review",
        "origin_fields": ["issues", "consistency_warnings"],
        "count": len(projection_items),
        "items": projection_items,
    }

    review_path = export_dir / "mission_graph_review.json"
    write_json(review_path, review_data)

    return {
        "status": "reviewed",
        "graph_path": str(graph_path),
        "review_path": str(review_path),
        "issue_count": len(review.issues),
        "warning_count": len(review.warnings),
        "recommendation_count": len(review.recommendations),
        **review_data,
    }


def _write_candidate_evaluation(
    export_dir: Path,
    mission_result: Dict[str, Any],
    mission_text: str,
) -> Dict[str, Any]:
    """
    Write candidate_evaluation_report.json into export_dir.

    Priority order:
    1. Pre-computed candidate_evaluation from mission_result artifacts.
    2. Evaluate design_candidates from mission_result artifacts on-demand.
    3. Write a skipped marker if neither is available.

    Always writes the file. May raise; callers must catch.
    """
    from agents.candidate_evaluator import evaluate_design_candidates

    artifacts = as_dict(mission_result.get("artifacts", {}))
    report_path = export_dir / "candidate_evaluation_report.json"

    candidate_evaluation = artifacts.get("candidate_evaluation")
    if (
        isinstance(candidate_evaluation, dict)
        and candidate_evaluation.get("candidates_evaluated", 0) > 0
    ):
        write_json(report_path, candidate_evaluation)
        return {
            "status": "evaluated",
            "report_path": str(report_path),
            "candidates_evaluated": candidate_evaluation["candidates_evaluated"],
            "recommended_candidate_id": candidate_evaluation.get("recommended_candidate_id"),
            "ranking": candidate_evaluation.get("ranking", []),
        }

    design_candidates = artifacts.get("design_candidates")
    if isinstance(design_candidates, list) and design_candidates:
        candidate_evaluation = evaluate_design_candidates(
            design_candidates, mission_text=mission_text
        )
        write_json(report_path, candidate_evaluation)
        return {
            "status": "evaluated",
            "report_path": str(report_path),
            "candidates_evaluated": candidate_evaluation["candidates_evaluated"],
            "recommended_candidate_id": candidate_evaluation.get("recommended_candidate_id"),
            "ranking": candidate_evaluation.get("ranking", []),
        }

    skipped: Dict[str, Any] = {
        "status": "skipped",
        "reason": "No design candidates available for evaluation.",
    }
    write_json(report_path, skipped)
    return {
        "status": "skipped",
        "report_path": str(report_path),
        "candidates_evaluated": 0,
        "recommended_candidate_id": None,
        "ranking": [],
    }


def _write_mission_intent(
    export_dir: Path,
    mission_result: Dict[str, Any],
    mission_text: str,
) -> Dict[str, Any]:
    """
    Write mission_intent_report.json into export_dir.

    Priority order:
    1. Pre-computed mission_intent from mission_result artifacts.
    2. Compile from mission_text on-demand.
    3. Write a failed marker if compilation raises.

    Always writes the file. May raise; callers must catch.
    """
    from backend.app.omni_core.mission_intent import compile_mission_intent

    artifacts = as_dict(mission_result.get("artifacts", {}))
    report_path = export_dir / "mission_intent_report.json"

    precomputed = artifacts.get("mission_intent")
    if isinstance(precomputed, dict) and precomputed.get("mission_type"):
        intent = precomputed
    else:
        intent = compile_mission_intent(mission_text)

    write_json(report_path, intent)
    return {
        "status": "compiled",
        "report_path": str(report_path),
        "mission_type": intent.get("mission_type", ""),
        "platform_intent": intent.get("platform_intent"),
        "detected_domain_count": len(intent.get("detected_domains") or []),
        "open_question_count": len(intent.get("open_questions") or []),
    }


def _write_pluto_safety_gate(
    export_dir: Path,
    mission_result: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Write pluto_safety_gate_report.json into export_dir.

    Priority order:
    1. Pre-computed pluto_safety_gate from mission_result artifacts.
    2. Evaluate on-demand from artifacts["mission_intent"] / ["candidate_evaluation"].
    3. Write a failed marker if evaluation raises.

    Always writes the file. May raise; callers must catch.
    """
    from backend.app.omni_core.safety_gate import evaluate_safety_gate

    artifacts = as_dict(mission_result.get("artifacts", {}))
    report_path = export_dir / "pluto_safety_gate_report.json"

    precomputed = artifacts.get("pluto_safety_gate")
    if isinstance(precomputed, dict) and precomputed.get("gate") == "pluto_safety_gate":
        gate = precomputed
    else:
        gate = evaluate_safety_gate(
            mission_intent=artifacts.get("mission_intent"),
            candidate_evaluation=artifacts.get("candidate_evaluation"),
            artifacts=artifacts,
        )

    write_json(report_path, gate)
    return {
        "status": gate.get("status", "unknown"),
        "report_path": str(report_path),
        "risk_level": gate.get("risk_level", "unknown"),
        "required_human_review": bool(gate.get("required_human_review", False)),
        "blocker_count": len(gate.get("blockers") or []),
        "warning_count": len(gate.get("warnings") or []),
        "next_check_count": len(gate.get("required_next_checks") or []),
    }


def _write_aeroforge_reports(
    export_dir: Path,
    mission_text: str,
    artifacts: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Write aeroforge_intent_report.json and aeroforge_entry_gate_report.json
    when aerospace signals are detected.

    Priority order:
    1. Pre-computed aeroforge_intent / aeroforge_entry_gate from artifacts.
    2. Classify and evaluate on-demand from mission_text.
    3. If aerospace is not detected, return status "not_applicable" without
       writing any report files.

    May raise; callers must catch.
    """
    from backend.app.aeroforge.foundation import (
        classify_aeroforge_intent,
        evaluate_aeroforge_entry_gate,
    )

    precomputed_intent = artifacts.get("aeroforge_intent")
    if isinstance(precomputed_intent, dict):
        aeroforge_intent = precomputed_intent
    else:
        aeroforge_intent = classify_aeroforge_intent(
            mission_text=mission_text,
            mission_intent=as_dict(artifacts.get("mission_intent")),
        )

    if not aeroforge_intent.get("aerospace_detected", False):
        return {"status": "not_applicable", "aerospace_detected": False}

    precomputed_gate = artifacts.get("aeroforge_entry_gate")
    if isinstance(precomputed_gate, dict):
        aeroforge_entry_gate = precomputed_gate
    else:
        aeroforge_entry_gate = evaluate_aeroforge_entry_gate(
            mission_text=mission_text,
            mission_intent=as_dict(artifacts.get("mission_intent")),
            readiness=as_dict(artifacts.get("mission_intelligence_readiness")),
        )

    intent_path = export_dir / "aeroforge_intent_report.json"
    gate_path = export_dir / "aeroforge_entry_gate_report.json"

    write_json(intent_path, aeroforge_intent)
    write_json(gate_path, aeroforge_entry_gate)

    return {
        "status": "detected",
        "intent_report_path": str(intent_path),
        "entry_gate_report_path": str(gate_path),
        "entry_gate_status": aeroforge_entry_gate.get("status"),
        "aerospace_detected": True,
        "platform_hint": aeroforge_intent.get("platform_hint"),
        "domain_count": len(as_list(aeroforge_intent.get("aero_domains", []))),
        "human_review_required": bool(aeroforge_entry_gate.get("human_review_required", False)),
        "concept_stage_only": bool(aeroforge_entry_gate.get("concept_stage_only", True)),
    }


def _write_design_understanding(
    export_dir: Path,
    mission_text: str,
) -> Dict[str, Any]:
    """
    Build the mission graph and review, evaluate design understanding, and write
    design_understanding_report.json into export_dir.

    Rebuilds the graph/review objects so this helper stays self-contained and
    does not require callers to thread live objects through.  May raise; callers
    are responsible for catching errors.
    """
    from backend.app.mission_graph.builder import build_graph
    from backend.app.mission_graph.reviewer import review_graph
    from backend.app.cortex.design_evaluator import evaluate_design_understanding

    graph = build_graph(export_dir)
    review = review_graph(graph)

    report = evaluate_design_understanding(
        mission_text,
        graph=graph,
        graph_review=review,
    )

    report_path = export_dir / "design_understanding_report.json"
    write_json(report_path, report.model_dump(mode="json"))

    return {
        "status": "evaluated",
        "report_path": str(report_path),
        "intended_platform": report.intended_platform,
        "semantic_match_score": report.semantic_match_score,
        "strength_count": len(report.strengths),
        "mismatch_count": len(report.mismatches),
        "next_action_count": len(report.next_design_actions),
    }


# -------------------------------------------------------------------------
# Phase 17E — Engineering Brain export helpers
# -------------------------------------------------------------------------


def _extract_engineering_inputs(
    mission_result: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    """
    Return explicit engineering inputs from mission_result without inventing values.
    Checks:
      1. mission_result.artifacts.engineering_inputs
      2. mission_result.engineering_inputs
    Returns None when no valid dict is found.
    """
    if not isinstance(mission_result, dict):
        return None
    artifacts = mission_result.get("artifacts", {})
    if isinstance(artifacts, dict):
        ei = artifacts.get("engineering_inputs")
        if isinstance(ei, dict) and ei:
            return ei
    ei = mission_result.get("engineering_inputs")
    if isinstance(ei, dict) and ei:
        return ei
    return None


def _write_engineering_brain(
    export_dir: Path,
    mission_result: Dict[str, Any],
    mission_text: str,
) -> Dict[str, Any]:
    """
    Build and write the Phase 17 engineering brain reports.

    Writes:
      engineering_knowledge_selection_report.json
      engineering_input_readiness_report.json
      engineering_calculation_report.json

    Returns a compact summary dict.
    No LLM calls. No internet. No simulation. No engineering validation implied.
    Concept-stage estimates only.
    """
    from backend.app.engineering.knowledge_selection_report import (
        build_engineering_knowledge_selection_report,
    )
    from backend.app.engineering.input_readiness_report import (
        build_engineering_input_readiness_report,
    )
    from backend.app.engineering.calculation_engine import (
        build_engineering_calculation_report,
    )

    provided_inputs = _extract_engineering_inputs(mission_result)

    selection_report = build_engineering_knowledge_selection_report(
        mission_result=mission_result,
        mission_text=mission_text,
    )
    readiness_report = build_engineering_input_readiness_report(
        mission_result=mission_result,
        mission_text=mission_text,
        provided_inputs=provided_inputs,
    )
    calc_report = build_engineering_calculation_report(
        mission_result=mission_result,
        mission_text=mission_text,
        provided_inputs=provided_inputs,
    )

    sel_path      = export_dir / "engineering_knowledge_selection_report.json"
    readiness_path = export_dir / "engineering_input_readiness_report.json"
    calc_path     = export_dir / "engineering_calculation_report.json"

    write_json(sel_path, selection_report)
    write_json(readiness_path, readiness_report)
    write_json(calc_path, calc_report)

    readiness_summary = readiness_report.get("readiness_summary", {})

    return {
        "status": "generated",
        "knowledge_selection": {
            "schema":                    selection_report.get("schema"),
            "platform_intent":           selection_report.get("platform_intent"),
            "platform_resolution_source": selection_report.get("platform_resolution_source"),
            "selected_check_count":      selection_report.get("selected_check_count"),
            "report_path":               str(sel_path),
        },
        "input_readiness": {
            "schema":          readiness_report.get("schema"),
            "platform_intent": readiness_report.get("platform_intent"),
            "overall_status":  readiness_summary.get("overall_status"),
            "total_checks":    readiness_summary.get("total_checks"),
            "ready_count":     readiness_summary.get("ready_count"),
            "partial_count":   readiness_summary.get("partial_count"),
            "missing_count":   readiness_summary.get("missing_count"),
            "report_path":     str(readiness_path),
        },
        "calculations": {
            "schema":                      calc_report.get("schema"),
            "calculation_performed":       calc_report.get("calculation_performed"),
            "computed_metric_count":       calc_report.get("computed_metric_count"),
            "blocked_calculation_count":   calc_report.get("blocked_calculation_count"),
            "supported_calculation_count": calc_report.get("supported_calculation_count"),
            "report_path":                 str(calc_path),
        },
    }


# -------------------------------------------------------------------------
# Phase 18A — Concept Dossier export helper
# -------------------------------------------------------------------------


def _write_concept_dossier(
    export_dir: Path,
    mission_result: Dict[str, Any],
    mission_text: str,
) -> Dict[str, Any]:
    """
    Build and write the Phase 18A Concept Dossier Manifest.
    Reads Visual Bay and Engineering Brain reports already present in export_dir.
    Returns a compact summary dict.
    No LLM calls. No internet. No simulation. No engineering validation implied.
    """
    from backend.app.concept_dossier.manifest import build_concept_dossier_manifest

    manifest = build_concept_dossier_manifest(
        mission_result=mission_result,
        mission_text=mission_text,
        export_dir=export_dir,
    )

    dossier_path = export_dir / "concept_dossier_manifest.json"
    write_json(dossier_path, manifest)

    return {
        "status":      manifest.get("status", "generated"),
        "schema":      manifest.get("schema"),
        "panel_count": len(manifest.get("dossier_panels", [])),
        "report_path": str(dossier_path),
        "manifest":    manifest if isinstance(manifest, dict) else None,
    }


# -------------------------------------------------------------------------
# Main export function
# -------------------------------------------------------------------------


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
    If electronics/PCB content is detected, this can generate a starter KiCad package
    and run the KiCad Knowledge Gate validator.
    Every export also receives a morphology_plan.json and Morphology Gate report.
    """
    if not isinstance(mission_result, dict):
        raise ValueError("mission_result must be a dictionary.")

    mission_result = sanitize_payload(mission_result)

    mission = extract_mission_text(mission_result)

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

    morphology_plan = plan_morphology_dict(mission)
    artifacts["morphology_plan"] = morphology_plan
    mission_result["artifacts"] = artifacts

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
    # Mission Knowledge Graph + deterministic review
    # (mission.json is guaranteed to exist at this point)
    # ---------------------------------------------------------

    graph_review: Optional[Dict[str, Any]] = None

    try:
        graph_review = _write_graph_review(export_dir)
        record(Path(graph_review["graph_path"]))
        record(Path(graph_review["review_path"]))
    except Exception as error:
        graph_review = {"status": "failed", "error": str(error)}
        path = export_dir / "mission_graph_review.json"
        write_json(path, graph_review)
        record(path)

    # ---------------------------------------------------------
    # Cortex — design understanding evaluation
    # (depends on mission_graph.json written above)
    # ---------------------------------------------------------

    design_understanding: Optional[Dict[str, Any]] = None

    try:
        design_understanding = _write_design_understanding(export_dir, mission)
        record(Path(design_understanding["report_path"]))
    except Exception as error:
        design_understanding = {"status": "failed", "error": str(error)}
        path = export_dir / "design_understanding_report.json"
        write_json(path, design_understanding)
        record(path)

    # ---------------------------------------------------------
    # Candidate evaluation export
    # ---------------------------------------------------------

    candidate_evaluation_summary: Optional[Dict[str, Any]] = None

    try:
        candidate_evaluation_summary = _write_candidate_evaluation(
            export_dir, mission_result, mission
        )
        record(Path(candidate_evaluation_summary["report_path"]))
    except Exception as error:
        candidate_evaluation_summary = {"status": "failed", "error": str(error)}
        path = export_dir / "candidate_evaluation_report.json"
        write_json(path, candidate_evaluation_summary)
        record(path)

    # ---------------------------------------------------------
    # Mission intent export
    # ---------------------------------------------------------

    mission_intent_summary: Optional[Dict[str, Any]] = None

    try:
        mission_intent_summary = _write_mission_intent(export_dir, mission_result, mission)
        record(Path(mission_intent_summary["report_path"]))
    except Exception as error:
        mission_intent_summary = {"status": "failed", "error": str(error)}
        path = export_dir / "mission_intent_report.json"
        write_json(path, mission_intent_summary)
        record(path)

    # ---------------------------------------------------------
    # Pluto safety gate export
    # ---------------------------------------------------------

    pluto_safety_gate_summary: Optional[Dict[str, Any]] = None

    try:
        pluto_safety_gate_summary = _write_pluto_safety_gate(export_dir, mission_result)
        record(Path(pluto_safety_gate_summary["report_path"]))
    except Exception as error:
        pluto_safety_gate_summary = {"status": "failed", "error": str(error)}
        path = export_dir / "pluto_safety_gate_report.json"
        write_json(path, pluto_safety_gate_summary)
        record(path)

    # ---------------------------------------------------------
    # AeroForge aerospace concept reports
    # ---------------------------------------------------------

    aeroforge_summary: Optional[Dict[str, Any]] = None

    try:
        aeroforge_summary = _write_aeroforge_reports(
            export_dir=export_dir,
            mission_text=mission,
            artifacts=artifacts,
        )
        if aeroforge_summary.get("aerospace_detected"):
            record(Path(aeroforge_summary["intent_report_path"]))
            record(Path(aeroforge_summary["entry_gate_report_path"]))
    except Exception as error:
        aeroforge_summary = {"status": "failed", "error": str(error)}
        path = export_dir / "aeroforge_export_error.json"
        write_json(path, aeroforge_summary)
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
        "morphology_plan.json": artifacts.get("morphology_plan", {}),
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
    # Generated KiCad electronics package + Knowledge Gate
    # ---------------------------------------------------------

    kicad_generation = None
    kicad_validation = None

    if should_generate_kicad_package(mission_result):
        try:
            electronics_plan = build_starter_electronics_plan(
                mission_result=mission_result,
                morphology_plan=morphology_plan,
            )

            kicad_files = KiCadProjectGenerator(
                output_root=export_dir.parent,
            ).generate(
                mission_slug=export_dir.name,
                electronics_plan=electronics_plan,
                mission_text=mission,
                morphology_plan=morphology_plan,
            )

            kicad_generation = {
                "status": "generated",
                "package_type": "starter_kicad_electronics_package",
                "files": list(kicad_files.values()),
                "file_map": kicad_files,
            }

            for generated_file in kicad_generation.get("files", []):
                record_generated_file(generated_file)

            kicad_validation = run_kicad_knowledge_gate(export_dir)

            kicad_validation_path = (
                export_dir / "generated_kicad" / "kicad_knowledge_gate_report.json"
            )
            write_json(kicad_validation_path, kicad_validation)
            record(kicad_validation_path)

            kicad_generation["knowledge_gate"] = kicad_validation
            kicad_generation["knowledge_gate_report"] = str(kicad_validation_path)

            path = artifact_dir / "kicad_generation_summary.json"
            write_json(path, kicad_generation)
            record(path)

        except Exception as error:
            kicad_generation = {
                "status": "failed",
                "error": str(error),
            }

            kicad_validation = {
                "validator": "kicad_knowledge_gate_validator",
                "status": "skipped",
                "summary": {
                    "blockers": 0,
                    "warnings": 0,
                    "info": 0,
                    "total_issues": 0,
                },
                "issues": [],
                "reason": "KiCad package generation failed, so KiCad validation was skipped.",
            }

            path = artifact_dir / "kicad_generation_summary.json"
            write_json(path, kicad_generation)
            record(path)

    # ---------------------------------------------------------
    # Morphology Gate validation
    # ---------------------------------------------------------

    morphology_validation = run_morphology_gate(export_dir)

    path = artifact_dir / "morphology_gate_report.json"
    write_json(path, morphology_validation)
    record(path)

    # ---------------------------------------------------------
    # Visual Bay manifest
    # ---------------------------------------------------------

    visual_bay_summary: Optional[Dict[str, Any]] = None

    try:
        from backend.app.visual_bay.manifest import build_visual_bay_manifest

        visual_bay_manifest = build_visual_bay_manifest(
            export_dir=export_dir,
            mission_result=mission_result,
        )

        sim  = visual_bay_manifest.get("simulation", {})
        f360 = visual_bay_manifest.get("fusion360", {})
        cq   = visual_bay_manifest.get("cadquery", {})
        r2   = visual_bay_manifest.get("ros2_preview", {})

        has_visual_artifacts = bool(
            f360.get("detected") or
            cq.get("detected") or
            r2.get("detected") or
            sim.get("status") != "not_available"
        )

        if has_visual_artifacts:
            try:
                from backend.app.visual_bay.gltf_preview import write_visual_bay_gltf_preview
                _gltf_result = write_visual_bay_gltf_preview(
                    export_dir,
                    manifest=visual_bay_manifest,
                    mission_result=mission_result,
                )
                if _gltf_result.get("written"):
                    record(_gltf_result["abs_path"])
                    visual_bay_manifest = build_visual_bay_manifest(
                        export_dir=export_dir,
                        mission_result=mission_result,
                    )
                    sim  = visual_bay_manifest.get("simulation", {})
                    f360 = visual_bay_manifest.get("fusion360", {})
                    cq   = visual_bay_manifest.get("cadquery", {})
                    r2   = visual_bay_manifest.get("ros2_preview", {})
            except Exception:
                pass

        manifest_path = export_dir / "visual_bay_manifest.json"
        write_json(manifest_path, visual_bay_manifest)
        record(manifest_path)

        raw_preview_assets = visual_bay_manifest.get("preview_assets", [])
        preview_assets_delivery = _sanitize_preview_assets(
            raw_preview_assets, export_dir, mission_id=folder_name
        )

        visual_bay_summary = {
            "status":                  visual_bay_manifest["status"],
            "report_path":             str(manifest_path),
            "has_cad":                 f360.get("detected", False) or cq.get("detected", False),
            "has_ros2":                r2.get("detected", False),
            "has_simulation_assets":   sim.get("status") != "not_available",
            "browser_preview_ready":   (
                f360.get("browser_preview_ready", False) or
                cq.get("browser_preview_ready", False)
            ),
            "safe_to_launch":          False,
            "browser_preview_ready_count":     visual_bay_manifest.get("browser_preview_ready_count", 0),
            "browser_preview_candidate_count": visual_bay_manifest.get("browser_preview_candidate_count", 0),
            "engineering_only_count":          visual_bay_manifest.get("engineering_only_count", 0),
            "execution_blocked_count":         visual_bay_manifest.get("execution_blocked_count", 0),
            "preview_assets":          preview_assets_delivery,
            "preview_asset_count":     len(preview_assets_delivery),
        }
    except Exception as error:
        visual_bay_summary = {"status": "failed", "error": str(error), "safe_to_launch": False}
        try:
            _err_path = export_dir / "visual_bay_manifest.json"
            write_json(_err_path, visual_bay_summary)
            record(_err_path)
        except Exception:
            pass

    # ---------------------------------------------------------
    # Phase 17E — Engineering Brain reports
    # ---------------------------------------------------------

    engineering_brain: Optional[Dict[str, Any]] = None

    try:
        engineering_brain = _write_engineering_brain(
            export_dir=export_dir,
            mission_result=mission_result,
            mission_text=mission,
        )
        record(Path(engineering_brain["knowledge_selection"]["report_path"]))
        record(Path(engineering_brain["input_readiness"]["report_path"]))
        record(Path(engineering_brain["calculations"]["report_path"]))
    except Exception as _eb_error:
        engineering_brain = {"status": "failed", "error": str(_eb_error)[:500]}
        try:
            _eb_path = export_dir / "engineering_calculation_report.json"
            write_json(_eb_path, engineering_brain)
            record(_eb_path)
        except Exception:
            pass

    # ---------------------------------------------------------
    # Phase 18A — Concept Dossier manifest
    # ---------------------------------------------------------

    concept_dossier: Optional[Dict[str, Any]] = None
    concept_dossier_manifest_full: Optional[Dict[str, Any]] = None

    try:
        concept_dossier = _write_concept_dossier(
            export_dir=export_dir,
            mission_result=mission_result,
            mission_text=mission,
        )
        record(Path(concept_dossier["report_path"]))
        concept_dossier_manifest_full = concept_dossier.pop("manifest", None)
    except Exception as _cd_error:
        concept_dossier = {"status": "failed", "error": str(_cd_error)[:500]}
        try:
            _cd_path = export_dir / "concept_dossier_manifest.json"
            write_json(_cd_path, concept_dossier)
            record(_cd_path)
        except Exception:
            pass

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
    kicad_validation_status = (
        kicad_validation.get("status", "not_run")
        if isinstance(kicad_validation, dict)
        else "not_run"
    )
    morphology_validation_status = (
        morphology_validation.get("status", "not_run")
        if isinstance(morphology_validation, dict)
        else "not_run"
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
            "kicad_validation": kicad_validation,
            "morphology_validation": morphology_validation,
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

## Morphology Gate
- Status: {morphology_validation_status}

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

## KiCad Electronics Package
- Status: {kicad_generation_status}
- Package Type: {kicad_package_type}
- Knowledge Gate: {kicad_validation_status}

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
        "kicad_validation": kicad_validation,
        "morphology_validation": morphology_validation,
        "mission_report": mission_report,
        "graph_review": graph_review,
        "cortex": {
            "design_understanding": design_understanding,
            "candidate_evaluation": candidate_evaluation_summary,
            "mission_intent": mission_intent_summary,
            "pluto_safety_gate": pluto_safety_gate_summary,
        },
        "aeroforge": aeroforge_summary,
        "visual_bay": visual_bay_summary,
        "engineering_brain": engineering_brain,
        "concept_dossier":          concept_dossier,
        "concept_dossier_manifest": concept_dossier_manifest_full,
    }
