from typing import Dict, Optional

from backend.app.cad.cad_script_runner import execute_generated_cad_script
from backend.app.cad.cadquery_script_generator import generate_cadquery_script_from_plan
from backend.app.cad.generated_script_writer import write_generated_cad_script
from backend.app.cad.workshop_part_cad_planner import generate_workshop_part_cad_plan
from backend.app.engineering.domains.workshop_parts.workshop_part_schema import WorkshopPartSpec
from backend.app.engineering.mission_schema import build_engineering_mission
from backend.app.engineering.validation_engine import validate_mission


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


def run_omni_forge_cad_script_generation(mission_text: str) -> Dict:
    """
    OMNI Forge Level 3 service.

    Converts a natural-language engineering prompt into:
    - validation report
    - CAD parameter plan
    - generated CadQuery script saved to disk

    This does not execute the CAD script.
    This does not control printers or physical devices.
    """

    validation_result = run_omni_forge_validation(mission_text)
    report = validation_result.get("report", {})
    cad_plan = report.get("cad_plan")

    if not cad_plan:
        return {
            "status": "blocked",
            "forge_level": "level_3_cadquery_script_generation",
            "message": "No CAD plan was available. Script generation was skipped.",
            "report": report,
            "cad_script": None,
        }

    script_text = generate_cadquery_script_from_plan(cad_plan)

    write_result = write_generated_cad_script(
        script_text=script_text,
        mission_text=mission_text,
        cad_plan=cad_plan,
    )

    return {
        "status": "success",
        "forge_level": "level_3_cadquery_script_generation",
        "message": "OMNI Forge generated a CadQuery script for human review.",
        "report": report,
        "cad_script": {
            **write_result,
            "script_text": script_text,
        },
    }


def run_omni_forge_cad_script_execution(script_path: str) -> Dict:
    """
    OMNI Forge Level 4 service.

    Executes a previously generated CadQuery script and exports CAD files.

    Safety boundaries:
    - Only scripts inside outputs/omni_forge/cad_scripts are allowed.
    - The script is scanned before execution.
    - A subprocess timeout is enforced.
    - This does not control printers.
    - This does not start fabrication.
    """

    execution_result = execute_generated_cad_script(script_path)

    return {
        "status": execution_result.get("status"),
        "forge_level": "level_4_cad_file_export",
        "message": execution_result.get("message"),
        "execution_result": execution_result,
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