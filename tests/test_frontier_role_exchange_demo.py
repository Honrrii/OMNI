"""
Phase 2A demonstration: the same provider-neutral Frontier Research
contracts (omni/frontier/protocol.py, omni/frontier/experiments.py) can
represent a full Claude (omni-frontier-architect) <-> Codex
(omni-frontier-experimentalist) research exchange.

This is a deterministic, non-model test. It does not invoke Claude Code or
Codex, does not open a connection, and does not call a model API — it only
constructs, validates, and round-trips FrontierMessage / FrontierExperiment
records through the exact dataclasses both skills are required to use.

Thread ID OMNI-FRONTIER-9999 here is a fixture id for this demonstration
only, not a reservation of a real research thread — a genuine thread gets
the next sequential id per .omni-lab/protocols/FRONTIER_RESEARCH_PROTOCOL.md
and is archived under .omni-lab/, which this test does not touch.
"""
from __future__ import annotations

import json

import pytest

from omni.frontier.experiments import (
    CONCLUSION_STATES,
    FrontierExperiment,
    FrontierResearchScore,
    frontier_experiment_from_dict,
)
from omni.frontier.experiments import to_json as experiment_to_json
from omni.frontier.protocol import (
    FrontierMessage,
    frontier_message_from_dict,
    to_json,
)

THREAD_ID = "OMNI-FRONTIER-9999"
CREATED_AT = "2026-08-26T00:00:00Z"


def _build_exchange() -> list[FrontierMessage]:
    """OMNI-FRONTIER-9999 demonstration thread.

    HYPOTHESIS (claude) -> COUNTER_HYPOTHESIS (codex) ->
    EXPERIMENT_PROPOSAL (claude) -> CHALLENGE (codex) ->
    EXPERIMENT_RESULT (claude) -> CONCLUSION (codex)
    """
    messages: list[FrontierMessage] = []

    hypothesis = FrontierMessage(
        thread_id=THREAD_ID,
        sequence=1,
        from_agent="claude",
        to_agent="codex",
        message_type="HYPOTHESIS",
        claim=(
            "Persistent engineering memory improves design consistency "
            "across OMNI mission runs."
        ),
        mechanism=(
            "A persisted memory store lets later runs reuse prior design "
            "decisions instead of re-deriving them, reducing drift."
        ),
        evidence=["omni/frontier/experiments.py"],
        uncertainties=[
            "Whether the effect is persistence itself, or just more "
            "metadata being available to later runs.",
        ],
        requested_action="Independently evaluate before an experiment is run.",
        confidence=0.61,
        created_at=CREATED_AT,
    )
    messages.append(hypothesis)

    counter_hypothesis = FrontierMessage(
        thread_id=THREAD_ID,
        sequence=2,
        from_agent="codex",
        to_agent="claude",
        message_type="COUNTER_HYPOTHESIS",
        claim=(
            "The observed consistency improvement may come from repeated "
            "metadata being available, not persistence of memory itself."
        ),
        mechanism=(
            "A run with additional metadata but no persistence could "
            "produce the same consistency gain, which would falsify "
            "persistence as the causal mechanism."
        ),
        evidence=["omni/frontier/protocol.py"],
        uncertainties=["No experiment has isolated metadata from persistence yet."],
        requested_action=(
            "Run a three-arm comparison: baseline, metadata-without-"
            "persistence, and persistent memory."
        ),
        confidence=0.28,
        in_reply_to=1,
        created_at=CREATED_AT,
    )
    messages.append(counter_hypothesis)

    experiment_proposal = FrontierMessage(
        thread_id=THREAD_ID,
        sequence=3,
        from_agent="claude",
        to_agent="codex",
        message_type="EXPERIMENT_PROPOSAL",
        claim=(
            "A controlled three-arm comparison (A: baseline, B: metadata "
            "without persistence, C: persistent memory) can distinguish "
            "the two explanations."
        ),
        mechanism="Ablation isolates persistence from metadata availability.",
        evidence=["omni/frontier/experiments.py"],
        requested_action="Codex: challenge the design before it runs.",
        confidence=0.61,
        in_reply_to=2,
        created_at=CREATED_AT,
    )
    messages.append(experiment_proposal)

    challenge = FrontierMessage(
        thread_id=THREAD_ID,
        sequence=4,
        from_agent="codex",
        to_agent="claude",
        message_type="CHALLENGE",
        claim=(
            "Arm B and arm C must use the same underlying task set, or a "
            "difference in outcome could be sample selection, not the "
            "mechanism under test."
        ),
        evidence=["omni/frontier/experiments.py"],
        requested_action="Confirm arms B and C share one fixed task set before running.",
        confidence=0.5,
        in_reply_to=3,
        created_at=CREATED_AT,
    )
    messages.append(challenge)

    experiment_result = FrontierMessage(
        thread_id=THREAD_ID,
        sequence=5,
        from_agent="claude",
        to_agent="codex",
        message_type="EXPERIMENT_RESULT",
        claim=(
            "All three arms ran against the same fixed task set; arm C "
            "showed materially lower stale-assumption propagation than "
            "arm B."
        ),
        evidence=["omni/frontier/experiments.py"],
        confidence=0.84,
        in_reply_to=4,
        created_at=CREATED_AT,
    )
    messages.append(experiment_result)

    conclusion = FrontierMessage(
        thread_id=THREAD_ID,
        sequence=6,
        from_agent="codex",
        to_agent="all",
        message_type="CONCLUSION",
        claim=(
            "SUPPORTED: persistence, not merely additional metadata, "
            "accounts for the consistency improvement given the shared "
            "task set across arms B and C."
        ),
        evidence=["omni/frontier/experiments.py"],
        confidence=0.76,
        in_reply_to=5,
        created_at=CREATED_AT,
    )
    messages.append(conclusion)

    return messages


