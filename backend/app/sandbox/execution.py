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
an optional ``allowed_executables`` gate (off by default).

Stage 9B-2 adds an opt-in capture-time output cap: when ``max_output_bytes`` is
configured, ``run_command`` switches to a streaming ``subprocess.Popen`` path
that retains at most ``max_output_bytes`` per stream and kills the process group
once a stream overflows, instead of buffering all output in memory via
``subprocess.run(capture_output=True)``. The cap is independent per stream
(worst-case retained output is ~``2 * max_output_bytes``) and is reported
separately from timeout. OS resource limits (CPU/memory/rlimits) remain
deliberately deferred to later stages.

Stage 9B-3C-2 makes launcher failures AUTHORITATIVE rather than heuristic. When
a resource policy causes launcher wrapping, the parent opens a dedicated POSIX
status pipe (never stdout/stderr), hands its write end to ``limited_launcher.py``
via ``--status-fd`` / ``pass_fds``, and closes its own copy of the write end
right after spawning. The launcher writes a single deterministic ASCII token on
any setup/exec failure and closes the fd (close-on-exec) on a successful
``execvp`` — so the parent reads a known token (launcher error), EOF (success),
or a malformed payload (fail-closed protocol error). A target command can now
exit with one of the launcher's reserved codes (115-119) WITHOUT being
misclassified as a launcher failure, because launcher errors come only from the
status channel.

