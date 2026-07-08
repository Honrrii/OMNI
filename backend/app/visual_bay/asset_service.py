"""
Visual Bay asset serving contract.

Deterministic, read-only helpers for safe preview-asset serving.
No execution. No script running. No path traversal. No arbitrary filesystem access.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

# ---------------------------------------------------------------------------
# Extension policy
# ---------------------------------------------------------------------------

# Files that may be served for read-only preview / metadata download.
_SERVABLE_SUFFIXES: frozenset = frozenset({
    ".glb",
    ".gltf",
    ".stl",
    ".obj",
    ".step",
    ".stp",
    ".iges",
    ".igs",
    ".urdf",
    ".xacro",
    ".rviz",
    ".yaml",
    ".yml",
    ".json",
    ".md",
})

# Extensions that must never be served, regardless of anything else.
_BLOCKED_SUFFIXES: frozenset = frozenset({
    ".py",
    ".sh",
    ".bash",
    ".zsh",
    ".fish",
    ".exe",
    ".bin",
    ".so",
    ".dylib",
    ".dll",
    ".bat",
    ".cmd",
})

# Filename endings for launch / automation files (checked before suffix).
_BLOCKED_NAME_ENDINGS = (
    ".launch.py",
    ".launch.xml",
    ".launch",
)


def _is_path_extension_servable(path_str: str) -> bool:
    """Return True only if the file has a servable, non-blocked extension."""
    name = Path(path_str).name.lower()
    if any(name.endswith(e) for e in _BLOCKED_NAME_ENDINGS):
        return False
    suffix = Path(path_str).suffix.lower()
    if suffix in _BLOCKED_SUFFIXES:
        return False
    return suffix in _SERVABLE_SUFFIXES


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def resolve_visual_bay_asset(export_dir: Path, asset_path: str) -> Optional[Path]:
    """
    Safely resolve *asset_path* relative to *export_dir*.

    Returns None (never raises) when:
    - asset_path is empty
    - asset_path is absolute
    - asset_path contains ``..`` traversal components
    - resolved path escapes export_dir (symlink or trick)
    - the resolved path is not a regular file
    """
    if not asset_path:
        return None

    # Reject absolute paths before any resolution.
    if Path(asset_path).is_absolute():
        return None

    # Reject traversal components in every platform's separator variant.
    parts = asset_path.replace("\\", "/").split("/")
    if ".." in parts:
        return None

    try:
        canonical_root = Path(export_dir).resolve()
        candidate = (canonical_root / asset_path).resolve()
        candidate.relative_to(canonical_root)  # raises ValueError if outside
    except (ValueError, OSError):
        return None

    if not candidate.is_file():
        return None

    return candidate


def is_visual_bay_asset_servable(asset: Dict[str, Any]) -> bool:
    """
    Return True if *asset* may be served for read-only preview.

    An asset is NOT servable when:
    - ``execution_blocked`` is True in the manifest contract
    - the file extension is not in the servable allowlist
    - the extension is in the blocked set (script/binary)
    """
    if not isinstance(asset, dict):
        return False
    if asset.get("execution_blocked"):
        return False
    return _is_path_extension_servable(str(asset.get("path", "")))


def build_visual_bay_asset_url(mission_id: str, asset_path: str) -> str:
    """Return the API URL for a servable Visual Bay asset."""
    return f"/api/visual-bay/assets/{mission_id}/{asset_path}"
