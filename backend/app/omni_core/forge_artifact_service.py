from typing import Any, Dict

from backend.app.cad.cad_artifact_manifest import build_cad_artifact_manifest


def create_cad_export_artifact_manifest(
    execution_result: Dict[str, Any],
) -> Dict[str, Any]:
    """
    OMNI Forge artifact packaging service.

    Takes a CAD execution result and creates a structured artifact manifest
    that the frontend can display cleanly.
    """

    manifest = build_cad_artifact_manifest(execution_result)

    return {
        "status": "success",
        "message": "CAD artifact manifest created.",
        "manifest": manifest,
    }