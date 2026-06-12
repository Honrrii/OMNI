"""Units/math sandbox check (Phase 11 Stage 1).

A single deterministic mass-balance check: does a declared total mass match the
sum of component masses within a tolerance? Pure Python arithmetic only — no
pint, no sympy, no external binaries.

Expected input shape (small)::

    {
        "declared_total_mass_kg": 2.0,
        "component_masses_kg": [1.0, 1.4],
        "tolerance_kg": 0.05,
    }

Outcomes:
- match within tolerance -> status "passed", one passing check
- mismatch              -> status "completed", one "warning" check with
                           expected/actual as stable strings
- missing/invalid input -> status "skipped", one "info" check
"""
from __future__ import annotations

from typing import Any, Optional

from backend.app.sandbox.report import SandboxCheckResult, SandboxReport

_SANDBOX_NAME = "units_math"
_CHECK_ID = "units.mass_balance"
_DEFAULT_TOLERANCE_KG = 0.05


def _format_kg(value: float) -> str:
    """Stable kilogram string. Trailing zeros trimmed, but never bare ".".

    Uses a fixed precision then strips trailing zeros so equal numeric values
    always render identically (e.g. 2.0 and 2.00 both -> "2 kg" ... here we keep
    one decimal minimum for readability: "2.0 kg").
    """
    # Round to a fixed precision for determinism, then render with one decimal
    # place minimum so values like 2.4 stay "2.4 kg" and 2.0 stays "2.0 kg".
    rounded = round(float(value), 6)
    text = f"{rounded:.1f}"
    return f"{text} kg"


def _coerce_number(value: Any) -> Optional[float]:
    """Return a float for real numeric input, else None. Bools are rejected."""
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _skip(message: str) -> SandboxReport:
    return SandboxReport(
        sandbox=_SANDBOX_NAME,
        status="skipped",
        checks=[
            SandboxCheckResult(
                check_id="units_math.input",
                ok=True,
                severity="info",
                message=message,
                metadata={"reason": "missing_or_invalid_input"},
            )
        ],
    )


def run_units_math_check(inputs: Optional[dict[str, Any]]) -> SandboxReport:
    """Run the deterministic mass-balance check over ``inputs``."""
    if not isinstance(inputs, dict):
        return _skip("units_math requires a dict of inputs; none was provided.")

    declared = _coerce_number(inputs.get("declared_total_mass_kg"))
    if declared is None:
        return _skip(
            "units_math requires a numeric 'declared_total_mass_kg'."
        )

    raw_components = inputs.get("component_masses_kg")
    if not isinstance(raw_components, (list, tuple)) or len(raw_components) == 0:
        return _skip(
            "units_math requires a non-empty 'component_masses_kg' list."
        )

    components: list[float] = []
    for item in raw_components:
        number = _coerce_number(item)
        if number is None:
            return _skip(
                "units_math 'component_masses_kg' must contain only numbers."
            )
        components.append(number)

    tolerance = _coerce_number(inputs.get("tolerance_kg"))
    if tolerance is None:
        tolerance = _DEFAULT_TOLERANCE_KG
    tolerance = abs(tolerance)

    summed = round(sum(components), 6)
    declared = round(declared, 6)
    delta = round(abs(summed - declared), 6)

    metadata = {
        "declared_total_mass_kg": declared,
        "summed_component_mass_kg": summed,
        "delta_kg": delta,
        "tolerance_kg": round(tolerance, 6),
        "component_count": len(components),
    }

    if delta <= tolerance:
        check = SandboxCheckResult(
            check_id=_CHECK_ID,
            ok=True,
            severity="info",
            message="Declared total mass matches summed component mass within tolerance.",
            expected=_format_kg(summed),
            actual=_format_kg(declared),
            metadata=metadata,
        )
        return SandboxReport(
            sandbox=_SANDBOX_NAME,
            status="passed",
            checks=[check],
        )

    check = SandboxCheckResult(
        check_id=_CHECK_ID,
        ok=False,
        severity="warning",
        message="Declared total mass does not match summed component mass.",
        expected=_format_kg(summed),
        actual=_format_kg(declared),
        metadata=metadata,
    )
    return SandboxReport(
        sandbox=_SANDBOX_NAME,
        status="completed",
        checks=[check],
    )
