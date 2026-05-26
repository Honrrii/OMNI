"""
Deterministic candidate evaluation harness for OMNI Vega design candidates.

Scores each candidate across OMNI specialist perspectives:
  sky   — robotics / ROS2 / autonomy fit
  isy   — physics / dynamics / control feasibility
  korva — electronics / power / wiring feasibility
  oli   — CAD / manufacturability / morphology clarity
  pluto — safety / risk / failure concern
  qaz   — validation readiness

All scores are bounded [0.0, 1.0].
No LLM calls. No network calls. No file I/O.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Primitive heuristics — each returns a float in [0.0, 1.0]
# ---------------------------------------------------------------------------

def _platform_known(c: Dict[str, Any]) -> bool:
    return c.get("platform", "unknown") not in ("unknown", "")


def _mobility_known(c: Dict[str, Any]) -> bool:
    return c.get("mobility_type", "unknown") not in ("unknown", "")


def _component_richness(c: Dict[str, Any]) -> float:
    return min(len(c.get("key_components", [])), 5) / 5.0


def _validation_richness(c: Dict[str, Any]) -> float:
    return min(len(c.get("required_validation", [])), 3) / 3.0


def _risk_burden(c: Dict[str, Any]) -> float:
    return min(len(c.get("risks", [])), 5) / 5.0


def _assumption_burden(c: Dict[str, Any]) -> float:
    return min(len(c.get("assumptions", [])), 5) / 5.0


def _has_morphology(c: Dict[str, Any]) -> float:
    return 1.0 if len(c.get("morphology_notes", "")) > 5 else 0.0


def _strength_richness(c: Dict[str, Any]) -> float:
    return min(len(c.get("strengths", [])), 3) / 3.0


# ---------------------------------------------------------------------------
# Per-axis scorers
# ---------------------------------------------------------------------------

def _sky_score(c: Dict[str, Any]) -> float:
    """Robotics / ROS2 / autonomy fit — rewards known platform, mobility, components."""
    s = 0.0
    s += 0.35 if _platform_known(c) else 0.0
    s += 0.25 if _mobility_known(c) else 0.0
    s += 0.30 * _component_richness(c)
    s += 0.10 * _strength_richness(c)
    return round(min(s, 1.0), 3)


def _isy_score(c: Dict[str, Any]) -> float:
    """Physics / dynamics / control feasibility — penalizes unresolved assumptions."""
    s = 0.0
    s += 0.30 if _platform_known(c) else 0.0
    s += 0.20 if _mobility_known(c) else 0.0
    s += 0.20 * _component_richness(c)
    s += 0.30 * (1.0 - _assumption_burden(c))
    return round(min(s, 1.0), 3)


def _korva_score(c: Dict[str, Any]) -> float:
    """Electronics / power / wiring feasibility — rewards component detail."""
    s = 0.0
    s += 0.25 if _platform_known(c) else 0.0
    s += 0.50 * _component_richness(c)
    s += 0.25 * _strength_richness(c)
    return round(min(s, 1.0), 3)


def _oli_score(c: Dict[str, Any]) -> float:
    """CAD / manufacturability / morphology clarity — rewards morphology notes."""
    s = 0.0
    s += 0.30 * _has_morphology(c)
    s += 0.25 if _platform_known(c) else 0.0
    s += 0.25 * _component_richness(c)
    s += 0.20 if _mobility_known(c) else 0.0
    return round(min(s, 1.0), 3)


def _pluto_score(c: Dict[str, Any]) -> float:
    """Safety / risk concern — starts high, deducted by risks and assumptions."""
    s = 1.0
    s -= 0.50 * _risk_burden(c)
    s -= 0.20 * _assumption_burden(c)
    s += 0.10 * _validation_richness(c)  # listing validation shows risk awareness
    return round(max(min(s, 1.0), 0.0), 3)


def _qaz_score(c: Dict[str, Any]) -> float:
    """Validation readiness — rewards explicit required_validation list."""
    s = 0.0
    s += 0.50 * _validation_richness(c)
    s += 0.25 if _platform_known(c) else 0.0
    s += 0.25 * _component_richness(c)
    return round(min(s, 1.0), 3)


# Axis weights must sum to 1.0.
_WEIGHTS: Dict[str, float] = {
    "sky":   0.20,
    "isy":   0.20,
    "korva": 0.15,
    "oli":   0.15,
    "pluto": 0.15,
    "qaz":   0.15,
}
_RECOMMENDED_BOOST = 0.05  # tie-break only — not a guaranteed victory


def _overall_score(c: Dict[str, Any], axes: Dict[str, float]) -> float:
    raw = sum(_WEIGHTS[k] * axes[k] for k in _WEIGHTS)
    if c.get("recommended", False):
        raw += _RECOMMENDED_BOOST
    return round(min(raw, 1.0), 3)


# ---------------------------------------------------------------------------
# Per-candidate evaluation
# ---------------------------------------------------------------------------

def _evaluate_one(c: Any) -> Dict[str, Any]:
    if not isinstance(c, dict):
        c = {}
    axes = {
        "sky":   _sky_score(c),
        "isy":   _isy_score(c),
        "korva": _korva_score(c),
        "oli":   _oli_score(c),
        "pluto": _pluto_score(c),
        "qaz":   _qaz_score(c),
    }
    return {
        "id":            c.get("id", "unknown"),
        "name":          c.get("name", "Unknown"),
        "sky_score":     axes["sky"],
        "isy_score":     axes["isy"],
        "korva_score":   axes["korva"],
        "oli_score":     axes["oli"],
        "pluto_score":   axes["pluto"],
        "qaz_score":     axes["qaz"],
        "overall_score": _overall_score(c, axes),
    }


# ---------------------------------------------------------------------------
# Diagnostic helpers
# ---------------------------------------------------------------------------

def _build_open_questions(candidates: List[Dict[str, Any]]) -> List[str]:
    questions: List[str] = []
    if any(c.get("platform", "unknown") in ("unknown", "") for c in candidates):
        questions.append("Confirm platform type for all design candidates.")
    if any(c.get("mobility_type", "unknown") in ("unknown", "") for c in candidates):
        questions.append("Confirm mobility type for all design candidates.")
    if all(not c.get("required_validation") for c in candidates):
        questions.append("Define required validation steps for each design candidate.")
    if all(not c.get("key_components") for c in candidates):
        questions.append("List key components for each design candidate.")
    if all(not c.get("morphology_notes") for c in candidates):
        questions.append("Add morphology/form notes to each design candidate.")
    return questions


def _build_council_summary(
    evaluations: List[Dict[str, Any]],
    recommended_id: Optional[str],
) -> str:
    if not evaluations:
        return "No candidates evaluated."
    top = next((e for e in evaluations if e["id"] == recommended_id), evaluations[0])
    return (
        f"{len(evaluations)} candidate(s) evaluated. "
        f"Top candidate: {top['name']} ({top['id']}, overall={top['overall_score']:.3f}). "
        f"Sky={top['sky_score']:.2f}, Isy={top['isy_score']:.2f}, "
        f"Korva={top['korva_score']:.2f}, Oli={top['oli_score']:.2f}, "
        f"Pluto={top['pluto_score']:.2f}, QaZ={top['qaz_score']:.2f}."
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def evaluate_design_candidates(
    candidates: List[Dict[str, Any]],
    mission_text: str = "",
) -> Dict[str, Any]:
    """
    Evaluate a list of normalized Vega design candidates.

    Returns:
      candidates_evaluated, evaluations, recommended_candidate_id,
      ranking, council_summary, open_questions.

    Deterministic. No LLM. No network. No file I/O.
    """
    if not isinstance(candidates, list):
        candidates = []

    if not candidates:
        return {
            "candidates_evaluated": 0,
            "evaluations": [],
            "recommended_candidate_id": None,
            "ranking": [],
            "council_summary": "No candidates evaluated.",
            "open_questions": [],
        }

    evaluations = [_evaluate_one(c) for c in candidates]

    # Stable sort: highest overall_score first; original list order breaks ties.
    ranked = sorted(evaluations, key=lambda e: e["overall_score"], reverse=True)
    ranking = [e["id"] for e in ranked]
    recommended_id = ranking[0]

    valid_candidates = [c for c in candidates if isinstance(c, dict)]
    open_questions = _build_open_questions(valid_candidates)
    council_summary = _build_council_summary(evaluations, recommended_id)

    return {
        "candidates_evaluated": len(evaluations),
        "evaluations": evaluations,
        "recommended_candidate_id": recommended_id,
        "ranking": ranking,
        "council_summary": council_summary,
        "open_questions": open_questions,
    }
