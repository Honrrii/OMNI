"""Phase 11 Stage 5: sandbox subprocess wall tests.

Exercises the low-level controlled execution boundary (backend/app/sandbox/
execution.py): success / failure / timeout, cwd isolation, environment
minimization, deterministic result dict, argv-only enforcement, and that no file
escapes the caller-provided temp dir. Only harmless commands are ever run
(sys.executable -c …). No ROS2/KiCad/colcon, no network.
"""

import ast
import inspect
import os
import sys
from pathlib import Path

import pytest

from backend.app.sandbox.execution import CommandResult, run_command

RESULT_KEYS = {
    "command",
    "returncode",
    "stdout",
    "stderr",
    "timed_out",
    "timeout_seconds",
}

EXECUTION_FILE = (
    Path(__file__).resolve().parent.parent
    / "backend"
    / "app"
    / "sandbox"
    / "execution.py"
)


# ---------------------------------------------------------------------------
# 1. success
# ---------------------------------------------------------------------------
def test_success_command(tmp_path):
    result = run_command(
        [sys.executable, "-c", "print('ok')"],
        cwd=tmp_path,
        timeout=10,
    )
    assert result.returncode == 0
    assert "ok" in result.stdout
    assert result.timed_out is False


# ---------------------------------------------------------------------------
# 2. failure
# ---------------------------------------------------------------------------
def test_failure_command(tmp_path):
    result = run_command(
        [sys.executable, "-c", "import sys; sys.exit(3)"],
        cwd=tmp_path,
        timeout=10,
    )
    assert result.returncode == 3
    assert result.timed_out is False


# ---------------------------------------------------------------------------
# 3. timeout
# ---------------------------------------------------------------------------
def test_timeout_command(tmp_path):
    result = run_command(
        [sys.executable, "-c", "import time; time.sleep(5)"],
        cwd=tmp_path,
        timeout=0.5,
    )
    assert result.timed_out is True
    assert result.returncode is None
    assert isinstance(result.stdout, str)
    assert isinstance(result.stderr, str)


# ---------------------------------------------------------------------------
# 4. cwd isolation
# ---------------------------------------------------------------------------
def test_cwd_isolation(tmp_path):
    result = run_command(
        [sys.executable, "-c", "import os; print(os.getcwd())"],
        cwd=tmp_path,
        timeout=10,
    )
    assert result.returncode == 0
    # The child's working directory is the caller-provided temp dir.
    assert result.stdout.strip() == str(tmp_path)


# ---------------------------------------------------------------------------
# 5. environment minimization
# ---------------------------------------------------------------------------
def test_env_minimization_does_not_leak_parent_secret(tmp_path, monkeypatch):
    monkeypatch.setenv("OMNI_SECRET", "leak")
    result = run_command(
        [sys.executable, "-c", "import os; print(os.environ.get('OMNI_SECRET'))"],
        cwd=tmp_path,
        timeout=10,
    )
    assert result.stdout.strip() == "None"


def test_env_minimization_defaults_present(tmp_path):
    result = run_command(
        [sys.executable, "-c", "import os; print(os.environ.get('LC_ALL'))"],
        cwd=tmp_path,
        timeout=10,
    )
    assert result.stdout.strip() == "C"


def test_caller_env_can_add_keys(tmp_path):
    result = run_command(
        [sys.executable, "-c", "import os; print(os.environ.get('OMNI_FLAG'))"],
        cwd=tmp_path,
        timeout=10,
        env={"OMNI_FLAG": "on"},
    )
    assert result.stdout.strip() == "on"


# ---------------------------------------------------------------------------
# 6. deterministic result dict
# ---------------------------------------------------------------------------
def test_deterministic_result_dict(tmp_path):
    cmd = [sys.executable, "-c", "print('stable')"]
    first = run_command(cmd, cwd=tmp_path, timeout=10).to_dict()
    second = run_command(cmd, cwd=tmp_path, timeout=10).to_dict()
    assert first == second
    assert set(first.keys()) == RESULT_KEYS


def test_to_dict_command_list_is_fresh(tmp_path):
    result = run_command(
        [sys.executable, "-c", "print('x')"], cwd=tmp_path, timeout=10
    )
    d = result.to_dict()
    d["command"].append("mutated")
    assert "mutated" not in result.command


# ---------------------------------------------------------------------------
# 7. argv-only / no shell
# ---------------------------------------------------------------------------
def test_string_command_rejected(tmp_path):
    with pytest.raises(TypeError):
        run_command("echo hi", cwd=tmp_path, timeout=10)


def test_empty_command_rejected(tmp_path):
    with pytest.raises(ValueError):
        run_command([], cwd=tmp_path, timeout=10)


