"""
OMNI Frontier Research Lab — Phase 2B append-only event log.

A deterministically ordered, append-only record of what happened during one
research shift. Ordering is a monotonic integer sequence assigned by
`EventLog.append` itself, not wall-clock time — two events created in the
same millisecond (plausible under a deterministic mock orchestrator with no
real I/O latency) still have an unambiguous order. `created_at` is carried
as supplementary metadata only; nothing in this module or
`omni/frontier/orchestrator.py` sorts or compares by it.

`EventLog`'s public API has no method that deletes or rewrites a previously
appended event — see `docs/agentic/repository_invariants.md`'s "deterministic
enforcement belongs in Python... not something an agent could talk past."
`events` returns a defensive copy so a caller mutating the returned list
cannot reach back into the log's own storage.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

EVENT_TYPES: tuple[str, ...] = (
    "SHIFT_STARTED",
    "THREAD_CREATED",
    "STATE_CHANGED",
    "AGENT_TURN_STARTED",
    "AGENT_TURN_COMPLETED",
    "MESSAGE_CREATED",
    "MESSAGE_ROUTED",
    "MESSAGE_REJECTED",
    "DEBATE_ROUND_COMPLETED",
    "EXPERIMENT_RESULT_RECORDED",
    "CONCLUSION_REACHED",
    "BUDGET_EXHAUSTED",
    "SAFETY_STOP",
    "HUMAN_ESCALATION",
    "ARCHIVE_WRITTEN",
    "SHIFT_COMPLETED",
)


def _require_nonempty(value: str, field_name: str) -> None:
    if not value or not value.strip():
        raise ValueError(f"FrontierEvent.{field_name} must be a non-empty string")


@dataclass(frozen=True)
class FrontierEvent:
    """One append-only log entry.

    `sequence` is assigned by `EventLog.append`, never supplied by a caller
    directly (see `EventLog.append`'s signature) — that is what makes
    ordering deterministic and gap-free regardless of who is logging.
    """

    sequence: int
    thread_id: str
    event_type: str
    actor: str
    state: str
    created_at: str
    message_ref: int | None = None
    detail: str = ""
    context: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.sequence, int) or isinstance(self.sequence, bool) or self.sequence < 1:
            raise ValueError(f"FrontierEvent.sequence must be a positive int; got {self.sequence!r}")
        _require_nonempty(self.thread_id, "thread_id")
        _require_nonempty(self.actor, "actor")
        _require_nonempty(self.state, "state")
        _require_nonempty(self.created_at, "created_at")
        if self.event_type not in EVENT_TYPES:
            raise ValueError(
                f"invalid FrontierEvent.event_type {self.event_type!r}; "
                f"must be one of {EVENT_TYPES}"
            )
        if self.message_ref is not None and self.message_ref < 1:
            raise ValueError(
                f"FrontierEvent.message_ref must be >= 1 when given; got {self.message_ref!r}"
            )


class EventLog:
    """Append-only, sequence-ordered log of `FrontierEvent` entries.

    There is deliberately no `remove`, `clear`, or index-assignment method.
    A caller that wants to "fix" a bad event appends a new event describing
    the correction; it never edits history in place.
    """

    def __init__(self) -> None:
        self._events: list[FrontierEvent] = []

    def append(
        self,
        *,
        thread_id: str,
        event_type: str,
        actor: str,
        state: str,
        created_at: str,
        message_ref: int | None = None,
        detail: str = "",
        context: dict | None = None,
    ) -> FrontierEvent:
        event = FrontierEvent(
            sequence=len(self._events) + 1,
            thread_id=thread_id,
            event_type=event_type,
            actor=actor,
            state=state,
            created_at=created_at,
            message_ref=message_ref,
            detail=detail,
            context=dict(context) if context else {},
        )
        self._events.append(event)
        return event

    @property
    def events(self) -> list[FrontierEvent]:
        """A defensive copy — mutating the returned list cannot alter the log."""
        return list(self._events)

    def __len__(self) -> int:
        return len(self._events)

    def __iter__(self):
        return iter(self.events)

    def to_jsonl(self) -> str:
        return "".join(json.dumps(asdict(event)) + "\n" for event in self._events)

    def write_jsonl(self, path: Path) -> None:
        Path(path).write_text(self.to_jsonl(), encoding="utf-8")


def read_jsonl(path: Path) -> list[FrontierEvent]:
    """Reconstruct a list of `FrontierEvent` from a events.jsonl file.

    Read-only reconstruction for archive/inspection purposes — this does not
    return a live `EventLog` a caller could append onto and mistake for the
    original in-memory log.
    """
    events: list[FrontierEvent] = []
    text = Path(path).read_text(encoding="utf-8")
    for line in text.splitlines():
        if not line.strip():
            continue
        events.append(FrontierEvent(**json.loads(line)))
    return events
