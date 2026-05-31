"""
OMNI Phase 16L — Visual Bay GLTF preview generator.

Writes a minimal, text-based, valid GLTF 2.0 placeholder into
generated_visual_bay/preview_scene.gltf when the mission has detected
visual artifacts (Fusion 360, CadQuery, ROS2, or simulation).

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
from typing import Any, Dict, Optional

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


def _build_placeholder_buffer() -> tuple:
    """
    Build an embedded base64 GLTF buffer for a small abstract pyramid marker.

    Buffer layout (72 bytes total):
      bytes  0-47: POSITION float32 × 4 vertices × 3 components (xyz)
      bytes 48-71: INDEX uint16 × 4 triangles × 3 indices

    Returns (data_uri, pos_byte_offset, idx_byte_offset, total_byte_length).

    No engineering geometry — purely abstract browser placeholder.
    """
    vertices = [
        ( 0.0,  0.5,  0.0),   # apex
        (-0.5, -0.25, -0.5),  # base left-back
        ( 0.5, -0.25, -0.5),  # base right-back
        ( 0.0, -0.25,  0.5),  # base front
    ]
    pos_bytes = bytearray()
    for vx, vy, vz in vertices:
        pos_bytes += struct.pack("<fff", vx, vy, vz)

    index_list = [
        1, 3, 2,   # base
        0, 1, 2,   # side A
        0, 2, 3,   # side B
        0, 3, 1,   # side C
    ]
    idx_bytes = bytearray()
    for idx in index_list:
        idx_bytes += struct.pack("<H", idx)

    pos_offset = 0
    idx_offset = len(pos_bytes)          # 48
    raw        = bytes(pos_bytes) + bytes(idx_bytes)
    data_uri   = (
        "data:application/octet-stream;base64,"
        + base64.b64encode(raw).decode("ascii")
    )
    return data_uri, pos_offset, idx_offset, len(raw)


def _build_preview_gltf_payload(
    manifest: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    extras: Dict[str, Any] = {
        "generated_by": "omni_visual_bay",
        "phase":        "16L",
        "note":         _SAFETY_NOTE,
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

    data_uri, pos_offset, idx_offset, buf_len = _build_placeholder_buffer()

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
                "name": "placeholder_pyramid",
                "primitives": [
                    {
                        "attributes": {"POSITION": 1},
                        "indices":    0,
                        "material":   0,
                    }
                ],
            }
        ],
        "accessors": [
            {
                # accessor 0 — indices (UNSIGNED_SHORT SCALAR ×12)
                "bufferView":    0,
                "byteOffset":    0,
                "componentType": 5123,   # UNSIGNED_SHORT
                "count":         12,
                "type":          "SCALAR",
            },
            {
                # accessor 1 — POSITION (FLOAT VEC3 ×4)
                "bufferView":    1,
                "byteOffset":    0,
                "componentType": 5126,   # FLOAT
                "count":         4,
                "type":          "VEC3",
                "min":           [-0.5, -0.25, -0.5],
                "max":           [ 0.5,  0.5,   0.5],
            },
        ],
        "bufferViews": [
            {
                # bufferView 0 — index data
                "buffer":     0,
                "byteOffset": idx_offset,   # 48
                "byteLength": 24,
                "target":     34963,        # ELEMENT_ARRAY_BUFFER
            },
            {
                # bufferView 1 — position data
                "buffer":     0,
                "byteOffset": pos_offset,   # 0
                "byteLength": 48,
                "target":     34962,        # ARRAY_BUFFER
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
                    "baseColorFactor": [0.2, 0.6, 1.0, 1.0],
                    "metallicFactor":  0.0,
                    "roughnessFactor": 0.8,
                },
            }
        ],
        "extras": extras,
    }


def write_visual_bay_gltf_preview(
    export_dir: Path,
    manifest: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Write a minimal GLTF 2.0 preview placeholder into
    export_dir/generated_visual_bay/preview_scene.gltf.

    Returns:
        {"written": True,  "path": <rel str>, "abs_path": <Path>}
        {"written": False, "reason": <str>}  on failure.
    """
    try:
        out_dir = export_dir / _PREVIEW_GLTF_SUBDIR
        out_dir.mkdir(parents=True, exist_ok=True)

        gltf_path = out_dir / _PREVIEW_GLTF_NAME
        payload   = _build_preview_gltf_payload(manifest)
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
