"""Phase 11 Stage 2: dimensional consistency sandbox check tests."""

from backend.app.sandbox.runner import run_sandbox

_MATCH = {
    "quantity": {
        "name": "wing_span",
        "value": 1.2,
        "unit": "m",
        "dimension": "length",
    },
    "expected_dimension": "length",
}

_MISMATCH = {
    "quantity": {
        "name": "battery_mass",
        "value": 2.0,
        "unit": "kg",
        "dimension": "mass",
    },
    "expected_dimension": "length",
}


def test_passing_case():
    out = run_sandbox("dimensional_consistency", _MATCH).to_dict()
    assert out["sandbox"] == "dimensional_consistency"
    assert out["status"] == "passed"
    assert len(out["checks"]) == 1
    check = out["checks"][0]
    assert check["ok"] is True
    assert check["check_id"] == "dimensional.consistency"


def test_mismatch_case_includes_expected_and_actual_dimension():
    out = run_sandbox("dimensional_consistency", _MISMATCH).to_dict()
    assert out["status"] == "completed"
    assert len(out["checks"]) == 1
    check = out["checks"][0]
    assert check["ok"] is False
    assert check["severity"] == "warning"
    assert check["expected"] == "length"
    assert check["actual"] == "mass"
    assert check["metadata"]["expected_dimension"] == "length"
    assert check["metadata"]["actual_dimension"] == "mass"


def test_case_insensitive_dimension_match():
    out = run_sandbox(
        "dimensional_consistency",
        {
            "quantity": {"name": "x", "dimension": "Length"},
            "expected_dimension": "LENGTH",
        },
    ).to_dict()
    assert out["status"] == "passed"


def test_missing_quantity_skips():
    out = run_sandbox("dimensional_consistency", {"expected_dimension": "length"}).to_dict()
    assert out["status"] == "skipped"
    assert out["checks"][0]["severity"] == "info"


def test_missing_dimension_skips():
    out = run_sandbox(
        "dimensional_consistency",
        {"quantity": {"name": "x"}, "expected_dimension": "length"},
    ).to_dict()
    assert out["status"] == "skipped"


def test_none_input_skips():
    out = run_sandbox("dimensional_consistency", None).to_dict()
    assert out["status"] == "skipped"


def test_deterministic():
    first = run_sandbox("dimensional_consistency", _MISMATCH).to_dict()
    second = run_sandbox("dimensional_consistency", _MISMATCH).to_dict()
    assert first == second


def test_does_not_mutate_input():
    import copy

    original = copy.deepcopy(_MISMATCH)
    run_sandbox("dimensional_consistency", _MISMATCH)
    assert _MISMATCH == original


def test_no_findings_keys():
    out = run_sandbox("dimensional_consistency", _MISMATCH).to_dict()
    assert "findings" not in out
    assert "findings_projection" not in out
