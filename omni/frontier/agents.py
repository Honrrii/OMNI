"""
OMNI Frontier Research Lab — Phase 2B provider-neutral research-agent
interface, plus deterministic MOCK adapters.

`ResearchAgent` is the seam Phase 3+ real adapters (`ClaudeCodeAdapter`,
`CodexAdapter`) will implement without the orchestrator changing at all —
the orchestrator only ever consumes a `ResearchTurnResult` built from the
validated `omni.frontier.protocol.FrontierMessage` contract, never a raw
provider CLI transcript. Nothing in this module launches Claude Code,
Codex, or any model API — `MockClaudeAdapter` and `MockCodexAdapter` are
pure functions of their input `ResearchTurnContext`: same context in, same
`ResearchTurnResult` out, every time.

Agents may only *request* an orchestration action
(`ResearchTurnResult.requested_control`), and the only request this phase
recognizes is `ESCALATE_TO_HUMAN` — see `ALLOWED_CONTROL_REQUESTS`. Anything
else fails closed at construction time (`ResearchTurnResult.__post_init__`),
not later inside the orchestrator, so "an agent tries to raise its own
turn/round limit" or "an agent tries to silence a safety stop" can never
even become a valid `ResearchTurnResult` in the first place.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from omni.frontier.config import CLAUDE_AGENT_ID, CODEX_AGENT_ID, FrontierLabConfig
from omni.frontier.experiments import FrontierExperiment
from omni.frontier.protocol import FrontierMessage

# One stage per kind of turn the orchestrator can ask an agent to run. These
# map onto (but are not identical to) omni.frontier.state's ShiftOrchestrator
# states — a stage names *what kind of turn this is*, independent of which
# debate round it falls in.
STAGE_INVESTIGATE = "INVESTIGATE"
STAGE_CHALLENGE = "CHALLENGE"
STAGE_RESPOND = "RESPOND"
STAGE_REASSESS = "REASSESS"
STAGE_EXPERIMENT_REPORT = "EXPERIMENT_REPORT"
STAGE_EXPERIMENT_REVIEW = "EXPERIMENT_REVIEW"
STAGE_CONCLUDE = "CONCLUDE"

STAGES: tuple[str, ...] = (
    STAGE_INVESTIGATE,
    STAGE_CHALLENGE,
    STAGE_RESPOND,
    STAGE_REASSESS,
    STAGE_EXPERIMENT_REPORT,
    STAGE_EXPERIMENT_REVIEW,
    STAGE_CONCLUDE,
)

# A converged reassessment/review lets the orchestrator leave the bounded
# debate loop early instead of spending the full round budget.
CONVERGENCE_MESSAGE_TYPES: frozenset[str] = frozenset({"REVIEW_FINDING"})

ESCALATE_TO_HUMAN = "ESCALATE_TO_HUMAN"
ALLOWED_CONTROL_REQUESTS: frozenset[str] = frozenset({ESCALATE_TO_HUMAN})

# Provider-neutral classification of *why* a failed turn failed, so the
# orchestrator can log a specific PROVIDER_* event (see
# omni.frontier.orchestrator._FAILURE_KIND_EVENTS) instead of only the
# generic AGENT_TURN_COMPLETED failure it already logs for every failure.
# Optional and unused by MockClaudeAdapter/MockCodexAdapter — Phase 3's
# ClaudeCodeAdapter (omni/frontier/claude_provider.py) is the first real
# producer of this field; any future real adapter (Codex included) can use
# the same small enum without the orchestrator changing.
FAILURE_KIND_TIMEOUT = "TIMEOUT"
FAILURE_KIND_MALFORMED_OUTPUT = "MALFORMED_OUTPUT"
FAILURE_KIND_VALIDATION_FAILED = "VALIDATION_FAILED"
FAILURE_KIND_INFRASTRUCTURE = "INFRASTRUCTURE"
FAILURE_KINDS: frozenset[str] = frozenset(
    {
        FAILURE_KIND_TIMEOUT,
        FAILURE_KIND_MALFORMED_OUTPUT,
        FAILURE_KIND_VALIDATION_FAILED,
        FAILURE_KIND_INFRASTRUCTURE,
    }
)


@dataclass(frozen=True)
class ResearchTurnContext:
    """Everything an agent's turn needs, and nothing it can mutate.

    `thread_messages` is a tuple (not a list) and `experiment_snapshot` is a
    disconnected copy of the orchestrator's live record — see
    `ShiftOrchestrator._context_for` — so a `ResearchAgent` implementation
    has no path back into the orchestrator's own state.
    """

    thread_id: str
    stage: str
    state: str
    round_number: int
    turn_number: int
    next_sequence: int
    created_at: str
    thread_messages: tuple[FrontierMessage, ...]
    experiment_snapshot: FrontierExperiment | None
    config: FrontierLabConfig

    def __post_init__(self) -> None:
        if self.stage not in STAGES:
            raise ValueError(f"invalid ResearchTurnContext.stage {self.stage!r}; must be one of {STAGES}")

    def last_message_from(self, agent_id: str) -> FrontierMessage | None:
        for message in reversed(self.thread_messages):
            if message.from_agent == agent_id:
                return message
        return None


@dataclass
class ResearchTurnResult:
    """What one agent turn produced.

    `ok=True` requires a `message` — a successful turn that produced
    nothing is a contradiction, not a valid result. `ok=False` represents a
    turn the agent itself could not complete (used by tests to exercise
    `max_consecutive_agent_failures`); `message` is typically `None` then,
    though a partial message is not forbidden.
    """

    ok: bool
    message: FrontierMessage | None = None
    error: str = ""
    requested_control: str | None = None
    failure_kind: str | None = None

    def __post_init__(self) -> None:
        if self.ok and self.message is None:
            raise ValueError("ResearchTurnResult.ok=True requires a non-None message")
        if self.requested_control is not None and self.requested_control not in ALLOWED_CONTROL_REQUESTS:
            raise ValueError(
                f"unsupported ResearchTurnResult.requested_control "
                f"{self.requested_control!r}; an agent may only request one of "
                f"{sorted(ALLOWED_CONTROL_REQUESTS)!r} — orchestration bounds "
                f"(turn/round limits, safety stops, state transitions) are never "
                f"agent-controlled, see omni/frontier/config.py"
            )
        if self.failure_kind is not None and self.failure_kind not in FAILURE_KINDS:
            raise ValueError(
                f"unsupported ResearchTurnResult.failure_kind {self.failure_kind!r}; "
                f"must be one of {sorted(FAILURE_KINDS)!r} or None"
            )
        if self.failure_kind is not None and self.ok:
            raise ValueError("ResearchTurnResult.failure_kind requires ok=False")


class ResearchAgent(Protocol):
    """Provider-neutral research-agent interface.

    Phase 2B ships only `MockClaudeAdapter`/`MockCodexAdapter`. A Phase 3+
    `ClaudeCodeAdapter`/`CodexAdapter` implements this same protocol; the
    orchestrator does not need to change to accept one.
    """

    agent_id: str

    def run_turn(self, context: ResearchTurnContext) -> ResearchTurnResult: ...


def _mock_message(
    context: ResearchTurnContext,
    *,
    from_agent: str,
    to_agent: str,
    message_type: str,
    claim: str,
    mechanism: str = "",
    evidence: list[str] | None = None,
    uncertainties: list[str] | None = None,
    requested_action: str = "",
    confidence: float | None = None,
    in_reply_to: int | None = None,
) -> FrontierMessage:
    return FrontierMessage(
        thread_id=context.thread_id,
        sequence=context.next_sequence,
        from_agent=from_agent,
        to_agent=to_agent,
        message_type=message_type,
        claim=claim,
        mechanism=mechanism,
        evidence=evidence or [],
        uncertainties=uncertainties or [],
        requested_action=requested_action,
        confidence=confidence,
        in_reply_to=in_reply_to,
        created_at=context.created_at,
    )


@dataclass
class MockClaudeAdapter:
    """Deterministic stand-in for the omni-frontier-architect role.

    Pure function of `context.stage` and `context.round_number` — no hidden
    counters, no randomness, no I/O. Behavior is scripted, not reasoning:
    it exists to drive the orchestrator's state machine through a realistic
    shape, not to demonstrate real research judgment.
    """

    agent_id: str = CLAUDE_AGENT_ID

    def run_turn(self, context: ResearchTurnContext) -> ResearchTurnResult:
        if context.stage == STAGE_INVESTIGATE:
            message = _mock_message(
                context,
                from_agent=self.agent_id,
                to_agent=CODEX_AGENT_ID,
                message_type="HYPOTHESIS",
                claim=(
                    "OMNI may lose engineering intent between interpretation and "
                    "validation."
                ),
                mechanism=(
                    "A field an early pipeline stage computes may not be the field "
                    "a later stage actually reads, so intent captured early can go "
                    "unchecked by the time validation runs."
                ),
                evidence=[
                    "backend/app/mission_graph/builder.py",
                    "backend/app/export/export_manager.py",
                ],
                uncertainties=[
                    "Whether this has ever produced a wrong result in a real run, "
                    "or is only a theoretical mismatch (MOCK: not checked in this "
                    "Phase 2B demonstration).",
                ],
                requested_action="Attempt to falsify the claim.",
                confidence=0.4,
            )
            return ResearchTurnResult(ok=True, message=message)

        if context.stage == STAGE_RESPOND:
            challenge = context.last_message_from(CODEX_AGENT_ID)
            in_reply_to = challenge.sequence if challenge else None
            if context.round_number <= 2:
                message = _mock_message(
                    context,
                    from_agent=self.agent_id,
                    to_agent=CODEX_AGENT_ID,
                    message_type="EXPERIMENT_PROPOSAL",
                    claim=(
                        "Propose tracing one concrete field across the pipeline "
                        "boundary named in the original hypothesis to see whether "
                        "it survives or is silently dropped."
                    ),
                    mechanism=(
                        "If the field's value changes identity or disappears "
                        "between the two named modules without an explicit "
                        "transformation, that is evidence for the original "
                        "hypothesis; if it is present but ignored downstream, "
                        "that favors the counter-hypothesis instead."
                    ),
                    evidence=[
                        "backend/app/mission_graph/builder.py",
                        "backend/app/export/export_manager.py",
                    ],
                    requested_action=(
                        "Run a scripted trace (MOCK: not executed in this Phase "
                        "2B demonstration) of the named field across both stages."
                    ),
                    confidence=0.45,
                    in_reply_to=in_reply_to,
                )
            else:
                message = _mock_message(
                    context,
                    from_agent=self.agent_id,
                    to_agent=CODEX_AGENT_ID,
                    message_type="RESPONSE",
                    claim=(
                        "Refining the experiment plan to explicitly trace the "
                        "field's presence, not just its name, per the requested "
                        "distinguishing experiment."
                    ),
                    mechanism=(
                        "A field that survives under a different name would "
                        "falsify a naive 'field disappears' check, so the refined "
                        "plan checks value provenance rather than key presence."
                    ),
                    requested_action="Re-run the refined trace plan.",
                    confidence=0.45,
                    in_reply_to=in_reply_to,
                )
            return ResearchTurnResult(ok=True, message=message)

        if context.stage == STAGE_EXPERIMENT_REPORT:
            message = _mock_message(
                context,
                from_agent=self.agent_id,
                to_agent=CODEX_AGENT_ID,
                message_type="EXPERIMENT_RESULT",
                claim=(
                    "MOCK experiment result: this Phase 2B demonstration does not "
                    "execute a real repository trace. A real run would record "
                    "here whether the traced field survived, was renamed, or was "
                    "dropped between the two named pipeline stages."
                ),
                evidence=[
                    "MOCK: no real repository command was executed for this "
                    "Phase 2B demonstration — this entry is a placeholder for "
                    "where real EXPERIMENT_RESULT evidence would be recorded.",
                ],
                confidence=0.5,
            )
            return ResearchTurnResult(ok=True, message=message)

        if context.stage == STAGE_CONCLUDE:
            message = _mock_message(
                context,
                from_agent=self.agent_id,
                to_agent=CODEX_AGENT_ID,
                message_type="CONCLUSION",
                claim=(
                    "MOCK conclusion: the original hypothesis remains "
                    "PROMISING_UNPROVEN — the mock experiment above is a "
                    "placeholder, not real evidence, so this thread cannot be "
                    "closed as CONFIRMED or REFUTED from this demonstration "
                    "alone."
                ),
                requested_action=(
                    "Run the real (non-mock) traced-field experiment in a future "
                    "phase before treating this thread as settled."
                ),
                confidence=0.4,
            )
            return ResearchTurnResult(ok=True, message=message)

        return ResearchTurnResult(
            ok=False,
            error=f"MockClaudeAdapter has no scripted behavior for stage {context.stage!r}",
        )


@dataclass
class MockCodexAdapter:
    """Deterministic stand-in for the omni-frontier-experimentalist role.

    Adversarial by construction: round 1 always offers a counter-hypothesis,
    round 2 always challenges for a distinguishing experiment, and only
    round 3+ converges (`REVIEW_FINDING`) — see `CONVERGENCE_MESSAGE_TYPES`.
    Pure function of `context.stage`/`context.round_number`, same as
    `MockClaudeAdapter`.
    """

    agent_id: str = CODEX_AGENT_ID

    def run_turn(self, context: ResearchTurnContext) -> ResearchTurnResult:
        if context.stage == STAGE_CHALLENGE:
            hypothesis = context.last_message_from(CLAUDE_AGENT_ID)
            message = _mock_message(
                context,
                from_agent=self.agent_id,
                to_agent=CLAUDE_AGENT_ID,
                message_type="COUNTER_HYPOTHESIS",
                claim=(
                    "The apparent information loss may instead be caused by "
                    "downstream consumers ignoring metadata that still exists."
                ),
                mechanism=(
                    "If the field is present at every stage but simply unread by "
                    "the final consumer, the fix is downstream consumption, not "
                    "upstream loss — a materially different remediation."
                ),
                uncertainties=[
                    "Whether the field is actually absent (supports the original "
                    "hypothesis) or present-but-ignored (supports this one) — not "
                    "yet distinguished.",
                ],
                requested_action=(
                    "Propose an experiment that distinguishes 'field absent' from "
                    "'field present but ignored.'"
                ),
                confidence=0.35,
                in_reply_to=hypothesis.sequence if hypothesis else None,
            )
            return ResearchTurnResult(ok=True, message=message)

        if context.stage == STAGE_REASSESS:
            prior = context.last_message_from(CLAUDE_AGENT_ID)
            in_reply_to = prior.sequence if prior else None
            if context.round_number <= 2:
                message = _mock_message(
                    context,
                    from_agent=self.agent_id,
                    to_agent=CLAUDE_AGENT_ID,
                    message_type="CHALLENGE",
                    claim=(
                        "The proposed experiment checks whether the field's key "
                        "exists, not whether its value is actually used further "
                        "downstream — that does not yet distinguish the two "
                        "hypotheses."
                    ),
                    requested_action=(
                        "Request a distinguishing experiment that traces "
                        "information across pipeline boundaries by value, not "
                        "just by key presence."
                    ),
                    confidence=0.4,
                    in_reply_to=in_reply_to,
                )
            else:
                message = _mock_message(
                    context,
                    from_agent=self.agent_id,
                    to_agent=CLAUDE_AGENT_ID,
                    message_type="REVIEW_FINDING",
                    claim=(
                        "The refined plan (trace by value provenance, not key "
                        "presence) is a genuine distinguishing experiment. "
                        "Proceeding to experiment verification is reasonable "
                        "given the (mock) plan above."
                    ),
                    confidence=0.5,
                    in_reply_to=in_reply_to,
                )
            return ResearchTurnResult(ok=True, message=message)

        if context.stage == STAGE_EXPERIMENT_REVIEW:
            result = context.last_message_from(CLAUDE_AGENT_ID)
            message = _mock_message(
                context,
                from_agent=self.agent_id,
                to_agent=CLAUDE_AGENT_ID,
                message_type="REVIEW_FINDING",
                claim=(
                    "MOCK review: the reported experiment result is a placeholder "
                    "(see its evidence entry), so it neither confirms nor refutes "
                    "the hypothesis. Independent review agrees this thread should "
                    "conclude PROMISING_UNPROVEN, not CONFIRMED, until a real "
                    "trace is run."
                ),
                confidence=0.45,
                in_reply_to=result.sequence if result else None,
            )
            return ResearchTurnResult(ok=True, message=message)

        return ResearchTurnResult(
            ok=False,
            error=f"MockCodexAdapter has no scripted behavior for stage {context.stage!r}",
        )
