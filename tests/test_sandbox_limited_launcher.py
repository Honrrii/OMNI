"""Phase 11 Stage 9B-3B-1: standalone resource-limit launcher tests.

Pure helper tests (arg/policy parsing, fail-closed mapping) run on every
platform. Process tests that actually apply ``RLIMIT_*`` are Linux-only and
``skipif``-guarded. Every spawned target is a harmless ``sys.executable -c …``
command; no ROS2/KiCad/colcon. The launcher is always executed through its
ABSOLUTE path from an arbitrary ``tmp_path`` under a minimal environment with no
inherited ``PYTHONPATH`` — proving the standalone-by-path design.
"""

import json
import signal
import subprocess
import sys
from pathlib import Path

import pytest

import backend.app.sandbox.limited_launcher as launcher
from backend.app.sandbox.limited_launcher import (
    EXIT_APPLY_FAILED,
    EXIT_BAD_ARGS,
    EXIT_BAD_POLICY,
    EXIT_EXEC_FAILED,
    EXIT_UNSUPPORTED,
    LauncherArgsError,
    LauncherPolicyError,
    LauncherUnsupportedError,
    build_rlimit_settings,
    parse_args,
    parse_policy,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
LAUNCHER_PATH = REPO_ROOT / "backend" / "app" / "sandbox" / "limited_launcher.py"

# Minimal child environment, deliberately WITHOUT PYTHONPATH, to prove the
# launcher runs by absolute path with no inherited package path.
MINIMAL_ENV = {
    "PATH": "/usr/bin:/bin",
    "LC_ALL": "C",
    "LANG": "C",
    "PYTHONDONTWRITEBYTECODE": "1",
}

IS_LINUX = sys.platform.startswith("linux")
linux_only = pytest.mark.skipif(
    not IS_LINUX, reason="resource-limit enforcement is Linux-only"
)


def _policy_dict(**overrides):
    policy = {field: None for field in launcher.POLICY_FIELDS}
    policy.update(overrides)
    return policy


def _policy_json(**overrides):
    return json.dumps(_policy_dict(**overrides), separators=(",", ":"))


def _run_launcher(policy_json, target_argv, *, cwd, timeout=30):
    return subprocess.run(
        [
            sys.executable,
            str(LAUNCHER_PATH),
            "--policy-json",
            policy_json,
            "--",
            *target_argv,
        ],
        cwd=str(cwd),
        env=MINIMAL_ENV,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


# ---------------------------------------------------------------------------
# 1-5. parse_args
# ---------------------------------------------------------------------------
def test_parse_args_valid():
    policy_json, command = parse_args(["--policy-json", "{}", "--", "echo", "hi"])
    assert policy_json == "{}"
    assert command == ["echo", "hi"]


def test_parse_args_missing_policy_flag():
    with pytest.raises(LauncherArgsError):
        parse_args(["nope", "--", "echo"])


def test_parse_args_missing_policy_value():
    with pytest.raises(LauncherArgsError):
        parse_args(["--policy-json"])


def test_parse_args_missing_separator():
    with pytest.raises(LauncherArgsError):
        parse_args(["--policy-json", "{}", "echo", "hi"])


def test_parse_args_empty_command():
    with pytest.raises(LauncherArgsError):
        parse_args(["--policy-json", "{}", "--"])


def test_parse_args_unexpected_arg_before_separator():
    with pytest.raises(LauncherArgsError):
        parse_args(["--policy-json", "{}", "--extra", "--", "echo"])


# ---------------------------------------------------------------------------
# 6-12. parse_policy
# ---------------------------------------------------------------------------
def test_parse_policy_valid():
    policy = parse_policy(_policy_json(cpu_seconds=2, core_size_bytes=0))
    assert policy["cpu_seconds"] == 2
    assert policy["core_size_bytes"] == 0
    assert policy["open_files"] is None


def test_parse_policy_malformed_json():
    with pytest.raises(LauncherPolicyError):
        parse_policy("{not valid json")


def test_parse_policy_not_an_object():
    with pytest.raises(LauncherPolicyError):
        parse_policy("[1, 2, 3]")


def test_parse_policy_unknown_key():
    data = _policy_dict()
    data["extra"] = 1
    with pytest.raises(LauncherPolicyError):
        parse_policy(json.dumps(data))


def test_parse_policy_missing_key():
    data = _policy_dict()
    del data["cpu_seconds"]
    with pytest.raises(LauncherPolicyError):
        parse_policy(json.dumps(data))


def test_parse_policy_negative_value():
    with pytest.raises(LauncherPolicyError):
        parse_policy(_policy_json(cpu_seconds=-1))


def test_parse_policy_boolean_value():
    with pytest.raises(LauncherPolicyError):
        parse_policy(_policy_json(cpu_seconds=True))


@pytest.mark.parametrize("bad", ["5", 1.5, [1], {"a": 1}])
def test_parse_policy_non_integer_value(bad):
    data = _policy_dict(cpu_seconds=bad)
    with pytest.raises(LauncherPolicyError):
        parse_policy(json.dumps(data))


# ---------------------------------------------------------------------------
# 13-16. build_rlimit_settings: deferred + unsupported fail closed
# ---------------------------------------------------------------------------
def test_deferred_address_space_fails_closed():
    with pytest.raises(LauncherUnsupportedError):
        build_rlimit_settings(_policy_dict(address_space_bytes=1_000_000))


def test_deferred_process_count_fails_closed():
    with pytest.raises(LauncherUnsupportedError):
        build_rlimit_settings(_policy_dict(process_count=8))


def test_missing_resource_module_fails_closed(monkeypatch):
    # Simulate a platform without the 'resource' module.
    monkeypatch.setattr(launcher, "resource", None)
    with pytest.raises(LauncherUnsupportedError):
        build_rlimit_settings(_policy_dict(core_size_bytes=0))


def test_missing_rlimit_constant_fails_closed(monkeypatch):
    # A resource-like object lacking RLIMIT_* constants must fail closed, never
    # silently skip the requested limit.
    monkeypatch.setattr(launcher, "resource", object())
    with pytest.raises(LauncherUnsupportedError):
        build_rlimit_settings(_policy_dict(core_size_bytes=0))


# ---------------------------------------------------------------------------
# 17. exit-code stability
# ---------------------------------------------------------------------------
def test_exit_codes_are_stable():
    assert EXIT_BAD_ARGS == 119
    assert EXIT_BAD_POLICY == 118
    assert EXIT_UNSUPPORTED == 117
    assert EXIT_APPLY_FAILED == 116
    assert EXIT_EXEC_FAILED == 115


# ---------------------------------------------------------------------------
# 18. launch by absolute path, arbitrary cwd, minimal env (the critical proof)
# ---------------------------------------------------------------------------
@linux_only
def test_launch_by_absolute_path_minimal_env(tmp_path):
    result = _run_launcher(
        _policy_json(),  # all-None policy -> no limits applied, just execvp
        [sys.executable, "-c", "print('ok')"],
        cwd=tmp_path,
    )
    assert result.returncode == 0
    assert "ok" in result.stdout


# ---------------------------------------------------------------------------
# 19-21. child introspection of applied RLIMIT_* values
# ---------------------------------------------------------------------------
@linux_only
def test_child_sees_rlimit_core(tmp_path):
    result = _run_launcher(
        _policy_json(core_size_bytes=0),
        [
            sys.executable,
            "-c",
            "import resource; print(resource.getrlimit(resource.RLIMIT_CORE))",
        ],
        cwd=tmp_path,
    )
    assert result.returncode == 0
    assert "(0, 0)" in result.stdout


@linux_only
def test_child_sees_rlimit_nofile(tmp_path):
    result = _run_launcher(
        _policy_json(open_files=256),
        [
            sys.executable,
            "-c",
            "import resource; print(resource.getrlimit(resource.RLIMIT_NOFILE))",
        ],
        cwd=tmp_path,
    )
    assert result.returncode == 0
    assert "(256, 256)" in result.stdout


@linux_only
def test_child_sees_rlimit_fsize(tmp_path):
    result = _run_launcher(
        _policy_json(file_size_bytes=4096),
        [
            sys.executable,
            "-c",
            "import resource; print(resource.getrlimit(resource.RLIMIT_FSIZE))",
        ],
        cwd=tmp_path,
    )
    assert result.returncode == 0
    assert "(4096, 4096)" in result.stdout


# ---------------------------------------------------------------------------
# 22. CPU limit -> SIGXCPU (assert on the signal, never on wall time)
# ---------------------------------------------------------------------------
@linux_only
def test_cpu_limit_terminates_with_sigxcpu(tmp_path):
    result = _run_launcher(
        _policy_json(cpu_seconds=1),
        [sys.executable, "-c", "while True:\n    pass"],
        cwd=tmp_path,
        timeout=30,
    )
    assert result.returncode == -signal.SIGXCPU


# ---------------------------------------------------------------------------
# 23 + 27. file-size limit enforced; writes confined to tmp_path
# ---------------------------------------------------------------------------
@linux_only
def test_file_size_limit_is_enforced(tmp_path):
    # RLIMIT_FSIZE enforcement manifests EITHER as SIGXFSZ termination OR as an
    # EFBIG write error (OSError -> nonzero exit), depending on the kernel's
    # SIGXFSZ disposition. Both prove the cap; assert the unbounded write failed
    # and no file grew past the limit.
    result = _run_launcher(
        _policy_json(file_size_bytes=1024),
        [
            sys.executable,
            "-c",
            "open('big.bin', 'wb').write(b'x' * 1000000)",
        ],
        cwd=tmp_path,
        timeout=30,
    )
    assert result.returncode != 0
    assert result.returncode in (-signal.SIGXFSZ, 1)
    big = tmp_path / "big.bin"
    if big.exists():
        assert big.stat().st_size <= 1024
    # Any partial file stayed inside the caller-provided cwd...
    assert not (REPO_ROOT / "big.bin").exists()
    assert not (Path.cwd() / "big.bin").exists()


# ---------------------------------------------------------------------------
# 24. bad policy -> reserved code, target never runs
# ---------------------------------------------------------------------------
@linux_only
def test_bad_policy_returns_reserved_code_and_skips_target(tmp_path):
    sentinel = tmp_path / "sentinel.txt"
    result = _run_launcher(
        "{not valid json",
        [sys.executable, "-c", f"open({str(sentinel)!r}, 'w').write('x')"],
        cwd=tmp_path,
    )
    assert result.returncode == EXIT_BAD_POLICY
    assert not sentinel.exists()


# ---------------------------------------------------------------------------
# 25. deferred limit -> EXIT_UNSUPPORTED, target never runs
# ---------------------------------------------------------------------------
@linux_only
def test_deferred_limit_returns_unsupported_and_skips_target(tmp_path):
    sentinel = tmp_path / "sentinel.txt"
    result = _run_launcher(
        _policy_json(address_space_bytes=1_000_000),
        [sys.executable, "-c", f"open({str(sentinel)!r}, 'w').write('x')"],
        cwd=tmp_path,
    )
    assert result.returncode == EXIT_UNSUPPORTED
    assert not sentinel.exists()


# ---------------------------------------------------------------------------
# 26. missing target executable -> EXIT_EXEC_FAILED
# ---------------------------------------------------------------------------
@linux_only
def test_missing_executable_returns_exec_failed(tmp_path):
    result = _run_launcher(
        _policy_json(),
        ["/nonexistent/omni_no_such_binary_xyz"],
        cwd=tmp_path,
    )
    assert result.returncode == EXIT_EXEC_FAILED


# ---------------------------------------------------------------------------
# 28. no orphan process remains (subprocess.run reaps; result is terminal)
# ---------------------------------------------------------------------------
@linux_only
def test_no_orphan_process_after_cpu_kill(tmp_path):
    result = _run_launcher(
        _policy_json(cpu_seconds=1),
        [sys.executable, "-c", "while True:\n    pass"],
        cwd=tmp_path,
        timeout=30,
    )
    # A terminal returncode means the child was reaped, not left orphaned.
    assert result.returncode is not None
    assert result.returncode == -signal.SIGXCPU
