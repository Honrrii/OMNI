"""Phase 10 Stage 3A — finding-shape characterization tests.

These are CHARACTERIZATION tests, not schema-replacement tests. They document
and lock down the finding-like shapes that exist in the deterministic mission
graph review TODAY, so that Stage 3B can add a projection helper (e.g. a
unified Finding view) with confidence that it preserves the current contract.

Scope intentionally narrow:
  - MissionGraphReviewIssue  (backend/app/mission_graph/reviewer.py)
  - ConsistencyWarning       (backend/app/mission_graph/schemas.py)
  - MissionGraphReview output preservation

Nothing here proposes a unified Finding schema, changes runtime behavior, or
touches exported JSON fields. If a future change alters these shapes, these
tests are expected to fail loudly so the change is reviewed deliberately.

No model calls. No file I/O. Fully deterministic (review_graph is pure).
"""
from __future__ import annotations

from backend.app.mission_graph.reviewer import (
    MissionGraphReview,
    MissionGraphReviewIssue,
    review_graph,
)
from backend.app.mission_graph.schemas import (
    CadFeature,
    Component,
    ConsistencyWarning,
    MissionKnowledgeGraph,
    Ros2Node,
)
from backend.app.mission_graph.finding_projection import (
    project_consistency_warning,
    project_review_findings,
    project_review_issue,
)


# The exact normalized finding schema Stage 3B projects onto. Locked here so a
# future change to the projection surfaces as a deliberate test update.
PROJECTED_FINDING_KEYS = {
    "id",
    "code",
    "source",
    "category",
    "severity",
    "status",
    "message",
    "recommendation",
    "related_ids",
    "file",
    "evidence_ids",
    "requires_human_review",
    "metadata",
}


def _graph(**kwargs) -> MissionKnowledgeGraph:
    return MissionKnowledgeGraph(
        graph_id="test", generated_at="2026-05-24T00:00:00+00:00", **kwargs
    )


def _graph_with_findings() -> MissionKnowledgeGraph:
    """A graph that deterministically produces every issue category today."""
    return _graph(
        components=[Component(id="c1", name="Sensor")],          # COMP_* issues
        ros2_nodes=[Ros2Node(id="n1", name="lonely_node")],      # NODE_* issue
        cad_features=[CadFeature(id="f1")],                      # CAD_* issue
    )


# Severity vocabularies currently in use. Kept as documentation of the present
# contract — Stage 3B's projection should map onto (a subset of) these.
ISSUE_SEVERITY_VOCAB = {"info", "warning", "error", "blocker"}
CONSISTENCY_SEVERITY_VOCAB = {"info", "warning", "error"}


# ---------------------------------------------------------------------------
# 1. MissionGraphReviewIssue shape
# ---------------------------------------------------------------------------

def test_review_issue_field_set_is_exactly_current_shape():
    """Lock the field set of MissionGraphReviewIssue as it exists today."""
    assert set(MissionGraphReviewIssue.model_fields) == {
        "code",
        "severity",
        "category",
        "message",
        "related_ids",
    }


def test_review_issue_instances_carry_all_fields():
    issues = review_graph(_graph_with_findings()).issues
    assert issues, "expected the characterization graph to produce issues"
    for issue in issues:
        dumped = issue.model_dump()
        assert set(dumped) == {"code", "severity", "category", "message", "related_ids"}
        assert isinstance(issue.code, str) and issue.code
        assert isinstance(issue.severity, str) and issue.severity
        assert isinstance(issue.category, str) and issue.category
        assert isinstance(issue.message, str) and issue.message
        assert isinstance(issue.related_ids, list)
        assert all(isinstance(rid, str) for rid in issue.related_ids)


# ---------------------------------------------------------------------------
# 2. ConsistencyWarning shape
# ---------------------------------------------------------------------------

def test_consistency_warning_field_set_is_exactly_current_shape():
    """Lock the field set of ConsistencyWarning as it exists today."""
    assert set(ConsistencyWarning.model_fields) == {
        "id",
        "code",
        "severity",
        "message",
        "related_ids",
    }


def test_consistency_warning_instance_carries_all_fields():
    cw = ConsistencyWarning(
        id="w1",
        code="ORPHAN_TOPIC",
        message="topic has no subscribers",
        related_ids=["t1"],
    )
    dumped = cw.model_dump()
    assert set(dumped) == {"id", "code", "severity", "message", "related_ids"}
    assert cw.id == "w1"
    assert cw.code == "ORPHAN_TOPIC"
    assert isinstance(cw.severity, str) and cw.severity
    assert cw.related_ids == ["t1"]


def test_consistency_warning_default_severity_is_warning():
    """Default severity is 'warning' — documented so Stage 3B can rely on it."""
    cw = ConsistencyWarning(id="w1", code="X", message="m")
    assert cw.severity == "warning"


