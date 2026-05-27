"""
OMNI Phase 15A — AeroForge foundation: deterministic aerospace domain classifier.

Detects aerospace signals in mission text and classifies intent for concept-stage
aerospace analysis only. Does not generate aircraft, engines, or fabrication-ready
designs. Does not claim airworthiness or flight safety.

No LLM calls. No network calls. No file I/O.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Set

MODULE_NAME = "aeroforge"
GATE_NAME = "aeroforge_entry_gate"

# ---------------------------------------------------------------------------
# Signal tables — sorted longest-first during iteration to avoid short keywords
# shadowing longer, more specific phrases.
# ---------------------------------------------------------------------------

# keyword → list of aerospace domain labels
_AERO_KEYWORD_TO_DOMAINS: Dict[str, List[str]] = {
    "control surfaces":  ["controls", "aerodynamics"],
    "attitude control":  ["controls"],
    "payload fairing":   ["airframe"],
    "heat shield":       ["thermal"],
    "carbon fiber":      ["materials"],
    "aerodynamics":      ["aerodynamics"],
    "airworthiness":     ["safety"],
    "certification":     ["safety"],
    "propulsion":        ["propulsion"],
    "simulation":        ["simulation"],
    "composite":         ["materials"],
    "materials":         ["materials"],
    "avionics":          ["avionics"],
    "ablative":          ["thermal", "materials"],
    "aerofoil":          ["airframe", "aerodynamics"],
    "airframe":          ["airframe"],
    "aircraft":          ["airframe"],
    "airfoil":           ["airframe", "aerodynamics"],
    "fuselage":          ["airframe"],
    "altitude":          ["controls"],
    "turbine":           ["propulsion"],
    "thermal":           ["thermal"],
    "rocket":            ["propulsion"],
    "thrust":            ["propulsion"],
    "nozzle":            ["propulsion"],
    "flying":            ["controls", "airframe"],
    "flight":            ["controls"],
    "rotor":             ["propulsion", "airframe"],
    "blade":             ["propulsion"],
    "drone":             ["airframe", "avionics"],
    "wing":              ["airframe", "aerodynamics"],
    "lift":              ["aerodynamics"],
    "drag":              ["aerodynamics"],
    "pitch":             ["controls", "aerodynamics"],
    "yaw":               ["controls"],
    "uav":               ["airframe", "avionics"],
    "fly":               ["controls"],
    "jet":               ["propulsion"],
    "faa":               ["safety"],
}

# Outputs permitted at concept stage only
_ALLOWED_OUTPUTS: List[str] = [
    "concept taxonomy of aerospace subsystems",
    "requirements questions for aerospace design",
    "non-fabrication design envelope sketch",
    "simulation planning checklist",
    "safety and validation gap list",
    "literature and knowledge areas to research",
    "high-level architecture overview",
]

# Outputs that must never be produced
_BLOCKED_OUTPUTS: List[str] = [
    "fabrication-ready aircraft instructions",
    "flight-ready engine design",
    "operational propulsion build parameters",
    "claims of airworthiness",
    "claims of safe flight",
    "bypassing human engineering review",
    "bypassing regulatory review",
]

# Specific claims that must never be made
_PROHIBITED_CLAIMS: List[str] = [
    "This design is airworthy.",
    "This aircraft is safe to fly.",
    "This engine is ready for operation.",
    "This design meets flight certification requirements.",
]

# Review gates always required for aerospace physical systems
_REQUIRED_REVIEW_GATES: List[str] = [
    "Human engineer must review all aerospace concept outputs before any physical work begins.",
    "Regulatory authority review is required before any hardware prototyping or testing.",
    "Pluto safety gate must be clear before AeroForge concept outputs are used for design decisions.",
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _as_dict(v: Any) -> Dict[str, Any]:
    return v if isinstance(v, dict) else {}


def _dedup_ordered(items: List[str]) -> List[str]:
    seen: Set[str] = set()
    out: List[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out


def _detect_aero_domains(text_lower: str) -> List[str]:
    """Return ordered, deduplicated aerospace domain labels detected in text."""
    detected: List[str] = []
    for kw in sorted(_AERO_KEYWORD_TO_DOMAINS, key=len, reverse=True):
        if kw in text_lower:
            for domain in _AERO_KEYWORD_TO_DOMAINS[kw]:
                if domain not in detected:
                    detected.append(domain)
    return detected


def _infer_platform_hint(
    text_lower: str,
    mission_intent: Dict[str, Any],
) -> Optional[str]:
    """Best-effort platform hint — informational only, not a design specification."""
    pi = mission_intent.get("platform_intent")
    if pi == "drone-uav":
        return "drone-uav"
    if "rocket" in text_lower:
        return "launch-vehicle"
    if ("aircraft" in text_lower or "airframe" in text_lower) and "jet" in text_lower:
        return "jet-powered-aircraft"
    if "aircraft" in text_lower or "airframe" in text_lower or "fuselage" in text_lower:
        return "fixed-wing-aircraft"
    if "drone" in text_lower or "uav" in text_lower:
        return "drone-uav"
    if "rotor" in text_lower:
        return "rotorcraft"
    return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def classify_aeroforge_intent(
    mission_text: str = "",
    mission_intent: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Classify aerospace domain signals in mission text.

    Concept-stage only — does not generate aircraft, engines, or fabrication designs.

    Deterministic. No LLM. No network. No file I/O.

    Returns:
      module, status, aerospace_detected, aero_domains, platform_hint,
      concept_stage_only, prohibited_claims, required_review_gates,
      allowed_outputs, blocked_outputs, rationale.
    """
    mi = _as_dict(mission_intent)
    text_lower = (mission_text or "").lower()

    aero_domains = _detect_aero_domains(text_lower)
    aerospace_detected = bool(aero_domains)

    if not aerospace_detected:
        return {
            "module":                MODULE_NAME,
            "status":                "not_applicable",
            "aerospace_detected":    False,
            "aero_domains":          [],
            "platform_hint":         None,
            "concept_stage_only":    False,
            "prohibited_claims":     [],
            "required_review_gates": [],
            "allowed_outputs":       [],
            "blocked_outputs":       [],
            "rationale": (
                "No aerospace signals detected in mission text. "
                "AeroForge classification is not applicable to this mission."
            ),
        }

    platform_hint = _infer_platform_hint(text_lower, mi)

    return {
        "module":                MODULE_NAME,
        "status":                "detected",
        "aerospace_detected":    True,
        "aero_domains":          aero_domains,
        "platform_hint":         platform_hint,
        "concept_stage_only":    True,
        "prohibited_claims":     _PROHIBITED_CLAIMS,
        "required_review_gates": _REQUIRED_REVIEW_GATES,
        "allowed_outputs":       _ALLOWED_OUTPUTS,
        "blocked_outputs":       _BLOCKED_OUTPUTS,
        "rationale": (
            f"Aerospace signals detected ({len(aero_domains)} domain(s): "
            f"{', '.join(aero_domains)}). "
            "AeroForge classification is concept-stage only. "
            "No fabrication-ready designs, flight-ready engines, or airworthiness claims "
            "may be produced. Human engineering review and regulatory review are required "
            "before any physical aerospace work begins."
        ),
    }


