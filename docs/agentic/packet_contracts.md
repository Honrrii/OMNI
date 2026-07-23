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

Produced when a review packet's verdict is `CHANGES_REQUIRED`. Scopes the
fix narrowly: a review-cycle number, the required actions, the allowed
repair scope, explicitly prohibited scope, and the evidence needed before
re-review. `production_protocol.md` caps this at **two** repair cycles for
v0.1; a repair packet with `review_cycle` outside `1..2` is invalid.

## Closeout packet

Produced at the end of a run, regardless of outcome. Records the final
verdict, which acceptance criteria were actually completed, final test
evidence, remaining limitations, commit information, and a recommended PR
title and body for a human to review. `human_approval_required` is always
`True` in v0.1 — this packet recommends a PR, it does not create, merge, or
push one.

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
