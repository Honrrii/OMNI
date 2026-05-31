"""
OMNI Phase 16P — Visual Bay GLTF preview generator.
Mission-aware abstract placeholder geometry.

Writes a valid GLTF 2.0 placeholder into
generated_visual_bay/preview_scene.gltf.

Browser visualization only.
- No CAD computation performed.
- No simulation launched.
- No scripts executed.
- No engineering validation implied.
- Not fabrication-ready.
- Not CAD-accurate.
- Concept preview placeholder only.
"""
from __future__ import annotations

import base64
import json
import struct
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

_PREVIEW_GLTF_SUBDIR = "generated_visual_bay"
_PREVIEW_GLTF_NAME   = "preview_scene.gltf"

_SAFETY_NOTE = (
    "Concept preview placeholder only. "
    "Not engineering CAD. "
    "Not CAD-accurate. "
    "Not fabrication-ready. "
    "No engineering validation implied. "
    "No simulation launched. "
    "No scripts executed."
)

# ---------------------------------------------------------------------------
# Platform classification
# ---------------------------------------------------------------------------

_UAV_KEYWORDS = frozenset({
    "drone", "uav", "quadcopter", "quadrotor", "multirotor",
    "aerial", "hexacopter", "octocopter", "vtol", "rotor",
    "propeller", "airborne",
})

_ROVER_KEYWORDS = frozenset({
    "rover", "crawler", "wheeled", "tracked robot",
    "ground vehicle", "ground robot", "patrol",
    "magnetic crawler", "wall crawler", "inspection crawler",
    "rolling robot",
})

_MANIPULATOR_KEYWORDS = frozenset({
    "manipulator", "robot arm", "robotic arm", "gripper",
    "6-dof", "7-dof", "pick and place", "articulated arm",
    "serial link",
})


def _classify_from_text(text: str) -> Optional[str]:
    t = text.lower()
    if any(kw in t for kw in _UAV_KEYWORDS):
        return "abstract_uav_marker"
    if any(kw in t for kw in _ROVER_KEYWORDS):
        return "abstract_rover_marker"
    if any(kw in t for kw in _MANIPULATOR_KEYWORDS):
        return "abstract_manipulator_marker"
    return None


def _platform_intent_to_kind(platform_intent: str) -> Optional[str]:
    p = platform_intent.lower()
    if any(kw in p for kw in ("drone", "uav", "quadcopter", "aerial", "multirotor", "vtol", "rotor")):
        return "abstract_uav_marker"
    if any(kw in p for kw in ("rover", "crawler", "ground", "wheeled", "tracked")):
        return "abstract_rover_marker"
    if any(kw in p for kw in ("arm", "manipulator", "gripper")):
        return "abstract_manipulator_marker"
    return None


def _extract_mission_text(mission_result: Dict[str, Any]) -> str:
    if not isinstance(mission_result, dict):
        return ""
    return (
        mission_result.get("mission")
        or mission_result.get("mission_text")
        or mission_result.get("prompt")
        or mission_result.get("user_prompt")
        or mission_result.get("title")
        or mission_result.get("summary")
        or ""
    )


def _classify_placeholder_kind(
    mission_result: Optional[Dict[str, Any]],
) -> Tuple[str, str]:
    """
    Returns (placeholder_kind, classification_source).

    Priority:
    1. mission_result.artifacts.mission_intent.platform_intent
    2. mission text keyword scan
    3. generic fallback
    """
    if not isinstance(mission_result, dict):
        return "abstract_generic_marker", "fallback"

    artifacts = mission_result.get("artifacts", {})
    if isinstance(artifacts, dict):
        intent = artifacts.get("mission_intent", {})
        if isinstance(intent, dict):
            platform = str(intent.get("platform_intent", "")).strip()
            if platform:
                kind = _platform_intent_to_kind(platform)
                if kind:
                    return kind, "mission_intent.platform_intent"

    text = _extract_mission_text(mission_result)
    if text:
        kind = _classify_from_text(text)
        if kind:
            return kind, "mission_text_keywords"

    return "abstract_generic_marker", "fallback"


# ---------------------------------------------------------------------------
# Shape geometry (non-indexed triangle lists)
# ---------------------------------------------------------------------------

# Each triangle is ((x0,y0,z0), (x1,y1,z1), (x2,y2,z2)).
# Shapes are purely abstract — no engineering dimensions.

_Vertex   = Tuple[float, float, float]
_Triangle = Tuple[_Vertex, _Vertex, _Vertex]


def _generic_beacon_triangles() -> List[_Triangle]:
    """Abstract pyramid beacon — generic fallback."""
    v0 = ( 0.0,  0.5,  0.0)
    v1 = (-0.5, -0.25, -0.5)
    v2 = ( 0.5, -0.25, -0.5)
    v3 = ( 0.0, -0.25,  0.5)
    return [
        (v1, v3, v2),
        (v0, v1, v2),
        (v0, v2, v3),
        (v0, v3, v1),
    ]


