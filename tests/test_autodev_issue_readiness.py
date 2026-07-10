"""
Phase 11 guard: the OMNI Auto Dev local issue readiness checker parses a
Markdown/text issue body deterministically and the CLI's check-issue command
behaves as a local-only checker (no network, no GitHub API, no gh CLI, no
LLM calls).
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "omni_autodev.py"

READY_ISSUE_BODY = """\
## Goal

Create a local-only issue readiness checker.

## Scope

Check a Markdown issue body for required Auto Dev sections.

## Out of Scope / Non-goals

Do not fetch GitHub issues.

## Expected Files

- scripts/omni_autodev.py
- omni/autodev/issue_readiness.py
- tests/test_autodev_issue_readiness.py

## Acceptance Criteria

- Checker reports READY when all required sections exist.
- Checker reports NEEDS_DETAIL when sections are missing.

## Validation Commands

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest tests/test_autodev_issue_readiness.py -q
```

## Stop Conditions

Stop if implementation requires GitHub access, network access, or LLM calls.

## Final Report

Include summary, files changed, commands run, test results, risks, and next issue.
"""


def _run_cli(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT_PATH), *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )


def test_check_issue_text_ready_when_all_sections_present():
    from omni.autodev.issue_readiness import check_issue_text

    report = check_issue_text(READY_ISSUE_BODY)
    assert report.verdict == "READY"
    assert report.missing_sections == []
    assert set(report.present_sections) == {
        "Goal",
        "Scope",
        "Out of Scope / Non-goals",
        "Expected Files",
        "Acceptance Criteria",
        "Validation Commands",
        "Stop Conditions",
        "Final Report",
    }


def test_check_issue_text_needs_detail_when_sections_missing():
    from omni.autodev.issue_readiness import check_issue_text

    partial_body = "## Goal\n\ndo the thing\n\n## Scope\n\nkeep it small\n"
    report = check_issue_text(partial_body)

    assert report.verdict == "NEEDS_DETAIL"
    assert report.present_sections == ["Goal", "Scope"]
    assert report.missing_sections == [
        "Out of Scope / Non-goals",
        "Expected Files",
        "Acceptance Criteria",
        "Validation Commands",
        "Stop Conditions",
        "Final Report",
    ]


def test_check_issue_text_accepts_alternate_non_goals_heading():
    from omni.autodev.issue_readiness import check_issue_text

    body = READY_ISSUE_BODY.replace("## Out of Scope / Non-goals", "## Non-goals")
    report = check_issue_text(body)

    assert report.verdict == "READY"
    assert "Out of Scope / Non-goals" in report.present_sections


def test_check_issue_text_ignores_headings_inside_code_fences():
    from omni.autodev.issue_readiness import check_issue_text

    body = "## Goal\n\ntext\n\n```text\n## Scope\n```\n"
    report = check_issue_text(body)

    assert "Goal" in report.present_sections
    assert "Scope" not in report.present_sections


def test_check_issue_file_missing_file_raises(tmp_path):
    from omni.autodev.issue_readiness import check_issue_file

    missing_path = tmp_path / "does_not_exist.md"
    with pytest.raises(FileNotFoundError):
        check_issue_file(missing_path)


def test_check_issue_file_reads_local_file(tmp_path):
    from omni.autodev.issue_readiness import check_issue_file

    issue_path = tmp_path / "issue.md"
    issue_path.write_text(READY_ISSUE_BODY, encoding="utf-8")

    report = check_issue_file(issue_path)
    assert report.verdict == "READY"


def test_cli_check_issue_ready(tmp_path):
    issue_path = tmp_path / "issue.md"
    issue_path.write_text(READY_ISSUE_BODY, encoding="utf-8")

    proc = _run_cli("check-issue", "--file", str(issue_path))

    assert proc.returncode == 0, proc.stderr
    assert "Issue readiness: READY" in proc.stdout
    assert "Missing sections: none" in proc.stdout
    assert "Warnings: none" in proc.stdout
    assert "- Goal: present" in proc.stdout


def test_cli_check_issue_needs_detail(tmp_path):
    issue_path = tmp_path / "issue.md"
    issue_path.write_text("## Goal\n\nonly a goal\n", encoding="utf-8")

    proc = _run_cli("check-issue", "--file", str(issue_path))

    assert proc.returncode == 0, proc.stderr
    assert "Issue readiness: NEEDS_DETAIL" in proc.stdout
    assert "- Goal: present" in proc.stdout
    assert "- Final Report: missing" in proc.stdout
    assert "Missing sections:" in proc.stdout
    assert "- Final Report" in proc.stdout


def test_cli_check_issue_missing_file_fails_clearly(tmp_path):
    missing_path = tmp_path / "does_not_exist.md"

    proc = _run_cli("check-issue", "--file", str(missing_path))

    assert proc.returncode != 0
    assert "error" in proc.stderr.lower()
    assert str(missing_path) in proc.stderr
