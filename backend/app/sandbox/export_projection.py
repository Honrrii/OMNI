"""
OMNI Sandbox — additive findings_projection export envelope (Phase 11 Stage 4).

Builds a thin, additive envelope around a raw ``omni.sandbox.report.v1`` report's
projected findings, using the SAME envelope vocabulary documented for the Phase 10
findings_projection contract (``schema`` / ``source`` / ``origin_fields`` /
``count`` / ``items``), plus an additive ``source_schema`` provenance key.

This is a STANDALONE helper. The sandbox is not mission-integrated, so nothing
here touches export_manager, the mission runtime, or writes any file. Pure
function: no I/O, no model calls, no subprocess, no mutation of the input report.
The raw report shape is never changed and never gains a ``findings`` /
``findings_projection`` key — the envelope is returned to the caller, not
embedded in the report.
"""
from __future__ import annotations

from dataclasses import is_dataclass
from typing import Any, Union

from backend.app.sandbox.finding_projection import project_sandbox_findings
from backend.app.sandbox.report import SandboxReport


def _read_sandbox_name(report: Union[SandboxReport, dict[str, Any]]) -> Any:
    """Read the sandbox name from a SandboxReport or a report dict."""
    if is_dataclass(report) and not isinstance(report, type):
        return getattr(report, "sandbox", None)
    if isinstance(report, dict):
        return report.get("sandbox")
    raise TypeError(f"unsupported report type for projection: {type(report)!r}")


def build_sandbox_findings_projection(
    report: Union[SandboxReport, dict[str, Any]],
) -> dict[str, Any]:
    """Build the additive sandbox findings_projection envelope for ``report``.

    Reuses :func:`project_sandbox_findings` for the items (failing checks only,
    in order). Deterministic, pure, no I/O, and no mutation of ``report``.
    """
    name = _read_sandbox_name(report)
    items = project_sandbox_findings(report)
    source = f"sandbox_{name}" if name else "sandbox"

    return {
        "schema": "omni.sandbox.findings_projection.v1",
        "source": source,
        "source_schema": "omni.sandbox.report.v1",
        "origin_fields": ["checks"],
        "count": len(items),
        "items": items,
    }
