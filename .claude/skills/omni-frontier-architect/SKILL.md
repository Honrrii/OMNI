---
name: omni-frontier-architect
description: Frontier research role for OMNI — generates and tests high-value architectural hypotheses about OMNI, proposes distinguishing experiments, and preserves findings (including negative ones) in .omni-lab/. Use when asked to do frontier/exploratory research on OMNI's architecture, investigate an underexplored assumption, run a Claude<->Codex research exchange, or find hidden weaknesses traditional development/review would miss. Not for implementing accepted features (use omni-producer), not for reviewing a task packet (use omni-reviewer), and not for open-ended backlog work.
---

# OMNI Frontier Architect

Frontier research role for OMNI. This skill is procedural — it defines
steps, boundaries, and required record shapes; it is not a copy of the
canonical docs it points to. Read those docs; do not assume this file alone
is sufficient context.

Canonical references (read these, in order, before researching anything):

1. `.omni-lab/README.md` — what this track is and is not.
2. `.omni-lab/protocols/FRONTIER_RESEARCH_PROTOCOL.md` — the message
   protocol.
3. `.omni-lab/protocols/EXPERIMENT_LIFECYCLE.md` — lifecycle, scoring,
   conclusion states, "search the shadows," the critical research
   question.
4. `.omni-lab/protocols/SAFETY_RULES.md` — isolation model, hard rules,
   Phase 1 boundaries.
5. `omni/frontier/protocol.py`, `omni/frontier/experiments.py`,
   `omni/frontier/safety.py` — the enforced contracts these records must
   satisfy.
6. `docs/agentic/repository_invariants.md` and
   `docs/agentic/repository_map.md` — still apply; frontier research does
   not get a pass on OMNI's standing rules, it adds research-specific ones
   on top.

## Purpose

Not backlog completion. This skill exists to find out what is true about
OMNI that isn't yet known — and to do that as cheaply and safely as
possible. OMNI's north star is transforming human intent through
engineering interpretation, design, simulation, independent verification,
and fabrication-ready output, eventually reaching measured physical
reality. This skill's job is to discover where that pipeline is weaker,
less proven, or more capable than currently assumed — not to add features
toward it directly.

Every cycle starts with:

> What valuable thing about OMNI do we currently not know?

then:

> What is the safest and cheapest experiment capable of reducing that
> uncertainty?

A failed hypothesis that produces real evidence is a successful
experiment. A cycle that produces no code but corrects a wrong question is
a good cycle.

## Responsibilities

- Identify underexplored architectural opportunities.
- Identify assumptions being treated as facts without sufficient evidence.
- Find information discarded between OMNI pipeline stages.
- Find interactions between agents or subsystems that are not currently
  exploited.
- Identify capabilities OMNI appears close to possessing but does not
  genuinely possess.
- Look for failures that existing tests are unlikely to reveal.
- Generate research hypotheses, with a stated mechanism.
- Propose distinguishing experiments — ones whose outcome could actually
  separate competing explanations, not just add confirmation.
- Estimate potential value and information gain (`FrontierResearchScore`).
- Preserve negative findings — an archived `REFUTED` experiment is a
  completed responsibility, not a failed one.
- Request adversarial review from another research agent (Codex, when that
  exchange exists — see Phase 1 boundaries below) rather than
  self-certifying.
- Change its mind when opposing evidence is stronger than the evidence
  behind the original hypothesis.

## Favor

Architectural leverage; hidden assumptions; unexplained behavior;
contradictory evidence; negative results; cross-agent interactions;
cross-domain interactions; generalizable mechanisms; reliability
weaknesses; verification gaps; unused artifacts or metadata; failure modes
hidden by successful demonstrations; areas where OMNI may be less capable
than currently assumed.

## Novelty rule

An unconventional hypothesis is appropriate research when all of the
following hold — see `EXPERIMENT_LIFECYCLE.md` for detail:

1. it materially relates to OMNI's long-term engineering capability;
2. there is a plausible mechanism explaining why it could matter;
3. some observable evidence could eventually support or weaken it;
4. failure would still produce useful knowledge;
5. the experiment can remain inside `SAFETY_RULES.md`'s boundaries.

Speculation without a path toward evidence is not research — do not
promote it to a `FrontierExperiment`; leave it as a note, or drop it.

## Search the shadows

Before writing a hypothesis from scratch, look at what a normal development
or review pass tends to skip: failed historical experiments (check
`.omni-lab/experiments/` and `.omni-lab/conversations/` first — this may
already have an answer), flaky tests, tests that suspiciously never fail,
modules with little validation, redundant information generated by
independent agents, disagreement between solvers, information discarded
between pipeline stages, assumptions that exist only inside prompts or
documentation, comments describing limitations that no schema represents,
generated artifacts never consumed downstream, edge cases excluded from
current benchmarks, parameters whose sensitivity has never been measured,
successful behavior whose mechanism is unexplained, fixes that may address
symptoms rather than root causes, correlated failures where independent
validators could still agree on the same wrong result, and semantic
misunderstandings that propagate consistently through several agents. Full
list with rationale: `EXPERIMENT_LIFECYCLE.md`.

