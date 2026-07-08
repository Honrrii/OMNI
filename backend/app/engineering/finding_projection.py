"""
Engineering gate validators — internal finding projection (Phase 10 Stage 3E).

Projects the deterministic engineering gate finding-like shapes
(KiCadGateIssue, MorphologyGateIssue, and their report dicts) into normalized
finding dictionaries with the SAME key set as the mission graph projection
(backend/app/mission_graph/finding_projection.py).

This is INTERNAL / TEST-FACING ONLY. It does NOT change any exported JSON,
the validators, or runtime behavior. Pure functions, no file I/O, no model
calls, and no mutation of the inputs.

Accepts either dataclass instances or the report's ``asdict``-style dicts;
both produce identical issue projections.
"""
from __future__ import annotations

from dataclasses import asdict, is_dataclass

from backend.app.engineering.kicad_knowledge_gate_validator import KiCadGateIssue
from backend.app.engineering.morphology_gate_validator import MorphologyGateIssue


# Known severities pass through (lowercased). Unknown non-empty strings are
# preserved lowercased rather than silently remapped, so a new severity
# surfaces instead of being hidden. Mirrors the mission graph projection.
_KNOWN_SEVERITIES = {"info", "warning", "error", "blocker"}


def _normalize_severity(severity: object) -> str:
    if not isinstance(severity, str):
        return "warning"
    cleaned = severity.strip().lower()
    if not cleaned:
        return "warning"
    return cleaned


def _as_issue_dict(issue: object) -> dict[str, object]:
    """Coerce a dataclass issue or a dict issue into a plain dict."""
    if is_dataclass(issue) and not isinstance(issue, type):
        return asdict(issue)
    if isinstance(issue, dict):
        return dict(issue)
    raise TypeError(f"unsupported issue type for projection: {type(issue)!r}")


def _project_issue(
    issue: object,
    *,
    source: str,
    origin: str,
    validator: str,
) -> dict[str, object]:
    data = _as_issue_dict(issue)
    return {
        "id": None,
        "code": data.get("rule_id"),
        "source": source,
        "category": "engineering",
        "severity": _normalize_severity(data.get("severity")),
        "status": "open",
        "message": data.get("message"),
        "recommendation": None,
        "related_ids": [],
        "file": data.get("file"),
        "evidence_ids": [],
        "requires_human_review": False,
        "metadata": {"origin": origin, "validator": validator},
    }


def project_kicad_gate_issue(
    issue: KiCadGateIssue | dict[str, object],
) -> dict[str, object]:
    """Project a single KiCad gate issue into a normalized finding dict."""
    return _project_issue(
        issue,
        source="kicad_knowledge_gate",
        origin="KiCadGateIssue",
        validator="kicad_knowledge_gate_validator",
    )


def project_morphology_gate_issue(
    issue: MorphologyGateIssue | dict[str, object],
) -> dict[str, object]:
    """Project a single morphology gate issue into a normalized finding dict."""
    return _project_issue(
        issue,
        source="morphology_gate",
        origin="MorphologyGateIssue",
        validator="morphology_gate_validator",
    )


# Stable, scalar report-context keys that may be folded into each projected
# finding's metadata when present. Deliberately small — no raw/huge payloads.
_KICAD_CONTEXT_KEYS = ("kicad_dir",)
_MORPHOLOGY_CONTEXT_KEYS = ("export_dir", "morphology_id", "project_family")


def _report_context(report: dict[str, object], keys: tuple[str, ...]) -> dict[str, object]:
    context: dict[str, object] = {}
    for key in keys:
        if key in report and report[key] is not None:
            context[key] = report[key]
    status = report.get("status")
    if status is not None:
        context["report_status"] = status
    return context


def project_kicad_gate_findings(report: dict[str, object]) -> list[dict[str, object]]:
    """Project a KiCad gate report's issues, in order. No issues -> []."""
    issues = report.get("issues") or []
    context = _report_context(report, _KICAD_CONTEXT_KEYS)
    findings: list[dict[str, object]] = []
    for issue in issues:
        finding = project_kicad_gate_issue(issue)
        finding["metadata"].update(context)
        findings.append(finding)
    return findings


def project_morphology_gate_findings(report: dict[str, object]) -> list[dict[str, object]]:
    """Project a morphology gate report's issues, in order. No issues -> []."""
    issues = report.get("issues") or []
    context = _report_context(report, _MORPHOLOGY_CONTEXT_KEYS)
    findings: list[dict[str, object]] = []
    for issue in issues:
        finding = project_morphology_gate_issue(issue)
        finding["metadata"].update(context)
        findings.append(finding)
    return findings
