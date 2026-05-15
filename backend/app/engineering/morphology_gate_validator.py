from __future__ import annotations

import json
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class MorphologyGateIssue:
    rule_id: str
    severity: str
    message: str
    file: Optional[str] = None


MORPHOLOGY_TO_FUSION_PROJECT_TYPE = {
    "segmented_insect_robot": "insect_robot",
    "wheeled_rover": "rover",
    "quadcopter_drone": "drone",
    "fixed_wing_uav": "aircraft",
    "vtol_uav": "aircraft",
    "robot_arm": "robot_arm",
    "sensor_module": "enclosure",
}


PATTERN_REQUIRED_TERMS = {
    "segmented_insect_robot": [
        "head",
        "thorax",
        "abdomen",
        "appendage",
        "sensor pod",
        "electronics bay",
        "battery bay",
        "segmented",
    ],
    "wheeled_rover": [
        "chassis",
        "wheel",
        "motor",
        "sensor mast",
        "battery",
    ],
    "quadcopter_drone": [
        "rotor",
        "motor mount",
        "central frame",
        "flight controller",
        "battery tray",
    ],
    "fixed_wing_uav": [
        "fuselage",
        "wing",
        "empennage",
        "aileron",
        "elevator",
        "rudder",
    ],
    "robot_arm": [
        "base",
        "shoulder",
        "elbow",
        "wrist",
        "end effector",
        "joint",
    ],
}


def resolve_export_dir(root_path: str | Path) -> Path:
    root = Path(root_path).resolve()

    if root.name in {"generated_fusion360", "generated_kicad", "artifacts"}:
        return root.parent

    return root


def add_issue(
    issues: List[MorphologyGateIssue],
    rule_id: str,
    severity: str,
    message: str,
    file: Optional[str] = None,
) -> None:
    issues.append(
        MorphologyGateIssue(
            rule_id=rule_id,
            severity=severity,
            message=message,
            file=file,
        )
    )


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return ""


def load_json(path: Path) -> tuple[Optional[Any], Optional[str]]:
    try:
        return json.loads(path.read_text(encoding="utf-8")), None
    except Exception as exc:
        return None, str(exc)


def normalize_text(text: str) -> str:
    text = str(text or "").lower()
    text = text.replace("_", " ")
    text = text.replace("-", " ")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def contains_term(text: str, term: str) -> bool:
    normalized_text = normalize_text(text)
    normalized_term = normalize_text(term)

    if not normalized_term:
        return False

    return normalized_term in normalized_text


def get_morphology_plan(export_dir: Path) -> tuple[Dict[str, Any], List[MorphologyGateIssue]]:
    issues: List[MorphologyGateIssue] = []
    path = export_dir / "artifacts" / "morphology_plan.json"

    if not path.exists():
        add_issue(
            issues,
            "MORPH.FS.001",
            "blocker",
            "Missing artifacts/morphology_plan.json.",
            "artifacts/morphology_plan.json",
        )
        return {}, issues

    data, error = load_json(path)

    if error:
        add_issue(
            issues,
            "MORPH.JSON.001",
            "blocker",
            f"morphology_plan.json is invalid JSON: {error}",
            "artifacts/morphology_plan.json",
        )
        return {}, issues

    if not isinstance(data, dict):
        add_issue(
            issues,
            "MORPH.JSON.002",
            "blocker",
            "morphology_plan.json must contain a JSON object.",
            "artifacts/morphology_plan.json",
        )
        return {}, issues

    return data, issues


