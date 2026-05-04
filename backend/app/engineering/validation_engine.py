from typing import Any, Dict, List, Optional

from backend.app.engineering.mission_schema import EngineeringMission
from backend.app.engineering.domains.workshop_parts.workshop_part_rules import infer_workshop_part_spec
from backend.app.engineering.domains.workshop_parts.workshop_part_validator import validate_workshop_part
from backend.app.engineering.golden_standards.golden_standard_registry import get_golden_standard
from backend.app.engineering.golden_standards.golden_standard_validator import (
    validate_against_golden_standard,
)


def detect_golden_standard_id(mission: EngineeringMission) -> Optional[str]:
    """
    Detect whether a mission appears to target one of OMNI's Golden Standards.

    This is intentionally simple for now.
    Later, this can be replaced by a richer classifier.
    """

    mission_text = mission.mission_text.lower()
    project_type = mission.project_type.lower()
    target_domain = mission.target_domain.lower()
    requested_outputs = " ".join(mission.requested_outputs).lower()

    searchable_text = " ".join(
        [
            mission_text,
            project_type,
            target_domain,
            requested_outputs,
        ]
    )

    # GS1: Quadcopter / aerial robotics benchmark
    gs1_keywords = [
        "gs1",
        "golden standard 1",
        "quadcopter",
        "quad copter",
        "drone",
        "aerial",
        "thrust",
        "flight time",
        "propeller",
        "esc",
    ]

    if any(keyword in searchable_text for keyword in gs1_keywords):
        return "GS1"

    # GS2: Autonomous rover / ground robotics benchmark
    gs2_keywords = [
        "gs2",
        "golden standard 2",
        "rover",
        "autonomous rover",
        "ground robot",
        "differential drive",
        "wheel radius",
        "motor torque",
        "indoor navigation",
    ]

    if any(keyword in searchable_text for keyword in gs2_keywords):
        return "GS2"

    return None


def validate_mission(
    mission: EngineeringMission,
    mission_result: Optional[Dict[str, Any]] = None,
) -> Dict:
    """
    OMNI Forge validation engine.

    Takes a structured EngineeringMission and returns a validation report.

    If mission_result is provided, this engine can also validate generated
    artifacts against OMNI's Golden Standard benchmarks.
    """

    passed_checks: List[str] = []
    warnings: List[str] = []
    blockers: List[str] = []
    domain_report = None
    derived_spec = None
    golden_standard_report = None

    # General mission validation
    if mission.mission_text.strip():
        passed_checks.append("Mission text received.")
    else:
        blockers.append("Mission text is empty.")

    if mission.project_type != "unknown":
        passed_checks.append(f"Project type detected: {mission.project_type}.")
    else:
        warnings.append("Project type could not be confidently detected.")

    if mission.target_domain != "general":
        passed_checks.append(f"Target domain selected: {mission.target_domain}.")
    else:
        warnings.append("Target domain is general. OMNI may need clarification.")

    if mission.requested_outputs:
        passed_checks.append(f"Requested outputs detected: {', '.join(mission.requested_outputs)}.")
    else:
        warnings.append("No requested outputs detected.")

    if mission.requires_cad:
        passed_checks.append("CAD output requested.")

    if mission.requires_simulation:
        passed_checks.append("Simulation output requested.")

    if mission.requires_fabrication_plan:
        passed_checks.append("Fabrication planning requested.")
        warnings.append("Physical fabrication must remain human-approved.")

    if mission.requires_safety_review:
        passed_checks.append("Safety review required.")

    if mission.requires_human_approval:
        passed_checks.append("Human approval gate enabled.")

    # Golden Standard detection
    golden_standard_id = detect_golden_standard_id(mission)

    if golden_standard_id:
        standard = get_golden_standard(golden_standard_id)
        passed_checks.append(
            f"Golden Standard detected: {standard.id} - {standard.name}."
        )

        if mission_result is not None:
            golden_standard_report = validate_against_golden_standard(
                mission_result=mission_result,
                standard_id=golden_standard_id,
            ).to_dict()

            if golden_standard_report["status"] == "passed":
                passed_checks.append(
                    f"Golden Standard validation passed with score {golden_standard_report['score']}."
                )

            elif golden_standard_report["status"] == "partial":
                warnings.append(
                    f"Golden Standard validation partial with score {golden_standard_report['score']}."
                )

            else:
                blockers.append(
                    f"Golden Standard validation failed with score {golden_standard_report['score']}."
                )
        else:
            warnings.append(
                "Golden Standard mission detected, but no mission_result was provided for artifact validation."
            )

    # Domain-specific validation
    if mission.target_domain == "workshop_parts":
        derived_spec = infer_workshop_part_spec(mission)
        domain_report = validate_workshop_part(derived_spec)

        if domain_report["status"] == "blocked":
            blockers.extend(domain_report["blockers"])

        warnings.extend(domain_report["warnings"])

    # Final status
    status = "pass"
    if warnings:
        status = "warning"
    if blockers:
        status = "blocked"

    return {
        "status": status,
        "mission": mission.dict(),
        "passed_checks": passed_checks,
        "warnings": warnings,
        "blockers": blockers,
        "domain_report": domain_report,
        "derived_spec": derived_spec.dict() if derived_spec else None,
        "golden_standard_id": golden_standard_id,
        "golden_standard_report": golden_standard_report,
    }