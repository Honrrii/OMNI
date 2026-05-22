"""
OMNI Fusion Detail Profiles.

Maps a CAD detail level (LOD0–LOD4) to a set of detail passes that control
what geometry the Fusion 360 generator emits.

Design rules:
- No LLM calls.
- No Fusion API imports.
- Deterministic: same inputs -> same output.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

try:
    from .cad_assembly_ir import (
        LOD0_SILHOUETTE,
        LOD1_MORPHOLOGY,
        LOD2_MECHANICAL_PLACEHOLDERS,
        LOD3_INTERNAL_ASSEMBLY,
        LOD4_TRANSPARENT_CUTAWAY,
        DETAIL_LEVELS,
        VISIBILITY_OPAQUE,
        VISIBILITY_CUTAWAY,
        DetailPassSpec,
    )
except ImportError:
    from cad_assembly_ir import (  # type: ignore
        LOD0_SILHOUETTE,
        LOD1_MORPHOLOGY,
        LOD2_MECHANICAL_PLACEHOLDERS,
        LOD3_INTERNAL_ASSEMBLY,
        LOD4_TRANSPARENT_CUTAWAY,
        DETAIL_LEVELS,
        VISIBILITY_OPAQUE,
        VISIBILITY_CUTAWAY,
        DetailPassSpec,
    )


# ─────────────────────────────────────────────────────────────
# Profile definitions
# ─────────────────────────────────────────────────────────────

_PROFILES: Dict[str, Dict[str, Any]] = {

    LOD0_SILHOUETTE: {
        "label": "Silhouette only",
        "description": "Outer hull / body silhouette with no internal detail.",
        "visibility_mode": VISIBILITY_OPAQUE,
        "include_internals": False,
        "include_labels": False,
        "include_fasteners": False,
        "include_ribs_bulkheads": False,
        "include_cable_corridors": False,
        "include_outer_shell": True,
        "include_components": False,
        "detail_passes": [
            DetailPassSpec("outer_shell", "shell", LOD0_SILHOUETTE),
        ],
    },

    LOD1_MORPHOLOGY: {
        "label": "Morphology layout",
        "description": "Body segmentation and appendages. No internals.",
        "visibility_mode": VISIBILITY_OPAQUE,
        "include_internals": False,
        "include_labels": True,
        "include_fasteners": False,
        "include_ribs_bulkheads": False,
        "include_cable_corridors": False,
        "include_outer_shell": True,
        "include_components": False,
        "detail_passes": [
            DetailPassSpec("outer_shell", "shell", LOD1_MORPHOLOGY),
            DetailPassSpec("labels",      "labels", LOD1_MORPHOLOGY),
        ],
    },

    LOD2_MECHANICAL_PLACEHOLDERS: {
        "label": "Mechanical placeholders",
        "description": "Outer shell + major component placeholder blocks (motor, battery, sensor).",
        "visibility_mode": VISIBILITY_OPAQUE,
        "include_internals": False,
        "include_labels": True,
        "include_fasteners": False,
        "include_ribs_bulkheads": False,
        "include_cable_corridors": False,
        "include_outer_shell": True,
        "include_components": True,
        "detail_passes": [
            DetailPassSpec("outer_shell",  "shell",       LOD2_MECHANICAL_PLACEHOLDERS),
            DetailPassSpec("components",   "internals",   LOD2_MECHANICAL_PLACEHOLDERS),
            DetailPassSpec("labels",       "labels",      LOD2_MECHANICAL_PLACEHOLDERS),
        ],
    },

    LOD3_INTERNAL_ASSEMBLY: {
        "label": "Internal assembly",
        "description": "Full internal component layout, mounting features, structural ribs, cable corridors.",
        "visibility_mode": VISIBILITY_OPAQUE,
        "include_internals": True,
        "include_labels": True,
        "include_fasteners": True,
        "include_ribs_bulkheads": True,
        "include_cable_corridors": True,
        "include_outer_shell": True,
        "include_components": True,
        "detail_passes": [
            DetailPassSpec("outer_shell",     "shell",       LOD3_INTERNAL_ASSEMBLY),
            DetailPassSpec("components",      "internals",   LOD3_INTERNAL_ASSEMBLY),
            DetailPassSpec("structural",      "structure",   LOD3_INTERNAL_ASSEMBLY),
            DetailPassSpec("fasteners",       "fasteners",   LOD3_INTERNAL_ASSEMBLY),
            DetailPassSpec("cable_corridors", "structure",   LOD3_INTERNAL_ASSEMBLY),
            DetailPassSpec("labels",          "labels",      LOD3_INTERNAL_ASSEMBLY),
        ],
    },

    LOD4_TRANSPARENT_CUTAWAY: {
        "label": "Transparent cutaway",
        "description": "All LOD3 content with transparent/cutaway top shell to expose internals.",
        "visibility_mode": VISIBILITY_CUTAWAY,
        "include_internals": True,
        "include_labels": True,
        "include_fasteners": True,
        "include_ribs_bulkheads": True,
        "include_cable_corridors": True,
        "include_outer_shell": True,
        "include_components": True,
        "detail_passes": [
            DetailPassSpec("outer_shell",     "shell",       LOD4_TRANSPARENT_CUTAWAY),
            DetailPassSpec("cutaway_marker",  "shell",       LOD4_TRANSPARENT_CUTAWAY),
            DetailPassSpec("components",      "internals",   LOD4_TRANSPARENT_CUTAWAY),
            DetailPassSpec("structural",      "structure",   LOD4_TRANSPARENT_CUTAWAY),
            DetailPassSpec("fasteners",       "fasteners",   LOD4_TRANSPARENT_CUTAWAY),
            DetailPassSpec("cable_corridors", "structure",   LOD4_TRANSPARENT_CUTAWAY),
            DetailPassSpec("labels",          "labels",      LOD4_TRANSPARENT_CUTAWAY),
        ],
    },
}

# ─────────────────────────────────────────────────────────────
# High-detail keyword triggers
# ─────────────────────────────────────────────────────────────

_HIGH_DETAIL_KEYWORDS = [
    "detailed",
    "detail",
    "engineered",
    "cutaway",
    "transparent",
    "internal",
    "cross section",
    "cross-section",
    "assembly",
    "exploded",
    "components",
    "wiring",
    "electronics bay",
    "battery bay",
    "high detail",
    "lod3",
    "lod4",
]

_CUTAWAY_KEYWORDS = [
    "cutaway",
    "transparent",
    "cross section",
    "cross-section",
    "exploded",
    "see through",
    "see-through",
    "lod4",
]


# ─────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────

def get_detail_profile(level: str) -> Dict[str, Any]:
    """
    Return a copy of the profile dict for the given level string.
    Falls back to LOD2 if the level is unrecognised.
    """
    key = str(level or LOD2_MECHANICAL_PLACEHOLDERS)
    profile = _PROFILES.get(key) or _PROFILES[LOD2_MECHANICAL_PLACEHOLDERS]
    # Return a shallow copy so callers cannot mutate the registry
    result = dict(profile)
    result["detail_passes"] = list(profile["detail_passes"])
    return result


def default_detail_level_for_mission(mission_text: str) -> str:
    """
    Heuristic: scan mission text for detail / cutaway keywords.

    Returns one of the LOD constants.
    """
    text = str(mission_text or "").lower()

    # Cutaway / transparent -> LOD4
    if any(kw in text for kw in _CUTAWAY_KEYWORDS):
        return LOD4_TRANSPARENT_CUTAWAY

    # High-detail assembly -> LOD3
    if any(kw in text for kw in _HIGH_DETAIL_KEYWORDS):
        return LOD3_INTERNAL_ASSEMBLY

    # Default for most missions
    return LOD2_MECHANICAL_PLACEHOLDERS


def resolve_detail_profile(
    mission_text: str,
    morphology_spec: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Choose and return a detail profile dict based on mission text and morphology spec.

    Priority:
    1. Explicit LOD keyword in mission text
    2. Cutaway / transparent keyword -> LOD4
    3. High-detail keyword -> LOD3
    4. morphology_spec.cad_detail_level override (future)
    5. Default: LOD2
    """
    text = str(mission_text or "").lower()

    # Check for explicit LOD strings
    for level in reversed(DETAIL_LEVELS):
        short = level.lower().replace("_", "").replace("lod", "lod")
        if short in text.replace(" ", "").replace("_", ""):
            return get_detail_profile(level)

    # Check morphology spec override
    if isinstance(morphology_spec, dict):
        spec_level = morphology_spec.get("cad_detail_level")
        if spec_level and spec_level in _PROFILES:
            return get_detail_profile(spec_level)

    # Heuristic keyword scan
    level = default_detail_level_for_mission(mission_text)
    return get_detail_profile(level)


def visibility_for_mission(mission_text: str) -> str:
    """Convenience: return VISIBILITY_CUTAWAY or VISIBILITY_OPAQUE."""
    text = str(mission_text or "").lower()
    if any(kw in text for kw in _CUTAWAY_KEYWORDS):
        return VISIBILITY_CUTAWAY
    return VISIBILITY_OPAQUE