For untrusted code or dangerous external tools, future stages must use real
isolation (OS rlimits/cgroups, nsjail/firejail, containers, seccomp, network
namespaces). This remains a controlled execution boundary, not a jail. It runs
only explicit argv commands passed by the caller; it does not run ROS2, KiCad,
or colcon.
"""
from __future__ import annotations

import json
import os
import selectors
import signal
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Optional, Union

from backend.app.sandbox.limited_launcher import (
    STATUS_APPLY_FAILED,
    STATUS_BAD_ARGS,
    STATUS_BAD_POLICY,
    STATUS_EXEC_FAILED,
    STATUS_PROTOCOL_ERROR,
    STATUS_UNSUPPORTED,
)
from backend.app.sandbox.resource_policy import (
    ResourceLimits,
    resource_limits_supported,
)

# Bytes read per pipe wake-up in the capped streaming path.
_READ_CHUNK = 65536

# Absolute path to the standalone resource-limit launcher (Phase 11 Stage
# 9B-3B-1). Resolved once, beside this module, so it is reachable from an
# arbitrary caller-provided cwd under the minimal child environment.
_LAUNCHER_PATH = Path(__file__).resolve().parent / "limited_launcher.py"

# The exact set of launcher-status tokens the parent will accept from the
# dedicated status pipe (Stage 9B-3C-2). Each maps one-to-one to a launcher
# reserved exit code; any other payload fails closed (see ``_classify_status``).
# Deterministic fail-closed verdict for a malformed, unknown, duplicated, or
# oversized launcher-status payload. The handshake is authoritative, so an
# uninterpretable payload is itself a (protocol) launcher error rather than
# being silently treated as success. The launcher emits this exact token
# (``STATUS_PROTOCOL_ERROR``) when it cannot make the status fd close-on-exec,
# so the parent accepts it as an explicit, authoritative launcher error too.
LAUNCHER_STATUS_PROTOCOL_ERROR = STATUS_PROTOCOL_ERROR

_KNOWN_LAUNCHER_STATUS = frozenset(
    {
        STATUS_BAD_ARGS,
        STATUS_BAD_POLICY,
        STATUS_UNSUPPORTED,
        STATUS_APPLY_FAILED,
        STATUS_EXEC_FAILED,
        STATUS_PROTOCOL_ERROR,
    }
)

# Upper bound on bytes read from the status pipe. The longest valid token is 27
# bytes; anything beyond this bound is treated as an oversized payload and fails
# closed. The launcher only ever writes one tiny token (well under PIPE_BUF), so
# this never truncates a legitimate message.
_STATUS_MAX_BYTES = 64


class ResourceLimitsUnsupportedError(RuntimeError):
    """Raised when a requested resource policy cannot be enforced."""


def _classify_resource_outcome(
    returncode: Optional[int],
) -> tuple[bool, Optional[str]]:
    """Classify a child's exit into ``(exceeded, kind)`` from RELIABLE signals.

    - ``-SIGXCPU`` -> a CPU resource limit was hit -> ``(True, "cpu")``.
    - ``-SIGXFSZ`` -> a file-size limit was hit -> ``(True, "file_size")``.

    Everything else stays unclassified ``(False, None)``. In particular
    ``SIGKILL`` (could be our own timeout/output-cap kill, an OOM kill, or a
    hard CPU limit after an ignored ``SIGXCPU``), ``SIGSEGV``, exit code ``1``,
    ``EFBIG`` surfacing as a write error instead of ``SIGXFSZ``, NOFILE-driven
    failures, and generic nonzero exits are NOT attributed to a resource limit,
    because the OS evidence does not distinguish them.

    Launcher errors are NOT inferred here: a target can itself exit with one of
    the launcher's reserved codes (115-119), so launcher failures are reported
    only through the dedicated status channel (see ``_LauncherStatusChannel``).
    """
    if returncode == -signal.SIGXCPU:
        return True, "cpu"
    if returncode == -signal.SIGXFSZ:
        return True, "file_size"
    return False, None


def _classify_status(raw: Optional[bytes]) -> Optional[str]:
    """Map a raw status-pipe payload to a launcher-error name, failing closed.

    - ``None`` (read error) -> protocol error.
    - empty (EOF, no payload) -> ``None`` (successful exec; no launcher error).
    - exactly one known ASCII token -> that token.
    - malformed / unknown / oversized -> ``LAUNCHER_STATUS_PROTOCOL_ERROR``.
    """
    if raw is None:
        return LAUNCHER_STATUS_PROTOCOL_ERROR
    if len(raw) == 0:
        return None
    if len(raw) > _STATUS_MAX_BYTES:
        return LAUNCHER_STATUS_PROTOCOL_ERROR
    try:
        text = raw.decode("ascii")
    except UnicodeDecodeError:
        return LAUNCHER_STATUS_PROTOCOL_ERROR
    if text in _KNOWN_LAUNCHER_STATUS:
        return text
    return LAUNCHER_STATUS_PROTOCOL_ERROR


class _LauncherStatusChannel:
    """A dedicated POSIX exec-status pipe between the parent and the launcher.

    Created ONLY when resource launcher wrapping is active. The write end is
    handed to ``limited_launcher.py`` via ``--status-fd`` and ``pass_fds``; the
    parent closes its own copy of the write end immediately after spawning and,
    after the child is reaped, reads a single bounded token from the read end:

    - a known token  -> that launcher error,
    - EOF / no bytes -> ``None`` (successful exec, no launcher error),
    - anything else  -> ``LAUNCHER_STATUS_PROTOCOL_ERROR`` (fail closed).

    ``close()`` closes both descriptors and is idempotent, so callers can close
    in a ``finally`` on every success/timeout/output-cap/spawn-failure path.
    """

    def __init__(self) -> None:
        # ``os.pipe`` fds are close-on-exec by default, so the parent's copies
        # never leak into the child; ``pass_fds`` re-enables inheritance of the
        # write end for the launcher only.
        self.read_fd: Optional[int] = None
        self.write_fd: Optional[int] = None
        self.read_fd, self.write_fd = os.pipe()

    @property
    def pass_fds(self) -> tuple[int, ...]:
        return () if self.write_fd is None else (self.write_fd,)

    def close_write_end(self) -> None:
        """Close the parent's copy of the write end (call right after spawn)."""
        if self.write_fd is not None:
            try:
                os.close(self.write_fd)
            except OSError:
                pass
            self.write_fd = None

    def read_status(self) -> Optional[str]:
        """Read a bounded payload and classify it into a launcher-error name."""
        if self.read_fd is None:
            return None
        chunks: list[bytes] = []
        total = 0
        cap = _STATUS_MAX_BYTES + 1  # one extra byte distinguishes oversized
        while total < cap:
            try:
                chunk = os.read(self.read_fd, cap - total)
            except OSError:
                return _classify_status(None)
            if not chunk:
                break
            chunks.append(chunk)
            total += len(chunk)
        return _classify_status(b"".join(chunks))

    def close(self) -> None:
        self.close_write_end()
        if self.read_fd is not None:
            try:
                os.close(self.read_fd)
            except OSError:
                pass
            self.read_fd = None


