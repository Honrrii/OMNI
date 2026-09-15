# Frontier Experiment Archive

One directory per research thread that reached at least an
`EXPERIMENT_PROPOSAL`, named after its thread ID:

```text
.omni-lab/experiments/OMNI-FRONTIER-XXXX/
├── hypothesis.md        — the original hypothesis, mechanism, and why it matters
├── messages.jsonl        — the thread's messages (FrontierMessage, one JSON object per line)
├── experiment_plan.md    — the safest/cheapest experiment chosen, and why
├── evidence/              — files, command output, generated artifacts gathered
├── results.json           — a FrontierExperiment record (omni/frontier/experiments.py)
└── conclusion.md          — human-readable writeup of the conclusion_state and what's next
```

`results.json` is the authoritative structured record — it should
deserialize with `omni.frontier.experiments.frontier_experiment_from_dict`
and pass that dataclass's validation. `conclusion.md` is the same
conclusion in prose, for a human or another agent reading the archive
without wanting to parse JSON first.

## Negative results are archive, not deletion

An experiment that concluded `REFUTED`, `INCONCLUSIVE`, or
`BLOCKED_BY_REQUIRED_EVIDENCE` is not deleted or excluded. A rejected
hypothesis is part of OMNI's research memory precisely so a later session
doesn't re-propose and re-run the same experiment without knowing it was
already tried — check this directory (or `../conversations/`, for threads
that never reached a formal experiment) before starting new research on a
topic that might already have a prior answer here.

## Relationship to `../conversations/`

`../conversations/` holds a thread's raw message exchange before (or
without) it ever escalating to a full `FrontierExperiment` archive here — a
`HYPOTHESIS`/`CHALLENGE` back-and-forth that never produced an
`EXPERIMENT_PROPOSAL` still lives there, not here. Once a thread proposes
and runs an actual experiment, it gets a directory in this location; the
thread's `messages.jsonl` can be the same file continued from
`../conversations/`, not a second independent log.
