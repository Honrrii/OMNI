"""
Phase 11 guard: the OMNI Auto Dev run directory / role packet scaffold
builds the expected local file layout and the CLI's init-run command
behaves as a scaffold only (no network, no LLM calls, no GitHub API, no
agent launching).
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "omni_autodev.py"


def _run_cli(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT_PATH), *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )


def test_build_run_files_contains_expected_filenames():
    from omni.autodev.config import RUN_TEMPLATE_FILENAMES
    from omni.autodev.models import AutoDevRunState
    from omni.autodev.run_layout import build_run_files

    state = AutoDevRunState(
        issue_number=60,
        issue_title="Run directory and role packet layout",
        branch="omni/phase11-autodev-run-directory-role-packets",
    )
    files = build_run_files(state)
    assert set(files) == set(RUN_TEMPLATE_FILENAMES)
    assert list(files) == RUN_TEMPLATE_FILENAMES


def test_state_json_contains_required_metadata():
    from omni.autodev.models import AutoDevRunState
    from omni.autodev.run_layout import render_state_json

    state = AutoDevRunState(
        issue_number=60,
        issue_title="Run directory and role packet layout",
        branch="omni/phase11-autodev-run-directory-role-packets",
        implementer="claude",
        reviewer="codex",
    )
    payload = json.loads(render_state_json(state))
    assert payload["issue_number"] == 60
    assert payload["issue_title"] == "Run directory and role packet layout"
    assert payload["branch"] == "omni/phase11-autodev-run-directory-role-packets"
    assert payload["implementer"] == "claude"
    assert payload["reviewer"] == "codex"
    assert payload["status"] == "planned"
    assert payload["human_approval_required"] is True


def test_packet_templates_mention_roles_and_rules():
    from omni.autodev.models import AutoDevRunState
    from omni.autodev.run_layout import render_implementer_packet, render_reviewer_packet

    state = AutoDevRunState(issue_number=1, issue_title="t", branch="b")
    implementer_packet = render_implementer_packet(state)
    reviewer_packet = render_reviewer_packet(state)

    assert "implementer" in implementer_packet.lower()
    assert "human approval" in implementer_packet.lower()
    assert "reviewer" in reviewer_packet.lower()
    assert "human approval" in reviewer_packet.lower()


def test_write_run_files_creates_all_files_on_disk(tmp_path):
    from omni.autodev.models import AutoDevRunState
    from omni.autodev.run_layout import build_run_files, write_run_files

    state = AutoDevRunState(issue_number=60, issue_title="t", branch="b")
    files = build_run_files(state)
    run_dir = tmp_path / "issue-60"

    written = write_run_files(run_dir, files)

    assert len(written) == len(files)
    for name in files:
        path = run_dir / name
        assert path.exists()
        assert path.read_text(encoding="utf-8") == files[name]


def test_write_run_files_refuses_to_overwrite_existing_file(tmp_path):
    from omni.autodev.models import AutoDevRunState
    from omni.autodev.run_layout import (
        AutoDevRunConflictError,
        build_run_files,
        write_run_files,
    )

    state = AutoDevRunState(issue_number=60, issue_title="t", branch="b")
    files = build_run_files(state)
    run_dir = tmp_path / "issue-60"

    write_run_files(run_dir, files)

    # Simulate an in-progress human/AI edit to one of the fillable reports.
    edited_path = run_dir / "IMPLEMENTER_REPORT.md"
    edited_content = "Status: in progress\n\nDo not clobber me.\n"
    edited_path.write_text(edited_content, encoding="utf-8")

    other_paths = {name: (run_dir / name).read_text(encoding="utf-8") for name in files if name != "IMPLEMENTER_REPORT.md"}

    new_state = AutoDevRunState(issue_number=60, issue_title="changed title", branch="b")
    new_files = build_run_files(new_state)

    with pytest.raises(AutoDevRunConflictError) as excinfo:
        write_run_files(run_dir, new_files)

    assert "IMPLEMENTER_REPORT.md" in str(excinfo.value)

    # Every existing file, edited or not, must be preserved byte-for-byte.
    assert edited_path.read_text(encoding="utf-8") == edited_content
    for name, content in other_paths.items():
        assert (run_dir / name).read_text(encoding="utf-8") == content


def test_cli_top_level_dry_run_still_works():
    proc = _run_cli("--dry-run")
    assert proc.returncode == 0, proc.stderr
    assert "skeleton only" in proc.stdout


def test_cli_init_run_dry_run_writes_no_files(tmp_path):
    output_dir = tmp_path / "issue-60"
    proc = _run_cli(
        "init-run",
        "--issue",
        "60",
        "--title",
        "Run directory and role packet layout",
        "--branch",
        "omni/phase11-autodev-run-directory-role-packets",
        "--implementer",
        "claude",
        "--reviewer",
        "codex",
        "--output",
        str(output_dir),
        "--dry-run",
    )
    assert proc.returncode == 0, proc.stderr
    assert "dry run" in proc.stdout.lower()
    assert str(output_dir) in proc.stdout
    assert "No files written" in proc.stdout
    assert not output_dir.exists()


def test_cli_init_run_creates_expected_files(tmp_path):
    from omni.autodev.config import RUN_TEMPLATE_FILENAMES

    output_dir = tmp_path / "issue-60"
    proc = _run_cli(
        "init-run",
        "--issue",
        "60",
        "--title",
        "Run directory and role packet layout",
        "--output",
        str(output_dir),
    )
    assert proc.returncode == 0, proc.stderr
    assert output_dir.is_dir()

    for name in RUN_TEMPLATE_FILENAMES:
        assert (output_dir / name).exists()

    state = json.loads((output_dir / "STATE.json").read_text(encoding="utf-8"))
    assert state["issue_number"] == 60
    assert state["issue_title"] == "Run directory and role packet layout"
    assert state["human_approval_required"] is True


def test_cli_init_run_rerun_fails_and_preserves_existing_files(tmp_path):
    output_dir = tmp_path / "issue-60"
    first = _run_cli(
        "init-run",
        "--issue",
        "60",
        "--title",
        "Run directory and role packet layout",
        "--output",
        str(output_dir),
    )
    assert first.returncode == 0, first.stderr

    # Simulate an in-progress edit to a fillable report before rerunning.
    report_path = output_dir / "IMPLEMENTER_REPORT.md"
    edited_content = "Status: in progress\n\nDo not clobber me.\n"
    report_path.write_text(edited_content, encoding="utf-8")

    second = _run_cli(
        "init-run",
        "--issue",
        "60",
        "--title",
        "a different title",
        "--output",
        str(output_dir),
    )

    assert second.returncode != 0
    assert "IMPLEMENTER_REPORT.md" in second.stderr
    assert report_path.read_text(encoding="utf-8") == edited_content
