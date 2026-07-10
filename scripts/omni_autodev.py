#!/usr/bin/env python3
"""
OMNI Auto Dev — core skeleton CLI (Phase 11).

Describes what Auto Dev would eventually do. Performs no autonomous
actions: no network calls, no LLM calls, no GitHub API calls, no
multi-step campaign execution.

Usage:
    python scripts/omni_autodev.py --help
    python scripts/omni_autodev.py --dry-run
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from omni.autodev.models import AutoDevDryRunSummary

PLANNED_FUTURE_LAYERS: list[str] = [
    "campaign YAML loading",
    "issue readiness scoring",
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
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.dry_run:
        print(render_dry_run_summary(build_dry_run_summary()))
        return 0

    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
