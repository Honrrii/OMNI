"""
OMNI Sandbox — CommandResult -> SandboxReport bridge (Phase 11 Stage 6).

Pure transform that interprets a low-level ``CommandResult`` (from
``backend/app/sandbox/execution.py``) as a single-check ``SandboxReport``, so a
command run can flow through the existing sandbox finding projection and export
envelope helpers.

This helper runs NOTHING. It does not import or call ``subprocess`` — it only
consumes an already-produced ``CommandResult``. No file I/O, no model calls, no
mission/export integration, no mutation of the input. It adds no isolation and
is not a security boundary; see ``execution.py`` for the honest limitations of
the underlying command runner.
"""
from __future__ import annotations

from dataclasses import asdict, is_dataclass
from typing import Any, Optional, Union

from backend.app.sandbox.execution import CommandResult
from backend.app.sandbox.report import SandboxCheckResult, SandboxReport


def _as_result_dict(
    result: Union[CommandResult, dict[str, Any]],
) -> dict[str, Any]:
    """Coerce a CommandResult dataclass or a result dict into a plain dict."""
    if is_dataclass(result) and not isinstance(result, type):
        return asdict(result)
    if isinstance(result, dict):
        return dict(result)
    raise TypeError(f"unsupported result type for command report: {type(result)!r}")


def _truncate(text: str, max_output_chars: Optional[int]) -> tuple[str, bool]:
    """Deterministically truncate ``text`` to ``max_output_chars``.

    Returns the (possibly truncated) text and a flag indicating whether
    truncation occurred. ``None`` means no truncation. Negative limits are
    rejected by the caller before this is reached.
    """
    if max_output_chars is None:
        return text, False
    if len(text) <= max_output_chars:
        return text, False
    dropped = len(text) - max_output_chars
    return f"{text[:max_output_chars]}…[truncated {dropped} chars]", True


def command_result_to_sandbox_report(
    result: Union[CommandResult, dict[str, Any]],
    *,
    sandbox: str = "command",
    check_id: str = "command.exit",
    max_output_chars: Optional[int] = None,
) -> SandboxReport:
    """Interpret a ``CommandResult`` as a one-check ``SandboxReport``.

    Outcome mapping:
    - success (returncode == 0, not timed out) -> ok=True, severity "info",
      report status "passed".
    - nonzero exit (not timed out) -> ok=False, severity "warning", status
      "completed".
    - timeout -> ok=False, severity "error", status "completed".

    Deterministic and side-effect free. ``max_output_chars`` (default None)
    optionally truncates stdout/stderr in the metadata with a fixed marker;
    original lengths are always preserved as ``stdout_len`` / ``stderr_len``.
    A negative ``max_output_chars`` is rejected.
    """
    if max_output_chars is not None and max_output_chars < 0:
        raise ValueError("max_output_chars must be None or a non-negative integer.")

    data = _as_result_dict(result)

    command = list(data.get("command") or [])
    returncode = data.get("returncode")
    timed_out = bool(data.get("timed_out"))
    timeout_seconds = data.get("timeout_seconds")
    stdout = data.get("stdout") or ""
    stderr = data.get("stderr") or ""

    if timed_out:
        ok = False
        severity = "error"
        status = "completed"
        message = "command timed out"
        expected, actual = "0", "timeout"
    elif returncode == 0:
        ok = True
        severity = "info"
        status = "passed"
        message = "command completed successfully"
        expected, actual = "0", "0"
    else:
        ok = False
        severity = "warning"
        status = "completed"
        message = "command exited with nonzero status"
        expected, actual = "0", str(returncode)

    out_text, out_truncated = _truncate(stdout, max_output_chars)
    err_text, err_truncated = _truncate(stderr, max_output_chars)

    check = SandboxCheckResult(
        check_id=check_id,
        ok=ok,
        severity=severity,
        message=message,
        expected=expected,
        actual=actual,
        file=None,
        metadata={
            "command": command,
            "returncode": returncode,
            "timed_out": timed_out,
            "timeout_seconds": timeout_seconds,
            "stdout": out_text,
            "stderr": err_text,
            "stdout_len": len(stdout),
            "stderr_len": len(stderr),
            "stdout_truncated": out_truncated,
            "stderr_truncated": err_truncated,
        },
    )

    return SandboxReport(sandbox=sandbox, status=status, checks=[check])
