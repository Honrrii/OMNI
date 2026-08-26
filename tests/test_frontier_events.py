"""
Phase 2B guard: the append-only event log (omni/frontier/events.py) assigns
deterministic, gap-free ordering and exposes no public way to delete or
rewrite a previously appended event. No network, no LLM calls, no model
process.
"""
from __future__ import annotations

import pytest

from omni.frontier.events import EventLog, FrontierEvent, read_jsonl

CREATED_AT = "2026-08-26T00:00:00Z"


def test_append_assigns_monotonic_sequence():
    log = EventLog()
    first = log.append(thread_id="OMNI-FRONTIER-0001", event_type="SHIFT_STARTED", actor="orchestrator", state="IDLE", created_at=CREATED_AT)
    second = log.append(thread_id="OMNI-FRONTIER-0001", event_type="THREAD_CREATED", actor="orchestrator", state="SHIFT_STARTING", created_at=CREATED_AT)
    assert first.sequence == 1
    assert second.sequence == 2


def test_events_property_returns_defensive_copy():
    log = EventLog()
    log.append(thread_id="OMNI-FRONTIER-0001", event_type="SHIFT_STARTED", actor="orchestrator", state="IDLE", created_at=CREATED_AT)
    snapshot = log.events
    snapshot.append("not a real event")
    assert len(log) == 1
    assert len(log.events) == 1


def test_event_log_has_no_public_delete_or_rewrite_api():
    log = EventLog()
    public_api = {name for name in dir(log) if not name.startswith("_")}
    assert "remove" not in public_api
    assert "clear" not in public_api
    assert "pop" not in public_api
    assert "__setitem__" not in dir(log)
    assert "__delitem__" not in dir(log)


def test_invalid_event_type_rejected():
    log = EventLog()
    with pytest.raises(ValueError):
        log.append(thread_id="OMNI-FRONTIER-0001", event_type="NOT_A_REAL_EVENT", actor="orchestrator", state="IDLE", created_at=CREATED_AT)


def test_frontier_event_rejects_empty_required_fields():
    with pytest.raises(ValueError):
        FrontierEvent(sequence=1, thread_id="", event_type="SHIFT_STARTED", actor="orchestrator", state="IDLE", created_at=CREATED_AT)
    with pytest.raises(ValueError):
        FrontierEvent(sequence=0, thread_id="OMNI-FRONTIER-0001", event_type="SHIFT_STARTED", actor="orchestrator", state="IDLE", created_at=CREATED_AT)


def test_jsonl_round_trip_preserves_order(tmp_path):
    log = EventLog()
    for index in range(5):
        log.append(
            thread_id="OMNI-FRONTIER-0001",
            event_type="STATE_CHANGED",
            actor="orchestrator",
            state=f"STATE_{index}",
            created_at=CREATED_AT,
        )
    path = tmp_path / "events.jsonl"
    log.write_jsonl(path)

    restored = read_jsonl(path)
    assert [event.sequence for event in restored] == [1, 2, 3, 4, 5]
    assert [event.state for event in restored] == [f"STATE_{index}" for index in range(5)]
    assert restored == log.events
