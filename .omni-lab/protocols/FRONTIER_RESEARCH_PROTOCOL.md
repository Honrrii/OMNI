# Frontier Research Protocol (v0.1)

The structured message protocol Claude Code and (eventually) Codex use to
exchange hypotheses, evidence, and challenges about OMNI's architecture.
This document defines message semantics. The enforced field-level contract
lives in `omni/frontier/protocol.py` (`FrontierMessage`); the
provider-neutral wire schema is `../schemas/frontier_message.schema.json`.
If this document and the code disagree, the code is authoritative for what
is actually validated today.

A message is a structured claim another agent can independently check
against the repository — not a narrative summary the reader has to trust.
See `docs/agentic/repository_invariants.md`'s "another agent's verdict is
not evidence": the `evidence` field should name something checkable (a
file, a command, a test), not restate the claim in other words.

## Thread IDs

Every research thread gets an ID of the form:

```text
OMNI-FRONTIER-0001
```

Four digits is the v0.1 floor, not a ceiling — `OMNI-FRONTIER-12345` is
valid once thread count grows past 9999. Enforced by
`omni.frontier.protocol.validate_thread_id`, shared with
`omni.frontier.experiments.FrontierExperiment.experiment_id` — one thread
is one experiment's identifier space in v0.1; there is no separate ID
scheme for experiments.

## Message shape

```json
{
  "thread_id": "OMNI-FRONTIER-0001",
  "sequence": 1,
  "from_agent": "claude",
  "to_agent": "codex",
  "message_type": "HYPOTHESIS",
  "claim": "The mission graph's ProvenanceRef and the export pipeline's stage-based dossier silently disagree on schema version after an export re-run.",
  "mechanism": "builder.py reads outputs/omni_missions/<slug>/mission_graph.json assuming the field names export_manager.py currently writes, but the two are not generated from one shared schema (see repository_map.md's export/graph-builder note).",
  "evidence": [
    "backend/app/mission_graph/builder.py",
    "backend/app/export/export_manager.py"
  ],
  "uncertainties": [
    "Whether this has ever actually produced a wrong graph in a real export, or only a theoretical mismatch."
  ],
  "requested_action": "Re-run a real export, then re-read it with builder.py, and diff the two field sets.",
  "confidence": 0.4,
  "created_at": "2026-08-26T00:00:00Z",
  "protocol_version": "0.1"
}
```

`from_agent`/`to_agent` are plain strings (`"claude"`, `"codex"`,
`"human"`, or a broadcast marker like `"all"`) rather than a closed enum —
v0.1 does not want to hard-code the set of participants into the schema
itself.

## Message types

| Type | Meaning |
| --- | --- |
| `HYPOTHESIS` | A claim about OMNI worth testing, with a stated mechanism. |
| `COUNTER_HYPOTHESIS` | An alternative explanation for the same observation. |
| `REVIEW_REQUEST` | Ask another agent to independently evaluate a claim or plan. |
| `REVIEW_FINDING` | The result of that independent evaluation. |
| `EVIDENCE` | A repository-checkable fact supporting a claim. |
| `COUNTEREVIDENCE` | A repository-checkable fact weakening a claim. |
| `EXPERIMENT_PROPOSAL` | A concrete, boundable experiment plan (see `EXPERIMENT_LIFECYCLE.md`). |
| `EXPERIMENT_RESULT` | What an experiment actually produced. |
| `CHALLENGE` | A direct objection to a claim, plan, or result. |
| `RESPONSE` | A reply to a `CHALLENGE`, `REVIEW_FINDING`, or `COUNTER_HYPOTHESIS`. |
| `CONCLUSION` | A thread's terminal message — see `EXPERIMENT_LIFECYCLE.md`'s conclusion states. |
| `ESCALATE_TO_HUMAN` | The thread cannot proceed without a human decision (mirrors `docs/agentic/stop_conditions.md`'s spirit — stop and report, don't improvise past it). |

## Evidence discipline

Prefer distinguishing experiments over subjective argument, and prefer
repository evidence — source, tests, generated artifacts, runtime results,
logs, schemas, benchmark or solver comparisons — over narrative agreement.
An agent should not concur with another agent's claim merely because the
explanation sounds plausible; it should look for repository evidence that
would exist if the claim were true, and evidence that would exist if it
were false. See `SAFETY_RULES.md`'s evidence-discipline section for the
specific technique list (differential testing, ablation, fault injection,
etc.) and `EXPERIMENT_LIFECYCLE.md`'s "what could show OMNI is less capable
than we think" question, which exists specifically to counter correlated
false agreement between validators.

## What this version does not do

Defining and validating this message shape does not, by itself, move a
message anywhere. Nothing in `omni/frontier/protocol.py` sends a message,
opens a connection, calls a model API, or launches Claude or Codex.
Messages in v0.1 are written by a human-directed session into
`.omni-lab/conversations/` or a specific experiment's `messages.jsonl` —
see `../experiments/README.md` and `../conversations/README.md`.