def test_non_string_element_rejected(tmp_path):
    with pytest.raises(TypeError):
        run_command([sys.executable, 123], cwd=tmp_path, timeout=10)


def test_run_command_has_no_shell_parameter():
    params = inspect.signature(run_command).parameters
    assert "shell" not in params


# ---------------------------------------------------------------------------
# 8. no file writes outside the caller temp dir
# ---------------------------------------------------------------------------
def test_child_file_writes_stay_in_temp_dir(tmp_path):
    sentinel = "omni_stage5_sentinel.txt"
    result = run_command(
        [
            sys.executable,
            "-c",
            "open('omni_stage5_sentinel.txt', 'w').write('hi')",
        ],
        cwd=tmp_path,
        timeout=10,
    )
    assert result.returncode == 0
    # Relative-path write landed inside the provided cwd...
    assert (tmp_path / sentinel).is_file()
    # ...and nowhere near the test process cwd or the repo root.
    assert not (Path.cwd() / sentinel).exists()
    repo_root = Path(__file__).resolve().parent.parent
    assert not (repo_root / sentinel).exists()


# ---------------------------------------------------------------------------
# 9. no real tool execution (static guard over helper + this test file)
# ---------------------------------------------------------------------------
def _called_func_name(call: ast.Call):
    if isinstance(call.func, ast.Name):
        return call.func.id
    if isinstance(call.func, ast.Attribute):
        return call.func.attr
    return None


def test_no_real_tool_names_invoked():
    # "Invoked" means passed as the argv of an actual command call: run_command
    # in the tests, or subprocess.run in the helper. Honest prose naming these
    # tools (to say they are NOT run) must not trip the guard.
    banned = ("colcon", "kicad", "ros2")
    invocation_funcs = {"run_command", "run"}
    for path in (EXECUTION_FILE, Path(__file__).resolve()):
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


# ---------------------------------------------------------------------------
# 10. honesty: module documents that it is not a full security sandbox
# ---------------------------------------------------------------------------
def test_module_docstring_declares_not_a_security_sandbox():
    import backend.app.sandbox.execution as execution_module

    doc = (execution_module.__doc__ or "").lower()
    assert "not a full security sandbox" in doc
    assert "network isolation" in doc
    assert "untrusted code" in doc


def test_command_result_is_dataclass_with_expected_fields():
    import dataclasses

    assert dataclasses.is_dataclass(CommandResult)
    field_names = {f.name for f in dataclasses.fields(CommandResult)}
    assert field_names == RESULT_KEYS


# ---------------------------------------------------------------------------
# Stage 9B: stdin closed (DEVNULL)
# ---------------------------------------------------------------------------
def test_stdin_is_closed_child_receives_eof(tmp_path):
    # The child reads stdin; with stdin closed it must get EOF -> empty string.
    result = run_command(
        [sys.executable, "-c", "import sys; print(repr(sys.stdin.read()))"],
        cwd=tmp_path,
        timeout=10,
    )
    assert result.returncode == 0
    assert result.timed_out is False
    assert result.stdout.strip() == "''"


# ---------------------------------------------------------------------------
# Stage 9B: optional executable allowlist
# ---------------------------------------------------------------------------
def test_allowlist_permits_full_executable_path(tmp_path):
    result = run_command(
        [sys.executable, "-c", "print('ok')"],
        cwd=tmp_path,
        timeout=10,
        allowed_executables=[sys.executable],
    )
    assert result.returncode == 0
    assert "ok" in result.stdout


def test_allowlist_permits_basename(tmp_path):
    basename = os.path.basename(sys.executable)
    result = run_command(
        [sys.executable, "-c", "print('ok')"],
        cwd=tmp_path,
        timeout=10,
        allowed_executables=[basename],
    )
    assert result.returncode == 0
    assert "ok" in result.stdout


def test_allowlist_rejects_unlisted_executable_before_spawn(tmp_path):
    # A command that WOULD write a sentinel if it ever ran; the rejection must
    # happen before spawn, so the sentinel must never appear.
    sentinel = tmp_path / "should_not_exist.txt"
    with pytest.raises(ValueError):
        run_command(
            [sys.executable, "-c", f"open({str(sentinel)!r}, 'w').write('x')"],
            cwd=tmp_path,
            timeout=10,
            allowed_executables=["definitely-not-this-binary"],
        )
    assert not sentinel.exists()


def test_allowlist_default_none_runs_anything(tmp_path):
    # Default behavior is unchanged: no allowlist means no gating.
    result = run_command(
        [sys.executable, "-c", "print('ok')"],
        cwd=tmp_path,
        timeout=10,
    )
    assert result.returncode == 0


def test_run_command_signature_has_allowed_executables_and_no_shell():
    params = inspect.signature(run_command).parameters
    assert "allowed_executables" in params
    assert "shell" not in params
