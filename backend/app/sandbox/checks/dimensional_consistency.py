"""Dimensional consistency sandbox check (Phase 11 Stage 2).

Validate that a declared quantity carries the expected physical dimension. Pure
Python only — no pint, no external binaries, no I/O.

Expected input shape::

    {
        "quantity": {
            "name": "wing_span",
            "value": 1.2,
            "unit": "m",
            "dimension": "length",
        },
        "expected_dimension": "length",
    }

Outcomes:
- declared dimension matches expected -> status "passed"
- mismatch                            -> status "completed", one "warning" check
- missing/invalid input              -> status "skipped", one "info" check
"""
from __future__ import annotations

from typing import Any, Optional

from backend.app.sandbox.report import SandboxCheckResult, SandboxReport

_SANDBOX_NAME = "dimensional_consistency"
_CHECK_ID = "dimensional.consistency"


def _skip(message: str) -> SandboxReport:
    return SandboxReport(
        sandbox=_SANDBOX_NAME,
        status="skipped",
        checks=[
            SandboxCheckResult(
                check_id="dimensional_consistency.input",
                ok=True,
                severity="info",
                message=message,
                metadata={"reason": "missing_or_invalid_input"},
            )
        ],
    )


def _clean_dimension(value: Any) -> Optional[str]:
    if not isinstance(value, str):
        return None
    cleaned = value.strip().lower()
    return cleaned or None


def run_dimensional_consistency_check(
    inputs: Optional[dict[str, Any]],
) -> SandboxReport:
    """Run the deterministic dimensional consistency check over ``inputs``."""
    if not isinstance(inputs, dict):
        return _skip(
            "dimensional_consistency requires a dict of inputs; none was provided."
        )

    quantity = inputs.get("quantity")
    if not isinstance(quantity, dict):
        return _skip(
            "dimensional_consistency requires a 'quantity' dict."
        )

    expected = _clean_dimension(inputs.get("expected_dimension"))
    if expected is None:
        return _skip(
            "dimensional_consistency requires a non-empty 'expected_dimension' string."
        )

    actual = _clean_dimension(quantity.get("dimension"))
    if actual is None:
        return _skip(
            "dimensional_consistency requires the quantity to declare a 'dimension'."
        )

    name = quantity.get("name")
    name_str = name if isinstance(name, str) and name.strip() else "quantity"
    unit = quantity.get("unit")

    metadata = {
        "quantity_name": name_str,
        "expected_dimension": expected,
        "actual_dimension": actual,
        "unit": unit if isinstance(unit, str) else None,
    }

    if actual == expected:
        check = SandboxCheckResult(
            check_id=_CHECK_ID,
            ok=True,
            severity="info",
            message=f"Quantity '{name_str}' has the expected dimension.",
            expected=expected,
            actual=actual,
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
        message=(
            f"Quantity '{name_str}' has dimension '{actual}', "
            f"expected '{expected}'."
        ),
        expected=expected,
        actual=actual,
        metadata=metadata,
    )
    return SandboxReport(
        sandbox=_SANDBOX_NAME,
        status="completed",
        checks=[check],
    )
