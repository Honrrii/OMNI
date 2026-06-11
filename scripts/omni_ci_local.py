#!/usr/bin/env python3
"""Run OMNI's local CI checks from the repository root."""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

# pytest exits 5 when it starts cleanly but collects zero tests. That means
# the curated tests/ suite is missing or empty, which is a CI failure, not
# a pass: a run that tests nothing proves nothing.
PYTEST_EXIT_NO_TESTS_COLLECTED = 5


def run_check(
    name: str,
    command: list[str],
    cwd: Path = ROOT,
    env: dict[str, str] | None = None,
) -> int:
    print(f"\n== {name} ==", flush=True)
    print("+ " + " ".join(command), flush=True)
    result = subprocess.run(command, cwd=cwd, env=env, check=False)
    if result.returncode == 0:
        print(f"{name}: PASS", flush=True)
    else:
        print(f"{name}: FAIL ({result.returncode})", flush=True)
    return result.returncode


def main() -> int:
    print("OMNI Local CI", flush=True)
    print(f"Repository: {ROOT}", flush=True)

    run_check("Git status", ["git", "status", "--short"])

    whitespace_rc = run_check("Git whitespace check", ["git", "diff", "--check"])

    pytest_rc = run_check(
        "Python tests",
        [sys.executable, "-m", "pytest", "tests"],
        env={**os.environ, "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1"},
    )
    if pytest_rc == PYTEST_EXIT_NO_TESTS_COLLECTED:
        print(
            "Python tests collected ZERO tests (pytest exit 5). The curated"
            " tests/ suite is missing or empty on this branch.",
            flush=True,
        )

    checks = [
        whitespace_rc == 0,
        pytest_rc == 0,
    ]

    frontend_package = ROOT / "frontend" / "package.json"
    if frontend_package.exists():
        with tempfile.TemporaryDirectory(prefix="omni-frontend-build-") as out_dir:
            checks.append(
                run_check(
                    "Frontend build",
                    ["npm", "run", "build", "--", "--outDir", out_dir, "--emptyOutDir"],
                    cwd=ROOT / "frontend",
                )
                == 0
            )
    else:
        print("\n== Frontend build ==", flush=True)
        print("frontend/package.json not found; skipping frontend build.", flush=True)

    if all(checks):
        print("\nOMNI Local CI: PASS", flush=True)
        return 0

    print("\nOMNI Local CI: FAIL", flush=True)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
