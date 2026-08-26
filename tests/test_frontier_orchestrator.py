"""
Phase 2B guard: `omni.frontier.orchestrator.ShiftOrchestrator` runs one
complete, deterministic MOCK research shift end to end using only
`MockClaudeAdapter`/`MockCodexAdapter`, and fails closed on every bounded
limit in `omni.frontier.config.FrontierLabConfig`.

This module is the Phase 2B end-to-end demonstration plus the required
failure-mode coverage. No network, no LLM calls, no GitHub API, no real
Claude Code or Codex process — every agent here is plain Python
(`omni/frontier/agents.py`, or a small in-file stub built the same way).
"""
from __future__ import annotations

import inspect
import json
from pathlib import Path

import pytest

from omni.frontier import agents as agents_module
from omni.frontier import orchestrator as orchestrator_module
from omni.frontier import state
from omni.frontier.agents import MockClaudeAdapter, MockCodexAdapter, ResearchTurnResult
from omni.frontier.config import FrontierLabConfig
from omni.frontier.events import EVENT_TYPES
from omni.frontier.experiments import FrontierExperiment, FrontierResearchScore, frontier_experiment_from_dict
from omni.frontier.mailbox import MailboxRejectionError
from omni.frontier.orchestrator import (
    ShiftOrchestrator,
    allocate_thread_id,
    ensure_multi_agent_participation,
    finalize_experiment_conclusion,
)
from omni.frontier.protocol import FrontierMessage

CREATED_AT = "2026-08-26T00:00:00Z"


def _orchestrator(tmp_path, **config_overrides) -> ShiftOrchestrator:
    config = FrontierLabConfig(**config_overrides)
    return ShiftOrchestrator(
        config=config,
        claude=MockClaudeAdapter(),
        codex=MockCodexAdapter(),
        lab_root=tmp_path / ".omni-lab",
    )


# ---------------------------------------------------------------------------
# Required end-to-end Phase 2B demonstration
# ---------------------------------------------------------------------------


def test_end_to_end_mock_shift(tmp_path):
    orch = _orchestrator(tmp_path)
    report = orch.run_mock_shift()

    # Terminal state and boundedness.
    assert report.final_state == state.ARCHIVED
    assert report.stopped_early is False
    assert report.turns_used <= orch.config.max_agent_turns
    assert report.rounds_completed <= orch.config.max_debate_rounds

    # Messages use FrontierMessage; experiment uses FrontierExperiment.
    for message in orch.thread_messages:
        assert isinstance(message, FrontierMessage)
    assert isinstance(report.experiment, FrontierExperiment)
    assert report.experiment.status == "COMPLETE"
    assert report.experiment.conclusion_state is not None

    # Expected message shape of the demonstrated exchange.
    types_in_order = [m.message_type for m in orch.thread_messages]
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

    # Ordering is deterministic: message sequence and event sequence are
    # both strictly increasing with no gaps.
    assert [m.sequence for m in orch.thread_messages] == list(range(1, len(orch.thread_messages) + 1))
    event_sequences = [event.sequence for event in report.events]
    assert event_sequences == list(range(1, len(report.events) + 1))

    # Every STATE_CHANGED event pair reflects a legal transition (re-derived
    # independently of the orchestrator's own bookkeeping).
    state_changes = [event.detail for event in report.events if event.event_type == "STATE_CHANGED"]
    cursor = state.IDLE
    for requested in state_changes:
        cursor = state.transition(cursor, requested)  # raises IllegalStateTransition if not legal
    assert cursor == state.ARCHIVED

    # Mailbox routed every message and everything was processed.
    assert len(report.mailbox_items) == len(orch.thread_messages)
    assert all(item.status == "PROCESSED" for item in report.mailbox_items)

    # Archive was created and can be read back.
    assert report.archive_dir.is_dir()
    for name in ("hypothesis.md", "messages.jsonl", "experiment_plan.md", "results.json", "conclusion.md"):
        assert (report.archive_dir / name).exists(), name
    assert (report.archive_dir / "evidence").is_dir()

    restored = frontier_experiment_from_dict(json.loads((report.archive_dir / "results.json").read_text()))
    assert restored == report.experiment

    restored_messages = [
        json.loads(line) for line in (report.archive_dir / "messages.jsonl").read_text().splitlines() if line
    ]
    assert [m["message_type"] for m in restored_messages] == types_in_order

    # Runtime snapshot exists and round-trips too.
    assert report.runtime_dir.is_dir()
    for name in ("state.json", "mailbox.jsonl", "events.jsonl"):
        assert (report.runtime_dir / name).exists(), name
    runtime_state = json.loads((report.runtime_dir / "state.json").read_text())
    assert runtime_state["state"] == state.ARCHIVED
    assert runtime_state["mock"] is True

    # Trusted OMNI state was not modified: the shift ran entirely against
    # the tmp_path lab_root, so the real repository's .omni-lab/ archive
    # never gained this thread's directory.
    real_repo_root = Path(__file__).resolve().parents[1]
    assert not (real_repo_root / ".omni-lab" / "experiments" / report.thread_id).exists()
    assert not (real_repo_root / ".omni-lab" / "runtime" / report.thread_id).exists()

    # No model process/API was invoked.
    assert report.provider_calls == 0
    assert report.mock is True


