#!/usr/bin/env python3
"""
OMNI Auto Dev — core skeleton CLI (Phase 11).

Describes what Auto Dev would eventually do. Performs no autonomous
actions: no network calls, no LLM calls, no GitHub API calls, no agent
launching, no multi-step campaign execution.

Usage:
    python scripts/omni_autodev.py --help
    python scripts/omni_autodev.py --dry-run
    python scripts/omni_autodev.py init-run --issue 60 --title "..." --dry-run
    python scripts/omni_autodev.py init-run --issue 60 --title "..."
    python scripts/omni_autodev.py check-issue --file /tmp/omni_issue_ready.md
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from omni.autodev.config import (
    DEFAULT_IMPLEMENTER,
    DEFAULT_REQUIRED_ISSUE_SECTIONS,
    DEFAULT_REVIEWER,
    DEFAULT_RUN_STATUS,
)
from omni.autodev.issue_readiness import check_issue_file
from omni.autodev.models import AutoDevDryRunSummary, AutoDevIssueReadiness, AutoDevRunState
from omni.autodev.run_layout import (
    AutoDevRunConflictError,
    build_run_files,
    default_run_dir,
    write_run_files,
)

PLANNED_FUTURE_LAYERS: list[str] = [
    "campaign YAML loading",
    "handoff packet generation",
    "validation result tracking",
    "protected path checks",
]


def build_dry_run_summary() -> AutoDevDryRunSummary:
    return AutoDevDryRunSummary(planned_future_layers=list(PLANNED_FUTURE_LAYERS))


def render_dry_run_summary(summary: AutoDevDryRunSummary) -> str:
    def flag(enabled: bool) -> str:
        return "enabled" if enabled else "disabled"

    lines = [
        "OMNI Auto Dev dry run",
        "",
        f"Status: {summary.status}",
        f"Network: {flag(summary.network_enabled)}",
        f"LLM calls: {flag(summary.llm_calls_enabled)}",
        f"GitHub API: {flag(summary.github_api_enabled)}",
        f"Autonomous execution: {flag(summary.autonomous_execution_enabled)}",
        "",
        "Planned future layers:",
    ]
    lines.extend(f"- {layer}" for layer in summary.planned_future_layers)
    return "\n".join(lines)


def render_init_run_preview(run_dir: Path, files: dict[str, str]) -> str:
    lines = [
        "OMNI Auto Dev init-run (dry run)",
        "",
        f"Would create: {run_dir}",
    ]
    lines.extend(f"  - {name}" for name in files)
    lines.extend(
        [
            "",
            "No files written. Network: disabled. LLM calls: disabled. "
            "GitHub API: disabled.",
        ]
    )
    return "\n".join(lines)


def run_init_run(args: argparse.Namespace) -> int:
    state = AutoDevRunState(
        issue_number=args.issue,
        issue_title=args.title,
        branch=args.branch or "unknown",
        implementer=args.implementer,
        reviewer=args.reviewer,
        status=DEFAULT_RUN_STATUS,
    )
    run_dir = Path(args.output) if args.output else default_run_dir(args.issue)
    files = build_run_files(state)

    if args.init_dry_run:
        print(render_init_run_preview(run_dir, files))
        return 0

    try:
        written = write_run_files(run_dir, files)
    except AutoDevRunConflictError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1

    print(f"Created Auto Dev run directory: {run_dir}")
    for path in written:
        print(f"  - {path.name}")
    return 0


def render_issue_readiness_report(report: AutoDevIssueReadiness) -> str:
    present = set(report.present_sections)
    lines = [f"Issue readiness: {report.verdict}", "", "Required sections:"]
    for name, _ in DEFAULT_REQUIRED_ISSUE_SECTIONS:
        status = "present" if name in present else "missing"
        lines.append(f"- {name}: {status}")

    lines.append("")
    if report.missing_sections:
        lines.append("Missing sections:")
        lines.extend(f"- {name}" for name in report.missing_sections)
    else:
        lines.append("Missing sections: none")

    if report.warnings:
        lines.append("Warnings:")
        lines.extend(f"- {warning}" for warning in report.warnings)
    else:
        lines.append("Warnings: none")

    return "\n".join(lines)


def run_check_issue(args: argparse.Namespace) -> int:
    try:
        report = check_issue_file(Path(args.file))
    except FileNotFoundError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1

    print(render_issue_readiness_report(report))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "OMNI Auto Dev core skeleton. Describes what Auto Dev will "
            "eventually do; this skeleton takes no autonomous action."
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print a local-only skeleton summary of the planned Auto Dev system.",
    )

    subparsers = parser.add_subparsers(dest="command")
    init_run = subparsers.add_parser(
        "init-run",
        help="Create a local file-based Auto Dev run directory (STATE.json plus role packets).",
    )
    init_run.add_argument("--issue", type=int, required=True, help="GitHub issue number.")
    init_run.add_argument("--title", required=True, help="Issue title.")
    init_run.add_argument("--branch", default=None, help="Working branch for this run.")
    init_run.add_argument(
        "--implementer",
        default=DEFAULT_IMPLEMENTER,
        help=f"Implementer role name (default: {DEFAULT_IMPLEMENTER}).",
    )
    init_run.add_argument(
        "--reviewer",
        default=DEFAULT_REVIEWER,
        help=f"Reviewer role name (default: {DEFAULT_REVIEWER}).",
    )
    init_run.add_argument(
        "--output",
        default=None,
        help="Directory to create. Defaults to artifacts/autodev/runs/issue-<N>.",
    )
    init_run.add_argument(
        "--dry-run",
        dest="init_dry_run",
        action="store_true",
        help="Print what would be created without writing any files.",
    )

    check_issue = subparsers.add_parser(
        "check-issue",
        help="Check a local Markdown/text issue body file for required Auto Dev sections.",
    )
    check_issue.add_argument("--file", required=True, help="Path to a local issue body file.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "init-run":
        return run_init_run(args)

    if args.command == "check-issue":
        return run_check_issue(args)

    if args.dry_run:
        print(render_dry_run_summary(build_dry_run_summary()))
        return 0

    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
