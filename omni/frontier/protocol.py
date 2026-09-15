"""
OMNI Frontier Research message protocol contracts (Phase 1).

Structured, validated shapes for the Claude <-> Codex frontier research
message protocol described in
`.omni-lab/protocols/FRONTIER_RESEARCH_PROTOCOL.md`. Mirrors the validation
style of `omni/autodev/packets.py`: an invalid thread ID, message type, or
out-of-range confidence raises `ValueError` at construction time rather than
being caught later by whoever reads the payload.

`.omni-lab/schemas/frontier_message.schema.json` is the provider-neutral
wire contract for this same shape (so Codex, or any other agent, can
validate a message without importing this Python package). Field names are
kept identical between the two on purpose — see
`tests/test_frontier_schemas.py` for the drift check between them.

This module only builds, validates, and (de)serializes messages. It does
not send a message anywhere, launch Claude or Codex, or call a model API.
"""
from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field

PROTOCOL_VERSION = "0.1"

# Matches OMNI-FRONTIER-0001, OMNI-FRONTIER-12345, etc. Four digits is the
# v0.1 floor, not a ceiling -- IDs are not zero-padded back down once a
# thread count grows past 9999.
THREAD_ID_PATTERN = re.compile(r"^OMNI-FRONTIER-\d{4,}$")

MESSAGE_TYPES = (
    "HYPOTHESIS",
    "COUNTER_HYPOTHESIS",
    "REVIEW_REQUEST",
    "REVIEW_FINDING",
    "EVIDENCE",
    "COUNTEREVIDENCE",
    "EXPERIMENT_PROPOSAL",
    "EXPERIMENT_RESULT",
    "CHALLENGE",
    "RESPONSE",
    "CONCLUSION",
    "ESCALATE_TO_HUMAN",
)


def validate_thread_id(value: str) -> str:
    """Return `value` unchanged if it matches `OMNI-FRONTIER-<4+ digits>`.

    Raises `ValueError` otherwise. Shared by `FrontierMessage.thread_id` and
    `omni.frontier.experiments.FrontierExperiment.experiment_id` — one
    thread is one experiment's identifier space in v0.1, so both use the
    same format and the same validator rather than two parallel ID schemes.
    """
    if not isinstance(value, str) or not THREAD_ID_PATTERN.match(value):
        raise ValueError(
            f"invalid frontier thread id {value!r}; must match "
            f"{THREAD_ID_PATTERN.pattern!r} (e.g. 'OMNI-FRONTIER-0001')"
        )
    return value


def _require_nonempty(value: str, field_name: str, shape_name: str) -> None:
    if not value or not value.strip():
        raise ValueError(f"{shape_name}.{field_name} must be a non-empty string")


@dataclass
class FrontierMessage:
    """One message on an OMNI Frontier Research thread.

    `evidence` and `uncertainties` are meant to hold repository-checkable
    strings (a file path, a command, a test name), not narrative assertions
    — see `docs/agentic/repository_invariants.md`'s "another agent's
    verdict is not evidence." This contract does not forbid narrative
    content (that would require judgment, not structure), but a reviewing
    agent should treat an evidence entry that names nothing checkable as
    unsupported.
    """

    thread_id: str
    sequence: int
    from_agent: str
    to_agent: str
    message_type: str
    claim: str
    created_at: str
    mechanism: str = ""
    evidence: list[str] = field(default_factory=list)
    uncertainties: list[str] = field(default_factory=list)
    requested_action: str = ""
    confidence: float | None = None
    in_reply_to: int | None = None
    protocol_version: str = PROTOCOL_VERSION

    def __post_init__(self) -> None:
        validate_thread_id(self.thread_id)
        _require_nonempty(self.from_agent, "from_agent", "FrontierMessage")
        _require_nonempty(self.to_agent, "to_agent", "FrontierMessage")
        _require_nonempty(self.claim, "claim", "FrontierMessage")
        _require_nonempty(self.created_at, "created_at", "FrontierMessage")
        if self.message_type not in MESSAGE_TYPES:
            raise ValueError(
                f"invalid FrontierMessage.message_type {self.message_type!r}; "
                f"must be one of {MESSAGE_TYPES}"
            )
        if self.protocol_version != PROTOCOL_VERSION:
            raise ValueError(
                f"FrontierMessage.protocol_version {self.protocol_version!r} does not "
                f"match the current PROTOCOL_VERSION {PROTOCOL_VERSION!r} — a version "
                f"bump is a deliberate change to omni/frontier/protocol.py, not "
                f"something a message can drift into"
            )
        if self.sequence < 1:
            raise ValueError(
                f"FrontierMessage.sequence must be >= 1 (1-indexed within its "
                f"thread); got {self.sequence!r}"
            )
        if self.confidence is not None and not (0.0 <= self.confidence <= 1.0):
            raise ValueError(
                f"FrontierMessage.confidence must be within [0.0, 1.0] when given; "
                f"got {self.confidence!r}"
            )
        if self.in_reply_to is not None and self.in_reply_to < 1:
            raise ValueError(
                f"FrontierMessage.in_reply_to must be >= 1 when given; "
                f"got {self.in_reply_to!r}"
            )


def to_dict(message: FrontierMessage) -> dict:
    return asdict(message)


def to_json(message: FrontierMessage) -> str:
    return json.dumps(to_dict(message), indent=2) + "\n"


def frontier_message_from_dict(data: dict) -> FrontierMessage:
    return FrontierMessage(**data)
