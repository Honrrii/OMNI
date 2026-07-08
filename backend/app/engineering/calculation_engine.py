"""
OMNI Phase 17D — Engineering Calculation Engine.

Deterministic, local, backend-only.
No LLM calls. No internet. No simulation launched.
No engineering validation implied. Concept-stage estimates only.

Computes a small, fixed set of engineering metrics when all required
numeric inputs are present and pass domain constraints.
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple

from backend.app.engineering.input_readiness_report import (
    build_engineering_input_readiness_report,
)

_SCHEMA = "engineering_calculation_report.v1"
_PHASE  = "17D"
_STATUS = "generated"

_G = 9.80665  # standard gravity, m/s²

_SAFETY_NOTE = (
    "Concept-stage estimate only. "
    "No engineering validation implied. "
    "Calculation performed only from provided inputs. "
    "Human engineering review required before fabrication, deployment, flight, or operation."
)

_SAFETY_HEADER = (
    "Concept-stage estimates only. "
    "No engineering validation implied. "
    "Calculation performed only from provided inputs. "
    "Human engineering review required before fabrication, deployment, flight, or operation."
)

# ---------------------------------------------------------------------------
# Numeric input validation
# ---------------------------------------------------------------------------

def _to_float(value: Any) -> Tuple[Optional[float], Optional[str]]:
    """
    Convert value to float for engineering calculation.
    Accepts int, float, or numeric string.
    Rejects bool, NaN, infinity, non-numeric strings, and all other types.
    Returns (float_value, error_message).
    """
    # Reject bool explicitly — True/False are not valid engineering inputs
    if isinstance(value, bool):
        return None, "Boolean values are not valid numeric inputs for engineering calculations."

    if isinstance(value, (int, float)):
        v = float(value)
        if math.isnan(v):
            return None, "NaN is not a valid input."
        if math.isinf(v):
            return None, "Infinity is not a valid input."
        return v, None

    if isinstance(value, str):
        try:
            v = float(value)
        except (ValueError, OverflowError):
            return None, f"Non-numeric string '{value}' cannot be used for calculation."
        if math.isnan(v):
            return None, "NaN string is not a valid input."
        if math.isinf(v):
            return None, "Infinity string is not a valid input."
        return v, None

    return None, f"Value of type '{type(value).__name__}' is not a valid numeric input."


# ---------------------------------------------------------------------------
# Per-calculation functions
# ---------------------------------------------------------------------------

def _calc_battery_runtime(
    inputs: Dict[str, float],
) -> Tuple[Optional[float], Optional[str]]:
    cap   = inputs["battery_capacity_wh"]
    power = inputs["average_power_w"]
    if power <= 0:
        return None, f"average_power_w must be > 0 (got {power})."
    return cap / power, None


def _calc_power_budget(
    inputs: Dict[str, float],
) -> Tuple[Optional[float], Optional[str]]:
    v = inputs["voltage_v"]
    a = inputs["current_a"]
    if v < 0:
        return None, f"voltage_v must be >= 0 (got {v})."
    if a < 0:
        return None, f"current_a must be >= 0 (got {a})."
    return v * a, None


def _calc_thrust_to_weight(
    inputs: Dict[str, float],
) -> Tuple[Optional[float], Optional[str]]:
    thrust = inputs["total_thrust_n"]
    mass   = inputs["mass_kg"]
    if mass <= 0:
        return None, f"mass_kg must be > 0 (got {mass})."
    return thrust / (mass * _G), None


# ---------------------------------------------------------------------------
# Supported calculation definitions
# ---------------------------------------------------------------------------

_SUPPORTED_CALCULATIONS: Dict[str, Dict[str, Any]] = {
    "battery_runtime_estimate": {
        "required_inputs": ["battery_capacity_wh", "average_power_w"],
        "metric_id":        "runtime_hours",
        "unit":             "hours",
        "formula":          "battery_capacity_wh / average_power_w",
        "assumptions": [
            "Assumes constant average power draw.",
            "No depth of discharge or efficiency correction applied unless inputs provided.",
            "Concept-stage estimate only.",
        ],
        "compute": _calc_battery_runtime,
    },
    "power_budget": {
        "required_inputs": ["voltage_v", "current_a"],
        "metric_id":        "power_w",
        "unit":             "W",
        "formula":          "voltage_v * current_a",
        "assumptions": [
            "Assumes DC power: P = V × I.",
            "No power factor, efficiency, or switching loss modeled.",
            "Concept-stage estimate only.",
        ],
        "compute": _calc_power_budget,
    },
    "thrust_to_weight_ratio": {
        "required_inputs": ["total_thrust_n", "mass_kg"],
        "metric_id":        "twr",
        "unit":             "dimensionless",
        "formula":          f"total_thrust_n / (mass_kg * {_G})",
        "assumptions": [
            f"Standard gravity g = {_G} m/s² used.",
            "No aerodynamic efficiency, motor characterisation, or propeller performance modeled.",
            "Concept-stage estimate only.",
            "Does not imply airworthiness, flight performance, or flight readiness.",
        ],
        "compute": _calc_thrust_to_weight,
    },
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def build_engineering_calculation_report(
    mission_result: Optional[Dict[str, Any]] = None,
    mission_text: Optional[str] = None,
    platform_intent: Optional[str] = None,
    provided_inputs: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Build a deterministic Engineering Calculation Report.

    Delegates platform resolution and check selection to Phase 17C, then
    computes supported metrics when all required numeric inputs are present
    and pass domain constraints.

    No LLM calls. No internet. No simulation. No engineering validation implied.
    Concept-stage estimates only.
    """
    readiness = build_engineering_input_readiness_report(
        mission_result=mission_result,
        mission_text=mission_text,
        platform_intent=platform_intent,
        provided_inputs=provided_inputs,
    )

    # Work from a copy so we never mutate the caller's dict
    pi: Dict[str, Any] = dict(provided_inputs) if provided_inputs else {}

    results:         List[Dict[str, Any]] = []
    blocked_results: List[Dict[str, Any]] = []

    seen_sn: set           = set()
    safety_notes: List[str] = [_SAFETY_HEADER]
    seen_sn.add(_SAFETY_HEADER)

    seen_bc: set              = set()
    blocked_claims: List[str] = []

    for chk in readiness["checks"]:
        check_id = chk["check_id"]

        # Propagate per-check safety_notes and blocked_claims
        for sn in chk.get("safety_notes", []):
            if sn not in seen_sn:
                seen_sn.add(sn)
                safety_notes.append(sn)
        for bc in chk.get("blocked_claims", []):
            if bc not in seen_bc:
                seen_bc.add(bc)
                blocked_claims.append(bc)

        if check_id not in _SUPPORTED_CALCULATIONS:
            blocked_results.append({
                "check_id":       check_id,
                "status":         "not_computed",
                "reason":         "unsupported_calculation",
                "missing_inputs": [],
                "required_inputs": chk.get("required_inputs", []),
            })
            continue

        calc_def   = _SUPPORTED_CALCULATIONS[check_id]
        req_inputs = calc_def["required_inputs"]

        # Identify which engine-specific required inputs are absent
        missing = [inp for inp in req_inputs if inp not in pi]
        if missing:
            reason = "inputs_missing" if len(missing) == len(req_inputs) else "inputs_partial"
            blocked_results.append({
                "check_id":        check_id,
                "status":          "not_computed",
                "reason":          reason,
                "missing_inputs":  missing,
                "required_inputs": req_inputs,
            })
            continue

        # Validate and convert all present inputs to float
        converted:   Dict[str, float] = {}
        warnings:    List[str]        = []
        input_error: Optional[str]    = None

        for inp in req_inputs:
            val = pi[inp]
            float_val, err = _to_float(val)
            if err:
                input_error = f"Input '{inp}': {err}"
                break
            if isinstance(val, str):
                warnings.append(
                    f"Input '{inp}' was provided as a numeric string and converted to float."
                )
            converted[inp] = float_val

        if input_error:
            blocked_results.append({
                "check_id":        check_id,
                "status":          "not_computed",
                "reason":          "invalid_input",
                "missing_inputs":  [],
                "required_inputs": req_inputs,
                "error_detail":    input_error,
            })
            continue

        # Compute (includes domain constraint checks)
        value, compute_err = calc_def["compute"](converted)

        if compute_err:
            blocked_results.append({
                "check_id":        check_id,
                "status":          "not_computed",
                "reason":          "invalid_input",
                "missing_inputs":  [],
                "required_inputs": req_inputs,
                "error_detail":    compute_err,
            })
            continue

        results.append({
            "check_id":     check_id,
            "status":       "computed",
            "metric_id":    calc_def["metric_id"],
            "value":        value,
            "unit":         calc_def["unit"],
            "formula":      calc_def["formula"],
            "input_values": dict(converted),
            "input_sources": {k: "provided_inputs" for k in req_inputs},
            "assumptions":  list(calc_def["assumptions"]),
            "warnings":     warnings,
            "confidence":   "concept_estimate",
            "safety_note":  _SAFETY_NOTE,
        })

    computed_metric_count    = len(results)
    blocked_calculation_count = len(blocked_results)
    supported_calculation_count = sum(
        1 for chk in readiness["checks"]
        if chk["check_id"] in _SUPPORTED_CALCULATIONS
    )

    rationale = (
        f"Platform resolved via '{readiness['platform_resolution_source']}'. "
        f"{supported_calculation_count} supported calculation(s) evaluated. "
        f"{computed_metric_count} computed, "
        f"{blocked_calculation_count} blocked (missing inputs, invalid inputs, or unsupported). "
        "Concept-stage estimates only. "
        "No engineering validation implied."
    )

    return {
        "schema":                      _SCHEMA,
        "status":                      _STATUS,
        "phase":                       _PHASE,
        "platform_intent":             readiness["platform_intent"],
        "platform_resolution_source":  readiness["platform_resolution_source"],
        "calculation_performed":       computed_metric_count > 0,
        "supported_calculation_count": supported_calculation_count,
        "computed_metric_count":       computed_metric_count,
        "blocked_calculation_count":   blocked_calculation_count,
        "results":                     results,
        "blocked_results":             blocked_results,
        "safety_notes":                safety_notes,
        "blocked_claims":              blocked_claims,
        "rationale":                   rationale,
    }
