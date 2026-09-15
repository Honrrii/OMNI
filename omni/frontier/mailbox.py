"""
OMNI Frontier Research Lab — Phase 2B deterministic mailbox.

A sender never calls a recipient directly; every `FrontierMessage`
(`omni/frontier/protocol.py`) passes through `Mailbox.deliver`, which is the
single choke point that enforces:

- only a valid, already-constructed `FrontierMessage` may enter (malformed
  data cannot reach this module — `FrontierMessage.__post_init__` already
  raised before a caller could get this far);
- the recipient must be a known participant (`FrontierLabConfig.participants`);
- no silent overwrite — a `(thread_id, message.sequence)` pair can be
  delivered exactly once;
- stable, gap-free ordering — a thread's messages must arrive with
  `sequence` exactly one more than the last accepted sequence for that
  thread (this doubles as duplicate detection: re-delivering `sequence` N
  after N has already been accepted is rejected, not silently accepted a
  second time);
- a processed/unprocessed lifecycle per item, so the orchestrator can tell
  a delivered-but-not-yet-consumed message from one already folded into the
  thread record.

This module keeps orchestration auditable: later Claude/Codex integration
(Phase 3+) still has to go through this same choke point, so the audit
trail does not depend on which adapter is real.
"""
from __future__ import annotations

from dataclasses import dataclass

from omni.frontier.protocol import FrontierMessage

MAILBOX_STATUSES: tuple[str, ...] = ("PENDING", "PROCESSED")


class MailboxRejectionError(ValueError):
    """Raised by `Mailbox.deliver` when a message cannot be accepted.

    Carries `reason` as a short machine-checkable code
    (`MailboxRejectionReason`) in addition to the human-readable message, so
    a caller (the orchestrator) can react differently to, say, a duplicate
    versus an unknown recipient without parsing prose.
    """

    def __init__(self, reason: str, message: str):
        self.reason = reason
        super().__init__(message)


class MailboxRejectionReason:
    UNKNOWN_RECIPIENT = "UNKNOWN_RECIPIENT"
    DUPLICATE_SEQUENCE = "DUPLICATE_SEQUENCE"
    OUT_OF_ORDER = "OUT_OF_ORDER"


@dataclass(frozen=True)
class MailboxItem:
    """One accepted mailbox entry.

    `mailbox_sequence` is the mailbox's own monotonic counter (assigned by
    `Mailbox.deliver`), distinct from `message.sequence` (the thread-level
    ordering `FrontierMessage` itself carries) — the mailbox may one day
    interleave more than one thread, so it needs an ordering key that is not
    scoped to a single thread.
    """

    mailbox_sequence: int
    thread_id: str
    sender: str
    recipient: str
    message: FrontierMessage
    status: str


class Mailbox:
    """Deterministic, append-only message router for one or more threads."""

    def __init__(self, participants: tuple[str, ...]):
        if not participants:
            raise ValueError("Mailbox requires at least one known participant")
        self._participants = frozenset(participants)
        self._items: list[MailboxItem] = []
        self._next_expected_sequence: dict[str, int] = {}

    @property
    def participants(self) -> frozenset[str]:
        return self._participants

    def deliver(self, message: FrontierMessage) -> MailboxItem:
        """Route `message` through the mailbox. Never called by a sender
        directly reaching a recipient — the orchestrator is the only caller.

        Raises `MailboxRejectionError` for an unknown recipient, a duplicate
        `(thread_id, sequence)`, or an out-of-order `sequence`. Returns the
        accepted `MailboxItem` (status `PENDING`) otherwise.
        """
        if message.to_agent not in self._participants:
            raise MailboxRejectionError(
                MailboxRejectionReason.UNKNOWN_RECIPIENT,
                f"mailbox recipient {message.to_agent!r} is not a known participant "
                f"({sorted(self._participants)!r}); a sender may not address anyone "
                f"outside the configured shift",
            )

        expected = self._next_expected_sequence.get(message.thread_id, 1)
        if message.sequence < expected:
            raise MailboxRejectionError(
                MailboxRejectionReason.DUPLICATE_SEQUENCE,
                f"mailbox already accepted sequence {message.sequence} (or later) on "
                f"thread {message.thread_id!r}; refusing to silently overwrite it",
            )
        if message.sequence > expected:
            raise MailboxRejectionError(
                MailboxRejectionReason.OUT_OF_ORDER,
                f"mailbox expected sequence {expected} on thread {message.thread_id!r}, "
                f"got {message.sequence}; messages must arrive in gap-free order",
            )

        item = MailboxItem(
            mailbox_sequence=len(self._items) + 1,
            thread_id=message.thread_id,
            sender=message.from_agent,
            recipient=message.to_agent,
            message=message,
            status="PENDING",
        )
        self._items.append(item)
        self._next_expected_sequence[message.thread_id] = expected + 1
        return item

    def mark_processed(self, mailbox_sequence: int) -> MailboxItem:
        """Transition one item from PENDING to PROCESSED.

        This replaces the stored item with a new frozen instance rather than
        mutating a shared object in place — no caller holding an earlier
        reference to the PENDING item observes it silently changing under
        them.
        """
        for index, item in enumerate(self._items):
            if item.mailbox_sequence == mailbox_sequence:
                if item.status == "PROCESSED":
                    return item
                updated = MailboxItem(
                    mailbox_sequence=item.mailbox_sequence,
                    thread_id=item.thread_id,
                    sender=item.sender,
                    recipient=item.recipient,
                    message=item.message,
                    status="PROCESSED",
                )
                self._items[index] = updated
                return updated
        raise KeyError(f"no mailbox item with mailbox_sequence={mailbox_sequence}")

    def inbox_for(self, recipient: str, *, thread_id: str | None = None, pending_only: bool = True) -> list[MailboxItem]:
        """Items addressed to `recipient`, in stable delivery order."""
        results = []
        for item in self._items:
            if item.recipient != recipient:
                continue
            if thread_id is not None and item.thread_id != thread_id:
                continue
            if pending_only and item.status != "PENDING":
                continue
            results.append(item)
        return results

    @property
    def items(self) -> list[MailboxItem]:
        return list(self._items)

    def __len__(self) -> int:
        return len(self._items)
