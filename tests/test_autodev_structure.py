"""
Phase 11 guard: the OMNI Auto Dev core skeleton imports cleanly and its CLI
behaves as a skeleton (no network, no LLM calls, no GitHub API, no
autonomous execution).
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


def test_package_imports_cleanly():
    import omni.autodev  # noqa: F401
    from omni.autodev import config, models  # noqa: F401


def test_config_defaults_are_nonempty_lists():
    from omni.autodev.config import (
        DEFAULT_NON_GOALS,
        DEFAULT_PROTECTED_AREAS,
        DEFAULT_VALIDATION_COMMANDS,
    )

    for values in (DEFAULT_PROTECTED_AREAS, DEFAULT_NON_GOALS, DEFAULT_VALIDATION_COMMANDS):
        assert isinstance(values, list)
        assert values
        assert all(isinstance(item, str) for item in values)


def test_model_stubs_construct_with_defaults():
    from omni.autodev.models import (
        AutoDevCampaign,
        AutoDevDryRunSummary,
        AutoDevSafetyRule,
        AutoDevTask,
        AutoDevValidationPlan,
    )

    task = AutoDevTask(name="t1", description="do a thing")
    assert task.status == "planned"

    rule = AutoDevSafetyRule(name="no-sandbox-edits", description="don't touch sandbox")
    plan = AutoDevValidationPlan()
    assert plan.commands == []

    campaign = AutoDevCampaign(name="c1", description="campaign", tasks=[task], safety_rules=[rule])
    assert campaign.tasks == [task]
    assert campaign.safety_rules == [rule]

    summary = AutoDevDryRunSummary()
    assert summary.status == "skeleton only"
    assert summary.network_enabled is False
    assert summary.llm_calls_enabled is False
    assert summary.github_api_enabled is False
    assert summary.autonomous_execution_enabled is False


def test_cli_help_exits_zero():
    proc = _run_cli("--help")
    assert proc.returncode == 0, proc.stderr
    assert "Auto Dev" in proc.stdout


def test_cli_dry_run_reports_disabled_capabilities():
    proc = _run_cli("--dry-run")
    assert proc.returncode == 0, proc.stderr
    out = proc.stdout
    assert "skeleton only" in out
    assert "Network: disabled" in out
    assert "LLM calls: disabled" in out
    assert "GitHub API: disabled" in out
    assert "Autonomous execution: disabled" in out


def test_cli_with_no_args_prints_help():
    proc = _run_cli()
    assert proc.returncode == 0, proc.stderr
    assert "usage" in proc.stdout.lower()
