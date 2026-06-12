"""Phase 11 Stage 7: harmless command pipeline orchestrator tests.

Proves one explicit argv command flows through the full sandbox chain
(run_command -> report -> findings -> envelope). Only harmless
sys.executable -c … commands are run. Deterministic; no real tools.
"""

import ast
import sys
from pathlib import Path

import pytest

from backend.app.sandbox.command_pipeline import (
    CommandPipelineResult,
    run_command_pipeline,
)

PIPELINE_FILE = (
    Path(__file__).resolve().parent.parent
    / "backend"
    / "app"
    / "sandbox"
    / "command_pipeline.py"
)


# ---------------------------------------------------------------------------
# 1-3. success / nonzero / timeout end-to-end
# ---------------------------------------------------------------------------
def test_success_end_to_end(tmp_path):
    result = run_command_pipeline(
        [sys.executable, "-c", "print('ok')"], cwd=tmp_path, timeout=10
    )
    assert result.command_result.returncode == 0
    assert "ok" in result.command_result.stdout
    assert result.report.status == "passed"
    assert result.findings == []
    assert result.findings_projection["count"] == 0


def test_nonzero_end_to_end(tmp_path):
    result = run_command_pipeline(
        [sys.executable, "-c", "import sys; sys.exit(3)"], cwd=tmp_path, timeout=10
    )
    assert result.report.status == "completed"
    assert len(result.findings) == 1
    assert result.findings[0]["severity"] == "warning"
    assert result.findings_projection["count"] == 1


def test_timeout_end_to_end(tmp_path):
    result = run_command_pipeline(
        [sys.executable, "-c", "import time; time.sleep(5)"],
        cwd=tmp_path,
        timeout=0.5,
    )
    assert result.report.status == "completed"
    assert len(result.findings) == 1
    assert result.findings[0]["severity"] == "error"
    assert result.findings_projection["count"] == 1


# ---------------------------------------------------------------------------
# 4. bundle completeness
# ---------------------------------------------------------------------------
def test_bundle_completeness(tmp_path):
    result = run_command_pipeline(
        [sys.executable, "-c", "import sys; sys.exit(1)"], cwd=tmp_path, timeout=10
    )
    out = result.to_dict()
    assert set(out.keys()) == {
        "schema",
        "command_result",
        "sandbox_report",
        "findings",
        "findings_projection",
    }
    assert out["schema"] == "omni.sandbox.command_pipeline.v1"
    # Component sections match the live objects' own to_dict().
    assert out["command_result"] == result.command_result.to_dict()
    assert out["sandbox_report"] == result.report.to_dict()
    assert out["findings_projection"] == result.findings_projection


# ---------------------------------------------------------------------------
# 5. invariant: findings == envelope items, count == len
# ---------------------------------------------------------------------------
def test_findings_match_envelope_items(tmp_path):
    result = run_command_pipeline(
        [sys.executable, "-c", "import sys; sys.exit(2)"], cwd=tmp_path, timeout=10
    )
    assert result.findings == result.findings_projection["items"]
    assert result.findings_projection["count"] == len(result.findings)


# ---------------------------------------------------------------------------
# 6. pass-through of sandbox name + max_output_chars
# ---------------------------------------------------------------------------
def test_sandbox_name_passthrough(tmp_path):
    result = run_command_pipeline(
        [sys.executable, "-c", "import sys; sys.exit(3)"],
        cwd=tmp_path,
        timeout=10,
        sandbox="ros2_build",
    )
    assert result.findings[0]["source"] == "sandbox_ros2_build"


def test_max_output_chars_passthrough_truncates(tmp_path):
    # Emit 50 chars to stdout, then exit nonzero so a finding is produced.
    result = run_command_pipeline(
        [sys.executable, "-c", "print('x' * 50); import sys; sys.exit(1)"],
        cwd=tmp_path,
        timeout=10,
        max_output_chars=8,
    )
    meta = result.report.checks[0].metadata
    assert meta["stdout_truncated"] is True
    assert "[truncated" in meta["stdout"]
    # Original length preserved (50 x's plus the trailing newline).
    assert meta["stdout_len"] == 51