# ---------------------------------------------------------------------------
# 3. MissionGraphReview output preserves the finding-bearing fields
# ---------------------------------------------------------------------------

def test_review_output_preserves_finding_fields():
    cw = ConsistencyWarning(id="w1", code="ORPHAN_TOPIC", message="topic orphaned")
    review = review_graph(_graph_with_findings().model_copy(
        update={"consistency_warnings": [cw]}
    ))
    assert isinstance(review, MissionGraphReview)

    # issues: structured MissionGraphReviewIssue objects
    assert isinstance(review.issues, list)
    assert review.issues and all(
        isinstance(i, MissionGraphReviewIssue) for i in review.issues
    )

    # warnings: legacy list[str], derived from issue messages
    assert isinstance(review.warnings, list)
    assert all(isinstance(w, str) for w in review.warnings)

    # recommendations: list[str]
    assert isinstance(review.recommendations, list)
    assert all(isinstance(r, str) for r in review.recommendations)

    # consistency_warnings: structured ConsistencyWarning objects, passed through
    assert isinstance(review.consistency_warnings, list)
    assert all(
        isinstance(c, ConsistencyWarning) for c in review.consistency_warnings
    )
    assert review.consistency_warnings[0].code == "ORPHAN_TOPIC"


# ---------------------------------------------------------------------------
# 4. Severity vocabulary is stable enough for future projection
# ---------------------------------------------------------------------------

def test_issue_severity_values_within_known_vocabulary():
    """Every issue severity emitted today is a lowercase string in the vocab."""
    issues = review_graph(_graph_with_findings()).issues
    observed = {i.severity for i in issues}
    assert observed, "expected at least one issue severity to observe"
    for sev in observed:
        assert isinstance(sev, str)
        assert sev == sev.lower()
        assert sev in ISSUE_SEVERITY_VOCAB, (
            f"unexpected issue severity {sev!r}; "
            f"update ISSUE_SEVERITY_VOCAB deliberately if the contract changed"
        )


def test_consistency_warning_severity_values_within_known_vocabulary():
    """ConsistencyWarning severity accepts exactly the documented vocabulary."""
    for sev in CONSISTENCY_SEVERITY_VOCAB:
        cw = ConsistencyWarning(id="w", code="C", message="m", severity=sev)
        assert cw.severity == sev
        assert isinstance(cw.severity, str)


# ---------------------------------------------------------------------------
# 5. Legacy warnings remain a derived list[str], not removed
# ---------------------------------------------------------------------------

def test_legacy_warnings_remain_derived_list_of_str():
    review = review_graph(_graph_with_findings())
    # Still present as a list of plain strings (backwards-compatible surface).
    assert isinstance(review.warnings, list)
    assert review.warnings, "expected derived warnings for a graph with issues"
    assert all(isinstance(w, str) for w in review.warnings)
    # Derived from issue messages and kept in sync, one-for-one in order.
    assert review.warnings == [i.message for i in review.issues]


def test_empty_graph_keeps_empty_warning_list_not_none():
    review = review_graph(_graph())
    assert review.warnings == []
    assert isinstance(review.warnings, list)


# ===========================================================================
# Stage 3B — internal mission graph finding projection helper.
#
# These exercise backend.app.mission_graph.finding_projection, an internal,
# test-facing view. They assert the projection is faithful and side-effect
# free, and that producing it does NOT change the exported MissionGraphReview
# shape (no "findings" key, legacy warnings untouched).
# ===========================================================================


def test_project_review_issue_returns_exact_field_set():
    issue = MissionGraphReviewIssue(
        code="COMP_MISSING_POWER_RAIL",
        severity="warning",
        category="component",
        message="component 'Sensor' (c1) missing power_rail_id",
        related_ids=["c1"],
    )
    finding = project_review_issue(issue)
    assert set(finding) == PROJECTED_FINDING_KEYS


def test_project_review_issue_preserves_core_fields():
    issue = MissionGraphReviewIssue(
        code="NODE_MISSING_COMPONENT_LINK",
        severity="warning",
        category="ros2",
        message="ros2_node 'lonely_node' (n1) missing component_ids",
        related_ids=["n1"],
    )
    finding = project_review_issue(issue)
    assert finding["id"] is None
    assert finding["code"] == "NODE_MISSING_COMPONENT_LINK"
    assert finding["source"] == "mission_graph_review"
    assert finding["category"] == "ros2"
    assert finding["severity"] == "warning"
    assert finding["status"] == "open"
    assert finding["message"] == issue.message
    assert finding["recommendation"] is None
    assert finding["related_ids"] == ["n1"]
    assert finding["file"] is None
    assert finding["evidence_ids"] == []
    assert finding["requires_human_review"] is False
    assert finding["metadata"] == {"origin": "MissionGraphReviewIssue"}