def validate_morphology_plan(plan: Dict[str, Any]) -> List[MorphologyGateIssue]:
    issues: List[MorphologyGateIssue] = []

    morphology_id = str(plan.get("morphology_id", "")).strip()
    project_family = str(plan.get("project_family", "")).strip()
    confidence = str(plan.get("confidence", "")).strip()

    body_plan = plan.get("body_plan", {})
    if not isinstance(body_plan, dict):
        body_plan = {}

    segments = body_plan.get("segments", [])
    required_features = body_plan.get("required_features", [])
    avoid_features = body_plan.get("avoid_features", [])

    if not morphology_id:
        add_issue(
            issues,
            "MORPH.PLAN.001",
            "blocker",
            "Morphology plan is missing morphology_id.",
            "artifacts/morphology_plan.json",
        )

    if not project_family:
        add_issue(
            issues,
            "MORPH.PLAN.002",
            "warning",
            "Morphology plan is missing project_family.",
            "artifacts/morphology_plan.json",
        )

    if not isinstance(segments, list) or not segments:
        add_issue(
            issues,
            "MORPH.PLAN.003",
            "blocker",
            "Morphology plan must define body_plan.segments.",
            "artifacts/morphology_plan.json",
        )

    if not isinstance(required_features, list) or not required_features:
        add_issue(
            issues,
            "MORPH.PLAN.004",
            "warning",
            "Morphology plan should define required_features.",
            "artifacts/morphology_plan.json",
        )

    if not isinstance(avoid_features, list) or not avoid_features:
        add_issue(
            issues,
            "MORPH.PLAN.005",
            "warning",
            "Morphology plan should define avoid_features to prevent morphology leakage.",
            "artifacts/morphology_plan.json",
        )

    if confidence in {"low", "ambiguous"}:
        add_issue(
            issues,
            "MORPH.PLAN.006",
            "warning",
            f"Morphology confidence is {confidence}. Downstream CAD/ROS2/KiCad outputs should be reviewed carefully.",
            "artifacts/morphology_plan.json",
        )

    return issues


def parse_python_constant(text: str, constant_name: str) -> str:
    pattern = rf'^{constant_name}\s*=\s*["\']([^"\']*)["\']'
    match = re.search(pattern, text, flags=re.MULTILINE)
    return match.group(1).strip() if match else ""


def collect_fusion_text(export_dir: Path) -> tuple[str, Dict[str, Path]]:
    fusion_dir = export_dir / "generated_fusion360"

    files = {
        "script": fusion_dir / "fusion360_model_generator.py",
        "readme": fusion_dir / "CAD_README.md",
        "params": fusion_dir / "fusion360_parameters.json",
    }

    combined = "\n".join(read_text(path) for path in files.values())
    return combined, files


