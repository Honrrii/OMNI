"""
OMNI Frontier Research Lab — Phase 2B deterministic orchestrator.

`ShiftOrchestrator` is the sole holder of deterministic control over one
research shift: experiment/thread ID assignment, state transitions, whose
turn it is, mailbox routing, the debate-round/turn/retry/invalid-message
budgets in `omni.frontier.config.FrontierLabConfig`, event logging,
completion conditions, safety stops, human-escalation state, and archive
finalization. A `ResearchAgent` (`omni/frontier/agents.py`) may only
*request* an action through `ResearchTurnResult` — it never receives a
mutable reference to this orchestrator's state, its event log, its
mailbox, or its `FrontierExperiment` record, so there is no code path by
which an agent turn could change orchestration boundaries.

This module itself still runs no model and calls no API — it does not
import a provider SDK, does not launch a subprocess, and does not open a
network connection. Phase 2B wires it to `MockClaudeAdapter`/
`MockCodexAdapter` only (`ShiftReport.provider_calls` is always `0` then).
Phase 3 (`scripts/omni_frontier_lab.py run-claude-shift`) wires the same
orchestrator, unchanged, to a real `omni.frontier.claude_provider.
ClaudeCodeAdapter` for Claude while Codex stays
`MockCodexAdapter` — the orchestrator does not know or care which kind of
`ResearchAgent` it was given; see `_count_provider_calls` and the optional
`preflight=` constructor argument for the only two Claude-Live-aware
(but still provider-neutral) additions this class gained in Phase 3.
"""
from __future__ import annotations

import dataclasses
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from omni.frontier import state
from omni.frontier.agents import (
    CONVERGENCE_MESSAGE_TYPES,
    ESCALATE_TO_HUMAN,
    FAILURE_KIND_INFRASTRUCTURE,
    FAILURE_KIND_MALFORMED_OUTPUT,
    FAILURE_KIND_TIMEOUT,
    FAILURE_KIND_VALIDATION_FAILED,
    STAGE_CHALLENGE,
    STAGE_CONCLUDE,
    STAGE_EXPERIMENT_REPORT,
    STAGE_EXPERIMENT_REVIEW,
    STAGE_INVESTIGATE,
    STAGE_REASSESS,
    STAGE_RESPOND,
    ResearchAgent,
    ResearchTurnContext,
    ResearchTurnResult,
)
from omni.frontier.config import FrontierLabConfig, MOCK_SHIFT_SCORE
from omni.frontier.events import EventLog, FrontierEvent
from omni.frontier.experiments import CONCLUSION_STATES, FrontierExperiment, to_json as experiment_to_json
from omni.frontier.mailbox import Mailbox, MailboxItem, MailboxRejectionError
from omni.frontier.protocol import FrontierMessage, to_dict as message_to_dict, validate_thread_id

THREAD_ID_SCAN_PATTERN = re.compile(r"OMNI-FRONTIER-(\d{4,})")

# A content-level tripwire, not real git enforcement (Phase 2B does not
# touch git at all — see .omni-lab/protocols/SAFETY_RULES.md). If a mock
# (or, later, real) agent's message claims or requests something that reads
# like one of omni.frontier.safety.HARD_SAFETY_RULES being violated, the
# orchestrator stops rather than continuing to route it. This exists so
# SAFETY_STOP is a reachable, testable state in Phase 2B, not dead code.
SAFETY_TRIGGER_PHRASES: tuple[str, ...] = (
    "force push",
    "force-push",
    "--force",
    "delete the main branch",
    "delete branch main",
    "merge into main",
    "merge to main",
    "push to main",
    "rewrite history",
    "bypass protections",
)

# A CONCLUDE-turn FrontierMessage has no dedicated conclusion-state field
# (see omni.frontier.protocol.FrontierMessage / frontier_message.schema.json)
# -- the claim's prose is the only place a CONCLUDE turn records its
# verdict, and naming one of the canonical
# omni.frontier.experiments.CONCLUSION_STATES words there is the documented
# convention (see tests/test_frontier_role_exchange_demo.py's
# test_conclusion_message_uses_an_existing_conclusion_state_vocabulary_word).
# Matched as whole words so e.g. "SUPPORTED" cannot match inside a longer
# token; alternation order does not affect which match wins because
# re.search always returns the leftmost match position.
_CONCLUSION_STATE_TOKEN_PATTERN = re.compile(
    r"\b(?:" + "|".join(re.escape(value) for value in CONCLUSION_STATES) + r")\b"
)


