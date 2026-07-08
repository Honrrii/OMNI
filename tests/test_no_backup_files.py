"""Phase 10 Stage 2 guard: no `.bak` files in live source trees.

Stage 2 removed the tracked backup
backend/app/generators/fusion360_script_generator.py.bak. This test keeps
backup files from reappearing in live source directories. It only scans the
filesystem — no imports of runtime modules, no network.
"""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# Live source trees only. Archive, knowledge, outputs, experiments, and
# memory are intentionally not scanned.
SOURCE_DIRS = ("backend", "agents", "scripts", "tests", "frontend/src")

EXCLUDED_DIR_NAMES = {"__pycache__", "avengers_env", "node_modules", ".git"}


def test_no_bak_files_in_source_trees():
    offenders = []
    for source_dir in SOURCE_DIRS:
        root = REPO_ROOT / source_dir
        if not root.is_dir():
            continue
        for path in sorted(root.rglob("*.bak")):
            if EXCLUDED_DIR_NAMES.intersection(path.parts):
                continue
            offenders.append(str(path.relative_to(REPO_ROOT)))
    assert not offenders, "backup files in live source trees:\n" + "\n".join(offenders)
