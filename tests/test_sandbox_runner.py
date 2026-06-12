"""Phase 11 Stage 1: sandbox runner + units/math check tests.

Covers the units/math check (pass / mismatch / skip), runner determinism, the
unknown-sandbox skip path, and two foundation-safety guards: the sandbox package
imports no heavy/runtime modules and contains no subprocess/shell execution.
"""

import ast
from pathlib import Path

from backend.app.sandbox.runner import run_sandbox

SANDBOX_DIR = Path(__file__).resolve().parent.parent / "backend" / "app" / "sandbox"


# ---------------------------------------------------------------------------
# units/math check behavior
# ---------------------------------------------------------------------------
def test_units_math_passing_case():
    out = run_sandbox(
        "units_math",
        {
            "declared_total_mass_kg": 2.4,
            "component_masses_kg": [1.0, 1.4],
            "tolerance_kg": 0.05,
        },
    ).to_dict()

    assert out["sandbox"] == "units_math"
    assert out["status"] == "passed"
    assert len(out["checks"]) == 1
    check = out["checks"][0]
    assert check["check_id"] == "units.mass_balance"
    assert check["ok"] is True
    assert check["severity"] == "info"


def test_units_math_mismatch_case():
    out = run_sandbox(
        "units_math",
        {
            "declared_total_mass_kg": 2.0,
            "component_masses_kg": [1.0, 1.4],
            "tolerance_kg": 0.05,
        },
    ).to_dict()

    assert out["status"] == "completed"
    assert len(out["checks"]) == 1
    check = out["checks"][0]
    assert check["check_id"] == "units.mass_balance"
    assert check["ok"] is False
    assert check["severity"] == "warning"
    assert check["expected"] == "2.4 kg"
    assert check["actual"] == "2.0 kg"


def test_units_math_within_default_tolerance_passes():
    # No tolerance_kg supplied -> default 0.05; 2.43 vs 2.4 is within it.
    out = run_sandbox(
        "units_math",
        {
            "declared_total_mass_kg": 2.43,
            "component_masses_kg": [1.0, 1.4],
        },
    ).to_dict()
    assert out["status"] == "passed"
    assert out["checks"][0]["ok"] is True


def test_units_math_missing_input_skips():
    out = run_sandbox("units_math", {}).to_dict()
    assert out["status"] == "skipped"
    assert len(out["checks"]) == 1
    assert out["checks"][0]["severity"] == "info"
    assert out["checks"][0]["ok"] is True


def test_units_math_none_input_skips():
    out = run_sandbox("units_math", None).to_dict()
    assert out["status"] == "skipped"
    assert out["checks"][0]["severity"] == "info"


def test_units_math_invalid_component_skips():
    out = run_sandbox(
        "units_math",
        {
            "declared_total_mass_kg": 2.0,
            "component_masses_kg": [1.0, "heavy"],
        },
    ).to_dict()
    assert out["status"] == "skipped"
    assert out["checks"][0]["severity"] == "info"


def test_units_math_bool_declared_is_invalid_and_skips():
    # bools are not accepted as masses even though they are int subclasses.
    out = run_sandbox(
        "units_math",
        {
            "declared_total_mass_kg": True,
            "component_masses_kg": [1.0, 1.4],
        },
    ).to_dict()
    assert out["status"] == "skipped"


# ---------------------------------------------------------------------------
# determinism
# ---------------------------------------------------------------------------
def test_run_sandbox_units_math_is_deterministic():
    inputs = {
        "declared_total_mass_kg": 2.0,
        "component_masses_kg": [1.0, 1.4],
        "tolerance_kg": 0.05,
    }
    first = run_sandbox("units_math", inputs).to_dict()
    second = run_sandbox("units_math", inputs).to_dict()
    assert first == second


def test_run_sandbox_does_not_mutate_inputs():
    inputs = {
        "declared_total_mass_kg": 2.0,
        "component_masses_kg": [1.0, 1.4],
        "tolerance_kg": 0.05,
    }
    snapshot = {
        "declared_total_mass_kg": 2.0,
        "component_masses_kg": [1.0, 1.4],
        "tolerance_kg": 0.05,
    }
    run_sandbox("units_math", inputs)
    assert inputs == snapshot


