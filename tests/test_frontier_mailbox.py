"""
Phase 2B guard: the deterministic mailbox (omni/frontier/mailbox.py) accepts
only valid FrontierMessage traffic between known participants, in gap-free
order, with no silent overwrite. No network, no LLM calls, no model
process.
"""
from __future__ import annotations

import pytest

from omni.frontier.mailbox import Mailbox, MailboxRejectionError, MailboxRejectionReason
from omni.frontier.protocol import FrontierMessage

CREATED_AT = "2026-08-26T00:00:00Z"


def _message(**overrides) -> FrontierMessage:
    kwargs = dict(
        thread_id="OMNI-FRONTIER-0001",
        sequence=1,
        from_agent="claude",
        to_agent="codex",
        message_type="HYPOTHESIS",
        claim="A test claim.",
        created_at=CREATED_AT,
    )
    kwargs.update(overrides)
    return FrontierMessage(**kwargs)


def test_deliver_accepts_valid_message_in_order():
    mailbox = Mailbox(participants=("claude", "codex"))
    item = mailbox.deliver(_message(sequence=1))
    assert item.status == "PENDING"
    assert item.mailbox_sequence == 1
    item2 = mailbox.deliver(_message(sequence=2, from_agent="codex", to_agent="claude", message_type="COUNTER_HYPOTHESIS"))
    assert item2.mailbox_sequence == 2


def test_deliver_rejects_unknown_recipient():
    mailbox = Mailbox(participants=("claude", "codex"))
    with pytest.raises(MailboxRejectionError) as excinfo:
        mailbox.deliver(_message(to_agent="human"))
    assert excinfo.value.reason == MailboxRejectionReason.UNKNOWN_RECIPIENT


def test_deliver_rejects_duplicate_sequence_no_silent_overwrite():
    mailbox = Mailbox(participants=("claude", "codex"))
    first = mailbox.deliver(_message(sequence=1))
    with pytest.raises(MailboxRejectionError) as excinfo:
        mailbox.deliver(_message(sequence=1, claim="A different claim entirely."))
    assert excinfo.value.reason == MailboxRejectionReason.DUPLICATE_SEQUENCE
    # The original item must be untouched by the rejected re-delivery attempt.
    assert mailbox.items == [first]


def test_deliver_rejects_out_of_order_sequence():
    mailbox = Mailbox(participants=("claude", "codex"))
    with pytest.raises(MailboxRejectionError) as excinfo:
        mailbox.deliver(_message(sequence=2))
    assert excinfo.value.reason == MailboxRejectionReason.OUT_OF_ORDER


def test_ordering_is_per_thread():
    mailbox = Mailbox(participants=("claude", "codex"))
    mailbox.deliver(_message(thread_id="OMNI-FRONTIER-0001", sequence=1))
    # A different thread starts its own sequence at 1 independently.
    mailbox.deliver(_message(thread_id="OMNI-FRONTIER-0002", sequence=1))
    mailbox.deliver(_message(thread_id="OMNI-FRONTIER-0001", sequence=2, from_agent="codex", to_agent="claude", message_type="COUNTER_HYPOTHESIS"))
    assert len(mailbox) == 3


def test_mark_processed_transitions_status_without_mutating_shared_item():
    mailbox = Mailbox(participants=("claude", "codex"))
    pending = mailbox.deliver(_message(sequence=1))
    assert pending.status == "PENDING"
    processed = mailbox.mark_processed(pending.mailbox_sequence)
    assert processed.status == "PROCESSED"
    # The originally returned object is frozen/unchanged.
    assert pending.status == "PENDING"


def test_mark_processed_unknown_sequence_raises():
    mailbox = Mailbox(participants=("claude", "codex"))
    with pytest.raises(KeyError):
        mailbox.mark_processed(999)


def test_inbox_for_filters_by_recipient_and_pending_status():
    mailbox = Mailbox(participants=("claude", "codex"))
    item1 = mailbox.deliver(_message(sequence=1, from_agent="claude", to_agent="codex"))
    mailbox.deliver(_message(sequence=2, from_agent="codex", to_agent="claude", message_type="COUNTER_HYPOTHESIS"))
    assert [item.mailbox_sequence for item in mailbox.inbox_for("codex")] == [1]
    mailbox.mark_processed(item1.mailbox_sequence)
    assert mailbox.inbox_for("codex") == []
    assert mailbox.inbox_for("codex", pending_only=False) == [mailbox.items[0]]


def test_mailbox_requires_at_least_one_participant():
    with pytest.raises(ValueError):
        Mailbox(participants=())