def test_no_model_process_or_api_referenced_in_orchestration_source():
    """Static guard: the orchestrator and agent modules must never gain a
    subprocess/network call path that could invoke a real model."""
    banned_tokens = (
        "import subprocess",
        "subprocess.",
        "os.system",
        "requests.",
        "urllib.request",
        "http.client",
        "socket.socket",
        "import anthropic",
        "import openai",
    )
    source = inspect.getsource(orchestrator_module) + inspect.getsource(agents_module)
    for token in banned_tokens:
        assert token not in source, f"found banned token {token!r} in Phase 2B orchestration source"


# ---------------------------------------------------------------------------
# Required failure-mode tests
# ---------------------------------------------------------------------------


def test_illegal_state_transition_rejected_inside_finalize(tmp_path):
    orch = _orchestrator(tmp_path)
    orch.thread_id = "OMNI-FRONTIER-9999"
    orch.state = state.CLAUDE_INVESTIGATING  # mid-shift, not CONCLUSION or terminal
    with pytest.raises(state.IllegalStateTransition):
        orch._finalize()


def test_malformed_frontier_message_from_a_bad_adapter_is_a_bounded_failure(tmp_path):
    class MalformedMessageClaude:
        agent_id = "claude"

        def run_turn(self, context):
            # message_type is not in MESSAGE_TYPES -> FrontierMessage raises
            # ValueError at construction, before a ResearchTurnResult even
            # exists.
            FrontierMessage(
                thread_id=context.thread_id,
                sequence=context.next_sequence,
                from_agent="claude",
                to_agent="codex",
                message_type="NOT_A_REAL_TYPE",
                claim="x",
                created_at=context.created_at,
            )
            raise AssertionError("unreachable")

    orch = ShiftOrchestrator(
        config=FrontierLabConfig(max_consecutive_agent_failures=1),
        claude=MalformedMessageClaude(),
        codex=MockCodexAdapter(),
        lab_root=tmp_path / ".omni-lab",
    )
    report = orch.run_mock_shift()
    assert report.final_state == state.ARCHIVED
    assert report.stopped_early is True
    assert "failed" in report.stop_reason


def test_wrong_recipient_rejected_by_orchestrator(tmp_path):
    class WrongRecipientClaude:
        agent_id = "claude"

        def run_turn(self, context):
            message = FrontierMessage(
                thread_id=context.thread_id,
                sequence=context.next_sequence,
                from_agent="claude",
                to_agent="human",  # not a configured participant
                message_type="HYPOTHESIS",
                claim="x",
                created_at=context.created_at,
            )
            return ResearchTurnResult(ok=True, message=message)

    orch = ShiftOrchestrator(
        config=FrontierLabConfig(max_invalid_messages=1),
        claude=WrongRecipientClaude(),
        codex=MockCodexAdapter(),
        lab_root=tmp_path / ".omni-lab",
    )
    report = orch.run_mock_shift()
    assert report.stopped_early is True
    assert report.final_state == state.ARCHIVED
    assert report.invalid_message_count >= 1
    rejected = [e for e in report.events if e.event_type == "MESSAGE_REJECTED"]
    assert rejected


