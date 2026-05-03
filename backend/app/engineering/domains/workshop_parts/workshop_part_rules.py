from backend.app.engineering.mission_schema import EngineeringMission
from backend.app.engineering.domains.workshop_parts.workshop_part_schema import WorkshopPartSpec


def infer_workshop_part_spec(mission: EngineeringMission) -> WorkshopPartSpec:
    """
    Convert a general EngineeringMission into a workshop-part-specific spec.

    This is intentionally simple for Level 1.
    Later, this can become much more advanced with CAD dimensions, tolerances,
    load cases, fastener sizes, and printer settings.
    """

    text = mission.mission_text.lower()

    part_type = "unknown"
    target_device = None
    mounting_style = None
    angle_degrees = None
    design_features = []
    missing_requirements = []
    safety_notes = []

    # Part type detection
    if "camera mount" in text:
        part_type = "camera_mount"
        design_features.append("camera attachment interface")
    elif "mount" in text:
        part_type = "mount"
    elif "bracket" in text:
        part_type = "bracket"
    elif "enclosure" in text or "case" in text:
        part_type = "electronics_enclosure"
        design_features.append("component clearance")
        design_features.append("service access")
    elif "holder" in text:
        part_type = "holder"
    elif "clip" in text:
        part_type = "clip"

    # Target device detection
    if "raspberry pi" in text or "pi camera" in text:
        target_device = "raspberry_pi_camera"
        design_features.append("camera cable clearance")

    if "esp32" in text:
        target_device = "esp32"
        design_features.append("usb port clearance")
        design_features.append("ventilation openings")

    if "breadboard" in text:
        target_device = "breadboard"

    # Mounting style
    if "screw" in text or "screw-mounted" in text:
        mounting_style = "screw_mounted"
        design_features.append("screw mounting holes")
    elif "wall" in text:
        mounting_style = "wall_mounted"
    elif "snap" in text:
        mounting_style = "snap_fit"

    # Angle detection
    if "25" in text and "degree" in text:
        angle_degrees = 25.0
        design_features.append("fixed 25 degree viewing angle")
    elif "angle" in text or "angled" in text:
        missing_requirements.append("Exact angle is needed for the mount.")

    # Material
    material = mission.material or "PLA"

    # Basic missing requirements
    if part_type == "unknown":
        missing_requirements.append("Part type is unclear.")

    if target_device is None:
        missing_requirements.append("Target device or object being held is not specified.")

    if mounting_style is None:
        missing_requirements.append("Mounting style is not specified.")

    if mission.requires_fabrication_plan:
        if material is None:
            missing_requirements.append("Material is not specified.")
        safety_notes.append("Do not start printing without human approval.")
        safety_notes.append("Verify printer bed is clear before fabrication.")

    return WorkshopPartSpec(
        part_type=part_type,
        material=material,
        fabrication_method=mission.fabrication_method or "fdm_3d_printing",
        mounting_style=mounting_style,
        target_device=target_device,
        angle_degrees=angle_degrees,
        design_features=sorted(set(design_features)),
        missing_requirements=missing_requirements,
        safety_notes=safety_notes,
    )