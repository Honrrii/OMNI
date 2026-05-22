"""
OMNI CAD Morphology Planner.

Converts a natural-language mission prompt into a structured MorphologySpec.
This layer sits between the mission text and the Fusion 360 / CadQuery generator.

Design rules:
- Pure keyword-based inference. No LLM calls.
- Deterministic: same input -> same output.
- Additive: existing drone/rover paths are unchanged.
- Geometry values are concept-stage defaults, not manufacturing specs.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional

try:
    from .cad_morphology_ir import (
        Appendage,
        AnchorPoint,
        BodySegment,
        MorphologySpec,
        VerticalStructure,
    )
except ImportError:  # Allows direct script execution from this folder.
    from cad_morphology_ir import (  # type: ignore
        Appendage,
        AnchorPoint,
        BodySegment,
        MorphologySpec,
        VerticalStructure,
    )



# ─────────────────────────────────────────────────────────────
# Biomorphic trait library
# ─────────────────────────────────────────────────────────────
try:
    from .biomorphic_trait_library import infer_biomorphic_hints
except ImportError:
    try:
        from biomorphic_trait_library import infer_biomorphic_hints
    except ImportError:
        infer_biomorphic_hints = None


def _contains(text: str, keywords: List[str]) -> bool:
    t = text.lower()
    return any(kw in t for kw in keywords)


def _extract_keywords(text: str, keyword_list: List[str]) -> List[str]:
    t = text.lower()
    return [kw for kw in keyword_list if kw in t]


def _explicit_hexapod(text: str) -> bool:
    return _contains(text, ["hexapod", "six-legged", "six legged", "6-leg", "6 leg", "6leg"])


def _explicit_quadruped(text: str) -> bool:
    return _contains(text, ["quadruped", "four-legged", "four legged", "4-leg", "4 leg", "4leg"])


def _explicit_octopod(text: str) -> bool:
    return _contains(text, ["octopod", "eight-legged", "eight legged", "8-leg", "8 leg", "8leg"])


def _insectoid_keywords(text: str) -> bool:
    return _contains(
        text,
        [
            "insect",
            "insect-inspired",
            "beetle",
            "ant",
            "bug",
            "spider",
            "arachnid",
            "biomorphic",
            "bio-inspired",
            "biomimetic",
            "crawler",
        ],
    )


def _detect_leg_count(text: str) -> int:
    """Detect explicit leg count from mission text. Returns 0 when unknown."""
    t = text.lower()
    if _explicit_octopod(t) or _contains(t, ["spider", "arachnid"]):
        return 8
    if _explicit_hexapod(t):
        return 6
    if _explicit_quadruped(t):
        return 4
    if _contains(t, ["biped", "two-legged", "two legged", "2-leg", "2 leg", "bipedal"]):
        return 2
    if _contains(t, ["insect", "beetle", "ant", "bug"]):
        return 6
    return 0


def _detect_family(text: str) -> str:
    """Primary morphology family detection.

    Important: explicit morphology words win over generic leg count. This prevents
    an insect-inspired robot from being mislabeled as a generic hexapod simply
    because insects use six legs.
    """
    t = text.lower()

    # Aerial vehicles are preserved as drone morphology, even if the name is biomimetic.
    if _contains(t, ["drone", "quadcopter", "hexacopter", "uav", "fpv", "propeller", "rotor"]):
        return "aerial_drone"

    # Ground vehicles before generic robot matching.
    if _contains(t, ["tracked", "tracks", "tank-style", "tank style"]):
        return "tracked_rover"
    if _contains(t, ["rover", "wheeled", "wheel", "mobile robot"]):
        return "wheeled_rover"

    # Manipulator / stationary systems.
    if _contains(t, ["robot arm", "manipulator", "gripper", "end effector", "end-effector"]):
        return "manipulator_arm"
    if _contains(t, ["sensor pod", "sensor station", "stationary sensor", "monitoring station"]):
        return "sensor_pod"

    # Explicit legged families.
    if _explicit_hexapod(t):
        return "hexapod_robot"
    if _explicit_quadruped(t):
        return "quadruped_robot"

    # Sci-fi walker/mech without explicit hexapod/quadruped.
    if _contains(t, ["sci-fi", "scifi", "sci fi", "mech", "exosuit", "walker", "strider", "bipedal walker", "humanoid"]):
        return "sci_fi_walker"

    # Biologically inspired walking robots.
    if _insectoid_keywords(t):
        return "insectoid_legged_robot"

    leg_count = _detect_leg_count(t)
    if leg_count == 6:
        return "hexapod_robot"
    if leg_count == 4:
        return "quadruped_robot"
    if leg_count > 0 or _contains(t, ["legged", "walking robot", "walking"]):
        return "insectoid_legged_robot"

    return "generic_robotic_platform"


def _resolved_legged_family(text: str, leg_count: int, family_hint: Optional[str]) -> str:
    if family_hint:
        return family_hint
    t = text.lower()
    if _explicit_hexapod(t):
        return "hexapod_robot"
    if _explicit_quadruped(t) or leg_count == 4:
        return "quadruped_robot"
    if _contains(t, ["sci-fi", "scifi", "sci fi", "mech", "walker", "strider"]):
        return "sci_fi_walker"
    return "insectoid_legged_robot"


def _build_legged_platform(
    text: str,
    leg_count: int = 6,
    family_hint: Optional[str] = None,
) -> MorphologySpec:
    """Build insectoid / hexapod / quadruped walking morphology."""
    if leg_count <= 0:
        leg_count = 6
    if leg_count % 2 != 0:
        leg_count += 1  # Keep bilateral pair symmetry.

    resolved_family = _resolved_legged_family(text, leg_count, family_hint)
    is_quadruped = resolved_family == "quadruped_robot"

    body_elev = 50.0 if not is_quadruped else 58.0

    abdomen = BodySegment(
        name="abdomen" if not is_quadruped else "rear_body",
        length_mm=70,
        width_mm=45,
        height_mm=22,
        z_base_mm=body_elev,
        label="Abdomen" if not is_quadruped else "Rear Body",
        notes="Rear body segment. Houses battery and main electronics bay.",
    )
    thorax = BodySegment(
        name="thorax" if not is_quadruped else "main_body",
        length_mm=55 if not is_quadruped else 90,
        width_mm=50,
        height_mm=20,
        z_base_mm=body_elev + 4,
        label="Thorax" if not is_quadruped else "Main Body",
        notes="Central body. Leg attachment points along sides. Compute board mounts here.",
    )
    head = BodySegment(
        name="head",
        length_mm=30,
        width_mm=34,
        height_mm=18,
        z_base_mm=body_elev + 8,
        label="Head / Sensor Module",
        notes="Front sensor module. Camera, ultrasonic, or IMU mount.",
    )

    legs_per_side = max(1, leg_count // 2)
    thorax_y_half = thorax.length_mm / 2
    attach_z = body_elev + thorax.height_mm * 0.3
    appendages: List[Appendage] = []
    anchor_points: List[AnchorPoint] = []

    if legs_per_side == 1:
        side_angles = [90.0]
    elif legs_per_side == 2:
        side_angles = [112.0, 68.0]
    elif legs_per_side == 3:
        side_angles = [122.0, 90.0, 58.0]
    elif legs_per_side == 4:
        side_angles = [132.0, 106.0, 74.0, 48.0]
    else:
        step = 84.0 / max(legs_per_side - 1, 1)
        side_angles = [132.0 - i * step for i in range(legs_per_side)]

    y_positions = [
        thorax_y_half * (0.65 - i * (1.3 / max(legs_per_side - 1, 1)))
        for i in range(legs_per_side)
    ]

    tilt_deg = 38.0 if not is_quadruped else 42.0
    leg_length = max(attach_z / math.sin(math.radians(tilt_deg)), 55.0)

    for i, (y_pos, angle) in enumerate(zip(y_positions, side_angles)):
        for side, x_sign, side_name in [("L", 1, "Left"), ("R", -1, "Right")]:
            mirror_angle = angle if side == "L" else 180.0 - angle
            appendages.append(
                Appendage(
                    name=f"leg_{side}{i + 1}",
                    appendage_type="leg",
                    attach_x_mm=x_sign * thorax.width_mm / 2,
                    attach_y_mm=y_pos,
                    attach_z_mm=attach_z,
                    angle_deg=mirror_angle,
                    tilt_deg=tilt_deg,
                    length_mm=round(leg_length, 1),
                    width_mm=7 if not is_quadruped else 10,
                    height_mm=7 if not is_quadruped else 9,
                    ground_contact=True,
                    foot_radius_mm=5 if not is_quadruped else 7,
                    notes=f"{side_name} leg {i + 1}. Angled downward toward ground plane.",
                )
            )
            anchor_points.append(
                AnchorPoint(
                    name=f"thorax_anchor_{side}{i + 1}",
                    x_mm=x_sign * thorax.width_mm / 2,
                    y_mm=y_pos,
                    z_mm=attach_z,
                    purpose=f"{side_name} leg {i + 1} mount",
                )
            )

    appendages.append(
        Appendage(
            name="sensor_stalk",
            appendage_type="sensor_stalk",
            attach_x_mm=0,
            attach_y_mm=head.length_mm / 2,
            attach_z_mm=body_elev + head.height_mm + 8,
            angle_deg=90.0,
            tilt_deg=-15.0,
            length_mm=20,
            width_mm=8,
            height_mm=8,
            ground_contact=False,
            notes="Camera / sensor mount at head tip.",
        )
    )

    if resolved_family == "hexapod_robot":
        silhouette = "raised-hexapod-inspection-platform"
        notes = "Hexapod robot. Six legs, bilateral symmetry, elevated body."
    elif resolved_family == "quadruped_robot":
        silhouette = "raised-quadruped-robotic-platform"
        notes = "Quadruped robot. Four legs, bilateral symmetry, elevated body."
    else:
        silhouette = "segmented-biological-mechanical"
        notes = f"Insectoid legged robot. {leg_count} legs, bilateral symmetry, elevated body."

    return MorphologySpec(
        morphology_family=resolved_family,
        body_posture="standing",
        silhouette=silhouette,
        symmetry_strategy="bilateral",
        primary_segments=[abdomen, thorax, head],
        appendages=appendages,
        appendage_count=len(appendages),
        anchor_points=anchor_points,
        vertical_structure=VerticalStructure(
            leg_ground_clearance_mm=body_elev * 0.6,
            body_elevation_mm=body_elev,
            legs_extend_downward=True,
            body_elevated_above_ground=True,
            use_segmented_z_heights=True,
            notes="Head/thorax/abdomen use different Z heights to avoid flat-plate fallback.",
        ),
        fabrication_hints=[
            "Start with FDM prototype at 0.2mm layer height.",
            "Print thorax/abdomen separately and assemble for easier access.",
            "Legs may need support structures if tilt exceeds 45 degrees.",
            "Foot contact pads should be rubber or TPU for grip.",
        ],
        allowed_primitive_shapes=["box", "cylinder", "sphere", "chamfered_box", "tapered_box"],
        hard_negatives=[
            "radial quadcopter arm layout",
            "flat single-plane body",
            "all components centered on XY plane at z=0",
            "drone motor mounts on arm tips",
            "propeller clearance disks",
            "legs floating without ground contact",
            "single circular body without segmentation",
        ],
        quality_checklist=[
            "body has at least 2 distinct Z heights",
            f"at least {leg_count} legs defined",
            "all legs have ground_contact=True",
            "leg attach points are on body sides (non-zero X)",
            "head segment is higher than rear body",
            "no hard-negative shapes in output",
            "sensor stalk or camera mount present",
        ],
        source_mission_keywords=_extract_keywords(
            text,
            [
                "insect",
                "beetle",
                "ant",
                "spider",
                "hexapod",
                "quadruped",
                "legged",
                "walking",
                "biomorphic",
                "exploration",
                "crawler",
            ],
        ),
        notes=notes,
    )


def _build_sci_fi_walker(text: str) -> MorphologySpec:
    """Build sci-fi / mech walker morphology."""
    leg_count = _detect_leg_count(text) or 4
    if leg_count % 2 != 0:
        leg_count += 1
    body_elev = 80.0

    pelvis = BodySegment(
        name="pelvis",
        length_mm=60,
        width_mm=55,
        height_mm=18,
        z_base_mm=body_elev - 10,
        label="Pelvis / Hip Plate",
        notes="Hip connection point. Leg pivots attach here.",
    )
    torso = BodySegment(
        name="torso",
        length_mm=80,
        width_mm=60,
        height_mm=35,
        z_base_mm=body_elev,
        label="Main Torso",
        notes="Central armored torso. Houses compute, power, and main actuator controllers.",
    )
    sensor_head = BodySegment(
        name="sensor_head",
        length_mm=35,
        width_mm=30,
        height_mm=28,
        z_base_mm=body_elev + torso.height_mm + 8,
        label="Sensor Head",
        notes="Elevated sensor cluster. Camera array, LIDAR, or multi-spectral sensor.",
    )

    appendages: List[Appendage] = []
    anchor_points: List[AnchorPoint] = []
    legs_per_side = max(1, leg_count // 2)
    attach_z = body_elev - 5.0
    tilt_deg = 42.0
    leg_length = max((body_elev + 10) / math.sin(math.radians(tilt_deg)), 80.0)
    side_angles = [120.0, 95.0, 70.0, 45.0][:legs_per_side]
    if len(side_angles) < legs_per_side:
        side_angles = [120.0 - i * (75.0 / max(legs_per_side - 1, 1)) for i in range(legs_per_side)]
    y_positions = [30.0 - i * (60.0 / max(legs_per_side - 1, 1)) for i in range(legs_per_side)]

    for i, (y_pos, angle) in enumerate(zip(y_positions, side_angles)):
        for side, x_sign, side_name in [("L", 1, "Left"), ("R", -1, "Right")]:
            mirror_angle = angle if side == "L" else 180.0 - angle
            appendages.append(
                Appendage(
                    name=f"leg_{side}{i + 1}",
                    appendage_type="leg",
                    attach_x_mm=x_sign * pelvis.width_mm / 2,
                    attach_y_mm=y_pos,
                    attach_z_mm=attach_z,
                    angle_deg=mirror_angle,
                    tilt_deg=tilt_deg,
                    length_mm=round(leg_length, 1),
                    width_mm=12,
                    height_mm=10,
                    ground_contact=True,
                    foot_radius_mm=7,
                    notes=f"{side_name} leg {i + 1}, armored sci-fi style.",
                )
            )
            anchor_points.append(
                AnchorPoint(
                    name=f"hip_anchor_{side}{i + 1}",
                    x_mm=x_sign * pelvis.width_mm / 2,
                    y_mm=y_pos,
                    z_mm=attach_z,
                    purpose=f"{side_name} hip/leg pivot",
                )
            )

    for side, x_sign in [("L", 1), ("R", -1)]:
        appendages.append(
            Appendage(
                name=f"shoulder_pod_{side}",
                appendage_type="sensor_stalk",
                attach_x_mm=x_sign * (torso.width_mm / 2 + 8),
                attach_y_mm=10,
                attach_z_mm=body_elev + torso.height_mm * 0.7,
                angle_deg=90.0 * x_sign,
                tilt_deg=0.0,
                length_mm=22,
                width_mm=14,
                height_mm=10,
                ground_contact=False,
                notes=f"Shoulder sensor / tool pod ({side} side).",
            )
        )

    return MorphologySpec(
        morphology_family="sci_fi_walker",
        body_posture="standing",
        silhouette="angular-armored-sci-fi",
        symmetry_strategy="bilateral",
        primary_segments=[pelvis, torso, sensor_head],
        appendages=appendages,
        appendage_count=len(appendages),
        anchor_points=anchor_points,
        vertical_structure=VerticalStructure(
            leg_ground_clearance_mm=body_elev * 0.5,
            body_elevation_mm=body_elev,
            legs_extend_downward=True,
            body_elevated_above_ground=True,
            use_segmented_z_heights=True,
            notes="High stance, multi-segment torso, raised sensor head.",
        ),
        fabrication_hints=[
            "Intended as a concept model, not a functional prototype.",
            "Use chamfered/beveled edges for sci-fi panel aesthetic.",
            "Separate torso and pelvis components for assembly access.",
        ],
        allowed_primitive_shapes=["box", "chamfered_box", "cylinder", "wedge"],
        hard_negatives=[
            "flat pancake body",
            "radial quadcopter layout",
            "single circular body",
            "drone arm geometry",
            "propeller disks",
        ],
        quality_checklist=[
            "pelvis, torso, and sensor head at distinct Z heights",
            f"at least {leg_count} legs with ground contact",
            "shoulder pods or upper-body appendages present",
            "sensor head elevated above torso",
            "no drone/flat-plate fallback geometry",
        ],
        source_mission_keywords=_extract_keywords(
            text,
            ["sci-fi", "scifi", "mech", "walker", "armored", "angular", "futuristic"],
        ),
        notes=f"Sci-fi walker. {leg_count} legs. Armored angular silhouette.",
    )


def _build_wheeled_rover(text: str) -> MorphologySpec:
    wheel_appendages = []
    for name, x, y in [
        ("wheel_front_left", 120, 80),
        ("wheel_front_right", 120, -80),
        ("wheel_rear_left", -120, 80),
        ("wheel_rear_right", -120, -80),
    ]:
        wheel_appendages.append(
            Appendage(
                name=name,
                appendage_type="wheel",
                attach_x_mm=x,
                attach_y_mm=y,
                attach_z_mm=18,
                angle_deg=0,
                tilt_deg=0,
                length_mm=40,
                width_mm=20,
                height_mm=40,
                ground_contact=True,
                notes="Wheel placeholder / drive module.",
            )
        )
    return MorphologySpec(
        morphology_family="wheeled_rover",
        body_posture="low_slung",
        silhouette="flat-chassis-with-mast",
        symmetry_strategy="bilateral",
        primary_segments=[BodySegment("chassis_plate", 300, 200, 8, 25, "Main Chassis Plate")],
        appendages=wheel_appendages,
        appendage_count=len(wheel_appendages),
        vertical_structure=VerticalStructure(
            leg_ground_clearance_mm=30,
            body_elevation_mm=25,
            legs_extend_downward=False,
            body_elevated_above_ground=False,
            use_segmented_z_heights=False,
            notes="Low-slung wheeled rover chassis.",
        ),
        fabrication_hints=["FDM chassis plate from PLA or PETG.", "Use standoffs for electronics boards."],
        allowed_primitive_shapes=["box", "cylinder"],
        hard_negatives=["legs without ground contact", "radial quadcopter arm layout"],
        quality_checklist=["chassis plate present", "4 wheel placeholders", "battery bay near center", "no legged-robot morphology"],
        notes="Wheeled rover. Flat chassis, differential/skid drive placeholder.",
    )


def _build_tracked_rover(text: str) -> MorphologySpec:
    return MorphologySpec(
        morphology_family="tracked_rover",
        body_posture="low_slung",
        silhouette="low-armored-tracked",
        symmetry_strategy="bilateral",
        primary_segments=[
            BodySegment("hull", 280, 160, 45, 20, "Main Hull", "Houses electronics above track level."),
            BodySegment("track_left", 280, 35, 30, 0, "Left Track Housing"),
            BodySegment("track_right", 280, 35, 30, 0, "Right Track Housing"),
        ],
        appendage_count=0,
        vertical_structure=VerticalStructure(
            leg_ground_clearance_mm=20,
            body_elevation_mm=20,
            legs_extend_downward=False,
            body_elevated_above_ground=True,
            use_segmented_z_heights=True,
            notes="Hull elevated above track housings.",
        ),
        fabrication_hints=[
            "Tracks can be approximated as extruded rectangular housings at concept stage.",
            "Hull can be printed separately from track modules.",
        ],
        allowed_primitive_shapes=["box", "cylinder", "chamfered_box"],
        hard_negatives=["radial arm layout", "legged gait geometry"],
        quality_checklist=["hull present and elevated", "two track housings", "no legs / radial arms"],
        notes="Tracked rover. Low-slung hull, two track housings.",
    )


def _build_aerial_drone(text: str) -> MorphologySpec:
    appendages = []
    for i, angle in enumerate([45, 135, 225, 315], start=1):
        appendages.append(
            Appendage(
                name=f"rotor_arm_{i}",
                appendage_type="rotor_arm",
                attach_x_mm=0,
                attach_y_mm=0,
                attach_z_mm=10,
                angle_deg=angle,
                tilt_deg=0,
                length_mm=95,
                width_mm=12,
                height_mm=8,
                ground_contact=False,
                notes="Quadcopter arm with motor mount placeholder.",
            )
        )
    return MorphologySpec(
        morphology_family="aerial_drone",
        body_posture="aerial",
        silhouette="radial-symmetric-drone",
        symmetry_strategy="radial_n",
        primary_segments=[BodySegment("central_body", 140, 140, 24, 0, "Central Body Plate")],
        appendages=appendages,
        appendage_count=len(appendages),
        vertical_structure=VerticalStructure(
            leg_ground_clearance_mm=0,
            body_elevation_mm=0,
            legs_extend_downward=False,
            body_elevated_above_ground=False,
            use_segmented_z_heights=False,
            notes="Aerial vehicle. No ground contact during flight.",
        ),
        fabrication_hints=["Use carbon fiber or aluminum for arms if weight is critical.", "Flight controller centered on body plate."],
        allowed_primitive_shapes=["box", "cylinder", "thin_disk"],
        hard_negatives=["walking legs", "ground contact appendages", "tracked rover hull"],
        quality_checklist=["central body present", "radial arms with motor mounts", "propeller clearance disks", "battery and flight controller placement"],
        notes="Aerial drone. Radial symmetry. No legs.",
    )


def _build_manipulator_arm(text: str) -> MorphologySpec:
    return MorphologySpec(
        morphology_family="manipulator_arm",
        body_posture="mounted",
        silhouette="articulated-arm-chain",
        symmetry_strategy="none",
        primary_segments=[
            BodySegment("base", 110, 110, 28, 0, "Base Rotation Platform"),
            BodySegment("upper_link", 120, 26, 18, 28, "Upper Link"),
            BodySegment("forearm_link", 110, 22, 16, 62, "Forearm Link"),
            BodySegment("wrist", 30, 22, 14, 95, "Wrist"),
        ],
        appendage_count=1,
        vertical_structure=VerticalStructure(0, 0, False, False, True, "Arm extends upward/outward from base."),
        fabrication_hints=["Each link is a separate printable component.", "Joints need clearance for servo flanges."],
        allowed_primitive_shapes=["box", "cylinder"],
        hard_negatives=["walking legs", "drone arms", "flat rover plate layout"],
        quality_checklist=["base, upper link, forearm, wrist present", "joints between links", "end effector placeholder"],
        notes="Manipulator arm. Articulated chain of links.",
    )


def _build_sensor_pod(text: str) -> MorphologySpec:
    return MorphologySpec(
        morphology_family="sensor_pod",
        body_posture="mounted",
        silhouette="compact-pod",
        symmetry_strategy="radial_n",
        primary_segments=[
            BodySegment("pod_body", 80, 80, 60, 0, "Sensor Pod Body"),
            BodySegment("sensor_head", 50, 50, 30, 60, "Sensor Array Head"),
        ],
        appendage_count=0,
        vertical_structure=VerticalStructure(0, 0, False, False, True, "Vertically stacked pod and sensor head."),
        fabrication_hints=["Single-print enclosure at concept stage."],
        allowed_primitive_shapes=["cylinder", "box"],
        hard_negatives=["walking legs", "wheels", "propellers"],
        quality_checklist=["pod body and sensor head present", "mounting interface on base"],
        notes="Stationary sensor pod.",
    )


def _build_generic(text: str) -> MorphologySpec:
    return MorphologySpec(
        morphology_family="generic_robotic_platform",
        body_posture="flat",
        silhouette="generic-plate",
        symmetry_strategy="bilateral",
        primary_segments=[BodySegment("base_plate", 300, 200, 4, 0, "Base Plate")],
        appendage_count=0,
        vertical_structure=VerticalStructure(0, 0, False, False, False),
        fabrication_hints=["Define more requirements before finalizing morphology."],
        allowed_primitive_shapes=["box", "cylinder"],
        hard_negatives=[],
        quality_checklist=["base plate present"],
        notes="Generic platform. Mission did not match a specific morphology family.",
    )



# ─────────────────────────────────────────────────────────────
# Biomorphic / creature-inspired builder
# ─────────────────────────────────────────────────────────────

def _segment_dimensions_for_biomorph(name: str, posture: str, index: int) -> tuple[float, float, float, float]:
    n = str(name or "").lower()

    if posture == "standing":
        base_z = 45.0 + index * 4.0
    elif posture in ("low_slung", "crouched"):
        base_z = 12.0 + index * 2.0
    elif posture == "segmented_chain":
        base_z = 8.0
    elif posture in ("aquatic", "aerial"):
        base_z = 0.0
    elif posture == "soft_radial":
        base_z = 12.0
    else:
        base_z = 10.0 + index * 2.0

    if "head" in n or "sensor" in n:
        return 35.0, 32.0, 20.0, base_z + 6.0
    if "tail" in n:
        return 65.0, 14.0, 12.0, base_z
    if "torso" in n or "body" in n or "chassis" in n or "shell" in n or "fuselage" in n:
        return 90.0, 48.0, 24.0, base_z
    if "hip" in n or "pelvis" in n:
        return 55.0, 42.0, 18.0, base_z - 2.0
    if "wing" in n or "fin" in n:
        return 85.0, 16.0, 4.0, base_z
    if "module" in n:
        return 42.0, 26.0, 22.0, base_z
    if "leg" in n or "limb" in n:
        return 55.0, 10.0, 8.0, base_z

    return 70.0, 36.0, 18.0, base_z


def _build_biomorphic_appendages(
    hints: Dict[str, Any],
    body_width_mm: float,
    body_length_mm: float,
    base_z_mm: float,
) -> tuple[List[Appendage], List[AnchorPoint]]:
    robot_family = str(hints.get("robot_family", "") or "").lower()
    posture = str(hints.get("body_posture", "") or "").lower()
    appendage_count = int(hints.get("appendage_count", 0) or 0)

    appendages: List[Appendage] = []
    anchors: List[AnchorPoint] = []

    if appendage_count <= 0:
        return appendages, anchors

    if robot_family in ("aquatic_glider_robot", "winged_uav", "biomorphic_micro_uav"):
        kind = "fin" if robot_family == "aquatic_glider_robot" else "wing"

        if robot_family == "biomorphic_micro_uav":
            y_positions = [body_length_mm * 0.18, -body_length_mm * 0.18]
            for i, y in enumerate(y_positions):
                for side, x_sign in [("L", 1), ("R", -1)]:
                    name = f"{kind}_{side}{i+1}"
                    appendages.append(Appendage(
                        name=name,
                        appendage_type=kind,
                        attach_x_mm=x_sign * body_width_mm / 2,
                        attach_y_mm=y,
                        attach_z_mm=base_z_mm + 12,
                        angle_deg=90.0 if x_sign > 0 else 270.0,
                        tilt_deg=0.0,
                        length_mm=70.0,
                        width_mm=8.0,
                        height_mm=3.0,
                        ground_contact=False,
                        notes=f"Biomorphic {kind} inspired by {hints.get('source_creature', 'creature')}.",
                    ))
                    anchors.append(AnchorPoint(
                        name=f"{name}_anchor",
                        x_mm=x_sign * body_width_mm / 2,
                        y_mm=y,
                        z_mm=base_z_mm + 12,
                        purpose=f"{kind} mount",
                    ))
            return appendages, anchors

        for side, x_sign in [("L", 1), ("R", -1)]:
            name = f"{kind}_{side}"
            appendages.append(Appendage(
                name=name,
                appendage_type=kind,
                attach_x_mm=x_sign * body_width_mm / 2,
                attach_y_mm=0.0,
                attach_z_mm=base_z_mm + 8,
                angle_deg=90.0 if x_sign > 0 else 270.0,
                tilt_deg=0.0,
                length_mm=90.0,
                width_mm=14.0,
                height_mm=4.0,
                ground_contact=False,
                notes=f"Large lateral {kind} surface inspired by {hints.get('source_creature', 'creature')}.",
            ))
            anchors.append(AnchorPoint(
                name=f"{name}_anchor",
                x_mm=x_sign * body_width_mm / 2,
                y_mm=0.0,
                z_mm=base_z_mm + 8,
                purpose=f"{kind} mount",
            ))

        return appendages, anchors

    if robot_family == "cephalopod_soft_robot" or posture == "soft_radial":
        for i in range(appendage_count):
            angle = i * (360.0 / appendage_count)
            appendages.append(Appendage(
                name=f"soft_arm_{i+1}",
                appendage_type="arm",
                attach_x_mm=0.0,
                attach_y_mm=0.0,
                attach_z_mm=base_z_mm + 8,
                angle_deg=angle,
                tilt_deg=10.0,
                length_mm=65.0,
                width_mm=7.0,
                height_mm=7.0,
                ground_contact=False,
                notes="Flexible radial arm / manipulator.",
            ))
        return appendages, anchors

    legs_per_side = max(1, appendage_count // 2)
    if legs_per_side == 1:
        y_positions = [0.0]
    else:
        y_positions = [
            body_length_mm * (0.35 - i * (0.7 / max(legs_per_side - 1, 1)))
            for i in range(legs_per_side)
        ]

    ground_contact = posture not in ("aerial", "aquatic", "soft_radial")
    attach_z = base_z_mm + 8.0
    tilt_deg = 35.0 if posture == "standing" else 20.0

    for i, y in enumerate(y_positions):
        for side, x_sign in [("L", 1), ("R", -1)]:
            name = f"leg_{side}{i+1}"
            appendages.append(Appendage(
                name=name,
                appendage_type="leg",
                attach_x_mm=x_sign * body_width_mm / 2,
                attach_y_mm=y,
                attach_z_mm=attach_z,
                angle_deg=95.0 if x_sign > 0 else 265.0,
                tilt_deg=tilt_deg,
                length_mm=58.0 if posture != "low_slung" else 38.0,
                width_mm=8.0,
                height_mm=8.0,
                ground_contact=ground_contact,
                foot_radius_mm=6.0,
                notes=f"Creature-inspired limb from {hints.get('source_creature', 'creature')} morphology.",
            ))
            anchors.append(AnchorPoint(
                name=f"{name}_anchor",
                x_mm=x_sign * body_width_mm / 2,
                y_mm=y,
                z_mm=attach_z,
                purpose="creature-inspired limb mount",
            ))

    return appendages[:appendage_count], anchors[:appendage_count]


def _build_biomorphic_from_hints(text: str, hints: Dict[str, Any]) -> MorphologySpec:
    source_creature = str(hints.get("source_creature", "") or "unknown_creature")
    robot_family = str(hints.get("robot_family", "") or "biomorphic_generic_robot")
    posture = str(hints.get("body_posture", "") or "standing")
    archetype = str(hints.get("morphology_archetype", "") or "")
    symmetry = str(hints.get("symmetry", "") or "bilateral")
    body_segment_names = list(hints.get("body_segments", []) or ["body"])

    primary_segments: List[BodySegment] = []
    for index, seg_name in enumerate(body_segment_names):
        length, width, height, z_base = _segment_dimensions_for_biomorph(seg_name, posture, index)
        primary_segments.append(BodySegment(
            name=str(seg_name),
            length_mm=length,
            width_mm=width,
            height_mm=height,
            z_base_mm=z_base,
            label=str(seg_name).replace("_", " ").title(),
            notes=f"Biomorphic segment inspired by {source_creature}.",
        ))

    body_width = max((s.width_mm for s in primary_segments), default=48.0)
    body_length = max((s.length_mm for s in primary_segments), default=90.0)
    base_z = min((s.z_base_mm for s in primary_segments), default=10.0)

    appendages, anchors = _build_biomorphic_appendages(
        hints=hints,
        body_width_mm=body_width,
        body_length_mm=body_length,
        base_z_mm=base_z,
    )

    body_elevated = posture in ("standing", "crouched")
    use_z = len({round(s.z_base_mm, 1) for s in primary_segments}) > 1

    specialized_features = list(hints.get("specialized_features", []) or [])
    cad_rules = list(hints.get("cad_rules", []) or [])
    hard_negatives = list(hints.get("hard_negatives", []) or [])

    quality_items = [
        f"bio inspiration captured: {source_creature}",
        f"morphology archetype: {archetype}",
        f"robot family: {robot_family}",
        "specialized creature features included",
        "CAD rules provided from biomorphic trait library",
        f"{len(primary_segments)} body segments defined",
    ]
    if appendages:
        quality_items.append(f"{len(appendages)} appendages defined from creature topology")

    return MorphologySpec(
        morphology_family=robot_family,
        body_posture=posture,
        silhouette=f"{source_creature}-inspired {archetype or robot_family}",
        symmetry_strategy=symmetry,
        primary_segments=primary_segments,
        appendages=appendages,
        appendage_count=len(appendages),
        anchor_points=anchors,
        vertical_structure=VerticalStructure(
            leg_ground_clearance_mm=25.0 if body_elevated else 8.0,
            body_elevation_mm=base_z,
            legs_extend_downward=any(a.appendage_type == "leg" for a in appendages),
            body_elevated_above_ground=body_elevated,
            use_segmented_z_heights=use_z,
            notes=f"Vertical posture derived from {source_creature} biomorphic trait record.",
        ),
        fabrication_hints=[
            "Concept-stage biomorphic morphology; validate mechanics before fabrication.",
            "Use simple primitives first, then refine into organic/mechanical surfaces.",
            "Keep creature-inspired features mechanically interpretable, not purely decorative.",
        ],
        allowed_primitive_shapes=[
            "box", "cylinder", "sphere", "chamfered_box", "capsule", "thin_plate", "wedge",
        ],
        hard_negatives=hard_negatives,
        morphology_archetype=archetype,
        bio_inspiration={
            "source_creature": source_creature,
            "creature_class": hints.get("creature_class", ""),
            "inspiration_mode": "functional_biomimicry",
            "borrowed_traits": specialized_features,
        },
        locomotion_strategy={
            "primary_mode": hints.get("locomotion_primary", ""),
            "secondary_modes": hints.get("locomotion_secondary", []),
            "terrain_target": hints.get("terrain", []),
        },
        specialized_features=specialized_features,
        cad_rules=cad_rules,
        quality_checklist=quality_items,
        source_mission_keywords=[source_creature, archetype, robot_family],
        notes=(
            f"Biomorphic morphology generated from trait library. "
            f"Creature={source_creature}, family={robot_family}, archetype={archetype}."
        ),
    )


def infer_morphology_spec(mission_text: str) -> MorphologySpec:
    """Main entry point. Takes a mission string and returns a MorphologySpec."""
    text = str(mission_text or "").lower().strip()

    # First: use the data-driven biomorphic trait library when a known
    # creature is mentioned. This prevents all animal-inspired robots from collapsing
    # into insect/drone/rover defaults.
    biomorphic_hints = (
        infer_biomorphic_hints(text)
        if infer_biomorphic_hints is not None
        else {}
    )
    if biomorphic_hints and biomorphic_hints.get("matched"):
        return _build_biomorphic_from_hints(text, biomorphic_hints)

    family = _detect_family(text)
    leg_count = _detect_leg_count(text)

    if family in {"insectoid_legged_robot", "hexapod_robot", "quadruped_robot"}:
        if leg_count == 0:
            leg_count = 4 if family == "quadruped_robot" else 6
        return _build_legged_platform(text, leg_count, family_hint=family)
    if family == "sci_fi_walker":
        return _build_sci_fi_walker(text)
    if family == "wheeled_rover":
        return _build_wheeled_rover(text)
    if family == "tracked_rover":
        return _build_tracked_rover(text)
    if family == "aerial_drone":
        return _build_aerial_drone(text)
    if family == "manipulator_arm":
        return _build_manipulator_arm(text)
    if family == "sensor_pod":
        return _build_sensor_pod(text)
    return _build_generic(text)


def infer_morphology_spec_dict(mission_text: str) -> Dict[str, Any]:
    """Convenience wrapper that returns a plain dict instead of MorphologySpec."""
    return infer_morphology_spec(mission_text).to_dict()


def morphology_family_for_project_type(project_type: str) -> str:
    """Maps OMNI's existing project_type strings to morphology family names."""
    mapping = {
        "drone": "aerial_drone",
        "rover": "wheeled_rover",
        "tracked_rover": "tracked_rover",
        "robot_arm": "manipulator_arm",
        "arm": "manipulator_arm",
        "enclosure": "sensor_pod",
        "sensor_pod": "sensor_pod",
        "generic_robotics": "generic_robotic_platform",
        "generic": "generic_robotic_platform",
    }
    return mapping.get(str(project_type or "").lower(), "generic_robotic_platform")
