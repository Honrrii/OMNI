"""Bubblewrap isolation composed with OMNI's existing bounded process runner."""
from __future__ import annotations

import json
import sys
import time
from dataclasses import dataclass
from pathlib import Path

from backend.app.sandbox.execution import run_command
from omni.testcube.collector_models import CollectorPolicy, CommandSpec, canonical_bytes


class CollectionError(RuntimeError):
    """Collector infrastructure is untrustworthy; do not invoke the arbiter."""


def write_new(path: Path, data: bytes) -> None:
    """Exclusive, durable artifact publication. Never follows a destination link."""
    import os

    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "wb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)


@dataclass(frozen=True)
class ObservedCommand:
    argv: tuple[str, ...]
    exit_code: int | None
    outcome: str
    duration_ns: int
    evidence_ref: str


def isolated_argv(worktree: Path, policy: CollectorPolicy, command: CommandSpec) -> list[str]:
    # No host root, source repository, artifacts, sockets, or Git metadata are
    # exposed. /work is immutable; all command writes live in ephemeral tmpfs.
    return [
        "/usr/bin/bwrap", "--unshare-all", "--unshare-user", "--unshare-net",
        "--unshare-pid", "--die-with-parent", "--new-session", "--cap-drop", "ALL",
        "--ro-bind", "/usr", "/usr",
        "--symlink", "usr/bin", "/bin", "--symlink", "usr/lib", "/lib",
        "--symlink", "usr/lib64", "/lib64",
        "--ro-bind", policy.runtime_root, "/runtime",
        "--ro-bind", str(worktree), "/work",
        "--ro-bind", str(Path(__file__).with_name("command_bootstrap.py")), "/bootstrap.py",
        "--tmpfs", "/work/.git", "--remount-ro", "/work/.git",
        "--proc", "/proc", "--dev", "/dev", "--tmpfs", "/tmp",
        "--tmpfs", "/scratch", "--chdir", "/work", "--clearenv",
        "--setenv", "PATH", "/runtime/bin:/usr/bin:/bin",
        "--setenv", "LANG", "C.UTF-8", "--setenv", "LC_ALL", "C.UTF-8",
        "--setenv", "TZ", "UTC", "--setenv", "PYTHONHASHSEED", "0",
        "--setenv", "PYTHONDONTWRITEBYTECODE", "1",
        "--setenv", "PYTHONNOUSERSITE", "1",
        "--setenv", "PYTEST_DISABLE_PLUGIN_AUTOLOAD", "1",
        "--setenv", "TMPDIR", "/tmp",
    ]


def run_isolated(
    worktree: Path, policy: CollectorPolicy, command: CommandSpec,
    bundle: Path, artifact_prefix: str,
) -> ObservedCommand:
    argv = isolated_argv(worktree, policy, command)
    prefix = bundle / artifact_prefix
    def artifact(suffix: str) -> Path:
        return Path(str(prefix) + suffix)

    spec_path, status_path = artifact(".launch.json"), artifact(".status.jsonl")
    write_new(spec_path, canonical_bytes({"isolation_argv": argv, "target_argv": list(command.argv)}))
    launcher = Path(__file__).with_name("isolation_launcher.py")
    started = time.perf_counter_ns()
    try:
        result = run_command(
            [sys.executable, "-I", str(launcher), str(spec_path), str(status_path)],
            cwd=bundle, timeout=command.timeout_seconds,
            max_output_bytes=command.output_limit_bytes, resource_limits=policy.resource_limits,
        )
    except Exception as exc:
        raise CollectionError(f"process runner failed for {command.check_id}") from exc
    elapsed = time.perf_counter_ns() - started
    write_new(artifact(".stdout.txt"), result.stdout.encode("utf-8"))
    write_new(artifact(".stderr.txt"), result.stderr.encode("utf-8"))
    payload = result.to_dict() | {
        "requested_argv": list(command.argv), "cwd": "/work", "duration_ns": elapsed,
        "stdout_ref": str(artifact(".stdout.txt").relative_to(bundle)),
        "stderr_ref": str(artifact(".stderr.txt").relative_to(bundle)),
    }
    evidence_path = artifact(".json")
    write_new(evidence_path, canonical_bytes(payload))
    if result.launcher_error:
        raise CollectionError(f"resource launcher failed: {result.launcher_error}")
    try:
        if Path(str(status_path) + ".ready").read_bytes() != b"ready\n":
            raise ValueError("target exec handshake missing or failed")
        raw = status_path.read_bytes()
        if len(raw) > 16384:
            raise ValueError("oversized status")
        events = [json.loads(line) for line in raw.splitlines()]
        if not events or type(events[0].get("child-pid")) is not int:
            raise ValueError("missing sandbox identity")
        # Completion is reported only after successful exec, independently of
        # candidate stdout, and must agree with the process runner's exit code.
        if not result.timed_out and not result.output_limit_exceeded:
            if len(events) != 2 or type(events[1].get("exit-code")) is not int or events[1]["exit-code"] != result.returncode:
                raise ValueError("sandbox did not report successful setup/exec")
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise CollectionError("unverified Bubblewrap setup/exec") from exc
    outcome = "timeout" if result.timed_out else "error" if result.output_limit_exceeded else "completed"
    code = result.returncode if outcome == "completed" else None
    return ObservedCommand(command.argv, code, outcome, elapsed, str(evidence_path.relative_to(bundle)))