def test_duplicate_message_rejected_by_mailbox_directly():
    from omni.frontier.mailbox import Mailbox

    mailbox = Mailbox(participants=("claude", "codex"))
    message = FrontierMessage(
        thread_id="OMNI-FRONTIER-0001", sequence=1, from_agent="claude", to_agent="codex",
        message_type="HYPOTHESIS", claim="x", created_at=CREATED_AT,
    )
    mailbox.deliver(message)
    with pytest.raises(MailboxRejectionError):
        mailbox.deliver(message)


def test_out_of_order_message_rejected_by_mailbox_directly():
    from omni.frontier.mailbox import Mailbox

    mailbox = Mailbox(participants=("claude", "codex"))
    message = FrontierMessage(
        thread_id="OMNI-FRONTIER-0001", sequence=5, from_agent="claude", to_agent="codex",
        message_type="HYPOTHESIS", claim="x", created_at=CREATED_AT,
    )
    with pytest.raises(MailboxRejectionError):
        mailbox.deliver(message)


def test_invalid_experiment_id_rejected(tmp_path):
    orch = _orchestrator(tmp_path)
    with pytest.raises(ValueError):
        orch.run_mock_shift(thread_id="not-a-valid-id")


def test_max_debate_rounds_reached_yields_budget_exhausted(tmp_path):
    orch = _orchestrator(tmp_path, max_debate_rounds=2)
    report = orch.run_mock_shift()
    assert report.final_state == state.ARCHIVED
    assert report.stopped_early is True
    assert "max_debate_rounds" in report.stop_reason
    assert report.experiment.conclusion_state == "BLOCKED_BY_REQUIRED_EVIDENCE"
    budget_events = [e for e in report.events if e.event_type == "BUDGET_EXHAUSTED"]
    assert budget_events


def test_max_agent_turns_reached_yields_budget_exhausted(tmp_path):
    orch = _orchestrator(tmp_path, max_agent_turns=3)
    report = orch.run_mock_shift()
    assert report.final_state == state.ARCHIVED
    assert report.stopped_early is True
    assert "max_agent_turns" in report.stop_reason
    assert report.turns_used <= 4  # never runs far past the configured budget


def test_repeated_mock_agent_failure_causes_bounded_stop(tmp_path):
    class AlwaysFailsClaude:
        agent_id = "claude"

        def run_turn(self, context):
            return ResearchTurnResult(ok=False, error="simulated infrastructure failure")

    orch = ShiftOrchestrator(
        config=FrontierLabConfig(max_consecutive_agent_failures=2),
        claude=AlwaysFailsClaude(),
        codex=MockCodexAdapter(),
        lab_root=tmp_path / ".omni-lab",
    )
    report = orch.run_mock_shift()
    assert report.final_state == state.ARCHIVED
    assert report.stopped_early is True
    assert report.turns_used == 2  # bounded, not infinite
    assert "consecutive" in report.stop_reason


def test_adapter_attempts_unsupported_action_is_a_bounded_failure(tmp_path):
    class RogueClaude:
        agent_id = "claude"

        def run_turn(self, context):
            message = FrontierMessage(
                thread_id=context.thread_id, sequence=context.next_sequence, from_agent="claude",
                to_agent="codex", message_type="HYPOTHESIS", claim="x", created_at=context.created_at,
            )
            # Not in ALLOWED_CONTROL_REQUESTS -> raises inside this call.
            return ResearchTurnResult(ok=True, message=message, requested_control="DISABLE_SAFETY_STOP")

    orch = ShiftOrchestrator(
        config=FrontierLabConfig(max_consecutive_agent_failures=1),
        claude=RogueClaude(),
        codex=MockCodexAdapter(),
        lab_root=tmp_path / ".omni-lab",
    )
    report = orch.run_mock_shift()
    assert report.final_state == state.ARCHIVED
    assert report.stopped_early is True
    # The orchestrator's own live state was never touched by the rogue request.
    assert orch.config.max_consecutive_agent_failures == 1


def test_archive_cannot_be_finalized_without_required_conclusion_data():
    experiment = FrontierExperiment(
        experiment_id="OMNI-FRONTIER-0001",
        title="t",
        hypothesis="h",
        scoring=FrontierResearchScore(1, 1, 1, 1, 1, 1, 1, 1),
        created_at=CREATED_AT,
    )
    with pytest.raises(ValueError):
        finalize_experiment_conclusion(
            experiment,
            conclusion_state="CONFIRMED",
            experiment_plan="did a thing",
            limitations=[],  # required non-empty for a concluded experiment
            remaining_uncertainty="none",
            recommended_next_action="ship it",
            evidence=["some/file.py"],
        )


