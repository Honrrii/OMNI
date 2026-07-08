"""Phase 10 Stage 1 guard: dead modules removed in the cleanup stay removed.

Walks every Python file in the repo's source trees, parses its import
statements with ast (no code execution), and asserts that nothing imports
the modules deleted in Stage 1. Also asserts the modules are gone from
disk and are not importable.
"""

import ast
import importlib.util
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent

# Modules deleted in Phase 10 Stage 1.
DELETED_MODULES = (
    "backend.app.omni_core.agent_council",
    "backend.app.omni_core.agent_protocol",
    "backend.app.omni_core.agent_communication",
    "backend.app.model_router",
    "backend.app.nvidia_client",
    "test_nvidia",
)

# Source trees that hold live Python code.
SOURCE_DIRS = ("backend", "agents", "scripts", "tests")

EXCLUDED_DIR_NAMES = {"__pycache__", "avengers_env", "node_modules", ".git"}


def iter_source_files():
    roots = [REPO_ROOT / d for d in SOURCE_DIRS if (REPO_ROOT / d).is_dir()]
    files = [p for p in REPO_ROOT.glob("*.py")]
    for root in roots:
        files.extend(root.rglob("*.py"))
    for path in sorted(set(files)):
        if EXCLUDED_DIR_NAMES.intersection(path.parts):
            continue
        yield path


def imported_module_names(path: Path):
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield alias.name
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                yield node.module


def test_deleted_module_files_are_gone():
    for module in DELETED_MODULES:
        path = REPO_ROOT / (module.replace(".", "/") + ".py")
        assert not path.exists(), f"deleted module still on disk: {path}"


def find_spec_safely(module: str):
    """Return a spec when importable, otherwise None.

    importlib.util.find_spec() can raise ModuleNotFoundError when a parent
    package is not importable. For this guard, that still means the deleted
    target module is not importable.
    """
    try:
        return importlib.util.find_spec(module)
    except ModuleNotFoundError:
        return None


@pytest.mark.parametrize("module", DELETED_MODULES)
def test_deleted_modules_are_not_importable(module):
    assert find_spec_safely(module) is None, (
        f"deleted module is still importable: {module}"
    )


def test_no_source_file_imports_deleted_modules():
    offenders = []
    for path in iter_source_files():
        for name in imported_module_names(path):
            for module in DELETED_MODULES:
                if name == module or name.startswith(module + "."):
                    offenders.append(f"{path}: imports {name}")
    assert not offenders, "live imports of deleted modules:\n" + "\n".join(offenders)