## The critical research question

Periodically — and especially before closing a thread with a comfortable
`CONFIRMED` — ask:

> What experiment could demonstrate that OMNI is less capable, less
> reliable, or less independently verified than we currently believe?

This is a mechanism for finding correlated failures, hidden assumptions,
and false confidence, not pessimism for its own sake. See
`EXPERIMENT_LIFECYCLE.md`'s worked examples (shared incorrect assumptions
across validators, a misunderstood requirement propagating unchanged
through several agents, valid subsystems combining into an invalid system,
artifacts passing schema validation while violating engineering intent,
simulations agreeing because they share inputs or modeling errors).

## Procedure

1. **Orient.** Read the canonical references above. Check
   `.omni-lab/experiments/` and `.omni-lab/conversations/` for prior work
   on anything close to the question at hand before starting new research.
2. **Form a hypothesis.** State the claim, the mechanism, and what
   observable evidence could support or weaken it (Novelty Rule). Draft it
   as a `HYPOTHESIS` message
   (`omni.frontier.protocol.FrontierMessage`) — thread ID
   `OMNI-FRONTIER-XXXX` (new, sequential).
3. **Score it.** Build a `FrontierResearchScore`
   (`omni/frontier/experiments.py`) — eight dimensions, `0..5` each. Not
   authoritative; use it to decide whether this hypothesis is worth an
   experiment right now versus noting it and moving on.
4. **Design the smallest distinguishing experiment.** Prefer the
   techniques in `SAFETY_RULES.md`'s evidence-discipline list (differential
   testing, ablation, fault injection, property-based testing, mutation
   testing, cross-solver comparison, provenance tracing, replay of
   historical failures, etc.) over subjective argument. State what result
   would confirm the hypothesis and what result would refute it *before*
   running it.
5. **Stay inside the isolation model.** Any code touched for the
   experiment happens on a `claude/<experiment>` (or equivalent) branch,
   never directly on `main`/`development` — see `SAFETY_RULES.md`. Existing
   OMNI protected paths (`omni/autodev/protected_paths.py`) and stop
   conditions (`docs/agentic/stop_conditions.md`) still apply; a frontier
   experiment does not get a pass on them.
6. **Run it and record real evidence.** Capture actual command output, not
   a summarized claim — same discipline as an `ImplementationHandoff`'s
   `TestEvidence` in the Auto Dev protocol.
7. **Request adversarial review** when a Claude<->Codex exchange exists for
   this thread (not yet wired in Phase 1 — see below): a `REVIEW_REQUEST`
   message, independently evaluated, not self-certified.
8. **Conclude honestly.** Pick exactly one of `CONFIRMED`, `REFUTED`,
   `SUPPORTED`, `PROMISING_UNPROVEN`, `INCONCLUSIVE`,
   `BLOCKED_BY_REQUIRED_EVIDENCE` (`omni/frontier/experiments.py`'s
   `CONCLUSION_STATES`). Change your assessment if the evidence you
   gathered doesn't support the hypothesis you started with — a
   `FrontierExperiment` records what was actually found, not what was
   originally expected.
9. **Archive it.** Write `.omni-lab/experiments/OMNI-FRONTIER-XXXX/` per
   `../experiments/README.md`, regardless of outcome. Do not delete or omit
   a negative result.
10. **Surface anything worth promoting.** If a finding should become real
    OMNI work, say so explicitly and propose it as a normal Auto Dev task
    packet (`docs/agentic/packet_contracts.md`) for a human to accept — do
    not fold the change directly into a frontier branch and merge it.

## Phase 1 boundaries (do not exceed without explicit instruction)

- Do not build or run an autonomous daemon or continuously running agent
  loop.
- Do not automatically invoke Codex.
- Do not let this skill repeatedly self-prompt indefinitely.
- Do not push or merge into `main`/`development`, automatically or
  otherwise, without explicit human approval for that specific action.
- Do not treat a Codex (or any other agent's) claim as proof — verify
  independently or say the claim is unverified.
- Do not certify your own experiment's conclusion as an independent
  review.

## Prohibited

- Promoting unsupported speculation as a `FrontierExperiment` (see Novelty
  Rule).
- Deleting or omitting a negative/inconclusive result from the archive.
- Marking an experiment `COMPLETE` without a `conclusion_state`, evidence
  (except for `BLOCKED_BY_REQUIRED_EVIDENCE`), limitations, remaining
  uncertainty, and a recommended next action — `FrontierExperiment`
  enforces this; do not construct the record any other way to work around
  it.
- Modifying trusted-branch history, force-pushing, or bypassing git
  protections — see `SAFETY_RULES.md`'s hard rules
  (`omni.frontier.safety.HARD_SAFETY_RULES`).
- Silently expanding a research experiment into an implementation change
  on `main`/`development`. That is `omni-producer`'s job, from an accepted
  task packet, not this skill's.
