"""Phase 11 Stage 3: internal sandbox finding projection tests.

Characterizes how raw omni.sandbox.report.v1 checks project into the Phase 10
normalized finding item shape. Internal/test-facing only — no export, no
envelope, no schema string. Deterministic and filesystem-free.
"""

from backend.app.sandbox.finding_projection import (
    _normalize_severity,
    project_sandbox_check_result,
    project_sandbox_findings,
)
from backend.app.sandbox.report import SandboxCheckResult, SandboxReport
from backend.app.sandbox.runner import run_sandbox

# The canonical Phase 10 finding item key set (mission graph / engineering).
CANONICAL_ITEM_KEYS = {
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


def _failing_check():
    return SandboxCheckResult(
        check_id="units.mass_balance",
        ok=False,
        severity="warning",
        message="Declared total mass does not match summed component mass.",
        expected="2.4 kg",
        actual="2.0 kg",
        file=None,
        metadata={"delta_kg": 0.4, "tolerance_kg": 0.05},
    )


# ---------------------------------------------------------------------------
# 1. canonical key set
# ---------------------------------------------------------------------------
def test_project_check_result_exact_key_set():
    out = project_sandbox_check_result(_failing_check(), sandbox="units_math")
    assert set(out.keys()) == CANONICAL_ITEM_KEYS


def test_project_check_result_field_mapping():
    out = project_sandbox_check_result(_failing_check(), sandbox="units_math")
    assert out["id"] is None
    assert out["code"] == "units.mass_balance"
    assert out["source"] == "sandbox_units_math"
    assert out["category"] == "sandbox"
    assert out["severity"] == "warning"
    assert out["status"] == "open"
    assert out["recommendation"] is None
    assert out["related_ids"] == []
    assert out["evidence_ids"] == []
    assert out["requires_human_review"] is False
    # expected/actual live in metadata, not top-level.
    assert "expected" not in out
    assert "actual" not in out
    assert out["metadata"]["expected"] == "2.4 kg"
    assert out["metadata"]["actual"] == "2.0 kg"
    assert out["metadata"]["origin"] == "SandboxCheckResult"
    assert out["metadata"]["sandbox"] == "units_math"


def test_project_check_result_source_fallback_without_sandbox():
    out = project_sandbox_check_result(_failing_check())
    assert out["source"] == "sandbox"
    assert out["metadata"]["sandbox"] is None


# ---------------------------------------------------------------------------
# 2. failing characterization per real check
# ---------------------------------------------------------------------------
def test_project_units_math_failure():
    report = run_sandbox(
        "units_math",
        {"declared_total_mass_kg": 2.0, "component_masses_kg": [1.0, 1.4]},
    )
    findings = project_sandbox_findings(report)
    assert len(findings) == 1
    item = findings[0]
    assert item["code"] == "units.mass_balance"
    assert item["source"] == "sandbox_units_math"
    assert item["category"] == "sandbox"
    assert item["severity"] == "warning"
    assert item["status"] == "open"
    assert item["metadata"]["expected"] == "2.4 kg"
    assert item["metadata"]["actual"] == "2.0 kg"


def test_project_dimensional_consistency_failure():
    report = run_sandbox(
        "dimensional_consistency",
        {
            "quantity": {"name": "battery_mass", "dimension": "mass"},
            "expected_dimension": "length",
        },
    )
    findings = project_sandbox_findings(report)
    assert len(findings) == 1
    item = findings[0]
    assert item["code"] == "dimensional.consistency"
    assert item["source"] == "sandbox_dimensional_consistency"
    assert item["category"] == "sandbox"
    assert item["severity"] == "warning"
    assert item["status"] == "open"
    assert item["metadata"]["expected"] == "length"
    assert item["metadata"]["actual"] == "mass"


def test_project_equation_sanity_failure():
    report = run_sandbox(
        "equation_sanity",
        {"left": "V", "right": "I * R", "values": {"V": 10, "I": 3, "R": 4}},
    )
    findings = project_sandbox_findings(report)
    assert len(findings) == 1
    item = findings[0]
    assert item["code"] == "equation.sanity"
    assert item["source"] == "sandbox_equation_sanity"
    assert item["category"] == "sandbox"
    assert item["severity"] == "warning"
    assert item["status"] == "open"
    assert item["metadata"]["expected"] == "10"
    assert item["metadata"]["actual"] == "12"


def test_project_artifact_shape_failure():
    report = run_sandbox(
        "artifact_shape",
        {
            "artifact": {"name": "test_robot", "type": "robot"},
            "required_fields": {"name": "str", "type": "str", "mass_kg": "number"},
        },
    )
    findings = project_sandbox_findings(report)
    assert len(findings) == 1
    item = findings[0]
    assert item["code"] == "artifact_shape.field.mass_kg"
    assert item["source"] == "sandbox_artifact_shape"
    assert item["category"] == "sandbox"
    assert item["severity"] == "warning"
    assert item["status"] == "open"
    assert item["metadata"]["expected"] == "number"
    assert item["metadata"]["actual"] == "missing"


# ---------------------------------------------------------------------------
# 3-5. non-failing reports project to []
# ---------------------------------------------------------------------------
def test_passing_report_projects_to_empty():
    report = run_sandbox(
        "units_math",
        {"declared_total_mass_kg": 2.4, "component_masses_kg": [1.0, 1.4]},
    )
    assert report.status == "passed"
    assert project_sandbox_findings(report) == []


def test_skipped_report_projects_to_empty():
    report = run_sandbox("units_math", {})
    assert report.status == "skipped"
    assert project_sandbox_findings(report) == []


def test_unknown_report_projects_to_empty():
    report = run_sandbox("ros2_colcon", {"anything": 1})
    assert report.status == "skipped"
    assert project_sandbox_findings(report) == []


# ---------------------------------------------------------------------------
# 6. artifact_shape multi-problem fan-out preserves sorted order
# ---------------------------------------------------------------------------
def test_artifact_shape_multi_problem_fans_out_in_sorted_order():
    report = run_sandbox(
        "artifact_shape",
        {
            "artifact": {"name": 5},  # name wrong type, mass_kg + type missing
            "required_fields": {"name": "str", "type": "str", "mass_kg": "number"},
        },
    )
    findings = project_sandbox_findings(report)
    codes = [f["code"] for f in findings]
    assert codes == [
        "artifact_shape.field.mass_kg",
        "artifact_shape.field.name",
        "artifact_shape.field.type",
    ]
    assert all(f["source"] == "sandbox_artifact_shape" for f in findings)


# ---------------------------------------------------------------------------
# 6b. mixed report: only the failing check projects (no phantom findings)
# ---------------------------------------------------------------------------
def test_mixed_report_only_projects_the_failing_check():
    report = SandboxReport(
        sandbox="units_math",
        status="completed",
        checks=[
            SandboxCheckResult(
                check_id="check.passing",
                ok=True,
                severity="info",
                message="all good",
            ),
            SandboxCheckResult(
                check_id="check.failing",
                ok=False,
                severity="warning",
                message="something is off",
                expected="2.4 kg",
                actual="2.0 kg",
            ),
            SandboxCheckResult(
                check_id="check.skipped",
                ok=True,
                severity="info",
                message="skipped/info",
                metadata={"reason": "missing_or_invalid_input"},
            ),
        ],
    )
    before = report.to_dict()

    projected = project_sandbox_findings(report)

    # Exactly one finding: the failing check only.
    assert len(projected) == 1
    assert projected[0]["code"] == "check.failing"
    assert projected[0]["source"] == "sandbox_units_math"

    # No passing/skipped/info check leaked through.
    codes = [item["code"] for item in projected]
    assert "check.passing" not in codes
    assert "check.skipped" not in codes

    # Raw report stays untouched: no mutation, no findings keys injected.
    after = report.to_dict()
    assert after == before
    assert "findings" not in after
    assert "findings_projection" not in after


# ---------------------------------------------------------------------------
# 7. dict/dataclass parity
# ---------------------------------------------------------------------------
def test_check_result_dict_dataclass_parity():
    check = _failing_check()
    from_obj = project_sandbox_check_result(check, sandbox="units_math")
    from_dict = project_sandbox_check_result(check.to_dict(), sandbox="units_math")
    assert from_obj == from_dict


def test_findings_dict_dataclass_parity():
    report = run_sandbox(
        "artifact_shape",
        {
            "artifact": {"name": 5},
            "required_fields": {"name": "str", "type": "str", "mass_kg": "number"},
        },
    )
    from_obj = project_sandbox_findings(report)
    from_dict = project_sandbox_findings(report.to_dict())
    assert from_obj == from_dict


# ---------------------------------------------------------------------------
# 8. metadata preservation + no mutation of source
# ---------------------------------------------------------------------------
def test_check_metadata_preserved():
    check = _failing_check()
    out = project_sandbox_check_result(check, sandbox="units_math")
    assert out["metadata"]["check_metadata"] == {"delta_kg": 0.4, "tolerance_kg": 0.05}


def test_mutating_projection_does_not_mutate_source_check():
    check = _failing_check()
    out = project_sandbox_check_result(check, sandbox="units_math")

    out["metadata"]["check_metadata"]["delta_kg"] = 999
    out["metadata"]["mutated"] = True
    out["related_ids"].append("x")
    out["evidence_ids"].append("y")

    assert check.metadata == {"delta_kg": 0.4, "tolerance_kg": 0.05}


def test_mutating_findings_does_not_mutate_source_report():
    report = run_sandbox(
        "units_math",
        {"declared_total_mass_kg": 2.0, "component_masses_kg": [1.0, 1.4]},
    )
    original_meta = dict(report.checks[0].metadata)

    findings = project_sandbox_findings(report)
    findings[0]["metadata"]["check_metadata"]["delta_kg"] = 999

    assert report.checks[0].metadata == original_meta


def test_related_ids_and_evidence_ids_are_fresh_lists():
    a = project_sandbox_check_result(_failing_check(), sandbox="units_math")
    b = project_sandbox_check_result(_failing_check(), sandbox="units_math")
    a["related_ids"].append("x")
    a["evidence_ids"].append("y")
    assert b["related_ids"] == []
    assert b["evidence_ids"] == []


# ---------------------------------------------------------------------------
# 9. severity normalization
# ---------------------------------------------------------------------------
def test_severity_uppercase_lowercased():
    assert _normalize_severity("WARNING") == "warning"


def test_severity_empty_becomes_warning():
    assert _normalize_severity("") == "warning"
    assert _normalize_severity("   ") == "warning"


def test_severity_non_string_becomes_warning():
    assert _normalize_severity(None) == "warning"
    assert _normalize_severity(7) == "warning"


def test_severity_unknown_non_empty_preserved_lowercased():
    assert _normalize_severity("Critical") == "critical"


def test_projection_normalizes_severity():
    check = SandboxCheckResult(
        check_id="x", ok=False, severity="BLOCKER", message="m"
    )
    out = project_sandbox_check_result(check, sandbox="units_math")
    assert out["severity"] == "blocker"


# ---------------------------------------------------------------------------
# 10. raw report stays untouched
# ---------------------------------------------------------------------------
def test_projection_does_not_add_findings_keys_or_mutate_report():
    report = run_sandbox(
        "units_math",
        {"declared_total_mass_kg": 2.0, "component_masses_kg": [1.0, 1.4]},
    )
    before = report.to_dict()

    project_sandbox_findings(report)

    after = report.to_dict()
    assert after == before
    assert "findings" not in after
    assert "findings_projection" not in after
    for check in after["checks"]:
        assert "findings" not in check
        assert "findings_projection" not in check


# ---------------------------------------------------------------------------
# 11. unsupported input types raise TypeError
# ---------------------------------------------------------------------------
def test_unsupported_check_type_raises():
    import pytest

    with pytest.raises(TypeError):
        project_sandbox_check_result("not a check", sandbox="units_math")


def test_unsupported_report_type_raises():
    import pytest

    with pytest.raises(TypeError):
        project_sandbox_findings("not a report")
