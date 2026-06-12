"""Raw sandbox report dataclasses (Phase 11 Stage 1).

Stdlib-only, deterministic, side-effect-free. These shapes are the raw output of
a sandbox check run. They are deliberately NOT the Phase 10 ``findings_projection``
shape — projection is a later stage. No timestamps, no UUIDs, no randomness.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class SandboxCheckResult:
    """A single deterministic check outcome.

    ``metadata`` is per-instance (default-factory dict) so two results never
    share the same mutable object.
    """

    check_id: str
    ok: bool
    severity: str
    message: str
    expected: Optional[str] = None
    actual: Optional[str] = None
    file: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Deterministic dict with a fixed key order and fresh objects.

        ``metadata`` is shallow-copied so callers cannot mutate the result's
        internal dict through the returned value.
        """
        return {
            "check_id": self.check_id,
            "ok": self.ok,
            "severity": self.severity,
            "message": self.message,
            "expected": self.expected,
            "actual": self.actual,
            "file": self.file,
            "metadata": dict(self.metadata),
        }


@dataclass
class SandboxReport:
    """A raw sandbox run report.

    ``schema`` is a stable version identifier. ``checks`` is rendered in the
    order it was supplied (deterministic check ordering is the caller's
    responsibility; the report preserves it).
    """

    sandbox: str
    status: str
    checks: list[SandboxCheckResult]
    schema: str = "omni.sandbox.report.v1"
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Deterministic dict with a fixed key order and fresh nested objects.

        Each check is serialized via its own ``to_dict``; the checks list and
        metadata dict are freshly built so the returned structure shares no
        mutable state with the report.
        """
        return {
            "schema": self.schema,
            "sandbox": self.sandbox,
            "status": self.status,
            "checks": [check.to_dict() for check in self.checks],
            "metadata": dict(self.metadata),
        }