def _with_status_fd(base_spawn_argv: list[str], write_fd: int) -> list[str]:
    """Insert ``--status-fd <write_fd>`` ahead of the launcher's ``--policy-json``.

    ``base_spawn_argv`` is ``[python, launcher_path, "--policy-json", ...]``;
    the status flag is placed right after the launcher path so it precedes the
    policy, matching the launcher's optional-leading-flag parsing.
    """
    return [
        base_spawn_argv[0],
        base_spawn_argv[1],
        "--status-fd",
        str(write_fd),
        *base_spawn_argv[2:],
    ]


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
    # Stage 9B-2 capture-time output cap (defaults preserve uncapped behavior).
    # ``output_limit_bytes`` echoes the configured per-stream cap (None when
    # uncapped). ``output_limit_exceeded`` is True iff a stream overflowed the
    # cap and the process group was killed. The ``*_capture_truncated`` flags
    # describe execution-time byte truncation and are distinct from the
    # report-level character truncation in ``command_report.py``.
    output_limit_bytes: Optional[int] = None
    output_limit_exceeded: bool = False
    stdout_capture_truncated: bool = False
    stderr_capture_truncated: bool = False
    # Stage 9B-3C-1/9B-3C-2 resource-limit / launcher-outcome classification.
    # ``resource_limits_requested`` echoes ``ResourceLimits.to_dict()`` when a
    # non-empty policy caused launcher wrapping (else None).
    # ``resource_limits_applied`` records the parent's known action (wrapping
    # happened), NOT proof every requested limit succeeded.
    # ``resource_limit_exceeded``/``resource_limit_kind`` are set only from
    # reliable signals (SIGXCPU/SIGXFSZ). ``launcher_error`` is AUTHORITATIVE: it
    # comes from the launcher's dedicated out-of-band status pipe, never from the
    # process return code, so a target that exits 115-119 is not misattributed to
    # the launcher (see ``_LauncherStatusChannel`` / ``_classify_status``).
    resource_limits_requested: Optional[dict[str, Optional[int]]] = None
    resource_limits_applied: bool = False
    resource_limit_exceeded: bool = False
    resource_limit_kind: Optional[str] = None
    launcher_error: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        """Deterministic dict with a fixed key order and a fresh command list."""
        return {
            "command": list(self.command),
            "returncode": self.returncode,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "timed_out": self.timed_out,
            "timeout_seconds": self.timeout_seconds,
            "output_limit_bytes": self.output_limit_bytes,
            "output_limit_exceeded": self.output_limit_exceeded,
            "stdout_capture_truncated": self.stdout_capture_truncated,
            "stderr_capture_truncated": self.stderr_capture_truncated,
            "resource_limits_requested": (
                dict(self.resource_limits_requested)
                if self.resource_limits_requested is not None
                else None
            ),
            "resource_limits_applied": self.resource_limits_applied,
            "resource_limit_exceeded": self.resource_limit_exceeded,
            "resource_limit_kind": self.resource_limit_kind,
            "launcher_error": self.launcher_error,
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


def _validate_max_output_bytes(value: Any) -> Optional[int]:
    """Validate the optional per-stream output cap before any process spawns.

    ``None`` means uncapped (current behavior). Otherwise the value must be a
    non-negative integer; ``0`` is valid (the first produced byte overflows).
    ``bool`` is rejected even though it is an ``int`` subclass.
    """
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(
            f"max_output_bytes must be None or a non-negative integer, got {type(value)!r}."
        )
    if value < 0:
        raise ValueError("max_output_bytes must be None or a non-negative integer.")
    return value


def _effective_env(env: Optional[dict[str, str]]) -> dict[str, str]:
    """Build the child environment: minimal defaults, caller keys override."""
    effective = dict(_DEFAULT_ENV)
    if env:
        effective.update(env)
    return effective


def _make_result(
    *,
    argv: list[str],
    returncode: Optional[int],
    stdout: str,
    stderr: str,
    timed_out: bool,
    timeout: float,
    output_limit_bytes: Optional[int],
    output_limit_exceeded: bool,
    stdout_capture_truncated: bool,
    stderr_capture_truncated: bool,
    resource_limits_requested: Optional[dict[str, Optional[int]]],
    resource_limits_applied: bool,
    resource_limit_exceeded: bool,
    resource_limit_kind: Optional[str],
    launcher_error: Optional[str],
) -> "CommandResult":
    """Single CommandResult factory so capped/uncapped paths cannot drift."""
    return CommandResult(
        command=argv,
        returncode=returncode,
        stdout=stdout,
        stderr=stderr,
        timed_out=timed_out,
        timeout_seconds=float(timeout),
        output_limit_bytes=output_limit_bytes,
        output_limit_exceeded=output_limit_exceeded,
        stdout_capture_truncated=stdout_capture_truncated,
        stderr_capture_truncated=stderr_capture_truncated,
        resource_limits_requested=resource_limits_requested,
        resource_limits_applied=resource_limits_applied,
        resource_limit_exceeded=resource_limit_exceeded,
        resource_limit_kind=resource_limit_kind,
        launcher_error=launcher_error,
    )


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
    max_output_bytes: Optional[int] = None,
    resource_limits: Optional[ResourceLimits] = None,
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

    ``max_output_bytes`` is an opt-in capture-time output cap (default ``None`` =
    uncapped, preserving the ``subprocess.run`` path). When configured, a
    streaming ``subprocess.Popen`` path retains at most ``max_output_bytes`` per
    stream and kills the process group once a stream overflows. Output-limit
    exceedance is reported separately from timeout (see the ``output_limit_*``
    and ``*_capture_truncated`` fields on ``CommandResult``).

    ``resource_limits`` is an opt-in OS resource policy (default ``None`` = no
    limits, preserving prior behavior). ``None`` and an empty policy never wrap.
    A non-empty policy on a Linux platform wraps the original command with the
    standalone launcher (``limited_launcher.py``), which applies the limits to
    itself and then ``execvp``-replaces itself with the real command — so the
    tool inherits the limits in the same PID/session group and every existing
    control (allowlist, stdin, env, cwd, timeout, output cap, process-group
    termination) still governs it. A non-empty policy on an unsupported platform
    raises ``ResourceLimitsUnsupportedError`` before spawning; requested limits
    are never silently skipped. The original caller command — not the launcher
    wrapper — is always echoed in ``CommandResult.command``. Reliable
    resource-limit terminations (``SIGXCPU``/``SIGXFSZ``) are recorded in the
    ``resource_*`` fields (see ``_classify_resource_outcome``). Launcher failures
    are recorded in ``launcher_error`` AUTHORITATIVELY, via a dedicated
    out-of-band status pipe to the launcher (``--status-fd``), so a target that
    happens to exit with one of the launcher's reserved codes is never
    misclassified as a launcher failure.
    """
    argv = _validate_command(command)
    _check_allowed(argv, allowed_executables)
    max_output_bytes = _validate_max_output_bytes(max_output_bytes)
    base_spawn_argv, wrapped = _wrap_with_resource_launcher(argv, resource_limits)
    requested = resource_limits.to_dict() if wrapped else None
    effective_env = _effective_env(env)

    if max_output_bytes is None:
        return _run_uncapped(
            base_spawn_argv,
            wrapped=wrapped,
            result_argv=argv,
            cwd=cwd,
            timeout=timeout,
            env=effective_env,
            resource_limits_requested=requested,
            resource_limits_applied=wrapped,
        )
    return _run_capped(
        base_spawn_argv,
        wrapped=wrapped,
        result_argv=argv,
        cwd=cwd,
        timeout=timeout,
        env=effective_env,
        max_output_bytes=max_output_bytes,
        resource_limits_requested=requested,
        resource_limits_applied=wrapped,
    )


def _wrap_with_resource_launcher(
    argv: list[str], resource_limits: Optional[ResourceLimits]
) -> tuple[list[str], bool]:
    """Return ``(spawn_argv, wrapped)``: the argv to spawn and whether wrapped.

    ``None`` or an empty policy returns ``(fresh copy of argv, False)`` (no
    wrapping, no platform requirement). A non-empty policy on an unsupported
    platform raises ``ResourceLimitsUnsupportedError`` before any spawn — the
    policy is never silently skipped. Otherwise the original argv is wrapped with
    ``sys.executable <abs launcher> --policy-json <json> -- <argv...>`` and
    ``wrapped`` is True; the launcher enforces (and fails closed on) the policy,
    including deferred fields, so the parent does not duplicate that field list.
    """
    if resource_limits is None:
        return list(argv), False
    if not isinstance(resource_limits, ResourceLimits):
        raise TypeError(
            f"resource_limits must be None or a ResourceLimits, "
            f"got {type(resource_limits)!r}."
        )
    if resource_limits.is_empty():
        return list(argv), False
    if not resource_limits_supported():
        raise ResourceLimitsUnsupportedError(
            "resource limits are not supported on this platform; "
            "refusing to silently skip the requested policy."
        )
    encoded_policy = json.dumps(resource_limits.to_dict(), separators=(",", ":"))
    spawn_argv = [
        sys.executable,
        str(_LAUNCHER_PATH),
        "--policy-json",
        encoded_policy,
        "--",
        *argv,
    ]
    return spawn_argv, True


def _run_uncapped(
    base_spawn_argv: list[str],
    *,
    wrapped: bool,
    result_argv: list[str],
    cwd: Union[str, Path],
    timeout: float,
    env: dict[str, str],
    resource_limits_requested: Optional[dict[str, Optional[int]]],
    resource_limits_applied: bool,
) -> CommandResult:
    """Uncapped path with full in-memory capture.

    ``base_spawn_argv`` is the argv to execute (the launcher wrapper when
    ``wrapped``); ``result_argv`` is the original caller command echoed in the
    result.

    Unwrapped commands keep the legacy ``subprocess.run`` implementation. Wrapped
    commands use a ``subprocess.Popen`` + ``communicate`` path so the parent's
    copy of the status write fd is closed IMMEDIATELY after spawning (not after
    the child completes), satisfying the handshake's descriptor lifecycle.
    """
    if not wrapped:
        return _run_uncapped_unwrapped(
            base_spawn_argv,
            result_argv=result_argv,
            cwd=cwd,
            timeout=timeout,
            env=env,
            resource_limits_requested=resource_limits_requested,
            resource_limits_applied=resource_limits_applied,
        )

    channel = _LauncherStatusChannel()
    spawn_argv = _with_status_fd(base_spawn_argv, channel.write_fd)
    pass_fds = channel.pass_fds
    try:
        proc = subprocess.Popen(  # noqa: S603 - argv-only, shell=False, confined here
            spawn_argv,
            cwd=str(cwd),
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            start_new_session=True,
            pass_fds=pass_fds,
        )
        # Close the parent's copy of the status write end immediately after the
        # spawn succeeds, so only the launcher holds it and the read end will
        # see EOF once the child is gone.
        channel.close_write_end()

        try:
            stdout, stderr = proc.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            # ``start_new_session=True`` made the child a process-group leader;
            # kill the whole group, then drain/reap via a second communicate().
            _best_effort_kill_group(proc.pid)
            stdout, stderr = proc.communicate()
            # Timeout is the primary outcome; invent no launcher error (the child
            # was killed by us, not reported through the status channel).
            return _make_result(
                argv=result_argv,
                returncode=None,
                stdout=_as_text(stdout),
                stderr=_as_text(stderr),
                timed_out=True,
                timeout=timeout,
                output_limit_bytes=None,
                output_limit_exceeded=False,
                stdout_capture_truncated=False,
                stderr_capture_truncated=False,
                resource_limits_requested=resource_limits_requested,
                resource_limits_applied=resource_limits_applied,
                resource_limit_exceeded=False,
                resource_limit_kind=None,
                launcher_error=None,
            )

        # The child has exited; read the launcher's authoritative outcome.
        launcher_error = channel.read_status()
        exceeded, kind = _classify_resource_outcome(proc.returncode)
        return _make_result(
            argv=result_argv,
            returncode=proc.returncode,
            stdout=_as_text(stdout),
            stderr=_as_text(stderr),
            timed_out=False,
            timeout=timeout,
            output_limit_bytes=None,
            output_limit_exceeded=False,
            stdout_capture_truncated=False,
            stderr_capture_truncated=False,
            resource_limits_requested=resource_limits_requested,
            resource_limits_applied=resource_limits_applied,
            resource_limit_exceeded=exceeded,
            resource_limit_kind=kind,
            launcher_error=launcher_error,
        )
    finally:
        channel.close()


def _run_uncapped_unwrapped(
    spawn_argv: list[str],
    *,
    result_argv: list[str],
    cwd: Union[str, Path],
    timeout: float,
    env: dict[str, str],
    resource_limits_requested: Optional[dict[str, Optional[int]]],
    resource_limits_applied: bool,
) -> CommandResult:
    """Legacy uncapped path: ``subprocess.run`` with full in-memory capture.

    Used only when no resource launcher wrapping is active, so there is no status
    pipe to manage and the original behavior is preserved exactly.
    """
    try:
        completed = subprocess.run(
            spawn_argv,
            cwd=str(cwd),
            env=env,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
            start_new_session=True,
        )
        exceeded, kind = _classify_resource_outcome(completed.returncode)
        return _make_result(
            argv=result_argv,
            returncode=completed.returncode,
            stdout=_as_text(completed.stdout),
            stderr=_as_text(completed.stderr),
            timed_out=False,
            timeout=timeout,
            output_limit_bytes=None,
            output_limit_exceeded=False,
            stdout_capture_truncated=False,
            stderr_capture_truncated=False,
            resource_limits_requested=resource_limits_requested,
            resource_limits_applied=resource_limits_applied,
            resource_limit_exceeded=exceeded,
            resource_limit_kind=kind,
            launcher_error=None,
        )
    except subprocess.TimeoutExpired as error:
        # ``subprocess.run`` already kills the direct child on timeout. With
        # ``start_new_session=True`` the child leads its own process group, so
        # best-effort terminate the whole group to reduce grandchild leakage.
        _best_effort_kill_group(getattr(error, "pid", None))
        return _make_result(
            argv=result_argv,
            returncode=None,
            stdout=_as_text(error.stdout),
            stderr=_as_text(error.stderr),
            timed_out=True,
            timeout=timeout,
            output_limit_bytes=None,
            output_limit_exceeded=False,
            stdout_capture_truncated=False,
            stderr_capture_truncated=False,
            resource_limits_requested=resource_limits_requested,
            resource_limits_applied=resource_limits_applied,
            resource_limit_exceeded=False,
            resource_limit_kind=None,
            launcher_error=None,
        )


def _run_capped(
    base_spawn_argv: list[str],
    *,
    wrapped: bool,
    result_argv: list[str],
    cwd: Union[str, Path],
    timeout: float,
    env: dict[str, str],
    max_output_bytes: int,
    resource_limits_requested: Optional[dict[str, Optional[int]]],
    resource_limits_applied: bool,
) -> CommandResult:
    """Streaming ``Popen`` path with a per-stream capture-time output cap.

    ``base_spawn_argv`` is the argv to execute (the launcher wrapper when
    ``wrapped``); ``result_argv`` is the original caller command echoed in the
    result. When wrapped, a dedicated status pipe carries the launcher's
    authoritative outcome; the parent closes its write end immediately after
    spawning and closes all status descriptors on every return path.

    stdout and stderr are drained concurrently with a selector over the raw
    pipe fds, so neither stream can deadlock the other. Each stream retains at
    most ``max_output_bytes``; reaching exactly the limit is NOT exceedance —
    the stream's ``*_capture_truncated`` flag is set only once at least one
    additional byte beyond the retained limit is observed and discarded. On the
    first overflow the process group is SIGKILLed and remaining output is
    drained-and-discarded until both pipes close. Timeout is enforced with a
    monotonic deadline and reported separately via ``timed_out``.
    """
    channel = _LauncherStatusChannel() if wrapped else None
    spawn_argv = base_spawn_argv
    pass_fds: tuple[int, ...] = ()
    if channel is not None:
        spawn_argv = _with_status_fd(base_spawn_argv, channel.write_fd)
        pass_fds = channel.pass_fds
    try:
        deadline = time.monotonic() + float(timeout)
        proc = subprocess.Popen(  # noqa: S603 - argv-only, shell=False, confined here
            spawn_argv,
            cwd=str(cwd),
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=True,
            pass_fds=pass_fds,
        )
        # Close the parent's copy of the status write end immediately after
        # spawning, so only the launcher holds it and the read end will see EOF.
        if channel is not None:
            channel.close_write_end()

        buffers = {"stdout": bytearray(), "stderr": bytearray()}
        truncated = {"stdout": False, "stderr": False}
        output_limit_exceeded = False
        timed_out = False
        killed = False

        selector = selectors.DefaultSelector()
        try:
            selector.register(proc.stdout, selectors.EVENT_READ, "stdout")
            selector.register(proc.stderr, selectors.EVENT_READ, "stderr")
            open_streams = 2

            while open_streams > 0:
                if not killed:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        timed_out = True
                        _best_effort_kill_group(proc.pid)
                        killed = True

                # Once killed, poll briefly so EOF is observed promptly without
                # spinning; otherwise block until the deadline.
                select_timeout = 0.1 if killed else max(0.0, deadline - time.monotonic())
                events = selector.select(select_timeout)
                if not events:
                    continue

                for key, _mask in events:
                    stream = key.data
                    data = os.read(key.fd, _READ_CHUNK)
                    if not data:
                        selector.unregister(key.fileobj)
                        key.fileobj.close()
                        open_streams -= 1
                        continue

                    buf = buffers[stream]
                    space = max_output_bytes - len(buf)
                    if space > 0:
                        buf.extend(data[:space])
                        overflow = len(data) > space
                    else:
                        overflow = True  # buffer already at cap; any byte overflows

                    if overflow and not truncated[stream]:
                        truncated[stream] = True
                    if overflow and not output_limit_exceeded:
                        output_limit_exceeded = True
                        if not killed:
                            _best_effort_kill_group(proc.pid)
                            killed = True
        finally:
            selector.close()
            for pipe in (proc.stdout, proc.stderr):
                try:
                    if pipe is not None and not pipe.closed:
                        pipe.close()
                except OSError:
                    pass

        # Reap. If the process is still alive (e.g. it closed its pipes but kept
        # running), bound the wait by the remaining deadline and treat overrun
        # as a timeout — keeping timeout enforcement honest without storing
        # elapsed time.
        if not killed:
            try:
                proc.wait(timeout=max(0.0, deadline - time.monotonic()))
            except subprocess.TimeoutExpired:
                timed_out = True
                _best_effort_kill_group(proc.pid)
        proc.wait()

        returncode = None if timed_out else proc.returncode

        # Classify from the final return code. Our own kills (timeout -> None,
        # output-cap -> SIGKILL) are not SIGXCPU/SIGXFSZ, so the classifier
        # returns clear defaults and never mislabels a parent kill as a resource
        # limit; report precedence keeps timeout/output-limit primary regardless.
        exceeded, kind = _classify_resource_outcome(returncode)

        # The launcher's authoritative outcome (None when unwrapped). On timeout
        # or output-cap kill the target's exec already closed the status fd, so
        # the read yields EOF -> None and no launcher error is invented.
        launcher_error = channel.read_status() if channel is not None else None

        return _make_result(
            argv=result_argv,
            returncode=returncode,
            stdout=_as_text(bytes(buffers["stdout"])),
            stderr=_as_text(bytes(buffers["stderr"])),
            timed_out=timed_out,
            timeout=timeout,
            output_limit_bytes=max_output_bytes,
            output_limit_exceeded=output_limit_exceeded,
            stdout_capture_truncated=truncated["stdout"],
            stderr_capture_truncated=truncated["stderr"],
            resource_limits_requested=resource_limits_requested,
            resource_limits_applied=resource_limits_applied,
            resource_limit_exceeded=exceeded,
            resource_limit_kind=kind,
            launcher_error=launcher_error,
        )
    finally:
        if channel is not None:
            channel.close()


def _best_effort_kill_group(pid: Optional[int]) -> None:
    """Try to SIGKILL the child's process group; never raise."""
    if not pid:
        return
    try:
        os.killpg(os.getpgid(pid), signal.SIGKILL)
    except (ProcessLookupError, PermissionError, OSError):
        # The child is already gone or the group is unavailable — nothing to do.
        pass
