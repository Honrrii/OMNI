from typing import Dict, Optional

from backend.app.engineering.mission_schema import build_engineering_mission
from backend.app.engineering.validation_engine import validate_mission
from backend.app.engineering.domains.workshop_parts.workshop_part_schema import WorkshopPartSpec
from backend.app.cad.workshop_part_cad_planner import generate_workshop_part_cad_plan


def run_omni_forge_validation(mission_text: str) -> Dict:
    """
    OMNI Forge Level 2 service.

    Converts a natural-language engineering prompt into:
    - structured mission schema
    - derived domain spec
    - validation report
    - CAD parameter plan when CAD is requested and supported

    This does not generate actual CAD geometry yet.
    This does not control printers or physical devices.
    """

    mission = build_engineering_mission(mission_text)
    report = validate_mission(mission)

    cad_plan = _maybe_generate_cad_plan(report)

    if cad_plan:
        report["cad_plan"] = cad_plan

    return {
        "status": "success",
        "forge_level": "level_2_cad_parameter_planning" if cad_plan else "level_1_validation",
        "message": "OMNI Forge validation completed.",
        "report": report,
    }


def _maybe_generate_cad_plan(report: Dict) -> Optional[Dict]:
    """
    Generate a CAD plan only when:
    - CAD is requested
    - the derived spec exists
    - the target domain is currently supported
    """

    mission = report.get("mission", {})
    derived_spec = report.get("derived_spec")

    if not mission.get("requires_cad"):
        return None

    if mission.get("target_domain") != "workshop_parts":
        return None

    if not derived_spec:
        return None

    spec = WorkshopPartSpec(**derived_spec)
    cad_plan = generate_workshop_part_cad_plan(spec)

    return cad_plan.dict()