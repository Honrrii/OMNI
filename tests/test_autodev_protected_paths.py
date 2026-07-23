"""
Phase 11 guard: the OMNI Auto Dev protected path policy defines protected
areas with reasons and matches individual paths deterministically. No git
diff scanning, changed-file enforcement, network access, or LLM calls.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "omni_autodev.py"


def _run_cli(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT_PATH), *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )


def test_default_protected_path_rules_are_nonempty_with_reasons():
    from omni.autodev.protected_paths import default_protected_path_rules

    rules = default_protected_path_rules()
    assert rules
    for rule in rules:
        assert rule.pattern
        assert rule.reason


def test_match_protected_path_matches_sandbox():
    from omni.autodev.protected_paths import match_protected_path

    rule = match_protected_path("backend/app/sandbox/limited_launcher.py")
    assert rule is not None
    assert "sandbox" in rule.reason.lower()


def test_match_protected_path_matches_frontend_ml_ros_visual_bay_mission_graph():
    from omni.autodev.protected_paths import match_protected_path

    assert match_protected_path("frontend/src/App.jsx") is not None
    assert match_protected_path("backend/app/ml/model.py") is not None
    assert match_protected_path("backend/app/ros/export.py") is not None
    assert match_protected_path("frontend/src/components/VisualBayPanel.jsx") is not None
    assert match_protected_path("backend/app/mission_graph/builder.py") is not None


def test_match_protected_path_returns_none_for_unprotected_path():
    from omni.autodev.protected_paths import match_protected_path

    assert match_protected_path("omni/autodev/config.py") is None
    assert match_protected_path("tests/test_autodev_protected_paths.py") is None


def test_match_protected_path_normalizes_leading_dot_slash_and_backslashes():
    from omni.autodev.protected_paths import match_protected_path

    assert match_protected_path("./backend/app/sandbox/x.py") is not None
    assert match_protected_path("backend\\app\\sandbox\\x.py") is not None


def test_cli_protected_paths_lists_patterns_and_reasons():
    from omni.autodev.config import DEFAULT_PROTECTED_PATH_RULES

    proc = _run_cli("protected-paths")
    assert proc.returncode == 0, proc.stderr
    for pattern, _reason in DEFAULT_PROTECTED_PATH_RULES:
        assert pattern in proc.stdout


def test_cli_top_level_dry_run_still_works():
    proc = _run_cli("--dry-run")
    assert proc.returncode == 0, proc.stderr
    assert "skeleton only" in proc.stdout