# ---------------------------------------------------------------------------
# unknown sandbox
# ---------------------------------------------------------------------------
def test_run_sandbox_unknown_name_skips():
    out = run_sandbox("ros2_colcon", {"anything": 1}).to_dict()
    assert out["sandbox"] == "ros2_colcon"
    assert out["status"] == "skipped"
    assert len(out["checks"]) == 1
    check = out["checks"][0]
    assert check["check_id"] == "sandbox.unknown"
    assert check["ok"] is True
    assert check["severity"] == "info"


def test_run_sandbox_unknown_name_is_deterministic():
    first = run_sandbox("nope", None).to_dict()
    second = run_sandbox("nope", None).to_dict()
    assert first == second


def test_no_report_contains_findings_keys():
    for name, inputs in (
        ("units_math", {"declared_total_mass_kg": 2.0, "component_masses_kg": [1.0, 1.4]}),
        ("units_math", {}),
        ("dimensional_consistency", {"quantity": {"dimension": "mass"}, "expected_dimension": "length"}),
        ("equation_sanity", {"left": "V", "right": "I * R", "values": {"V": 1, "I": 1, "R": 1}}),
        ("artifact_shape", {"artifact": {"name": "x"}, "required_fields": {"name": "str"}}),
        ("unknown_box", None),
    ):
        out = run_sandbox(name, inputs).to_dict()
        assert "findings" not in out
        assert "findings_projection" not in out


# ---------------------------------------------------------------------------
# Stage 2: runner dispatches each registered check by name
# ---------------------------------------------------------------------------
def test_runner_dispatches_dimensional_consistency():
    out = run_sandbox(
        "dimensional_consistency",
        {"quantity": {"name": "x", "dimension": "length"}, "expected_dimension": "length"},
    ).to_dict()
    assert out["sandbox"] == "dimensional_consistency"
    assert out["status"] == "passed"


def test_runner_dispatches_equation_sanity():
    out = run_sandbox(
        "equation_sanity",
        {"left": "V", "right": "I * R", "values": {"V": 12, "I": 3, "R": 4}},
    ).to_dict()
    assert out["sandbox"] == "equation_sanity"
    assert out["status"] == "passed"


def test_runner_dispatches_artifact_shape():
    out = run_sandbox(
        "artifact_shape",
        {
            "artifact": {"name": "r", "type": "robot", "mass_kg": 2.4},
            "required_fields": {"name": "str", "type": "str", "mass_kg": "number"},
        },
    ).to_dict()
    assert out["sandbox"] == "artifact_shape"
    assert out["status"] == "passed"


# ---------------------------------------------------------------------------
# foundation-safety guards (AST, no execution)
# ---------------------------------------------------------------------------
FORBIDDEN_IMPORTS = (
    "backend.app.main",
    "agents.supervisor",
    "agents.validator_agent",
    "agents.critic_agent",
    "agents.artifact_synthesizer",
    "backend.app.reliability",
    "backend.app.export.export_manager",
)

FORBIDDEN_CALL_ATTRS = {
    ("os", "system"),
    ("os", "popen"),
    ("subprocess", "run"),
    ("subprocess", "Popen"),
    ("subprocess", "call"),
    ("subprocess", "check_call"),
    ("subprocess", "check_output"),
}

FORBIDDEN_IMPORT_MODULES = {"subprocess"}


def _sandbox_py_files():
    return sorted(SANDBOX_DIR.rglob("*.py"))


def _imported_names(tree):
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield alias.name
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                yield node.module


def test_sandbox_does_not_import_forbidden_modules():
    offenders = []
    for path in _sandbox_py_files():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for name in _imported_names(tree):
            for forbidden in FORBIDDEN_IMPORTS:
                if name == forbidden or name.startswith(forbidden + "."):
                    offenders.append(f"{path.name}: imports {name}")
    assert not offenders, "sandbox imports forbidden modules:\n" + "\n".join(offenders)


def test_sandbox_has_no_subprocess_or_shell_execution():
    offenders = []
    for path in _sandbox_py_files():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for name in _imported_names(tree):
            top = name.split(".")[0]
            if top in FORBIDDEN_IMPORT_MODULES:
                offenders.append(f"{path.name}: imports {name}")
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                value = node.func.value
                if isinstance(value, ast.Name):
                    if (value.id, node.func.attr) in FORBIDDEN_CALL_ATTRS:
                        offenders.append(
                            f"{path.name}: calls {value.id}.{node.func.attr}()"
                        )
    assert not offenders, (
        "sandbox uses subprocess/shell execution:\n" + "\n".join(offenders)
    )
