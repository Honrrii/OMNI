#!/usr/bin/env python3
"""
OMNI Frontier Research Lab — Phase 2B local CLI.

*** MOCK / NON-MODEL EXECUTION ONLY ***

Every command in this script runs `omni.frontier.agents.MockClaudeAdapter`
and `omni.frontier.agents.MockCodexAdapter` — deterministic Python functions
that never call Claude Code, never call Codex, never call a model API, and
never open a network connection. This script does not schedule itself, does
not loop, and exits after one command.

Usage:
    python3 scripts/omni_frontier_lab.py run-mock-shift
    python3 scripts/omni_frontier_lab.py run-mock-shift --dry-run
    python3 scripts/omni_frontier_lab.py run-mock-shift --thread-id OMNI-FRONTIER-0001
    python3 scripts/omni_frontier_lab.py show-state --thread-id OMNI-FRONTIER-0001
"""
from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from omni.frontier.agents import MockClaudeAdapter, MockCodexAdapter
from omni.frontier.config import FrontierLabConfig
from omni.frontier.orchestrator import ShiftOrchestrator, ShiftReport

MOCK_BANNER = (
    "*** OMNI Frontier Research Lab — MOCK / NON-MODEL EXECUTION ***\n"
    "This run uses MockClaudeAdapter and MockCodexAdapter only. No real "
    "Claude Code process, Codex process, or model API is invoked."
)

DEFAULT_LAB_ROOT = ROOT / ".omni-lab"


def render_shift_report(report: ShiftReport) -> str:
    lines = [
        MOCK_BANNER,
        "",
        f"Thread ID: {report.thread_id}",
        f"Final state: {report.final_state}",
        f"Stopped early: {report.stopped_early}"
        + (f" ({report.stop_reason})" if report.stopped_early else ""),
        f"Debate rounds completed: {report.rounds_completed}",
        f"Agent turns used: {report.turns_used}",
        f"Invalid messages rejected: {report.invalid_message_count}",
        f"Messages on thread: {report.message_count}",
        f"Events logged: {len(report.events)}",
        f"Provider (real model) calls: {report.provider_calls}",
    ]
    if report.experiment is not None:
        lines.append(f"Experiment status: {report.experiment.status}")
        lines.append(f"Conclusion state: {report.experiment.conclusion_state}")
    else:
        lines.append("Experiment record: none created before the shift stopped")
    lines.append(f"Archive: {report.archive_dir}")
    lines.append(f"Runtime snapshot: {report.runtime_dir}")
    return "\n".join(lines)


def run_run_mock_shift(args: argparse.Namespace) -> int:
    config = FrontierLabConfig()

    if args.dry_run:
        with tempfile.TemporaryDirectory(prefix="omni-frontier-lab-dry-run-") as tmp:
            orchestrator = ShiftOrchestrator(
                config=config,
                claude=MockClaudeAdapter(),
                codex=MockCodexAdapter(),
                lab_root=Path(tmp),
            )
            report = orchestrator.run_mock_shift(thread_id=args.thread_id)
            print(render_shift_report(report))
            print("\n(--dry-run: archive and runtime files were written to a "
                  "temporary directory and discarded, not to .omni-lab/)")
        return 0

    lab_root = Path(args.output_root) if args.output_root else DEFAULT_LAB_ROOT
    orchestrator = ShiftOrchestrator(
        config=config,
        claude=MockClaudeAdapter(),
        codex=MockCodexAdapter(),
        lab_root=lab_root,
    )
    report = orchestrator.run_mock_shift(thread_id=args.thread_id)
    print(render_shift_report(report))
    return 0


def run_show_state(args: argparse.Namespace) -> int:
    lab_root = Path(args.root) if args.root else DEFAULT_LAB_ROOT
    state_path = lab_root / "runtime" / args.thread_id / "state.json"
    if not state_path.exists():
        print(f"error: no runtime state found at {state_path}", file=sys.stderr)
        return 1
    print(MOCK_BANNER)
    print("")
    print(state_path.read_text(encoding="utf-8"))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "OMNI Frontier Research Lab Phase 2B CLI. Runs only deterministic "
            "MOCK Claude/Codex adapters — never a real model, never a network "
            "call, never self-scheduling."
        ),
    )
    subparsers = parser.add_subparsers(dest="command")

    run_mock_shift = subparsers.add_parser(
        "run-mock-shift",
        help="Run one complete deterministic mock research shift end to end.",
    )
    run_mock_shift.add_argument(
        "--thread-id",
        default=None,
        help="Explicit thread ID (e.g. OMNI-FRONTIER-0001). Default: allocate the next unused one.",
    )
    run_mock_shift.add_argument(
        "--output-root",
        default=None,
        help="Lab root directory to write archive/runtime files under. Default: .omni-lab/.",
    )
    run_mock_shift.add_argument(
        "--dry-run",
        action="store_true",
        help="Run the full mock shift against a discarded temporary directory instead of .omni-lab/.",
    )

    show_state = subparsers.add_parser(
        "show-state",
        help="Print a previously written runtime state.json for a thread.",
    )
    show_state.add_argument("--thread-id", required=True, help="Thread ID to show, e.g. OMNI-FRONTIER-0001.")
    show_state.add_argument("--root", default=None, help="Lab root directory. Default: .omni-lab/.")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "run-mock-shift":
        return run_run_mock_shift(args)
    if args.command == "show-state":
        return run_show_state(args)

    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
