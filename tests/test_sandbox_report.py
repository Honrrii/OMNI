"""Phase 11 Stage 1: raw sandbox report shape tests.

Pins the SandboxCheckResult / SandboxReport key sets, asserts the raw report
carries no findings / findings_projection yet, and proves to_dict() returns
fresh mutable objects so callers cannot corrupt shared state.
"""

from backend.app.sandbox.report import SandboxCheckResult, SandboxReport


def _sample_check():
    return SandboxCheckResult(
        check_id="units.mass_balance",
        ok=False,
        severity="warning",
        message="mismatch",
        expected="2.4 kg",
        actual="2.0 kg",
        file="exports/mission/units.json",
        metadata={"delta_kg": 0.4},
    )


def test_check_result_to_dict_exact_key_set():
    out = _sample_check().to_dict()
    assert set(out.keys()) == {
        "check_id",
        "ok",
        "severity",
        "message",
        "expected",
        "actual",
        "file",
        "metadata",
    }


def test_check_result_to_dict_values():
    out = _sample_check().to_dict()
    assert out["check_id"] == "units.mass_balance"
    assert out["ok"] is False
    assert out["severity"] == "warning"
    assert out["expected"] == "2.4 kg"
    assert out["actual"] == "2.0 kg"
    assert out["file"] == "exports/mission/units.json"
    assert out["metadata"] == {"delta_kg": 0.4}


def test_check_result_defaults_are_none_and_empty_metadata():
    minimal = SandboxCheckResult(
        check_id="x", ok=True, severity="info", message="ok"
    )
    out = minimal.to_dict()
    assert out["expected"] is None
    assert out["actual"] is None
    assert out["file"] is None
    assert out["metadata"] == {}


def test_check_result_metadata_default_is_not_shared():
    a = SandboxCheckResult(check_id="a", ok=True, severity="info", message="a")
    b = SandboxCheckResult(check_id="b", ok=True, severity="info", message="b")
    a.metadata["k"] = 1
    # Distinct default-factory dicts: mutating one must not touch the other.
    assert b.metadata == {}


def test_report_to_dict_exact_key_set():
    report = SandboxReport(sandbox="units_math", status="passed", checks=[])
    out = report.to_dict()
    assert set(out.keys()) == {"schema", "sandbox", "status", "checks", "metadata"}


def test_report_schema_default():
    report = SandboxReport(sandbox="units_math", status="passed", checks=[])
    assert report.to_dict()["schema"] == "omni.sandbox.report.v1"


def test_report_has_no_findings_keys():
    report = SandboxReport(
        sandbox="units_math", status="completed", checks=[_sample_check()]
    )
    out = report.to_dict()
    assert "findings" not in out
    assert "findings_projection" not in out
    # And not nested inside a check either.
    for check in out["checks"]:
        assert "findings" not in check
        assert "findings_projection" not in check


def test_report_to_dict_creates_fresh_objects():
    check = _sample_check()
    report = SandboxReport(
        sandbox="units_math",
        status="completed",
        checks=[check],
        metadata={"run": 1},
    )

    first = report.to_dict()
    second = report.to_dict()

    # Equal in value...
    assert first == second
    # ...but independent objects: mutating one snapshot must not affect another
    # or the report's own internal state.
    first["checks"].append({"injected": True})
    first["metadata"]["mutated"] = True
    first["checks"][0]["metadata"]["mutated"] = True

    assert len(second["checks"]) == 1
    assert "mutated" not in second["metadata"]
    assert "mutated" not in second["checks"][0]["metadata"]
    assert report.metadata == {"run": 1}
    assert check.metadata == {"delta_kg": 0.4}


def test_report_preserves_check_order():
    checks = [
        SandboxCheckResult(check_id=f"c{i}", ok=True, severity="info", message=str(i))
        for i in range(5)
    ]
    out = SandboxReport(sandbox="units_math", status="passed", checks=checks).to_dict()
    assert [c["check_id"] for c in out["checks"]] == ["c0", "c1", "c2", "c3", "c4"]
