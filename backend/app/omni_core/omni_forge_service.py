from typing import Dict

from backend.app.engineering.mission_schema import build_engineering_mission
from backend.app.engineering.validation_engine import validate_mission


def run_omni_forge_validation(mission_text: str) -> Dict:
    """
    OMNI Forge Level 1 service.

    Converts a natural-language engineering prompt into:
    - structured mission schema
    - derived domain spec
    - validation report

    This does not generate CAD yet.
    This does not control printers or physical devices.
    """

    mission = build_engineering_mission(mission_text)
    report = validate_mission(mission)

    return {
        "status": "success",
        "forge_level": "level_1_validation",
        "message": "OMNI Forge validation completed.",
        "report": report,
    }