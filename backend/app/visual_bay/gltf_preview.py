"""
OMNI Phase 16K — Visual Bay GLTF preview generator.

Writes a minimal, text-based, valid GLTF 2.0 placeholder into
generated_visual_bay/preview_scene.gltf when the mission has detected
visual artifacts (Fusion 360, CadQuery, ROS2, or simulation).

Browser visualization only.
- No CAD computation performed.
- No simulation launched.
- No scripts executed.
- No engineering validation implied.
- Not fabrication-ready.
- Do not claim CAD accuracy.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional

_PREVIEW_GLTF_SUBDIR = "generated_visual_bay"
_PREVIEW_GLTF_NAME   = "preview_scene.gltf"

_SAFETY_NOTE = (
    "Browser visualization placeholder only. "
    "No engineering validation implied. "
    "No simulation launched. "
    "No scripts executed. "
    "Not fabrication-ready."
)


def _build_preview_gltf_payload(
    manifest: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    extras: Dict[str, Any] = {
        "generated_by": "omni_visual_bay",
        "phase":        "16K",
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

    return {
        "asset": {
            "version":   "2.0",
            "generator": "OMNI Visual Bay Phase 16K",
        },
        "scene":  0,
        "scenes": [{"name": "preview", "nodes": [0]}],
        "nodes":  [{"name": "preview_root"}],
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