def evaluate_aeroforge_entry_gate(
    mission_text: str = "",
    mission_intent: Optional[Dict[str, Any]] = None,
    readiness: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Evaluate whether AeroForge may begin concept-stage aerospace analysis.

    Blocks entry when mission_intelligence_readiness is 'blocked'.
    Always requires human review for aerospace physical systems.

    Deterministic. No LLM. No network. No file I/O.

    Returns:
      gate, status, aerospace_detected, readiness_status, human_review_required,
      concept_stage_only, blockers, allowed_outputs, blocked_outputs, rationale.
    """
    aero = classify_aeroforge_intent(mission_text=mission_text, mission_intent=mission_intent)
    aerospace_detected = aero["aerospace_detected"]

    readiness_dict = _as_dict(readiness)
    readiness_status = readiness_dict.get("status", "unknown")

    if not aerospace_detected:
        return {
            "gate":                  GATE_NAME,
            "status":                "not_applicable",
            "aerospace_detected":    False,
            "readiness_status":      readiness_status,
            "human_review_required": False,
            "concept_stage_only":    False,
            "blockers":              [],
            "allowed_outputs":       [],
            "blocked_outputs":       [],
            "rationale": (
                "No aerospace signals detected. "
                "AeroForge entry gate is not applicable to this mission."
            ),
        }

    blockers: List[str] = []

    if readiness_status == "blocked":
        blockers.append(
            "mission_intelligence_readiness is 'blocked'. "
            "AeroForge entry requires readiness status 'ready' or 'warn'."
        )

    if blockers:
        return {
            "gate":                  GATE_NAME,
            "status":                "blocked",
            "aerospace_detected":    True,
            "readiness_status":      readiness_status,
            "human_review_required": True,
            "concept_stage_only":    True,
            "blockers":              blockers,
            "allowed_outputs":       [],
            "blocked_outputs":       _BLOCKED_OUTPUTS,
            "rationale": (
                "AeroForge entry is blocked. "
                "mission_intelligence_readiness must not be 'blocked' before "
                "aerospace concept analysis can begin. "
                "Resolve all readiness gate blockers first."
            ),
        }

    return {
        "gate":                  GATE_NAME,
        "status":                "concept_stage_only",
        "aerospace_detected":    True,
        "readiness_status":      readiness_status,
        "human_review_required": True,
        "concept_stage_only":    True,
        "blockers":              [],
        "allowed_outputs":       _ALLOWED_OUTPUTS,
        "blocked_outputs":       _BLOCKED_OUTPUTS,
        "rationale": (
            "Aerospace signals detected and mission intelligence readiness is clear. "
            "AeroForge entry allowed at concept stage only. "
            "No fabrication-ready designs, flight-ready engine designs, or airworthiness claims "
            "may be produced. Human engineering review and regulatory authority review are "
            "required before any physical aerospace work begins."
        ),
    }