def _extract_conclusion_state(message: FrontierMessage) -> str | None:
    """Return the first CONCLUSION_STATES word named in `message.claim`, or
    `None` if the claim names none of them.

    "First" means leftmost in reading order: a CONCLUDE claim states its
    verdict up front and may mention other states only contrastively later
    (e.g. "remains PROMISING_UNPROVEN ... not yet CONFIRMED or REFUTED").
    Returning `None` lets the caller fail closed instead of guessing or
    falling back to a default.
    """
    match = _CONCLUSION_STATE_TOKEN_PATTERN.search(message.claim)
    return match.group(0) if match else None


# Maps ResearchTurnResult.failure_kind -> the specific event logged in
# addition to the generic AGENT_TURN_COMPLETED failure entry every failed
# turn already gets. Provider-neutral: this is keyed on the small enum in
# omni.frontier.agents, not on any adapter class, so a future real Codex
# adapter reporting a TIMEOUT gets the same PROVIDER_TIMEOUT event a real
# Claude adapter does.
_FAILURE_KIND_EVENTS: dict[str, str] = {
    FAILURE_KIND_TIMEOUT: "PROVIDER_TIMEOUT",
    FAILURE_KIND_MALFORMED_OUTPUT: "PROVIDER_OUTPUT_REJECTED",
    FAILURE_KIND_VALIDATION_FAILED: "PROVIDER_OUTPUT_REJECTED",
    FAILURE_KIND_INFRASTRUCTURE: "PROVIDER_FAILURE",
}


@dataclass(frozen=True)
class PreflightResult:
    """Whether a provider is ready to run a live turn, checked once before a
    shift starts. Provider-neutral: `ShiftOrchestrator` only knows it got a
    `ready` bool and a short `status` code back from whatever callable was
    passed as `preflight=`. See `omni.frontier.claude_provider.
    check_claude_availability` for the concrete Claude Code implementation.
    """

    ready: bool
    status: str
    detail: str = ""
    provider_version: str = ""


def _real_utc_clock() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def allocate_thread_id(lab_root: Path) -> str:
    """Deterministically allocate the next unused OMNI-FRONTIER-#### id.

    Scans `lab_root/experiments` and `lab_root/runtime` for existing thread
    directories and `lab_root/conversations` for existing thread logs;
    returns one past the highest id found (minimum `OMNI-FRONTIER-0001`).
    Given the same directory contents, this always returns the same id —
    determinism here means "reproducible given the same disk state," not
    "constant across calls."
    """
    highest = 0
    for subdir in ("experiments", "runtime"):
        directory = Path(lab_root) / subdir
        if not directory.is_dir():
            continue
        for entry in directory.iterdir():
            match = THREAD_ID_SCAN_PATTERN.fullmatch(entry.name)
            if match:
                highest = max(highest, int(match.group(1)))
    conversations = Path(lab_root) / "conversations"
    if conversations.is_dir():
        for entry in conversations.glob("OMNI-FRONTIER-*.jsonl"):
            match = THREAD_ID_SCAN_PATTERN.search(entry.stem)
            if match:
                highest = max(highest, int(match.group(1)))
    return f"OMNI-FRONTIER-{highest + 1:04d}"


class AgentIdentityViolation(ValueError):
    """Raised when a turn result's message claims an identity or thread the
    orchestrator did not ask it to speak as/on. Distinct from
    `MailboxRejectionError`: this is a contract violation by the adapter
    itself, not an ordinary routing rejection, so the orchestrator treats it
    as an immediate bounded stop rather than a retryable rejection.
    """


class SelfCertificationError(ValueError):
    """Raised when a thread would reach CONCLUSION without every configured
    participant ever having spoken on it — see
    `ensure_multi_agent_participation`.
    """


