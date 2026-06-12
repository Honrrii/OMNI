"""Phase 10 Stage 3D — engineering gate finding-shape characterization tests.

These are CHARACTERIZATION tests, not schema-replacement tests. They document
and lock down the finding-like shapes produced TODAY by the two deterministic
engineering gate validators, so a future projection helper (a later stage) can
be added with confidence that it preserves the current contract:

  - backend/app/engineering/kicad_knowledge_gate_validator.py
  - backend/app/engineering/morphology_gate_validator.py

Both use the same issue shape (rule_id, severity, message, file) and the same
report shape (validator, status, summary, issues). Nothing here adds a
projection helper, changes runtime code, or changes exported JSON.

Tests exercise only public entry points (validate_* and build_report) plus the
public dataclasses. Fully deterministic: filesystem-only, no model calls.
"""
from __future__ import annotations

from dataclasses import fields

from backend.app.engineering.kicad_knowledge_gate_validator import (
    KiCadGateIssue,
    build_report as kicad_build_report,
    validate_kicad_package,
)
from backend.app.engineering.morphology_gate_validator import (
    MorphologyGateIssue,
    build_report as morph_build_report,
    validate_morphology_export,
)

EXPECTED_ISSUE_FIELDS = ("rule_id", "severity", "message", "file")
EXPECTED_SUMMARY_KEYS = {"blockers", "warnings", "info", "total_issues"}


# ===========================================================================
# KiCad knowledge gate validator
# ===========================================================================

def test_kicad_gate_issue_dataclass_fields_exact():
    names = tuple(f.name for f in fields(KiCadGateIssue))
    assert names == EXPECTED_ISSUE_FIELDS


def test_kicad_missing_dir_report_shape(tmp_path):
    missing = tmp_path / "nonexistent_kicad_root"
    report = validate_kicad_package(missing)

    assert report["validator"] == "kicad_knowledge_gate_validator"
    assert report["status"] == "failed"

    assert set(report["summary"]) == EXPECTED_SUMMARY_KEYS

    # Exactly one blocker issue for a missing directory.
    assert isinstance(report["issues"], list)
    assert len(report["issues"]) == 1
    issue = report["issues"][0]
    assert issue["severity"] == "blocker"
    assert report["summary"]["blockers"] == 1
    assert report["summary"]["total_issues"] == 1


def test_kicad_report_issue_dicts_have_exact_keys(tmp_path):
    report = validate_kicad_package(tmp_path / "nonexistent_kicad_root")
    for issue in report["issues"]:
        assert set(issue) == set(EXPECTED_ISSUE_FIELDS)


def test_kicad_summary_counts_match_issue_severities():
    from pathlib import Path
    issues = [
        KiCadGateIssue("R.B1", "blocker", "b1"),
        KiCadGateIssue("R.B2", "blocker", "b2"),
        KiCadGateIssue("R.W1", "warning", "w1"),
        KiCadGateIssue("R.I1", "info", "i1"),
        KiCadGateIssue("R.I2", "info", "i2"),
    ]
    report = kicad_build_report(Path("/tmp/kicad"), issues)
    summary = report["summary"]
    assert summary["blockers"] == 2
    assert summary["warnings"] == 1
    assert summary["info"] == 2
    assert summary["total_issues"] == 5
    # Counts are derived from the issue severities, one-for-one.
    assert summary["blockers"] == sum(1 for i in issues if i.severity == "blocker")
    assert summary["warnings"] == sum(1 for i in issues if i.severity == "warning")
    assert summary["info"] == sum(1 for i in issues if i.severity == "info")


def test_kicad_status_mapping_blocker_is_failed():
    from pathlib import Path
    report = kicad_build_report(Path("/tmp/kicad"), [
        KiCadGateIssue("R.B", "blocker", "b"),
        KiCadGateIssue("R.W", "warning", "w"),
        KiCadGateIssue("R.I", "info", "i"),
    ])
    assert report["status"] == "failed"


def test_kicad_status_mapping_warnings_only_is_passed_with_warnings():
    from pathlib import Path
    report = kicad_build_report(Path("/tmp/kicad"), [
        KiCadGateIssue("R.W", "warning", "w"),
    ])
    assert report["status"] == "passed_with_warnings"


