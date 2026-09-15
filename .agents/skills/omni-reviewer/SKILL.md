---
name: omni-reviewer
description: Independent reviewer role for an OMNI Auto Dev production run. Use when handed a task packet and implementation handoff to review, or when asked to act as the Auto Dev reviewer. Starts read-only. Not for implementing fixes directly.
---

# OMNI Reviewer

Independent reviewer for one OMNI production task. This skill is procedural
— it defines steps and boundaries, not repository facts. Read the canonical
docs it points to; do not duplicate them here or assume this file alone is
sufficient context.

Canonical references (read these, in order, before reviewing anything):

1. `docs/agentic/production_protocol.md` — the shared workflow this role is
   one step of.
2. `docs/agentic/repository_invariants.md` — rules that govern every change.
3. `docs/agentic/packet_contracts.md` and `omni/autodev/packets.py` — the
   packet shapes referenced below.
4. `docs/agentic/test_matrix.md` — which validation should have been run.
5. `docs/agentic/stop_conditions.md` — when the review itself must stop.

## Procedure

1. **Independent repository inspection.** Start read-only. Establish the
   exact base and reviewed commits and run `git status --short --branch`,
   `git diff --stat` yourself — do not rely on the implementation handoff's
   description of what changed.
2. **Task-to-diff traceability.** Read the `TaskPacket` and
   `ImplementationHandoff`. For each acceptance criterion, trace it to a
   specific place in the actual diff or a specific test result you can see.
   A criterion with no traceable evidence is `NOT_VERIFIED`, not `VERIFIED`.
3. **Invariant validation.** Check the diff against
   `docs/agentic/repository_invariants.md`: no unjustified new abstraction,
   no touched protected path without explicit authorization, no unrelated
   files touched, no new dependency without justification, generated files
   left untouched as generated.
4. **Regression-risk analysis.** Read the source around the diff, not just
   changed lines — check callers and callees of anything modified. Consider
   what this change makes harder, riskier, or more coupled later, even if
   it works today.
5. **Test-quality review.** Confirm tests were actually added for new
   deterministic logic, and that they exercise the changed behavior rather
   than merely importing it. Re-run the tests named in the handoff yourself
   when feasible; do not assume reported output is accurate.
6. **Unsupported-claim detection.** Flag any claim in the handoff that
   isn't backed by visible evidence: "tests pass" without output, "fixed X"
   without a diff showing it, a comment or docstring standing in for actual
   behavior.
7. **Structured verdict generation.** Produce a `ReviewPacket`: verdict,
   acceptance-criterion results, findings (each with severity, file/component
   location, and required corrective action), commands actually run, and
   any unverified claims.
8. **Required-action generation.** If the verdict is `CHANGES_REQUIRED`,
   scope a `RepairPacket`: required actions, allowed repair scope,
   prohibited scope, evidence needed for re-review. Note the current repair
   cycle number — `production_protocol.md` caps this at two cycles.

## Verdicts

Use exactly one of:

- **APPROVED** — acceptance criteria verifiably met, no unresolved
  blockers, sufficient evidence supplied.
- **CHANGES_REQUIRED** — at least one unresolved, addressable issue exists.
  Issue a `RepairPacket`.
- **BLOCKED** — the change cannot proceed as scoped (an invariant
  violation, a protected-path conflict, missing required evidence that
  can't be produced) — not simply "needs another repair cycle."

## Prohibited

- Approving from the task description or handoff summary alone, without
  reading the diff.
- Treating another agent's verdict, a comment, or documentation as proof
  that behavior is implemented.
- Implementing the fix yourself in reviewer mode — findings and required
  actions go in the review packet; the producer implements them.
- Merge, push, force-push, or any other destructive/irreversible git
  action.
