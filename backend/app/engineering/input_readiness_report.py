"""
OMNI Phase 17C — Engineering Input Readiness Report.

Deterministic, local, backend-only.
No LLM calls. No internet. No numeric calculations. No simulation launched.
No engineering validation implied. Concept-stage only.

Classifies each selected engineering check as:
  inputs_missing              — no required inputs provided
  inputs_partial              — some required inputs provided
  inputs_ready_for_calculation — all required inputs provided (no calculation yet)
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from backend.app.engineering.knowledge_selection_report import (
    build_engineering_knowledge_selection_report,
)

_SCHEMA      = "engineering_input_readiness_report.v1"
_PHASE       = "17C"
_STATUS      = "generated"
_CALC_STATUS = "not_computed_phase_17c"

_SAFETY_HEADER = (
    "No engineering calculation performed. "
    "No engineering validation implied. "
    "Provided inputs were checked for presence only. "
    "Inputs ready for future calculation when all required inputs are provided. "
    "Human engineering review required before fabrication, deployment, flight, or operation."
)

_READINESS_MISSING  = "inputs_missing"
_READINESS_PARTIAL  = "inputs_partial"
_READINESS_READY    = "inputs_ready_for_calculation"


# ---------------------------------------------------------------------------
# Input presence check
# ---------------------------------------------------------------------------

def _is_present(value: Any) -> bool:
    """
    A required-input value counts as present unless it is:
      None, empty string, empty list, or empty dict.
    Numeric zero and boolean False count as present.
    """
    if value is None:
        return False
    if isinstance(value, str) and value == "":
        return False
    if isinstance(value, list) and len(value) == 0:
        return False
    if isinstance(value, dict) and len(value) == 0:
        return False
    return True


# ---------------------------------------------------------------------------
# Per-check readiness classification
# ---------------------------------------------------------------------------

def _classify_check_readiness(
    required_inputs: List[str],
    provided_inputs: Dict[str, Any],
) -> Tuple[List[str], List[str], str]:
    """
    Returns (present_input_names, missing_input_names, readiness_status).

    Only evaluates whether required inputs are present —
    no engineering correctness check is performed.
    """
    present: List[str] = []
    missing: List[str] = []

    for inp in required_inputs:
        if inp in provided_inputs and _is_present(provided_inputs[inp]):
            present.append(inp)
        else:
            missing.append(inp)

    if not required_inputs:
        status = _READINESS_READY
    elif not missing:
        status = _READINESS_READY
    elif not present:
        status = _READINESS_MISSING
    else:
        status = _READINESS_PARTIAL

    return present, missing, status


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def build_engineering_input_readiness_report(
    mission_result: Optional[Dict[str, Any]] = None,
    mission_text: Optional[str] = None,
    platform_intent: Optional[str] = None,
    provided_inputs: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Build a deterministic Engineering Input Readiness Report.

    Delegates platform resolution and check selection to Phase 17B, then
    classifies each check by how many of its required inputs are present
    in provided_inputs.

    No LLM calls. No internet. No numeric calculations. No simulation.
    No engineering validation implied. Concept-stage only.
    """
    selection = build_engineering_knowledge_selection_report(
        mission_result=mission_result,
        mission_text=mission_text,
        platform_intent=platform_intent,
    )

    pi: Dict[str, Any] = dict(provided_inputs) if provided_inputs else {}

    checks: List[Dict[str, Any]] = []
    ready_count   = 0
    partial_count = 0
    missing_count = 0
    ready_check_ids: List[str] = []

    seen_missing: set   = set()
    missing_input_summary: List[str] = []

    seen_bc: set           = set()
    blocked_claims: List[str] = []

    seen_sn: set           = set()
    safety_notes: List[str] = [_SAFETY_HEADER]
    seen_sn.add(_SAFETY_HEADER)

    for sel_chk in selection["selected_checks"]:
        required = sel_chk["required_inputs"]
        present_names, missing_names, status = _classify_check_readiness(required, pi)

        if status == _READINESS_READY:
            ready_count += 1
            ready_check_ids.append(sel_chk["check_id"])
        elif status == _READINESS_PARTIAL:
            partial_count += 1
        else:
            missing_count += 1

        for m in missing_names:
            if m not in seen_missing:
                seen_missing.add(m)
                missing_input_summary.append(m)

        for bc in sel_chk.get("blocked_claims", []):
            if bc not in seen_bc:
                seen_bc.add(bc)
                blocked_claims.append(bc)

        for sn in sel_chk.get("safety_notes", []):
            if sn not in seen_sn:
                seen_sn.add(sn)
                safety_notes.append(sn)

        checks.append({
            "check_id":              sel_chk["check_id"],
            "domain":                sel_chk["domain"],
            "title":                 sel_chk["title"],
            "required_inputs":       list(required),
            "provided_inputs":       present_names,
            "missing_inputs":        missing_names,
            "readiness_status":      status,
            "calculation_status":    _CALC_STATUS,
            "missing_input_behavior": sel_chk.get("missing_input_behavior", "do_not_compute"),
            "safety_notes":          list(sel_chk.get("safety_notes", [])),
            "blocked_claims":        list(sel_chk.get("blocked_claims", [])),
        })

    total_checks = len(checks)
    if total_checks == 0 or missing_count == total_checks:
        overall_status = _READINESS_MISSING
    elif ready_count == total_checks:
        overall_status = _READINESS_READY
    else:
        overall_status = _READINESS_PARTIAL

    rationale = (
        f"Platform resolved via '{selection['platform_resolution_source']}'. "
        f"Evaluated readiness for {total_checks} check(s): "
        f"{ready_count} ready, {partial_count} partial, {missing_count} missing. "
        "No engineering calculation performed. "
        "Provided inputs were checked for presence only."
    )

    return {
        "schema":                    _SCHEMA,
        "status":                    _STATUS,
        "phase":                     _PHASE,
        "platform_intent":           selection["platform_intent"],
        "platform_resolution_source": selection["platform_resolution_source"],
        "calculation_performed":     False,
        "readiness_summary": {
            "total_checks":   total_checks,
            "ready_count":    ready_count,
            "partial_count":  partial_count,
            "missing_count":  missing_count,
            "overall_status": overall_status,
        },
        "checks":                    checks,
        "missing_input_summary":     missing_input_summary,
        "ready_check_ids":           ready_check_ids,
        "blocked_claims":            blocked_claims,
        "safety_notes":              safety_notes,
        "rationale":                 rationale,
    }
