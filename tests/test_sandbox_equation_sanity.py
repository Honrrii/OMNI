"""Phase 11 Stage 2: equation sanity sandbox check tests."""

from backend.app.sandbox.runner import run_sandbox

_OHMS_OK = {
    "equation_id": "ohms_law",
    "left": "V",
    "right": "I * R",
    "values": {"V": 12, "I": 3, "R": 4},
    "tolerance": 0.000001,
}

_OHMS_BAD = {
    "equation_id": "ohms_law",
    "left": "V",
    "right": "I * R",
    "values": {"V": 10, "I": 3, "R": 4},
    "tolerance": 0.000001,
}


def test_passing_case():
    out = run_sandbox("equation_sanity", _OHMS_OK).to_dict()
    assert out["sandbox"] == "equation_sanity"
    assert out["status"] == "passed"
    assert len(out["checks"]) == 1
    check = out["checks"][0]
    assert check["ok"] is True
    assert check["check_id"] == "equation.sanity"


def test_mismatch_includes_expected_and_evaluated_sides():
    out = run_sandbox("equation_sanity", _OHMS_BAD).to_dict()
    assert out["status"] == "completed"
    check = out["checks"][0]
    assert check["ok"] is False
    assert check["severity"] == "warning"
    # left = V = 10, right = I*R = 12
    assert check["expected"] == "10"
    assert check["actual"] == "12"
    assert check["metadata"]["left_value"] == 10
    assert check["metadata"]["right_value"] == 12
    assert check["metadata"]["delta"] == 2


def test_supports_pow_and_parentheses():
    out = run_sandbox(
        "equation_sanity",
        {
            "equation_id": "area",
            "left": "A",
            "right": "(s ** 2)",
            "values": {"A": 9, "s": 3},
        },
    ).to_dict()
    assert out["status"] == "passed"


def test_unsafe_expression_skips():
    # Function calls are not part of the permitted grammar.
    out = run_sandbox(
        "equation_sanity",
        {
            "left": "V",
            "right": "__import__('os').getcwd()",
            "values": {"V": 1},
        },
    ).to_dict()
    assert out["status"] == "skipped"
    assert out["checks"][0]["severity"] == "info"


def test_unknown_variable_skips():
    out = run_sandbox(
        "equation_sanity",
        {"left": "V", "right": "I * R", "values": {"V": 12, "I": 3}},
    ).to_dict()
    assert out["status"] == "skipped"


def test_division_by_zero_skips():
    out = run_sandbox(
        "equation_sanity",
        {"left": "V", "right": "I / R", "values": {"V": 1, "I": 1, "R": 0}},
    ).to_dict()
    assert out["status"] == "skipped"


def test_missing_values_skips():
    out = run_sandbox(
        "equation_sanity", {"left": "V", "right": "I * R"}
    ).to_dict()
    assert out["status"] == "skipped"


def test_none_input_skips():
    out = run_sandbox("equation_sanity", None).to_dict()
    assert out["status"] == "skipped"


def test_deterministic():
    first = run_sandbox("equation_sanity", _OHMS_BAD).to_dict()
    second = run_sandbox("equation_sanity", _OHMS_BAD).to_dict()
    assert first == second


def test_does_not_mutate_input():
    import copy

    original = copy.deepcopy(_OHMS_BAD)
    run_sandbox("equation_sanity", _OHMS_BAD)
    assert _OHMS_BAD == original


def test_no_findings_keys():
    out = run_sandbox("equation_sanity", _OHMS_BAD).to_dict()
    assert "findings" not in out
    assert "findings_projection" not in out
