"""
Phase 2B guard: scripts/omni_frontier_lab.py runs only MOCK adapters,
clearly labels itself as non-model execution, and leaves no persistent
junk in the real repository when run against an explicit output root or
--dry-run. No network, no LLM calls, no model process, no self-scheduling.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / "scripts" / "omni_frontier_lab.py"

_spec = importlib.util.spec_from_file_location("omni_frontier_lab_cli", SCRIPT_PATH)
cli = importlib.util.module_from_spec(_spec)
sys.modules.setdefault("omni_frontier_lab_cli", cli)
_spec.loader.exec_module(cli)


def test_run_mock_shift_writes_under_explicit_output_root(tmp_path, capsys):
    output_root = tmp_path / "lab"
    exit_code = cli.main(["run-mock-shift", "--output-root", str(output_root)])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "MOCK / NON-MODEL EXECUTION" in captured.out
    assert "Final state: ARCHIVED" in captured.out
    assert (output_root / "experiments").is_dir()
    assert (output_root / "runtime").is_dir()


def test_run_mock_shift_dry_run_writes_nothing_persistent(tmp_path, capsys, monkeypatch):
    before = {p for p in (ROOT / ".omni-lab").rglob("*")}
    exit_code = cli.main(["run-mock-shift", "--dry-run"])
    captured = capsys.readouterr()
    after = {p for p in (ROOT / ".omni-lab").rglob("*")}

    assert exit_code == 0
    assert "--dry-run" in captured.out
    assert before == after  # nothing new appeared under the real .omni-lab/


def test_show_state_reads_back_a_prior_run(tmp_path, capsys):
    output_root = tmp_path / "lab"
    cli.main(["run-mock-shift", "--output-root", str(output_root), "--thread-id", "OMNI-FRONTIER-0042"])
    capsys.readouterr()

    exit_code = cli.main(["show-state", "--thread-id", "OMNI-FRONTIER-0042", "--root", str(output_root)])
    captured = capsys.readouterr()
    assert exit_code == 0
    assert "MOCK / NON-MODEL EXECUTION" in captured.out
    assert "OMNI-FRONTIER-0042" in captured.out

    payload = json.loads((output_root / "runtime" / "OMNI-FRONTIER-0042" / "state.json").read_text())
    assert payload["thread_id"] == "OMNI-FRONTIER-0042"
    assert payload["state"] == "ARCHIVED"


def test_show_state_missing_thread_errors_cleanly(tmp_path, capsys):
    exit_code = cli.main(["show-state", "--thread-id", "OMNI-FRONTIER-9999", "--root", str(tmp_path / "empty")])
    assert exit_code == 1


def test_cli_never_imports_a_provider_sdk_or_subprocess():
    source = SCRIPT_PATH.read_text(encoding="utf-8")
    for banned in ("import subprocess", "import anthropic", "import openai", "os.system", "socket.socket"):
        assert banned not in source


# ---------------------------------------------------------------------------
# Phase 5: run-dual-live-shift wiring (real Claude + real Codex)
# ---------------------------------------------------------------------------


def test_run_dual_live_shift_is_a_registered_command():
    parser = cli.build_parser()
    args = parser.parse_args(["run-dual-live-shift", "--mission-file", "mission.md"])
    assert args.command == "run-dual-live-shift"
    assert args.claude_executable == "claude"
    assert args.codex_executable == "codex"
    assert args.claude_timeout_seconds > 0
    assert args.codex_timeout_seconds > 0


def test_run_dual_live_shift_accepts_thread_id_and_output_root():
    parser = cli.build_parser()
    args = parser.parse_args(
        [
            "run-dual-live-shift",
            "--mission-file", "mission.md",
            "--thread-id",
            "OMNI-FRONTIER-0099",
            "--output-root",
            "/tmp/some-lab-root",
            "--dry-run",
        ]
    )
    assert args.thread_id == "OMNI-FRONTIER-0099"
    assert args.output_root == "/tmp/some-lab-root"
    assert args.dry_run is True


def test_dual_live_source_wires_both_real_adapter_classes():
    """Static guard: run-dual-live-shift must construct both real adapter
    classes (not silently fall back to a mock for either side)."""
    source = SCRIPT_PATH.read_text(encoding="utf-8")
    dual_shift_source = source[source.index("def _run_dual_live_shift") : source.index("def run_run_dual_live_shift")]
    assert "ClaudeCodeAdapter(" in dual_shift_source
    assert "CodexAdapter(" in dual_shift_source
    assert "MockClaudeAdapter(" not in dual_shift_source
    assert "MockCodexAdapter(" not in dual_shift_source


def test_dual_live_banner_names_both_real_providers_as_read_only():
    assert "REAL CLAUDE CODE ENABLED" in cli.DUAL_LIVE_BANNER
    assert "REAL CODEX ENABLED" in cli.DUAL_LIVE_BANNER
    assert "READ-ONLY" in cli.DUAL_LIVE_BANNER
    assert "NO GIT WRITE AUTHORITY" in cli.DUAL_LIVE_BANNER


# ---------------------------------------------------------------------------
# combined_dual_preflight: pure composition of two PreflightResults
# ---------------------------------------------------------------------------


def test_combined_dual_preflight_ready_when_both_ready():
    claude_ready = cli.PreflightResult(ready=True, status="CLAUDE_READY", provider_version="2.1.246")
    codex_ready = cli.PreflightResult(ready=True, status="CODEX_READY", provider_version="0.145.0")
    result = cli.combined_dual_preflight(claude_ready, codex_ready)
    assert result.ready is True
    assert result.status == "DUAL_READY"
    assert "claude=CLAUDE_READY" in result.detail
    assert "codex=CODEX_READY" in result.detail


def test_combined_dual_preflight_not_ready_when_claude_fails():
    claude_not_ready = cli.PreflightResult(ready=False, status="CLAUDE_NOT_AUTHENTICATED", detail="loggedIn=false")
    codex_ready = cli.PreflightResult(ready=True, status="CODEX_READY")
    result = cli.combined_dual_preflight(claude_not_ready, codex_ready)
    assert result.ready is False
    assert result.status == "DUAL_PREFLIGHT_FAILED"
    assert "claude=CLAUDE_NOT_AUTHENTICATED" in result.detail
    assert "codex=" not in result.detail  # codex was ready, so it is not named among failures


def test_combined_dual_preflight_not_ready_when_codex_fails():
    claude_ready = cli.PreflightResult(ready=True, status="CLAUDE_READY")
    codex_not_ready = cli.PreflightResult(ready=False, status="CODEX_EXECUTABLE_NOT_FOUND", detail="not on PATH")
    result = cli.combined_dual_preflight(claude_ready, codex_not_ready)
    assert result.ready is False
    assert result.status == "DUAL_PREFLIGHT_FAILED"
    assert "codex=CODEX_EXECUTABLE_NOT_FOUND" in result.detail


def test_combined_dual_preflight_not_ready_when_both_fail():
    claude_not_ready = cli.PreflightResult(ready=False, status="CLAUDE_EXECUTABLE_NOT_FOUND")
    codex_not_ready = cli.PreflightResult(ready=False, status="CODEX_EXECUTABLE_NOT_FOUND")
    result = cli.combined_dual_preflight(claude_not_ready, codex_not_ready)
    assert result.ready is False
    assert "claude=CLAUDE_EXECUTABLE_NOT_FOUND" in result.detail
    assert "codex=CODEX_EXECUTABLE_NOT_FOUND" in result.detail
