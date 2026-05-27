"""
OMNI Phase 16A/16C — Visual Bay manifest: deterministic mission visual artifact scanner.

Summarizes which CAD, CadQuery, Fusion 360, ROS2, and simulation assets exist
inside an export directory. Does NOT render 3D, launch simulators, or execute
generated scripts.

Phase 16C adds a preview_assets contract: each discovered file gets a compact
object describing its browser-preview readiness, execution safety, and next-step
requirements.

No LLM calls. No network calls. No file execution.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

MODULE_NAME = "visual_bay"

# ---------------------------------------------------------------------------
# Blocked actions that must always be present
# ---------------------------------------------------------------------------

_BLOCKED_ACTIONS: List[str] = [
    "Do not launch generated simulation automatically without validation.",
    "Do not execute generated scripts from the browser.",
    "Hardware deployment requires human review.",
]

# ---------------------------------------------------------------------------
# File-suffix sets
# ---------------------------------------------------------------------------

_BROWSER_PREVIEW_SUFFIXES = {".glb", ".gltf"}
_MESH_SUFFIXES = {".stl", ".obj"}
_ENGINEERING_CAD_SUFFIXES = {".step", ".stp", ".iges", ".igs"}
_LAUNCH_SUFFIXES = {".launch.py", ".launch.xml", ".launch"}
_URDF_SUFFIXES = {".urdf", ".xacro"}
_SIM_WORLD_SUFFIXES = {".world", ".gazebo", ".sdf"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _dir_exists(base: Path, name: str) -> bool:
    return (base / name).is_dir()


def _file_exists(base: Path, name: str) -> bool:
    return (base / name).is_file()


def _rglob_suffixes(base: Path, suffixes: set) -> List[str]:
    """Return relative path strings for all files matching any of the given suffixes."""
    if not base.is_dir():
        return []
    results: List[str] = []
    for path in base.rglob("*"):
        if path.is_file() and path.suffix.lower() in suffixes:
            try:
                results.append(str(path.relative_to(base)))
            except ValueError:
                results.append(str(path))
    return sorted(results)


def _rglob_name(base: Path, filename: str) -> List[str]:
    """Return relative path strings for all files with exactly this name."""
    if not base.is_dir():
        return []
    results: List[str] = []
    for path in base.rglob(filename):
        if path.is_file():
            try:
                results.append(str(path.relative_to(base)))
            except ValueError:
                results.append(str(path))
    return sorted(results)


def _rglob_launch_files(base: Path) -> List[str]:
    """Find launch files by checking if the full filename ends with a launch suffix."""
    if not base.is_dir():
        return []
    results: List[str] = []
    for path in base.rglob("*"):
        if not path.is_file():
            continue
        name = path.name.lower()
        if any(name.endswith(s) for s in _LAUNCH_SUFFIXES):
            try:
                results.append(str(path.relative_to(base)))
            except ValueError:
                results.append(str(path))
    return sorted(results)


# ---------------------------------------------------------------------------
# Preview asset contract (Phase 16C)
# ---------------------------------------------------------------------------

def _classify_asset_file(
    path: Path,
    export_dir: Path,
) -> Optional[Dict[str, Any]]:
    """
    Classify a single file into a preview asset object.

    Returns None for files that are not visual/CAD/ROS2/simulation assets
    (e.g. plain JSON, Markdown, CSV) so they are excluded from preview_assets.
    """
    name   = path.name.lower()
    suffix = path.suffix.lower()

    try:
        rel = str(path.relative_to(export_dir))
    except ValueError:
        rel = str(path)

    # .glb / .gltf — browser-ready
    if suffix in (".glb", ".gltf"):
        return {
            "path":                    rel,
            "kind":                    suffix.lstrip("."),
            "browser_preview_ready":   True,
            "browser_preview_candidate": True,
            "engineering_only":        False,
            "execution_blocked":       False,
            "requires_conversion":     False,
            "requires_external_tool":  False,
            "notes":                   [],
        }

    # .stl / .obj — mesh present, viewer support pending
    if suffix in (".stl", ".obj"):
        return {
            "path":                    rel,
            "kind":                    "stl",
            "browser_preview_ready":   False,
            "browser_preview_candidate": True,
            "engineering_only":        False,
            "execution_blocked":       False,
            "requires_conversion":     False,
            "requires_external_tool":  False,
            "notes":                   ["Viewer support pending"],
        }

    # .step / .stp / .iges / .igs — engineering CAD only
    if suffix in (".step", ".stp", ".iges", ".igs"):
        return {
            "path":                    rel,
            "kind":                    "step",
            "browser_preview_ready":   False,
            "browser_preview_candidate": False,
            "engineering_only":        True,
            "execution_blocked":       False,
            "requires_conversion":     False,
            "requires_external_tool":  True,
            "notes":                   [],
        }

    # .urdf / .xacro — preview candidate, parser not implemented
    if suffix in (".urdf", ".xacro"):
        return {
            "path":                    rel,
            "kind":                    "urdf",
            "browser_preview_ready":   False,
            "browser_preview_candidate": True,
            "engineering_only":        False,
            "execution_blocked":       False,
            "requires_conversion":     True,
            "requires_external_tool":  False,
            "notes":                   ["URDF preview parser not implemented yet"],
        }

    # .rviz — execution blocked, external tool required
    if suffix == ".rviz":
        return {
            "path":                    rel,
            "kind":                    "rviz",
            "browser_preview_ready":   False,
            "browser_preview_candidate": False,
            "engineering_only":        True,
            "execution_blocked":       True,
            "requires_conversion":     False,
            "requires_external_tool":  True,
            "notes":                   [],
        }

    # Launch files (.launch.py / .launch.xml / .launch)
    if any(name.endswith(s) for s in _LAUNCH_SUFFIXES):
        return {
            "path":                    rel,
            "kind":                    "ros2_launch",
            "browser_preview_ready":   False,
            "browser_preview_candidate": False,
            "engineering_only":        True,
            "execution_blocked":       True,
            "requires_conversion":     False,
            "requires_external_tool":  True,
            "notes":                   [],
        }

    # Fusion 360 model generator script (specific filename)
    if name == "fusion360_model_generator.py":
        return {
            "path":                    rel,
            "kind":                    "fusion_script",
            "browser_preview_ready":   False,
            "browser_preview_candidate": False,
            "engineering_only":        True,
            "execution_blocked":       True,
            "requires_conversion":     False,
            "requires_external_tool":  True,
            "notes":                   [],
        }

    # Python scripts inside generated_fusion360/ — Fusion scripts
    if suffix == ".py":
        parts = Path(rel).parts
        if "generated_fusion360" in parts:
            return {
                "path":                    rel,
                "kind":                    "fusion_script",
                "browser_preview_ready":   False,
                "browser_preview_candidate": False,
                "engineering_only":        True,
                "execution_blocked":       True,
                "requires_conversion":     False,
                "requires_external_tool":  True,
                "notes":                   [],
            }
        # Python scripts inside generated_cad/ — CadQuery scripts
        if "generated_cad" in parts:
            return {
                "path":                    rel,
                "kind":                    "cadquery_script",
                "browser_preview_ready":   False,
                "browser_preview_candidate": False,
                "engineering_only":        True,
                "execution_blocked":       True,
                "requires_conversion":     False,
                "requires_external_tool":  True,
                "notes":                   [],
            }

    return None  # not a visual/CAD/ROS2 asset — exclude


def _build_preview_assets(export_dir: Path) -> List[Dict[str, Any]]:
    """
    Walk export_dir recursively and classify every visual/CAD/ROS2/sim file
    into a preview asset object. Returns a deterministically sorted list.
    """
    if not export_dir.is_dir():
        return []
    assets: List[Dict[str, Any]] = []
    seen: set = set()
    for path in sorted(export_dir.rglob("*")):
        if not path.is_file():
            continue
        asset = _classify_asset_file(path, export_dir)
        if asset is None:
            continue
        key = asset["path"]
        if key not in seen:
            seen.add(key)
            assets.append(asset)
    return assets


# ---------------------------------------------------------------------------
# Sub-scanners
# ---------------------------------------------------------------------------

def _scan_fusion360(export_dir: Path) -> Dict[str, Any]:
    """Detect Fusion 360 / general CAD artifacts."""
    fusion_dir = export_dir / "generated_fusion360"
    has_dir = fusion_dir.is_dir()

    script_files = _rglob_name(export_dir, "fusion360_model_generator.py")
    param_files  = _rglob_name(export_dir, "fusion360_parameters.json")
    readme_files = _rglob_name(export_dir, "CAD_README.md")

    glb_files   = _rglob_suffixes(export_dir, _BROWSER_PREVIEW_SUFFIXES)
    stl_files   = _rglob_suffixes(export_dir, _MESH_SUFFIXES)
    step_files  = _rglob_suffixes(export_dir, _ENGINEERING_CAD_SUFFIXES)

    detected = has_dir or bool(script_files or param_files or readme_files)

    browser_preview_ready = bool(glb_files)
    mesh_available        = bool(stl_files)
    engineering_cad       = bool(step_files)

    return {
        "detected":              detected,
        "fusion_dir_present":    has_dir,
        "script_files":          script_files,
        "parameter_files":       param_files,
        "readme_files":          readme_files,
        "glb_files":             glb_files,
        "stl_files":             stl_files,
        "step_files":            step_files,
        "browser_preview_ready": browser_preview_ready,
        "mesh_available":        mesh_available,
        "engineering_cad_available": engineering_cad,
        "preview_only":          True,
        "note": (
            "Fusion 360 scripts are concept-stage only. "
            "Do not execute for fabrication without engineering review."
            if detected else ""
        ),
    }


def _scan_cadquery(export_dir: Path) -> Dict[str, Any]:
    """Detect CadQuery artifacts."""
    cad_dir = export_dir / "generated_cad"
    has_dir = cad_dir.is_dir()

    py_files  = _rglob_suffixes(cad_dir, {".py"}) if has_dir else []
    glb_files = _rglob_suffixes(export_dir, _BROWSER_PREVIEW_SUFFIXES)
    stl_files = _rglob_suffixes(cad_dir, _MESH_SUFFIXES) if has_dir else []
    step_files = _rglob_suffixes(cad_dir, _ENGINEERING_CAD_SUFFIXES) if has_dir else []

    detected = has_dir or bool(py_files)

    browser_preview_ready = bool(glb_files)
    mesh_available        = bool(stl_files)
    engineering_cad       = bool(step_files)

    return {
        "detected":              detected,
        "cad_dir_present":       has_dir,
        "script_files":          py_files,
        "glb_files":             glb_files,
        "stl_files":             stl_files,
        "step_files":            step_files,
        "browser_preview_ready": browser_preview_ready,
        "mesh_available":        mesh_available,
        "engineering_cad_available": engineering_cad,
        "preview_only":          True,
        "note": (
            "CadQuery scripts are concept-stage only. "
            "Do not execute for fabrication without engineering review."
            if detected else ""
        ),
    }


def _scan_ros2(export_dir: Path) -> Dict[str, Any]:
    """Detect ROS2 package artifacts."""
    ros2_dir = export_dir / "generated_ros2"
    has_dir = ros2_dir.is_dir()

    package_xml  = _rglob_name(export_dir, "package.xml")
    launch_files = _rglob_launch_files(export_dir)
    urdf_files   = _rglob_suffixes(export_dir, _URDF_SUFFIXES)
    config_files = _rglob_name(export_dir, "*.yaml") or []

    detected = has_dir or bool(package_xml or launch_files or urdf_files)

    return {
        "detected":          detected,
        "ros2_dir_present":  has_dir,
        "package_xml_files": package_xml,
        "launch_files":      launch_files,
        "urdf_files":        urdf_files,
        "config_files":      config_files,
        "preview_only":      True,
        "note": (
            "ROS2 package is concept-stage scaffold. "
            "Build and deployment require colcon build and hardware review."
            if detected else ""
        ),
    }


def _scan_simulation(export_dir: Path) -> Dict[str, Any]:
    """Detect simulation assets. safe_to_launch is always False."""
    launch_files = _rglob_launch_files(export_dir)
    world_files  = _rglob_suffixes(export_dir, _SIM_WORLD_SUFFIXES)
    rviz_files   = _rglob_name(export_dir, "*.rviz") or []

    has_worlds_dir = _dir_exists(export_dir, "worlds")
    has_models_dir = _dir_exists(export_dir, "models")
    has_gazebo_dir = _dir_exists(export_dir, "gazebo")
    has_rviz_dir   = _dir_exists(export_dir, "rviz")

    sim_dirs_found = has_worlds_dir or has_models_dir or has_gazebo_dir or has_rviz_dir

    if launch_files or world_files or rviz_files:
        status = "launch_files_found" if launch_files else "assets_found"
    elif sim_dirs_found:
        status = "assets_found"
    else:
        status = "not_available"

    return {
        "status":            status,
        "launch_files":      launch_files,
        "world_files":       world_files,
        "rviz_files":        rviz_files,
        "worlds_dir":        has_worlds_dir,
        "models_dir":        has_models_dir,
        "gazebo_dir":        has_gazebo_dir,
        "rviz_dir":          has_rviz_dir,
        "safe_to_launch":    False,
        "preview_only":      True,
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def build_visual_bay_manifest(
    export_dir: Path,
    mission_result: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Scan export_dir for visual artifacts and return a manifest dict.

    Deterministic. No LLM. No network. No file execution. No 3D rendering.

    Args:
        export_dir: Root export directory for this mission.
        mission_result: Optional mission result dict (unused in this phase,
                        reserved for future domain-hint enrichment).

    Returns:
        Manifest dict with module, status, preview_only, sub-sections,
        safety_notes, blocked_actions, and next_steps.
    """
    export_dir = Path(export_dir)

    fusion360 = _scan_fusion360(export_dir)
    cadquery  = _scan_cadquery(export_dir)
    ros2      = _scan_ros2(export_dir)
    simulation = _scan_simulation(export_dir)

    has_cad      = fusion360["detected"] or cadquery["detected"]
    has_ros2     = ros2["detected"]
    has_sim      = simulation["status"] != "not_available"
    browser_ready = fusion360["browser_preview_ready"] or cadquery["browser_preview_ready"]
    mesh_avail    = fusion360["mesh_available"] or cadquery["mesh_available"]

    if has_cad or has_ros2 or has_sim:
        if browser_ready or has_ros2 or has_sim:
            status = "available"
        else:
            status = "partial"
    else:
        status = "empty"

    safety_notes: List[str] = [
        "All outputs are concept-stage only. No fabrication or deployment readiness is implied.",
        "3D preview (if available) is for visualization only and does not constitute an engineering design.",
        "ROS2 scaffolds require colcon build, hardware-in-the-loop testing, and human review before use.",
    ]

    if mesh_avail and not browser_ready:
        safety_notes.append(
            ".stl mesh files require conversion to .glb/.gltf for browser preview."
        )

    next_steps: List[str] = []
    if fusion360["detected"]:
        next_steps.append("Review Fusion 360 concept scripts with a licensed CAD engineer.")
    if cadquery["detected"]:
        next_steps.append("Review CadQuery scripts before executing locally.")
    if ros2["detected"]:
        next_steps.append("Run colcon build locally to verify ROS2 package scaffold.")
    if simulation["status"] == "launch_files_found":
        next_steps.append("Inspect launch files before executing in a local ROS2 environment.")
    if browser_ready:
        next_steps.append(".glb/.gltf files are available for browser-based 3D preview.")
    if not next_steps:
        next_steps.append("Run a full OMNI mission to generate CAD, ROS2, and simulation artifacts.")

    preview_assets = _build_preview_assets(export_dir)

    browser_preview_ready_count    = sum(1 for a in preview_assets if a["browser_preview_ready"])
    browser_preview_candidate_count = sum(1 for a in preview_assets if a["browser_preview_candidate"])
    engineering_only_count         = sum(1 for a in preview_assets if a["engineering_only"])
    execution_blocked_count        = sum(1 for a in preview_assets if a["execution_blocked"])

    return {
        "module":       MODULE_NAME,
        "status":       status,
        "preview_only": True,
        "cad_preview": {
            "has_cad":              has_cad,
            "browser_preview_ready": browser_ready,
            "mesh_available":        mesh_avail,
        },
        "fusion360":   fusion360,
        "cadquery":    cadquery,
        "ros2_preview": ros2,
        "simulation":  simulation,
        "safety_notes":    safety_notes,
        "blocked_actions": _BLOCKED_ACTIONS,
        "next_steps":      next_steps,
        "preview_assets":               preview_assets,
        "browser_preview_ready_count":   browser_preview_ready_count,
        "browser_preview_candidate_count": browser_preview_candidate_count,
        "engineering_only_count":        engineering_only_count,
        "execution_blocked_count":       execution_blocked_count,
    }
