"""Phase 11 Stage 6: CommandResult -> SandboxReport bridge tests.

Pure transform: maps a low-level CommandResult into a one-check SandboxReport
and proves it flows through the existing sandbox finding projection and export
envelope. Deterministic; only one harmless command is ever run.
"""

import ast
import sys
from pathlib import Path

import pytest

from backend.app.sandbox.command_report import command_result_to_sandbox_report
from backend.app.sandbox.execution import CommandResult, run_command
from backend.app.sandbox.export_projection import build_sandbox_findings_projection
from backend.app.sandbox.finding_projection import project_sandbox_findings

COMMAND_REPORT_FILE = (
    Path(__file__).resolve().parent.parent
    / "backend"
    / "app"
    / "sandbox"
    / "command_report.py"
)


def _success_result():
    return CommandResult(
        command=[sys.executable, "-c", "print('ok')"],
        returncode=0,
        stdout="ok\n",
        stderr="",
        timed_out=False,
        timeout_seconds=10.0,
    )


def _failure_result():
    return CommandResult(
        command=[sys.executable, "-c", "import sys; sys.exit(3)"],
        returncode=3,
        stdout="",
        stderr="boom\n",
        timed_out=False,
        timeout_seconds=10.0,
    )


def _timeout_result():
    return CommandResult(
        command=[sys.executable, "-c", "import time; time.sleep(5)"],
        returncode=None,
        stdout="",
        stderr="",
        timed_out=True,
        timeout_seconds=0.5,
    )


# ---------------------------------------------------------------------------
# 1-3. outcome mappings
# ---------------------------------------------------------------------------
def test_success_mapping():
    report = command_result_to_sandbox_report(_success_result())
    assert report.sandbox == "command"
    assert report.status == "passed"
    assert len(report.checks) == 1
    check = report.checks[0]
    assert check.check_id == "command.exit"
    assert check.ok is True
    assert check.severity == "info"
    assert check.message == "command completed successfully"
    assert check.expected == "0"
    assert check.actual == "0"
    assert check.file is None


def test_nonzero_exit_mapping():
    report = command_result_to_sandbox_report(_failure_result())
    assert report.status == "completed"
    check = report.checks[0]
    assert check.ok is False
    assert check.severity == "warning"
    assert check.message == "command exited with nonzero status"
    assert check.expected == "0"
    assert check.actual == "3"


def test_timeout_mapping():
    report = command_result_to_sandbox_report(_timeout_result())
    assert report.status == "completed"
    check = report.checks[0]
    assert check.ok is False
    assert check.severity == "error"
    assert check.message == "command timed out"
    assert check.expected == "0"
    assert check.actual == "timeout"


# ---------------------------------------------------------------------------
# 4. metadata preservation
# ---------------------------------------------------------------------------
def test_metadata_preservation():
    result = _failure_result()
    meta = command_result_to_sandbox_report(result).checks[0].metadata
    assert meta["command"] == [sys.executable, "-c", "import sys; sys.exit(3)"]
    assert meta["returncode"] == 3
    assert meta["timed_out"] is False
    assert meta["timeout_seconds"] == 10.0
    assert meta["stdout"] == ""
    assert meta["stderr"] == "boom\n"
    assert meta["stdout_len"] == 0
    assert meta["stderr_len"] == len("boom\n")
    assert meta["stdout_truncated"] is False
    assert meta["stderr_truncated"] is False


def test_metadata_command_is_fresh_list():
    result = _success_result()
    report = command_result_to_sandbox_report(result)
    report.checks[0].metadata["command"].append("mutated")
    assert "mutated" not in result.command


# ---------------------------------------------------------------------------
# 5. dict/dataclass parity
# ---------------------------------------------------------------------------
def test_dict_dataclass_parity():
    result = _failure_result()
    from_obj = command_result_to_sandbox_report(result).to_dict()
    from_dict = command_result_to_sandbox_report(result.to_dict()).to_dict()
    assert from_obj == from_dict


def test_unsupported_input_raises():
    with pytest.raises(TypeError):
        command_result_to_sandbox_report("not a result")


# ---------------------------------------------------------------------------
# 6. custom sandbox name -> source
# ---------------------------------------------------------------------------
def test_custom_sandbox_name_projects_to_source():
    report = command_result_to_sandbox_report(_failure_result(), sandbox="ros2_build")
    findings = project_sandbox_findings(report)
    assert len(findings) == 1
    assert findings[0]["source"] == "sandbox_ros2_build"