def _uav_marker_triangles() -> List[_Triangle]:
    """
    Abstract UAV marker: small central pyramid + 4 flat arm tip markers.
    No motor specs, propeller geometry, or flight-ready claims.
    """
    c0 = ( 0.0,  0.18,  0.0)
    c1 = (-0.15,  0.0, -0.15)
    c2 = ( 0.15,  0.0, -0.15)
    c3 = ( 0.0,   0.0,  0.2)
    body: List[_Triangle] = [
        (c1, c3, c2),
        (c0, c1, c2),
        (c0, c2, c3),
        (c0, c3, c1),
    ]
    arms: List[_Triangle] = [
        # front
        (( 0.0,  0.02,  0.65), (-0.09, 0.02,  0.28), ( 0.09, 0.02,  0.28)),
        # back
        (( 0.0,  0.02, -0.65), ( 0.09, 0.02, -0.28), (-0.09, 0.02, -0.28)),
        # left
        ((-0.65, 0.02,  0.0),  (-0.28, 0.02,  0.09), (-0.28, 0.02, -0.09)),
        # right
        (( 0.65, 0.02,  0.0),  ( 0.28, 0.02, -0.09), ( 0.28, 0.02,  0.09)),
    ]
    return body + arms


def _rover_marker_triangles() -> List[_Triangle]:
    """
    Abstract rover marker: wide squat body + 4 corner wheel markers.
    No drivetrain detail, no fabrication claims.
    """
    r0 = ( 0.0,  0.12,  0.0)
    r1 = (-0.4,  0.0,  -0.3)
    r2 = ( 0.4,  0.0,  -0.3)
    r3 = ( 0.4,  0.0,   0.3)
    r4 = (-0.4,  0.0,   0.3)
    body: List[_Triangle] = [
        (r1, r2, r3), (r1, r3, r4),
        (r0, r1, r2),
        (r0, r2, r3),
        (r0, r3, r4),
        (r0, r4, r1),
    ]
    wheels: List[_Triangle] = [
        (( 0.55, 0.0,  0.4),  ( 0.38, 0.0,  0.55), ( 0.38, 0.0,  0.25)),
        ((-0.55, 0.0,  0.4),  (-0.38, 0.0,  0.25), (-0.38, 0.0,  0.55)),
        (( 0.55, 0.0, -0.4),  ( 0.38, 0.0, -0.25), ( 0.38, 0.0, -0.55)),
        ((-0.55, 0.0, -0.4),  (-0.38, 0.0, -0.55), (-0.38, 0.0, -0.25)),
    ]
    return body + wheels


def _manipulator_marker_triangles() -> List[_Triangle]:
    """
    Abstract manipulator marker: 3 stacked link-like pyramids.
    No joint dimensions, torque specs, or fabrication claims.
    """
    base_link: List[_Triangle] = [
        ((-0.18, 0.0, -0.18), ( 0.0, 0.0,  0.22), (0.18, 0.0, -0.18)),
        (( 0.0,  0.22,  0.0), (-0.18, 0.0, -0.18), (0.18, 0.0, -0.18)),
        (( 0.0,  0.22,  0.0), ( 0.18, 0.0, -0.18), (0.0,  0.0,  0.22)),
        (( 0.0,  0.22,  0.0), ( 0.0,  0.0,  0.22), (-0.18, 0.0, -0.18)),
    ]
    mid_link: List[_Triangle] = [
        (( 0.05, 0.3, -0.1),  ( 0.2,  0.3,  0.05), (-0.1, 0.3,  0.05)),
        (( 0.05, 0.55, -0.02),(0.05,  0.3,  -0.1),  ( 0.2, 0.3,  0.05)),
        (( 0.05, 0.55, -0.02),( 0.2,  0.3,   0.05), (-0.1, 0.3,  0.05)),
        (( 0.05, 0.55, -0.02),(-0.1,  0.3,   0.05), ( 0.05, 0.3, -0.1)),
    ]
    end_tip: List[_Triangle] = [
        (( 0.1,  0.65, -0.08), (0.22, 0.65,  0.04), (0.0,  0.65,  0.04)),
        (( 0.12, 0.82,  0.0),  (0.1,  0.65, -0.08), (0.22, 0.65,  0.04)),
        (( 0.12, 0.82,  0.0),  (0.22, 0.65,  0.04), (0.0,  0.65,  0.04)),
        (( 0.12, 0.82,  0.0),  (0.0,  0.65,  0.04), (0.1,  0.65, -0.08)),
    ]
    return base_link + mid_link + end_tip


_SHAPE_TRIANGLES: Dict[str, Any] = {
    "abstract_uav_marker":         _uav_marker_triangles,
    "abstract_rover_marker":       _rover_marker_triangles,
    "abstract_manipulator_marker": _manipulator_marker_triangles,
    "abstract_generic_marker":     _generic_beacon_triangles,
}

_SHAPE_COLORS: Dict[str, List[float]] = {
    "abstract_uav_marker":         [1.0, 0.55, 0.1],   # amber
    "abstract_rover_marker":       [0.2, 0.75, 0.3],   # green
    "abstract_manipulator_marker": [0.6, 0.3,  0.9],   # purple
    "abstract_generic_marker":     [0.2, 0.6,  1.0],   # blue
}


