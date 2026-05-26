"""
OMNI Phase 14B — Deterministic mission intelligence memory seed builder.

Extracts compact, reusable lessons from mission_intent, candidate_evaluation,
and pluto_safety_gate into a structured seed dict. The seed is designed to be
stored later (Phase 14C) — this module only builds and returns it.

No LLM calls. No network calls. No file I/O.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _as_dict(v: Any) -> Dict[str, Any]:
    return v if isinstance(v, dict) else {}


def _as_list(v: Any) -> List[Any]:
    return v if isinstance(v, list) else []


def _str(v: Any, default: str = "") -> str:
    return str(v) if v is not None else default


def _dedup(items: List[str]) -> List[str]:
    seen: set = set()
    out: List[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out


# ---------------------------------------------------------------------------
# Risk theme extractor
# ---------------------------------------------------------------------------

def _extract_risk_themes(warnings: List[Any], next_checks: List[Any]) -> List[str]:
    """Condense Pluto warnings into short recurring-risk theme phrases."""
    themes: List[str] = []
    for w in warnings:
        text = _str(w).strip()
        if not text:
            continue
        # Truncate to a concise phrase (first sentence or 120 chars).
        first_sentence = text.split(".")[0].strip()
        theme = first_sentence[:120] if first_sentence else text[:120]
        themes.append(theme)
    return _dedup(themes)


def _extract_design_lessons(next_checks: List[Any]) -> List[str]:
    """Convert Pluto required_next_checks into actionable design lessons."""
    lessons: List[str] = []
    for check in next_checks:
        text = _str(check).strip()
        if text:
            lessons.append(text[:160])
    return _dedup(lessons)


# ---------------------------------------------------------------------------
# Memory summary builder
# ---------------------------------------------------------------------------

def _build_memory_summary(
    mission_type: Optional[str],
    platform_intent: Optional[str],
    recommended_id: Optional[str],
    risk_level: Optional[str],
    safety_status: Optional[str],
    unresolved_count: int,
    required_human_review: bool,
) -> str:
    parts: List[str] = []

    # Sentence 1 — mission and platform.
    if mission_type and platform_intent:
        parts.append(
            f"Mission type '{mission_type}' targeting platform '{platform_intent}'."
        )
    elif platform_intent:
        parts.append(f"Mission targets platform '{platform_intent}'.")
    elif mission_type:
        parts.append(f"Mission type: '{mission_type}'.")
    else:
        parts.append("Mission platform and type could not be resolved.")

    # Sentence 2 — recommended candidate.
    if recommended_id:
        parts.append(f"Recommended design candidate: {recommended_id}.")
    else:
        parts.append("No recommended design candidate was identified.")

    # Sentence 3 — safety gate outcome.
    if risk_level and safety_status:
        review_note = " Human review required." if required_human_review else ""
        parts.append(
            f"Pluto safety gate: {safety_status}, risk level {risk_level}.{review_note}"
        )

    # Sentence 4 — open questions note.
    if unresolved_count > 0:
        parts.append(
            f"{unresolved_count} unresolved question(s) remain and must be addressed "
            "before physical implementation."
        )

    return " ".join(parts)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def build_mission_memory_seed(
    mission_intent: Optional[Dict[str, Any]] = None,
    candidate_evaluation: Optional[Dict[str, Any]] = None,
    pluto_safety_gate: Optional[Dict[str, Any]] = None,
    mission_text: str = "",
) -> Dict[str, Any]:
    """
    Build a compact memory seed from mission intelligence outputs.

    Deterministic. No LLM. No network. No file I/O.

    Returns:
      status, mission_type, platform_intent, recommended_candidate_id,
      risk_level, safety_status, required_human_review,
      unresolved_questions, recurring_risk_themes, next_design_lessons,
      memory_summary.
    """
    mi  = _as_dict(mission_intent)
    ce  = _as_dict(candidate_evaluation)
    psg = _as_dict(pluto_safety_gate)

    # Determine whether we have any meaningful input.
    has_content = bool(mi or ce or psg or mission_text)

    # --- mission_intent fields ---
    mission_type    = mi.get("mission_type") or None
    platform_intent = mi.get("platform_intent") or None
    open_questions  = _as_list(mi.get("open_questions"))
    unresolved_questions = [_str(q) for q in open_questions if _str(q).strip()]

    # --- candidate_evaluation fields ---
    recommended_id = ce.get("recommended_candidate_id") or None
    ranking        = _as_list(ce.get("ranking"))

    # --- pluto_safety_gate fields ---
    risk_level            = psg.get("risk_level") or None
    safety_status         = psg.get("status") or None
    required_human_review = bool(psg.get("required_human_review", False))
    warnings              = _as_list(psg.get("warnings"))
    next_checks           = _as_list(psg.get("required_next_checks"))

    recurring_risk_themes = _extract_risk_themes(warnings, next_checks)
    next_design_lessons   = _extract_design_lessons(next_checks)

    memory_summary = _build_memory_summary(
        mission_type,
        platform_intent,
        recommended_id,
        risk_level,
        safety_status,
        len(unresolved_questions),
        required_human_review,
    )

    status = "generated" if has_content else "empty"

    return {
        "status":                 status,
        "mission_type":           mission_type,
        "platform_intent":        platform_intent,
        "recommended_candidate_id": recommended_id,
        "ranking":                ranking,
        "risk_level":             risk_level,
        "safety_status":          safety_status,
        "required_human_review":  required_human_review,
        "unresolved_questions":   unresolved_questions,
        "recurring_risk_themes":  recurring_risk_themes,
        "next_design_lessons":    next_design_lessons,
        "memory_summary":         memory_summary,
    }
