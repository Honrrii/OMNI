#!/usr/bin/env python3
"""Explicit supervised TestCube entry points. No default live command."""
from __future__ import annotations

import argparse
from dataclasses import asdict
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from omni.frontier.config import ClaudeProviderConfig, CodexProviderConfig
from omni.testcube.candidate_harness import run_supervised_trial
from omni.testcube.candidate_models import CANDIDATE_SCHEMA, EDIT_SCHEMA, strict_json, task_from_dict
from omni.testcube.candidate_providers import CandidateProvider, ProviderProcessResult
from omni.testcube.collector import _read_regular
from omni.testcube.collector_models import CollectorPolicy, CommandSpec, canonical_bytes
from omni.testcube.models import CandidatePolicy

LIVE_BANNER = """REAL CLAUDE CANDIDATE GENERATION: ENABLED
REAL CODEX CANDIDATE GENERATION: ENABLED
PROVIDERS: READ-ONLY
TRUSTED REPOSITORY: NO WRITE AUTHORITY
TESTCUBE ISOLATION: REQUIRED
AUTOMATIC MERGE: DISABLED
HUMAN REVIEW: REQUIRED"""


class FileResponseRunner:
    """Explicit fake pathway: inert files replace provider processes only."""
    def __init__(self, provider, raw):
        self.provider, self.raw = provider, raw

    def run(self, argv, **kwargs):
        if "--version" in argv:
            output = "fake-provider-v1"
        elif "auth" in argv:
            output = '{"loggedIn": true}'
        elif "login" in argv:
            output = "Logged in (fake)"
        else:
            output = self.raw
        return ProviderProcessResult(0, output, "", 0)


def load_inputs(task_path, commands_path, runtime_root):
    task = task_from_dict(strict_json(_read_regular(task_path, 128 * 1024)))
    raw_commands = strict_json(_read_regular(commands_path, 128 * 1024))
    if type(raw_commands) is not list:
        raise ValueError("commands must be a JSON list of CommandSpec objects")
    commands = []
    for record in raw_commands:
        record = dict(record)
        if type(record.get("argv")) is not list:
            raise ValueError("command argv must be a JSON list")
        record["argv"] = tuple(record["argv"])
        commands.append(CommandSpec(**record))
    p = CandidatePolicy(task.task_id, task.allowed_paths, task.required_tests,
                        forbidden_paths=task.forbidden_paths, required_validators=task.required_validators,
                        max_touched_files=task.max_touched_files, max_changed_lines=task.max_changed_lines)
    policy = CollectorPolicy(p, task.base_revision, str(runtime_root.resolve()), tuple(commands), max_patch_bytes=128 * 1024)
    task.validate_policy(policy)
    return task, policy


def build_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for command in ("validate-task", "fake-dual-candidate", "supervised-dual-candidate-live"):
        p = sub.add_parser(command)
        p.add_argument("--task", type=Path, required=True)
        p.add_argument("--commands", type=Path, required=True, help="Human-owned JSON list of trusted CommandSpecs")
        p.add_argument("--runtime-root", type=Path, default=Path(sys.prefix))
        if command == "validate-task":
            continue
        p.add_argument("--repo", type=Path, required=True)
        p.add_argument("--output-root", type=Path, required=True, help="Existing external root, outside repository/runtime")
        if command == "fake-dual-candidate":
            p.add_argument("--candidate-transport", choices=(EDIT_SCHEMA, CANDIDATE_SCHEMA), default=EDIT_SCHEMA,
                           help="Explicit version; legacy patch transport is for compatibility fixtures")
            p.add_argument("--claude-output", type=Path, required=True, help="Fake Claude JSON success envelope")
            p.add_argument("--codex-output", type=Path, required=True, help="Fake Codex candidate JSON")
        else:
            p.add_argument("--claude-executable", default="claude")
            p.add_argument("--codex-executable", default="codex")
            p.add_argument("--timeout-seconds", type=int, default=180)
            p.add_argument("--output-limit-bytes", type=int, default=400000)
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        task, policy = load_inputs(args.task, args.commands, args.runtime_root)
        if args.command == "validate-task":
            print("TASK_VALID: first-trial policy; zero provider calls")
            return 0
        if args.command == "fake-dual-candidate":
            providers = (
                CandidateProvider("claude", ClaudeProviderConfig(), runner=FileResponseRunner("claude", _read_regular(args.claude_output, 400000).decode())),
                CandidateProvider("codex", CodexProviderConfig(), runner=FileResponseRunner("codex", _read_regular(args.codex_output, 400000).decode())),
            )
        else:
            print(LIVE_BANNER, flush=True)
            providers = (
                CandidateProvider("claude", ClaudeProviderConfig("claude-live", args.claude_executable, args.timeout_seconds, args.output_limit_bytes), enable_live=True),
                CandidateProvider("codex", CodexProviderConfig("codex-live", args.codex_executable, args.timeout_seconds, args.output_limit_bytes), enable_live=True),
            )
        result = run_supervised_trial(task=task, source_repo=args.repo, output_root=args.output_root,
                                      policy=policy, providers=providers,
                                      candidate_transport=getattr(args, "candidate_transport", EDIT_SCHEMA))
        print(canonical_bytes(asdict(result)).decode(), end="")
        return 0 if result.outcome == "TRIAL_COMPLETE" else 1
    except (OSError, ValueError, TypeError, UnicodeError) as exc:
        print(f"INPUT_REJECTED: {type(exc).__name__}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
