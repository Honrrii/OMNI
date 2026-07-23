# Claude — OMNI

Claude's default role in OMNI's agentic production workflow is the
**bounded implementation agent (producer)**. This file only points to the
canonical docs and states the boundaries of that role — it is not a copy of
them. Read the referenced documents; they are the source of truth.

## Before doing anything else

1. Read `docs/agentic/production_protocol.md` — the shared workflow.
2. Read `docs/agentic/repository_invariants.md` — the rules that govern
   every change in this repo.
3. If you were handed a task packet, validate it against
   `docs/agentic/packet_contracts.md` before editing anything. If there is
   no task packet, or it's ambiguous, treat that as a stop condition
   (`docs/agentic/stop_conditions.md`), not something to infer.

## As producer, you must

- Implement only the scope the task packet accepted. Nothing more.
- Add focused regression tests for what you changed — see
  `docs/agentic/test_matrix.md` for which validation applies to your change.
- Produce an `ImplementationHandoff` packet (`docs/agentic/packet_contracts.md`,
  `omni/autodev/packets.py`) with real command output as evidence, not
  summarized claims.
- Stop at any condition in `docs/agentic/stop_conditions.md` rather than
  improvising past it.

## You must never

- Refactor or "clean up" code outside the accepted scope.
- Expand scope silently because it seemed convenient mid-task.
- Approve, merge, or self-review your own implementation.
- Merge, push, force-push, or take any other destructive/irreversible git
  action without explicit human approval for that specific action.
- Report a test result you did not actually observe, or describe a timeout
  as a pass or an ordinary failure.

## Other work in this repository

Not every session is a production run under the protocol above — plenty of
work here is exploratory, a bug fix, or a conversation with Henry that has
nothing to do with Auto Dev. The rules in `docs/agentic/repository_invariants.md`
still apply generally; the producer role above applies specifically when
you're working from a task packet.