def test_kicad_status_mapping_info_only_is_passed():
    from pathlib import Path
    report = kicad_build_report(Path("/tmp/kicad"), [
        KiCadGateIssue("R.I", "info", "i"),
    ])
    assert report["status"] == "passed"


def test_kicad_report_has_no_findings_projection_yet(tmp_path):
    report = validate_kicad_package(tmp_path / "nonexistent_kicad_root")
    assert "findings_projection" not in report


# ===========================================================================
# Morphology gate validator
# ===========================================================================

def test_morphology_gate_issue_dataclass_fields_exact():
    names = tuple(f.name for f in fields(MorphologyGateIssue))
    assert names == EXPECTED_ISSUE_FIELDS


def test_morphology_missing_dir_report_shape(tmp_path):
    missing = tmp_path / "nonexistent_export_root"
    report = validate_morphology_export(missing)

    assert report["validator"] == "morphology_gate_validator"
    assert report["status"] == "failed"

    assert set(report["summary"]) == EXPECTED_SUMMARY_KEYS

    assert isinstance(report["issues"], list)
    assert len(report["issues"]) == 1
    issue = report["issues"][0]
    assert issue["severity"] == "blocker"
    assert report["summary"]["blockers"] == 1
    assert report["summary"]["total_issues"] == 1


def test_morphology_missing_plan_returns_morph_fs_001(tmp_path):
    # An existing export dir with no artifacts/morphology_plan.json must yield
    # exactly the MORPH.FS.001 blocker.
    export_dir = tmp_path / "mission_export"
    export_dir.mkdir()
    report = validate_morphology_export(export_dir)

    assert report["status"] == "failed"
    assert len(report["issues"]) == 1
    issue = report["issues"][0]
    assert issue["rule_id"] == "MORPH.FS.001"
    assert issue["severity"] == "blocker"
    assert issue["file"] == "artifacts/morphology_plan.json"


def test_morphology_report_issue_dicts_have_exact_keys(tmp_path):
    report = validate_morphology_export(tmp_path / "nonexistent_export_root")
    for issue in report["issues"]:
        assert set(issue) == set(EXPECTED_ISSUE_FIELDS)


def test_morphology_summary_counts_match_issue_severities():
    from pathlib import Path
    issues = [
        MorphologyGateIssue("R.B1", "blocker", "b1"),
        MorphologyGateIssue("R.W1", "warning", "w1"),
        MorphologyGateIssue("R.W2", "warning", "w2"),
        MorphologyGateIssue("R.W3", "warning", "w3"),
        MorphologyGateIssue("R.I1", "info", "i1"),
    ]
    report = morph_build_report(Path("/tmp/export"), {}, issues)
    summary = report["summary"]
    assert summary["blockers"] == 1
    assert summary["warnings"] == 3
    assert summary["info"] == 1
    assert summary["total_issues"] == 5
    assert summary["blockers"] == sum(1 for i in issues if i.severity == "blocker")
    assert summary["warnings"] == sum(1 for i in issues if i.severity == "warning")
    assert summary["info"] == sum(1 for i in issues if i.severity == "info")


def test_morphology_status_mapping_blocker_is_failed():
    from pathlib import Path
    report = morph_build_report(Path("/tmp/export"), {}, [
        MorphologyGateIssue("R.B", "blocker", "b"),
        MorphologyGateIssue("R.W", "warning", "w"),
    ])
    assert report["status"] == "failed"


def test_morphology_status_mapping_warnings_only_is_passed_with_warnings():
    from pathlib import Path
    report = morph_build_report(Path("/tmp/export"), {}, [
        MorphologyGateIssue("R.W", "warning", "w"),
    ])
    assert report["status"] == "passed_with_warnings"


def test_morphology_status_mapping_info_only_is_passed():
    from pathlib import Path
    report = morph_build_report(Path("/tmp/export"), {}, [
        MorphologyGateIssue("R.I", "info", "i"),
    ])
    assert report["status"] == "passed"


def test_morphology_report_has_no_findings_projection_yet(tmp_path):
    report = validate_morphology_export(tmp_path / "nonexistent_export_root")
    assert "findings_projection" not in report
