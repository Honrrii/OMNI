"""Sandbox runner (Phase 11 Stage 1).

Explicit, side-effect-free dispatch to a named sandbox check. No autostart, no
file I/O, no model calls, no subprocess. An unknown sandbox name is a safe
"skipped" report rather than an error.
"""
from __future__ import annotations

from typing import Any, Optional

from backend.app.sandbox.checks.artifact_shape import run_artifact_shape_check
from backend.app.sandbox.checks.dimensional_consistency import (
    run_dimensional_consistency_check,
)
from backend.app.sandbox.checks.equation_sanity import run_equation_sanity_check
from backend.app.sandbox.checks.units_math import run_units_math_check
from backend.app.sandbox.report import SandboxCheckResult, SandboxReport

# Explicit name -> check function dispatch table. Deterministic, no autostart.
_CHECKS = {
    "units_math": run_units_math_check,
    "dimensional_consistency": run_dimensional_consistency_check,
    "equation_sanity": run_equation_sanity_check,
    "artifact_shape": run_artifact_shape_check,
}


def _unknown(name: str) -> SandboxReport:
    return SandboxReport(
        sandbox=name,
        status="skipped",
        checks=[
            SandboxCheckResult(
                check_id="sandbox.unknown",
                ok=True,
                severity="info",
                message=f"Unknown sandbox '{name}'; nothing to run, skipped.",
                metadata={"reason": "unknown_sandbox"},
            )
        ],
    )


def run_sandbox(
    name: str,
    inputs: Optional[dict[str, Any]] = None,
) -> SandboxReport:
    """Run a named sandbox check explicitly and return its raw report.

    Dispatches the registered sandbox checks (``units_math``,
    ``dimensional_consistency``, ``equation_sanity``, ``artifact_shape``). Any
    other name yields a safe skipped report. Deterministic: the same name +
    inputs always produce an equal report.
    """
    check = _CHECKS.get(name)
    if check is not None:
        return check(inputs)
    return _unknown(name)
