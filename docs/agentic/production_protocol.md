# OMNI Agentic Production Protocol (v0.1)

The canonical, provider-neutral workflow for taking an OMNI issue through
implementation and review. This document defines the workflow itself. It
does not restate repository facts (`repository_map.md`), enforceable rules
(`repository_invariants.md`), or packet shapes (`packet_contracts.md`) —
read those separately.

This is **workflow definition, not a running system**. Nothing in this
version launches a model, commits automatically, or merges automatically.
Every step is carried out by a human-directed agent session; the packets
below are the structured record of that session, not a queue a scheduler
drains.

## Workflow (v0.1)

```text
Issue
  → readiness evaluation
  → bounded task packet
  → producer implementation
  → implementation handoff
  → independent reviewer
  → bounded repair
  → closeout
```

1. **Issue.** A GitHub issue (or equivalent local issue body file) describes
   the work.
2. **Readiness evaluation.** The issue is checked for the sections a task
   packet needs (goal, scope, non-goals, acceptance criteria, validation
   commands, stop conditions). OMNI already has a deterministic local
   checker for this: `omni/autodev/issue_readiness.py`
   (`python scripts/omni_autodev.py check-issue --file <path>`). An issue
   that is `NEEDS_DETAIL` does not proceed to a task packet.
3. **Bounded task packet.** A `TaskPacket` (`packet_contracts.md`) is
   produced: goal, in-scope paths, out-of-scope paths, invariants that
   apply, acceptance criteria, required evidence, risk notes, and a
   readiness status. This is the scope contract for the rest of the run.
4. **Producer implementation.** One producer agent (Claude's default role,
   see `CLAUDE.md`) implements only the accepted scope, following
   `repository_invariants.md`, and adds focused regression tests.
5. **Implementation handoff.** The producer emits an `ImplementationHandoff`
   packet: files changed, acceptance-criterion mapping, commands run, test
   results (as `TestEvidence`), deviations, known limitations, and areas the
   reviewer should focus on.
6. **Independent reviewer.** One reviewer agent (Codex's default role, see
   `AGENTS.md`) inspects the task packet and implementation handoff against
   the actual repository and diff — independently, starting read-only — and
   produces a `ReviewPacket` with a verdict of `APPROVED`,
   `CHANGES_REQUIRED`, or `BLOCKED`.
7. **Bounded repair.** If `CHANGES_REQUIRED`, a `RepairPacket` scopes the
   fix: required actions, allowed repair scope, prohibited scope, evidence
   needed for re-review. Maximum **two** repair cycles in v0.1 — see
   `packet_contracts.md`.
8. **Closeout.** A `CloseoutPacket` records the final verdict, completed
   acceptance criteria, final test evidence, remaining limitations, commit
   information, and a recommended PR title/body. Human approval is still
   required before anything merges.

## v0.1 constraints

These bound the scope of this version deliberately — they are not
aspirational, they are what this version does and does not do:

- One producer, one reviewer, one writer at a time. No concurrent producers
  on overlapping scope.
- Maximum of two repair cycles. A third failed cycle is a stop condition
  (`stop_conditions.md`), not a third attempt.
- No automatic merge.
- No force push.
- No autonomous roadmap selection — a human or an explicit issue picks the
  next unit of work; nothing in this version chooses its own next task.
- No concurrent modification of overlapping files by more than one agent.

## Roles

- **Producer** (Claude's default production role): bounded implementer.
  Scope, prohibitions, and required outputs are in
  `.claude/skills/omni-producer/SKILL.md`.
- **Reviewer** (Codex's default production role): independent verifier.
  Scope, prohibitions, and required outputs are in
  `.agents/skills/omni-reviewer/SKILL.md`.

Both roles read this document and `repository_invariants.md` before doing
anything else in a production run.

## Evidence a reviewer needs

At minimum: the task packet and its acceptance criteria; the base and
reviewed commit SHAs; the actual changed-file list and diff; the source
around the diff, not only changed lines; real test output (not an assumed
result); and any generated artifacts relevant to the change (a mission
export tree, a screenshot, a validation report). See `test_matrix.md` for
which validation applies to which kind of change.

A packet or document describing a change is not evidence that the change is
correct. It orients a reviewer; it does not substitute for reading the diff.
