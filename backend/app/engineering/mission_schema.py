from typing import List, Optional
from pydantic import BaseModel, Field


class EngineeringMission(BaseModel):
    """
    Structured mission object for OMNI Forge.

    This is the first step in turning natural language into an engineering
    workflow that can be validated, simulated, and eventually fabricated.
    """

    mission_text: str = Field(..., description="Original user prompt")
    project_type: str = Field(default="unknown", description="Detected project type")
    target_domain: str = Field(default="general", description="Engineering domain")
    requested_outputs: List[str] = Field(default_factory=list)

    material: Optional[str] = None
    fabrication_method: Optional[str] = None

    requires_cad: bool = False
    requires_simulation: bool = False
    requires_fabrication_plan: bool = False
    requires_safety_review: bool = True
    requires_human_approval: bool = True

    notes: List[str] = Field(default_factory=list)


def build_engineering_mission(mission_text: str) -> EngineeringMission:
    """
    Lightweight rule-based mission parser.

    Later, OMNI can use an LLM to fill this schema more intelligently.
    For now, this keeps the system deterministic and cheap.
    """

    text = mission_text.lower()

    project_type = "unknown"
    target_domain = "general"
    requested_outputs = []
    notes = []

    requires_cad = False
    requires_simulation = False
    requires_fabrication_plan = False
    requires_safety_review = True
    requires_human_approval = True

    material = None
    fabrication_method = None

    # Detect project type / domain
    if any(word in text for word in ["mount", "bracket", "holder", "case", "enclosure", "organizer", "clip"]):
        project_type = "workshop_part"
        target_domain = "workshop_parts"

    if any(word in text for word in ["drone", "quadcopter", "hexacopter", "uav"]):
        project_type = "drone"
        target_domain = "drones"

    if any(word in text for word in ["robot arm", "manipulator", "gripper"]):
        project_type = "robotic_system"
        target_domain = "robotics"

    # Detect requested outputs
    if any(word in text for word in ["cad", "fusion", "fusion 360", "model", "stl", "step"]):
        requires_cad = True
        requested_outputs.append("cad_plan")

    if any(word in text for word in ["simulate", "simulation", "ros2", "gazebo", "rviz", "urdf"]):
        requires_simulation = True
        requested_outputs.append("simulation_plan")

    if any(word in text for word in ["print", "3d print", "printable", "fabricate", "slicer", "g-code", "gcode"]):
        requires_fabrication_plan = True
        requested_outputs.append("fabrication_plan")

    if any(word in text for word in ["validate", "safety", "review", "test", "testing"]):
        requires_safety_review = True
        requested_outputs.append("validation_report")

    # Detect material
    if "pla" in text:
        material = "PLA"
    elif "petg" in text:
        material = "PETG"
    elif "abs" in text:
        material = "ABS"
    elif "carbon fiber" in text or "carbon-fiber" in text:
        material = "carbon_fiber"

    # Detect fabrication method
    if any(word in text for word in ["3d print", "printable", "printer", "slicer", "g-code", "gcode"]):
        fabrication_method = "fdm_3d_printing"

    # Always require approval for physical actions
    if any(word in text for word in ["start print", "print it", "begin printing", "heat", "move robot"]):
        notes.append("Physical execution requested. Human approval and safety checks are required.")

    if not requested_outputs:
        notes.append("No explicit outputs detected. Defaulting to engineering summary and safety review.")
        requested_outputs.append("engineering_summary")
        requested_outputs.append("validation_report")

    return EngineeringMission(
        mission_text=mission_text,
        project_type=project_type,
        target_domain=target_domain,
        requested_outputs=requested_outputs,
        material=material,
        fabrication_method=fabrication_method,
        requires_cad=requires_cad,
        requires_simulation=requires_simulation,
        requires_fabrication_plan=requires_fabrication_plan,
        requires_safety_review=requires_safety_review,
        requires_human_approval=requires_human_approval,
        notes=notes,
    )