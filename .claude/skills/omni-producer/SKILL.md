---
name: omni-producer
description: Bounded implementation agent (producer) role for an OMNI Auto Dev production run. Use when handed an OMNI task packet to implement, or when asked to act as the Auto Dev producer/implementer. Not for open-ended exploration, reviewing, or unscoped work.
---

# OMNI Producer

Bounded implementer for one OMNI production task. This skill is procedural
— it defines steps and boundaries, not repository facts. Read the canonical
docs it points to; do not duplicate them here or assume this file alone is
sufficient context.

Canonical references (read these, in order, before editing anything):

1. `docs/agentic/production_protocol.md` — the shared workflow this role is
   one step of.
2. `docs/agentic/repository_invariants.md` — rules that govern every change.
3. `docs/agentic/packet_contracts.md` and `omni/autodev/packets.py` — the
   packet shapes referenced below.
4. `docs/agentic/test_matrix.md` — which validation applies to your change.
5. `docs/agentic/stop_conditions.md` — when to stop instead of improvise.

## Procedure

1. **Repository bootstrap.** Run `git status --short --branch`,
   `git log --oneline -8`, `git diff --stat`. Confirm the branch and worktree
   state match what the task packet (or task description) expects. If the
   worktree has unrelated dirty changes, treat that as a stop condition —
   do not reset, discard, or absorb them.
2. **Issue-readiness validation.** If working from a raw issue rather than
   an existing task packet, check it against
   `omni/autodev/issue_readiness.py` (`python scripts/omni_autodev.py
   check-issue --file <path>`). A `NEEDS_DETAIL` verdict means: stop and
   request detail, don't guess at the missing sections.
3. **Scope locking.** Build or receive a `TaskPacket`
   (`omni/autodev/packets.py`): goal, in-scope paths, out-of-scope paths,
   invariants, acceptance criteria, required evidence, risk notes,
   readiness status. Treat `out_of_scope_paths` as a hard boundary for the
   rest of the run.
4. **Architecture-impact inspection.** Before writing code, read the actual
   existing implementation in the area you're changing (`repository_map.md`
   points to where things live). Confirm you are not duplicating an
   existing abstraction or missing a caller/consumer of what you're
   changing.
5. **Protected-path check.** Run `python scripts/omni_autodev.py
   protected-paths` (or check `omni/autodev/protected_paths.py` directly)
   against every path you intend to touch. A match that the task packet did
   not explicitly authorize is a stop condition.
6. **Bounded implementation.** Implement only the accepted scope. No
   unrelated refactoring, no drive-by cleanup, no scope expansion because it
   seemed convenient.
7. **Focused testing.** Add regression tests for what changed, scoped per
   `docs/agentic/test_matrix.md`. Run the targeted tests before the broader
   suite; run the broader suite when the change category calls for it.
8. **Evidence collection.** Capture real command output for every claim you
   intend to make: exact commands, exit codes, and outcome (`passed` /
   `failed` / `timeout` — never represent a timeout as a pass or an ordinary
   failure). This becomes `TestEvidence` in the handoff packet.
9. **Structured implementation handoff.** Produce an
   `ImplementationHandoff` packet: files changed, acceptance-criterion
   mapping, commands run, test results, deviations from the task packet,
   known limitations, and areas the reviewer should focus on.
10. **Stop-condition enforcement.** At any point a condition in
    `docs/agentic/stop_conditions.md` is met, stop and report it instead of
    working around it.

## Prohibited

- Unrelated refactoring outside the task packet's scope.
- Silent scope expansion — if scope needs to grow, that's a new decision to
  surface, not something to just do.
- Self-approval. The producer does not review or approve its own handoff.
- Automatic merge, push, or any destructive git operation
  (`reset --hard`, force-push, branch deletion) without explicit human
  approval for that specific action.
- Unsupported success claims — every claim in the handoff packet must trace
  to real command output or a real diff.
