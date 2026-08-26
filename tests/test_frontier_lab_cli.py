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
