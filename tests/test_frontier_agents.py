"""
Phase 2B guard: the provider-neutral ResearchAgent interface
(omni/frontier/agents.py) and the deterministic MockClaudeAdapter /
MockCodexAdapter. Confirms both mocks are pure functions of their input
context — same context in, same FrontierMessage-carrying result out — and
that ResearchTurnResult fails closed on an unsupported control request.
No network, no LLM calls, no model process: both adapters are plain Python.
"""
from __future__ import annotations

import pytest

from omni.frontier.agents import (
    ALLOWED_CONTROL_REQUESTS,
    STAGE_CHALLENGE,
    STAGE_CONCLUDE,
    STAGE_EXPERIMENT_REPORT,
    STAGE_EXPERIMENT_REVIEW,
    STAGE_INVESTIGATE,
    STAGE_REASSESS,
    STAGE_RESPOND,
    MockClaudeAdapter,
    MockCodexAdapter,
    ResearchTurnContext,
    ResearchTurnResult,
)
from omni.frontier.config import DEFAULT_LAB_CONFIG
from omni.frontier.protocol import FrontierMessage

CREATED_AT = "2026-08-26T00:00:00Z"
THREAD_ID = "OMNI-FRONTIER-0001"


def _context(stage: str, *, round_number: int = 1, next_sequence: int = 1, messages: tuple = ()) -> ResearchTurnContext:
    return ResearchTurnContext(
        thread_id=THREAD_ID,
        stage=stage,
        state="CLAUDE_INVESTIGATING",
        round_number=round_number,
        turn_number=next_sequence,
        next_sequence=next_sequence,
        created_at=CREATED_AT,
        thread_messages=messages,
        experiment_snapshot=None,
        config=DEFAULT_LAB_CONFIG,
    )


# ---------------------------------------------------------------------------
# ResearchTurnResult contract
# ---------------------------------------------------------------------------


def test_ok_result_requires_a_message():
    with pytest.raises(ValueError):
        ResearchTurnResult(ok=True, message=None)


def test_failed_result_does_not_require_a_message():
    result = ResearchTurnResult(ok=False, error="simulated")
    assert result.message is None


def test_unsupported_control_request_fails_closed():
    message = FrontierMessage(
        thread_id=THREAD_ID, sequence=1, from_agent="claude", to_agent="codex",
        message_type="HYPOTHESIS", claim="x", created_at=CREATED_AT,
    )
    with pytest.raises(ValueError):
        ResearchTurnResult(ok=True, message=message, requested_control="DISABLE_SAFETY_STOP")
    with pytest.raises(ValueError):
        ResearchTurnResult(ok=True, message=message, requested_control="INCREASE_MAX_AGENT_TURNS")


def test_allowed_control_request_is_only_escalate_to_human():
    assert ALLOWED_CONTROL_REQUESTS == frozenset({"ESCALATE_TO_HUMAN"})
    message = FrontierMessage(
        thread_id=THREAD_ID, sequence=1, from_agent="claude", to_agent="codex",
        message_type="ESCALATE_TO_HUMAN", claim="x", created_at=CREATED_AT,
    )
    result = ResearchTurnResult(ok=True, message=message, requested_control="ESCALATE_TO_HUMAN")
    assert result.requested_control == "ESCALATE_TO_HUMAN"


def test_context_rejects_unknown_stage():
    with pytest.raises(ValueError):
        _context("NOT_A_REAL_STAGE")


# ---------------------------------------------------------------------------
# MockClaudeAdapter — deterministic, pure function of context
# ---------------------------------------------------------------------------


def test_mock_claude_investigate_emits_hypothesis():
    adapter = MockClaudeAdapter()
    result = adapter.run_turn(_context(STAGE_INVESTIGATE, round_number=1, next_sequence=1))
    assert result.ok
    assert result.message.message_type == "HYPOTHESIS"
    assert result.message.from_agent == "claude"
    assert result.message.to_agent == "codex"
    assert result.message.thread_id == THREAD_ID
    assert result.message.sequence == 1


def test_mock_claude_is_pure_same_context_same_output():
    adapter = MockClaudeAdapter()
    ctx = _context(STAGE_INVESTIGATE, round_number=1, next_sequence=1)
    first = adapter.run_turn(ctx)
    second = adapter.run_turn(ctx)
    assert first.message == second.message


