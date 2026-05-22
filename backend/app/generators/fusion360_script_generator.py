import json
import pprint

try:
    from backend.app.cad.cad_detail_pass_planner import (
        plan_cad_detail_passes,
        assembly_spec_to_dict,
        summarize_assembly_spec,
    )
except Exception:
    try:
        from cad.cad_detail_pass_planner import (
            plan_cad_detail_passes,
            assembly_spec_to_dict,
            summarize_assembly_spec,
        )
    except Exception:
        try:
            from app.cad.cad_detail_pass_planner import (
                plan_cad_detail_passes,
                assembly_spec_to_dict,
                summarize_assembly_spec,
            )
        except Exception:
            plan_cad_detail_passes = None
            assembly_spec_to_dict = None
            summarize_assembly_spec = None


import re
from pathlib import Path
from typing import Any, Dict, List


# ---------------------------------------------------------
# CAD Knowledge Bridge
# ---------------------------------------------------------
try:
    from backend.app.knowledge.cad_pattern_library import summarize_cad_context
except ModuleNotFoundError:
    try:
        from knowledge.cad_pattern_library import summarize_cad_context
    except ModuleNotFoundError:
        summarize_cad_context = None

try:
    from backend.app.knowledge.aircraft_aerospace_cad_pattern_library import (
        get_aircraft_cad_context,
        mission_matches_aircraft_cad,
    )
except Exception:
    try:
        from knowledge.aircraft_aerospace_cad_pattern_library import (
            get_aircraft_cad_context,
            mission_matches_aircraft_cad,
        )
    except Exception:
        get_aircraft_cad_context = None
        mission_matches_aircraft_cad = None


# ---------------------------------------------------------
# CAD Morphology Compiler
# ---------------------------------------------------------
try:
    from backend.app.cad.morphology_artifact_writer import build_morphology_artifacts
except Exception:
    try:
        from cad.morphology_artifact_writer import build_morphology_artifacts
    except Exception:
        build_morphology_artifacts = None


# ---------------------------------------------------------
# Naming Helpers
# ---------------------------------------------------------
def safe_name(value: Any, fallback: str = "omni_cad_model") -> str:
    text = str(value or fallback).lower().strip()
    text = re.sub(r"[^a-z0-9_]+", "_", text)
    text = re.sub(r"_+", "_", text).strip("_")

    if not text:
        return fallback

    if text[0].isdigit():
        text = f"model_{text}"

    return text


def mission_text(mission_result: Dict[str, Any]) -> str:
    mission = str(mission_result.get("mission", ""))
    artifacts = mission_result.get("artifacts", {}) or {}

    try:
        artifact_text = json.dumps(artifacts, default=str)
    except Exception:
        artifact_text = str(artifacts)

    return f"{mission}\n{artifact_text}".lower()


def infer_project_type(mission_result: Dict[str, Any]) -> str:
    """
    Infer CAD project type from mission text.

    Bio-inspired, insect, and legged robots get their own morphology route.
    This prevents them from being forced into drone or rover templates.
    """
    if not isinstance(mission_result, dict):
        mission_text = str(mission_result or "")
    else:
        fields = [
            "mission",
            "mission_text",
            "user_prompt",
            "prompt",
            "original_mission",
        ]

        mission_text = "\n".join(
            str(mission_result.get(field, "") or "")
            for field in fields
        )

        if not mission_text.strip():
            try:
                mission_text = json.dumps(mission_result, default=str)
            except Exception:
                mission_text = str(mission_result)

    text = mission_text.lower()

    insect_terms = [
        "insect",
        "insect-inspired",
        "hexapod",
        "six leg",
        "six-legged",
        "6 leg",
        "6-legged",
        "legged",
        "walking",
        "crawler",
        "crawling",
        "biomimetic",
        "bio-inspired",
        "bio inspired",
        "arthropod",
        "ant-like",
        "antlike",
        "beetle",
        "cockroach",
        "spider-like",
        "spiderlike",
        "terrain scouting",
    ]

    drone_terms = [
        "drone",
        "quadcopter",
        "hexacopter",
        "octocopter",
        "uav",
        "aerial",
        "flight",
        "flying",
        "rotor",
        "propeller",
        "multirotor",
    ]

    rover_terms = [
        "rover",
        "wheeled",
        "wheel",
        "tracked",
        "tank tread",
        "differential drive",
        "ground vehicle",
        "mobile base",
    ]

    arm_terms = [
        "robot arm",
        "manipulator",
        "end effector",
        "gripper arm",
        "pick and place",
    ]

    enclosure_terms = [
        "enclosure",
        "case",
        "housing",
        "electronics box",
        "shell",
    ]

    if any(term in text for term in insect_terms):
        return "insect_robot"

    if any(term in text for term in drone_terms):
        return "drone"

    if any(term in text for term in rover_terms):
        return "rover"

    if any(term in text for term in arm_terms):
        return "robot_arm"

    if any(term in text for term in enclosure_terms):
        return "enclosure"

    return "generic_robotics"

def default_parameters(project_type: str) -> Dict[str, Any]:
    if project_type == "insect_robot":
        return {
            "units": "mm",
            "body_height": 18,
            "head_radius": 26,
            "thorax_radius": 42,
            "abdomen_radius": 36,
            "head_x": 78,
            "abdomen_x": -76,
            "leg_side_offset_y": 42,
            "upper_leg_length": 48,
            "lower_leg_length": 52,
            "leg_width": 8,
            "leg_height": 7,
            "mount_hole_radius": 2.2,
            "standoff_radius": 3,
            "standoff_height": 10,
            "label_height": 4,
        }

    common = {
        "units": "mm",
        "base_length": 300,
        "base_width": 200,
        "base_height": 35,
        "plate_thickness": 4,
        "corner_radius": 12,
        "mount_hole_radius": 2.2,
        "standoff_radius": 3,
        "standoff_height": 12,
        "label_height": 4,
    }

    if project_type == "drone":
        common.update(
            {
                "rotor_count": 4,
                "center_body_radius": 70,
                "center_body_height": 24,
                "arm_length": 185,
                "arm_width": 18,
                "arm_height": 10,
                "motor_mount_radius": 22,
                "motor_placeholder_radius": 18,
                "motor_placeholder_height": 22,
                "propeller_disk_radius": 48,
                "battery_length": 95,
                "battery_width": 38,
                "battery_height": 28,
                "flight_controller_size": 38,
                "esc_length": 34,
                "esc_width": 14,
                "esc_height": 6,
                "payload_mount_length": 70,
                "payload_mount_width": 45,
                "payload_mount_height": 10,
            }
        )

    elif project_type == "rover":
        common.update(
            {
                "wheel_radius": 38,
                "wheel_width": 18,
                "wheel_offset_x": 110,
                "wheel_offset_y": 115,
                "camera_mast_height": 120,
                "camera_body_width": 42,
                "camera_body_height": 28,
                "raspberry_pi_length": 85,
                "raspberry_pi_width": 56,
                "battery_length": 95,
                "battery_width": 45,
                "battery_height": 25,
                "sensor_block_width": 28,
                "motor_driver_length": 50,
                "motor_driver_width": 45,
                "motor_driver_height": 8,
                "bumper_length": 150,
                "bumper_width": 12,
                "bumper_height": 18,
                "gusset_length": 35,
                "gusset_width": 6,
                "gusset_height": 45,
            }
        )

    elif project_type == "robot_arm":
        common.update(
            {
                "base_radius": 55,
                "base_cylinder_height": 28,
                "link_length": 120,
                "link_width": 26,
                "link_height": 18,
                "joint_radius": 22,
                "joint_width": 20,
            }
        )

    elif project_type == "enclosure":
        common.update(
            {
                "box_length": 140,
                "box_width": 90,
                "box_height": 45,
                "wall_thickness": 3,
                "lid_thickness": 3,
                "port_width": 22,
                "port_height": 12,
            }
        )

    return common


def extract_cad_artifact(mission_result: Dict[str, Any]) -> Dict[str, Any]:
    artifacts = mission_result.get("artifacts", {}) or {}

    if not isinstance(artifacts, dict):
        return {}

    for key in ["fusion360_concept", "cad_model_plan", "cad_parameters", "mechanical_design"]:
        value = artifacts.get(key)

        if isinstance(value, dict):
            return value

    return {}


def merge_parameters(base: Dict[str, Any], cad_artifact: Dict[str, Any]) -> Dict[str, Any]:
    merged = dict(base)
    possible_params = {}

    if isinstance(cad_artifact, dict):
        if isinstance(cad_artifact.get("parameters"), dict):
            possible_params.update(cad_artifact["parameters"])

        if isinstance(cad_artifact.get("dimensions"), dict):
            possible_params.update(cad_artifact["dimensions"])

    for key, value in possible_params.items():
        clean_key = safe_name(key)

        if isinstance(value, (int, float)):
            merged[clean_key] = value
        else:
            try:
                numeric = float(str(value).replace("mm", "").strip())
                merged[clean_key] = numeric
            except Exception:
                pass

    return merged