def ensure_multi_agent_participation(
    messages: list[FrontierMessage], participants: tuple[str, ...]
) -> None:
    """Refuse to let a thread conclude if only one agent ever spoke on it.

    Mirrors `docs/agentic/repository_invariants.md`'s "implementation
    agents cannot approve their own work" applied to research: a thread
    cannot reach CONCLUSION certified only by the agent that proposed the
    hypothesis in the first place. Raises `SelfCertificationError` if any
    configured participant never appears as a message's `from_agent`.
    """
    authors = {message.from_agent for message in messages}
    missing = [participant for participant in participants if participant not in authors]
    if missing:
        raise SelfCertificationError(
            f"refusing to reach CONCLUSION: participant(s) {missing!r} never sent a "
            f"message on this thread — a single agent may not certify its own "
            f"material implementation without independent participation"
        )


def finalize_experiment_conclusion(
    experiment: FrontierExperiment,
    *,
    conclusion_state: str,
    experiment_plan: str,
    limitations: list[str],
    remaining_uncertainty: str,
    recommended_next_action: str,
    evidence: list[str],
) -> FrontierExperiment:
    """Build the COMPLETE version of `experiment`.

    This is the only place Phase 2B constructs a concluded
    `FrontierExperiment`, and it does so through the dataclass's own
    constructor (`dataclasses.replace`), which re-runs
    `FrontierExperiment.__post_init__` — so a conclusion missing required
    data (e.g. empty `limitations`, or empty `evidence` for a conclusion
    state that requires it) raises `ValueError` here rather than silently
    producing an archive that only looks complete. See
    `docs/agentic/packet_contracts.md`'s "the code is authoritative."
    """
    return dataclasses.replace(
        experiment,
        status="COMPLETE",
        conclusion_state=conclusion_state,
        experiment_plan=experiment_plan,
        limitations=limitations,
        remaining_uncertainty=remaining_uncertainty,
        recommended_next_action=recommended_next_action,
        evidence=evidence,
    )


@dataclass
class ShiftReport:
    """Summary of one completed (or stopped) research shift.

    `mock` is `True` when the orchestrator was constructed with no
    `preflight=` (Phase 2B's `run-mock-shift`), `False` when it was (Phase
    3's `run-claude-shift`, whether or not the preflight actually passed).
    `provider_calls` sums each configured agent's own `provider_calls`
    attribute, if it has one — see `_count_provider_calls`.
    """

    thread_id: str
    final_state: str
    stopped_early: bool
    stop_reason: str
    rounds_completed: int
    turns_used: int
    invalid_message_count: int
    message_count: int
    experiment: FrontierExperiment | None
    events: list[FrontierEvent]
    mailbox_items: list[MailboxItem]
    archive_dir: Path
    runtime_dir: Path
    provider_calls: int = 0
    mock: bool = True


