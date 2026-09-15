"""File-auth Codex runtime: namespace-only scratch, no credential serialization.

Codex 0.153.4 was probed without network or generation: login reads auth.json;
even help creates tmp/arg0 aliases and a lock under CODEX_HOME. Support only
that verified file-auth layout. Keyring and environment auth are not fallbacks.
This file also runs as an isolated Python entrypoint inside Bubblewrap.
"""
from __future__ import annotations

from dataclasses import dataclass
import fcntl
import json
import os
from pathlib import Path
import stat
import sys
import tempfile

PRIVATE_HOME = Path("/run/testcube-codex")


@dataclass(frozen=True)
class CodexRuntime:
    host_home: Path
    host_state: Path

    @classmethod
    def discover(cls, source: Path, hidden_root: Path):
        home = Path(os.environ["HOME"])
        state = Path(os.environ.get("CODEX_HOME", str(home / ".codex")))
        for path in (home, state):
            if not path.is_absolute() or path.resolve(strict=True) != path or not path.is_dir():
                raise ValueError("unsupported Codex home layout")
            if path in (Path("/"), Path("/tmp"), Path("/run")) or Path("/run") in path.parents:
                raise ValueError("unsupported Codex home location")
        # A state mask must never cover source, archive, HOME, or the launcher.
        for path in (source, hidden_root, home):
            if state == path or state in path.parents or (path != home and path in state.parents):
                raise ValueError("overlapping Codex state location")
        auth = state / "auth.json"
        if not stat.S_ISREG(auth.lstat().st_mode):
            raise ValueError("Codex requires a regular file-auth artifact")
        return cls(home, state)

    def mount_argv(self) -> list[str]:
        return [
            # Preserve HOME's read-only view even for synthetic homes under /tmp.
            "--ro-bind", str(self.host_home), str(self.host_home),
            "--perms", "0700", "--tmpfs", str(PRIVATE_HOME),
            "--ro-bind", str(self.host_state / "auth.json"), str(PRIVATE_HOME / "auth.json"),
            # Hide unrelated sessions, config, caches and credentials in host state.
            "--tmpfs", str(self.host_state), "--remount-ro", str(self.host_state),
            "--setenv", "CODEX_HOME", str(PRIVATE_HOME),
            "--setenv", "XDG_CONFIG_HOME", str(PRIVATE_HOME / "xdg/config"),
            "--setenv", "XDG_STATE_HOME", str(PRIVATE_HOME / "xdg/state"),
            "--setenv", "XDG_CACHE_HOME", str(PRIVATE_HOME / "xdg/cache"),
            "--unsetenv", "OPENAI_API_KEY", "--unsetenv", "CODEX_API_KEY",
            "--unsetenv", "ANTHROPIC_API_KEY", "--unsetenv", "CLAUDE_CONFIG_DIR",
        ]

    def guarded_command(self, source: Path, hidden_root: Path, argv: list[str]) -> list[str]:
        boundary = [str(p) for p in (self.host_home, self.host_state, source, hidden_root)]
        return [sys.executable, "-I", str(Path(__file__).resolve()), json.dumps(boundary), *argv]


def check_boundary(host_home: Path, host_state: Path, source: Path, hidden_root: Path):
    """Check mount authority without attempting any host write, even on failure."""
    for path in (host_home, host_state, source, source / ".git", PRIVATE_HOME / "auth.json"):
        if not os.statvfs(path).f_flag & os.ST_RDONLY:
            raise ValueError("read-only boundary missing")
    if (any(hidden_root.iterdir()) or
            hidden_root.stat().st_dev == hidden_root.parent.stat().st_dev):
        raise ValueError("archive mask missing")
    if os.environ.get("CODEX_HOME") != str(PRIVATE_HOME):
        raise ValueError("private Codex home missing")
    fd = os.open(PRIVATE_HOME / "auth.json", os.O_RDONLY | os.O_NOFOLLOW)
    os.close(fd)  # Authentication contents are exclusively the CLI's concern.
    # Exercise the mechanics observed in CLI startup, not guessed session names.
    with tempfile.TemporaryDirectory(prefix="boundary-", dir=PRIVATE_HOME) as temp:
        root = Path(temp)
        with (root / "runtime.lock").open("xb") as stream:
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
            stream.write(b"private runtime probe\n")
            stream.flush()
            os.fsync(stream.fileno())
        (root / "alias").symlink_to(root / "runtime.lock")


def main():
    try:
        check_boundary(*(Path(p) for p in json.loads(sys.argv[1])))
    except Exception:
        # No raw auth, CLI diagnostics, or environmental details on failure.
        print("Codex runtime boundary incompatible", file=sys.stderr)
        return 1
    os.execv(sys.argv[2], sys.argv[2:])


if __name__ == "__main__":
    sys.exit(main())