def extract_morphology_plan(mission_result: Dict[str, Any]) -> Dict[str, Any]:
    artifacts = mission_result.get("artifacts", {})
    if not isinstance(artifacts, dict):
        return {}

    morphology_plan = artifacts.get("morphology_plan", {})
    return morphology_plan if isinstance(morphology_plan, dict) else {}


def fusion_project_type_from_morphology(
    fallback_project_type: str,
    morphology_plan: Dict[str, Any],
) -> str:
    morphology_id = str(morphology_plan.get("morphology_id", "")).lower()
    project_family = str(morphology_plan.get("project_family", "")).lower()

    if morphology_id == "segmented_insect_robot":
        return "insect_robot"

    if morphology_id == "wheeled_rover" or project_family == "wheeled_rover":
        return "rover"

    if morphology_id == "quadcopter_drone" or project_family == "quadcopter_drone":
        return "drone"

    if morphology_id == "robot_arm" or project_family == "robot_arm":
        return "robot_arm"

    if morphology_id in {"sensor_module", "enclosure"}:
        return "enclosure"

    return fallback_project_type or "concept"


def model_name_from_morphology(
    fallback_model_name: str,
    morphology_plan: Dict[str, Any],
) -> str:
    morphology_id = str(morphology_plan.get("morphology_id", "")).strip()

    if morphology_id:
        return f"omni_{morphology_id}"

    return fallback_model_name


def fusion_project_type_from_morphology_spec(
    fallback_project_type: str,
    morphology_spec: Dict[str, Any],
) -> str:
    """
    Use the new MorphologySpec family as Fusion export identity.

    Existing builder-compatible families map to old project types.
    New biomorphic families keep their own family name so generated artifacts
    stop appearing as generic_robotics.
    """
    if not isinstance(morphology_spec, dict):
        return fallback_project_type or "concept"

    family = str(morphology_spec.get("morphology_family", "") or "").lower().strip()

    if not family:
        return fallback_project_type or "concept"

    builder_compatible = {
        "aerial_drone": "drone",
        "wheeled_rover": "rover",
        "tracked_rover": "rover",
        "armored_rover": "rover",
        "manipulator_arm": "robot_arm",
        "sensor_pod": "enclosure",
        "insectoid_legged_robot": "insect_robot",
        "hexapod_robot": "insect_robot",
    }

    if family in builder_compatible:
        return builder_compatible[family]

    # New biomorphic families are allowed to pass through as their own
    # project_type. The generated Fusion script will safely fall back to the
    # generic builder until specialized visual builders are added.
    return family


def model_name_from_morphology_spec(
    fallback_model_name: str,
    morphology_spec: Dict[str, Any],
) -> str:
    """
    Create a more descriptive model name from MorphologySpec.

    Example:
        gecko + wall_climbing_robot
        -> omni_gecko_wall_climbing_robot_fusion_concept
    """
    if not isinstance(morphology_spec, dict):
        return fallback_model_name

    family = str(morphology_spec.get("morphology_family", "") or "").strip()
    bio = morphology_spec.get("bio_inspiration", {}) or {}
    source_creature = str(bio.get("source_creature", "") or "").strip()

    parts = [p for p in [source_creature, family] if p]

    if not parts:
        return fallback_model_name

    return f"omni_{safe_name('_'.join(parts))}_fusion_concept"


