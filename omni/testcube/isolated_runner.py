"""Bubblewrap isolation composed with OMNI's existing bounded process runner."""
from __future__ import annotations

import json
import os
import stat
import sys
import time
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from backend.app.sandbox.execution import run_command
from omni.testcube.collector_models import CollectorPolicy, CommandSpec, canonical_bytes

_PYVENV_LIMIT = 64 * 1024
_USR = PurePosixPath("/usr")
# Paths the sandbox itself creates or masks. A base installation at or beneath
# one would collide with, or be hidden by, those mounts.
_SANDBOX_PATHS = tuple(PurePosixPath(path) for path in (
    "/bin", "/lib", "/lib64", "/runtime", "/work", "/bootstrap.py",
    "/proc", "/dev", "/tmp", "/scratch",
))


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


def paths_overlap(first: Path, second: Path) -> bool:
    return first == second or first in second.parents or second in first.parents


def _pyvenv_home(raw: bytes) -> str:
    """The single ``home`` value, accepted only in the exact form ``venv`` writes.

    CPython startup and ``site`` parse pyvenv.cfg differently. Anything either
    could read differently (case, spacing, duplicates, unusual line breaks) is
    rejected rather than interpreted.
    """
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise CollectionError("runtime pyvenv.cfg is not UTF-8") from exc
    lines = text.split("\n")
    if "\0" in text or any(line.splitlines() not in ([], [line]) for line in lines):
        raise CollectionError("runtime pyvenv.cfg contains unsupported control characters")
    entries = [line for line in lines if "=" in line and line.partition("=")[0].strip().lower() == "home"]
    if len(entries) != 1:
        raise CollectionError("runtime pyvenv.cfg must contain exactly one home entry")
    home = entries[0][len("home = "):]
    if not entries[0].startswith("home = ") or not home or home != home.strip():
        raise CollectionError("runtime pyvenv.cfg home entry is malformed")
    return home


def _base_prefix_for_home(home: str) -> PurePosixPath:
    """Base prefix of a venv ``home``, which must be that installation's bin directory."""
    path = PurePosixPath(home)
    if not path.is_absolute() or str(path) != home or home.startswith("//") or ".." in path.parts:
        raise CollectionError("runtime Python home must be an absolute canonical path")
    if path.name != "bin":
        raise CollectionError("runtime Python home must be a POSIX bin directory")
    base = path.parent
    if base == PurePosixPath("/"):
        raise CollectionError("runtime Python base prefix must not be /")
    if any(base == reserved or reserved in base.parents for reserved in _SANDBOX_PATHS):
        raise CollectionError("runtime Python base prefix collides with a sandbox path")
    return base


def runtime_base_prefix(runtime_root: str) -> str | None:
    """Base Python installation a trusted virtualenv needs outside ``/usr``.

    Returns None when the base is already under the ``/usr`` mount, otherwise the
    one canonical prefix to expose read-only at its own path. It is derived from
    the virtualenv's own pyvenv.cfg, never by following the interpreter symlink.
    """
    runtime = Path(runtime_root)
    try:
        if not runtime.is_absolute() or runtime.resolve(strict=True) != runtime:
            raise CollectionError("runtime_root must be canonical, not a mutable symlink alias")
        fd = os.open(runtime / "pyvenv.cfg", os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        try:
            info = os.fstat(fd)
            if (not stat.S_ISREG(info.st_mode) or info.st_size > _PYVENV_LIMIT or
                    info.st_uid not in (0, os.geteuid()) or info.st_mode & 0o022):
                raise CollectionError("runtime pyvenv.cfg must be a bounded regular file owned by "
                                      "the operator or root and not group/other writable")
            raw = os.read(fd, _PYVENV_LIMIT + 1)
        finally:
            os.close(fd)
        if len(raw) > _PYVENV_LIMIT:
            raise CollectionError("runtime pyvenv.cfg exceeds its size limit")
        home = _pyvenv_home(raw)
        base = _base_prefix_for_home(home)
        if Path(home).resolve(strict=True) != Path(home) or not Path(home).is_dir():
            raise CollectionError("runtime Python home must be an existing directory without symlink aliases")
        interpreter = (runtime / "bin/python").resolve(strict=True)
        if not any(root in interpreter.parents for root in (runtime, Path(_USR), Path(base))):
            raise CollectionError("runtime interpreter must resolve inside the virtualenv, /usr, or its base prefix")
    except CollectionError:
        raise
    except (OSError, RuntimeError, ValueError) as exc:
        raise CollectionError(f"cannot validate runtime Python base: {type(exc).__name__}") from exc
    return None if base == _USR or _USR in base.parents else str(base)


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
    # A virtualenv whose base Python lives outside /usr cannot start without that
    # installation, so exactly its canonical prefix is added read-only.
    base = runtime_base_prefix(policy.runtime_root)
    base_mount = [] if base is None else ["--ro-bind", base, base]
    return [
        "/usr/bin/bwrap", "--unshare-all", "--unshare-user", "--unshare-net",
        "--unshare-pid", "--die-with-parent", "--new-session", "--cap-drop", "ALL",
        "--ro-bind", "/usr", "/usr", *base_mount,
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
        raise CollectionError(
            f"unverified Bubblewrap setup/exec: {type(exc).__name__}: {exc}"
        ) from exc
    outcome = "timeout" if result.timed_out else "error" if result.output_limit_exceeded else "completed"
    code = result.returncode if outcome == "completed" else None
    return ObservedCommand(command.argv, code, outcome, elapsed, str(evidence_path.relative_to(bundle)))
