"""
OMNI Frontier Research Lab — Phase 2B orchestration state machine.

An explicit, closed state machine for one research *shift* (one run of the
orchestrator against one thread). This is a different, more granular set of
states than `omni.frontier.experiments.EXPERIMENT_STATUSES`
(`PROPOSED`/`IN_PROGRESS`/`COMPLETE`) — that enum tracks the *experiment
record's* lifecycle; this module tracks the *orchestrator's* turn-by-turn
control state, which the experiment record's lifecycle is a coarse
projection of.

Every legal transition is listed explicitly in `TRANSITIONS`. `transition()`
is the only way this module allows moving between states, and it raises
`IllegalStateTransition` for anything not in that table — there is no
arbitrary string-based state jump. This is the deterministic control
surface `docs/agentic/repository_invariants.md` asks for: a rule enforced
in code, not one an agent (or a caller) could talk past.
"""
from __future__ import annotations

# --- Nominal (happy-path) states -------------------------------------------
IDLE = "IDLE"
SHIFT_STARTING = "SHIFT_STARTING"
RESEARCH_TRIAGE = "RESEARCH_TRIAGE"
CLAUDE_INVESTIGATING = "CLAUDE_INVESTIGATING"
AWAITING_CODEX_REVIEW = "AWAITING_CODEX_REVIEW"
CODEX_CHALLENGING = "CODEX_CHALLENGING"
AWAITING_CLAUDE_RESPONSE = "AWAITING_CLAUDE_RESPONSE"
CLAUDE_RESPONDING = "CLAUDE_RESPONDING"
AWAITING_CODEX_REASSESSMENT = "AWAITING_CODEX_REASSESSMENT"
CODEX_REASSESSING = "CODEX_REASSESSING"
EXPERIMENT_VERIFICATION = "EXPERIMENT_VERIFICATION"
CONCLUSION = "CONCLUSION"
ARCHIVED = "ARCHIVED"

# --- Terminal / interruption states -----------------------------------------
BLOCKED = "BLOCKED"
SAFETY_STOP = "SAFETY_STOP"
BUDGET_EXHAUSTED = "BUDGET_EXHAUSTED"
HUMAN_ESCALATION = "HUMAN_ESCALATION"
FAILED_INFRASTRUCTURE = "FAILED_INFRASTRUCTURE"

# Interruptions reachable from any non-terminal, in-flight state. These are
# deterministic orchestrator decisions (a budget check, a safety rule, an
# infrastructure error) — never something a message payload can request by
# naming the state directly.
INTERRUPTION_STATES: frozenset[str] = frozenset(
    {BLOCKED, SAFETY_STOP, BUDGET_EXHAUSTED, HUMAN_ESCALATION, FAILED_INFRASTRUCTURE}
)

# Every state that can appear once a shift is running (excludes IDLE, which
# only exists before a shift has been started).
ACTIVE_STATES: frozenset[str] = frozenset(
    {
        SHIFT_STARTING,
        RESEARCH_TRIAGE,
        CLAUDE_INVESTIGATING,
        AWAITING_CODEX_REVIEW,
        CODEX_CHALLENGING,
        AWAITING_CLAUDE_RESPONSE,
        CLAUDE_RESPONDING,
        AWAITING_CODEX_REASSESSMENT,
        CODEX_REASSESSING,
        EXPERIMENT_VERIFICATION,
        CONCLUSION,
    }
)

# A shift that reaches ARCHIVED is done; nothing transitions out of it.
TERMINAL_STATES: frozenset[str] = INTERRUPTION_STATES | {ARCHIVED}

ALL_STATES: frozenset[str] = ACTIVE_STATES | TERMINAL_STATES | {IDLE}


def _happy_path_and_interruptions(*happy_next: str) -> frozenset[str]:
    return frozenset(happy_next) | INTERRUPTION_STATES


