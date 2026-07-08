"""Phase 11 Stage 2: artifact shape sandbox check tests."""

from backend.app.sandbox.runner import run_sandbox

_REQUIRED = {"name": "str", "type": "str", "mass_kg": "number"}

_OK = {
    "artifact_name": "sandbox_candidate",
    "artifact": {"name": "test_robot", "type": "robot", "mass_kg": 2.4},
    "required_fields": _REQUIRED,
}


def test_passing_case():
    out = run_sandbox("artifact_shape", _OK).to_dict()
    assert out["sandbox"] == "artifact_shape"
    assert out["status"] == "passed"
    assert len(out["checks"]) == 1
    assert out["checks"][0]["ok"] is True
    assert out["checks"][0]["check_id"] == "artifact_shape.ok"


def test_missing_field_case():
    out = run_sandbox(
        "artifact_shape",
        {
            "artifact_name": "sandbox_candidate",
            "artifact": {"name": "test_robot", "type": "robot"},
            "required_fields": _REQUIRED,
        },
    ).to_dict()
    assert out["status"] == "completed"
    assert len(out["checks"]) == 1
    check = out["checks"][0]
    assert check["ok"] is False
    assert check["severity"] == "warning"
    assert check["metadata"]["problem"] == "missing_field"
    assert check["metadata"]["field"] == "mass_kg"
    assert check["actual"] == "missing"


def test_wrong_type_case():
    out = run_sandbox(
        "artifact_shape",
        {
            "artifact": {"name": "test_robot", "type": "robot", "mass_kg": "heavy"},
            "required_fields": _REQUIRED,
        },
    ).to_dict()
    assert out["status"] == "completed"
    check = out["checks"][0]
    assert check["ok"] is False
    assert check["metadata"]["problem"] == "wrong_type"
    assert check["metadata"]["field"] == "mass_kg"
    assert check["expected"] == "number"
    assert check["actual"] == "str"


def test_multiple_problems_sorted_by_field_name():
    out = run_sandbox(
        "artifact_shape",
        {
            "artifact": {"name": 5},  # name wrong type, mass_kg + type missing
            "required_fields": _REQUIRED,
        },
    ).to_dict()
    assert out["status"] == "completed"
    fields = [c["metadata"]["field"] for c in out["checks"]]
    # Deterministic ordering by sorted field name: mass_kg, name, type
    assert fields == ["mass_kg", "name", "type"]


def test_number_rejects_bool():
    out = run_sandbox(
        "artifact_shape",
        {
            "artifact": {"name": "r", "type": "robot", "mass_kg": True},
            "required_fields": _REQUIRED,
        },
    ).to_dict()
    assert out["status"] == "completed"
    assert out["checks"][0]["metadata"]["field"] == "mass_kg"
    assert out["checks"][0]["actual"] == "bool"


def test_missing_artifact_skips():
    out = run_sandbox(
        "artifact_shape", {"required_fields": _REQUIRED}
    ).to_dict()
    assert out["status"] == "skipped"
    assert out["checks"][0]["severity"] == "info"


def test_empty_required_fields_skips():
    out = run_sandbox(
        "artifact_shape", {"artifact": {"name": "x"}, "required_fields": {}}
    ).to_dict()
    assert out["status"] == "skipped"


def test_unknown_type_token_skips():
    out = run_sandbox(
        "artifact_shape",
        {"artifact": {"name": "x"}, "required_fields": {"name": "uuid"}},
    ).to_dict()
    assert out["status"] == "skipped"


def test_none_input_skips():
    out = run_sandbox("artifact_shape", None).to_dict()
    assert out["status"] == "skipped"


def test_deterministic():
    inputs = {
        "artifact": {"name": 5},
        "required_fields": _REQUIRED,
    }
    first = run_sandbox("artifact_shape", inputs).to_dict()
    second = run_sandbox("artifact_shape", inputs).to_dict()
    assert first == second


def test_does_not_mutate_input():
    import copy

    original = copy.deepcopy(_OK)
    run_sandbox("artifact_shape", _OK)
    assert _OK == original


def test_no_findings_keys():
    out = run_sandbox("artifact_shape", _OK).to_dict()
    assert "findings" not in out
    assert "findings_projection" not in out
