"""
Visual Bay API routes.

Safe, read-only endpoints for Visual Bay manifest access and preview asset serving.
No execution. No script running. No path traversal. No arbitrary filesystem access.
"""
from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse, JSONResponse

from backend.app.export.export_manager import OUTPUT_ROOT
from backend.app.visual_bay.asset_service import (
    resolve_visual_bay_asset,
    _is_path_extension_servable,
)

router = APIRouter()


def _mission_export_dir(mission_id: str) -> Path:
    """Resolve the export directory for a given mission_id (folder name)."""
    return OUTPUT_ROOT / mission_id


def _reject_mission_id(mission_id: str) -> bool:
    """Return True if mission_id contains traversal or path separator characters."""
    return ".." in mission_id or "/" in mission_id or "\\" in mission_id


# ---------------------------------------------------------------------------
# GET /manifest/{mission_id}
# ---------------------------------------------------------------------------

@router.get("/manifest/{mission_id}")
def get_visual_bay_manifest(mission_id: str) -> JSONResponse:
    """
    Return the visual_bay_manifest.json for a mission export.

    Read-only. Does not execute anything.
    Returns 404 JSON if the manifest file is missing.
    Returns 400 JSON if mission_id is invalid.
    """
    if _reject_mission_id(mission_id):
        return JSONResponse(
            status_code=400,
            content={"status": "blocked", "reason": "Invalid mission_id."},
        )

    manifest_path = _mission_export_dir(mission_id) / "visual_bay_manifest.json"

    if not manifest_path.is_file():
        return JSONResponse(
            status_code=404,
            content={
                "status": "not_found",
                "reason": "visual_bay_manifest.json not found for this mission.",
            },
        )

    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
        return JSONResponse(content=data)
    except Exception as exc:
        return JSONResponse(
            status_code=500,
            content={"status": "error", "reason": f"Failed to read manifest: {exc}"},
        )


# ---------------------------------------------------------------------------
# GET /assets/{mission_id}/{asset_path:path}
# ---------------------------------------------------------------------------

@router.get("/assets/{mission_id}/{asset_path:path}")
def get_visual_bay_asset(mission_id: str, asset_path: str):
    """
    Serve a Visual Bay preview asset file (read-only).

    Rejects:
    - mission_id with path-traversal characters
    - absolute asset_path
    - asset_path with ``..`` traversal
    - blocked/script file extensions (.py, .sh, .launch.py, etc.)
    - files not present or outside the mission export folder

    Returns FileResponse for allowed files.
    Returns structured JSON error for blocked or missing assets.
    """
    if _reject_mission_id(mission_id):
        return JSONResponse(
            status_code=400,
            content={"status": "blocked", "reason": "Invalid mission_id."},
        )

    export_dir = _mission_export_dir(mission_id)

    if not export_dir.is_dir():
        return JSONResponse(
            status_code=404,
            content={"status": "not_found", "reason": "Mission export folder not found."},
        )

    # Reject absolute asset paths before any filesystem access.
    if Path(asset_path).is_absolute():
        return JSONResponse(
            status_code=400,
            content={"status": "blocked", "reason": "Absolute paths are not allowed."},
        )

    # Reject traversal in asset_path.
    parts = asset_path.replace("\\", "/").split("/")
    if ".." in parts:
        return JSONResponse(
            status_code=400,
            content={"status": "blocked", "reason": "Path traversal is not allowed."},
        )

    # Check extension allowlist before any filesystem resolution.
    if not _is_path_extension_servable(asset_path):
        return JSONResponse(
            status_code=403,
            content={
                "status": "blocked",
                "reason": (
                    "This file type is not servable. "
                    "Script and execution-capable files are blocked."
                ),
            },
        )

    # Safe resolution — also validates the file stays inside export_dir.
    resolved = resolve_visual_bay_asset(export_dir, asset_path)

    if resolved is None:
        return JSONResponse(
            status_code=404,
            content={
                "status": "not_found",
                "reason": "Asset not found in mission export folder.",
            },
        )

    return FileResponse(path=str(resolved))