def validate_fusion_morphology(
    export_dir: Path,
    plan: Dict[str, Any],
) -> List[MorphologyGateIssue]:
    issues: List[MorphologyGateIssue] = []

    fusion_dir = export_dir / "generated_fusion360"
    if not fusion_dir.exists():
        add_issue(
            issues,
            "MORPH.FUSION.000",
            "info",
            "No generated_fusion360 folder found. Skipping Fusion morphology checks.",
            "generated_fusion360",
        )
        return issues

    script_path = fusion_dir / "fusion360_model_generator.py"

    if not script_path.exists():
        add_issue(
            issues,
            "MORPH.FUSION.001",
            "warning",
            "Fusion export folder exists, but fusion360_model_generator.py is missing.",
            "generated_fusion360/fusion360_model_generator.py",
        )
        return issues

    script_text = read_text(script_path)
    combined_text, files = collect_fusion_text(export_dir)

    morphology_id = str(plan.get("morphology_id", "")).strip()
    expected_model_name = f"omni_{morphology_id}" if morphology_id else ""
    expected_project_type = MORPHOLOGY_TO_FUSION_PROJECT_TYPE.get(morphology_id)

    model_name = parse_python_constant(script_text, "MODEL_NAME")
    project_type = parse_python_constant(script_text, "PROJECT_TYPE")
    script_morphology_id = parse_python_constant(script_text, "MORPHOLOGY_ID")

    if not script_morphology_id:
        add_issue(
            issues,
            "MORPH.FUSION.002",
            "blocker",
            "Fusion script is missing MORPHOLOGY_ID constant.",
            "generated_fusion360/fusion360_model_generator.py",
        )
    elif script_morphology_id != morphology_id:
        add_issue(
            issues,
            "MORPH.FUSION.003",
            "blocker",
            f"Fusion MORPHOLOGY_ID mismatch. Expected {morphology_id}, got {script_morphology_id}.",
            "generated_fusion360/fusion360_model_generator.py",
        )

    if expected_model_name and model_name != expected_model_name:
        add_issue(
            issues,
            "MORPH.FUSION.004",
            "warning",
            f"Fusion MODEL_NAME should be {expected_model_name}, got {model_name or 'missing'}.",
            "generated_fusion360/fusion360_model_generator.py",
        )

    if expected_project_type and project_type != expected_project_type:
        add_issue(
            issues,
            "MORPH.FUSION.005",
            "blocker",
            f"Fusion PROJECT_TYPE mismatch. Expected {expected_project_type}, got {project_type or 'missing'}.",
            "generated_fusion360/fusion360_model_generator.py",
        )

    if morphology_id != "quadcopter_drone":
        if "drone" in normalize_text(model_name):
            add_issue(
                issues,
                "MORPH.FUSION.006",
                "blocker",
                f"Fusion MODEL_NAME contains drone even though morphology_id is {morphology_id}.",
                "generated_fusion360/fusion360_model_generator.py",
            )

        if project_type == "drone":
            add_issue(
                issues,
                "MORPH.FUSION.007",
                "blocker",
                f"Fusion PROJECT_TYPE is drone even though morphology_id is {morphology_id}.",
                "generated_fusion360/fusion360_model_generator.py",
            )

    body_plan = plan.get("body_plan", {})
    if not isinstance(body_plan, dict):
        body_plan = {}

    segments = body_plan.get("segments", [])
    mounting_points = body_plan.get("mounting_points", [])

    for segment in segments:
        if not contains_term(combined_text, segment):
            add_issue(
                issues,
                f"MORPH.FUSION.SEGMENT.{str(segment).upper()}",
                "warning",
                f"Fusion artifacts do not mention required body segment: {segment}",
                "generated_fusion360",
            )

    for mount in mounting_points:
        if not contains_term(combined_text, mount):
            add_issue(
                issues,
                f"MORPH.FUSION.MOUNT.{str(mount).upper()}",
                "warning",
                f"Fusion artifacts do not mention morphology mounting point: {mount}",
                "generated_fusion360",
            )

    for term in PATTERN_REQUIRED_TERMS.get(morphology_id, []):
        if not contains_term(combined_text, term):
            add_issue(
                issues,
                f"MORPH.FUSION.TERM.{term.upper().replace(' ', '_')}",
                "warning",
                f"Fusion artifacts do not mention expected morphology term: {term}",
                "generated_fusion360",
            )

    return issues


def validate_kicad_morphology(
    export_dir: Path,
    plan: Dict[str, Any],
) -> List[MorphologyGateIssue]:
    """
    Light KiCad morphology check.

    This intentionally does not block yet because the KiCad generator is still a
    starter package generator. It verifies whether electronics intent is at
    least represented somewhere in the generated KiCad support artifacts.
    """
    issues: List[MorphologyGateIssue] = []

    kicad_dir = export_dir / "generated_kicad"
    if not kicad_dir.exists():
        add_issue(
            issues,
            "MORPH.KICAD.000",
            "info",
            "No generated_kicad folder found. Skipping KiCad morphology checks.",
            "generated_kicad",
        )
        return issues

    support_files = [
        kicad_dir / "electronics_architecture.json",
        kicad_dir / "power_budget.json",
        kicad_dir / "connector_map.json",
        kicad_dir / "kicad_knowledge_context.md",
        kicad_dir / "README.md",
    ]

    combined_text = "\n".join(read_text(path) for path in support_files)

    electronics_intent = plan.get("electronics_intent", {})
    if not isinstance(electronics_intent, dict):
        electronics_intent = {}

    expected_locations = [
        electronics_intent.get("primary_pcb_location", ""),
        electronics_intent.get("battery_location", ""),
    ]

    expected_connectors = []
    expected_connectors.extend(electronics_intent.get("sensor_connectors", []) or [])
    expected_connectors.extend(electronics_intent.get("actuator_connectors", []) or [])

    for location in expected_locations:
        if location and not contains_term(combined_text, location):
            add_issue(
                issues,
                f"MORPH.KICAD.LOCATION.{str(location).upper()}",
                "info",
                f"KiCad support artifacts do not yet mention morphology electronics location: {location}",
                "generated_kicad",
            )

    for connector in expected_connectors:
        if connector and not contains_term(combined_text, connector):
            add_issue(
                issues,
                f"MORPH.KICAD.CONNECTOR.{str(connector).upper()}",
                "info",
                f"KiCad support artifacts do not yet mention morphology connector intent: {connector}",
                "generated_kicad",
            )

    return issues