def test_exchange_uses_only_the_shared_frontier_message_contract():
    exchange = _build_exchange()
    assert len(exchange) == 6
    for message in exchange:
        assert isinstance(message, FrontierMessage)
        assert message.thread_id == THREAD_ID


def test_exchange_alternates_between_claude_and_codex_as_from_agent():
    exchange = _build_exchange()
    from_agents = [message.from_agent for message in exchange]
    assert from_agents == ["claude", "codex", "claude", "codex", "claude", "codex"]


def test_exchange_sequence_numbers_are_monotonic_and_reply_chained():
    exchange = _build_exchange()
    for index, message in enumerate(exchange, start=1):
        assert message.sequence == index
    for message in exchange[1:]:
        assert message.in_reply_to == message.sequence - 1


def test_exchange_covers_hypothesis_through_conclusion_message_types():
    exchange = _build_exchange()
    observed_types = [message.message_type for message in exchange]
    assert observed_types == [
        "HYPOTHESIS",
        "COUNTER_HYPOTHESIS",
        "EXPERIMENT_PROPOSAL",
        "CHALLENGE",
        "EXPERIMENT_RESULT",
        "CONCLUSION",
    ]


def test_exchange_round_trips_through_json_without_loss():
    exchange = _build_exchange()
    for message in exchange:
        payload = json.loads(to_json(message))
        restored = frontier_message_from_dict(payload)
        assert restored == message


def test_confidence_shifts_toward_agreement_after_the_experiment_runs():
    exchange = _build_exchange()
    initial_claude, initial_codex = exchange[0], exchange[1]
    final_claude, final_codex = exchange[4], exchange[5]
    assert initial_claude.confidence < final_claude.confidence
    assert initial_codex.confidence < final_codex.confidence
    initial_gap = abs(initial_claude.confidence - initial_codex.confidence)
    final_gap = abs(final_claude.confidence - final_codex.confidence)
    assert final_gap < initial_gap


def test_conclusion_message_uses_an_existing_conclusion_state_vocabulary_word():
    exchange = _build_exchange()
    conclusion = exchange[-1]
    assert any(state in conclusion.claim for state in CONCLUSION_STATES)


def test_demonstration_thread_can_be_archived_as_a_frontier_experiment():
    """The same thread escalates into a FrontierExperiment record, using
    exactly the shape both omni-frontier-architect and
    omni-frontier-experimentalist are required to produce — no
    Codex-specific experiment shape exists.
    """
    experiment = FrontierExperiment(
        experiment_id=THREAD_ID,
        title="Persistent engineering memory vs. metadata availability",
        hypothesis=(
            "Persistent engineering memory improves design consistency "
            "across OMNI mission runs."
        ),
        scoring=FrontierResearchScore(
            omni_alignment=4,
            potential_impact=4,
            information_gain=4,
            generalizability=3,
            novelty=3,
            experimentalability=4,
            risk=1,
            implementation_cost=2,
        ),
        created_at=CREATED_AT,
        mechanism=(
            "A persisted memory store lets later runs reuse prior design "
            "decisions instead of re-deriving them, reducing drift."
        ),
        competing_hypotheses=[
            "The improvement comes from additional metadata availability, "
            "not persistence itself.",
        ],
        predicted_evidence=[
            "Arm C shows lower stale-assumption propagation than arm B "
            "on a shared task set.",
        ],
        experiment_plan=(
            "Three-arm ablation (baseline, metadata-without-persistence, "
            "persistent memory) against one fixed task set."
        ),
        participants=["claude", "codex"],
        status="COMPLETE",
        conclusion_state="SUPPORTED",
        evidence=["omni/frontier/experiments.py"],
        counterevidence=[],
        limitations=[
            "Single task-set sample; not yet replicated across mission types.",
        ],
        remaining_uncertainty=(
            "Whether the effect generalizes beyond the tested task set."
        ),
        recommended_next_action=(
            "Replicate the ablation against a second, unrelated task set "
            "before treating this as generalizable."
        ),
    )

    assert experiment.status == "COMPLETE"
    assert experiment.conclusion_state in CONCLUSION_STATES

    serialized = experiment_to_json(experiment)
    restored = frontier_experiment_from_dict(json.loads(serialized))
    assert restored.experiment_id == THREAD_ID
    assert restored.conclusion_state == "SUPPORTED"


def test_incomplete_experiment_without_conclusion_state_still_validates():
    """PROPOSED status needs no conclusion_state yet -- both roles can
    hand off a still-open thread, not just a closed one.
    """
    experiment = FrontierExperiment(
        experiment_id=THREAD_ID,
        title="Persistent engineering memory vs. metadata availability",
        hypothesis="Persistent engineering memory improves design consistency.",
        scoring=FrontierResearchScore(
            omni_alignment=4,
            potential_impact=4,
            information_gain=4,
            generalizability=3,
            novelty=3,
            experimentalability=4,
            risk=1,
            implementation_cost=2,
        ),
        created_at=CREATED_AT,
        participants=["claude", "codex"],
        status="PROPOSED",
    )
    assert experiment.conclusion_state is None


def test_malformed_message_type_is_rejected_by_the_shared_contract():
    """Neither role gets a permissive parallel schema -- an invented
    message type is rejected by the one enforced contract.
    """
    with pytest.raises(ValueError):
        FrontierMessage(
            thread_id=THREAD_ID,
            sequence=1,
            from_agent="codex",
            to_agent="claude",
            message_type="CODEX_ONLY_VERDICT",
            claim="This message type does not exist in MESSAGE_TYPES.",
            created_at=CREATED_AT,
        )
