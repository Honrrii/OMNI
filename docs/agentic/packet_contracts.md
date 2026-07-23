# OMNI Production Packet Contracts

This document explains what each production packet means and when it's
produced. It does not restate field lists exhaustively or duplicate
enforcement logic — the Python dataclasses in `omni/autodev/packets.py`
enforce structure (required fields, allowed verdict values, repair-cycle
limits, timeout representation); this document explains semantics and
lifecycle. If the two disagree, the code is authoritative for what is
actually enforced today.

All packets carry a `packet_version` field (currently `"0.1"`). A future
version bump is a deliberate, reviewed change to `omni/autodev/packets.py`,
not something a packet's contents can silently drift into.

**One shared repository-relative path contract.** Both this module and
`omni/autodev/protected_paths.py`'s protected-path policy use the same two
primitives (defined in `protected_paths.py`, imported by `packets.py`):
`normalize_repo_relative_path` (strict — fails closed with `ValueError` on
empty, malformed, absolute, drive-qualified, UNC, or repository-escaping
input; used for *concrete* paths) and `spec_matches` (literal, prefix, or
glob matching against an already-normalized candidate; used for *scope
specifications*). `match_protected_path` fails closed the same way a repair
packet's path validation does — an invalid path is a `ValueError`, never an
ordinary unprotected `None`.

## Run manifest

Produced once, at the start of a production run. Records the environment
the run started in: a run identifier, creation timestamp, repository root,
starting commit, branch, a summary of any pre-existing dirty state, the
requested operation, and the packet version. Exists so that later packets
in the same run (and any reviewer looking back at it) can answer "what was
true when this started" without re-deriving it from git history.

## Task packet

Produced after issue-readiness evaluation, before implementation starts.
Defines the bounded scope contract for the producer: goal, in-scope paths,
out-of-scope paths, the invariants that apply, acceptance criteria,
required evidence, risk notes, and a readiness status. A task packet with a
`NOT_READY` readiness status does not proceed to implementation. The
producer is bound to this scope — see `repository_invariants.md`'s "no
silent scope expansion."

**`in_scope_paths` / `out_of_scope_paths` are scope *specifications*, not
concrete paths**: each entry may be a literal repository-relative path, a
repository-relative directory prefix (`omni/autodev` covers everything
under it), or a glob containing `* ? [ ]` (`omni/autodev/**`). All three
forms are matched the same way protected-path policy patterns are matched
(`omni.autodev.protected_paths.spec_matches`) — one shared
repository-relative matching contract, not two.

**Acceptance-criterion identity for v0.1** is the criterion string itself,
validated and compared after trimming whitespace: empty or whitespace-only
criteria are rejected, and two criteria that are identical after trimming
are rejected as duplicates. There is no separate criterion-ID model in this
version — a validated, trimmed string is the identity.

## Implementation handoff

Produced by the producer when implementation is done. Records what actually
happened: files changed, an acceptance-criterion-by-criterion result
mapping, the commands run, test results (as `TestEvidence` entries),
deviations from the task packet, known limitations, and areas the reviewer
should pay attention to. This is the producer's evidence — it must be
checkable against the real diff and real command output, not a summary a
reviewer has to take on faith.

## Test evidence

A single command's execution record: the command, working directory, exit
code, start/completion information where available, an output summary, and
an outcome of `passed`, `failed`, or `timeout`. A `timeout` outcome never
carries an exit code — a hung or truncated run is not a pass or an ordinary
failure, and the contract enforces that distinction rather than relying on
whoever writes the packet to remember it (see `repository_invariants.md`).

## Review packet

Produced by the independent reviewer. Carries a verdict
(`APPROVED` / `CHANGES_REQUIRED` / `BLOCKED`), acceptance-criterion results,
findings (each with a severity, a file/component location, and a required
corrective action), the commands the reviewer actually ran, and any
unverified claims the reviewer could not confirm. A reviewer must start
read-only and produce this packet from independent inspection of the
repository and diff — not from trusting the implementation handoff at face
value.

## Repair packet

Produced when a review packet's verdict is `CHANGES_REQUIRED`. Carries the
`task_id` of the task it repairs, a review-cycle number, the required
actions, the allowed repair scope, explicitly prohibited scope, and the
evidence needed before re-review. `production_protocol.md` caps this at
**two** repair cycles for v0.1; a repair packet with `review_cycle` outside
`1..2` is invalid.

**A repair packet is bound to its task.**
`validate_repair_within_task_scope(repair, task)` checks `repair.task_id`
against `task.task_id` *before* checking anything about paths — a repair
packet must never validate against an unrelated task merely because its
paths happen to fit that other task's scope.

**`allowed_repair_scope` must contain concrete repository-relative paths
only** — no glob metacharacters, unlike `TaskPacket.in_scope_paths` /
`out_of_scope_paths`. Each entry is normalized through
`omni.autodev.protected_paths.normalize_repo_relative_path`, which fails
closed (raises, does not silently pass through) on empty, malformed,
absolute, drive-qualified, UNC, or repository-escaping input. This
deliberately avoids attempting general pattern-to-pattern set containment:
a repair packet names what it will concretely touch, not another pattern to
reconcile against the task's patterns.

**Out-of-scope rules take precedence.** For each `allowed_repair_scope`
path: if it matches any `out_of_scope_paths` specification, it is rejected
regardless of `in_scope_paths`. If `in_scope_paths` is non-empty, the path
must additionally match at least one of its specifications. If
`in_scope_paths` is empty, the task did not enumerate a boundary, and scope
is intentionally unconstrained (subject still to the out-of-scope check).

## Closeout packet

Produced at the end of a run, regardless of outcome. Records the final
verdict, which acceptance criteria were actually completed, final test
evidence, remaining limitations, commit information, and a recommended PR
title and body for a human to review.

`human_approval_required` must be exactly `True` (the bool, not a truthy
value like `1` or `"yes"`) in v0.1 — this packet recommends a PR, it does
not create, merge, or push one.

**An `APPROVED` closeout requires meaningful completion evidence**: a
non-empty branch and commit, at least one completed acceptance criterion
(each a non-empty string), at least one final test evidence entry, no
`timeout` (or otherwise inconclusive) outcome among that evidence, and a
non-empty recommended PR title and body. A `CHANGES_REQUIRED` or `BLOCKED`
closeout only needs to be structurally valid — it is not required to look
like finished, approved work.

## Lifecycle summary

```text
RunManifest (once, at start)
  → TaskPacket (once, after readiness)
    → ImplementationHandoff (each producer pass; carries TestEvidence)
      → ReviewPacket (each reviewer pass)
        → RepairPacket (only if CHANGES_REQUIRED; max 2 cycles)
      → ReviewPacket (re-review, if a repair packet was issued)
  → CloseoutPacket (once, at the end)
```

## What this version does not do

Producing and validating these packets does not, by itself, execute a
workflow. Nothing in `omni/autodev/packets.py` invokes a model API,
launches Claude or Codex, commits automatically, opens a PR, or merges. The
packets are the structured record a human-directed session produces; wiring
them into an automated orchestrator is explicitly out of scope for this
slice.