def test_project_consistency_warning_returns_exact_field_set():
    cw = ConsistencyWarning(
        id="w1", code="ORPHAN_TOPIC", message="topic has no subscribers",
        related_ids=["t1"],
    )
    finding = project_consistency_warning(cw)
    assert set(finding) == PROJECTED_FINDING_KEYS


def test_project_consistency_warning_preserves_core_fields():
    cw = ConsistencyWarning(
        id="w42", code="ORPHAN_TOPIC", severity="error",
        message="topic has no subscribers", related_ids=["t1", "t2"],
    )
    finding = project_consistency_warning(cw)
    assert finding["id"] == "w42"
    assert finding["code"] == "ORPHAN_TOPIC"
    assert finding["source"] == "mission_graph_consistency"
    assert finding["category"] == "consistency"
    assert finding["severity"] == "error"
    assert finding["status"] == "open"
    assert finding["message"] == "topic has no subscribers"
    assert finding["recommendation"] is None
    assert finding["related_ids"] == ["t1", "t2"]
    assert finding["file"] is None
    assert finding["evidence_ids"] == []
    assert finding["requires_human_review"] is False
    assert finding["metadata"] == {"origin": "ConsistencyWarning"}


def test_project_review_findings_orders_issues_then_consistency():
    cw = ConsistencyWarning(id="w1", code="ORPHAN_TOPIC", message="topic orphaned")
    review = review_graph(_graph_with_findings().model_copy(
        update={"consistency_warnings": [cw]}
    ))
    findings = project_review_findings(review)

    expected = (
        [project_review_issue(i) for i in review.issues]
        + [project_consistency_warning(c) for c in review.consistency_warnings]
    )
    assert findings == expected

    # All issue-sourced findings precede all consistency-sourced ones.
    sources = [f["source"] for f in findings]
    n_issues = len(review.issues)
    assert sources[:n_issues] == ["mission_graph_review"] * n_issues
    assert set(sources[n_issues:]) == {"mission_graph_consistency"}


def test_projection_does_not_mutate_source_or_share_list_refs():
    issue = MissionGraphReviewIssue(
        code="COMP_MISSING_DATA_BUS", severity="warning",
        category="component", message="missing data bus", related_ids=["c1"],
    )
    cw = ConsistencyWarning(
        id="w1", code="ORPHAN_TOPIC", message="orphaned", related_ids=["t1"],
    )

    issue_finding = project_review_issue(issue)
    warning_finding = project_consistency_warning(cw)

    # related_ids in the projection is a distinct list object (a copy).
    assert issue_finding["related_ids"] is not issue.related_ids
    assert warning_finding["related_ids"] is not cw.related_ids

    # Mutating the projection must not affect the source object.
    issue_finding["related_ids"].append("MUTATED")
    warning_finding["related_ids"].append("MUTATED")
    assert issue.related_ids == ["c1"]
    assert cw.related_ids == ["t1"]


def test_review_model_dump_unchanged_and_has_no_findings_key():
    review = review_graph(_graph_with_findings())
    dumped = review.model_dump()

    # Projecting findings is non-mutating and adds nothing to the model.
    project_review_findings(review)
    assert review.model_dump() == dumped

    # The exported review shape gains no "findings" key.
    assert "findings" not in dumped
    # The compatibility surface is intact.
    assert set(dumped) == {
        "graph_id", "platform", "platform_normalized",
        "component_coverage", "ros2_coverage", "morphology_cad_coverage",
        "issues", "warnings", "recommendations", "consistency_warnings",
    }


def test_projection_keeps_legacy_warnings_derived_list_of_str():
    review = review_graph(_graph_with_findings())
    project_review_findings(review)
    assert isinstance(review.warnings, list)
    assert all(isinstance(w, str) for w in review.warnings)
    assert review.warnings == [i.message for i in review.issues]


def test_project_empty_review_returns_empty_list():
    review = review_graph(_graph())
    assert review.issues == []
    assert review.consistency_warnings == []
    assert project_review_findings(review) == []


def test_project_severity_normalization_known_values():
    for sev in ("info", "warning", "error", "blocker"):
        issue = MissionGraphReviewIssue(
            code="X", severity=sev, category="component", message="m",
        )
        assert project_review_issue(issue)["severity"] == sev


def test_project_severity_uppercase_known_value_is_lowercased():
    issue = MissionGraphReviewIssue(
        code="X", severity="ERROR", category="component", message="m",
    )
    assert project_review_issue(issue)["severity"] == "error"


def test_project_severity_empty_string_becomes_warning():
    issue = MissionGraphReviewIssue(
        code="X", severity="", category="component", message="m",
    )
    assert project_review_issue(issue)["severity"] == "warning"


def test_project_severity_unknown_string_preserved_lowercased():
    issue = MissionGraphReviewIssue(
        code="X", severity="Critical", category="component", message="m",
    )
    # Unknown, non-empty -> preserved (lowercased), NOT remapped to "warning".
    assert project_review_issue(issue)["severity"] == "critical"
