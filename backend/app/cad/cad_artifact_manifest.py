import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List


CAD_FILE_TYPE_MAP = {
    ".step": "STEP",
    ".stp": "STEP",
    ".stl": "STL",
    ".3mf": "3MF",
}


def build_cad_artifact_manifest(
    execution_result: Dict[str, Any],
    manifest_root: str = "outputs/omni_forge/manifests",
) -> Dict[str, Any]:
    """
    Build a frontend-ready artifact manifest for exported CAD files.

    This does not fabricate anything.
    This only organizes exported CAD files into a structured package.
    """

    exported_files = execution_result.get("exported_files", [])
    script_path = execution_result.get("script_path")
    execution_status = execution_result.get("status", "unknown")

    artifact_files = _normalize_exported_files(exported_files)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    script_stem = _script_stem(script_path)
    manifest_id = f"{timestamp}_{script_stem}_cad_manifest"

    manifest_dir = Path(manifest_root)
    manifest_dir.mkdir(parents=True, exist_ok=True)

    manifest_path = manifest_dir / f"{manifest_id}.json"

    ready_for_fabrication_review = (
        execution_status in ["success", "warning"]
        and len(artifact_files) > 0
    )

    manifest = {
        "manifest_id": manifest_id,
        "created_at": datetime.now().isoformat(),
        "artifact_type": "cad_export_package",
        "source_script_path": script_path,
        "execution_status": execution_status,
        "files": artifact_files,
        "file_count": len(artifact_files),
        "ready_for_fabrication_review": ready_for_fabrication_review,
        "human_review_required": True,
        "physical_execution_performed": False,
        "safety_status": {
            "printer_control_used": False,
            "fabrication_started": False,
            "requires_human_review_before_printing": True,
            "notes": [
                "CAD files were generated only for review.",
                "No 3D printer, slicer, heater, robot, or workshop hardware was controlled.",
                "User must inspect geometry before slicing or fabrication.",
            ],
        },
        "recommended_next_steps": [
            "Open the STEP file in a CAD viewer or Fusion 360.",
            "Inspect part dimensions and mounting geometry.",
            "Verify Raspberry Pi camera board measurements.",
            "Confirm screw hole spacing and cable clearance.",
            "Only after review, move to slicer preparation.",
        ],
        "manifest_path": str(manifest_path),
    }

    manifest_path.write_text(
        json.dumps(manifest, indent=2),
        encoding="utf-8",
    )

    return manifest


def _normalize_exported_files(exported_files: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    normalized_files = []

    for file_info in exported_files:
        path = Path(file_info.get("path", ""))
        suffix = path.suffix.lower()
        file_type = CAD_FILE_TYPE_MAP.get(suffix, suffix.replace(".", "").upper())

        normalized_files.append(
            {
                "name": file_info.get("filename", path.name),
                "path": str(path),
                "type": file_type,
                "suffix": suffix,
                "size_bytes": file_info.get("size_bytes"),
                "review_status": "pending_human_review",
                "fabrication_ready": False,
            }
        )

    return normalized_files


def _script_stem(script_path: str | None) -> str:
    if not script_path:
        return "unknown_script"

    stem = Path(script_path).stem
    stem = re.sub(r"[^a-zA-Z0-9_]+", "_", stem)
    stem = re.sub(r"_+", "_", stem)

    return stem[:80] or "unknown_script"