def validate_ros2_morphology(
    export_dir: Path,
    plan: Dict[str, Any],
) -> List[MorphologyGateIssue]:
    """
    Light ROS2 morphology check.

    This is currently non-blocking because ROS2 generation has not been fully
    wired to morphology_plan yet.
    """
    issues: List[MorphologyGateIssue] = []

    ros2_dir = export_dir / "generated_ros2"
    if not ros2_dir.exists():
        add_issue(
            issues,
            "MORPH.ROS2.000",
            "info",
            "No generated_ros2 folder found. Skipping ROS2 morphology checks.",
            "generated_ros2",
        )
        return issues

    combined_text = ""
    for path in ros2_dir.rglob("*"):
        if path.is_file() and path.suffix.lower() in {".py", ".xml", ".urdf", ".xacro", ".yaml", ".yml", ".md"}:
            combined_text += "\n" + read_text(path)

    ros2_intent = plan.get("ros2_intent", {})
    if not isinstance(ros2_intent, dict):
        ros2_intent = {}

    expected_frames = ros2_intent.get("recommended_frames", []) or []
    expected_nodes = ros2_intent.get("recommended_nodes", []) or []
    expected_topics = ros2_intent.get("recommended_topics", []) or []

    for frame in expected_frames:
        if frame and not contains_term(combined_text, frame):
            add_issue(
                issues,
                f"MORPH.ROS2.FRAME.{str(frame).upper()}",
                "info",
                f"ROS2 artifacts do not yet mention morphology frame: {frame}",
                "generated_ros2",
            )

    for node in expected_nodes:
        if node and not contains_term(combined_text, node):
            add_issue(
                issues,
                f"MORPH.ROS2.NODE.{str(node).upper()}",
                "info",
                f"ROS2 artifacts do not yet mention morphology node: {node}",
                "generated_ros2",
            )

    for topic in expected_topics:
        if topic and not contains_term(combined_text, topic):
            add_issue(
                issues,
                f"MORPH.ROS2.TOPIC.{str(topic).upper().replace('/', '_')}",
                "info",
                f"ROS2 artifacts do not yet mention morphology topic: {topic}",
                "generated_ros2",
            )

    return issues


def validate_morphology_export(root_path: str | Path) -> Dict[str, Any]:
    export_dir = resolve_export_dir(root_path)

    issues: List[MorphologyGateIssue] = []

    if not export_dir.exists():
        add_issue(
            issues,
            "MORPH.PATH.001",
            "blocker",
            f"Export directory does not exist: {export_dir}",
        )
        return build_report(export_dir, {}, issues)

    plan, plan_issues = get_morphology_plan(export_dir)
    issues.extend(plan_issues)

    if not plan:
        return build_report(export_dir, plan, issues)

    issues.extend(validate_morphology_plan(plan))
    issues.extend(validate_fusion_morphology(export_dir, plan))
    issues.extend(validate_kicad_morphology(export_dir, plan))
    issues.extend(validate_ros2_morphology(export_dir, plan))

    return build_report(export_dir, plan, issues)


def build_report(
    export_dir: Path,
    plan: Dict[str, Any],
    issues: List[MorphologyGateIssue],
) -> Dict[str, Any]:
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
        "validator": "morphology_gate_validator",
        "export_dir": str(export_dir),
        "morphology_id": plan.get("morphology_id") if isinstance(plan, dict) else None,
        "project_family": plan.get("project_family") if isinstance(plan, dict) else None,
        "status": status,
        "summary": {
            "blockers": blocker_count,
            "warnings": warning_count,
            "info": info_count,
            "total_issues": len(issues),
        },
        "issues": [asdict(issue) for issue in issues],
    }


def main() -> None:
    if len(sys.argv) < 2:
        print(
            "Usage: python -m backend.app.engineering.morphology_gate_validator "
            "<mission_export_dir>"
        )
        raise SystemExit(1)

    result = validate_morphology_export(sys.argv[1])
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()