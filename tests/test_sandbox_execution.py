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

import signal

from backend.app.sandbox.execution import (
    CommandResult,
    ResourceLimitsUnsupportedError,
    _LAUNCHER_PATH,
    _classify_resource_outcome,
    run_command,
)
from backend.app.sandbox.limited_launcher import (
    EXIT_APPLY_FAILED,
    EXIT_BAD_ARGS,
    EXIT_BAD_POLICY,
    EXIT_EXEC_FAILED,
    EXIT_UNSUPPORTED,
)
from backend.app.sandbox.resource_policy import ResourceLimits

IS_LINUX = sys.platform.startswith("linux")
linux_only = pytest.mark.skipif(
    not IS_LINUX, reason="resource-limit enforcement is Linux-only"
)

RESULT_KEYS = {
    "command",
    "returncode",
    "stdout",
    "stderr",
    "timed_out",
    "timeout_seconds",
    "output_limit_bytes",
    "output_limit_exceeded",
    "stdout_capture_truncated",
    "stderr_capture_truncated",
    "resource_limits_requested",
    "resource_limits_applied",
    "resource_limit_exceeded",
    "resource_limit_kind",
    "launcher_error",
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


# ---------------------------------------------------------------------------
# Stage 9B-2: capture-time per-stream output cap
# ---------------------------------------------------------------------------
def _write_bytes_cmd(stream: str, count: int) -> list[str]:
    # Emit exactly ``count`` raw bytes to the named stream (no trailing newline).
    return [
        sys.executable,
        "-c",
        f"import sys; sys.{stream}.buffer.write(b'x' * {count})",
    ]


def test_uncapped_default_has_new_fields_defaults(tmp_path):
    result = run_command(
        [sys.executable, "-c", "print('ok')"],
        cwd=tmp_path,
        timeout=10,
    )
    assert result.returncode == 0
    assert "ok" in result.stdout
    assert result.output_limit_bytes is None
    assert result.output_limit_exceeded is False
    assert result.stdout_capture_truncated is False
    assert result.stderr_capture_truncated is False


def test_cap_not_exceeded_retains_full_output(tmp_path):
    result = run_command(
        [
            sys.executable,
            "-c",
            "import sys; sys.stdout.buffer.write(b'hello'); "
            "sys.stderr.buffer.write(b'err')",
        ],
        cwd=tmp_path,
        timeout=10,
        max_output_bytes=1000,
    )
    assert result.returncode == 0
    assert result.stdout == "hello"
    assert result.stderr == "err"
    assert result.output_limit_bytes == 1000
    assert result.output_limit_exceeded is False
    assert result.stdout_capture_truncated is False
    assert result.stderr_capture_truncated is False


def test_exact_limit_output_is_not_truncated(tmp_path):
    # Output byte length exactly equals the limit -> NOT exceedance.
    result = run_command(
        _write_bytes_cmd("stdout", 10),
        cwd=tmp_path,
        timeout=10,
        max_output_bytes=10,
    )
    assert result.returncode == 0
    assert len(result.stdout.encode("utf-8")) == 10
    assert result.output_limit_exceeded is False
    assert result.stdout_capture_truncated is False


def test_stdout_exceeds_limit(tmp_path):
    result = run_command(
        _write_bytes_cmd("stdout", 100_000),
        cwd=tmp_path,
        timeout=10,
        max_output_bytes=100,
    )
    assert len(result.stdout.encode("utf-8")) <= 100
    assert result.stdout_capture_truncated is True
    assert result.output_limit_exceeded is True
    assert result.timed_out is False


def test_stderr_exceeds_limit(tmp_path):
    result = run_command(
        _write_bytes_cmd("stderr", 100_000),
        cwd=tmp_path,
        timeout=10,
        max_output_bytes=100,
    )
    assert len(result.stderr.encode("utf-8")) <= 100
    assert result.stderr_capture_truncated is True
    assert result.output_limit_exceeded is True
    assert result.timed_out is False


def test_zero_byte_limit_retains_nothing(tmp_path):
    result = run_command(
        _write_bytes_cmd("stdout", 50),
        cwd=tmp_path,
        timeout=10,
        max_output_bytes=0,
    )
    assert result.stdout == ""
    assert result.output_limit_bytes == 0
    assert result.output_limit_exceeded is True
    assert result.stdout_capture_truncated is True
    assert result.timed_out is False


def test_output_limit_distinct_from_timeout(tmp_path):
    # Fast flood with a generous timeout: the cap fires, not the clock.
    result = run_command(
        _write_bytes_cmd("stdout", 1_000_000),
        cwd=tmp_path,
        timeout=30,
        max_output_bytes=100,
    )
    assert result.output_limit_exceeded is True
    assert result.timed_out is False


def test_capped_result_is_deterministic(tmp_path):
    cmd = _write_bytes_cmd("stdout", 1000)
    first = run_command(cmd, cwd=tmp_path, timeout=10, max_output_bytes=100).to_dict()
    second = run_command(cmd, cwd=tmp_path, timeout=10, max_output_bytes=100).to_dict()
    assert first == second
    assert set(first.keys()) == RESULT_KEYS


def test_negative_max_output_bytes_rejected(tmp_path):
    with pytest.raises(ValueError):
        run_command(
            [sys.executable, "-c", "print('x')"],
            cwd=tmp_path,
            timeout=10,
            max_output_bytes=-1,
        )


def test_non_integer_max_output_bytes_rejected(tmp_path):
    with pytest.raises(TypeError):
        run_command(
            [sys.executable, "-c", "print('x')"],
            cwd=tmp_path,
            timeout=10,
            max_output_bytes=1.5,
        )


def test_run_command_signature_has_max_output_bytes():
    params = inspect.signature(run_command).parameters
    assert "max_output_bytes" in params


def test_allowlist_and_cap_work_together(tmp_path):
    basename = os.path.basename(sys.executable)
    result = run_command(
        [sys.executable, "-c", "import sys; sys.stdout.buffer.write(b'ok')"],
        cwd=tmp_path,
        timeout=10,
        allowed_executables=[basename],
        max_output_bytes=1000,
    )
    assert result.returncode == 0
    assert result.stdout == "ok"
    assert result.output_limit_exceeded is False


# ---------------------------------------------------------------------------
# Stage 9B-3B-2: resource-limit launcher integration
# ---------------------------------------------------------------------------
_ALL_NONE_POLICY = ResourceLimits(
    cpu_seconds=None,
    address_space_bytes=None,
    file_size_bytes=None,
    open_files=None,
    process_count=None,
    core_size_bytes=None,
)


def _getrlimit_cmd(const_name: str) -> list[str]:
    return [
        sys.executable,
        "-c",
        f"import resource; print(resource.getrlimit(resource.{const_name}))",
    ]


# 1. no policy -> existing behavior, original command echoed
def test_resource_limits_none_preserves_behavior(tmp_path):
    cmd = [sys.executable, "-c", "print('ok')"]
    result = run_command(cmd, cwd=tmp_path, timeout=10, resource_limits=None)
    assert result.returncode == 0
    assert "ok" in result.stdout
    assert result.command == cmd


# 2. all-None policy is empty -> no wrapping, no platform requirement
def test_all_none_policy_does_not_wrap_or_require_support(tmp_path, monkeypatch):
    import backend.app.sandbox.execution as execution_module

    # Even if the platform reports unsupported, an empty policy must still run
    # (it never reaches the launcher / platform gate).
    monkeypatch.setattr(execution_module, "resource_limits_supported", lambda: False)
    assert _ALL_NONE_POLICY.is_empty() is True
    result = run_command(
        [sys.executable, "-c", "print('ok')"],
        cwd=tmp_path,
        timeout=10,
        resource_limits=_ALL_NONE_POLICY,
    )
    assert result.returncode == 0
    assert "ok" in result.stdout


# 3. invalid policy type -> TypeError before any spawn
@pytest.mark.parametrize("bad", ["policy", {"cpu_seconds": 1}, 5, object()])
def test_invalid_resource_limits_type_rejected(tmp_path, bad):
    sentinel = tmp_path / "sentinel.txt"
    with pytest.raises(TypeError):
        run_command(
            [sys.executable, "-c", f"open({str(sentinel)!r}, 'w').write('x')"],
            cwd=tmp_path,
            timeout=10,
            resource_limits=bad,
        )
    assert not sentinel.exists()


# 4. default ResourceLimits() wraps and applies RLIMIT_CORE=(0, 0)
@linux_only
def test_default_policy_applies_core_zero(tmp_path):
    result = run_command(
        _getrlimit_cmd("RLIMIT_CORE"),
        cwd=tmp_path,
        timeout=30,
        resource_limits=ResourceLimits(),
    )
    assert result.returncode == 0
    assert "(0, 0)" in result.stdout


# 5. original allowlist permits the original executable with a policy
@linux_only
def test_allowlist_permits_original_executable_with_policy(tmp_path):
    basename = os.path.basename(sys.executable)
    result = run_command(
        [sys.executable, "-c", "print('ok')"],
        cwd=tmp_path,
        timeout=30,
        allowed_executables=[basename],
        resource_limits=ResourceLimits(),
    )
    assert result.returncode == 0
    assert "ok" in result.stdout


# 6. original allowlist rejects before wrapping; no child/launcher runs
def test_allowlist_rejects_original_before_wrapping(tmp_path):
    sentinel = tmp_path / "sentinel.txt"
    with pytest.raises(ValueError):
        run_command(
            [sys.executable, "-c", f"open({str(sentinel)!r}, 'w').write('x')"],
            cwd=tmp_path,
            timeout=10,
            allowed_executables=["definitely-not-this-binary"],
            resource_limits=ResourceLimits(),
        )
    assert not sentinel.exists()


# 7. original command identity is preserved (no wrapper leakage)
@linux_only
def test_command_echo_is_original_not_wrapper(tmp_path):
    cmd = [sys.executable, "-c", "print('hi')"]
    result = run_command(
        cmd, cwd=tmp_path, timeout=30, resource_limits=ResourceLimits()
    )
    assert result.command == cmd
    flat = " ".join(result.command)
    assert str(_LAUNCHER_PATH) not in flat
    assert "--policy-json" not in result.command
    assert "core_size_bytes" not in flat


# 8. uncapped path with a policy succeeds (harmless limit applied)
@linux_only
def test_uncapped_path_with_policy(tmp_path):
    result = run_command(
        _getrlimit_cmd("RLIMIT_NOFILE"),
        cwd=tmp_path,
        timeout=30,
        resource_limits=ResourceLimits(open_files=256),
    )
    assert result.returncode == 0
    assert "(256, 256)" in result.stdout


# 9. capped path with a policy still caps flooding output
@linux_only
def test_capped_path_with_policy_truncates(tmp_path):
    result = run_command(
        [sys.executable, "-c", "import sys; sys.stdout.buffer.write(b'x' * 100000)"],
        cwd=tmp_path,
        timeout=30,
        max_output_bytes=100,
        resource_limits=ResourceLimits(),
    )
    assert len(result.stdout.encode("utf-8")) <= 100
    assert result.stdout_capture_truncated is True
    assert result.output_limit_exceeded is True


# 10. timeout still fires with the launcher in the path
@linux_only
def test_timeout_with_policy(tmp_path):
    result = run_command(
        [sys.executable, "-c", "import time; time.sleep(5)"],
        cwd=tmp_path,
        timeout=0.5,
        resource_limits=ResourceLimits(),
    )
    assert result.timed_out is True
    assert result.returncode is None


# 11. arbitrary tmp_path cwd: launcher reachable, child sees the cwd
@linux_only
def test_policy_run_from_arbitrary_cwd(tmp_path):
    result = run_command(
        [sys.executable, "-c", "import os; print(os.getcwd())"],
        cwd=tmp_path,
        timeout=30,
        resource_limits=ResourceLimits(),
    )
    assert result.returncode == 0
    assert result.stdout.strip() == str(tmp_path)


# 12. unsupported platform fails closed before spawn
def test_unsupported_platform_fails_closed(tmp_path, monkeypatch):
    import backend.app.sandbox.execution as execution_module

    monkeypatch.setattr(execution_module, "resource_limits_supported", lambda: False)
    sentinel = tmp_path / "sentinel.txt"
    with pytest.raises(ResourceLimitsUnsupportedError):
        run_command(
            [sys.executable, "-c", f"open({str(sentinel)!r}, 'w').write('x')"],
            cwd=tmp_path,
            timeout=10,
            resource_limits=ResourceLimits(),
        )
    assert not sentinel.exists()


# 13. deferred address_space_bytes -> launcher fails closed, target never runs
@linux_only
def test_deferred_address_space_fails_closed(tmp_path):
    sentinel = tmp_path / "sentinel.txt"
    result = run_command(
        [sys.executable, "-c", f"open({str(sentinel)!r}, 'w').write('x')"],
        cwd=tmp_path,
        timeout=30,
        resource_limits=ResourceLimits(address_space_bytes=1_000_000),
    )
    assert result.returncode == EXIT_UNSUPPORTED
    assert not sentinel.exists()


# 14. deferred process_count -> same fail-closed behavior
@linux_only
def test_deferred_process_count_fails_closed(tmp_path):
    sentinel = tmp_path / "sentinel.txt"
    result = run_command(
        [sys.executable, "-c", f"open({str(sentinel)!r}, 'w').write('x')"],
        cwd=tmp_path,
        timeout=30,
        resource_limits=ResourceLimits(process_count=8),
    )
    assert result.returncode == EXIT_UNSUPPORTED
    assert not sentinel.exists()


# 15. launcher path is absolute and present
def test_launcher_path_is_absolute_and_exists():
    assert _LAUNCHER_PATH.is_absolute()
    assert _LAUNCHER_PATH.exists()


# 16. signature includes resource_limits
def test_run_command_signature_has_resource_limits():
    params = inspect.signature(run_command).parameters
    assert "resource_limits" in params


# 17. CommandResult field set is unchanged by this stage
def test_command_result_field_set_unchanged():
    import dataclasses

    field_names = {f.name for f in dataclasses.fields(CommandResult)}
    assert field_names == RESULT_KEYS


# 18. determinism for identical harmless policy-enabled runs
@linux_only
def test_policy_enabled_run_is_deterministic(tmp_path):
    cmd = _getrlimit_cmd("RLIMIT_CORE")
    first = run_command(
        cmd, cwd=tmp_path, timeout=30, resource_limits=ResourceLimits()
    ).to_dict()
    second = run_command(
        cmd, cwd=tmp_path, timeout=30, resource_limits=ResourceLimits()
    ).to_dict()
    assert first == second
    assert set(first.keys()) == RESULT_KEYS


# ---------------------------------------------------------------------------
# Stage 9B-3C-1: resource-limit / launcher-outcome classification
# ---------------------------------------------------------------------------
# Pure classifier: deterministic, no spawning.
def test_classify_sigxcpu_is_cpu():
    assert _classify_resource_outcome(-signal.SIGXCPU, True) == (True, "cpu", None)
    # Reliable signals are classified regardless of the applied flag.
    assert _classify_resource_outcome(-signal.SIGXCPU, False) == (True, "cpu", None)


def test_classify_sigxfsz_is_file_size():
    assert _classify_resource_outcome(-signal.SIGXFSZ, True) == (
        True,
        "file_size",
        None,
    )


@pytest.mark.parametrize(
    "code, kind",
    [
        (EXIT_BAD_ARGS, "bad_launcher_args"),
        (EXIT_BAD_POLICY, "invalid_resource_policy"),
        (EXIT_UNSUPPORTED, "unsupported_resource_policy"),
        (EXIT_APPLY_FAILED, "resource_limit_apply_failed"),
        (EXIT_EXEC_FAILED, "target_exec_failed"),
    ],
)
def test_classify_launcher_codes_when_applied(code, kind):
    assert _classify_resource_outcome(code, True) == (False, None, kind)


@pytest.mark.parametrize(
    "code",
    [EXIT_BAD_ARGS, EXIT_BAD_POLICY, EXIT_UNSUPPORTED, EXIT_APPLY_FAILED, EXIT_EXEC_FAILED],
)
def test_classify_launcher_codes_ignored_when_not_applied(code):
    # Without wrapping, a positive reserved code is the target's own exit code.
    assert _classify_resource_outcome(code, False) == (False, None, None)


def test_classify_success_is_unclassified():
    assert _classify_resource_outcome(0, True) == (False, None, None)


def test_classify_ordinary_nonzero_is_unclassified():
    assert _classify_resource_outcome(3, True) == (False, None, None)


def test_classify_sigkill_is_unclassified():
    assert _classify_resource_outcome(-signal.SIGKILL, True) == (False, None, None)


def test_classify_sigsegv_is_unclassified():
    assert _classify_resource_outcome(-signal.SIGSEGV, True) == (False, None, None)


def test_classify_none_returncode_is_unclassified():
    assert _classify_resource_outcome(None, True) == (False, None, None)


# Execution facts: requested / applied recorded by run_command.
def test_no_policy_records_no_resource_facts(tmp_path):
    result = run_command(
        [sys.executable, "-c", "print('ok')"], cwd=tmp_path, timeout=10
    )
    assert result.resource_limits_requested is None
    assert result.resource_limits_applied is False
    assert result.resource_limit_exceeded is False
    assert result.resource_limit_kind is None
    assert result.launcher_error is None


def test_all_none_policy_records_no_resource_facts(tmp_path):
    result = run_command(
        [sys.executable, "-c", "print('ok')"],
        cwd=tmp_path,
        timeout=10,
        resource_limits=_ALL_NONE_POLICY,
    )
    assert result.resource_limits_requested is None
    assert result.resource_limits_applied is False


@linux_only
def test_default_policy_success_records_applied(tmp_path):
    result = run_command(
        [sys.executable, "-c", "print('ok')"],
        cwd=tmp_path,
        timeout=30,
        resource_limits=ResourceLimits(),
    )
    assert result.returncode == 0
    assert result.resource_limits_requested == ResourceLimits().to_dict()
    assert result.resource_limits_applied is True
    assert result.resource_limit_exceeded is False
    assert result.resource_limit_kind is None
    assert result.launcher_error is None


@linux_only
def test_cpu_limit_integration_classifies_cpu(tmp_path):
    result = run_command(
        [sys.executable, "-c", "while True:\n    pass"],
        cwd=tmp_path,
        timeout=30,
        resource_limits=ResourceLimits(cpu_seconds=1),
    )
    assert result.returncode == -signal.SIGXCPU
    assert result.resource_limit_exceeded is True
    assert result.resource_limit_kind == "cpu"
    assert result.launcher_error is None
    assert result.resource_limits_applied is True


@linux_only
def test_deferred_policy_classifies_launcher_error(tmp_path):
    sentinel = tmp_path / "sentinel.txt"
    result = run_command(
        [sys.executable, "-c", f"open({str(sentinel)!r}, 'w').write('x')"],
        cwd=tmp_path,
        timeout=30,
        resource_limits=ResourceLimits(address_space_bytes=1_000_000),
    )
    assert result.returncode == EXIT_UNSUPPORTED
    assert result.launcher_error == "unsupported_resource_policy"
    assert result.resource_limit_exceeded is False
    assert not sentinel.exists()


@linux_only
def test_timeout_with_policy_preserves_facts_without_resource_classification(tmp_path):
    result = run_command(
        [sys.executable, "-c", "import time; time.sleep(5)"],
        cwd=tmp_path,
        timeout=0.5,
        resource_limits=ResourceLimits(),
    )
    assert result.timed_out is True
    assert result.returncode is None
    assert result.resource_limits_applied is True
    assert result.resource_limits_requested == ResourceLimits().to_dict()
    # Timeout is the cause; resource classification stays at clear defaults.
    assert result.resource_limit_exceeded is False
    assert result.resource_limit_kind is None
    assert result.launcher_error is None


@linux_only
def test_output_cap_with_policy_preserves_output_facts(tmp_path):
    result = run_command(
        [sys.executable, "-c", "import sys; sys.stdout.buffer.write(b'x' * 100000)"],
        cwd=tmp_path,
        timeout=30,
        max_output_bytes=100,
        resource_limits=ResourceLimits(),
    )
    assert result.output_limit_exceeded is True
    assert result.stdout_capture_truncated is True
    # Our SIGKILL is not a resource-limit signal; classification stays clean.
    assert result.resource_limit_exceeded is False
    assert result.resource_limit_kind is None
    assert result.launcher_error is None
    assert result.resource_limits_applied is True