def test_event_ordering_remains_stable_across_a_stopped_shift(tmp_path):
    orch = _orchestrator(tmp_path, max_debate_rounds=1)
    report = orch.run_mock_shift()
    sequences = [event.sequence for event in report.events]
    assert sequences == sorted(sequences)
    assert len(sequences) == len(set(sequences))
    assert sequences == list(range(1, len(sequences) + 1))


def test_one_agent_cannot_silently_certify_its_own_implementation():
    only_claude = [
        FrontierMessage(thread_id="OMNI-FRONTIER-0001", sequence=1, from_agent="claude", to_agent="codex", message_type="HYPOTHESIS", claim="a", created_at=CREATED_AT),
        FrontierMessage(thread_id="OMNI-FRONTIER-0001", sequence=2, from_agent="claude", to_agent="codex", message_type="CONCLUSION", claim="b", created_at=CREATED_AT),
    ]
    with pytest.raises(ValueError):
        ensure_multi_agent_participation(only_claude, ("claude", "codex"))

    both_spoke = only_claude + [
        FrontierMessage(thread_id="OMNI-FRONTIER-0001", sequence=3, from_agent="codex", to_agent="claude", message_type="REVIEW_FINDING", claim="c", created_at=CREATED_AT),
    ]
    ensure_multi_agent_participation(both_spoke, ("claude", "codex"))  # does not raise


def test_safety_stop_is_terminal(tmp_path):
    class SafetyViolatingClaude:
        agent_id = "claude"

        def run_turn(self, context):
            message = FrontierMessage(
                thread_id=context.thread_id, sequence=context.next_sequence, from_agent="claude",
                to_agent="codex", message_type="HYPOTHESIS",
                claim="We should force push to main to land this quickly.",
                created_at=context.created_at,
            )
            return ResearchTurnResult(ok=True, message=message)

    orch = ShiftOrchestrator(
        config=FrontierLabConfig(),
        claude=SafetyViolatingClaude(),
        codex=MockCodexAdapter(),
        lab_root=tmp_path / ".omni-lab",
    )
    report = orch.run_mock_shift()

    assert report.final_state == state.ARCHIVED
    safety_stop_events = [e for e in report.events if e.event_type == "SAFETY_STOP"]
    assert len(safety_stop_events) == 1
    safety_index = report.events.index(safety_stop_events[0])
    # Nothing acts (no further agent turns) after the safety stop fires.
    assert all(
        event.event_type != "AGENT_TURN_STARTED" for event in report.events[safety_index + 1 :]
    )
    # SAFETY_STOP itself only ever leads to ARCHIVED (re-check against the
    # shared state table, not just this orchestrator run).
    assert state.TRANSITIONS[state.SAFETY_STOP] == frozenset({state.ARCHIVED})


# ---------------------------------------------------------------------------
# allocate_thread_id
# ---------------------------------------------------------------------------


def test_allocate_thread_id_starts_at_0001_for_an_empty_lab(tmp_path):
    assert allocate_thread_id(tmp_path / ".omni-lab") == "OMNI-FRONTIER-0001"


def test_allocate_thread_id_continues_past_existing_experiments(tmp_path):
    lab_root = tmp_path / ".omni-lab"
    (lab_root / "experiments" / "OMNI-FRONTIER-0007").mkdir(parents=True)
    (lab_root / "runtime" / "OMNI-FRONTIER-0003").mkdir(parents=True)
    assert allocate_thread_id(lab_root) == "OMNI-FRONTIER-0008"


def test_all_event_types_used_by_a_full_shift_are_declared(tmp_path):
    orch = _orchestrator(tmp_path)
    report = orch.run_mock_shift()
    seen_types = {event.event_type for event in report.events}
    assert seen_types <= set(EVENT_TYPES)
    assert "SHIFT_STARTED" in seen_types
    assert "ARCHIVE_WRITTEN" in seen_types
    assert "SHIFT_COMPLETED" in seen_types
