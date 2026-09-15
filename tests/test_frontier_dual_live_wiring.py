"""
Phase 5 guard: `ShiftOrchestrator` runs one complete, bounded research shift
end to end with a *real-shaped* `ClaudeCodeAdapter` on one side and a
*real-shaped* `CodexAdapter` on the other — both the actual Phase 3/4B
adapter classes, each backed by an injected fake `ProcessRunner` instead of
a real subprocess. This is the automated, pre-live proof that
`ShiftOrchestrator` requires no Claude/Codex-specific branch to coordinate
two real providers simultaneously (see `omni/frontier/orchestrator.py`'s
module docstring: the orchestrator never imports either provider module and
never changes to accept one).

Distinct from the existing coverage this complements:
- `tests/test_frontier_orchestrator.py`'s `_RealShapedAdapter` tests prove
  archive *provenance* rendering across mock/real combinations using a thin
  wrapper around the deterministic mock agents — useful, but it never drives
  the actual `ClaudeCodeAdapter`/`CodexAdapter` prompt-building, schema, or
  failure-classification code paths.
- `tests/test_frontier_claude_provider.py` and
  `tests/test_frontier_codex_provider.py` each exercise one real adapter in
  isolation with a scripted single-envelope fake runner.

This module is the first to run *both* real adapter classes together
through the unmodified canonical stage machine, so it is the automated
evidence Issue 3 (Frontier: validate first bounded real Claude<->Codex
research exchange) requires before any billed real-provider invocation.

No network, no LLM calls, no real `claude`/`codex` process — every
subprocess call in this file is intercepted by a fake `ProcessRunner`.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from omni.frontier.claude_provider import ClaudeCodeAdapter
from omni.frontier.claude_provider import ProcessResult as ClaudeProcessResult
from omni.frontier.codex_provider import CodexAdapter
from omni.frontier.codex_provider import ProcessResult as CodexProcessResult
from omni.frontier.config import (
    CLAUDE_AGENT_ID,
    CODEX_AGENT_ID,
    PROVIDER_MODE_CLAUDE_LIVE,
    PROVIDER_MODE_CODEX_LIVE,
    ClaudeProviderConfig,
    CodexProviderConfig,
    FrontierLabConfig,
)
from omni.frontier.experiments import frontier_experiment_from_dict
from omni.frontier.orchestrator import PreflightResult, ShiftOrchestrator

_LINE_PATTERN = "- {key}: "


def _extract(text: str, key: str) -> str:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith(f"- {key}:"):
            return stripped.split(":", 1)[1].strip()
    raise AssertionError(f"no {key!r} line found in:\n{text}")


@dataclass
class _StageRoundAwareClaudeRunner:
    """Real-shaped fake for the `claude` subprocess: reads `stage`/`round`
    back out of the adapter's own trusted system prompt (the same envelope
    a real `claude -p --append-system-prompt ...` invocation would receive)
    and returns a schema-valid, stage-appropriate `structured_output` so a
    full multi-round shift can complete against the unmodified
    `ClaudeCodeAdapter.run_turn`. Mirrors
    `tests/test_frontier_claude_provider.py::_StageAwareFakeRunner`, extended
    to also branch on `round_number` so RESPOND alternates
    EXPERIMENT_PROPOSAL/RESPONSE the same way `MockClaudeAdapter` does.
    """

    calls: list[dict] = None

    def __post_init__(self):
        self.calls = []

    def run(self, argv, *, cwd, input_text, timeout) -> ClaudeProcessResult:
        self.calls.append({"argv": argv, "cwd": cwd, "input_text": input_text, "timeout": timeout})
        system_prompt = argv[argv.index("--append-system-prompt") + 1]
        stage = _extract(system_prompt, "stage")
        round_number = int(_extract(system_prompt, "round"))

        if stage == "INVESTIGATE":
            message_type = "HYPOTHESIS"
        elif stage == "RESPOND":
            message_type = "EXPERIMENT_PROPOSAL" if round_number <= 2 else "RESPONSE"
        elif stage == "EXPERIMENT_REPORT":
            message_type = "EXPERIMENT_RESULT"
        elif stage == "CONCLUDE":
            message_type = "CONCLUSION"
        else:
            raise AssertionError(f"unexpected stage {stage!r}")

        claim = f"Real-Claude-adapter-shaped content for stage {stage}, round {round_number}."
        if stage == "CONCLUDE":
            claim = f"SUPPORTED: {claim}"

        structured = {"message_type": message_type, "claim": claim}
        if stage == "EXPERIMENT_REPORT":
            structured["evidence"] = ["fake-runner-shaped evidence entry (dual-live wiring test)"]

        envelope = {"is_error": False, "subtype": "success", "structured_output": structured}
        return ClaudeProcessResult(
            returncode=0, stdout=json.dumps(envelope), stderr="", duration_seconds=0.01, timed_out=False
        )


@dataclass
class _StageRoundAwareCodexRunner:
    """Real-shaped fake for the `codex exec` subprocess: reads `stage`/
    `round` out of the combined prompt sent via stdin (`input_text`) — the
    same envelope a real `codex exec - --sandbox read-only ...` invocation
    would receive on stdin — and writes a schema-valid, stage-appropriate
    structured response to the `--output-last-message` path, exactly as the
    real `codex` CLI does. Mirrors `MockCodexAdapter`'s round-based
    convergence: CHALLENGE at round 1, CHALLENGE again through round <= 2 on
    REASSESS, REVIEW_FINDING once round > 2 (or during EXPERIMENT_REVIEW).
    """

    calls: list[dict] = None

    def __post_init__(self):
        self.calls = []

    def run(self, argv, *, cwd, input_text, timeout) -> CodexProcessResult:
        self.calls.append({"argv": argv, "cwd": cwd, "input_text": input_text, "timeout": timeout})
        stage = _extract(input_text, "stage")
        round_number = int(_extract(input_text, "round"))

        if stage == "CHALLENGE":
            message_type = "COUNTER_HYPOTHESIS"
        elif stage == "REASSESS":
            message_type = "CHALLENGE" if round_number <= 2 else "REVIEW_FINDING"
        elif stage == "EXPERIMENT_REVIEW":
            message_type = "REVIEW_FINDING"
        else:
            raise AssertionError(f"unexpected stage {stage!r}")

        structured = {
            "message_type": message_type,
            "claim": f"Real-Codex-adapter-shaped content for stage {stage}, round {round_number}.",
            "mechanism": "",
            "evidence": [],
            "uncertainties": [],
            "requested_action": "",
            "confidence": 0.4,
            "in_reply_to": None,
            "requested_control": None,
        }

        output_path = argv[argv.index("--output-last-message") + 1]
        Path(output_path).write_text(json.dumps(structured), encoding="utf-8")
        return CodexProcessResult(returncode=0, stdout="", stderr="", duration_seconds=0.01, timed_out=False)


def _dual_live_orchestrator(
    tmp_path, *, claude_runner=None, codex_runner=None, mission=None, **config_overrides
) -> tuple[ShiftOrchestrator, ClaudeCodeAdapter, CodexAdapter]:
    claude_adapter = ClaudeCodeAdapter(
        config=ClaudeProviderConfig(provider_mode=PROVIDER_MODE_CLAUDE_LIVE),
        cwd=Path("/tmp"),
        process_runner=claude_runner or _StageRoundAwareClaudeRunner(),
    )
    codex_adapter = CodexAdapter(
        config=CodexProviderConfig(provider_mode=PROVIDER_MODE_CODEX_LIVE),
        cwd=Path("/tmp"),
        process_runner=codex_runner or _StageRoundAwareCodexRunner(),
    )
    orchestrator = ShiftOrchestrator(
        config=FrontierLabConfig(**config_overrides),
        mission=mission,
        claude=claude_adapter,
        codex=codex_adapter,
        lab_root=tmp_path / ".omni-lab",
        preflight=lambda: PreflightResult(ready=True, status="DUAL_READY"),
    )
    return orchestrator, claude_adapter, codex_adapter


# ---------------------------------------------------------------------------
# Real-shaped + real-shaped wiring
# ---------------------------------------------------------------------------


def test_dual_real_shaped_adapters_run_through_canonical_stage_machine(tmp_path):
    orchestrator, claude_adapter, codex_adapter = _dual_live_orchestrator(tmp_path)
    report = orchestrator.run_mock_shift()

    assert report.final_state == "ARCHIVED"
    assert report.stopped_early is False
    assert report.mock is False

    types_in_order = [m.message_type for m in orchestrator.thread_messages]
    assert types_in_order == [
        "HYPOTHESIS",
        "COUNTER_HYPOTHESIS",
        "EXPERIMENT_PROPOSAL",
        "CHALLENGE",
        "RESPONSE",
        "REVIEW_FINDING",
        "EXPERIMENT_RESULT",
        "REVIEW_FINDING",
        "CONCLUSION",
    ]

    # Orchestrator-owned identity: sequence is strictly increasing, senders
    # alternate exactly per the requested stage (never provider-chosen).
    assert [m.sequence for m in orchestrator.thread_messages] == list(
        range(1, len(orchestrator.thread_messages) + 1)
    )
    senders = [m.from_agent for m in orchestrator.thread_messages]
    assert senders == [
        CLAUDE_AGENT_ID,
        CODEX_AGENT_ID,
        CLAUDE_AGENT_ID,
        CODEX_AGENT_ID,
        CLAUDE_AGENT_ID,
        CODEX_AGENT_ID,
        CLAUDE_AGENT_ID,
        CODEX_AGENT_ID,
        CLAUDE_AGENT_ID,
    ]


# ---------------------------------------------------------------------------
# Message routing: Claude -> mailbox/orchestrator -> Codex context, and back
# ---------------------------------------------------------------------------


def test_claude_message_routes_to_codex_via_mailbox_and_orchestration(tmp_path):
    orchestrator, claude_adapter, codex_adapter = _dual_live_orchestrator(tmp_path)
    orchestrator.run_mock_shift()

    hypothesis = next(m for m in orchestrator.thread_messages if m.message_type == "HYPOTHESIS")
    codex_runner = codex_adapter.process_runner
    challenge_call = codex_runner.calls[0]  # Codex's first turn is STAGE_CHALLENGE
    assert hypothesis.claim in challenge_call["input_text"]

    mailbox_item = next(
        item for item in orchestrator.mailbox.items if item.message.sequence == hypothesis.sequence
    )
    assert mailbox_item.recipient == CODEX_AGENT_ID
    assert mailbox_item.status == "PROCESSED"


def test_codex_message_routes_to_claude_via_mailbox_and_orchestration(tmp_path):
    orchestrator, claude_adapter, codex_adapter = _dual_live_orchestrator(tmp_path)
    orchestrator.run_mock_shift()

    counter_hypothesis = next(m for m in orchestrator.thread_messages if m.message_type == "COUNTER_HYPOTHESIS")
    claude_runner = claude_adapter.process_runner
    # Claude's second turn (index 1) is STAGE_RESPOND, round 2, which
    # receives the full thread_messages history including Codex's challenge.
    respond_call = claude_runner.calls[1]
    assert counter_hypothesis.claim in respond_call["input_text"]

    mailbox_item = next(
        item for item in orchestrator.mailbox.items if item.message.sequence == counter_hypothesis.sequence
    )
    assert mailbox_item.recipient == CLAUDE_AGENT_ID
    assert mailbox_item.status == "PROCESSED"


# ---------------------------------------------------------------------------
# Provenance: archive must report both participants as real
# ---------------------------------------------------------------------------


def test_archive_reports_both_claude_and_codex_as_real(tmp_path):
    orchestrator, claude_adapter, codex_adapter = _dual_live_orchestrator(tmp_path)
    report = orchestrator.run_mock_shift()

    conclusion_md = (report.archive_dir / "conclusion.md").read_text()
    assert "MOCK shift" not in conclusion_md
    assert "remained a deterministic MOCK" not in conclusion_md  # nobody stayed mocked
    assert f"real provider process for: {CLAUDE_AGENT_ID}, {CODEX_AGENT_ID}" in conclusion_md

    runtime_state = json.loads((report.runtime_dir / "state.json").read_text())
    assert runtime_state["mock"] is False


# ---------------------------------------------------------------------------
# Provider-call accounting
# ---------------------------------------------------------------------------


def test_provider_call_counts_reflect_both_participants(tmp_path):
    orchestrator, claude_adapter, codex_adapter = _dual_live_orchestrator(tmp_path)
    report = orchestrator.run_mock_shift()

    assert claude_adapter.provider_calls > 0
    assert codex_adapter.provider_calls > 0
    assert report.provider_calls == claude_adapter.provider_calls + codex_adapter.provider_calls

    claude_messages = [m for m in orchestrator.thread_messages if m.from_agent == CLAUDE_AGENT_ID]
    codex_messages = [m for m in orchestrator.thread_messages if m.from_agent == CODEX_AGENT_ID]
    assert len(claude_messages) == claude_adapter.provider_calls
    assert len(codex_messages) == codex_adapter.provider_calls


# ---------------------------------------------------------------------------
# Failure behavior: a failing real-shaped provider stops the shift safely
# ---------------------------------------------------------------------------


class _AlwaysFailingCodexRunner:
    def run(self, argv, *, cwd, input_text, timeout):
        return CodexProcessResult(returncode=1, stdout="", stderr="simulated codex infrastructure failure", duration_seconds=0.05, timed_out=False)


def test_one_real_provider_failing_stops_the_shift_safely_not_a_fabricated_success(tmp_path):
    orchestrator, claude_adapter, codex_adapter = _dual_live_orchestrator(
        tmp_path, codex_runner=_AlwaysFailingCodexRunner(), max_consecutive_agent_failures=2
    )
    report = orchestrator.run_mock_shift()

    assert report.final_state == "ARCHIVED"
    assert report.stopped_early is True
    assert "consecutive" in report.stop_reason or "failed" in report.stop_reason
    assert report.experiment is not None
    assert report.experiment.conclusion_state == "BLOCKED_BY_REQUIRED_EVIDENCE"
    failure_events = [e for e in report.events if e.event_type == "PROVIDER_FAILURE"]
    assert failure_events
    # Claude's real turn(s) still ran and were counted -- the failure was
    # Codex's alone, not silently attributed to or masking Claude's side.
    assert claude_adapter.provider_calls >= 1
    assert codex_adapter.provider_calls >= 1


# ---------------------------------------------------------------------------
# Conclusion integrity survives to durable archive
# ---------------------------------------------------------------------------


def test_validated_conclusion_state_survives_into_durable_archive(tmp_path):
    orchestrator, claude_adapter, codex_adapter = _dual_live_orchestrator(tmp_path)
    report = orchestrator.run_mock_shift()

    assert report.experiment.conclusion_state == "SUPPORTED"
    archived = frontier_experiment_from_dict(json.loads((report.archive_dir / "results.json").read_text()))
    assert archived.conclusion_state == "SUPPORTED"
    assert archived == report.experiment
    assert "Conclusion state: `SUPPORTED`" in (report.archive_dir / "conclusion.md").read_text()
