#!/usr/bin/env python3
"""
OMNI Codex/Claude handoff packet generator.

Produces a compact Markdown "handoff packet" that gives Codex or Claude the
right context for one scoped engineering task, without pasting large amounts of
repo history. The packet is meant to be copied straight into a chat.

Hard guarantees:
  - Standard library only. No LLM calls, no GitHub API, no network.
  - Works offline and fails gracefully outside a git repository (git-derived
    fields degrade to "unknown"/"n/a" instead of crashing).
  - Read-only against the repository. The only thing written is the output
    file (when ``--output`` is given); otherwise the packet goes to stdout.

Usage:
    python scripts/omni_handoff_packet.py \
        --task "Phase 11 Stage 9B3D3 process-count feasibility audit" \
        --branch "omni/phase11-stage9b3d3-process-count-feasibility-audit" \
        --scope "Audit process_count enforcement feasibility; do not implement RLIMIT_NPROC yet" \
        --output /tmp/omni_handoff.md

Token-minimized mode:
    add ``--concise`` to trim recent commits and drop long boilerplate.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Areas OMNI branches must not touch unless only referenced in docs/examples.
# These mirror the standing workflow constraints and are used as the default
# "forbidden" list when the caller does not pass --forbid.
DEFAULT_FORBIDDEN = [
    "Sandbox implementation (backend/app/sandbox/**)",
    "UI / frontend",
    "ML model code",
    "ROS export",
    "Visual Bay",
    "Mission graph",
]

DEFAULT_FIRST_COMMANDS = [
    "git status --short --branch",
    "git log --oneline -5",
]

DEFAULT_TEST_COMMANDS = [
    "PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest tests -q",
]

DEFAULT_CHECKLIST = [
    "Diagnosis / design summary shown",
    "Proposed diff shown",
    "Test results shown",
    "`git diff --stat` shown",
    "`git status --short --branch` shown",
]


def _git(args: list[str]) -> str | None:
    """Run a read-only git command from ROOT.

    Returns stripped stdout, or ``None`` when git is unavailable, the command
    fails, or we are not inside a git repository. Never raises.
    """
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
            timeout=15,
        )
    except (FileNotFoundError, subprocess.SubprocessError, OSError):
        return None
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def _in_git_repo() -> bool:
    return _git(["rev-parse", "--is-inside-work-tree"]) == "true"


def _current_branch() -> str | None:
    return _git(["rev-parse", "--abbrev-ref", "HEAD"]) or None


def _repo_status() -> str:
    status = _git(["status", "--short", "--branch"])
    if status is None:
        return "n/a (not a git repository)"
    return status or "(clean working tree)"


def _recent_commits(count: int) -> list[str]:
    log = _git(["log", f"-{count}", "--oneline"])
    if not log:
        return []
    return log.splitlines()


def _last_merged_checkpoint() -> str:
    merge = _git(["log", "--merges", "-1", "--oneline"])
    if merge:
        return merge
    latest = _git(["log", "-1", "--oneline"])
    return latest or "n/a (not a git repository)"


def _md_list(items: list[str], *, ordered: bool = False, checkbox: bool = False) -> str:
    if not items:
        return "_(none provided)_\n"
    lines = []
    for index, item in enumerate(items, start=1):
        if checkbox:
            prefix = "- [ ]"
        elif ordered:
            prefix = f"{index}."
        else:
            prefix = "-"
        lines.append(f"{prefix} {item}")
    return "\n".join(lines) + "\n"


def _code_block(lines: list[str], lang: str = "bash") -> str:
    body = "\n".join(lines) if lines else "# (none)"
    return f"```{lang}\n{body}\n```\n"


def build_packet(args: argparse.Namespace) -> str:
    branch = args.branch or _current_branch() or "unknown"
    commit_count = 3 if args.concise else args.commits
    commits = _recent_commits(commit_count)
    forbidden = args.forbid or DEFAULT_FORBIDDEN
    relevant = args.file or []
    first_commands = args.first_command or DEFAULT_FIRST_COMMANDS
    test_commands = args.test_command or DEFAULT_TEST_COMMANDS
    checklist = args.checklist or DEFAULT_CHECKLIST

    parts: list[str] = []
    parts.append(f"# OMNI Handoff Packet — {args.task}\n")
    parts.append(f"_Generated {date.today().isoformat()} for Codex/Claude. Paste this whole block into the chat._\n")

    parts.append("## Current branch\n")
    parts.append(f"`{branch}`\n")

    parts.append("## Recent merged checkpoint\n")
    parts.append(f"`{_last_merged_checkpoint()}`\n")

    if not args.concise:
        parts.append("## Repo status\n")
        parts.append(_code_block([_repo_status()], lang="text"))

    parts.append("## Recent commits\n")
    parts.append(_code_block(commits, lang="text") if commits else "_(no git history available)_\n")

    parts.append("## Scope\n")
    parts.append(f"{args.scope or '_(scope not provided)_'}\n")

    parts.append("## Non-goals / forbidden areas\n")
    parts.append("Do not modify these unless they are only referenced in docs/examples:\n")
    parts.append(_md_list(forbidden))

    parts.append("## Relevant files\n")
    parts.append(_md_list(relevant))

    parts.append("## First commands to run (before editing)\n")
    parts.append(_code_block(first_commands))

    parts.append("## Test commands (after editing)\n")
    parts.append(_code_block(test_commands))

    parts.append("## Do-not-commit-until checklist\n")
    parts.append(_md_list(checklist, checkbox=True))

    if not args.concise:
        parts.append("## Reporting format for Codex/Claude\n")
        parts.append(
            "Reply with, in order:\n\n"
            "1. Diagnosis / design summary\n"
            "2. Proposed diff\n"
            "3. Test results\n"
            "4. `git diff --stat`\n"
            "5. `git status --short --branch`\n"
        )

    return "\n".join(parts).rstrip() + "\n"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate a compact Codex/Claude handoff packet for one scoped OMNI task.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--task", required=True, help="Task title (e.g. 'Stage 9B3D3 process-count feasibility audit').")
    parser.add_argument("--branch", default=None, help="Working branch. Defaults to the current git branch.")
    parser.add_argument("--scope", default=None, help="One or two sentences describing what is in scope.")
    parser.add_argument(
        "--forbid",
        action="append",
        default=None,
        metavar="AREA",
        help="Forbidden area (repeatable). Overrides the default OMNI forbidden list.",
    )
    parser.add_argument(
        "--file",
        action="append",
        default=None,
        metavar="PATH",
        help="Relevant file or glob likely to matter for the task (repeatable).",
    )
    parser.add_argument(
        "--first-command",
        action="append",
        default=None,
        metavar="CMD",
        help="Command to run before editing (repeatable). Overrides defaults.",
    )
    parser.add_argument(
        "--test-command",
        action="append",
        default=None,
        metavar="CMD",
        help="Command to run after editing (repeatable). Overrides defaults.",
    )
    parser.add_argument(
        "--checklist",
        action="append",
        default=None,
        metavar="ITEM",
        help="Do-not-commit-until checklist item (repeatable). Overrides defaults.",
    )
    parser.add_argument("--commits", type=int, default=5, help="How many recent commits to include (default 5).")
    parser.add_argument(
        "--concise",
        action="store_true",
        help="Token-minimized mode: fewer commits, drop repo status and reporting boilerplate.",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Write the packet to this path. Defaults to stdout.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if not _in_git_repo():
        print(
            "warning: not inside a git repository; git-derived fields will be 'unknown'/'n/a'.",
            file=sys.stderr,
        )
    packet = build_packet(args)
    if args.output:
        out_path = Path(args.output)
        try:
            out_path.write_text(packet, encoding="utf-8")
        except OSError as error:
            print(f"error: could not write {out_path}: {error}", file=sys.stderr)
            return 1
        print(f"Handoff packet written to {out_path} ({len(packet)} chars)")
    else:
        sys.stdout.write(packet)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
