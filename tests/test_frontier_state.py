"""
Phase 2B guard: the Frontier Research Lab orchestration state machine
(omni/frontier/state.py) only allows the explicitly listed transitions,
fails closed on anything else, and every declared state has an entry in
TRANSITIONS. No network, no LLM calls, no model process — this module is
plain data plus one pure function.
"""
from __future__ import annotations

import pytest

from omni.frontier import state


def test_every_state_has_a_transitions_entry():
    assert set(state.TRANSITIONS) == state.ALL_STATES


def test_idle_only_transitions_to_shift_starting():
    assert state.transition(state.IDLE, state.SHIFT_STARTING) == state.SHIFT_STARTING
    with pytest.raises(state.IllegalStateTransition):
        state.transition(state.IDLE, state.CLAUDE_INVESTIGATING)


@pytest.mark.parametrize(
    "current,requested",
    [
        (state.SHIFT_STARTING, state.RESEARCH_TRIAGE),
        (state.RESEARCH_TRIAGE, state.CLAUDE_INVESTIGATING),
        (state.CLAUDE_INVESTIGATING, state.AWAITING_CODEX_REVIEW),
        (state.AWAITING_CODEX_REVIEW, state.CODEX_CHALLENGING),
        (state.CODEX_CHALLENGING, state.AWAITING_CLAUDE_RESPONSE),
        (state.CODEX_CHALLENGING, state.EXPERIMENT_VERIFICATION),
        (state.AWAITING_CLAUDE_RESPONSE, state.CLAUDE_RESPONDING),
        (state.CLAUDE_RESPONDING, state.AWAITING_CODEX_REASSESSMENT),
        (state.AWAITING_CODEX_REASSESSMENT, state.CODEX_REASSESSING),
        (state.CODEX_REASSESSING, state.AWAITING_CLAUDE_RESPONSE),
        (state.CODEX_REASSESSING, state.EXPERIMENT_VERIFICATION),
        (state.EXPERIMENT_VERIFICATION, state.CONCLUSION),
        (state.CONCLUSION, state.ARCHIVED),
    ],
)
def test_legal_happy_path_transitions(current, requested):
    assert state.transition(current, requested) == requested


@pytest.mark.parametrize(
    "interruption",
    [state.BLOCKED, state.SAFETY_STOP, state.BUDGET_EXHAUSTED, state.HUMAN_ESCALATION, state.FAILED_INFRASTRUCTURE],
)
@pytest.mark.parametrize(
    "active_state",
    [
        state.SHIFT_STARTING,
        state.RESEARCH_TRIAGE,
        state.CLAUDE_INVESTIGATING,
        state.AWAITING_CODEX_REVIEW,
        state.CODEX_CHALLENGING,
        state.AWAITING_CLAUDE_RESPONSE,
        state.CLAUDE_RESPONDING,
        state.AWAITING_CODEX_REASSESSMENT,
        state.CODEX_REASSESSING,
        state.EXPERIMENT_VERIFICATION,
        state.CONCLUSION,
    ],
)
def test_every_active_state_is_interruptible(active_state, interruption):
    assert state.transition(active_state, interruption) == interruption


@pytest.mark.parametrize(
    "terminal_state",
    [
        state.BLOCKED,
        state.SAFETY_STOP,
        state.BUDGET_EXHAUSTED,
        state.HUMAN_ESCALATION,
        state.FAILED_INFRASTRUCTURE,
    ],
)
def test_interruption_states_only_exit_to_archived(terminal_state):
    assert state.transition(terminal_state, state.ARCHIVED) == state.ARCHIVED
    with pytest.raises(state.IllegalStateTransition):
        state.transition(terminal_state, state.CLAUDE_INVESTIGATING)


def test_archived_is_terminal_with_no_outgoing_transitions():
    assert state.is_terminal(state.ARCHIVED)
    for candidate in state.ALL_STATES:
        with pytest.raises(state.IllegalStateTransition):
            state.transition(state.ARCHIVED, candidate)


@pytest.mark.parametrize(
    "current,requested",
    [
        (state.IDLE, state.ARCHIVED),
        (state.CLAUDE_INVESTIGATING, state.CODEX_REASSESSING),
        (state.RESEARCH_TRIAGE, state.CONCLUSION),
        (state.EXPERIMENT_VERIFICATION, state.CLAUDE_INVESTIGATING),
        ("NOT_A_REAL_STATE", state.IDLE),
        (state.IDLE, "NOT_A_REAL_STATE"),
    ],
)
def test_illegal_transitions_fail_closed(current, requested):
    with pytest.raises(state.IllegalStateTransition):
        state.transition(current, requested)


def test_is_interruption():
    assert state.is_interruption(state.SAFETY_STOP)
    assert not state.is_interruption(state.ARCHIVED)
    assert not state.is_interruption(state.CLAUDE_INVESTIGATING)
