"""
Phase 1 guard: OMNI Frontier Research message contracts
(omni/frontier/protocol.py) validate correctly, reject malformed thread
IDs/types/confidence, and serialize round-trip. No network, no LLM calls,
no GitHub API, no autonomous execution — these tests only exercise plain
dataclasses.
"""
from __future__ import annotations

import json

import pytest

from omni.frontier.protocol import (
    MESSAGE_TYPES,
    PROTOCOL_VERSION,
    FrontierMessage,
    frontier_message_from_dict,
    to_dict,
    to_json,
    validate_thread_id,
)


def _valid_kwargs(**overrides):
    kwargs = dict(
        thread_id="OMNI-FRONTIER-0001",
        sequence=1,
        from_agent="claude",
        to_agent="codex",
        message_type="HYPOTHESIS",
        claim="The mission graph and export pipeline disagree on schema version.",
        created_at="2026-08-26T00:00:00Z",
    )
    kwargs.update(overrides)
    return kwargs


# ---------------------------------------------------------------------------
# Thread ID format
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "thread_id",
    ["OMNI-FRONTIER-0001", "OMNI-FRONTIER-9999", "OMNI-FRONTIER-12345"],
)
def test_validate_thread_id_accepts_valid_ids(thread_id):
    assert validate_thread_id(thread_id) == thread_id


@pytest.mark.parametrize(
    "thread_id",
    [
        "",
        "OMNI-FRONTIER-1",
        "OMNI-FRONTIER-001",
        "omni-frontier-0001",
        "OMNI-FRONTIER-0001x",
        "FRONTIER-0001",
        "OMNI-FRONTIER-",
        None,
        123,
    ],
)
def test_validate_thread_id_rejects_invalid_ids(thread_id):
    with pytest.raises(ValueError):
        validate_thread_id(thread_id)


# ---------------------------------------------------------------------------
# Valid message construction
# ---------------------------------------------------------------------------


def test_message_constructs_with_defaults():
    message = FrontierMessage(**_valid_kwargs())
    assert message.evidence == []
    assert message.uncertainties == []
    assert message.confidence is None
    assert message.in_reply_to is None
    assert message.protocol_version == PROTOCOL_VERSION


def test_message_accepts_all_message_types():
    for message_type in MESSAGE_TYPES:
        message = FrontierMessage(**_valid_kwargs(message_type=message_type))
        assert message.message_type == message_type


def test_message_accepts_boundary_confidence_values():
    for confidence in (0.0, 0.5, 1.0):
        message = FrontierMessage(**_valid_kwargs(confidence=confidence))
        assert message.confidence == confidence


# ---------------------------------------------------------------------------
# Invalid/required-field rejection
# ---------------------------------------------------------------------------


def test_message_rejects_missing_required_fields():
    with pytest.raises(TypeError):
        FrontierMessage(thread_id="OMNI-FRONTIER-0001")  # missing most fields


def test_message_rejects_invalid_message_type():
    with pytest.raises(ValueError):
        FrontierMessage(**_valid_kwargs(message_type="NOT_A_TYPE"))


def test_message_rejects_empty_claim():
    with pytest.raises(ValueError):
        FrontierMessage(**_valid_kwargs(claim="   "))


def test_message_rejects_invalid_thread_id():
    with pytest.raises(ValueError):
        FrontierMessage(**_valid_kwargs(thread_id="not-a-thread-id"))


def test_message_rejects_non_positive_sequence():
    with pytest.raises(ValueError):
        FrontierMessage(**_valid_kwargs(sequence=0))


@pytest.mark.parametrize("confidence", [-0.01, 1.01, 5.0, -5.0])
def test_message_rejects_out_of_range_confidence(confidence):
    with pytest.raises(ValueError):
        FrontierMessage(**_valid_kwargs(confidence=confidence))


def test_message_rejects_non_positive_in_reply_to():
    with pytest.raises(ValueError):
        FrontierMessage(**_valid_kwargs(in_reply_to=0))


def test_message_rejects_mismatched_protocol_version():
    with pytest.raises(ValueError):
        FrontierMessage(**_valid_kwargs(protocol_version="9.9"))


# ---------------------------------------------------------------------------
# Serialization round-trip
# ---------------------------------------------------------------------------


def test_message_to_dict_and_json_round_trip():
    message = FrontierMessage(
        **_valid_kwargs(
            mechanism="Two code paths write different field names for the same value.",
            evidence=["backend/app/mission_graph/builder.py"],
            uncertainties=["Whether this has ever produced a wrong graph in practice."],
            requested_action="Diff a real export against builder.py's expected fields.",
            confidence=0.4,
            in_reply_to=None,
        )
    )

    as_dict = to_dict(message)
    assert as_dict["thread_id"] == "OMNI-FRONTIER-0001"
    assert as_dict["evidence"] == ["backend/app/mission_graph/builder.py"]

    as_json = to_json(message)
    assert json.loads(as_json) == as_dict

    rebuilt = frontier_message_from_dict(as_dict)
    assert rebuilt == message
