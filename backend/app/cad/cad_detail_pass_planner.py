"""
OMNI CAD Detail Pass Planner.

Takes mission text, a morphology_spec dict, and a platform type, then returns
a fully populated AssemblySpec that the Fusion 360 generator can consume.

Design rules:
- No LLM calls.
- No Fusion API imports.
- No file I/O.
- Deterministic.
- Additive: new platforms can be added by appending to the dispatch table.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

try:
    from .cad_assembly_ir import (
        AssemblySpec,
        DetailPassSpec,
        FastenerPatternSpec,
        InternalVolumeSpec,
        MechanicalComponentSpec,
        MountingFeatureSpec,
        OuterShellSpec,
        PanelFeatureSpec,
        StructuralFeatureSpec,
        SubassemblySpec,
        LOD2_MECHANICAL_PLACEHOLDERS,
        LOD3_INTERNAL_ASSEMBLY,
        LOD4_TRANSPARENT_CUTAWAY,
        VISIBILITY_OPAQUE,
        VISIBILITY_CUTAWAY,
    )
    from .fusion_detail_profiles import (
        resolve_detail_profile,
        visibility_for_mission,
    )
    from .mechanical_component_library import (
        components_for_platform,
        components_for_traits,
        default_dims,
        component_shape,
    )
except ImportError:
    from cad_assembly_ir import (  # type: ignore
        AssemblySpec,
        DetailPassSpec,
        FastenerPatternSpec,
        InternalVolumeSpec,
        MechanicalComponentSpec,
        MountingFeatureSpec,
        OuterShellSpec,
        PanelFeatureSpec,
        StructuralFeatureSpec,
        SubassemblySpec,
        LOD2_MECHANICAL_PLACEHOLDERS,
        LOD3_INTERNAL_ASSEMBLY,
        LOD4_TRANSPARENT_CUTAWAY,
        VISIBILITY_OPAQUE,
        VISIBILITY_CUTAWAY,
    )
    from fusion_detail_profiles import (  # type: ignore
        resolve_detail_profile,
        visibility_for_mission,
    )
    from mechanical_component_library import (  # type: ignore
        components_for_platform,
        components_for_traits,
        default_dims,
        component_shape,
    )


# ─────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────

def _mcomp(
    name: str,
    component_type: str,
    x: float = 0.0,
    y: float = 0.0,
    z: float = 0.0,
    angle: float = 0.0,
    label: str = "",
    notes: str = "",
    tags: Optional[List[str]] = None,
) -> MechanicalComponentSpec:
    L, W, H = default_dims(component_type)
    return MechanicalComponentSpec(
        name=name,
        component_type=component_type,
        x_mm=x,
        y_mm=y,
        z_mm=z,
        angle_deg=angle,
        length_mm=L,
        width_mm=W,
        height_mm=H,
        label=label or name,
        notes=notes,
        tags=tags or [],
    )


def _boss(name: str, x: float, y: float, z: float) -> MountingFeatureSpec:
    return MountingFeatureSpec(
        name=name,
        feature_type="boss",
        x_mm=x,
        y_mm=y,
        z_mm=z,
        diameter_mm=6.0,
        height_mm=8.0,
    )


def _rib(name: str, x: float, y: float, z: float,
         length: float = 60.0, width: float = 3.0, height: float = 22.0,
         angle: float = 0.0) -> StructuralFeatureSpec:
    return StructuralFeatureSpec(
        name=name,
        feature_type="rib",
        length_mm=length,
        width_mm=width,
        height_mm=height,
        x_mm=x,
        y_mm=y,
        z_mm=z,
        angle_deg=angle,
    )


def _bulkhead(name: str, x: float, y: float, z: float,
              length: float = 60.0, height: float = 30.0) -> StructuralFeatureSpec:
    return StructuralFeatureSpec(
        name=name,
        feature_type="bulkhead",
        length_mm=length,
        width_mm=4.0,
        height_mm=height,
        x_mm=x,
        y_mm=y,
        z_mm=z,
    )


def _cable(name: str, x: float, y: float, z: float, length: float = 180.0) -> StructuralFeatureSpec:
    return StructuralFeatureSpec(
        name=name,
        feature_type="cable_corridor",
        length_mm=length,
        width_mm=10.0,
        height_mm=6.0,
        x_mm=x,
        y_mm=y,
        z_mm=z,
    )


def _panel(name: str, panel_type: str,
           length: float, width: float, thickness: float,
           x: float, y: float, z: float,
           transparent: bool = False) -> PanelFeatureSpec:
    return PanelFeatureSpec(
        name=name,
        panel_type=panel_type,
        length_mm=length,
        width_mm=width,
        thickness_mm=thickness,
        x_mm=x,
        y_mm=y,
        z_mm=z,
        transparent=transparent,
    )


# ─────────────────────────────────────────────────────────────
# Platform-specific assembly builders
# ─────────────────────────────────────────────────────────────

def _build_aquatic_glider(
    profile: Dict[str, Any],
    morphology_spec: Dict[str, Any],
    visibility: str,
) -> AssemblySpec:
    """Manta-ray / aquatic glider assembly."""
    include_internals = profile.get("include_internals", False)
    include_ribs = profile.get("include_ribs_bulkheads", False)
    include_cables = profile.get("include_cable_corridors", False)
    cutaway = visibility == VISIBILITY_CUTAWAY

    # ── Outer shell ────────────────────────────────────────
    panels = [
        _panel("hull_bottom",     "bottom_plate",  200, 80,  8,  0,  0,  0),
        _panel("hull_top",        "top_shell",     200, 80,  6,  0,  0, 28, transparent=cutaway),
        _panel("nose_cap",        "nose_cap",       30, 60, 10, 100, 0, 14),
        _panel("tail_fairing",    "side_fairing",   40, 30,  6, -90, 0, 14),
        _panel("fin_left",        "fin_panel",      95, 16,  4,   0, 80, 14),
        _panel("fin_right",       "fin_panel",      95, 16,  4,   0,-80, 14),
    ]
    shell = OuterShellSpec(
        shell_type="monocoque",
        visibility_mode=visibility,
        panels=panels,
    )

    # ── Power subassembly ──────────────────────────────────
    power_comps: List[MechanicalComponentSpec] = []
    power_mounting: List[MountingFeatureSpec] = []
    power_volumes: List[InternalVolumeSpec] = []

    if profile.get("include_components", True):
        power_comps = [_mcomp("battery_main", "battery_pack", 20, 0, 10, label="LiPo Battery")]
        power_mounting = [
            _boss("battery_boss_fl", -28, -18, 8),
            _boss("battery_boss_fr", -28,  18, 8),
            _boss("battery_boss_rl",  68, -18, 8),
            _boss("battery_boss_rr",  68,  18, 8),
        ]
    if include_internals:
        power_volumes = [InternalVolumeSpec("battery_bay", "battery", 95, 40, 26, 20, 0, 8)]

    power_sub = SubassemblySpec(
        name="power",
        zone="power",
        components=power_comps,
        mounting_features=power_mounting,
        internal_volumes=power_volumes,
    )

    # ── Compute subassembly ────────────────────────────────
    compute_comps: List[MechanicalComponentSpec] = []
    if profile.get("include_components", True):
        compute_comps = [
            _mcomp("compute_board", "electronics_board", -30, 0, 18, label="Compute Board"),
            _mcomp("sensor_nose",   "sensor_pod",        90, 0, 18, label="Sensor/Sonar Pod"),
            _mcomp("sonar_ring",    "sonar_ring",        105, 0, 18, label="Sonar Ring"),
            _mcomp("camera_lens",   "camera_lens",       110, 0, 20, label="Forward Camera"),
        ]
    compute_sub = SubassemblySpec(
        name="compute_sensor",
        zone="compute",
        components=compute_comps,
    )

    # ── Actuation subassembly ──────────────────────────────
    actuation_comps: List[MechanicalComponentSpec] = []
    if profile.get("include_components", True):
        actuation_comps = [
            _mcomp("tail_actuator", "actuator_block", -85, 0, 16, label="Tail Actuator"),
            _mcomp("fin_servo_l",   "servo_motor",      0, 80, 14, label="Left Fin Servo"),
            _mcomp("fin_servo_r",   "servo_motor",      0,-80, 14, label="Right Fin Servo"),
        ]
    act_sub = SubassemblySpec(
        name="actuation",
        zone="propulsion",
        components=actuation_comps,
    )

    # ── Structural features ────────────────────────────────
    structural: List[StructuralFeatureSpec] = []
    if include_ribs:
        structural.extend([
            _rib("fin_rib_l1", 30, 70, 12, 55, 3, 22),
            _rib("fin_rib_l2", -20, 70, 12, 55, 3, 22),
            _rib("fin_rib_r1", 30, -70, 12, 55, 3, 22),
            _rib("fin_rib_r2", -20, -70, 12, 55, 3, 22),
            _bulkhead("bulkhead_fwd", 60, 0, 8, 60, 28),
            _bulkhead("bulkhead_mid",  0, 0, 8, 60, 28),
            _bulkhead("bulkhead_aft", -60, 0, 8, 60, 28),
        ])
    if include_cables:
        structural.append(_cable("cable_corridor_main", 0, 0, 12, 180))

    # ── Detail passes ──────────────────────────────────────
    passes = [DetailPassSpec(p.pass_name, p.pass_type, p.detail_level)
              for p in profile.get("detail_passes", [])]

    return AssemblySpec(
        assembly_name="omni_aquatic_glider_assembly",
        platform_type="aquatic_glider_robot",
        morphology_family="aquatic_glider_robot",
        detail_level=profile.get("detail_passes", [{}])[-1].detail_level
                     if profile.get("detail_passes") else LOD2_MECHANICAL_PLACEHOLDERS,
        visibility_mode=visibility,
        outer_shell=shell,
        subassemblies=[power_sub, compute_sub, act_sub],
        structural_features=structural,
        detail_passes=passes,
        trait_sources=list(morphology_spec.get("bio_inspiration", {}).get("borrowed_traits", [])),
        specialized_features=list(morphology_spec.get("specialized_features", [])),
    )


def _build_hybrid_drone(
    profile: Dict[str, Any],
    morphology_spec: Dict[str, Any],
    visibility: str,
) -> AssemblySpec:
    """Biomorphic drone (manta-ray drone, dragonfly UAV, etc.)."""
    include_internals = profile.get("include_internals", False)
    include_ribs = profile.get("include_ribs_bulkheads", False)
    include_cables = profile.get("include_cable_corridors", False)
    cutaway = visibility == VISIBILITY_CUTAWAY
    traits = list(morphology_spec.get("bio_inspiration", {}).get("borrowed_traits", []))
    trait_text = " ".join(traits).lower()
    has_crab = "crab" in trait_text or "landing" in trait_text

    panels = [
        _panel("fuselage_body", "top_shell", 160, 50, 8, 0, 0, 0),
        _panel("fuselage_top",  "top_shell", 140, 40, 4, 0, 0, 18, transparent=cutaway),
        _panel("nose_pod",      "nose_cap",   30, 30, 8, 85, 0, 10),
        _panel("tail_boom",     "side_fairing", 60, 12, 8, -90, 0, 10),
        _panel("wide_fin_l",    "fin_panel",   90, 18, 4, 0,  80, 12),
        _panel("wide_fin_r",    "fin_panel",   90, 18, 4, 0, -80, 12),
    ]
    shell = OuterShellSpec("monocoque", visibility, panels)

    power_comps: List[MechanicalComponentSpec] = []
    if profile.get("include_components", True):
        power_comps = [
            _mcomp("battery_main", "battery_pack", 10, 0, 8, label="LiPo Battery"),
            _mcomp("fc_board", "flight_controller", -10, 0, 18, label="Flight Controller"),
        ]
    power_sub = SubassemblySpec("power_compute", "power", components=power_comps)

    prop_comps: List[MechanicalComponentSpec] = []
    if profile.get("include_components", True):
        for i, (px, py) in enumerate([(60, 45), (60, -45), (-60, 45), (-60, -45)], 1):
            prop_comps.append(_mcomp(f"motor_{i}", "motor_can", px, py, 20, label=f"Motor {i}"))
            prop_comps.append(_mcomp(f"prop_{i}", "propeller_disk", px, py, 30, label=f"Prop {i}"))
        prop_comps.append(_mcomp("sensor_nose", "sensor_pod", 90, 0, 14, label="Sensor Nose"))

    if has_crab and profile.get("include_components", True):
        for i, (lx, ly) in enumerate([(40, 30), (40, -30), (-40, 30), (-40, -30)], 1):
            prop_comps.append(_mcomp(f"landing_pad_{i}", "landing_pad", lx, ly, 0, label=f"Landing Pad {i}"))

    prop_sub = SubassemblySpec("propulsion_sensor", "propulsion", components=prop_comps)

    structural: List[StructuralFeatureSpec] = []
    if include_ribs:
        structural.extend([
            _rib("fin_rib_l", 0, 75, 10, 80, 3, 18),
            _rib("fin_rib_r", 0, -75, 10, 80, 3, 18),
            _bulkhead("bulk_fwd", 50, 0, 8, 40, 22),
            _bulkhead("bulk_aft", -50, 0, 8, 40, 22),
        ])
    if include_cables:
        structural.append(_cable("main_harness", 0, 0, 10, 150))

    passes = [DetailPassSpec(p.pass_name, p.pass_type, p.detail_level)
              for p in profile.get("detail_passes", [])]

    return AssemblySpec(
        assembly_name="omni_hybrid_biomorphic_drone_assembly",
        platform_type="hybrid_biomorphic_drone",
        morphology_family="hybrid_biomorphic_drone",
        detail_level=LOD3_INTERNAL_ASSEMBLY if include_internals else LOD2_MECHANICAL_PLACEHOLDERS,
        visibility_mode=visibility,
        outer_shell=shell,
        subassemblies=[power_sub, prop_sub],
        structural_features=structural,
        detail_passes=passes,
        trait_sources=traits,
        specialized_features=list(morphology_spec.get("specialized_features", [])),
    )


def _build_biomorphic_rover(
    profile: Dict[str, Any],
    morphology_spec: Dict[str, Any],
    visibility: str,
) -> AssemblySpec:
    """Rover with creature traits (turtle, gecko, etc.)."""
    include_internals = profile.get("include_internals", False)
    include_ribs = profile.get("include_ribs_bulkheads", False)
    include_cables = profile.get("include_cable_corridors", False)
    cutaway = visibility == VISIBILITY_CUTAWAY
    traits = list(morphology_spec.get("bio_inspiration", {}).get("borrowed_traits", []))
    trait_text = " ".join(traits).lower()
    has_armor = any(t in trait_text for t in ["turtle", "armor", "armour", "shell"])
    has_gecko = any(t in trait_text for t in ["gecko", "adhesive", "climbing"])

    panels = [
        _panel("chassis_plate",  "bottom_plate", 280, 180, 6,  0, 0, 0),
        _panel("chassis_top",    "top_shell",    240, 160, 4,  0, 0, 40, transparent=cutaway),
    ]
    if has_armor:
        panels.append(_panel("armor_plate", "side_fairing", 200, 140, 10, 0, 0, 50))
    shell = OuterShellSpec("monocoque", visibility, panels)

    power_comps: List[MechanicalComponentSpec] = []
    if profile.get("include_components", True):
        power_comps = [
            _mcomp("battery_bay",    "battery_pack",      40, 0, 8, label="LiPo Battery"),
            _mcomp("compute_board",  "compute_module",   -40, 0, 18, label="Compute Module"),
            _mcomp("front_sensor",   "sensor_pod",       120, 0, 22, label="Front Sensor Head"),
            _mcomp("camera",         "camera_lens",      135, 0, 24, label="Camera"),
            _mcomp("cable_ch",       "cable_channel",      0, 0, 12, label="Cable Channel"),
        ]
        if has_gecko:
            for i, (lx, ly) in enumerate([(100, 70), (100,-70), (-80, 70), (-80,-70)], 1):
                power_comps.append(_mcomp(f"adhesive_pad_{i}", "adhesive_pad", lx, ly, 0,
                                          label=f"Adhesive Pad {i}"))
        else:
            for i, (wx, wy) in enumerate([(100, 90), (100,-90), (-80, 90), (-80,-90)], 1):
                power_comps.append(_mcomp(f"wheel_{i}", "landing_pad", wx, wy, 0,
                                          label=f"Wheel {i} Placeholder"))

        for bid, (bx, by) in enumerate([(60,-60),(60,60),(-50,-60),(-50,60)], 1):
            power_comps.append(_mcomp(f"boss_{bid}", "screw_boss", bx, by, 18,
                                      label=f"Mounting Boss {bid}"))

    power_sub = SubassemblySpec(
        "chassis_internals", "power",
        components=power_comps,
        mounting_features=[_boss(f"rail_boss_{i}", -80 + i*50, 0, 6) for i in range(5)],
    )

    structural: List[StructuralFeatureSpec] = []
    if include_ribs:
        for rx in [-60, 0, 60]:
            structural.append(_rib(f"cross_rib_{rx}", rx, 0, 6, 160, 4, 30))
        structural.append(_bulkhead("bh_front",  90, 0, 6, 160, 30))
        structural.append(_bulkhead("bh_rear",  -60, 0, 6, 160, 30))
    if include_cables:
        structural.append(_cable("main_harness", 0, 0, 10, 240))

    passes = [DetailPassSpec(p.pass_name, p.pass_type, p.detail_level)
              for p in profile.get("detail_passes", [])]

    return AssemblySpec(
        assembly_name="omni_biomorphic_rover_assembly",
        platform_type="biomorphic_rover",
        morphology_family="biomorphic_rover",
        detail_level=LOD3_INTERNAL_ASSEMBLY if include_internals else LOD2_MECHANICAL_PLACEHOLDERS,
        visibility_mode=visibility,
        outer_shell=shell,
        subassemblies=[power_sub],
        structural_features=structural,
        detail_passes=passes,
        trait_sources=traits,
        specialized_features=list(morphology_spec.get("specialized_features", [])),
    )


def _build_generic_assembly(
    profile: Dict[str, Any],
    morphology_spec: Dict[str, Any],
    project_type: str,
    visibility: str,
) -> AssemblySpec:
    """Fallback assembly for any platform without a dedicated builder."""
    include_ribs = profile.get("include_ribs_bulkheads", False)
    include_cables = profile.get("include_cable_corridors", False)
    cutaway = visibility == VISIBILITY_CUTAWAY

    panels = [
        _panel("base_plate", "bottom_plate", 280, 180, 4, 0, 0, 0),
        _panel("top_cover",  "top_shell",    260, 160, 3, 0, 0, 30, transparent=cutaway),
    ]
    shell = OuterShellSpec("monocoque", visibility, panels)

    comps: List[MechanicalComponentSpec] = []
    if profile.get("include_components", True):
        comps = [
            _mcomp("battery",    "battery_pack",    40, 0, 8, label="Battery"),
            _mcomp("compute",    "compute_module", -40, 0, 18, label="Compute"),
            _mcomp("sensor",     "sensor_pod",      110, 0, 20, label="Sensor"),
        ]
    generic_sub = SubassemblySpec("generic_internals", "structure", components=comps)

    structural: List[StructuralFeatureSpec] = []
    if include_ribs:
        structural.append(_bulkhead("bh_mid", 0, 0, 4, 150, 28))
    if include_cables:
        structural.append(_cable("harness", 0, 0, 8, 220))

    passes = [DetailPassSpec(p.pass_name, p.pass_type, p.detail_level)
              for p in profile.get("detail_passes", [])]

    return AssemblySpec(
        assembly_name=f"omni_{project_type}_assembly",
        platform_type=project_type,
        morphology_family=morphology_spec.get("morphology_family", project_type),
        detail_level=LOD2_MECHANICAL_PLACEHOLDERS,
        visibility_mode=visibility,
        outer_shell=shell,
        subassemblies=[generic_sub],
        structural_features=structural,
        detail_passes=passes,
        trait_sources=list(morphology_spec.get("bio_inspiration", {}).get("borrowed_traits", [])),
        specialized_features=list(morphology_spec.get("specialized_features", [])),
    )


# ─────────────────────────────────────────────────────────────
# Dispatch table
# ─────────────────────────────────────────────────────────────

_BUILDER_MAP = {
    "aquatic_glider_robot":  _build_aquatic_glider,
    "hybrid_biomorphic_drone": _build_hybrid_drone,
    "biomorphic_rover":      _build_biomorphic_rover,
    "armored_rover":         _build_biomorphic_rover,
}


# ─────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────

def plan_cad_detail_passes(
    mission_text: str,
    morphology_spec: Optional[Dict[str, Any]],
    project_type: str,
) -> AssemblySpec:
    """
    Main entry point.  Returns a populated AssemblySpec.

    Parameters
    ----------
    mission_text   : raw mission string (used for keyword detection)
    morphology_spec: to_dict() output from MorphologySpec, or {} / None
    project_type   : OMNI project type string ("aquatic_glider_robot", etc.)
    """
    morphology_spec = morphology_spec or {}
    profile = resolve_detail_profile(mission_text, morphology_spec)
    visibility = visibility_for_mission(mission_text)

    # Try platform-specific builder first; family override second; generic fallback.
    family = str(morphology_spec.get("morphology_family", project_type) or project_type)
    builder = _BUILDER_MAP.get(project_type) or _BUILDER_MAP.get(family)

    if builder is not None:
        return builder(profile, morphology_spec, visibility)

    return _build_generic_assembly(profile, morphology_spec, project_type, visibility)


def assembly_spec_to_dict(spec: AssemblySpec) -> Dict[str, Any]:
    """Thin wrapper so callers don't need to import AssemblySpec."""
    return spec.to_dict()


def summarize_assembly_spec(spec: AssemblySpec) -> str:
    """Return a one-line human-readable summary."""
    return (
        f"AssemblySpec: {spec.assembly_name} | "
        f"platform={spec.platform_type} | "
        f"detail={spec.detail_level} | "
        f"visibility={spec.visibility_mode} | "
        f"components={spec.component_count} | "
        f"structural={spec.structural_feature_count}"
    )