class ShiftOrchestrator:
    """Deterministic controller for one Frontier Research Lab mock shift.

    Owns: thread/experiment ID assignment, the state machine
    (`omni.frontier.state`), the mailbox (`omni.frontier.mailbox.Mailbox`),
    the append-only event log (`omni.frontier.events.EventLog`), and every
    budget in `FrontierLabConfig`. `claude`/`codex` are `ResearchAgent`
    implementations — `scripts/omni_frontier_lab.py`'s `run-mock-shift`
    constructs this with `MockClaudeAdapter`/`MockCodexAdapter`, and its
    `run-claude-shift` constructs it with a real
    `omni.frontier.claude_provider.ClaudeCodeAdapter` for `claude` and
    `MockCodexAdapter` (still) for `codex`. This class never imports either
    module — nothing in it assumes which kind of agent it was given.
    """

    def __init__(
        self,
        *,
        config: FrontierLabConfig,
        claude: ResearchAgent,
        codex: ResearchAgent,
        lab_root: Path,
        clock: Callable[[], str] | None = None,
        preflight: Callable[[], PreflightResult] | None = None,
    ):
        self.config = config
        self.claude = claude
        self.codex = codex
        self.lab_root = Path(lab_root)
        self._clock = clock or _real_utc_clock
        self._preflight = preflight

        self.state: str = state.IDLE
        self.thread_id: str | None = None
        self.thread_messages: list[FrontierMessage] = []
        self.experiment: FrontierExperiment | None = None
        self.mailbox: Mailbox = Mailbox(participants=config.participants)
        self.events: EventLog = EventLog()

        self.turn_number = 0
        self.consecutive_failures = 0
        self.invalid_message_count = 0
        self.experiment_retries = 0
        self.rounds_completed = 0
        self._stopped = False
        self._stop_reason = ""

    # -- logging / state -----------------------------------------------

    def _log(
        self,
        event_type: str,
        *,
        actor: str,
        message_ref: int | None = None,
        detail: str = "",
        context: dict | None = None,
    ) -> FrontierEvent:
        return self.events.append(
            thread_id=self.thread_id or "",
            event_type=event_type,
            actor=actor,
            state=self.state,
            created_at=self._clock(),
            message_ref=message_ref,
            detail=detail,
            context=context,
        )

    def _transition(self, requested: str) -> str:
        self.state = state.transition(self.state, requested)
        self._log("STATE_CHANGED", actor="orchestrator", detail=requested)
        return self.state

    def _stop(self, terminal_state: str, detail: str) -> None:
        self._transition(terminal_state)
        event_type = {
            state.BUDGET_EXHAUSTED: "BUDGET_EXHAUSTED",
            state.HUMAN_ESCALATION: "HUMAN_ESCALATION",
            state.SAFETY_STOP: "SAFETY_STOP",
        }.get(terminal_state)
        if event_type:
            self._log(event_type, actor="orchestrator", detail=detail)
        self._stopped = True
        self._stop_reason = detail

    # -- turn execution ---------------------------------------------------

    def _context_for(self, agent_id: str, stage: str, round_number: int) -> ResearchTurnContext:
        return ResearchTurnContext(
            thread_id=self.thread_id,
            stage=stage,
            state=self.state,
            round_number=round_number,
            turn_number=self.turn_number,
            next_sequence=len(self.thread_messages) + 1,
            created_at=self._clock(),
            thread_messages=tuple(self.thread_messages),
            experiment_snapshot=dataclasses.replace(self.experiment) if self.experiment else None,
            config=self.config,
        )

    def _accept_message(self, agent_id: str, message: FrontierMessage) -> MailboxItem:
        if message.from_agent != agent_id:
            raise AgentIdentityViolation(
                f"agent {agent_id!r} returned a message with from_agent="
                f"{message.from_agent!r}; an agent may not send as another identity"
            )
        if message.thread_id != self.thread_id:
            raise AgentIdentityViolation(
                f"agent {agent_id!r} returned a message for thread "
                f"{message.thread_id!r}, expected {self.thread_id!r}"
            )
        violation = _violates_safety(message)
        item = self.mailbox.deliver(message)
        self.thread_messages.append(message)
        self._log("MESSAGE_CREATED", actor=agent_id, message_ref=message.sequence)
        self._log(
            "MESSAGE_ROUTED",
            actor=agent_id,
            message_ref=message.sequence,
            context={"to_agent": message.to_agent},
        )
        self.mailbox.mark_processed(item.mailbox_sequence)
        if violation:
            self._stop(state.SAFETY_STOP, f"message content matched safety trigger {violation!r}")
        return item

    def _run_turn(self, agent: ResearchAgent, stage: str, round_number: int) -> FrontierMessage | None:
        while True:
            self.turn_number += 1
            if self.turn_number > self.config.max_agent_turns:
                self._stop(state.BUDGET_EXHAUSTED, f"max_agent_turns={self.config.max_agent_turns} reached")
                return None

            context = self._context_for(agent.agent_id, stage, round_number)
            self._log("AGENT_TURN_STARTED", actor=agent.agent_id, context={"stage": stage, "round": round_number})

            try:
                result: ResearchTurnResult = agent.run_turn(context)
            except Exception as exc:  # noqa: BLE001 - any adapter failure is a bounded agent failure
                result = ResearchTurnResult(ok=False, error=f"{type(exc).__name__}: {exc}")

            if not result.ok:
                self._log("AGENT_TURN_COMPLETED", actor=agent.agent_id, detail=f"failed: {result.error}")
                failure_event = _FAILURE_KIND_EVENTS.get(result.failure_kind)
                if failure_event:
                    self._log(failure_event, actor=agent.agent_id, detail=result.error)
                if stage in (STAGE_EXPERIMENT_REPORT, STAGE_EXPERIMENT_REVIEW):
                    self.experiment_retries += 1
                    if self.experiment_retries >= self.config.max_experiment_retries:
                        self._stop(
                            state.FAILED_INFRASTRUCTURE,
                            f"max_experiment_retries={self.config.max_experiment_retries} "
                            f"reached at stage {stage}",
                        )
                        return None
                else:
                    self.consecutive_failures += 1
                    if self.consecutive_failures >= self.config.max_consecutive_agent_failures:
                        self._stop(
                            state.BLOCKED,
                            f"{agent.agent_id} failed {self.consecutive_failures} consecutive "
                            f"turn(s) (max_consecutive_agent_failures="
                            f"{self.config.max_consecutive_agent_failures})",
                        )
                        return None
                continue

            self.consecutive_failures = 0
            self._log(
                "AGENT_TURN_COMPLETED",
                actor=agent.agent_id,
                message_ref=result.message.sequence,
                detail="ok",
                context={"message_type": result.message.message_type},
            )

            if result.requested_control == ESCALATE_TO_HUMAN:
                self._stop(state.HUMAN_ESCALATION, f"{agent.agent_id} requested human escalation")
                return None

            try:
                self._accept_message(agent.agent_id, result.message)
            except AgentIdentityViolation as exc:
                self._log("MESSAGE_REJECTED", actor=agent.agent_id, detail=str(exc))
                self._stop(state.BLOCKED, str(exc))
                return None
            except MailboxRejectionError as exc:
                self.invalid_message_count += 1
                self._log(
                    "MESSAGE_REJECTED",
                    actor=agent.agent_id,
                    detail=str(exc),
                    context={"reason": exc.reason},
                )
                if self.invalid_message_count >= self.config.max_invalid_messages:
                    self._stop(
                        state.HUMAN_ESCALATION,
                        f"max_invalid_messages={self.config.max_invalid_messages} reached",
                    )
                    return None
                continue

            if self._stopped:
                # A safety trigger inside _accept_message already stopped us.
                return None
            return result.message

    # -- experiment record bookkeeping ------------------------------------

    def _record_hypothesis(self, message: FrontierMessage) -> None:
        title = message.claim.strip().splitlines()[0][:88]
        self.experiment = FrontierExperiment(
            experiment_id=self.thread_id,
            title=f"Mock shift: {title}",
            hypothesis=message.claim,
            mechanism=message.mechanism,
            predicted_evidence=list(message.evidence),
            scoring=MOCK_SHIFT_SCORE,
            created_at=self._clock(),
            participants=list(self.config.participants),
            status="PROPOSED",
        )

    def _record_counter(self, message: FrontierMessage) -> None:
        self.experiment = dataclasses.replace(
            self.experiment,
            competing_hypotheses=self.experiment.competing_hypotheses + [message.claim],
        )

    def _record_response(self, message: FrontierMessage) -> None:
        if message.message_type == "EXPERIMENT_PROPOSAL":
            self.experiment = dataclasses.replace(
                self.experiment,
                experiment_plan=message.claim,
                predicted_evidence=self.experiment.predicted_evidence + list(message.evidence),
                status="IN_PROGRESS",
            )
        else:
            plan = self.experiment.experiment_plan
            self.experiment = dataclasses.replace(
                self.experiment,
                experiment_plan=(plan + " " + message.claim).strip() if plan else message.claim,
            )

    def _record_reassessment(self, message: FrontierMessage) -> None:
        return None  # procedural only in Phase 2B — see module docstring

    def _record_experiment_result(self, message: FrontierMessage) -> None:
        self.experiment = dataclasses.replace(
            self.experiment,
            evidence=self.experiment.evidence + list(message.evidence),
        )
        self._log("EXPERIMENT_RESULT_RECORDED", actor=message.from_agent, message_ref=message.sequence)

    def _record_experiment_review(self, message: FrontierMessage) -> None:
        return None  # procedural only in Phase 2B — see module docstring

    def _record_conclusion(self, message: FrontierMessage) -> None:
        conclusion_state = _extract_conclusion_state(message)
        if conclusion_state is None:
            self._stop(
                state.BLOCKED,
                "CONCLUDE-turn message names no CONCLUSION_STATES vocabulary "
                f"word in its claim: {message.claim[:120]!r}",
            )
            return

        self.experiment = finalize_experiment_conclusion(
            self.experiment,
            conclusion_state=conclusion_state,
            experiment_plan=self.experiment.experiment_plan or message.claim,
            limitations=[
                "MOCK: Phase 2B does not execute a real repository experiment; "
                "this record demonstrates deterministic orchestration only, not "
                "a real finding.",
            ],
            remaining_uncertainty=message.claim,
            recommended_next_action=message.requested_action or (
                "Run the real (non-mock) experiment in a later phase."
            ),
            evidence=self.experiment.evidence,
        )
        self._log(
            "CONCLUSION_REACHED",
            actor=message.from_agent,
            message_ref=message.sequence,
            context={"conclusion_state": conclusion_state},
        )

    # -- main entry point ---------------------------------------------------

    def run_mock_shift(self, thread_id: str | None = None) -> ShiftReport:
        """Run one complete research shift end to end, with whichever
        `ResearchAgent` implementations this instance was constructed with
        (see class docstring). Always returns a `ShiftReport` — a shift
        that hits a budget, a safety trigger, a failed provider preflight,
        or an agent failure still completes by reaching `ARCHIVED`, per
        `.omni-lab/protocols/EXPERIMENT_LIFECYCLE.md`'s "negative,
        inconclusive, and escalated results are legitimate archives."

        The name predates Phase 3 (`ShiftOrchestrator` was mock-only when
        this method was written) and is kept for API stability — nothing
        about this method is actually mock-specific.
        """
        self.thread_id = validate_thread_id(thread_id or allocate_thread_id(self.lab_root))

        self._log("SHIFT_STARTED", actor="orchestrator", detail=f"lab_root={self.lab_root}")
        self._transition(state.SHIFT_STARTING)

        if self._preflight is not None:
            self._log("PROVIDER_PREFLIGHT_STARTED", actor="orchestrator")
            result = self._preflight()
            self._log(
                "PROVIDER_PREFLIGHT_COMPLETED",
                actor="orchestrator",
                detail=f"{result.status}: {result.detail}" if result.detail else result.status,
                context={"ready": result.ready, "provider_version": result.provider_version},
            )
            if not result.ready:
                self._stop(
                    state.FAILED_INFRASTRUCTURE,
                    f"provider preflight failed ({result.status}): {result.detail or 'no detail'}",
                )
                return self._finalize()

        self._log("THREAD_CREATED", actor="orchestrator", context={"thread_id": self.thread_id})
        self._transition(state.RESEARCH_TRIAGE)
        self._transition(state.CLAUDE_INVESTIGATING)

        round_number = 1
        message = self._run_turn(self.claude, STAGE_INVESTIGATE, round_number)
        if message is None:
            return self._finalize()
        self._record_hypothesis(message)

        self._transition(state.AWAITING_CODEX_REVIEW)
        self._transition(state.CODEX_CHALLENGING)
        message = self._run_turn(self.codex, STAGE_CHALLENGE, round_number)
        if message is None:
            return self._finalize()
        self._record_counter(message)

        converged = self._advance_or_stop(message, round_number)
        if converged is False:
            return self._finalize()

        while converged is None:
            round_number += 1
            self._transition(state.CLAUDE_RESPONDING)
            message = self._run_turn(self.claude, STAGE_RESPOND, round_number)
            if message is None:
                return self._finalize()
            self._record_response(message)

            self._transition(state.AWAITING_CODEX_REASSESSMENT)
            self._transition(state.CODEX_REASSESSING)
            message = self._run_turn(self.codex, STAGE_REASSESS, round_number)
            if message is None:
                return self._finalize()
            self._record_reassessment(message)

            converged = self._advance_or_stop(message, round_number)
            if converged is False:
                return self._finalize()

        self.rounds_completed = round_number

        message = self._run_turn(self.claude, STAGE_EXPERIMENT_REPORT, round_number)
        if message is None:
            return self._finalize()
        self._record_experiment_result(message)

        message = self._run_turn(self.codex, STAGE_EXPERIMENT_REVIEW, round_number)
        if message is None:
            return self._finalize()
        self._record_experiment_review(message)

        try:
            ensure_multi_agent_participation(self.thread_messages, self.config.participants)
        except SelfCertificationError as exc:
            self._stop(state.BLOCKED, str(exc))
            return self._finalize()

        self._transition(state.CONCLUSION)
        message = self._run_turn(self.claude, STAGE_CONCLUDE, round_number)
        if message is None:
            return self._finalize()
        self._record_conclusion(message)

        return self._finalize()

    def _advance_or_stop(self, codex_message: FrontierMessage, round_number: int) -> bool | None:
        """Returns True (converged), False (stopped on budget), or None (continue)."""
        self._log(
            "DEBATE_ROUND_COMPLETED",
            actor="orchestrator",
            context={"round": round_number, "message_type": codex_message.message_type},
        )
        if codex_message.message_type in CONVERGENCE_MESSAGE_TYPES:
            self._transition(state.EXPERIMENT_VERIFICATION)
            self.rounds_completed = round_number
            return True
        if round_number >= self.config.max_debate_rounds:
            self._stop(
                state.BUDGET_EXHAUSTED,
                f"max_debate_rounds={self.config.max_debate_rounds} reached without convergence",
            )
            return False
        self._transition(state.AWAITING_CLAUDE_RESPONSE)
        return None

    # -- finalize / archive -------------------------------------------------

    def _finalize(self) -> ShiftReport:
        if self.experiment is not None and self.experiment.status != "COMPLETE":
            self.experiment = finalize_experiment_conclusion(
                self.experiment,
                conclusion_state="BLOCKED_BY_REQUIRED_EVIDENCE",
                experiment_plan=self.experiment.experiment_plan
                or "Shift stopped before an experiment plan was finalized.",
                limitations=["Shift did not reach CONCLUSION; see remaining_uncertainty for why."],
                remaining_uncertainty=self._stop_reason or "Shift ended before a conclusion was reached.",
                recommended_next_action="Re-run the shift, or escalate to a human, per the recorded stop reason.",
                evidence=self.experiment.evidence,
            )

        if self.state != state.CONCLUSION and self.state not in state.TERMINAL_STATES:
            # _finalize is only ever reached from CONCLUSION (the happy
            # path, about to archive) or from a state _stop() already moved
            # to a terminal interruption. Anything else is a bug in the
            # caller, not a recoverable orchestration outcome — fail closed.
            raise state.IllegalStateTransition(self.state, state.ARCHIVED)
        if self.state != state.ARCHIVED:
            self._transition(state.ARCHIVED)

        archive_dir, runtime_dir = self._write_disk_state()
        self._log("ARCHIVE_WRITTEN", actor="orchestrator", context={"archive_dir": str(archive_dir)})
        self._log("SHIFT_COMPLETED", actor="orchestrator", detail=self._stop_reason or "completed")
        # Runtime snapshot is written after the final two events too, so a
        # restored state.json reflects the true end of the shift.
        self._write_runtime_snapshot(runtime_dir)

        return ShiftReport(
            thread_id=self.thread_id,
            final_state=self.state,
            stopped_early=self._stopped,
            stop_reason=self._stop_reason,
            rounds_completed=self.rounds_completed,
            turns_used=self.turn_number,
            invalid_message_count=self.invalid_message_count,
            message_count=len(self.thread_messages),
            experiment=self.experiment,
            events=self.events.events,
            mailbox_items=self.mailbox.items,
            archive_dir=archive_dir,
            runtime_dir=runtime_dir,
            provider_calls=self._count_provider_calls(),
            mock=self._preflight is None,
        )

    def _count_provider_calls(self) -> int:
        """Sum of `provider_calls` on each configured agent, if it has one.

        Duck-typed and optional on purpose: `MockClaudeAdapter`/
        `MockCodexAdapter` never gain this attribute, so this reads `0` for
        every Phase 2B shift without either mock module changing. A real
        adapter (`omni.frontier.claude_provider.ClaudeCodeAdapter`) exposes
        it as a plain int counter it increments itself — the orchestrator
        never has to know what "Claude" is to report it accurately.
        """
        return getattr(self.claude, "provider_calls", 0) + getattr(self.codex, "provider_calls", 0)

    def _write_disk_state(self) -> tuple[Path, Path]:
        archive_dir = self.lab_root / "experiments" / self.thread_id
        runtime_dir = self.lab_root / "runtime" / self.thread_id
        archive_dir.mkdir(parents=True, exist_ok=True)
        (archive_dir / "evidence").mkdir(parents=True, exist_ok=True)
        runtime_dir.mkdir(parents=True, exist_ok=True)

        messages_jsonl = "".join(json.dumps(message_to_dict(m)) + "\n" for m in self.thread_messages)
        (archive_dir / "messages.jsonl").write_text(messages_jsonl, encoding="utf-8")

        (archive_dir / "hypothesis.md").write_text(self._render_hypothesis_md(), encoding="utf-8")
        (archive_dir / "experiment_plan.md").write_text(self._render_experiment_plan_md(), encoding="utf-8")
        (archive_dir / "conclusion.md").write_text(self._render_conclusion_md(), encoding="utf-8")

        if self.experiment is not None:
            (archive_dir / "results.json").write_text(experiment_to_json(self.experiment), encoding="utf-8")
            if self.experiment.evidence:
                evidence_text = "\n".join(f"- {item}" for item in self.experiment.evidence) + "\n"
                (archive_dir / "evidence" / "evidence.txt").write_text(evidence_text, encoding="utf-8")

        return archive_dir, runtime_dir

    def _write_runtime_snapshot(self, runtime_dir: Path) -> None:
        state_payload = {
            "thread_id": self.thread_id,
            "state": self.state,
            "rounds_completed": self.rounds_completed,
            "turns_used": self.turn_number,
            "consecutive_failures": self.consecutive_failures,
            "invalid_message_count": self.invalid_message_count,
            "experiment_retries": self.experiment_retries,
            "stopped_early": self._stopped,
            "stop_reason": self._stop_reason,
            "mock": self._preflight is None,
        }
        (runtime_dir / "state.json").write_text(json.dumps(state_payload, indent=2) + "\n", encoding="utf-8")

        mailbox_jsonl = "".join(
            json.dumps(
                {
                    "mailbox_sequence": item.mailbox_sequence,
                    "thread_id": item.thread_id,
                    "sender": item.sender,
                    "recipient": item.recipient,
                    "status": item.status,
                    "message": message_to_dict(item.message),
                }
            )
            + "\n"
            for item in self.mailbox.items
        )
        (runtime_dir / "mailbox.jsonl").write_text(mailbox_jsonl, encoding="utf-8")

        self.events.write_jsonl(runtime_dir / "events.jsonl")

    # -- archive prose rendering ---------------------------------------------

    def _render_hypothesis_md(self) -> str:
        if self.experiment is None:
            return (
                f"# {self.thread_id} — Hypothesis\n\n"
                "No experiment record was created before this shift stopped "
                f"({self._stop_reason or 'no reason recorded'}).\n"
            )
        return (
            f"# {self.thread_id} — Hypothesis\n\n"
            f"{self.experiment.hypothesis}\n\n"
            "## Mechanism\n\n"
            f"{self.experiment.mechanism or '(none recorded)'}\n\n"
            "## Competing hypotheses\n\n"
            + ("\n".join(f"- {item}" for item in self.experiment.competing_hypotheses) or "(none)")
            + "\n"
        )

    def _render_experiment_plan_md(self) -> str:
        plan = self.experiment.experiment_plan if self.experiment else ""
        return (
            f"# {self.thread_id} — Experiment plan\n\n"
            f"{plan or '(no experiment plan was finalized before this shift stopped)'}\n"
        )

    def _render_conclusion_md(self) -> str:
        lines = [f"# {self.thread_id} — Conclusion", ""]
        lines.append(f"Final orchestration state: `{self.state}`")
        if self._stopped:
            lines.append(f"Shift stop reason: {self._stop_reason}")
        lines.append("")
        if self.experiment is not None:
            lines.append(f"Conclusion state: `{self.experiment.conclusion_state}`")
            lines.append("")
            lines.append("## Remaining uncertainty")
            lines.append("")
            lines.append(self.experiment.remaining_uncertainty or "(none recorded)")
            lines.append("")
            lines.append("## Recommended next action")
            lines.append("")
            lines.append(self.experiment.recommended_next_action or "(none recorded)")
        else:
            lines.append("No experiment record was ever created for this thread.")
        lines.append("")
        if self._preflight is None:
            lines.append(
                "This is a MOCK shift — no real Claude Code or Codex process was "
                "invoked, and no real repository experiment was executed."
            )
        else:
            lines.append(
                f"This shift used a real Claude Code process for Claude's turns "
                f"({self._count_provider_calls()} provider call(s)) behind a "
                f"read-only, no-git-write tool boundary; Codex remained a "
                f"deterministic MOCK. No real repository experiment was executed."
            )
        return "\n".join(lines) + "\n"


def _violates_safety(message: FrontierMessage) -> str | None:
    haystack = f"{message.claim} {message.requested_action}".lower()
    for phrase in SAFETY_TRIGGER_PHRASES:
        if phrase in haystack:
            return phrase
    return None
