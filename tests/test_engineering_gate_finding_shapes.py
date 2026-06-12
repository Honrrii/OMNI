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
from backend.app.engineering.finding_projection import (
    project_kicad_gate_findings,
    project_kicad_gate_issue,
    project_morphology_gate_findings,
    project_morphology_gate_issue,
)

EXPECTED_ISSUE_FIELDS = ("rule_id", "severity", "message", "file")
EXPECTED_SUMMARY_KEYS = {"blockers", "warnings", "info", "total_issues"}

# The normalized finding key set shared with the mission graph projection.
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


# ===========================================================================
# Stage 3E — internal engineering gate finding projection helper.
#
# Exercises backend.app.engineering.finding_projection, an internal,
# test-facing view that normalizes KiCad/morphology gate issues onto the same
# finding key set as the mission graph projection. Asserts faithful mapping,
# dict/dataclass equivalence, order preservation, side-effect freedom, and
# that the validators still export no findings_projection key.
# ===========================================================================


def test_project_kicad_gate_issue_exact_key_set():
    issue = KiCadGateIssue("KICAD.FS.README_MD", "blocker", "Missing README.md", "README.md")
    finding = project_kicad_gate_issue(issue)
    assert set(finding) == PROJECTED_FINDING_KEYS


def test_project_morphology_gate_issue_exact_key_set():
    issue = MorphologyGateIssue("MORPH.FS.001", "blocker", "Missing plan.", "artifacts/morphology_plan.json")
    finding = project_morphology_gate_issue(issue)
    assert set(finding) == PROJECTED_FINDING_KEYS


def test_project_kicad_gate_issue_preserves_core_fields():
    issue = KiCadGateIssue("KICAD.PATH.001", "blocker", "dir missing", "generated_kicad")
    finding = project_kicad_gate_issue(issue)
    assert finding["id"] is None
    assert finding["code"] == "KICAD.PATH.001"
    assert finding["source"] == "kicad_knowledge_gate"
    assert finding["category"] == "engineering"
    assert finding["severity"] == "blocker"
    assert finding["status"] == "open"
    assert finding["message"] == "dir missing"
    assert finding["recommendation"] is None
    assert finding["related_ids"] == []
    assert finding["file"] == "generated_kicad"
    assert finding["evidence_ids"] == []
    assert finding["requires_human_review"] is False
    assert finding["metadata"] == {
        "origin": "KiCadGateIssue",
        "validator": "kicad_knowledge_gate_validator",
    }


def test_project_morphology_gate_issue_preserves_core_fields():
    issue = MorphologyGateIssue("MORPH.PLAN.001", "warning", "missing id", "artifacts/morphology_plan.json")
    finding = project_morphology_gate_issue(issue)
    assert finding["id"] is None
    assert finding["code"] == "MORPH.PLAN.001"
    assert finding["source"] == "morphology_gate"
    assert finding["category"] == "engineering"
    assert finding["severity"] == "warning"
    assert finding["status"] == "open"
    assert finding["message"] == "missing id"
    assert finding["recommendation"] is None
    assert finding["related_ids"] == []
    assert finding["file"] == "artifacts/morphology_plan.json"
    assert finding["evidence_ids"] == []
    assert finding["requires_human_review"] is False
    assert finding["metadata"] == {
        "origin": "MorphologyGateIssue",
        "validator": "morphology_gate_validator",
    }


def test_dataclass_and_dict_inputs_produce_identical_projection():
    from dataclasses import asdict

    kissue = KiCadGateIssue("KICAD.BOM.002", "warning", "BOM empty", "bom.csv")
    assert project_kicad_gate_issue(kissue) == project_kicad_gate_issue(asdict(kissue))

    missue = MorphologyGateIssue("MORPH.PLAN.002", "warning", "no family", "artifacts/morphology_plan.json")
    assert project_morphology_gate_issue(missue) == project_morphology_gate_issue(asdict(missue))


def test_report_projection_preserves_issue_order():
    from pathlib import Path
    kreport = kicad_build_report(Path("/tmp/kicad"), [
        KiCadGateIssue("R.1", "blocker", "a"),
        KiCadGateIssue("R.2", "warning", "b"),
        KiCadGateIssue("R.3", "info", "c"),
    ])
    codes = [f["code"] for f in project_kicad_gate_findings(kreport)]
    assert codes == ["R.1", "R.2", "R.3"]

    mreport = morph_build_report(Path("/tmp/export"), {}, [
        MorphologyGateIssue("M.1", "blocker", "a"),
        MorphologyGateIssue("M.2", "info", "b"),
    ])
    mcodes = [f["code"] for f in project_morphology_gate_findings(mreport)]
    assert mcodes == ["M.1", "M.2"]


def test_passed_report_with_no_issues_projects_to_empty(tmp_path):
    from pathlib import Path
    # build_report with an empty issue list -> status "passed", no issues.
    kreport = kicad_build_report(Path("/tmp/kicad"), [])
    assert kreport["status"] == "passed"
    assert project_kicad_gate_findings(kreport) == []

    mreport = morph_build_report(Path("/tmp/export"), {}, [])
    assert mreport["status"] == "passed"
    assert project_morphology_gate_findings(mreport) == []

    # A report dict that omits "issues" entirely also projects to [].
    assert project_kicad_gate_findings({"validator": "x"}) == []
    assert project_morphology_gate_findings({"validator": "x"}) == []


def test_projection_does_not_mutate_source_issue_dict():
    source = {"rule_id": "R.1", "severity": "Blocker", "message": "m", "file": "f"}
    snapshot = dict(source)
    project_kicad_gate_issue(source)
    project_morphology_gate_issue(source)
    assert source == snapshot


def test_projection_does_not_share_mutable_list_references():
    issue = KiCadGateIssue("R.1", "warning", "m", "f")
    f1 = project_kicad_gate_issue(issue)
    f2 = project_kicad_gate_issue(issue)
    # Distinct list objects per projection — mutating one is isolated.
    assert f1["related_ids"] is not f2["related_ids"]
    assert f1["evidence_ids"] is not f2["evidence_ids"]
    f1["related_ids"].append("x")
    f1["evidence_ids"].append("y")
    assert f2["related_ids"] == []
    assert f2["evidence_ids"] == []


def test_severity_normalization_known_lowercase():
    for sev in ("info", "warning", "error", "blocker"):
        finding = project_kicad_gate_issue({"rule_id": "R", "severity": sev, "message": "m", "file": None})
        assert finding["severity"] == sev


def test_severity_normalization_uppercase_is_lowercased():
    finding = project_kicad_gate_issue({"rule_id": "R", "severity": "BLOCKER", "message": "m", "file": None})
    assert finding["severity"] == "blocker"


def test_severity_normalization_empty_becomes_warning():
    finding = project_morphology_gate_issue({"rule_id": "R", "severity": "", "message": "m", "file": None})
    assert finding["severity"] == "warning"


def test_severity_normalization_non_string_becomes_warning():
    finding = project_morphology_gate_issue({"rule_id": "R", "severity": None, "message": "m", "file": None})
    assert finding["severity"] == "warning"


def test_severity_normalization_unknown_string_preserved_lowercased():
    finding = project_kicad_gate_issue({"rule_id": "R", "severity": "Critical", "message": "m", "file": None})
    assert finding["severity"] == "critical"


def test_validators_still_export_no_findings_projection(tmp_path):
    kreport = validate_kicad_package(tmp_path / "nope_kicad")
    mreport = validate_morphology_export(tmp_path / "nope_export")
    assert "findings_projection" not in kreport
    assert "findings_projection" not in mreport
