"""
OMNI Mechanical Component Library.

A reusable pattern registry for mechanical and electronic component placeholders.
Every pattern is a plain dict; no Fusion imports, no LLM calls.

Usage:
    from backend.app.cad.mechanical_component_library import (
        get_component_pattern,
        components_for_platform,
        components_for_traits,
    )
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional


# ─────────────────────────────────────────────────────────────
# Component pattern registry
# Each entry has:
#   default_dims      : (length_mm, width_mm, height_mm) defaults
#   shape             : "box" | "cylinder" | "thin_disk" | "ring"
#   mounting_hint     : text description of where / how to attach
#   placement_hint    : typical placement relative to body centre
#   platforms         : list of morphology_family strings this fits
#   tags              : free-form capability / material tags
# ─────────────────────────────────────────────────────────────

_COMPONENT_PATTERNS: Dict[str, Dict[str, Any]] = {

    # ── Power ─────────────────────────────────────────────
    "battery_pack": {
        "default_dims": (95, 40, 26),
        "shape": "box",
        "mounting_hint": "Place low and near centre of mass. Use strap/clip mounts.",
        "placement_hint": "centre or rear of chassis, low z",
        "platforms": [
            "wheeled_rover", "tracked_rover", "aerial_drone",
            "aquatic_glider_robot", "insectoid_legged_robot",
            "hexapod_robot", "quadruped_robot", "manipulator_arm",
            "hybrid_biomorphic_drone", "biomorphic_rover",
            "serpentine_robot", "generic_robotic_platform",
        ],
        "tags": ["power", "lipo", "18650", "heavy"],
    },

    # ── Compute ───────────────────────────────────────────
    "electronics_board": {
        "default_dims": (85, 56, 8),
        "shape": "box",
        "mounting_hint": "Mount on M2.5–M3 standoffs above chassis plate.",
        "placement_hint": "centre-rear of chassis or inside hull",
        "platforms": [
            "wheeled_rover", "tracked_rover", "aquatic_glider_robot",
            "insectoid_legged_robot", "hexapod_robot", "quadruped_robot",
            "biomorphic_rover", "generic_robotic_platform",
        ],
        "tags": ["compute", "pcb", "raspberry_pi", "jetson"],
    },
    "compute_module": {
        "default_dims": (70, 45, 12),
        "shape": "box",
        "mounting_hint": "Standoffs. Keep clear of high-current wiring.",
        "placement_hint": "central electronics bay",
        "platforms": ["wheeled_rover", "biomorphic_rover", "aquatic_glider_robot",
                      "tracked_rover", "generic_robotic_platform"],
        "tags": ["compute", "jetson", "rpi", "orin"],
    },
    "flight_controller": {
        "default_dims": (38, 38, 8),
        "shape": "box",
        "mounting_hint": "Vibration-isolated on 4-point standoff pattern.",
        "placement_hint": "centre of drone fuselage",
        "platforms": ["aerial_drone", "hybrid_biomorphic_drone"],
        "tags": ["compute", "fc", "imu", "flight"],
    },

    # ── Propulsion ────────────────────────────────────────
    "motor_can": {
        "default_dims": (0, 22, 28),        # cylinder: (unused, radius_mm, height_mm)
        "shape": "cylinder",
        "mounting_hint": "Bolted to motor mount pad at arm tip.",
        "placement_hint": "end of propulsion arm",
        "platforms": ["aerial_drone", "hybrid_biomorphic_drone"],
        "tags": ["propulsion", "brushless", "motor"],
    },
    "servo_motor": {
        "default_dims": (23, 12, 24),
        "shape": "box",
        "mounting_hint": "Bracket-mounted at joint pivot. Keep cable routing clear.",
        "placement_hint": "joint pivot point",
        "platforms": [
            "insectoid_legged_robot", "hexapod_robot", "quadruped_robot",
            "manipulator_arm", "sci_fi_walker", "serpentine_robot",
            "aquatic_glider_robot", "biomorphic_rover",
        ],
        "tags": ["actuation", "servo", "joint"],
    },
    "actuator_block": {
        "default_dims": (45, 30, 20),
        "shape": "box",
        "mounting_hint": "Bolted to structural rib or bulkhead.",
        "placement_hint": "tail or fin root",
        "platforms": ["aquatic_glider_robot", "serpentine_robot",
                      "biomorphic_rover", "manipulator_arm"],
        "tags": ["actuation", "linear", "fin", "tail"],
    },
    "ducted_fan_placeholder": {
        "default_dims": (0, 40, 20),
        "shape": "cylinder",
        "mounting_hint": "Ring-mounted in fuselage nacelle.",
        "placement_hint": "fuselage side or tail",
        "platforms": ["hybrid_biomorphic_drone", "aerial_drone"],
        "tags": ["propulsion", "edf", "fan"],
    },
    "propeller_disk": {
        "default_dims": (0, 48, 2),
        "shape": "thin_disk",
        "mounting_hint": "Clearance disk only—represents sweep area.",
        "placement_hint": "above motor can",
        "platforms": ["aerial_drone", "hybrid_biomorphic_drone"],
        "tags": ["propulsion", "clearance", "disk"],
    },

    # ── Sensing ───────────────────────────────────────────
    "sensor_pod": {
        "default_dims": (40, 30, 28),
        "shape": "box",
        "mounting_hint": "Front-facing on nose bracket or sensor mast.",
        "placement_hint": "nose / forward fuselage",
        "platforms": [
            "wheeled_rover", "biomorphic_rover", "aquatic_glider_robot",
            "insectoid_legged_robot", "hexapod_robot", "quadruped_robot",
            "aerial_drone", "hybrid_biomorphic_drone",
            "serpentine_robot", "generic_robotic_platform",
        ],
        "tags": ["sensing", "camera", "lidar", "sonar"],
    },
    "camera_lens": {
        "default_dims": (0, 8, 12),
        "shape": "cylinder",
        "mounting_hint": "Press-fit or adhesive in sensor pod face.",
        "placement_hint": "front of sensor pod",
        "platforms": [
            "wheeled_rover", "biomorphic_rover", "aquatic_glider_robot",
            "aerial_drone", "hybrid_biomorphic_drone",
            "insectoid_legged_robot", "hexapod_robot",
        ],
        "tags": ["sensing", "optical", "camera"],
    },
    "sonar_ring": {
        "default_dims": (0, 18, 10),
        "shape": "ring",
        "mounting_hint": "Forward-facing, flush with nose shell.",
        "placement_hint": "nose tip",
        "platforms": ["aquatic_glider_robot", "serpentine_robot"],
        "tags": ["sensing", "sonar", "acoustic"],
    },

    # ── Structure / Fasteners ─────────────────────────────
    "standoff": {
        "default_dims": (0, 3, 12),
        "shape": "cylinder",
        "mounting_hint": "M3 thread, between chassis and electronics board.",
        "placement_hint": "PCB mounting points",
        "platforms": ["*"],
        "tags": ["structure", "fastener", "standoff"],
    },
    "screw_boss": {
        "default_dims": (0, 4, 8),
        "shape": "cylinder",
        "mounting_hint": "Integral boss on moulded shell or chassis plate.",
        "placement_hint": "shell corners / mid-span",
        "platforms": ["*"],
        "tags": ["structure", "fastener", "boss"],
    },
    "mounting_rail": {
        "default_dims": (180, 8, 6),
        "shape": "box",
        "mounting_hint": "Longitudinal rail along bottom of chassis.",
        "placement_hint": "centreline fore/aft",
        "platforms": ["wheeled_rover", "biomorphic_rover", "aquatic_glider_robot",
                      "tracked_rover", "generic_robotic_platform"],
        "tags": ["structure", "rail", "mounting"],
    },
    "cable_channel": {
        "default_dims": (200, 10, 6),
        "shape": "box",
        "mounting_hint": "Route along chassis centreline between bays.",
        "placement_hint": "centreline, mid-chassis height",
        "platforms": ["*"],
        "tags": ["structure", "cable", "routing"],
    },
    "bulkhead_plate": {
        "default_dims": (60, 4, 40),
        "shape": "box",
        "mounting_hint": "Perpendicular to centreline at bay boundaries.",
        "placement_hint": "between power and compute bays",
        "platforms": ["aquatic_glider_robot", "serpentine_robot",
                      "hybrid_biomorphic_drone", "biomorphic_rover"],
        "tags": ["structure", "bulkhead", "separation"],
    },
    "structural_rib": {
        "default_dims": (50, 3, 25),
        "shape": "box",
        "mounting_hint": "Spanning shell inner surface. Space at 40–60 mm intervals.",
        "placement_hint": "inside fin or shell, lateral",
        "platforms": ["aquatic_glider_robot", "hybrid_biomorphic_drone",
                      "biomorphic_rover", "tracked_rover"],
        "tags": ["structure", "rib", "stiffener"],
    },
    "transparent_shell_panel": {
        "default_dims": (120, 80, 3),
        "shape": "box",
        "mounting_hint": "Replaces top shell in cutaway mode.",
        "placement_hint": "top of hull",
        "platforms": ["*"],
        "tags": ["shell", "transparent", "cutaway"],
    },

    # ── Bio-morphic / trait-specific ──────────────────────
    "fin_rib": {
        "default_dims": (55, 3, 22),
        "shape": "box",
        "mounting_hint": "Inside fin surface at 25 mm intervals from root.",
        "placement_hint": "inside fin panel",
        "platforms": ["aquatic_glider_robot", "hybrid_biomorphic_drone",
                      "biomorphic_micro_uav"],
        "tags": ["structure", "fin", "rib", "aquatic", "wing"],
    },
    "landing_pad": {
        "default_dims": (28, 18, 4),
        "shape": "box",
        "mounting_hint": "Bottom of leg tip. Rubber or TPU material.",
        "placement_hint": "foot / leg tip",
        "platforms": [
            "insectoid_legged_robot", "hexapod_robot", "quadruped_robot",
            "aerial_drone", "hybrid_biomorphic_drone", "sci_fi_walker",
        ],
        "tags": ["contact", "landing", "foot"],
    },
    "adhesive_pad": {
        "default_dims": (24, 16, 3),
        "shape": "box",
        "mounting_hint": "Gecko-style adhesive pad at foot contact point.",
        "placement_hint": "foot / leg tip",
        "platforms": ["wall_climbing_robot", "biomorphic_rover"],
        "tags": ["contact", "adhesive", "gecko", "climbing"],
    },
    "armored_shell_plate": {
        "default_dims": (140, 100, 8),
        "shape": "box",
        "mounting_hint": "Protective outer plate over standard chassis.",
        "placement_hint": "top of chassis or rover hull",
        "platforms": ["biomorphic_rover", "tracked_rover", "wheeled_rover"],
        "tags": ["shell", "armor", "turtle", "protection"],
    },
}


# ─────────────────────────────────────────────────────────────
# Public helpers
# ─────────────────────────────────────────────────────────────

def normalize_component_name(name: str) -> str:
    """Lower-case and underscore-normalise a component name."""
    import re
    text = str(name or "").lower().strip()
    text = re.sub(r"[^a-z0-9_]+", "_", text)
    text = re.sub(r"_+", "_", text).strip("_")
    return text


def get_component_pattern(name: str) -> Optional[Dict[str, Any]]:
    """
    Return the pattern dict for a component name, or None if not found.

    >>> get_component_pattern("battery_pack")["shape"]
    'box'
    """
    key = normalize_component_name(name)
    return _COMPONENT_PATTERNS.get(key)


def list_component_patterns() -> List[str]:
    """Return sorted list of all registered component names."""
    return sorted(_COMPONENT_PATTERNS.keys())


def components_for_platform(platform_type: str) -> List[str]:
    """
    Return component names that list this platform (or "*" wildcard).

    >>> "battery_pack" in components_for_platform("aerial_drone")
    True
    """
    target = str(platform_type or "").lower()
    return sorted(
        name
        for name, pat in _COMPONENT_PATTERNS.items()
        if "*" in pat.get("platforms", []) or target in pat.get("platforms", [])
    )


def components_for_traits(trait_sources: List[str]) -> List[str]:
    """
    Return component names whose tags overlap with any of the trait_sources.

    trait_sources typically come from morphology_spec.bio_inspiration.borrowed_traits
    or morphology_spec.specialized_features.

    >>> "adhesive_pad" in components_for_traits(["gecko_adhesion"])
    True
    """
    trait_tokens = set()
    for trait in (trait_sources or []):
        for token in str(trait).lower().replace("-", "_").replace(" ", "_").split("_"):
            if token:
                trait_tokens.add(token)

    results = []
    for name, pat in _COMPONENT_PATTERNS.items():
        tag_tokens: set = set()
        for tag in pat.get("tags", []):
            for token in str(tag).lower().replace("-", "_").split("_"):
                if token:
                    tag_tokens.add(token)
        if trait_tokens & tag_tokens:
            results.append(name)

    return sorted(results)


def default_dims(component_name: str) -> tuple:
    """Return (length_mm, width_mm, height_mm) defaults, or (50, 30, 15) fallback."""
    pat = get_component_pattern(component_name)
    if pat:
        return tuple(pat["default_dims"])
    return (50.0, 30.0, 15.0)


def component_shape(component_name: str) -> str:
    """Return shape string ('box', 'cylinder', 'thin_disk', 'ring'), or 'box'."""
    pat = get_component_pattern(component_name)
    if pat:
        return pat.get("shape", "box")
    return "box"