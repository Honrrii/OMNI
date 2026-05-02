from typing import Any, Dict, List


CAD_REFERENCE_SOURCES = {
    "drone_frame": {
        "source_folder": "knowledge/cad_sources/drone_frames",
        "reference_files": [
            "PA-001-DF7.STEP",
            "PA-001-DF7.STL",
            "Apex HD 7 inch.pdf",
        ],
        "lessons": [
            "Drone frames should use symmetric arm layouts.",
            "Motor mounts should be placed at arm ends with circular bolt patterns.",
            "Central plates should reserve space for battery, flight controller, and wiring.",
            "Weight-reduction cutouts should avoid weakening motor mount and arm root regions.",
            "Propeller clearance must be preserved around all motor positions.",
        ],
    },
    "rover_chassis": {
        "source_folder": "knowledge/cad_sources/rover_chassis",
        "reference_files": [
            "New_Chassis v9.step",
            "SKIBBS_.step",
            "2a.SLDASM",
        ],
        "lessons": [
            "Rover chassis should define wheelbase and track width early.",
            "Battery mass should be placed low and near the center of the chassis.",
            "Compute boards should mount on standoffs instead of directly on the plate.",
            "Camera masts need gussets or support brackets when tall.",
            "Front sensors need an unobstructed field of view.",
            "Leave service access for wiring, motor drivers, and battery removal.",
        ],
    },
    "drivetrain": {
        "source_folder": "knowledge/cad_sources/drivetrains",
        "reference_files": [
            "Drivetrain.step",
        ],
        "lessons": [
            "Drivetrains need clear motor mounting zones.",
            "Wheel and axle alignment should be symmetric and constrained by the chassis.",
            "Drive components need service clearance.",
            "Structural rails should support loads between wheel modules.",
            "Motor controllers should be mounted with airflow and cable strain relief.",
        ],
    },
    "nasa_mesh_reference": {
        "source_folder": "knowledge/cad_sources/nasa_meshes",
        "reference_files": [
            "Fuselage top.stl",
            "Left wing.stl",
            "Right wing.stl",
            "Tail section.stl",
        ],
        "lessons": [
            "Large aerospace shapes can be split into modular body sections.",
            "Mesh references are useful for visual inspiration but not enough for manufacturing rules.",
            "Separate major structures into logical subassemblies.",
        ],
    },
}


CAD_PATTERNS = {
    "rover": {
        "recommended_features": [
            "main chassis plate",
            "rounded or chamfered chassis corners",
            "wheel clearance cutouts",
            "battery tray near center of mass",
            "Raspberry Pi or compute board standoffs",
            "motor driver mounting zone",
            "camera mast",
            "camera mast gussets",
            "front sensor bracket",
            "rear service block",
            "mounting hole pattern",
            "cable routing corridor",
            "front bumper or impact zone",
        ],
        "design_rules": [
            "Keep the battery low and near the center of the wheelbase.",
            "Keep the camera mast near the front-center unless the mission requires rear vision.",
            "Add support gussets to tall vertical masts.",
            "Reserve enough wheel clearance around all wheel placeholders.",
            "Use standoffs for electronics rather than placing boards directly on the chassis.",
            "Leave cable routing space between compute, battery, motor driver, and sensors.",
            "Avoid blocking front sensor field of view.",
            "Separate high-current motor wiring from sensor wiring where possible.",
        ],
        "default_dimensions_mm": {
            "base_length": 300,
            "base_width": 200,
            "plate_thickness": 4,
            "wheel_radius": 38,
            "wheel_width": 18,
            "camera_mast_height": 120,
            "battery_length": 95,
            "battery_width": 45,
            "raspberry_pi_length": 85,
            "raspberry_pi_width": 56,
        },
    },
    "drone": {
        "recommended_features": [
            "central body plate",
            "symmetric arms",
            "motor mount pads",
            "flight controller mounting square",
            "battery tray",
            "camera mount",
            "propeller clearance zones",
            "weight-reduction cutouts",
            "arm root reinforcement",
        ],
        "design_rules": [
            "Use symmetry around the center body.",
            "Keep motor positions equidistant from the center for balanced thrust.",
            "Reserve a central flat region for flight controller mounting.",
            "Keep battery placement centered on the thrust axis.",
            "Avoid weight-reduction cutouts near motor mounts and arm roots.",
            "Preserve propeller clearance around each motor.",
        ],
        "default_dimensions_mm": {
            "center_body_radius": 70,
            "center_body_height": 24,
            "arm_length": 180,
            "arm_width": 18,
            "arm_height": 10,
            "motor_mount_radius": 22,
            "battery_length": 85,
            "battery_width": 35,
        },
    },
    "enclosure": {
        "recommended_features": [
            "main enclosure body",
            "removable lid",
            "mounting holes",
            "cable ports",
            "ventilation slots",
            "internal standoffs",
            "rounded corners",
        ],
        "design_rules": [
            "Leave clearance around electronics and connectors.",
            "Provide access to ports and switches.",
            "Include ventilation for heat-generating components.",
            "Use standoffs for PCBs.",
            "Avoid sharp internal corners when 3D printing.",
        ],
        "default_dimensions_mm": {
            "box_length": 140,
            "box_width": 90,
            "box_height": 45,
            "wall_thickness": 3,
            "lid_thickness": 3,
        },
    },
}


def get_cad_pattern(project_type: str) -> Dict[str, Any]:
    return CAD_PATTERNS.get(project_type, CAD_PATTERNS["rover"])


def get_cad_lessons(project_type: str) -> List[str]:
    if project_type == "drone":
        keys = ["drone_frame"]
    elif project_type == "rover":
        keys = ["rover_chassis", "drivetrain"]
    elif project_type == "enclosure":
        keys = ["rover_chassis"]
    else:
        keys = ["rover_chassis", "drivetrain", "drone_frame"]

    lessons = []

    for key in keys:
        lessons.extend(CAD_REFERENCE_SOURCES.get(key, {}).get("lessons", []))

    return lessons


def summarize_cad_context(project_type: str) -> Dict[str, Any]:
    pattern = get_cad_pattern(project_type)

    return {
        "project_type": project_type,
        "recommended_features": pattern.get("recommended_features", []),
        "design_rules": pattern.get("design_rules", []),
        "reference_lessons": get_cad_lessons(project_type),
        "default_dimensions_mm": pattern.get("default_dimensions_mm", {}),
    }


if __name__ == "__main__":
    import argparse
    import json

    parser = argparse.ArgumentParser(description="Inspect OMNI CAD pattern knowledge.")
    parser.add_argument(
        "--project-type",
        default="rover",
        choices=["rover", "drone", "enclosure", "generic_robotics"],
    )

    args = parser.parse_args()

    print(json.dumps(summarize_cad_context(args.project_type), indent=2))