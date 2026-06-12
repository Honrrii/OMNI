"""Sandbox runner (Phase 11 Stage 1).

Explicit, side-effect-free dispatch to a named sandbox check. No autostart, no
file I/O, no model calls, no subprocess. An unknown sandbox name is a safe
"skipped" report rather than an error.
"""
from __future__ import annotations

from typing import Any, Optional

from backend.app.sandbox.checks.units_math import run_units_math_check
from backend.app.sandbox.report import SandboxCheckResult, SandboxReport


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

    Stage 1 dispatches only ``"units_math"``. Any other name yields a safe
    skipped report. Deterministic: the same name + inputs always produce an
    equal report.
    """
    if name == "units_math":
        return run_units_math_check(inputs)
    return _unknown(name)
