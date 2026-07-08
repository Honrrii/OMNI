"""
OMNI Phase 17B — Engineering Knowledge Selection Report.

Deterministic, local, backend-only.
No LLM calls. No internet. No numeric calculations. No simulation launched.
No engineering validation implied. Concept-stage only.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from backend.app.engineering.knowledge_registry import (
    select_engineering_knowledge_for_platform,
)

_SCHEMA       = "engineering_knowledge_selection_report.v1"
_PHASE        = "17B"
_STATUS       = "generated"
_CALC_STATUS  = "not_computed_phase_17b"

_SAFETY_HEADER = (
    "Engineering checks selected. "
    "Inputs required before calculation. "
    "Missing inputs must be provided before computation. "
    "No engineering calculation performed. "
    "No engineering validation implied. "
    "Human engineering review required before fabrication, deployment, flight, or operation."
)

# ---------------------------------------------------------------------------
# Platform keyword sets (mirrors gltf_preview classification)
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
        return "uav"
    if any(kw in t for kw in _ROVER_KEYWORDS):
        return "rover"
    if any(kw in t for kw in _MANIPULATOR_KEYWORDS):
        return "manipulator"
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


def _resolve_platform_intent(
    mission_result: Optional[Dict[str, Any]],
    mission_text: Optional[str],
    platform_intent: Optional[str],
) -> Tuple[str, str]:
    """
    Returns (resolved_platform, resolution_source).

    Priority:
    1. Explicit platform_intent argument.
    2. mission_result.artifacts.mission_intent.platform_intent.
    3. mission_text keyword scan.
    4. mission_result mission text keyword scan.
    5. Unknown fallback (empty string → conservative base selection).
    """
    # Priority 1: explicit argument
    if platform_intent and platform_intent.strip():
        return platform_intent.strip(), "explicit_platform_intent"

    # Priority 2: mission_result structured field
    if isinstance(mission_result, dict):
        artifacts = mission_result.get("artifacts", {})
        if isinstance(artifacts, dict):
            intent = artifacts.get("mission_intent", {})
            if isinstance(intent, dict):
                p = str(intent.get("platform_intent", "")).strip()
                if p:
                    return p, "mission_result.artifacts.mission_intent.platform_intent"

    # Priority 3: mission_text argument keyword scan
    if mission_text and mission_text.strip():
        kind = _classify_from_text(mission_text)
        if kind:
            return kind, "mission_text_keywords"

    # Priority 4: mission_result text keyword scan
    if isinstance(mission_result, dict):
        text = _extract_mission_text(mission_result)
        if text:
            kind = _classify_from_text(text)
            if kind:
                return kind, "mission_result_text_keywords"

    return "", "unknown_fallback"


# ---------------------------------------------------------------------------
# Per-check builder
# ---------------------------------------------------------------------------

def _build_selected_check(entry: Dict[str, Any]) -> Dict[str, Any]:
    required_inputs   = list(entry.get("required_inputs", []))
    confidence_rules  = entry.get("confidence_rules", [])
    return {
        "check_id":              entry["id"],
        "domain":                entry["domain"],
        "title":                 entry["title"],
        "required_inputs":       required_inputs,
        "optional_inputs":       list(entry.get("optional_inputs", [])),
        "computed_outputs":      list(entry.get("computed_outputs", [])),
        "missing_inputs":        list(required_inputs),   # all required until inputs are provided
        "assumptions":           list(entry.get("assumptions", [])),
        "missing_input_behavior": entry.get("missing_input_behavior", "do_not_compute"),
        "confidence_rule":       confidence_rules[0] if confidence_rules else "",
        "safety_notes":          list(entry.get("safety_notes", [])),
        "blocked_claims":        list(entry.get("blocked_claims", [])),
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def build_engineering_knowledge_selection_report(
    mission_result: Optional[Dict[str, Any]] = None,
    mission_text: Optional[str] = None,
    platform_intent: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Build a deterministic Engineering Knowledge Selection Report.

    Selects applicable engineering checks for the resolved platform and
    summarises required inputs, missing inputs, assumptions, safety notes,
    and blocked claims.

    No LLM calls. No internet. No numeric calculations. No simulation.
    No engineering validation implied. Concept-stage only.
    """
    resolved_platform, resolution_source = _resolve_platform_intent(
        mission_result, mission_text, platform_intent
    )

    selected_entries = select_engineering_knowledge_for_platform(
        resolved_platform if resolved_platform else None
    )

    selected_checks = [_build_selected_check(e) for e in selected_entries]

    # Aggregate required_input_summary — unique, ordered by first appearance
    seen_req: set = set()
    required_input_summary: List[str] = []
    for chk in selected_checks:
        for inp in chk["required_inputs"]:
            if inp not in seen_req:
                seen_req.add(inp)
                required_input_summary.append(inp)

    # missing_input_summary starts equal to required (no inputs provided yet)
    missing_input_summary = list(required_input_summary)

    # Aggregate blocked_claims — deduped, ordered by first appearance
    seen_bc: set = set()
    blocked_claims: List[str] = []
    for chk in selected_checks:
        for bc in chk["blocked_claims"]:
            if bc not in seen_bc:
                seen_bc.add(bc)
                blocked_claims.append(bc)

    # Aggregate safety_notes — safety header first, then per-check notes, deduped
    seen_sn: set = set()
    safety_notes: List[str] = [_SAFETY_HEADER]
    seen_sn.add(_SAFETY_HEADER)
    for chk in selected_checks:
        for sn in chk["safety_notes"]:
            if sn not in seen_sn:
                seen_sn.add(sn)
                safety_notes.append(sn)

    rationale = (
        f"Platform resolved via '{resolution_source}'. "
        f"Selected {len(selected_checks)} engineering check(s) "
        f"for platform '{resolved_platform or 'unknown'}'. "
        "No engineering calculation performed. "
        "Missing inputs must be provided before computation."
    )

    return {
        "schema":                    _SCHEMA,
        "status":                    _STATUS,
        "phase":                     _PHASE,
        "platform_intent":           resolved_platform,
        "platform_resolution_source": resolution_source,
        "selected_check_count":      len(selected_checks),
        "selected_checks":           selected_checks,
        "required_input_summary":    required_input_summary,
        "missing_input_summary":     missing_input_summary,
        "blocked_claims":            blocked_claims,
        "safety_notes":              safety_notes,
        "calculation_status":        _CALC_STATUS,
        "rationale":                 rationale,
    }
