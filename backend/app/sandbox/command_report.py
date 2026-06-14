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

    Outcome mapping (precedence: timeout > output-limit > launcher error >
    resource-limit termination > success > nonzero):
    - timeout -> ok=False, severity "error", status "completed".
    - output limit exceeded -> ok=False, severity "error", status "completed",
      actual "output_limit_exceeded" (Stage 9B-2 capture-time cap).
    - launcher error -> ok=False, severity "error", status "completed",
      actual "launcher_error:<kind>" (Stage 9B-3C-1; heuristic — a target can
      itself exit the launcher's reserved codes).
    - resource-limit termination -> ok=False, severity "error", status
      "completed", actual "resource_limit:<kind>" (reliable SIGXCPU/SIGXFSZ).
    - success (returncode == 0) -> ok=True, severity "info", status "passed".
    - nonzero exit -> ok=False, severity "warning", status "completed" (an
      ambiguous nonzero exit under a policy is NOT claimed to be a resource
      limit).

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
    output_limit_bytes = data.get("output_limit_bytes")
    output_limit_exceeded = bool(data.get("output_limit_exceeded"))
    stdout_capture_truncated = bool(data.get("stdout_capture_truncated"))
    stderr_capture_truncated = bool(data.get("stderr_capture_truncated"))
    resource_limits_requested = data.get("resource_limits_requested")
    resource_limits_applied = bool(data.get("resource_limits_applied"))
    resource_limit_exceeded = bool(data.get("resource_limit_exceeded"))
    resource_limit_kind = data.get("resource_limit_kind")
    launcher_error = data.get("launcher_error")

    # Outcome precedence: timeout > output-limit exceedance > launcher setup
    # failure > reliably-identified resource-limit termination > success >
    # ordinary nonzero exit. Parent-initiated kills (timeout, output cap) win
    # because the parent KNOWS it caused them. A launcher error and a resource
    # termination are mutually exclusive by return-code sign (positive reserved
    # code vs negative signal), so their relative order is only nominal.
    if timed_out:
        ok = False
        severity = "error"
        status = "completed"
        message = "command timed out"
        expected, actual = "0", "timeout"
    elif output_limit_exceeded:
        ok = False
        severity = "error"
        status = "completed"
        message = "command output limit exceeded"
        expected, actual = "0", "output_limit_exceeded"
    elif launcher_error:
        ok = False
        severity = "error"
        status = "completed"
        message = f"resource launcher error: {launcher_error}"
        expected, actual = "0", f"launcher_error:{launcher_error}"
    elif resource_limit_exceeded:
        ok = False
        severity = "error"
        status = "completed"
        message = f"command exceeded {resource_limit_kind} resource limit"
        expected, actual = "0", f"resource_limit:{resource_limit_kind}"
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
            # Report-level character truncation (post-capture, Stage 6).
            "stdout_truncated": out_truncated,
            "stderr_truncated": err_truncated,
            # Execution-time byte truncation (Stage 9B-2). Distinct from the
            # character-level *_truncated flags above.
            "output_limit_bytes": output_limit_bytes,
            "output_limit_exceeded": output_limit_exceeded,
            "stdout_capture_truncated": stdout_capture_truncated,
            "stderr_capture_truncated": stderr_capture_truncated,
            # Resource-limit / launcher-outcome classification (Stage 9B-3C-1).
            # ``launcher_error`` is heuristic (a target can itself exit 115-119).
            "resource_limits_requested": resource_limits_requested,
            "resource_limits_applied": resource_limits_applied,
            "resource_limit_exceeded": resource_limit_exceeded,
            "resource_limit_kind": resource_limit_kind,
            "launcher_error": launcher_error,
        },
    )

    return SandboxReport(sandbox=sandbox, status=status, checks=[check])