# ---------------------------------------------------------------------------
# GLTF buffer builder
# ---------------------------------------------------------------------------

def _make_buffer_from_triangles(
    triangles: List[_Triangle],
) -> Tuple[str, int, List[float], List[float], int]:
    """
    Pack triangle vertices into a float32 GLTF position buffer (non-indexed).
    Returns (data_uri, vertex_count, min_xyz, max_xyz, byte_length).
    """
    xs: List[float] = []
    ys: List[float] = []
    zs: List[float] = []
    pos_bytes = bytearray()
    for tri in triangles:
        for vx, vy, vz in tri:
            pos_bytes += struct.pack("<fff", vx, vy, vz)
            xs.append(vx)
            ys.append(vy)
            zs.append(vz)
    raw      = bytes(pos_bytes)
    data_uri = (
        "data:application/octet-stream;base64,"
        + base64.b64encode(raw).decode("ascii")
    )
    return (
        data_uri,
        len(triangles) * 3,
        [min(xs), min(ys), min(zs)],
        [max(xs), max(ys), max(zs)],
        len(raw),
    )


# ---------------------------------------------------------------------------
# GLTF payload builder
# ---------------------------------------------------------------------------

def _build_preview_gltf_payload(
    manifest: Optional[Dict[str, Any]] = None,
    mission_result: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    placeholder_kind, classification_source = _classify_placeholder_kind(mission_result)

    extras: Dict[str, Any] = {
        "generated_by":          "omni_visual_bay",
        "phase":                 "16P",
        "placeholder_kind":      placeholder_kind,
        "classification_source": classification_source,
        "note":                  _SAFETY_NOTE,
    }

    if manifest:
        sources: list = []
        if manifest.get("fusion360", {}).get("detected"):
            sources.append("fusion360")
        if manifest.get("cadquery", {}).get("detected"):
            sources.append("cadquery")
        if manifest.get("ros2_preview", {}).get("detected"):
            sources.append("ros2")
        if manifest.get("simulation", {}).get("status") != "not_available":
            sources.append("simulation")
        if sources:
            extras["artifact_sources"] = sources

    shape_fn  = _SHAPE_TRIANGLES.get(placeholder_kind, _generic_beacon_triangles)
    triangles = shape_fn()
    color     = _SHAPE_COLORS.get(placeholder_kind, [0.2, 0.6, 1.0])

    data_uri, vertex_count, min_xyz, max_xyz, buf_len = _make_buffer_from_triangles(triangles)

    return {
        "asset": {
            "version":   "2.0",
            "generator": "OMNI Visual Bay placeholder",
        },
        "scene":  0,
        "scenes": [{"name": "preview", "nodes": [0]}],
        "nodes":  [{"name": "preview_marker", "mesh": 0}],
        "meshes": [
            {
                "name": f"placeholder_{placeholder_kind}",
                "primitives": [
                    {
                        "attributes": {"POSITION": 0},
                        "material":   0,
                    }
                ],
            }
        ],
        "accessors": [
            {
                # accessor 0 — POSITION (FLOAT VEC3, non-indexed)
                "bufferView":    0,
                "byteOffset":    0,
                "componentType": 5126,   # FLOAT
                "count":         vertex_count,
                "type":          "VEC3",
                "min":           min_xyz,
                "max":           max_xyz,
            },
        ],
        "bufferViews": [
            {
                "buffer":     0,
                "byteOffset": 0,
                "byteLength": buf_len,
                "target":     34962,     # ARRAY_BUFFER
            },
        ],
        "buffers": [
            {
                "uri":        data_uri,
                "byteLength": buf_len,
            }
        ],
        "materials": [
            {
                "name": "placeholder_material",
                "pbrMetallicRoughness": {
                    "baseColorFactor": color + [1.0],
                    "metallicFactor":  0.0,
                    "roughnessFactor": 0.8,
                },
            }
        ],
        "extras": extras,
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def write_visual_bay_gltf_preview(
    export_dir: Path,
    manifest: Optional[Dict[str, Any]] = None,
    mission_result: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Write a mission-aware GLTF 2.0 abstract placeholder into
    export_dir/generated_visual_bay/preview_scene.gltf.

    Returns:
        {"written": True,  "path": <rel str>, "abs_path": <Path>}
        {"written": False, "reason": <str>}  on failure.
    """
    try:
        out_dir = export_dir / _PREVIEW_GLTF_SUBDIR
        out_dir.mkdir(parents=True, exist_ok=True)

        gltf_path = out_dir / _PREVIEW_GLTF_NAME
        payload   = _build_preview_gltf_payload(manifest, mission_result)
        gltf_path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        return {
            "written":  True,
            "path":     str(gltf_path.relative_to(export_dir)),
            "abs_path": gltf_path,
        }
    except Exception as exc:
        return {"written": False, "reason": str(exc)}
