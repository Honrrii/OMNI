"""OMNI Sandbox — deterministic local verification harness (Phase 11 Stage 1).

A tiny, additive, read-only verification chamber. Stage 1 provides only the raw
report shape (``SandboxReport`` / ``SandboxCheckResult``), an explicit ``run_sandbox``
entry point, and a single external-binary-free units/math check.

Design rules (Stage 1):
- Pure standard library. No model calls, no file I/O, no subprocess, no shell.
- Deterministic: the same input yields byte-identical dictionaries.
- No timestamps, no UUIDs, no randomness in report output.
- Raw reports only — NO ``findings`` / ``findings_projection`` here yet. Projection
  into the Phase 10 normalized findings shape is a later, separate stage.
"""

from backend.app.sandbox.report import SandboxCheckResult, SandboxReport
from backend.app.sandbox.runner import run_sandbox

__all__ = ["SandboxCheckResult", "SandboxReport", "run_sandbox"]