# ---------------------------------------------------------------------------
# 7. argv-only enforcement (delegated to run_command)
# ---------------------------------------------------------------------------
def test_string_command_rejected(tmp_path):
    with pytest.raises(TypeError):
        run_command_pipeline("echo hi", cwd=tmp_path, timeout=10)


# ---------------------------------------------------------------------------
# 8. determinism
# ---------------------------------------------------------------------------
def test_deterministic_to_dict(tmp_path):
    cmd = [sys.executable, "-c", "import sys; sys.exit(3)"]
    first = run_command_pipeline(cmd, cwd=tmp_path, timeout=10).to_dict()
    second = run_command_pipeline(cmd, cwd=tmp_path, timeout=10).to_dict()
    assert first == second


# ---------------------------------------------------------------------------
# 9. no mutation / fresh output
# ---------------------------------------------------------------------------
def test_to_dict_returns_fresh_findings_list(tmp_path):
    result = run_command_pipeline(
        [sys.executable, "-c", "import sys; sys.exit(3)"], cwd=tmp_path, timeout=10
    )
    out = result.to_dict()
    out["findings"].append({"injected": True})
    out["findings"][0]["mutated"] = True
    # Stored result is unaffected.
    assert len(result.findings) == 1
    assert "mutated" not in result.findings[0]


def test_mutating_envelope_copy_does_not_mutate_result(tmp_path):
    result = run_command_pipeline(
        [sys.executable, "-c", "import sys; sys.exit(3)"], cwd=tmp_path, timeout=10
    )
    out = result.to_dict()
    out["findings_projection"]["count"] = 999
    assert result.findings_projection["count"] == 1


# ---------------------------------------------------------------------------
# 10. no file writes outside tmp_path
# ---------------------------------------------------------------------------
def test_child_file_writes_stay_in_tmp_path(tmp_path):
    sentinel = "omni_stage7_sentinel.txt"
    result = run_command_pipeline(
        [sys.executable, "-c", "open('omni_stage7_sentinel.txt','w').write('hi')"],
        cwd=tmp_path,
        timeout=10,
    )
    assert result.report.status == "passed"
    assert (tmp_path / sentinel).is_file()
    assert not (Path.cwd() / sentinel).exists()
    repo_root = Path(__file__).resolve().parent.parent
    assert not (repo_root / sentinel).exists()


# ---------------------------------------------------------------------------
# 11 + 12. no real tools, no subprocess in command_pipeline.py
# ---------------------------------------------------------------------------
def _called_func_name(call: ast.Call):
    if isinstance(call.func, ast.Name):
        return call.func.id
    if isinstance(call.func, ast.Attribute):
        return call.func.attr
    return None


def test_no_real_tool_names_invoked():
    banned = ("colcon", "kicad", "ros2")
    invocation_funcs = {"run_command_pipeline", "run_command", "run"}
    for path in (PIPELINE_FILE, Path(__file__).resolve()):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            if _called_func_name(node) not in invocation_funcs:
                continue
            if not node.args:
                continue
            argv = node.args[0]
            if not isinstance(argv, (ast.List, ast.Tuple)):
                continue
            for element in argv.elts:
                if isinstance(element, ast.Constant) and isinstance(element.value, str):
                    lowered = element.value.lower()
                    for tool in banned:
                        assert tool not in lowered, (
                            f"{path.name}: invokes tool {tool!r} in a command argv"
                        )


def test_command_pipeline_does_not_use_subprocess():
    tree = ast.parse(PIPELINE_FILE.read_text(encoding="utf-8"))
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


def test_result_is_dataclass_with_expected_fields():
    import dataclasses

    assert dataclasses.is_dataclass(CommandPipelineResult)
    names = {f.name for f in dataclasses.fields(CommandPipelineResult)}
    assert names == {"command_result", "report", "findings", "findings_projection"}
