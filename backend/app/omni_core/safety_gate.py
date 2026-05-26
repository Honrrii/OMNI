"""
OMNI Phase 13A — Deterministic Pluto safety gate.

Evaluates mission intent and candidate evaluation to produce an advisory
safety gate result. This gate is NEVER a substitute for human engineering
review before physical hardware testing or deployment.

No LLM calls. No network calls. No file I/O.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

GATE_NAME = "pluto_safety_gate"

# Platforms that carry elevated hardware/regulatory risk by nature.
_HIGH_RISK_PLATFORMS = {"drone-uav", "auv", "rov", "manta-ray-uuv"}

# Platforms that always need at least a medium-risk classification.
_MEDIUM_RISK_PLATFORMS = {"hexapod", "quadruped", "humanoid", "ground-rover", "robot-arm"}

# Keywords that signal physical hardware build intent in mission or candidate text.
_PHYSICAL_BUILD_SIGNALS = {
    "fabricate", "manufacture", "assemble", "deploy", "test hardware",
    "prototype", "weld", "solder", "3d print", "machine", "install",
}

# Keywords hinting at electrical / power concerns that should be confirmed.
_POWER_SIGNALS = {
    "battery", "power", "voltage", "watt", "amp", "current", "energy",
    "charging", "regulator", "fuse",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _as_dict(v: Any) -> Dict[str, Any]:
    return v if isinstance(v, dict) else {}


def _as_list(v: Any) -> List[Any]:
    return v if isinstance(v, list) else []


def _text_contains_any(text: str, signals: set) -> bool:
    lower = text.lower()
    return any(sig in lower for sig in signals)


def _physical_build_suspected(mission_intent: Dict[str, Any]) -> bool:
    """True when the mission or its fields suggest physical hardware construction."""
    # A resolved hardware platform is the strongest signal — if OMNI identified
    # a platform, this is a hardware mission.
    if mission_intent.get("platform_intent") is not None:
        return True
    raw = str(mission_intent.get("raw_mission", "")).lower()
    if _text_contains_any(raw, _PHYSICAL_BUILD_SIGNALS):
        return True
    # Constraints like power/battery also imply hardware.
    constraints = _as_list(mission_intent.get("constraints"))
    for c in constraints:
        if _text_contains_any(str(c), _POWER_SIGNALS):
            return True
    return False


def _power_info_present(mission_intent: Dict[str, Any]) -> bool:
    raw = str(mission_intent.get("raw_mission", "")).lower()
    if _text_contains_any(raw, _POWER_SIGNALS):
        return True
    constraints = _as_list(mission_intent.get("constraints"))
    for c in constraints:
        if _text_contains_any(str(c), _POWER_SIGNALS):
            return True
    return False


# ---------------------------------------------------------------------------
# Rule evaluators — each appends to blockers / warnings / checks as needed
# ---------------------------------------------------------------------------

def _rule_elevated_safety_mode(
    mission_intent: Dict[str, Any],
    warnings: List[str],
    required_human_review: List[bool],
    required_next_checks: List[str],
) -> None:
    if mission_intent.get("safety_mode") == "elevated":
        required_human_review.append(True)
        warnings.append(
            "Mission safety mode is 'elevated'. Human engineering review is required "
            "before any physical build, test, or deployment."
        )
        required_next_checks.append("Confirm safety mode justification with human engineer.")


def _rule_high_risk_platform(
    platform: Optional[str],
    warnings: List[str],
    required_human_review: List[bool],
    required_next_checks: List[str],
) -> None:
    if platform in _HIGH_RISK_PLATFORMS:
        required_human_review.append(True)
        warnings.append(
            f"Platform '{platform}' operates in a high-risk domain "
            "(aerial / underwater / autonomous marine). "
            "Regulatory, structural, and fail-safe review required."
        )
        required_next_checks.append(
            f"Confirm {platform} operational authorisation, emergency stop, and fail-safe design."
        )


def _rule_unknown_platform(
    platform: Optional[str],
    physical_build: bool,
    blockers: List[str],
    warnings: List[str],
    required_human_review: List[bool],
) -> None:
    if platform is not None:
        return
    if physical_build:
        blockers.append(
            "Platform type is unknown but mission appears to involve physical hardware. "
            "A platform must be identified before safety analysis can proceed."
        )
        required_human_review.append(True)
    else:
        warnings.append(
            "Platform type could not be resolved. "
            "Confirm platform before proceeding to hardware design."
        )


def _rule_open_questions(
    mission_intent: Dict[str, Any],
    warnings: List[str],
    required_next_checks: List[str],
) -> None:
    questions = _as_list(mission_intent.get("open_questions"))
    if questions:
        warnings.append(
            f"{len(questions)} open question(s) remain in the mission intent. "
            "These must be resolved before physical implementation."
        )
        required_next_checks.append("Resolve all open mission intent questions.")


def _rule_missing_power_info(
    mission_intent: Dict[str, Any],
    physical_build: bool,
    required_next_checks: List[str],
    warnings: List[str],
) -> None:
    if not physical_build:
        return
    if not _power_info_present(mission_intent):
        warnings.append(
            "No power or battery information found for a mission that appears to involve "
            "physical hardware. Power budget, battery chemistry, and regulator sizing "
            "must be defined before fabrication."
        )
        required_next_checks.append("Define power budget, battery, and regulator plan.")


def _rule_candidate_evaluation_quality(
    candidate_evaluation: Dict[str, Any],
    warnings: List[str],
    required_next_checks: List[str],
) -> None:
    status = candidate_evaluation.get("status")
    candidates_evaluated = candidate_evaluation.get("candidates_evaluated", 0)

    if status in ("skipped", "failed"):
        warnings.append(
            f"Candidate evaluation status is '{status}'. "
            "No structured design candidates were evaluated by Pluto."
        )
        required_next_checks.append(
            "Provide structured design candidates so Pluto can assess risk per alternative."
        )
    elif candidates_evaluated == 0:
        warnings.append(
            "No design candidates were evaluated. "
            "Risk assessment per alternative is not possible without candidates."
        )
        required_next_checks.append(
            "Add structured Vega design candidates before Pluto review."
        )


def _rule_no_validation_plan(
    mission_intent: Dict[str, Any],
    physical_build: bool,
    required_next_checks: List[str],
) -> None:
    if not physical_build:
        return
    outputs = _as_list(mission_intent.get("required_outputs"))
    has_validation = any(
        "validation" in str(o).lower() or "checklist" in str(o).lower()
        for o in outputs
    )
    if not has_validation:
        required_next_checks.append(
            "Define a validation checklist before physical build or test."
        )


# ---------------------------------------------------------------------------
# Risk level aggregator
# ---------------------------------------------------------------------------

def _compute_risk_level(
    blockers: List[str],
    warnings: List[str],
    platform: Optional[str],
    mission_intent: Dict[str, Any],
) -> str:
    if blockers:
        return "high"
    if mission_intent.get("safety_mode") == "elevated":
        return "high"
    if platform in _HIGH_RISK_PLATFORMS:
        return "high"
    if len(warnings) >= 3:
        return "high"
    if warnings or platform in _MEDIUM_RISK_PLATFORMS:
        return "medium"
    return "low"


def _compute_status(
    blockers: List[str],
    warnings: List[str],
    required_human_review: List[bool],
) -> str:
    if blockers:
        return "blocked"
    if warnings or any(required_human_review):
        return "warn"
    return "passed"


def _build_rationale(
    status: str,
    risk_level: str,
    blockers: List[str],
    warnings: List[str],
    required_human_review: bool,
    platform: Optional[str],
) -> str:
    parts: List[str] = []

    if status == "blocked":
        parts.append(
            f"Gate BLOCKED ({len(blockers)} blocker(s)). "
            "Critical information is missing and must be resolved before proceeding."
        )
    elif status == "warn":
        parts.append(
            f"Gate WARN — risk level '{risk_level}'. "
            f"{len(warnings)} warning(s) identified."
        )
    else:
        parts.append(f"Gate PASSED — risk level '{risk_level}'.")

    if required_human_review:
        parts.append(
            "Human engineering review is REQUIRED before physical build, test, or deployment."
        )

    if platform:
        parts.append(f"Resolved platform: {platform}.")
    else:
        parts.append("Platform: unresolved.")

    parts.append(
        "This gate is advisory. It does not authorise physical hardware testing or deployment."
    )

    return " ".join(parts)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def evaluate_safety_gate(
    mission_intent: Optional[Dict[str, Any]] = None,
    candidate_evaluation: Optional[Dict[str, Any]] = None,
    artifacts: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Evaluate the Pluto safety gate against mission intent and candidate evaluation.

    Deterministic. No LLM. No network. No file I/O.

    Returns:
      status, gate, risk_level, blockers, warnings,
      required_human_review, required_next_checks, rationale.
    """
    mi = _as_dict(mission_intent)
    ce = _as_dict(candidate_evaluation)

    # If top-level dicts are empty but artifacts was provided, attempt to pull from it.
    if not mi and artifacts:
        mi = _as_dict(_as_dict(artifacts).get("mission_intent"))
    if not ce and artifacts:
        ce = _as_dict(_as_dict(artifacts).get("candidate_evaluation"))

    platform: Optional[str] = mi.get("platform_intent") or None
    physical_build = _physical_build_suspected(mi)

    blockers: List[str] = []
    warnings: List[str] = []
    required_human_review: List[bool] = []
    required_next_checks: List[str] = []

    # Always require human review for physical systems — this is non-negotiable.
    if physical_build or platform is not None:
        required_human_review.append(True)

    _rule_elevated_safety_mode(mi, warnings, required_human_review, required_next_checks)
    _rule_high_risk_platform(platform, warnings, required_human_review, required_next_checks)
    _rule_unknown_platform(platform, physical_build, blockers, warnings, required_human_review)
    _rule_open_questions(mi, warnings, required_next_checks)
    _rule_missing_power_info(mi, physical_build, required_next_checks, warnings)
    _rule_candidate_evaluation_quality(ce, warnings, required_next_checks)
    _rule_no_validation_plan(mi, physical_build, required_next_checks)

    risk_level = _compute_risk_level(blockers, warnings, platform, mi)
    status = _compute_status(blockers, warnings, required_human_review)
    needs_review = any(required_human_review)
    rationale = _build_rationale(status, risk_level, blockers, warnings, needs_review, platform)

    return {
        "gate":                  GATE_NAME,
        "status":                status,
        "risk_level":            risk_level,
        "blockers":              blockers,
        "warnings":              warnings,
        "required_human_review": needs_review,
        "required_next_checks":  list(dict.fromkeys(required_next_checks)),  # dedup, stable order
        "rationale":             rationale,
    }