# ---------------------------------------------------------------------------
# 7-11. end-to-end projection + envelope
# ---------------------------------------------------------------------------
def test_success_projects_to_empty_findings_and_envelope():
    report = command_result_to_sandbox_report(_success_result())
    assert project_sandbox_findings(report) == []
    env = build_sandbox_findings_projection(report)
    assert env["count"] == 0
    assert env["items"] == []
    assert env["source"] == "sandbox_command"


def test_failure_projects_to_one_warning_finding():
    report = command_result_to_sandbox_report(_failure_result())
    findings = project_sandbox_findings(report)
    assert len(findings) == 1
    item = findings[0]
    assert item["code"] == "command.exit"
    assert item["source"] == "sandbox_command"
    assert item["category"] == "sandbox"
    assert item["status"] == "open"
    assert item["severity"] == "warning"
    assert item["metadata"]["check_metadata"]["returncode"] == 3

    env = build_sandbox_findings_projection(report)
    assert env["count"] == 1
    assert env["items"] == findings


def test_timeout_projects_to_one_error_finding():
    report = command_result_to_sandbox_report(_timeout_result())
    findings = project_sandbox_findings(report)
    assert len(findings) == 1
    assert findings[0]["severity"] == "error"
    assert findings[0]["metadata"]["check_metadata"]["timed_out"] is True
    assert build_sandbox_findings_projection(report)["count"] == 1


# ---------------------------------------------------------------------------
# 12-14. determinism / no mutation / no findings keys on raw report
# ---------------------------------------------------------------------------
def test_deterministic_report_dict():
    result = _failure_result()
    first = command_result_to_sandbox_report(result).to_dict()
    second = command_result_to_sandbox_report(result).to_dict()
    assert first == second


def test_no_input_mutation_dict():
    result = _failure_result()
    snapshot = result.to_dict()
    command_result_to_sandbox_report(result)
    assert result.to_dict() == snapshot


def test_raw_report_has_no_findings_keys():
    report = command_result_to_sandbox_report(_failure_result())
    out = report.to_dict()
    assert "findings" not in out
    assert "findings_projection" not in out
    for check in out["checks"]:
        assert "findings" not in check
        assert "findings_projection" not in check


# ---------------------------------------------------------------------------
# 15-16. truncation
# ---------------------------------------------------------------------------
def test_truncation_applies_with_limit():
    result = CommandResult(
        command=["x"],
        returncode=1,
        stdout="abcdefghij",  # 10 chars
        stderr="0123456789",  # 10 chars
        timed_out=False,
        timeout_seconds=5.0,
    )
    meta = command_result_to_sandbox_report(result, max_output_chars=4).checks[0].metadata
    assert meta["stdout"] == "abcd…[truncated 6 chars]"
    assert meta["stderr"] == "0123…[truncated 6 chars]"
    assert meta["stdout_truncated"] is True
    assert meta["stderr_truncated"] is True
    # Original lengths preserved.
    assert meta["stdout_len"] == 10
    assert meta["stderr_len"] == 10


def test_truncation_no_op_when_under_limit():
    result = CommandResult(
        command=["x"], returncode=0, stdout="hi", stderr="", timed_out=False,
        timeout_seconds=5.0,
    )
    meta = command_result_to_sandbox_report(result, max_output_chars=100).checks[0].metadata
    assert meta["stdout"] == "hi"
    assert meta["stdout_truncated"] is False


def test_default_no_truncation():
    big = "x" * 5000
    result = CommandResult(
        command=["x"], returncode=0, stdout=big, stderr="", timed_out=False,
        timeout_seconds=5.0,
    )
    meta = command_result_to_sandbox_report(result).checks[0].metadata
    assert meta["stdout"] == big
    assert meta["stdout_truncated"] is False
    assert meta["stdout_len"] == 5000


def test_negative_max_output_chars_rejected():
    with pytest.raises(ValueError):
        command_result_to_sandbox_report(_success_result(), max_output_chars=-1)


# ---------------------------------------------------------------------------
# 17. one harmless real run_command smoke
# ---------------------------------------------------------------------------
def test_real_run_command_smoke(tmp_path):
    result = run_command(
        [sys.executable, "-c", "print('ok')"], cwd=tmp_path, timeout=10
    )
    report = command_result_to_sandbox_report(result)
    assert report.status == "passed"
    assert report.checks[0].ok is True
    assert project_sandbox_findings(report) == []


# ---------------------------------------------------------------------------
# 18. command_report.py must not import or call subprocess
# ---------------------------------------------------------------------------
def test_command_report_does_not_import_or_call_subprocess():
    tree = ast.parse(COMMAND_REPORT_FILE.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert alias.name.split(".")[0] != "subprocess"
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                assert node.module.split(".")[0] != "subprocess"
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            value = node.func.value
            if isinstance(value, ast.Name):
                assert value.id != "subprocess"
