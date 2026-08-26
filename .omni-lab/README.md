# OMNI Frontier Research Lab

`.omni-lab/` is the home of OMNI's **Frontier Research** track: a structured
way for Claude Code and (eventually) Codex to propose hypotheses about
OMNI's architecture, challenge each other, run small isolated experiments,
and record what was actually learned — including when the answer is "we
should not build this" or "we were asking the wrong question."

This is **separate from** `docs/agentic/`'s Auto Dev production protocol.
Auto Dev is the bounded implement → review → merge path for accepted work.
Frontier Research is exploratory and disposable: it exists to generate
evidence and reduce uncertainty about what OMNI can become, not to ship
features. A frontier finding that turns out to matter gets *proposed* into
Auto Dev as a normal task packet — it does not merge itself.

## Phase 1 — what exists right now

This is architecture, protocol, schema, documentation, and tests only.
Explicitly **not** built yet, and not to be described as built:

- no autonomous daemon or continuously running agent loop;
- no automatic invocation of Codex;
- no self-prompting loop (Claude does not repeatedly re-prompt itself);
- no automated pushing or merging into trusted branches;
- no orchestrator that drains a queue of experiments on its own.

Every research thread today is a human-directed session that happens to
produce structured records (`omni/frontier/protocol.py`,
`omni/frontier/experiments.py`) in this shape. See
`protocols/SAFETY_RULES.md` for the full boundary list.

## Layout

```text
.omni-lab/
├── README.md                          — this file
├── protocols/
│   ├── FRONTIER_RESEARCH_PROTOCOL.md  — message types, thread IDs, evidence discipline
│   ├── EXPERIMENT_LIFECYCLE.md        — lifecycle, scoring, conclusion states, "search the shadows"
│   └── SAFETY_RULES.md                — isolation model, hard rules, Phase 1 boundaries
├── experiments/
│   └── README.md                      — per-experiment archive convention
├── conversations/
│   └── README.md                      — raw thread message logs
└── schemas/
    ├── frontier_message.schema.json   — wire schema for FrontierMessage
    └── frontier_experiment.schema.json — wire schema for FrontierExperiment
```

## Where enforcement actually lives

The schemas here are the provider-neutral spec — readable by Codex or any
other agent without importing OMNI's Python package. The validated,
enforced version of the same shapes is `omni/frontier/protocol.py`
(`FrontierMessage`) and `omni/frontier/experiments.py`
(`FrontierExperiment`, `FrontierResearchScore`) — plain dataclasses that
raise `ValueError` on malformed data, in the same style as
`omni/autodev/packets.py`. `omni/frontier/safety.py` holds the deterministic,
testable half of the isolation model (branch-name classification); the rest
of the isolation model is process, described in `protocols/SAFETY_RULES.md`.

Tests: `tests/test_frontier_protocol.py`, `tests/test_frontier_experiments.py`,
`tests/test_frontier_safety.py`, `tests/test_frontier_schemas.py` (the last
one checks the Python contracts and the JSON schemas haven't drifted apart).

## The Claude Code skill

`.claude/skills/omni-frontier-architect/SKILL.md` defines the research role
that uses this infrastructure: what it looks for, how it scores a
hypothesis, and what it must never do. Read it before starting a research
session, not this file alone.

## Core research loop

Every cycle starts with:

> What valuable thing about OMNI do we currently not know?

then:

> What is the safest and cheapest experiment capable of reducing that
> uncertainty?

A failed hypothesis that generates real evidence is a successful
experiment. A cycle that produces no code but corrects a wrong question is
a good cycle — see `protocols/EXPERIMENT_LIFECYCLE.md`.