def build_cad_context(
    project_type: str,
    morphology_plan: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    """
    Build CAD context for Fusion generation.

    If a MorphologyPlan exists, it becomes the primary source of physical design
    intent. This prevents unrelated CAD pattern leakage, such as rover/drone
    guidance appearing inside insect robot CAD exports.

    If no MorphologyPlan exists, OMNI falls back to the older CAD pattern library.
    """
    morphology_plan = morphology_plan or {}

    if morphology_plan:
        body_plan = morphology_plan.get("body_plan", {})
        body_segments = body_plan.get("segments", [])
        required_features = body_plan.get("required_features", [])
        avoid_features = body_plan.get("avoid_features", [])
        mounting_points = body_plan.get("mounting_points", [])

        morphology_id = morphology_plan.get("morphology_id", "")
        project_family = morphology_plan.get("project_family", "")
        display_name = morphology_plan.get("display_name", "")
        description = morphology_plan.get("description", "")

        cad_context: Dict[str, Any] = {
            "project_type": project_type,
            "morphology_id": morphology_id,
            "project_family": project_family,
            "display_name": display_name,
            "description": description,
            "morphology_plan": morphology_plan,
            "recommended_features": [],
            "design_rules": [],
            "reference_lessons": [
                "Morphology Engine context is active.",
                "Use morphology_plan as the primary physical design contract.",
                "Do not mix reference patterns from unrelated robot families.",
                "CAD output should reflect the selected morphology_id and avoid all avoid_features.",
            ],
            "default_dimensions_mm": {},
        }

        cad_context["recommended_features"].extend(body_segments)
        cad_context["recommended_features"].extend(required_features)
        cad_context["recommended_features"].extend(mounting_points)

        cad_context["design_rules"].extend(
            [
                f"Use morphology_id: {morphology_id}",
                f"Use project_family: {project_family}",
                "Generated CAD must follow morphology_plan body segments.",
                "Generated CAD must include morphology_plan required_features.",
                "Generated CAD must include morphology_plan mounting_points when mechanically relevant.",
                "Generated CAD must avoid morphology_plan avoid_features.",
            ]
        )

        for avoid in avoid_features:
            cad_context["design_rules"].append(f"AVOID: {avoid}")

        return cad_context

    if summarize_cad_context is None:
        return {
            "project_type": project_type,
            "recommended_features": [],
            "design_rules": [],
            "reference_lessons": [
                "CAD pattern library unavailable. Procedural CAD generation will still run."
            ],
            "default_dimensions_mm": {},
        }

    try:
        return summarize_cad_context(project_type)
    except Exception as exc:
        return {
            "project_type": project_type,
            "recommended_features": [],
            "design_rules": [],
            "reference_lessons": [
                f"CAD pattern library failed safely: {exc}",
                "Procedural CAD generation will still run.",
            ],
            "default_dimensions_mm": {},
        }


def cad_context_to_brief(cad_context: Dict[str, Any]) -> str:
    lines = [
        "CAD REFERENCE CONTEXT",
        "=====================",
        f"Project type: {cad_context.get('project_type', 'unknown')}",
        "",
        "Recommended features:",
    ]

    for item in cad_context.get("recommended_features", []):
        lines.append(f"- {item}")

    lines.extend(["", "Design rules:"])

    for item in cad_context.get("design_rules", []):
        lines.append(f"- {item}")

    lines.extend(["", "Reference lessons:"])

    for item in cad_context.get("reference_lessons", []):
        lines.append(f"- {item}")

    return "\n".join(lines)


# ---------------------------------------------------------
# Fusion Script Generation
# ---------------------------------------------------------
def generate_fusion360_script(
    model_name: str,
    project_type: str,
    parameters: Dict[str, Any],
    cad_reference_brief: str = "",
    morphology_id: str = "",
) -> str:
    params_json = pprint.pformat(parameters, indent=4, width=120, sort_dicts=False)
    cad_reference_json = json.dumps(cad_reference_brief, indent=4)

    return f'''"""
Generated by OMNI Command.

Model: {model_name}
Project type: {project_type}
Morphology ID: {morphology_id}

How to use:
1. Open Autodesk Fusion 360.
2. Create or open a design.
3. Go to Utilities / Tools -> Scripts and Add-Ins.
4. Create or open a Python script.
5. Replace the script contents with this file.
6. Run the script.

This creates a parametric concept model, not a final manufacturing-ready design.
Review dimensions, clearances, material choices, mounting holes, and safety constraints.

Fusion compatibility note:
This script builds directly into the active root component. It does not create a
new component and does not rename the root component, because some Fusion Part
Design documents only allow one component and do not allow root renaming.
"""

import math
import traceback
import adsk.core
import adsk.fusion


MODEL_NAME = "{model_name}"
PROJECT_TYPE = "{project_type}"
MORPHOLOGY_ID = "{morphology_id}"

PARAMS = {params_json}

CAD_REFERENCE_BRIEF = {cad_reference_json}


def mm(value):
    # Fusion's internal raw numeric unit is centimeters.
    # 10 mm = 1 cm.
    return float(value) / 10.0


def get_param(name, fallback):
    return PARAMS.get(name, fallback)


def clamp_int(value, minimum, maximum, fallback):
    try:
        number = int(value)
    except Exception:
        number = fallback

    return max(minimum, min(maximum, number))


def add_body_translation(body, x_mm=0, y_mm=0, z_mm=0):
    try:
        matrix = adsk.core.Matrix3D.create()
        matrix.translation = adsk.core.Vector3D.create(mm(x_mm), mm(y_mm), mm(z_mm))
        body.transform(matrix)
    except Exception:
        pass


def create_rotated_rectangle_profile(sketch, center_x_mm, center_y_mm, length_mm, width_mm, angle_deg=0):
    cx = mm(center_x_mm)
    cy = mm(center_y_mm)
    half_l = mm(length_mm) / 2.0
    half_w = mm(width_mm) / 2.0

    angle = math.radians(angle_deg)
    ux = (math.cos(angle), math.sin(angle))
    uy = (-math.sin(angle), math.cos(angle))

    raw_corners = [
        (-half_l, -half_w),
        (half_l, -half_w),
        (half_l, half_w),
        (-half_l, half_w),
    ]

    points = []

    for lx, ly in raw_corners:
        x = cx + lx * ux[0] + ly * uy[0]
        y = cy + lx * ux[1] + ly * uy[1]
        points.append(adsk.core.Point3D.create(x, y, 0))

    lines = sketch.sketchCurves.sketchLines

    for index in range(len(points)):
        start = points[index]
        end = points[(index + 1) % len(points)]
        lines.addByTwoPoints(start, end)

    return sketch.profiles.item(0)


def create_box(
    component,
    name,
    length_mm,
    width_mm,
    height_mm,
    center_x=0,
    center_y=0,
    base_z=0,
    angle_deg=0,
):
    sketches = component.sketches
    xy_plane = component.xYConstructionPlane
    sketch = sketches.add(xy_plane)
    sketch.name = name + "_sketch"

    profile = create_rotated_rectangle_profile(
        sketch,
        center_x,
        center_y,
        length_mm,
        width_mm,
        angle_deg,
    )

    extrudes = component.features.extrudeFeatures
    distance = adsk.core.ValueInput.createByReal(mm(height_mm))
    extrude_input = extrudes.createInput(profile, adsk.fusion.FeatureOperations.NewBodyFeatureOperation)
    extrude_input.setDistanceExtent(False, distance)

    body = extrudes.add(extrude_input).bodies.item(0)
    body.name = name

    add_body_translation(body, 0, 0, base_z)

    return body


def create_cylinder(
    component,
    name,
    radius_mm,
    height_mm,
    center_x=0,
    center_y=0,
    base_z=0,
):
    sketches = component.sketches
    xy_plane = component.xYConstructionPlane
    sketch = sketches.add(xy_plane)
    sketch.name = name + "_sketch"

    center = adsk.core.Point3D.create(mm(center_x), mm(center_y), 0)
    sketch.sketchCurves.sketchCircles.addByCenterRadius(center, mm(radius_mm))

    profile = sketch.profiles.item(0)

    extrudes = component.features.extrudeFeatures
    distance = adsk.core.ValueInput.createByReal(mm(height_mm))
    extrude_input = extrudes.createInput(profile, adsk.fusion.FeatureOperations.NewBodyFeatureOperation)
    extrude_input.setDistanceExtent(False, distance)

    body = extrudes.add(extrude_input).bodies.item(0)
    body.name = name

    add_body_translation(body, 0, 0, base_z)

    return body


def create_label(component, text, x_mm, y_mm, z_mm=0):
    # Lightweight sketch text label.
    # If Fusion text creation fails, the model still generates.
    try:
        sketches = component.sketches
        xy_plane = component.xYConstructionPlane
        sketch = sketches.add(xy_plane)
        sketch.name = "label_" + text.replace(" ", "_").lower()

        point = adsk.core.Point3D.create(mm(x_mm), mm(y_mm), 0)
        text_input = sketch.sketchTexts.createInput(text, mm(get_param("label_height", 4)), point)
        sketch.sketchTexts.add(text_input)
    except Exception:
        pass


def create_reference_note_label(component):
    try:
        if not CAD_REFERENCE_BRIEF:
            return

        create_label(component, "CAD reference context embedded", -130, 105, 0)
    except Exception:
        pass



def build_insect_robot(component):
    # Bio-inspired insect robot concept.
    # This is intentionally not a drone or rover template.

    body_height = get_param("body_height", 18)

    # Segmented body: head, thorax, abdomen.
    create_cylinder(
        component,
        "head_sensor_capsule",
        get_param("head_radius", 26),
        body_height,
        get_param("head_x", 78),
        0,
        0,
    )

    create_cylinder(
        component,
        "thorax_electronics_body",
        get_param("thorax_radius", 42),
        body_height + 6,
        0,
        0,
        0,
    )

    create_cylinder(
        component,
        "abdomen_battery_body",
        get_param("abdomen_radius", 36),
        body_height,
        get_param("abdomen_x", -76),
        0,
        0,
    )

    # Body bridges.
    create_box(
        component,
        "head_to_thorax_bridge",
        44,
        14,
        8,
        42,
        0,
        body_height / 2,
        0,
    )

    create_box(
        component,
        "thorax_to_abdomen_bridge",
        48,
        16,
        8,
        -40,
        0,
        body_height / 2,
        0,
    )

    # Electronics and battery placeholders.
    create_box(
        component,
        "electronics_bay_pi_zero_placeholder",
        46,
        28,
        7,
        0,
        0,
        body_height + 8,
        0,
    )

    create_box(
        component,
        "battery_bay_under_abdomen",
        58,
        26,
        8,
        -76,
        0,
        body_height + 2,
        0,
    )

    create_box(
        component,
        "front_camera_or_distance_sensor_pod",
        20,
        14,
        14,
        108,
        0,
        body_height + 4,
        0,
    )

    # Six legs: three per side.
    leg_x_positions = [42, 0, -42]
    side_y = get_param("leg_side_offset_y", 42)

    upper_leg_length = get_param("upper_leg_length", 48)
    lower_leg_length = get_param("lower_leg_length", 52)
    leg_width = get_param("leg_width", 8)
    leg_height = get_param("leg_height", 7)

    # Angles make the front/middle/rear legs splay outward like an insect.
    left_upper_angles = [55, 90, 125]
    left_lower_angles = [70, 90, 110]

    for index, x in enumerate(leg_x_positions):
        for side in [-1, 1]:
            side_name = "left" if side > 0 else "right"
            leg_name = side_name + "_leg_" + str(index + 1)

            hip_y = side * side_y
            knee_y = side * (side_y + 36)
            foot_y = side * (side_y + 78)

            upper_angle = left_upper_angles[index] * side
            lower_angle = left_lower_angles[index] * side

            # Hip joint marker.
            create_cylinder(
                component,
                leg_name + "_hip_joint_marker",
                7,
                5,
                x,
                hip_y,
                body_height / 2,
            )

            # Upper leg segment.
            create_box(
                component,
                leg_name + "_upper_segment",
                upper_leg_length,
                leg_width,
                leg_height,
                x,
                (hip_y + knee_y) / 2,
                body_height / 2,
                upper_angle,
            )

            # Knee joint marker.
            create_cylinder(
                component,
                leg_name + "_knee_joint_marker",
                6,
                5,
                x,
                knee_y,
                body_height / 2 - 3,
            )

            # Lower leg segment.
            create_box(
                component,
                leg_name + "_lower_segment",
                lower_leg_length,
                leg_width,
                leg_height,
                x,
                (knee_y + foot_y) / 2,
                body_height / 2 - 6,
                lower_angle,
            )

            # Foot pad.
            create_box(
                component,
                leg_name + "_compliant_foot_pad",
                22,
                11,
                4,
                x,
                foot_y,
                0,
                0,
            )

    # Mounting bosses on thorax.
    for boss_x in [-18, 18]:
        for boss_y in [-18, 18]:
            create_cylinder(
                component,
                "thorax_mounting_boss",
                get_param("standoff_radius", 3),
                get_param("standoff_height", 10),
                boss_x,
                boss_y,
                body_height + 6,
            )

    # Subsystem labels.
    create_label(component, "HEAD SENSOR POD", 62, -24, body_height + 12)
    create_label(component, "THORAX ELECTRONICS", -30, -32, body_height + 14)
    create_label(component, "ABDOMEN BATTERY", -112, -26, body_height + 10)
    create_label(component, MODEL_NAME, -128, -92, body_height + 2)
    create_reference_note_label(component)


def build_rover(component):
    base_length = get_param("base_length", 300)
    base_width = get_param("base_width", 200)
    plate_thickness = get_param("plate_thickness", 4)

    create_box(component, "main_chassis_plate", base_length, base_width, plate_thickness, 0, 0, 0)

    create_box(
        component,
        "raspberry_pi_mount_placeholder",
        get_param("raspberry_pi_length", 85),
        get_param("raspberry_pi_width", 56),
        6,
        -45,
        0,
        plate_thickness,
    )

    create_box(
        component,
        "battery_bay_placeholder",
        get_param("battery_length", 95),
        get_param("battery_width", 45),
        get_param("battery_height", 25),
        55,
        0,
        plate_thickness,
    )

    create_box(
        component,
        "motor_driver_mount_zone",
        get_param("motor_driver_length", 50),
        get_param("motor_driver_width", 45),
        get_param("motor_driver_height", 8),
        -55,
        55,
        plate_thickness,
    )

    create_box(
        component,
        "camera_mast",
        12,
        12,
        get_param("camera_mast_height", 120),
        115,
        0,
        plate_thickness,
    )

    # Simple mast gussets based on CAD pattern library lesson.
    create_box(
        component,
        "camera_mast_left_gusset",
        get_param("gusset_length", 35),
        get_param("gusset_width", 6),
        get_param("gusset_height", 45),
        98,
        -10,
        plate_thickness,
        28,
    )

    create_box(
        component,
        "camera_mast_right_gusset",
        get_param("gusset_length", 35),
        get_param("gusset_width", 6),
        get_param("gusset_height", 45),
        98,
        10,
        plate_thickness,
        -28,
    )

    create_box(
        component,
        "camera_module_placeholder",
        get_param("camera_body_width", 42),
        16,
        get_param("camera_body_height", 28),
        115,
        0,
        plate_thickness + get_param("camera_mast_height", 120),
    )

    create_box(
        component,
        "front_sensor_block",
        get_param("sensor_block_width", 28),
        18,
        16,
        145,
        0,
        plate_thickness,
    )

    create_box(
        component,
        "rear_service_block",
        28,
        18,
        16,
        -145,
        0,
        plate_thickness,
    )

    create_box(
        component,
        "front_bumper_placeholder",
        get_param("bumper_width", 12),
        get_param("bumper_length", 150),
        get_param("bumper_height", 18),
        base_length / 2 + 10,
        0,
        0,
    )

    create_box(
        component,
        "center_cable_routing_corridor_marker",
        base_length * 0.62,
        8,
        2,
        0,
        0,
        plate_thickness + 2,
    )

    wheel_radius = get_param("wheel_radius", 38)
    wheel_width = get_param("wheel_width", 18)
    wheel_offset_x = get_param("wheel_offset_x", 110)
    wheel_offset_y = get_param("wheel_offset_y", 115)

    for x in [-wheel_offset_x, wheel_offset_x]:
        for y in [-wheel_offset_y, wheel_offset_y]:
            create_cylinder(component, "wheel_placeholder", wheel_radius, wheel_width, x, y, 0)

    hole_radius = get_param("mount_hole_radius", 2.2)

    for x in [-base_length / 2 + 20, base_length / 2 - 20]:
        for y in [-base_width / 2 + 20, base_width / 2 - 20]:
            create_cylinder(component, "mount_hole_marker", hole_radius, 3, x, y, plate_thickness)

    standoff_radius = get_param("standoff_radius", 3)
    standoff_height = get_param("standoff_height", 12)

    for x in [-78, -12]:
        for y in [-22, 22]:
            create_cylinder(component, "raspberry_pi_standoff_marker", standoff_radius, standoff_height, x, y, plate_thickness)

    create_label(component, MODEL_NAME, -base_length / 2 + 18, -base_width / 2 + 12, plate_thickness + 1)
    create_reference_note_label(component)


def build_drone(component):
    rotor_count = clamp_int(get_param("rotor_count", 4), 3, 8, 4)

    center_radius = get_param("center_body_radius", 70)
    center_height = get_param("center_body_height", 24)
    arm_length = get_param("arm_length", 185)
    arm_width = get_param("arm_width", 18)
    arm_height = get_param("arm_height", 10)

    create_cylinder(component, "central_body_plate", center_radius, center_height, 0, 0, 0)

    create_box(
        component,
        "battery_placeholder",
        get_param("battery_length", 95),
        get_param("battery_width", 38),
        get_param("battery_height", 28),
        0,
        0,
        center_height,
        0,
    )

    fc_size = get_param("flight_controller_size", 38)

    create_box(
        component,
        "flight_controller_placeholder",
        fc_size,
        fc_size,
        8,
        0,
        0,
        center_height + get_param("battery_height", 28) + 4,
        0,
    )

    create_box(
        component,
        "payload_mount_placeholder",
        get_param("payload_mount_length", 70),
        get_param("payload_mount_width", 45),
        get_param("payload_mount_height", 10),
        0,
        -center_radius * 0.45,
        center_height + 6,
        0,
    )

    motor_mount_radius = get_param("motor_mount_radius", 22)
    motor_placeholder_radius = get_param("motor_placeholder_radius", 18)
    motor_placeholder_height = get_param("motor_placeholder_height", 22)
    propeller_disk_radius = get_param("propeller_disk_radius", 48)

    esc_length = get_param("esc_length", 34)
    esc_width = get_param("esc_width", 14)
    esc_height = get_param("esc_height", 6)

    motor_distance = center_radius + arm_length
    start_angle = 90.0

    for index in range(rotor_count):
        angle_deg = start_angle + (360.0 / rotor_count) * index
        angle_rad = math.radians(angle_deg)

        dx = math.cos(angle_rad)
        dy = math.sin(angle_rad)

        motor_x = dx * motor_distance
        motor_y = dy * motor_distance

        arm_center_x = dx * (motor_distance / 2.0)
        arm_center_y = dy * (motor_distance / 2.0)

        esc_x = dx * (center_radius + arm_length * 0.45)
        esc_y = dy * (center_radius + arm_length * 0.45)

        create_box(
            component,
            "arm_%02d_structural_beam" % (index + 1),
            motor_distance,
            arm_width,
            arm_height,
            arm_center_x,
            arm_center_y,
            center_height / 2,
            angle_deg,
        )

        create_box(
            component,
            "esc_%02d_placeholder" % (index + 1),
            esc_length,
            esc_width,
            esc_height,
            esc_x,
            esc_y,
            center_height + 4,
            angle_deg,
        )

        create_cylinder(
            component,
            "motor_mount_%02d" % (index + 1),
            motor_mount_radius,
            6,
            motor_x,
            motor_y,
            center_height,
        )

        create_cylinder(
            component,
            "motor_body_%02d_placeholder" % (index + 1),
            motor_placeholder_radius,
            motor_placeholder_height,
            motor_x,
            motor_y,
            center_height + 6,
        )

        create_cylinder(
            component,
            "propeller_clearance_disk_%02d" % (index + 1),
            propeller_disk_radius,
            1.5,
            motor_x,
            motor_y,
            center_height + 6 + motor_placeholder_height,
        )

    standoff_radius = get_param("standoff_radius", 3)
    standoff_height = get_param("standoff_height", 12)

    for x in [-32, 32]:
        for y in [-32, 32]:
            create_cylinder(
                component,
                "electronics_standoff_marker",
                standoff_radius,
                standoff_height,
                x,
                y,
                center_height,
            )

    create_label(component, MODEL_NAME, -60, -20, center_height + 40)
    create_reference_note_label(component)


def build_robot_arm(component):
    base_radius = get_param("base_radius", 55)
    base_height = get_param("base_cylinder_height", 28)
    link_length = get_param("link_length", 120)
    link_width = get_param("link_width", 26)
    link_height = get_param("link_height", 18)
    joint_radius = get_param("joint_radius", 22)
    joint_width = get_param("joint_width", 20)

    create_cylinder(component, "base_rotation_placeholder", base_radius, base_height, 0, 0, 0)
    create_cylinder(component, "shoulder_joint_placeholder", joint_radius, joint_width, 0, 0, base_height)

    create_box(
        component,
        "upper_link_placeholder",
        link_length,
        link_width,
        link_height,
        link_length / 2,
        0,
        base_height + joint_width,
    )

    create_cylinder(
        component,
        "elbow_joint_placeholder",
        joint_radius,
        joint_width,
        link_length,
        0,
        base_height + joint_width,
    )

    create_box(
        component,
        "forearm_link_placeholder",
        link_length,
        link_width,
        link_height,
        link_length * 1.5,
        0,
        base_height + joint_width,
    )

    create_cylinder(
        component,
        "wrist_joint_placeholder",
        joint_radius * 0.75,
        joint_width,
        link_length * 2,
        0,
        base_height + joint_width,
    )

    create_box(
        component,
        "end_effector_placeholder",
        35,
        18,
        14,
        link_length * 2 + 25,
        0,
        base_height + joint_width,
    )

    create_label(component, MODEL_NAME, -50, -50, base_height + 2)
    create_reference_note_label(component)


def build_enclosure(component):
    box_length = get_param("box_length", 140)
    box_width = get_param("box_width", 90)
    box_height = get_param("box_height", 45)
    lid_thickness = get_param("lid_thickness", 3)

    create_box(component, "electronics_enclosure_body_placeholder", box_length, box_width, box_height, 0, 0, 0)

    create_box(
        component,
        "removable_lid_placeholder",
        box_length + 4,
        box_width + 4,
        lid_thickness,
        0,
        0,
        box_height,
    )

    create_box(
        component,
        "front_port_placeholder",
        get_param("port_width", 22),
        4,
        get_param("port_height", 12),
        box_length / 2,
        0,
        box_height / 2,
    )

    for x in [-box_length / 2 + 12, box_length / 2 - 12]:
        for y in [-box_width / 2 + 12, box_width / 2 - 12]:
            create_cylinder(
                component,
                "lid_screw_marker",
                get_param("mount_hole_radius", 2.2),
                2,
                x,
                y,
                box_height + lid_thickness,
            )

    create_label(component, MODEL_NAME, -box_length / 2 + 12, -box_width / 2 + 10, box_height + lid_thickness + 1)
    create_reference_note_label(component)



def _bio_clean_name(value, fallback):
    text = str(value or fallback).lower().strip()
    text = text.replace(" ", "_").replace("-", "_").replace("/", "_")
    safe = ""
    for ch in text:
        if ch.isalnum() or ch == "_":
            safe += ch
    if not safe:
        safe = fallback
    return safe


def _bio_float(value, fallback):
    try:
        return float(value)
    except Exception:
        return float(fallback)


def _bio_list(value):
    if isinstance(value, list):
        return value
    return []


def _get_morphology_spec():
    spec = PARAMS.get("morphology_spec", dict())
    if isinstance(spec, dict):
        return spec
    return dict()


def _bio_segment_box(component, segment, index, x_offset):
    name = _bio_clean_name(segment.get("name", "segment"), "segment_" + str(index + 1))
    length = _bio_float(segment.get("length_mm", 70), 70)
    width = _bio_float(segment.get("width_mm", 36), 36)
    height = _bio_float(segment.get("height_mm", 18), 18)
    z_base = _bio_float(segment.get("z_base_mm", 0), 0)

    create_box(
        component,
        "bio_segment_" + name,
        length,
        width,
        height,
        x_offset,
        0,
        z_base,
    )


def _bio_draw_low_quadruped(component, spec):
    bio = spec.get("bio_inspiration", dict())
    source = _bio_clean_name(bio.get("source_creature", "creature"), "creature")

    create_box(component, source + "_low_torso", 95, 45, 18, 0, 0, 14)
    create_box(component, source + "_sensor_head", 35, 28, 18, 62, 0, 18)
    create_box(component, source + "_tail_stabilizer", 70, 10, 8, -78, 0, 16)

    leg_x = [-28, 28]
    leg_y = [-32, 32]

    index = 1
    for x in leg_x:
        for y in leg_y:
            create_box(component, source + "_splayed_limb_" + str(index), 52, 8, 8, x, y, 8)
            create_box(component, source + "_adhesive_foot_pad_" + str(index), 24, 18, 4, x, y + 16 if y > 0 else y - 16, 2)
            index += 1

    create_label(component, source + " wall-climbing morphology", -95, -60, 8)


def _bio_draw_quadruped_runner(component, spec):
    bio = spec.get("bio_inspiration", dict())
    source = _bio_clean_name(bio.get("source_creature", "quadruped"), "quadruped")

    create_box(component, source + "_raised_torso", 110, 38, 28, 0, 0, 52)
    create_box(component, source + "_hip_body", 46, 36, 22, -58, 0, 48)
    create_box(component, source + "_sensor_head", 38, 28, 22, 72, 0, 58)
    create_box(component, source + "_tail_balance_beam", 70, 8, 8, -100, 0, 56)

    positions = [(32, 24), (32, -24), (-38, 24), (-38, -24)]
    for i, pos in enumerate(positions):
        x = pos[0]
        y = pos[1]
        create_box(component, source + "_upper_leg_" + str(i + 1), 10, 8, 34, x, y, 31)
        create_box(component, source + "_lower_leg_" + str(i + 1), 8, 7, 32, x + 8, y, 12)
        create_box(component, source + "_foot_" + str(i + 1), 24, 10, 5, x + 16, y, 1)

    create_label(component, source + " quadruped morphology", -95, -60, 12)


def _bio_draw_serpentine(component, spec):
    bio = spec.get("bio_inspiration", dict())
    source = _bio_clean_name(bio.get("source_creature", "snake"), "snake")

    module_count = 8
    spacing = 34
    start_x = -spacing * (module_count - 1) / 2

    for i in range(module_count):
        x = start_x + i * spacing
        create_box(component, source + "_body_module_" + str(i + 1), 28, 24, 18, x, 0, 8)
        if i < module_count - 1:
            create_box(component, source + "_flex_joint_" + str(i + 1), 10, 14, 12, x + spacing / 2, 0, 8)

    create_box(component, source + "_front_sensor_head", 34, 26, 22, start_x + module_count * spacing, 0, 10)
    create_label(component, source + " serpentine modular chain", start_x, -45, 8)


def _bio_draw_aquatic_glider(component, spec):
    bio = spec.get("bio_inspiration", dict())
    source = _bio_clean_name(bio.get("source_creature", "manta"), "manta")

    create_box(component, source + "_central_hydrodynamic_body", 90, 45, 14, 0, 0, 8)
    create_box(component, source + "_left_wide_fin", 80, 95, 4, 0, 72, 7)
    create_box(component, source + "_right_wide_fin", 80, 95, 4, 0, -72, 7)
    create_box(component, source + "_front_sensor_pod", 28, 24, 16, 58, 0, 10)
    create_box(component, source + "_tail_stabilizer", 70, 8, 5, -78, 0, 8)

    create_label(component, source + " aquatic glider morphology", -95, -95, 8)


def _bio_draw_winged_uav(component, spec):
    bio = spec.get("bio_inspiration", dict())
    source = _bio_clean_name(bio.get("source_creature", "bird"), "bird")

    create_box(component, source + "_lightweight_fuselage", 125, 28, 18, 0, 0, 14)
    create_box(component, source + "_left_wing_surface", 85, 100, 4, 0, 72, 15)
    create_box(component, source + "_right_wing_surface", 85, 100, 4, 0, -72, 15)
    create_box(component, source + "_tail_plane", 38, 62, 4, -80, 0, 18)
    create_box(component, source + "_nose_sensor", 24, 22, 16, 75, 0, 18)

    if source in ("dragonfly", "damselfly"):
        create_box(component, source + "_front_left_wing", 62, 72, 3, 26, 58, 18)
        create_box(component, source + "_front_right_wing", 62, 72, 3, 26, -58, 18)
        create_box(component, source + "_rear_left_wing", 58, 68, 3, -22, 52, 18)
        create_box(component, source + "_rear_right_wing", 58, 68, 3, -22, -52, 18)
        create_box(component, source + "_long_tail_boom", 95, 8, 8, -78, 0, 15)

    create_label(component, source + " winged biomorphic morphology", -95, -95, 8)


def _bio_draw_crustacean(component, spec):
    bio = spec.get("bio_inspiration", dict())
    source = _bio_clean_name(bio.get("source_creature", "crab"), "crab")

    create_box(component, source + "_wide_armored_shell", 80, 105, 24, 0, 0, 16)
    create_box(component, source + "_front_sensor_bar", 36, 42, 14, 52, 0, 22)

    y_values = [62, 82, -62, -82]
    x_values = [30, 5, -20, -45]
    index = 1

    for side in [1, -1]:
        for x in x_values:
            y = 62 * side
            create_box(component, source + "_lateral_leg_" + str(index), 55, 8, 7, x, y, 8)
            create_box(component, source + "_foot_pad_" + str(index), 16, 18, 4, x, y + 24 * side, 2)
            index += 1

    create_box(component, source + "_left_front_claw", 34, 18, 10, 70, 42, 14)
    create_box(component, source + "_right_front_claw", 34, 18, 10, 70, -42, 14)

    create_label(component, source + " crustacean lateral walker", -95, -95, 8)


def _bio_draw_soft_radial(component, spec):
    bio = spec.get("bio_inspiration", dict())
    source = _bio_clean_name(bio.get("source_creature", "octopus"), "octopus")

    create_cylinder(component, source + "_central_soft_body", 32, 28, 0, 0, 18)
    create_box(component, source + "_sensor_head", 36, 24, 18, 0, 0, 42)

    arm_count = 8
    for i in range(arm_count):
        angle = math.radians(i * 360.0 / arm_count)
        x = math.cos(angle) * 45
        y = math.sin(angle) * 45
        create_box(component, source + "_soft_arm_" + str(i + 1), 52, 7, 7, x, y, 10)

    create_label(component, source + " soft radial morphology", -95, -95, 8)


def _bio_draw_from_spec_generic(component, spec):
    segments = _bio_list(spec.get("primary_segments", []))
    appendages = _bio_list(spec.get("appendages", []))

    if not segments:
        create_box(component, "biomorphic_generic_body", 100, 55, 24, 0, 0, 18)
    else:
        spacing = 55
        start_x = -spacing * max(0, len(segments) - 1) / 2
        for i, segment in enumerate(segments):
            _bio_segment_box(component, segment, i, start_x + i * spacing)

    for i, app in enumerate(appendages):
        app_type = str(app.get("appendage_type", app.get("type", "appendage")) or "appendage")
        attach = app.get("attach", [0, 0, 0])
        if not isinstance(attach, list) or len(attach) != 3:
            attach = [app.get("attach_x_mm", 0), app.get("attach_y_mm", 0), app.get("attach_z_mm", 0)]

        x = _bio_float(attach[0], 0)
        y = _bio_float(attach[1], 0)
        z = _bio_float(attach[2], 8)

        length = _bio_float(app.get("length_mm", 45), 45)
        width = _bio_float(app.get("width_mm", 8), 8)
        height = _bio_float(app.get("height_mm", 8), 8)

        create_box(
            component,
            "bio_" + _bio_clean_name(app_type, "appendage") + "_" + str(i + 1),
            max(12, length),
            max(4, width),
            max(3, height),
            x,
            y,
            z,
        )

        if app.get("ground_contact", False):
            create_box(
                component,
                "bio_foot_contact_" + str(i + 1),
                18,
                14,
                4,
                x,
                y,
                1,
            )



# ─────────────────────────────────────────────────────────────
# AssemblySpec Rendering Helpers
# ─────────────────────────────────────────────────────────────

def _get_assembly_spec():
    spec = PARAMS.get("assembly_spec", dict())
    if isinstance(spec, dict):
        return spec
    return dict()


def _has_assembly_spec():
    spec = _get_assembly_spec()
    return bool(spec)


def _asm_float(value, fallback):
    try:
        return float(value)
    except Exception:
        return float(fallback)


def _asm_list(value):
    if isinstance(value, list):
        return value
    return []


def _asm_dict(value):
    if isinstance(value, dict):
        return value
    return dict()


def _asm_name(value, fallback):
    return _bio_clean_name(value, fallback)


def _asm_component_dims(component):
    length = _asm_float(component.get("length_mm", 0), 0)
    width = _asm_float(component.get("width_mm", 0), 0)
    height = _asm_float(component.get("height_mm", 0), 0)

    if length <= 0:
        length = 50
    if width <= 0:
        width = 28
    if height <= 0:
        height = 12

    return length, width, height


def _asm_draw_panel(component, panel):
    panel = _asm_dict(panel)

    name = _asm_name(panel.get("name", "panel"), "panel")
    panel_type = str(panel.get("panel_type", "panel") or "panel")
    transparent = bool(panel.get("transparent", False))

    length = _asm_float(panel.get("length_mm", 100), 100)
    width = _asm_float(panel.get("width_mm", 50), 50)
    thickness = _asm_float(panel.get("thickness_mm", 3), 3)

    x = _asm_float(panel.get("x_mm", 0), 0)
    y = _asm_float(panel.get("y_mm", 0), 0)
    z = _asm_float(panel.get("z_mm", 0), 0)
    angle = _asm_float(panel.get("angle_deg", 0), 0)

    body_name = "asm_panel_" + name
    if transparent:
        body_name = body_name + "_transparent_marker"

    create_box(
        component,
        body_name,
        length,
        width,
        thickness,
        x,
        y,
        z,
        angle,
    )

    if transparent:
        create_label(component, "transparent cutaway shell", x - length / 2, y, z + thickness + 2)

    if panel_type in ("fin_panel", "wing_panel"):
        create_label(component, panel_type, x - length / 2, y, z + thickness + 2)


def _asm_draw_component(component, comp):
    comp = _asm_dict(comp)

    name = _asm_name(comp.get("name", "component"), "component")
    ctype = str(comp.get("component_type", "box") or "box").lower()

    x = _asm_float(comp.get("x_mm", 0), 0)
    y = _asm_float(comp.get("y_mm", 0), 0)
    z = _asm_float(comp.get("z_mm", 0), 0)
    angle = _asm_float(comp.get("angle_deg", 0), 0)

    length, width, height = _asm_component_dims(comp)

    label = str(comp.get("label", "") or name)

    # Cylindrical components use width as radius by convention.
    if ctype in ("motor_can", "propeller_disk", "sonar_ring", "camera_lens", "standoff", "screw_boss"):
        radius = max(2.0, width)
        create_cylinder(
            component,
            "asm_component_" + name,
            radius,
            height,
            x,
            y,
            z,
        )
    else:
        create_box(
            component,
            "asm_component_" + name,
            length,
            width,
            height,
            x,
            y,
            z,
            angle,
        )

    if ctype in ("battery_pack", "electronics_board", "compute_module", "flight_controller", "sensor_pod"):
        create_label(component, label, x - length / 2, y - width / 2, z + height + 2)


def _asm_draw_mounting_feature(component, mount):
    mount = _asm_dict(mount)

    name = _asm_name(mount.get("name", "mount"), "mount")
    feature_type = str(mount.get("feature_type", "boss") or "boss").lower()

    x = _asm_float(mount.get("x_mm", 0), 0)
    y = _asm_float(mount.get("y_mm", 0), 0)
    z = _asm_float(mount.get("z_mm", 0), 0)

    diameter = _asm_float(mount.get("diameter_mm", 6), 6)
    height = _asm_float(mount.get("height_mm", 8), 8)

    if feature_type in ("boss", "standoff", "hole_pattern"):
        create_cylinder(
            component,
            "asm_mount_" + name,
            diameter / 2.0,
            height,
            x,
            y,
            z,
        )
    elif feature_type in ("rail", "slot"):
        create_box(
            component,
            "asm_mount_" + name,
            80,
            max(4, diameter),
            max(3, height),
            x,
            y,
            z,
        )
    else:
        create_box(
            component,
            "asm_mount_" + name,
            20,
            8,
            height,
            x,
            y,
            z,
        )


def _asm_draw_fastener_pattern(component, pattern):
    pattern = _asm_dict(pattern)

    name = _asm_name(pattern.get("name", "fasteners"), "fasteners")
    xs = _asm_list(pattern.get("x_positions_mm", []))
    ys = _asm_list(pattern.get("y_positions_mm", []))

    z = _asm_float(pattern.get("z_mm", 0), 0)
    diameter = _asm_float(pattern.get("diameter_mm", 3.2), 3.2)
    depth = _asm_float(pattern.get("depth_mm", 4), 4)

    index = 1
    for x in xs:
        for y in ys:
            create_cylinder(
                component,
                "asm_fastener_" + name + "_" + str(index),
                diameter / 2.0,
                depth,
                _asm_float(x, 0),
                _asm_float(y, 0),
                z,
            )
            index += 1


def _asm_draw_structural_feature(component, feature):
    feature = _asm_dict(feature)

    name = _asm_name(feature.get("name", "structural"), "structural")
    ftype = str(feature.get("feature_type", "rib") or "rib").lower()

    length = _asm_float(feature.get("length_mm", 60), 60)
    width = _asm_float(feature.get("width_mm", 4), 4)
    height = _asm_float(feature.get("height_mm", 20), 20)

    x = _asm_float(feature.get("x_mm", 0), 0)
    y = _asm_float(feature.get("y_mm", 0), 0)
    z = _asm_float(feature.get("z_mm", 0), 0)
    angle = _asm_float(feature.get("angle_deg", 0), 0)

    create_box(
        component,
        "asm_" + ftype + "_" + name,
        length,
        width,
        height,
        x,
        y,
        z,
        angle,
    )

    if ftype in ("cable_corridor", "bulkhead"):
        create_label(component, ftype, x - length / 2, y, z + height + 2)


def _asm_draw_subassembly(component, subassembly):
    subassembly = _asm_dict(subassembly)

    for comp in _asm_list(subassembly.get("components", [])):
        _asm_draw_component(component, comp)

    for mount in _asm_list(subassembly.get("mounting_features", [])):
        _asm_draw_mounting_feature(component, mount)

    for pattern in _asm_list(subassembly.get("fastener_patterns", [])):
        _asm_draw_fastener_pattern(component, pattern)


def _asm_render_assembly_spec(component, family_label):
    assembly = _get_assembly_spec()

    if not assembly:
        return False

    outer_shell = _asm_dict(assembly.get("outer_shell", dict()))
    panels = _asm_list(outer_shell.get("panels", []))

    for panel in panels:
        _asm_draw_panel(component, panel)

    for subassembly in _asm_list(assembly.get("subassemblies", [])):
        _asm_draw_subassembly(component, subassembly)

    for feature in _asm_list(assembly.get("structural_features", [])):
        _asm_draw_structural_feature(component, feature)

    create_label(
        component,
        "Assembly: " + str(assembly.get("assembly_name", "assembly")),
        -140,
        125,
        10,
    )
    create_label(
        component,
        "Detail: " + str(assembly.get("detail_level", "unknown")),
        -140,
        140,
        10,
    )
    create_label(
        component,
        "Visibility: " + str(assembly.get("visibility_mode", "opaque")),
        -140,
        155,
        10,
    )
    create_label(
        component,
        "Family: " + str(family_label),
        -140,
        170,
        10,
    )

    create_reference_note_label(component)
    return True


def build_detailed_aquatic_glider(component):
    rendered = _asm_render_assembly_spec(component, "aquatic_glider_robot")
    if not rendered:
        build_biomorphic_robot(component)


def build_detailed_hybrid_biomorphic_drone(component):
    rendered = _asm_render_assembly_spec(component, "hybrid_biomorphic_drone")
    if not rendered:
        build_biomorphic_robot(component)


def build_detailed_biomorphic_rover(component):
    rendered = _asm_render_assembly_spec(component, "biomorphic_rover")
    if not rendered:
        build_biomorphic_robot(component)


def build_biomorphic_robot(component):
    spec = _get_morphology_spec()
    family = str(spec.get("morphology_family", PROJECT_TYPE) or PROJECT_TYPE).lower()
    bio = spec.get("bio_inspiration", dict())
    source = _bio_clean_name(bio.get("source_creature", family), family)

    if family == "wall_climbing_robot":
        _bio_draw_low_quadruped(component, spec)
    elif family == "quadruped_robot":
        _bio_draw_quadruped_runner(component, spec)
    elif family == "serpentine_robot":
        _bio_draw_serpentine(component, spec)
    elif family == "aquatic_glider_robot":
        _bio_draw_aquatic_glider(component, spec)
    elif family == "winged_uav" or family == "biomorphic_micro_uav":
        _bio_draw_winged_uav(component, spec)
    elif family == "crustacean_walker":
        _bio_draw_crustacean(component, spec)
    elif family == "cephalopod_soft_robot":
        _bio_draw_soft_radial(component, spec)
    else:
        _bio_draw_from_spec_generic(component, spec)

    create_label(component, "Morphology: " + family, -130, 95, 8)
    create_label(component, "Bio source: " + source, -130, 110, 8)
    create_reference_note_label(component)


def build_generic_robotics(component):
    create_box(
        component,
        "generic_base_plate",
        get_param("base_length", 300),
        get_param("base_width", 200),
        get_param("plate_thickness", 4),
        0,
        0,
        0,
    )

    create_box(component, "compute_module_placeholder", 85, 56, 8, -40, 0, 4)
    create_box(component, "battery_placeholder", 95, 45, 25, 55, 0, 4)
    create_box(component, "sensor_module_placeholder", 40, 24, 22, 120, 0, 4)

    create_label(component, MODEL_NAME, -120, -85, 6)
    create_reference_note_label(component)


def run(context):
    ui = None

    try:
        app = adsk.core.Application.get()
        ui = app.userInterface

        design = app.activeProduct

        if not isinstance(design, adsk.fusion.Design):
            ui.messageBox("No active Fusion design found. Create or open a design first.")
            return

        root_comp = design.rootComponent
        model_component = root_comp

        if PROJECT_TYPE == "insect_robot":
            build_insect_robot(model_component)
        elif PROJECT_TYPE == "rover":
            build_rover(model_component)
        elif PROJECT_TYPE == "drone":
            build_drone(model_component)
        elif PROJECT_TYPE == "robot_arm":
            build_robot_arm(model_component)
        elif PROJECT_TYPE == "enclosure":
            build_enclosure(model_component)
        elif PROJECT_TYPE == "aquatic_glider_robot" and _has_assembly_spec():
            build_detailed_aquatic_glider(model_component)
        elif PROJECT_TYPE == "hybrid_biomorphic_drone" and _has_assembly_spec():
            build_detailed_hybrid_biomorphic_drone(model_component)
        elif PROJECT_TYPE == "biomorphic_rover" and _has_assembly_spec():
            build_detailed_biomorphic_rover(model_component)
        elif PROJECT_TYPE in (
            "wall_climbing_robot",
            "serpentine_robot",
            "aquatic_glider_robot",
            "winged_uav",
            "crustacean_walker",
            "cephalopod_soft_robot",
            "armored_rover",
            "jumping_robot",
            "biomorphic_micro_uav",
            "biomorphic_generic_robot",
            "hybrid_biomorphic_drone",
            "biomorphic_rover",
            "biomorphic_underwater_robot",
            "hybrid_biomorphic_walker",
        ):
            build_biomorphic_robot(model_component)
        else:
            build_generic_robotics(model_component)

        message = "OMNI Fusion 360 concept model generated: " + MODEL_NAME

        if CAD_REFERENCE_BRIEF:
            message += "\\n\\nCAD reference context was embedded in the generated script."

        ui.messageBox(message)

    except Exception:
        if ui:
            ui.messageBox("OMNI Fusion 360 script failed:\\n" + traceback.format_exc())


def stop(context):
    pass
'''


def generate_parameters_json(
    model_name: str,
    project_type: str,
    parameters: Dict[str, Any],
    mission_result: Dict[str, Any],
    cad_context: Dict[str, Any],
    cad_reference_brief: str = "",
) -> Dict[str, Any]:
    return {
        "model_name": model_name,
        "project_type": project_type,
        "units": "mm",
        "parameters": parameters,
        "cad_context": cad_context,
        "source_mission": mission_result.get("mission", ""),
        "cad_reference_brief": cad_reference_brief,
        "notes": [
            "Generated by OMNI Command.",
            "This is a concept-stage Fusion 360 script.",
            "Do not treat placeholder dimensions as manufacturing-ready.",
            "Confirm component dimensions, mounting hole placement, clearances, materials, and mechanical loads.",
            "CAD reference context is used as guidance unless the Fusion script explicitly imports a CAD file.",
        ],
    }


def generate_cad_readme(
    model_name: str,
    project_type: str,
    cad_reference_brief: str = "",
) -> str:
    reference_text = cad_reference_brief or "No CAD reference context was available."

    lines = [
        "# OMNI Fusion 360 CAD Export",
        "",
        "## Model",
        "",
        model_name,
        "",
        "## Project Type",
        "",
        project_type,
        "",
        "## Files",
        "",
        "- `fusion360_model_generator.py` — Fusion 360 Python script.",
        "- `fusion360_parameters.json` — Parameters used by the generated script.",
        "- `CAD_README.md` — This file.",
        "",
        "## CAD Reference Context",
        "",
        "```text",
        reference_text,
        "```",
        "",
        "## How to Run in Fusion 360",
        "",
        "1. Open Autodesk Fusion 360.",
        "2. Create a new design or open an existing design.",
        "3. Go to **Utilities** or **Tools**.",
        "4. Open **Scripts and Add-Ins**.",
        "5. Create a new Python script or open an existing script folder.",
        "6. Replace the script content with `fusion360_model_generator.py`.",
        "7. Run the script.",
        "8. Review the generated model.",
        "9. Edit parameters as needed and rerun.",
        "",
        "## Important Safety Notes",
        "",
        "This is a parametric concept model only.",
        "",
        "Before fabrication or hardware use, confirm:",
        "",
        "- Real component dimensions",
        "- Mounting hole locations",
        "- Screw sizes",
        "- Material thickness",
        "- Clearances",
        "- Cable routing",
        "- Battery placement",
        "- Weight distribution",
        "- Structural loads",
        "- Heat and airflow",
        "- Maintenance access",
        "- Sharp edges and pinch points",
        "",
        "## Recommended Next Step",
        "",
        "Use this generated model as the first Fusion 360 concept blockout. "
        "Then replace placeholders with measured components and verified mechanical constraints.",
        "",
    ]

    return "\n".join(lines)


def should_generate_fusion360_script(mission_result: Dict[str, Any]) -> bool:
    combined = mission_text(mission_result)

    keywords = [
        "fusion",
        "fusion 360",
        "cad",
        "3d model",
        "3d design",
        "chassis",
        "enclosure",
        "mount",
        "mechanical",
        "rover",
        "drone",
        "robot",
        "hexacopter",
        "quadcopter",
        "uav",
    ]

    return any(keyword in combined for keyword in keywords)


def generate_fusion360_export(
    mission_result: Dict[str, Any],
    output_root: Path,
) -> Dict[str, Any]:
    if not isinstance(mission_result, dict):
        raise ValueError("mission_result must be a dictionary.")

    output_root = Path(output_root)

    project_type = infer_project_type(mission_result)
    model_name = f"omni_{project_type}_fusion_concept"

    morphology_plan = extract_morphology_plan(mission_result)

    morphology_compiler_artifacts: Dict[str, Any] = {}
    morphology_compiler_error = ""

    assembly_spec = None
    assembly_spec_dict = None
    assembly_planner_error = ""

    if build_morphology_artifacts is not None:
        try:
            morphology_compiler_artifacts = build_morphology_artifacts(
                mission_text(mission_result)
            )
        except Exception as exc:
            morphology_compiler_error = str(exc)

    morphology_spec = (
        morphology_compiler_artifacts.get("morphology_spec", {})
        if isinstance(morphology_compiler_artifacts, dict)
        else {}
    )
    morphology_quality_gate = (
        morphology_compiler_artifacts.get("morphology_quality_gate", {})
        if isinstance(morphology_compiler_artifacts, dict)
        else {}
    )

    project_type = fusion_project_type_from_morphology(
        fallback_project_type=project_type,
        morphology_plan=morphology_plan,
    )

    model_name = model_name_from_morphology(
        fallback_model_name=model_name,
        morphology_plan=morphology_plan,
    )

    if morphology_spec:
        project_type = fusion_project_type_from_morphology_spec(
            fallback_project_type=project_type,
            morphology_spec=morphology_spec,
        )
        model_name = model_name_from_morphology_spec(
            fallback_model_name=model_name,
            morphology_spec=morphology_spec,
        )

    cad_context = build_cad_context(project_type, morphology_plan)

    if morphology_spec:
        # For data-driven biomorphic projects, avoid leaking old rover/drone
        # pattern-library guidance into the CAD reference brief.
        biomorphic_families = {
            "wall_climbing_robot",
            "serpentine_robot",
            "aquatic_glider_robot",
            "winged_uav",
            "crustacean_walker",
            "cephalopod_soft_robot",
            "armored_rover",
            "jumping_robot",
            "biomorphic_micro_uav",
            "biomorphic_generic_robot",
        }

        morphology_family = str(
            morphology_spec.get("morphology_family", "")
        ).lower().strip()

        if morphology_family in biomorphic_families:
            bio = morphology_spec.get("bio_inspiration", {}) or {}

            cad_context = {
                "project_type": project_type,
                "morphology_spec": morphology_spec,
                "recommended_features": (
                    list(morphology_spec.get("specialized_features", []) or [])
                    + list(morphology_spec.get("cad_rules", []) or [])
                ),
                "design_rules": [
                    "Use morphology_spec as the structured CAD morphology contract.",
                    "Respect morphology_spec body_posture, primary_segments, appendages, anchor_points, and vertical_structure.",
                    "Avoid all morphology_spec hard_negatives.",
                    f"Use biomorphic source creature: {bio.get('source_creature', 'unknown')}.",
                    f"Use morphology archetype: {morphology_spec.get('morphology_archetype', 'unknown')}.",
                ],
                "reference_lessons": [
                    "CAD Morphology Compiler context is active.",
                    "Biomorphic trait library context is active.",
                    "Generate creature-inspired robotic geometry from structured traits, not generic rover/drone defaults.",
                    "Creature-inspired features should remain mechanically interpretable, not purely decorative.",
                ],
                "default_dimensions_mm": {},
            }
        else:
            cad_context["morphology_spec"] = morphology_spec
            cad_context.setdefault("reference_lessons", []).append(
                "CAD Morphology Compiler context is active."
            )
            cad_context.setdefault("design_rules", []).extend(
                [
                    "Use morphology_spec as the structured CAD morphology contract.",
                    "Respect morphology_spec body_posture, primary_segments, appendages, anchor_points, and vertical_structure.",
                    "Avoid all morphology_spec hard_negatives.",
                ]
            )

    if morphology_quality_gate:
        cad_context["morphology_quality_gate"] = morphology_quality_gate
        cad_context.setdefault("design_rules", []).append(
            f"CAD morphology gate verdict: {morphology_quality_gate.get('verdict', 'UNKNOWN')}"
        )

    cad_reference_brief = cad_context_to_brief(cad_context)

    cad_artifact = extract_cad_artifact(mission_result)

    base_parameters = default_parameters(project_type)
    base_parameters.update(cad_context.get("default_dimensions_mm", {}))

    parameters = merge_parameters(base_parameters, cad_artifact)

    if project_type == "drone":
        parameters["rotor_count"] = infer_rotor_count(mission_result)

    if morphology_spec and plan_cad_detail_passes is not None and assembly_spec_to_dict is not None:
        try:
            detail_mission_text = str(
                mission_result.get("mission")
                or mission_result.get("mission_text")
                or mission_result.get("prompt")
                or mission_result.get("original_prompt")
                or mission_text
                or ""
            )

            assembly_spec = plan_cad_detail_passes(
                mission_text=detail_mission_text,
                morphology_spec=morphology_spec,
                project_type=project_type,
            )
            assembly_spec_dict = assembly_spec_to_dict(assembly_spec)
            parameters["assembly_spec"] = assembly_spec_dict

            cad_context.setdefault("reference_lessons", []).append(
                "Assembly detail planner context is active."
            )
            cad_context.setdefault("design_rules", []).append(
                "Use PARAMS['assembly_spec'] for detailed internal assembly layout when available."
            )
        except Exception as exc:
            assembly_planner_error = str(exc)
            assembly_spec = None
            assembly_spec_dict = None

    if morphology_spec:
        parameters["morphology_spec"] = morphology_spec

    if morphology_quality_gate:
        parameters["morphology_quality_gate"] = morphology_quality_gate

    fusion_dir = output_root / "generated_fusion360"
    fusion_dir.mkdir(parents=True, exist_ok=True)

    script_path = fusion_dir / "fusion360_model_generator.py"
    params_path = fusion_dir / "fusion360_parameters.json"
    readme_path = fusion_dir / "CAD_README.md"
    morphology_spec_path = fusion_dir / "morphology_spec.json"
    morphology_gate_path = fusion_dir / "morphology_quality_gate.json"
    assembly_spec_path = fusion_dir / "assembly_spec.json"

    script_content = generate_fusion360_script(
        model_name=model_name,
        project_type=project_type,
        parameters=parameters,
        cad_reference_brief=cad_reference_brief,
        morphology_id=(
            morphology_plan.get("morphology_id", "")
            or morphology_spec.get("morphology_family", "")
        ),
    )

    params_content = generate_parameters_json(
        model_name=model_name,
        project_type=project_type,
        parameters=parameters,
        mission_result=mission_result,
        cad_context=cad_context,
        cad_reference_brief=cad_reference_brief,
    )

    readme_content = generate_cad_readme(
        model_name=model_name,
        project_type=project_type,
        cad_reference_brief=cad_reference_brief,
    )

    script_path.write_text(script_content, encoding="utf-8")
    params_path.write_text(json.dumps(params_content, indent=2), encoding="utf-8")
    readme_path.write_text(readme_content, encoding="utf-8")

    if morphology_spec:
        morphology_spec_path.write_text(
            json.dumps(morphology_spec, indent=2),
            encoding="utf-8",
        )

    if morphology_quality_gate:
        morphology_gate_path.write_text(
            json.dumps(morphology_quality_gate, indent=2),
            encoding="utf-8",
        )

    if assembly_spec_dict:
        assembly_spec_path.write_text(
            json.dumps(assembly_spec_dict, indent=2),
            encoding="utf-8",
        )

    files = [
        str(script_path.relative_to(output_root)),
        str(params_path.relative_to(output_root)),
        str(readme_path.relative_to(output_root)),
    ]

    if morphology_spec:
        files.append(str(morphology_spec_path.relative_to(output_root)))

    if morphology_quality_gate:
        files.append(str(morphology_gate_path.relative_to(output_root)))

    if assembly_spec_dict:
        files.append(str(assembly_spec_path.relative_to(output_root)))

    return {
        "status": "generated",
        "model_name": model_name,
        "project_type": project_type,
        "fusion_dir": str(fusion_dir),
        "files": files,
        "file_count": len(files),
        "cad_reference_context_available": bool(cad_reference_brief),
        "morphology_compiler_available": bool(morphology_spec),
        "morphology_gate_verdict": (
            morphology_quality_gate.get("verdict")
            if isinstance(morphology_quality_gate, dict)
            else None
        ),
        "morphology_gate_score": (
            morphology_quality_gate.get("overall_score")
            if isinstance(morphology_quality_gate, dict)
            else None
        ),
        "morphology_compiler_error": morphology_compiler_error or None,
        "assembly_detail_available": bool(assembly_spec_dict),
        "assembly_detail_level": (
            assembly_spec_dict.get("detail_level")
            if isinstance(assembly_spec_dict, dict)
            else None
        ),
        "assembly_visibility_mode": (
            assembly_spec_dict.get("visibility_mode")
            if isinstance(assembly_spec_dict, dict)
            else None
        ),
        "assembly_component_count": (
            assembly_spec_dict.get("component_count")
            if isinstance(assembly_spec_dict, dict)
            else None
        ),
        "assembly_structural_feature_count": (
            assembly_spec_dict.get("structural_feature_count")
            if isinstance(assembly_spec_dict, dict)
            else None
        ),
        "assembly_planner_error": assembly_planner_error or None,
        "morphology_family": (
            morphology_spec.get("morphology_family")
            if isinstance(morphology_spec, dict)
            else None
        ),
        "morphology_archetype": (
            morphology_spec.get("morphology_archetype")
            if isinstance(morphology_spec, dict)
            else None
        ),
        "bio_inspiration": (
            morphology_spec.get("bio_inspiration")
            if isinstance(morphology_spec, dict)
            else None
        ),
        "rotor_count": parameters.get("rotor_count") if project_type == "drone" else None,
    }
