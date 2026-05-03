from typing import Dict, List

from backend.app.engineering.mission_schema import EngineeringMission
from backend.app.engineering.domains.workshop_parts.workshop_part_rules import infer_workshop_part_spec
from backend.app.engineering.domains.workshop_parts.workshop_part_validator import validate_workshop_part


def validate_mission(mission: EngineeringMission) -> Dict:
    """
    OMNI Forge Level 1 validation engine.

    Takes a structured EngineeringMission and returns a validation report.
    """

    passed_checks: List[str] = []
    warnings: List[str] = []
    blockers: List[str] = []
    domain_report = None
    derived_spec = None

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
    }