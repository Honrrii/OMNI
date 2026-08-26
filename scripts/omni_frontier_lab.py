#!/usr/bin/env python3
"""
OMNI Frontier Research Lab — Phase 2B/3 local CLI.

`run-mock-shift`/`show-state` (Phase 2B): *** MOCK / NON-MODEL EXECUTION
ONLY ***. Both run `omni.frontier.agents.MockClaudeAdapter`/
`MockCodexAdapter` — deterministic Python functions that never call Claude
Code, never call Codex, never call a model API, and never open a network
connection.

`run-claude-shift` (Phase 3): launches a real `claude` subprocess for the
Claude side of the shift (`omni.frontier.claude_provider.ClaudeCodeAdapter`)
in a bounded, read-only research turn; Codex stays `MockCodexAdapter`. This
command is the only place in this script that can invoke a real model, and
only when explicitly run — the default (`run-mock-shift`) never does.

Nothing in this script schedules itself, loops, or runs more than one
command per invocation.

Usage:
    python3 scripts/omni_frontier_lab.py run-mock-shift
    python3 scripts/omni_frontier_lab.py run-mock-shift --dry-run
    python3 scripts/omni_frontier_lab.py run-mock-shift --thread-id OMNI-FRONTIER-0001
    python3 scripts/omni_frontier_lab.py show-state --thread-id OMNI-FRONTIER-0001
    python3 scripts/omni_frontier_lab.py run-claude-shift
    python3 scripts/omni_frontier_lab.py run-claude-shift --dry-run
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
from omni.frontier.claude_provider import ClaudeCodeAdapter, check_claude_availability
from omni.frontier.config import ClaudeProviderConfig, FrontierLabConfig, PROVIDER_MODE_CLAUDE_LIVE
from omni.frontier.orchestrator import PreflightResult, ShiftOrchestrator, ShiftReport

MOCK_BANNER = (
    "*** OMNI Frontier Research Lab — MOCK / NON-MODEL EXECUTION ***\n"
    "This run uses MockClaudeAdapter and MockCodexAdapter only. No real "
    "Claude Code process, Codex process, or model API is invoked."
)

CLAUDE_LIVE_BANNER = (
    "*** OMNI Frontier Research Lab ***\n"
    "REAL CLAUDE CODE ENABLED\n"
    "CODEX IS MOCKED\n"
    "READ-ONLY RESEARCH MODE\n"
    "NO GIT WRITE AUTHORITY\n"
    "The Claude side of this shift launches a real `claude` subprocess "
    "(omni/frontier/claude_provider.py) with no Edit/Write/NotebookEdit "
    "tool access and no mutating git command allowed. Codex remains "
    "MockCodexAdapter. No branch/worktree is created, and nothing is "
    "pushed or merged."
)

DEFAULT_LAB_ROOT = ROOT / ".omni-lab"


def render_shift_report(report: ShiftReport, *, banner: str | None = MOCK_BANNER) -> str:
    lines = [] if banner is None else [banner, ""]
    lines += [
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


def _run_claude_shift(args: argparse.Namespace, lab_root: Path) -> ShiftReport:
    provider_config = ClaudeProviderConfig(
        provider_mode=PROVIDER_MODE_CLAUDE_LIVE,
        claude_executable=args.claude_executable,
        claude_timeout_seconds=args.claude_timeout_seconds,
    )
    claude_adapter = ClaudeCodeAdapter(config=provider_config, cwd=ROOT)

    def preflight() -> PreflightResult:
        return check_claude_availability(provider_config, cwd=ROOT)

    orchestrator = ShiftOrchestrator(
        config=FrontierLabConfig(),
        claude=claude_adapter,
        codex=MockCodexAdapter(),
        lab_root=lab_root,
        preflight=preflight,
    )
    report = orchestrator.run_mock_shift(thread_id=args.thread_id)
    print(render_shift_report(report, banner=None))
    if claude_adapter.call_history:
        print("\nClaude provider call history:")
        for record in claude_adapter.call_history:
            summary = f" — {record.error_summary}" if record.error_summary else ""
            print(
                f"  turn {record.turn_number} [{record.stage}] "
                f"{record.exit_classification} ({record.duration_seconds:.2f}s){summary}"
            )
    print("\nThread messages:")
    for message in orchestrator.thread_messages:
        print(f"  [{message.sequence}] {message.from_agent} -> {message.to_agent} ({message.message_type}):")
        print(f"      {message.claim}")
    return report


def run_run_claude_shift(args: argparse.Namespace) -> int:
    print(CLAUDE_LIVE_BANNER)
    print("")

    if args.dry_run:
        with tempfile.TemporaryDirectory(prefix="omni-frontier-lab-claude-dry-run-") as tmp:
            _run_claude_shift(args, Path(tmp))
            print(
                "\n(--dry-run: archive and runtime files were written to a "
                "temporary directory and discarded, not to .omni-lab/. The "
                "real `claude` subprocess, if reached, was still invoked.)"
            )
        return 0

    lab_root = Path(args.output_root) if args.output_root else DEFAULT_LAB_ROOT
    _run_claude_shift(args, lab_root)
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
            "OMNI Frontier Research Lab CLI. run-mock-shift/show-state use only "
            "deterministic MOCK Claude/Codex adapters. run-claude-shift launches "
            "a real, read-only, bounded Claude Code process for Claude's turns "
            "while Codex stays mocked — never automatically, never scheduled."
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

    run_claude_shift = subparsers.add_parser(
        "run-claude-shift",
        help=(
            "Run one bounded, read-only research shift using a REAL Claude Code "
            "process for Claude's turns; Codex stays MockCodexAdapter. Requires "
            "an explicit command — run-mock-shift never does this."
        ),
    )
    run_claude_shift.add_argument(
        "--thread-id",
        default=None,
        help="Explicit thread ID (e.g. OMNI-FRONTIER-0001). Default: allocate the next unused one.",
    )
    run_claude_shift.add_argument(
        "--output-root",
        default=None,
        help="Lab root directory to write archive/runtime files under. Default: .omni-lab/.",
    )
    run_claude_shift.add_argument(
        "--dry-run",
        action="store_true",
        help=(
            "Write archive/runtime files to a discarded temporary directory instead "
            "of .omni-lab/. Still invokes the real claude subprocess if the "
            "provider preflight passes — this is not a way to avoid a real call."
        ),
    )
    run_claude_shift.add_argument(
        "--claude-executable",
        default="claude",
        help="Claude Code executable name or path (default: claude).",
    )
    run_claude_shift.add_argument(
        "--claude-timeout-seconds",
        type=int,
        default=ClaudeProviderConfig().claude_timeout_seconds,
        help="Per-turn timeout for the claude subprocess, in seconds.",
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "run-mock-shift":
        return run_run_mock_shift(args)
    if args.command == "show-state":
        return run_show_state(args)
    if args.command == "run-claude-shift":
        return run_run_claude_shift(args)

    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
