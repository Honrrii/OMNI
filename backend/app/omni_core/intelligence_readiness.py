"""
OMNI Phase 14E — Deterministic mission intelligence readiness gate.

Checks whether a mission result/artifact stack is complete and
integration-ready before larger domain extensions like AeroForge.

No LLM calls. No network calls. No file I/O.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Set

GATE_NAME = "mission_intelligence_readiness"

# Weights must sum to 1.0 — score reflects artifact completeness, not quality.
_SCORE_WEIGHTS: Dict[str, float] = {
    "mission_intent":                                0.20,
    "mission_intent.platform_intent":               0.15,
    "candidate_evaluation":                         0.15,
    "candidate_evaluation.recommended_candidate_id": 0.10,
    "pluto_safety_gate":                            0.20,
    "mission_memory_seed":                          0.10,
    "mission_memory_persistence":                   0.10,
}

# Signals in mission text indicating physical hardware build intent.
_PHYSICAL_TEXT_SIGNALS = {
    "fabricate", "manufacture", "assemble", "deploy", "prototype",
    "weld", "solder", "3d print", "machine", "install",
    "crawler", "rover", "robot", "drone", "uav", "hexapod", "quadruped",
    "legged", "tracked", "wheeled locomotion",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _as_dict(v: Any) -> Dict[str, Any]:
    return v if isinstance(v, dict) else {}


def _is_physical_mission(mission_intent: Dict[str, Any], mission_text: str) -> bool:
    """True when mission involves physical robotics hardware."""
    if mission_intent.get("platform_intent") is not None:
        return True
    lower = (mission_text or "").lower()
    return any(sig in lower for sig in _PHYSICAL_TEXT_SIGNALS)


def _compute_score(earned: Dict[str, bool]) -> float:
    total = sum(_SCORE_WEIGHTS[k] for k, present in earned.items() if present)
    return round(min(max(total, 0.0), 1.0), 3)


def _build_rationale(
    status: str,
    blockers: List[str],
    warnings: List[str],
    score: float,
) -> str:
    if status == "ready":
        return (
            f"Mission intelligence stack is ready for the next software phase "
            f"(readiness score: {score:.2f}). "
            "All core artifacts are present and the Pluto safety gate is clear. "
            "This assessment covers artifact completeness only — not engineering validation."
        )
    if status == "warn":
        return (
            f"Mission intelligence stack has {len(warnings)} warning(s) "
            f"(readiness score: {score:.2f}). "
            "Review and resolve warnings before advancing to the next software phase. "
            "This assessment covers artifact completeness only — not engineering validation."
        )
    return (
        f"Mission intelligence stack is blocked — {len(blockers)} blocker(s) present "
        f"(readiness score: {score:.2f}). "
        "Resolve all blockers before proceeding to the next software phase. "
        "This assessment covers artifact completeness only — not engineering validation."
    )


def _dedup_ordered(items: List[str]) -> List[str]:
    seen: Set[str] = set()
    out: List[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def evaluate_mission_intelligence_readiness(
    artifacts: Optional[Dict[str, Any]] = None,
    export_result: Optional[Dict[str, Any]] = None,
    mission_text: str = "",
) -> Dict[str, Any]:
    """
    Evaluate whether a mission artifact stack is complete and integration-ready.

    Deterministic. No LLM. No network. No file I/O.

    Returns:
      gate, status, readiness_score, present_artifacts, missing_artifacts,
      warnings, blockers, next_actions, rationale.
    """
    arts = _as_dict(artifacts)
    exp = _as_dict(export_result)

    # --- Extract artifacts ---
    mission_intent = _as_dict(arts.get("mission_intent"))
    candidate_evaluation = _as_dict(arts.get("candidate_evaluation"))
    pluto_safety_gate = _as_dict(arts.get("pluto_safety_gate"))
    mission_memory_seed = _as_dict(arts.get("mission_memory_seed"))
    mission_memory_persistence = _as_dict(arts.get("mission_memory_persistence"))
    design_candidates = arts.get("design_candidates")

    # Optional artifacts — may appear in artifacts or export_result.
    graph_review = arts.get("graph_review") or exp.get("graph_review")
    cortex = _as_dict(exp.get("cortex", {}))
    design_understanding = (
        arts.get("design_understanding") or cortex.get("design_understanding")
    )

    # --- Presence booleans ---
    has_mission_intent = bool(mission_intent)
    platform_intent = mission_intent.get("platform_intent") if has_mission_intent else None
    has_platform_intent = bool(platform_intent)

    has_candidate_evaluation = bool(candidate_evaluation)
    recommended_id = (
        candidate_evaluation.get("recommended_candidate_id")
        if has_candidate_evaluation else None
    )
    has_recommended_id = bool(recommended_id)

    has_pluto_gate = bool(
        pluto_safety_gate and pluto_safety_gate.get("gate") == "pluto_safety_gate"
    )
    pluto_status = pluto_safety_gate.get("status") if has_pluto_gate else None

    has_memory_seed = bool(
        mission_memory_seed and mission_memory_seed.get("status") == "generated"
    )
    has_memory_persistence = bool(
        mission_memory_persistence and mission_memory_persistence.get("status") == "saved"
    )

    has_design_candidates = bool(
        isinstance(design_candidates, list) and design_candidates
    )
    has_graph_review = bool(graph_review)
    has_design_understanding = bool(design_understanding)

    is_physical = _is_physical_mission(mission_intent, mission_text)

    # --- Build present/missing artifact lists ---
    present_artifacts: List[str] = []
    missing_artifacts: List[str] = []

    def _check(name: str, present: bool) -> None:
        (present_artifacts if present else missing_artifacts).append(name)

    _check("mission_intent", has_mission_intent)
    _check("mission_intent.platform_intent", has_platform_intent)
    _check("design_candidates", has_design_candidates)
    _check("candidate_evaluation", has_candidate_evaluation)
    _check("candidate_evaluation.recommended_candidate_id", has_recommended_id)
    _check("pluto_safety_gate", has_pluto_gate)
    _check("pluto_safety_gate.status", has_pluto_gate and pluto_status is not None)
    _check("mission_memory_seed", has_memory_seed)
    _check("mission_memory_persistence", has_memory_persistence)

    if has_graph_review:
        present_artifacts.append("graph_review")
    if has_design_understanding:
        present_artifacts.append("design_understanding")

    # --- Rules → blockers / warnings / next_actions ---
    blockers: List[str] = []
    warnings: List[str] = []
    next_actions: List[str] = []

    # Rule 1: Missing mission_intent is a blocker.
    if not has_mission_intent:
        blockers.append(
            "mission_intent artifact is missing. "
            "Cannot assess readiness without a compiled mission intent."
        )
        next_actions.append(
            "Run compile_mission_intent and include the result in artifacts."
        )

    # Rule 2: Missing platform_intent is a blocker.
    elif not has_platform_intent:
        blockers.append(
            "mission_intent.platform_intent is not resolved. "
            "A platform type is required for integration readiness."
        )
        next_actions.append(
            "Revise mission text to include a recognizable platform type, "
            "or confirm platform with the human engineer."
        )

    # Rule 3: Missing candidate_evaluation is a warning.
    if not has_candidate_evaluation:
        warnings.append(
            "candidate_evaluation artifact is missing or empty. "
            "Design candidates have not been evaluated."
        )
        next_actions.append(
            "Add Vega design candidates and run evaluate_design_candidates."
        )

    # Rule 4: Missing recommended_candidate_id is a warning.
    elif not has_recommended_id:
        warnings.append(
            "candidate_evaluation has no recommended_candidate_id. "
            "A top design candidate has not been selected."
        )
        next_actions.append(
            "Ensure candidate evaluation produces a recommended_candidate_id."
        )

    # Rule 5: Missing pluto_safety_gate is a blocker for physical robotics missions.
    if is_physical and not has_pluto_gate:
        blockers.append(
            "Physical robotics mission is missing the pluto_safety_gate artifact. "
            "Safety gate evaluation is required before advancing to the next software phase."
        )
        next_actions.append(
            "Run evaluate_safety_gate and include the result in artifacts."
        )

    # Rule 6: Pluto blocked status blocks readiness.
    if has_pluto_gate and pluto_status == "blocked":
        blockers.append(
            "pluto_safety_gate.status is 'blocked'. "
            "The safety gate has unresolved blockers that must be addressed "
            "before the mission intelligence stack can advance."
        )
        next_actions.append(
            "Resolve all pluto_safety_gate blockers before proceeding."
        )

    # Rule 7: Missing mission_memory_seed is a warning.
    if not has_memory_seed:
        warnings.append(
            "mission_memory_seed artifact is missing or not in 'generated' status. "
            "Memory learning from this mission is incomplete."
        )
        next_actions.append(
            "Ensure build_mission_memory_seed runs and produces status 'generated'."
        )

    # Rule 8: Missing memory persistence is a warning.
    if not has_memory_persistence:
        warnings.append(
            "mission_memory_persistence status is not 'saved'. "
            "Memory from this mission has not been persisted."
        )
        next_actions.append(
            "Ensure add_mission_memory_seed runs successfully."
        )

    # --- Score ---
    readiness_score = _compute_score({
        "mission_intent":                                has_mission_intent,
        "mission_intent.platform_intent":               has_platform_intent,
        "candidate_evaluation":                         has_candidate_evaluation,
        "candidate_evaluation.recommended_candidate_id": has_recommended_id,
        "pluto_safety_gate":                            has_pluto_gate,
        "mission_memory_seed":                          has_memory_seed,
        "mission_memory_persistence":                   has_memory_persistence,
    })

    # --- Status ---
    if blockers:
        status = "blocked"
    elif warnings:
        status = "warn"
    else:
        status = "ready"

    rationale = _build_rationale(status, blockers, warnings, readiness_score)

    return {
        "gate":              GATE_NAME,
        "status":            status,
        "readiness_score":   readiness_score,
        "present_artifacts": present_artifacts,
        "missing_artifacts": missing_artifacts,
        "warnings":          warnings,
        "blockers":          blockers,
        "next_actions":      _dedup_ordered(next_actions),
        "rationale":         rationale,
    }
