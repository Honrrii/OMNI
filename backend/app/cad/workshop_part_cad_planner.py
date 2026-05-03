from backend.app.cad.cad_parameter_schema import CADParameterPlan
from backend.app.engineering.domains.workshop_parts.workshop_part_schema import WorkshopPartSpec


def generate_workshop_part_cad_plan(spec: WorkshopPartSpec) -> CADParameterPlan:
    """
    Generate a CAD parameter plan for a workshop part.

    Level 2 goal:
    Turn a validated workshop part spec into concrete CAD parameters.

    This does not create a model yet.
    The next level will consume these parameters to generate Fusion 360,
    CadQuery, or FreeCAD scripts.
    """

    if spec.part_type == "camera_mount":
        return _generate_camera_mount_plan(spec)

    if spec.part_type == "electronics_enclosure":
        return _generate_electronics_enclosure_plan(spec)

    return _generate_generic_workshop_part_plan(spec)


def _generate_camera_mount_plan(spec: WorkshopPartSpec) -> CADParameterPlan:
    angle = spec.angle_degrees if spec.angle_degrees is not None else 25.0

    parameters = {
        "base_plate_width_mm": 60,
        "base_plate_depth_mm": 42,
        "base_plate_thickness_mm": 4,
        "mount_wall_height_mm": 38,
        "mount_wall_thickness_mm": 5,
        "mount_angle_degrees": angle,
        "camera_clearance_mm": 8,
        "screw_hole_diameter_mm": 3.2,
        "screw_hole_spacing_mm": 45,
        "edge_margin_mm": 7.5,
        "fillet_radius_mm": 3,
        "cable_channel_width_mm": 10,
        "cable_channel_height_mm": 5,
    }

    design_features = [
        "rectangular base plate",
        "angled camera support wall",
        "screw mounting holes",
        "camera cable clearance channel",
        "rounded/filleted edges",
        "flat bottom for easy printing",
    ]

    manufacturing_notes = [
        "Recommended material: PLA for first prototype.",
        "Recommended print orientation: base plate flat on print bed.",
        "Use 3 perimeters/walls for better screw strength.",
        "Use 20-35% infill for a light but sturdy prototype.",
        "Add supports only if the final angled geometry creates steep overhangs.",
    ]

    assumptions = [
        "Camera module dimensions are not yet explicitly provided.",
        "Default screw holes assume M3-style clearance.",
        "Base dimensions are prototype defaults and should be adjusted after measuring the real mounting surface.",
        "The 25 degree camera angle is treated as a fixed viewing angle.",
    ]

    warnings = [
        "Verify Raspberry Pi camera board dimensions before generating final CAD.",
        "Check screw length so it does not damage the mounting surface.",
        "Confirm cable bend radius before printing.",
        "Do not start physical printing without human approval.",
    ]

    return CADParameterPlan(
        part_type=spec.part_type,
        parameters=parameters,
        design_features=design_features,
        manufacturing_notes=manufacturing_notes,
        assumptions=assumptions,
        warnings=warnings,
        ready_for_script_generation=True,
    )


def _generate_electronics_enclosure_plan(spec: WorkshopPartSpec) -> CADParameterPlan:
    parameters = {
        "outer_length_mm": 80,
        "outer_width_mm": 50,
        "outer_height_mm": 28,
        "wall_thickness_mm": 2.4,
        "lid_thickness_mm": 2.0,
        "corner_radius_mm": 4,
        "vent_slot_width_mm": 3,
        "vent_slot_count": 8,
        "usb_cutout_width_mm": 12,
        "usb_cutout_height_mm": 7,
        "mounting_hole_diameter_mm": 3.2,
    }

    design_features = [
        "rounded rectangular enclosure body",
        "removable lid",
        "ventilation slots",
        "USB/service port cutout",
        "internal component clearance",
        "optional wall-mount holes",
    ]

    manufacturing_notes = [
        "Recommended material: PLA for early fit-check prototype.",
        "Print enclosure body open-side up if possible.",
        "Use PETG later if heat resistance is needed.",
        "Avoid thin walls below 2 mm for durability.",
    ]

    assumptions = [
        "Electronics board dimensions are not explicitly provided.",
        "Default dimensions are suitable only for rough prototype planning.",
        "Exact port positions need to be measured before final CAD.",
    ]

    warnings = [
        "Verify heat buildup for enclosed electronics.",
        "Confirm all port and cable clearances before printing.",
        "Do not start physical printing without human approval.",
    ]

    return CADParameterPlan(
        part_type=spec.part_type,
        parameters=parameters,
        design_features=design_features,
        manufacturing_notes=manufacturing_notes,
        assumptions=assumptions,
        warnings=warnings,
        ready_for_script_generation=True,
    )


def _generate_generic_workshop_part_plan(spec: WorkshopPartSpec) -> CADParameterPlan:
    parameters = {
        "default_length_mm": 60,
        "default_width_mm": 40,
        "default_thickness_mm": 4,
        "fillet_radius_mm": 3,
        "mounting_hole_diameter_mm": 3.2,
    }

    design_features = [
        "simple printable workshop part body",
        "rounded edges",
        "prototype-safe dimensions",
    ]

    manufacturing_notes = [
        "Recommended material: PLA for first prototype.",
        "Print flat side down when possible.",
        "Revise dimensions after measuring real-world mounting constraints.",
    ]

    assumptions = [
        "Specific part geometry is not fully defined.",
        "Default dimensions are placeholders.",
    ]

    warnings = [
        "More requirements are needed before generating final CAD.",
        "Do not start physical printing without human approval.",
    ]

    return CADParameterPlan(
        part_type=spec.part_type,
        parameters=parameters,
        design_features=design_features,
        manufacturing_notes=manufacturing_notes,
        assumptions=assumptions,
        warnings=warnings,
        ready_for_script_generation=False,
    )