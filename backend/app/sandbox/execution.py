"""
OMNI Sandbox — low-level controlled command execution (Phase 11 Stage 5).

This module is the sandbox "subprocess wall": a single, explicit boundary for
running an external command with ``shell=False``, an enforced timeout, captured
output, a caller-provided working directory, a minimal deterministic
environment, a closed stdin, and an optional executable allowlist.

HONEST SECURITY NOTE — this is NOT a full security sandbox.
Python ``subprocess`` controls do not provide:
- a shell (shell execution is unsupported and never enabled here),
- network isolation (a child process can still open sockets — unsupported),
- filesystem isolation (the working directory is a convention, not a jail —
  a child can read/write anywhere the running user can),
- resource isolation (no CPU, memory, file-descriptor, or process-count
  limits; output is buffered in memory),
- protection from untrusted code.

Stage 9B added two minimal hardenings without changing the result shape:
``stdin`` is always closed (``subprocess.DEVNULL``), and ``run_command`` accepts
an optional ``allowed_executables`` gate (off by default). A capture-time output
cap and OS resource limits are deliberately deferred to later stages.

For untrusted code or dangerous external tools, future stages must use real
isolation (OS rlimits/cgroups, nsjail/firejail, containers, seccomp, network
namespaces). This remains a controlled execution boundary, not a jail. It runs
only explicit argv commands passed by the caller; it does not run ROS2, KiCad,
or colcon.
"""
from __future__ import annotations

import os
import signal
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Optional, Union


# Minimal, deterministic default environment. The full parent ``os.environ`` is
# never inherited implicitly; callers may override or add keys via ``env``.
_DEFAULT_ENV = {
    "PATH": "/usr/bin:/bin",
    "LC_ALL": "C",
    "LANG": "C",
}


@dataclass
class CommandResult:
    """The deterministic outcome of a single command run.

    No timestamps, no UUIDs, and no measured wall-clock duration are stored, so
    the same command over the same inputs yields an equal ``to_dict()``.
    ``timeout_seconds`` is the configured limit (an input echo), not elapsed
    time.
    """

    command: list[str]
    returncode: Optional[int]
    stdout: str
    stderr: str
    timed_out: bool
    timeout_seconds: float

    def to_dict(self) -> dict[str, Any]:
        """Deterministic dict with a fixed key order and a fresh command list."""
        return {
            "command": list(self.command),
            "returncode": self.returncode,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "timed_out": self.timed_out,
            "timeout_seconds": self.timeout_seconds,
        }


def _validate_command(command: Union[list, tuple]) -> list[str]:
    """Coerce and validate an argv command. Reject strings and bad elements."""
    if isinstance(command, str):
        raise TypeError(
            "command must be an argv list/tuple, not a string "
            "(string commands would imply shell execution, which is unsupported)."
        )
    if not isinstance(command, (list, tuple)):
        raise TypeError(f"command must be a list or tuple of strings, got {type(command)!r}.")
    if len(command) == 0:
        raise ValueError("command must be a non-empty argv list/tuple.")
    argv: list[str] = []
    for element in command:
        if not isinstance(element, str):
            raise TypeError(
                f"command elements must all be strings; got {type(element)!r}."
            )
        argv.append(element)
    return argv


def _check_allowed(argv: list[str], allowed: Optional[Iterable[str]]) -> None:
    """Gate the executable against an optional allowlist, before spawning.

    No allowlist (``None``) means no gating — current default behavior. When an
    allowlist is provided, ``argv[0]`` is permitted if it matches an entry
    exactly OR its basename matches an entry; otherwise a ``ValueError`` is
    raised before any process is started.
    """
    if allowed is None:
        return
    allowed_set = set(allowed)
    executable = argv[0]
    if executable in allowed_set or os.path.basename(executable) in allowed_set:
        return
    raise ValueError(
        f"executable {executable!r} is not in the allowed_executables allowlist."
    )


def _effective_env(env: Optional[dict[str, str]]) -> dict[str, str]:
    """Build the child environment: minimal defaults, caller keys override."""
    effective = dict(_DEFAULT_ENV)
    if env:
        effective.update(env)
    return effective


def _as_text(value: Any) -> str:
    """Normalize possibly-None / bytes stream content to a string."""
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


def run_command(
    command: Union[list[str], tuple],
    *,
    cwd: Union[str, Path],
    timeout: float,
    env: Optional[dict[str, str]] = None,
    allowed_executables: Optional[Iterable[str]] = None,
) -> CommandResult:
    """Run an explicit argv command with ``shell=False`` and an enforced timeout.

    There is intentionally no ``shell`` parameter — shell execution is
    unsupported. The command runs in ``cwd`` with a minimal deterministic
    environment (``env`` overrides/extends the defaults) and with ``stdin``
    closed (``subprocess.DEVNULL``). On timeout the child is killed (best effort,
    including its process group), ``timed_out`` is True, and ``returncode`` is
    None.

    ``allowed_executables`` is an opt-in gate (default ``None`` = no gating,
    preserving prior behavior). When provided, the command's executable
    (``argv[0]``) must match an allowlist entry exactly or by basename, else a
    ``ValueError`` is raised before any process is spawned.
    """
    argv = _validate_command(command)
    _check_allowed(argv, allowed_executables)
    effective_env = _effective_env(env)

    try:
        completed = subprocess.run(
            argv,
            cwd=str(cwd),
            env=effective_env,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
            start_new_session=True,
        )
        return CommandResult(
            command=argv,
            returncode=completed.returncode,
            stdout=_as_text(completed.stdout),
            stderr=_as_text(completed.stderr),
            timed_out=False,
            timeout_seconds=float(timeout),
        )
    except subprocess.TimeoutExpired as error:
        # ``subprocess.run`` already kills the direct child on timeout. With
        # ``start_new_session=True`` the child leads its own process group, so
        # best-effort terminate the whole group to reduce grandchild leakage.
        # (A guaranteed group reap would need a lower-level Popen handle, which
        # Stage 5 intentionally does not use.)
        _best_effort_kill_group(getattr(error, "pid", None))
        return CommandResult(
            command=argv,
            returncode=None,
            stdout=_as_text(error.stdout),
            stderr=_as_text(error.stderr),
            timed_out=True,
            timeout_seconds=float(timeout),
        )


def _best_effort_kill_group(pid: Optional[int]) -> None:
    """Try to SIGKILL the child's process group; never raise."""
    if not pid:
        return
    try:
        os.killpg(os.getpgid(pid), signal.SIGKILL)
    except (ProcessLookupError, PermissionError, OSError):
        # The child is already gone or the group is unavailable — nothing to do.
        pass