# The closed transition table. Every key is a state that can be the
# "current" state passed to transition(); every value is the exhaustive set
# of states legally reachable from it in one call. A state with no entry
# here (or an entry that doesn't contain the requested state) fails closed.
TRANSITIONS: dict[str, frozenset[str]] = {
    IDLE: frozenset({SHIFT_STARTING}),
    SHIFT_STARTING: _happy_path_and_interruptions(RESEARCH_TRIAGE),
    RESEARCH_TRIAGE: _happy_path_and_interruptions(CLAUDE_INVESTIGATING),
    CLAUDE_INVESTIGATING: _happy_path_and_interruptions(AWAITING_CODEX_REVIEW),
    AWAITING_CODEX_REVIEW: _happy_path_and_interruptions(CODEX_CHALLENGING),
    # Round 1's Codex turn may already converge straight to verification, or
    # continue the debate.
    CODEX_CHALLENGING: _happy_path_and_interruptions(
        AWAITING_CLAUDE_RESPONSE, EXPERIMENT_VERIFICATION
    ),
    AWAITING_CLAUDE_RESPONSE: _happy_path_and_interruptions(CLAUDE_RESPONDING),
    CLAUDE_RESPONDING: _happy_path_and_interruptions(AWAITING_CODEX_REASSESSMENT),
    AWAITING_CODEX_REASSESSMENT: _happy_path_and_interruptions(CODEX_REASSESSING),
    # Bounded debate loop: an unconverged reassessment goes back to another
    # round (AWAITING_CLAUDE_RESPONSE); a converged one proceeds to
    # verification. The orchestrator's round counter (not this table) is
    # what keeps this loop finite — see FrontierLabConfig.max_debate_rounds.
    CODEX_REASSESSING: _happy_path_and_interruptions(
        AWAITING_CLAUDE_RESPONSE, EXPERIMENT_VERIFICATION
    ),
    EXPERIMENT_VERIFICATION: _happy_path_and_interruptions(CONCLUSION),
    # Even the final CONCLUSION turn can, in principle, trip a safety check
    # (omni.frontier.orchestrator._violates_safety runs on every accepted
    # message) — CONCLUSION must stay interruptible for the same reason
    # every other in-flight state is.
    CONCLUSION: _happy_path_and_interruptions(ARCHIVED),
    # Every terminal/interruption state's only legal exit is to ARCHIVED —
    # an interrupted shift is still archived (see
    # docs describing "negative, inconclusive, and escalated results are
    # legitimate archives").
    BLOCKED: frozenset({ARCHIVED}),
    SAFETY_STOP: frozenset({ARCHIVED}),
    BUDGET_EXHAUSTED: frozenset({ARCHIVED}),
    HUMAN_ESCALATION: frozenset({ARCHIVED}),
    FAILED_INFRASTRUCTURE: frozenset({ARCHIVED}),
    ARCHIVED: frozenset(),
}

assert set(TRANSITIONS) == ALL_STATES, "TRANSITIONS must cover every declared state"


class IllegalStateTransition(ValueError):
    """Raised when a requested state transition is not in `TRANSITIONS`.

    Fails closed: an unknown current state, an unknown requested state, or a
    combination not explicitly listed all raise this — none of them fall
    through to a permissive default.
    """

    def __init__(self, current: str, requested: str):
        self.current = current
        self.requested = requested
        super().__init__(
            f"illegal shift state transition: {current!r} -> {requested!r} is not "
            f"in omni.frontier.state.TRANSITIONS"
        )


def transition(current: str, requested: str) -> str:
    """Return `requested` if `current -> requested` is a legal transition.

    Raises `IllegalStateTransition` otherwise. This is the only function in
    this module that changes state on behalf of a caller — there is no
    lower-level "just set the state" escape hatch.
    """
    legal_next = TRANSITIONS.get(current)
    if legal_next is None or requested not in legal_next:
        raise IllegalStateTransition(current, requested)
    return requested


def is_terminal(state: str) -> bool:
    return state in TERMINAL_STATES


def is_interruption(state: str) -> bool:
    return state in INTERRUPTION_STATES
