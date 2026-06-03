"""
OMNI Phase 18A — Concept Dossier Manifest.

Deterministic, local, backend-only.
No LLM calls. No internet. No simulation. No image generation.
No engineering validation implied. No fabrication claims.
Concept-stage only.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

_MODULE = "concept_dossier"
_SCHEMA = "concept_dossier_manifest.v1"
_STATUS = "generated"

_GLTF_PREVIEW_PATH = "generated_visual_bay/preview_scene.gltf"

_SAFETY_NOTES: List[str] = [
    "Concept-stage presentation only.",
    "No engineering validation implied.",
    "No simulation launched.",
    "No fabrication, flight, or deployment readiness claims.",
    "Visual previews are abstract placeholders — not CAD-accurate.",
    "Human engineering review required before fabrication, deployment, flight, or operation.",
]

_BLOCKED_CLAIMS: List[str] = [
    "CAD-accurate",
    "fabrication-ready",
    "flight-ready",
    "airworthy",
    "deployment-ready",
    "engineering validated",
    "simulation verified",
]

_ALLOWED_VISUAL_MODES: List[str] = [
    "concept preview",
    "blueprint-style summary",
    "cutaway-style explanation",
    "subsystem callout panel",
    "engineering readiness panel",
]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _read_json_safe(path: Path) -> Optional[Dict[str, Any]]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _extract_mission_title(
    mission_result: Optional[Dict[str, Any]],
    mission_text: Optional[str],
) -> str:
    if isinstance(mission_result, dict):
        title = (
            mission_result.get("mission")
            or mission_result.get("mission_text")
            or mission_result.get("title")
            or mission_result.get("prompt")
            or ""
        )
        if title:
            return str(title).strip()
    if mission_text:
        return mission_text.strip()
    return "Untitled Mission"


def _extract_platform_intent(mission_result: Optional[Dict[str, Any]]) -> str:
    if not isinstance(mission_result, dict):
        return ""
    artifacts = mission_result.get("artifacts", {})
    if isinstance(artifacts, dict):
        intent = artifacts.get("mission_intent", {})
        if isinstance(intent, dict):
            p = str(intent.get("platform_intent", "")).strip()
            if p:
                return p
    return ""


def _extract_mission_type(mission_result: Optional[Dict[str, Any]]) -> str:
    if not isinstance(mission_result, dict):
        return ""
    artifacts = mission_result.get("artifacts", {})
    if isinstance(artifacts, dict):
        intent = artifacts.get("mission_intent", {})
        if isinstance(intent, dict):
            mt = str(intent.get("mission_type", "")).strip()
            if mt:
                return mt
    return ""


# ---------------------------------------------------------------------------
# Panel builders
# ---------------------------------------------------------------------------

def _build_hero_visual(export_dir: Optional[Path]) -> Dict[str, Any]:
    hero: Dict[str, Any] = {
        "type":            "visual_bay_gltf_placeholder",
        "path":            _GLTF_PREVIEW_PATH,
        "label":           "Mission-aware concept preview",
        "not_cad_accurate": True,
    }
    if export_dir is not None:
        hero["gltf_exists"] = (export_dir / _GLTF_PREVIEW_PATH).exists()
    return hero


def _build_mission_overview_panel(
    mission_title: str,
    platform_intent: str,
    mission_type: str,
) -> Dict[str, Any]:
    items: List[Dict[str, str]] = [
        {"label": "Mission", "value": mission_title},
    ]
    if platform_intent:
        items.append({"label": "Platform", "value": platform_intent})
    if mission_type:
        items.append({"label": "Mission type", "value": mission_type})
    items.append({
        "label": "Concept stage",
        "value": "Concept-stage only. No engineering validation implied.",
    })
    return {
        "id":         "mission_overview",
        "title":      "Mission Overview",
        "panel_type": "summary",
        "status":     "available",
        "items":      items,
    }


def _build_visual_bay_panel(export_dir: Optional[Path]) -> Dict[str, Any]:
    panel: Dict[str, Any] = {
        "id":         "visual_bay_preview",
        "title":      "Visual Bay Preview",
        "panel_type": "visual_inventory",
    }

    if export_dir is None:
        panel["status"] = "missing"
        panel["note"]   = "No export directory provided."
        return panel

    manifest_path = export_dir / "visual_bay_manifest.json"
    if not manifest_path.exists():
        panel["status"] = "missing"
        panel["note"]   = "visual_bay_manifest.json not found."
        return panel

    gltf_exists = (export_dir / _GLTF_PREVIEW_PATH).exists()
    manifest    = _read_json_safe(manifest_path)

    panel["status"]                = "available"
    panel["gltf_preview_available"] = gltf_exists

    if gltf_exists:
        panel["gltf_preview_path"] = _GLTF_PREVIEW_PATH
        panel["items"] = [
            {"label": "GLTF preview",    "value": _GLTF_PREVIEW_PATH},
            {"label": "Not CAD-accurate", "value": "Concept placeholder only."},
        ]
    else:
        panel["items"] = [
            {"label": "Status", "value": (
                "Visual Bay manifest present; GLTF preview not generated."
            )},
        ]

    if manifest:
        panel["manifest_status"] = manifest.get("status", "unknown")

    return panel


def _build_engineering_brain_panel(export_dir: Optional[Path]) -> Dict[str, Any]:
    panel: Dict[str, Any] = {
        "id":         "engineering_brain",
        "title":      "Engineering Brain",
        "panel_type": "engineering_summary",
    }

    if export_dir is None:
        panel["status"] = "missing"
        panel["note"]   = "No export directory provided."
        return panel

    sel_path       = export_dir / "engineering_knowledge_selection_report.json"
    readiness_path = export_dir / "engineering_input_readiness_report.json"
    calc_path      = export_dir / "engineering_calculation_report.json"

    sel       = _read_json_safe(sel_path)       if sel_path.exists()       else None
    readiness = _read_json_safe(readiness_path) if readiness_path.exists() else None
    calc      = _read_json_safe(calc_path)      if calc_path.exists()      else None

    if sel is None and readiness is None and calc is None:
        panel["status"] = "missing"
        panel["note"]   = "No engineering brain reports found in export directory."
        return panel

    panel["status"] = "available"
    items: List[Dict[str, str]] = []

    if sel is not None:
        count    = sel.get("selected_check_count")
        platform = sel.get("platform_intent", "")
        if count is not None:
            items.append({"label": "Selected checks", "value": str(count)})
        if platform:
            items.append({"label": "Platform (resolved)", "value": platform})

    if readiness is not None:
        rs      = readiness.get("readiness_summary", {})
        overall = rs.get("overall_status", "")
        if overall:
            items.append({"label": "Input readiness", "value": overall})

    if calc is not None:
        computed = calc.get("computed_metric_count")
        blocked  = calc.get("blocked_calculation_count")
        if computed is not None:
            items.append({"label": "Computed metrics",      "value": str(computed)})
        if blocked is not None:
            items.append({"label": "Blocked calculations", "value": str(blocked)})
        items.append({
            "label": "Calculation note",
            "value": "Concept-stage estimates only. No engineering validation implied.",
        })

    panel["items"] = items
    panel["summary"] = {
        "selected_check_count": sel.get("selected_check_count") if sel else None,
        "readiness_overall_status": (
            (readiness.get("readiness_summary") or {}).get("overall_status")
            if readiness else None
        ),
        "computed_metric_count":     calc.get("computed_metric_count")     if calc else None,
        "blocked_calculation_count": calc.get("blocked_calculation_count") if calc else None,
    }

    return panel


def _build_safety_boundary_panel() -> Dict[str, Any]:
    return {
        "id":             "safety_boundary",
        "title":          "Safety Boundary",
        "panel_type":     "safety",
        "status":         "available",
        "items":          [{"label": note, "value": ""} for note in _SAFETY_NOTES],
        "blocked_claims": list(_BLOCKED_CLAIMS),
    }


def _build_blueprint_panel() -> Dict[str, Any]:
    return {
        "id":         "blueprint_placeholders",
        "title":      "Blueprint / Cutaway Placeholders",
        "panel_type": "future_visual_panels",
        "status":     "planned",
        "note":       "Blueprint and cutaway-style panels are planned for a future phase.",
    }


def _build_source_reports(export_dir: Optional[Path]) -> Dict[str, Any]:
    if export_dir is None:
        return {}
    sources: Dict[str, str] = {}
    for fname, key in [
        ("visual_bay_manifest.json",                      "visual_bay_manifest"),
        ("engineering_knowledge_selection_report.json",   "knowledge_selection"),
        ("engineering_input_readiness_report.json",       "input_readiness"),
        ("engineering_calculation_report.json",           "calculation"),
    ]:
        if (export_dir / fname).exists():
            sources[key] = fname
    return sources


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def build_concept_dossier_manifest(
    mission_result: Optional[Dict[str, Any]] = None,
    mission_text: Optional[str] = None,
    export_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """
    Build a deterministic Concept Dossier Manifest.

    Summarises the mission as a technical presentation board contract.
    References Visual Bay and Engineering Brain reports from export_dir
    when available — does not generate them.

    No LLM calls. No internet. No simulation. No image generation.
    No engineering validation implied. No fabrication claims.
    Concept-stage only.
    """
    mission_title   = _extract_mission_title(mission_result, mission_text)
    platform_intent = _extract_platform_intent(mission_result)
    mission_type    = _extract_mission_type(mission_result)

    return {
        "module":             _MODULE,
        "schema":             _SCHEMA,
        "status":             _STATUS,
        "concept_stage_only": True,
        "mission_title":      mission_title,
        "platform_intent":    platform_intent,
        "mission_type":       mission_type,
        "hero_visual":        _build_hero_visual(export_dir),
        "dossier_panels": [
            _build_mission_overview_panel(mission_title, platform_intent, mission_type),
            _build_visual_bay_panel(export_dir),
            _build_engineering_brain_panel(export_dir),
            _build_safety_boundary_panel(),
            _build_blueprint_panel(),
        ],
        "allowed_visual_modes": list(_ALLOWED_VISUAL_MODES),
        "blocked_claims":       list(_BLOCKED_CLAIMS),
        "safety_notes":         list(_SAFETY_NOTES),
        "source_reports":       _build_source_reports(export_dir),
    }
