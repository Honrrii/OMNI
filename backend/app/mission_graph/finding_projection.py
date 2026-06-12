"""
Mission Knowledge Graph — internal finding projection (Phase 10 Stage 3B).

Projects the deterministic mission graph review's finding-like shapes
(MissionGraphReviewIssue, ConsistencyWarning) into normalized finding
dictionaries with a single, stable schema.

This is INTERNAL / TEST-FACING ONLY. It does NOT change any exported JSON,
the MissionGraphReview model, or runtime behavior. Nothing here writes files
or calls a model. Pure functions, no side effects on the source objects.
"""
from __future__ import annotations

from backend.app.mission_graph.reviewer import (
    MissionGraphReview,
    MissionGraphReviewIssue,
)
from backend.app.mission_graph.schemas import ConsistencyWarning


# Known severities pass through unchanged (lowercased). Unknown non-empty
# strings are preserved lowercased rather than silently remapped, so that a
# new severity surfaces instead of being hidden.
_KNOWN_SEVERITIES = {"info", "warning", "error", "blocker"}


def _normalize_severity(severity: object) -> str:
    """Normalize a severity value.

    - Known lowercase values map to themselves.
    - Empty or non-string values become "warning".
    - Unknown non-empty strings are preserved, lowercased.
    """
    if not isinstance(severity, str):
        return "warning"
    cleaned = severity.strip().lower()
    if not cleaned:
        return "warning"
    if cleaned in _KNOWN_SEVERITIES:
        return cleaned
    return cleaned


def project_review_issue(issue: MissionGraphReviewIssue) -> dict[str, object]:
    """Project a MissionGraphReviewIssue into a normalized finding dict."""
    return {
        "id": None,
        "code": issue.code,
        "source": "mission_graph_review",
        "category": issue.category,
        "severity": _normalize_severity(issue.severity),
        "status": "open",
        "message": issue.message,
        "recommendation": None,
        "related_ids": list(issue.related_ids),
        "file": None,
        "evidence_ids": [],
        "requires_human_review": False,
        "metadata": {"origin": "MissionGraphReviewIssue"},
    }


def project_consistency_warning(warning: ConsistencyWarning) -> dict[str, object]:
    """Project a ConsistencyWarning into a normalized finding dict."""
    return {
        "id": warning.id,
        "code": warning.code,
        "source": "mission_graph_consistency",
        "category": "consistency",
        "severity": _normalize_severity(warning.severity),
        "status": "open",
        "message": warning.message,
        "recommendation": None,
        "related_ids": list(warning.related_ids),
        "file": None,
        "evidence_ids": [],
        "requires_human_review": False,
        "metadata": {"origin": "ConsistencyWarning"},
    }


def project_review_findings(review: MissionGraphReview) -> list[dict[str, object]]:
    """Project a full review into normalized findings.

    Review issues come first (in order), then consistency warnings (in order).
    An empty review yields an empty list.
    """
    findings: list[dict[str, object]] = [
        project_review_issue(issue) for issue in review.issues
    ]
    findings.extend(
        project_consistency_warning(warning)
        for warning in review.consistency_warnings
    )
    return findings
