"""
OMNI Sandbox — internal finding projection (Phase 11 Stage 3).

Projects raw ``omni.sandbox.report.v1`` check shapes (``SandboxCheckResult`` and
its report dicts) into normalized finding dictionaries with the SAME key set as
the mission graph and engineering projections
(backend/app/mission_graph/finding_projection.py,
backend/app/engineering/finding_projection.py).

This is INTERNAL / TEST-FACING ONLY. It does NOT change any exported JSON, the
raw sandbox report shape, the runner, or runtime behavior. It adds no envelope
and no schema string. Pure functions, no file I/O, no model calls, no subprocess,
and no mutation of the inputs.

Accepts either dataclass instances or the report's ``to_dict``/``asdict``-style
dicts; both produce identical projections.
"""
from __future__ import annotations

from dataclasses import asdict, is_dataclass
from typing import Any, Optional, Union

from backend.app.sandbox.report import SandboxCheckResult, SandboxReport


# Known severities pass through (lowercased). Unknown non-empty strings are
# preserved lowercased rather than silently remapped, so a new severity surfaces
# instead of being hidden. Mirrors the engineering/mission graph projections.
_KNOWN_SEVERITIES = {"info", "warning", "error", "blocker"}


def _normalize_severity(severity: object) -> str:
    if not isinstance(severity, str):
        return "warning"
    cleaned = severity.strip().lower()
    if not cleaned:
        return "warning"
    return cleaned


def _as_check_dict(
    check: Union[SandboxCheckResult, dict[str, Any]],
) -> dict[str, Any]:
    """Coerce a dataclass check or a dict check into a plain dict."""
    if is_dataclass(check) and not isinstance(check, type):
        return asdict(check)
    if isinstance(check, dict):
        return dict(check)
    raise TypeError(f"unsupported check type for projection: {type(check)!r}")


def _as_report_dict(
    report: Union[SandboxReport, dict[str, Any]],
) -> dict[str, Any]:
    """Coerce a dataclass report or a dict report into a plain dict."""
    if is_dataclass(report) and not isinstance(report, type):
        return asdict(report)
    if isinstance(report, dict):
        return dict(report)
    raise TypeError(f"unsupported report type for projection: {type(report)!r}")


def project_sandbox_check_result(
    check: Union[SandboxCheckResult, dict[str, Any]],
    *,
    sandbox: Optional[str] = None,
) -> dict[str, Any]:
    """Project a single sandbox check into a normalized finding dict.

    ``expected`` and ``actual`` carry no slot in the canonical finding item
    shape, so they are routed into ``metadata`` rather than added as top-level
    keys. ``check.metadata`` is copied so mutating the projected result cannot
    mutate the source.
    """
    data = _as_check_dict(check)
    metadata = data.get("metadata")
    check_metadata = dict(metadata) if isinstance(metadata, dict) else {}

    return {
        "id": None,
        "code": data.get("check_id"),
        "source": f"sandbox_{sandbox}" if sandbox else "sandbox",
        "category": "sandbox",
        "severity": _normalize_severity(data.get("severity")),
        "status": "open",
        "message": data.get("message"),
        "recommendation": None,
        "related_ids": [],
        "file": data.get("file"),
        "evidence_ids": [],
        "requires_human_review": False,
        "metadata": {
            "origin": "SandboxCheckResult",
            "sandbox": sandbox,
            "expected": data.get("expected"),
            "actual": data.get("actual"),
            "check_metadata": check_metadata,
        },
    }


def project_sandbox_findings(
    report: Union[SandboxReport, dict[str, Any]],
) -> list[dict[str, Any]]:
    """Project a sandbox report's failing checks into normalized findings.

    Only checks where ``ok`` is False are projected, in their original order.
    Passing, skipped, and unknown-sandbox reports yield an empty list. The
    report is not mutated.
    """
    data = _as_report_dict(report)
    sandbox = data.get("sandbox")
    checks = data.get("checks") or []

    findings: list[dict[str, Any]] = []
    for check in checks:
        check_data = _as_check_dict(check)
        if check_data.get("ok") is False:
            findings.append(
                project_sandbox_check_result(check_data, sandbox=sandbox)
            )
    return findings