def test_mock_claude_respond_round2_proposes_experiment_round3_responds():
    adapter = MockClaudeAdapter()
    round2 = adapter.run_turn(_context(STAGE_RESPOND, round_number=2, next_sequence=3))
    assert round2.message.message_type == "EXPERIMENT_PROPOSAL"
    round3 = adapter.run_turn(_context(STAGE_RESPOND, round_number=3, next_sequence=5))
    assert round3.message.message_type == "RESPONSE"


def test_mock_claude_experiment_report_marks_evidence_as_mock():
    adapter = MockClaudeAdapter()
    result = adapter.run_turn(_context(STAGE_EXPERIMENT_REPORT, round_number=3, next_sequence=7))
    assert result.message.message_type == "EXPERIMENT_RESULT"
    assert any("MOCK" in item for item in result.message.evidence)


def test_mock_claude_conclude_emits_conclusion():
    adapter = MockClaudeAdapter()
    result = adapter.run_turn(_context(STAGE_CONCLUDE, round_number=3, next_sequence=9))
    assert result.message.message_type == "CONCLUSION"


def test_mock_claude_unscripted_stage_fails_without_raising():
    adapter = MockClaudeAdapter()
    result = adapter.run_turn(_context(STAGE_CHALLENGE))  # Codex's stage, not Claude's
    assert result.ok is False
    assert result.message is None


# ---------------------------------------------------------------------------
# MockCodexAdapter — adversarial by construction
# ---------------------------------------------------------------------------


def test_mock_codex_challenge_emits_counter_hypothesis():
    adapter = MockCodexAdapter()
    result = adapter.run_turn(_context(STAGE_CHALLENGE, round_number=1, next_sequence=2))
    assert result.ok
    assert result.message.message_type == "COUNTER_HYPOTHESIS"
    assert result.message.from_agent == "codex"
    assert result.message.to_agent == "claude"


def test_mock_codex_reassess_round2_challenges_round3_converges():
    adapter = MockCodexAdapter()
    round2 = adapter.run_turn(_context(STAGE_REASSESS, round_number=2, next_sequence=4))
    assert round2.message.message_type == "CHALLENGE"
    round3 = adapter.run_turn(_context(STAGE_REASSESS, round_number=3, next_sequence=6))
    assert round3.message.message_type == "REVIEW_FINDING"


def test_mock_codex_is_adversarial_not_immediately_agreeable():
    """Round 1 must never converge — see FRONTIER_RESEARCH_PROTOCOL.md's
    evidence discipline: agreement should follow an attempted falsification,
    not precede one."""
    from omni.frontier.agents import CONVERGENCE_MESSAGE_TYPES

    adapter = MockCodexAdapter()
    result = adapter.run_turn(_context(STAGE_CHALLENGE, round_number=1, next_sequence=2))
    assert result.message.message_type not in CONVERGENCE_MESSAGE_TYPES


def test_mock_codex_experiment_review_converges():
    adapter = MockCodexAdapter()
    result = adapter.run_turn(_context(STAGE_EXPERIMENT_REVIEW, round_number=3, next_sequence=8))
    assert result.message.message_type == "REVIEW_FINDING"


def test_mock_codex_unscripted_stage_fails_without_raising():
    adapter = MockCodexAdapter()
    result = adapter.run_turn(_context(STAGE_INVESTIGATE))  # Claude's stage, not Codex's
    assert result.ok is False
    assert result.message is None


def test_context_last_message_from_returns_most_recent():
    hyp = FrontierMessage(thread_id=THREAD_ID, sequence=1, from_agent="claude", to_agent="codex", message_type="HYPOTHESIS", claim="a", created_at=CREATED_AT)
    counter = FrontierMessage(thread_id=THREAD_ID, sequence=2, from_agent="codex", to_agent="claude", message_type="COUNTER_HYPOTHESIS", claim="b", created_at=CREATED_AT)
    ctx = _context(STAGE_RESPOND, round_number=2, next_sequence=3, messages=(hyp, counter))
    assert ctx.last_message_from("codex") is counter
    assert ctx.last_message_from("claude") is hyp
    assert ctx.last_message_from("human") is None
