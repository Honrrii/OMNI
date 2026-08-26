"""
Phase 1 guard: OMNI Frontier Research experiment contracts
(omni/frontier/experiments.py) validate correctly, cap the score dimensions
to 0..5, require every CONCLUSION_STATES value to carry meaningful
completion evidence (except BLOCKED_BY_REQUIRED_EVIDENCE's evidence list),
and serialize round-trip. No network, no LLM calls, no autonomous
execution — these tests only exercise plain dataclasses.
"""
from __future__ import annotations

import json

import pytest

from omni.frontier.experiments import (
    CONCLUSION_STATES,
    EXPERIMENT_STATUSES,
    PROTOCOL_VERSION,
    FrontierExperiment,
    FrontierResearchScore,
    frontier_experiment_from_dict,
    to_dict,
    to_json,
)


def _valid_score(**overrides):
    kwargs = dict(
        omni_alignment=3,
        potential_impact=3,
        information_gain=3,
        generalizability=3,
        novelty=3,
        experimentalability=3,
        risk=1,
        implementation_cost=2,
    )
    kwargs.update(overrides)
    return FrontierResearchScore(**kwargs)


def _valid_kwargs(**overrides):
    kwargs = dict(
        experiment_id="OMNI-FRONTIER-0001",
        title="Provenance shape drift across export and graph builder",
        hypothesis="export_manager.py and builder.py silently disagree on field names.",
        scoring=_valid_score(),
        created_at="2026-08-26T00:00:00Z",
    )
    kwargs.update(overrides)
    return kwargs


def _concluded_kwargs(conclusion_state="CONFIRMED", **overrides):
    kwargs = _valid_kwargs(
        status="COMPLETE",
        conclusion_state=conclusion_state,
        experiment_plan="Ran a real export, re-read it with builder.py, diffed field sets.",
        evidence=["outputs/omni_missions/example/mission_graph.json diff"],
        limitations=["Only tested one mission type."],
        remaining_uncertainty="Unknown whether other mission types hit the same drift.",
        recommended_next_action="Re-run against an aerospace-intent mission export.",
    )
    kwargs.update(overrides)
    return kwargs


# ---------------------------------------------------------------------------
# FrontierResearchScore
# ---------------------------------------------------------------------------


def test_score_constructs_with_valid_dimensions():
    score = _valid_score()
    assert score.total() == 3 + 3 + 3 + 3 + 3 + 3 + 1 + 2


@pytest.mark.parametrize("value", [-1, 6, 10])
def test_score_rejects_out_of_range_dimension(value):
    with pytest.raises(ValueError):
        _valid_score(novelty=value)


def test_score_rejects_non_int_dimension():
    with pytest.raises(ValueError):
        _valid_score(novelty=3.5)


def test_score_rejects_bool_dimension():
    # bool is a subclass of int in Python; must not silently pass as 0/1.
    with pytest.raises(ValueError):
        _valid_score(novelty=True)


# ---------------------------------------------------------------------------
# Valid experiment construction
# ---------------------------------------------------------------------------


def test_experiment_constructs_with_defaults():
    experiment = FrontierExperiment(**_valid_kwargs())
    assert experiment.status == "PROPOSED"
    assert experiment.conclusion_state is None
    assert experiment.competing_hypotheses == []
    assert experiment.protocol_version == PROTOCOL_VERSION


def test_experiment_accepts_all_statuses_when_not_complete():
    for status in ("PROPOSED", "IN_PROGRESS"):
        experiment = FrontierExperiment(**_valid_kwargs(status=status))
        assert experiment.status == status


@pytest.mark.parametrize("conclusion_state", CONCLUSION_STATES)
def test_experiment_accepts_all_conclusion_states_with_required_evidence(conclusion_state):
    experiment = FrontierExperiment(**_concluded_kwargs(conclusion_state=conclusion_state))
    assert experiment.conclusion_state == conclusion_state


def test_blocked_by_required_evidence_does_not_need_evidence_list():
    kwargs = _concluded_kwargs(conclusion_state="BLOCKED_BY_REQUIRED_EVIDENCE")
    kwargs["evidence"] = []
    experiment = FrontierExperiment(**kwargs)
    assert experiment.evidence == []


def test_competing_hypotheses_and_counterevidence_may_be_empty():
    experiment = FrontierExperiment(**_concluded_kwargs())
    assert experiment.competing_hypotheses == []
    assert experiment.counterevidence == []


# ---------------------------------------------------------------------------
# Required-field / invariant rejection
# ---------------------------------------------------------------------------


def test_experiment_rejects_missing_required_fields():
    with pytest.raises(TypeError):
        FrontierExperiment(experiment_id="OMNI-FRONTIER-0001")  # missing most fields


def test_experiment_rejects_invalid_experiment_id():
    with pytest.raises(ValueError):
        FrontierExperiment(**_valid_kwargs(experiment_id="not-an-id"))


def test_experiment_rejects_invalid_status():
    with pytest.raises(ValueError):
        FrontierExperiment(**_valid_kwargs(status="DONE"))


def test_experiment_rejects_invalid_conclusion_state():
    with pytest.raises(ValueError):
        FrontierExperiment(**_concluded_kwargs(conclusion_state="MAYBE"))


def test_experiment_rejects_mismatched_protocol_version():
    with pytest.raises(ValueError):
        FrontierExperiment(**_valid_kwargs(protocol_version="9.9"))


def test_complete_status_requires_conclusion_state():
    with pytest.raises(ValueError):
        FrontierExperiment(**_valid_kwargs(status="COMPLETE"))


@pytest.mark.parametrize(
    "missing_field",
    ["experiment_plan", "limitations", "remaining_uncertainty", "recommended_next_action"],
)
def test_concluded_experiment_rejects_missing_completion_evidence(missing_field):
    kwargs = _concluded_kwargs()
    empty_value = [] if missing_field == "limitations" else ""
    kwargs[missing_field] = empty_value
    with pytest.raises(ValueError):
        FrontierExperiment(**kwargs)


@pytest.mark.parametrize(
    "conclusion_state",
    [s for s in CONCLUSION_STATES if s != "BLOCKED_BY_REQUIRED_EVIDENCE"],
)
def test_concluded_experiment_requires_evidence_except_when_blocked(conclusion_state):
    kwargs = _concluded_kwargs(conclusion_state=conclusion_state)
    kwargs["evidence"] = []
    with pytest.raises(ValueError):
        FrontierExperiment(**kwargs)


def test_experiment_status_and_conclusion_state_lists_are_exact():
    assert EXPERIMENT_STATUSES == ("PROPOSED", "IN_PROGRESS", "COMPLETE")
    assert CONCLUSION_STATES == (
        "CONFIRMED",
        "REFUTED",
        "SUPPORTED",
        "PROMISING_UNPROVEN",
        "INCONCLUSIVE",
        "BLOCKED_BY_REQUIRED_EVIDENCE",
    )


# ---------------------------------------------------------------------------
# Serialization round-trip
# ---------------------------------------------------------------------------


def test_experiment_to_dict_and_json_round_trip():
    experiment = FrontierExperiment(**_concluded_kwargs())

    as_dict = to_dict(experiment)
    assert as_dict["experiment_id"] == "OMNI-FRONTIER-0001"
    assert as_dict["scoring"]["novelty"] == 3

    as_json = to_json(experiment)
    assert json.loads(as_json) == as_dict

    rebuilt = frontier_experiment_from_dict(as_dict)
    assert rebuilt == experiment
