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

## Phase 1 — contracts, safety, archive foundations

This is architecture, protocol, schema, documentation, and tests only.
Explicitly **not** built in Phase 1, and not to be described as built:

- no autonomous daemon or continuously running agent loop;
- no automatic invocation of Codex;
- no self-prompting loop (Claude does not repeatedly re-prompt itself);
- no automated pushing or merging into trusted branches;
- no orchestrator that drains a queue of experiments on its own.

Every research thread in Phase 1 is a human-directed session that happens
to produce structured records (`omni/frontier/protocol.py`,
`omni/frontier/experiments.py`) in this shape. See
`protocols/SAFETY_RULES.md` for the full boundary list.

## Phase 2A — complementary Claude/Codex research roles

Two skills (`.claude/skills/omni-frontier-architect/SKILL.md` and
`.agents/skills/omni-frontier-experimentalist/SKILL.md`) define the
synthesis-biased and falsification-biased sides of a research exchange
using the Phase 1 contracts. Phase 2A still does not wire an automatic
exchange between the two — a human runs each side.

## Phase 2B — deterministic mock orchestration

`omni/frontier/{config,state,events,mailbox,agents,orchestrator}.py` and
`scripts/omni_frontier_lab.py` add a deterministic **local** orchestrator
("nervous system") that proves OMNI can coordinate a full research shift —
experiment creation, state transitions, message routing, turn-taking,
event logging, bounded debate, evidence recording, conclusion handling,
archiving, and safety stopping — without depending on either real model.

**Every agent in Phase 2B is a deterministic MOCK.**
`omni.frontier.agents.MockClaudeAdapter`/`MockCodexAdapter` are pure
Python functions of their input context; nothing in
`omni/frontier/orchestrator.py` or `run-mock-shift` launches a real Claude
Code or Codex process, calls a model API, opens a network connection,
touches git, or schedules itself. Phase 2B's own infrastructure never
grows into invoking a real model on its own — that is Phase 3 below, a
separate, explicit command.

Run it locally:

```bash
python3 scripts/omni_frontier_lab.py run-mock-shift          # writes under .omni-lab/
python3 scripts/omni_frontier_lab.py run-mock-shift --dry-run  # writes to a discarded temp dir
python3 scripts/omni_frontier_lab.py show-state --thread-id OMNI-FRONTIER-0001
```

Tests: `tests/test_frontier_state.py`, `tests/test_frontier_mailbox.py`,
`tests/test_frontier_events.py`, `tests/test_frontier_agents.py`,
`tests/test_frontier_orchestrator.py`, `tests/test_frontier_lab_cli.py`.

## Phase 3 — one real provider, read-only

`omni/frontier/claude_provider.py` adds `ClaudeCodeAdapter`, a real
`ResearchAgent` implementation behind the same interface
`MockClaudeAdapter` implements — `ShiftOrchestrator` did not change to
accept it. **Codex stays `MockCodexAdapter`.** `run-claude-shift` is the
only command that can invoke a real model; `run-mock-shift` still never
does.

**Read-only, bounded, single-provider only.** Every `claude` invocation
this adapter builds excludes `Edit`/`Write`/`NotebookEdit` and every
mutating git/shell pattern via an explicit `--tools`/`--allowedTools`/
`--disallowedTools` boundary (never `--dangerously-skip-permissions`); it
creates no git branch or worktree, invokes no other AI CLI, and never
pushes or merges. Claude may inspect the repository with its own
read-only tools and produce research content (`claim`, `mechanism`,
`evidence`, `uncertainties`, `requested_action`, `confidence`) via a
`--json-schema`-constrained structured response; it never supplies
thread/sequence/state/routing — those stay orchestrator-owned, filled in
from `ResearchTurnContext` regardless of what the provider returns. A
provider failure (missing executable, timeout, non-zero exit, malformed
JSON, schema-invalid output, canonical `FrontierMessage`/
`ResearchTurnResult` validation failure) is always a bounded
`ResearchTurnResult(ok=False, failure_kind=...)`, never a crash — the
existing `max_consecutive_agent_failures`/`max_experiment_retries` budgets
turn it into `BLOCKED`/`FAILED_INFRASTRUCTURE`, archived like any other
stopped Phase 2B shift.

Run it locally (invokes a real, billed Claude Code process; requires
`claude` installed and authenticated):

```bash
python3 scripts/omni_frontier_lab.py run-claude-shift
python3 scripts/omni_frontier_lab.py run-claude-shift --dry-run
```

Tests: `tests/test_frontier_claude_provider.py` — all fake-runner based; no
test in the normal suite requires a real `claude` install or
authentication (see `docs/agentic/test_matrix.md`).

## Layout

```text
.omni-lab/
├── README.md                          — this file
├── protocols/
│   ├── FRONTIER_RESEARCH_PROTOCOL.md  — message types, thread IDs, evidence discipline
│   ├── EXPERIMENT_LIFECYCLE.md        — lifecycle, scoring, conclusion states, "search the shadows"
│   └── SAFETY_RULES.md                — isolation model, hard rules, Phase 1 boundaries
├── experiments/
│   └── OMNI-FRONTIER-XXXX/            — durable research archive (tracked; see experiments/README.md)
├── conversations/
│   └── README.md                      — raw thread message logs
├── runtime/
│   └── OMNI-FRONTIER-XXXX/            — Phase 2B per-shift scratch state (gitignored; see below)
└── schemas/
    ├── frontier_message.schema.json   — wire schema for FrontierMessage
    └── frontier_experiment.schema.json — wire schema for FrontierExperiment
```

`runtime/<thread-id>/` (`state.json`, `mailbox.jsonl`, `events.jsonl`) is
Phase 2B's serializable orchestration snapshot for one shift — ephemeral,
gitignored, and distinct from the durable `experiments/<thread-id>/`
archive. It exists so a future resume/recovery layer (Phase 3+) has
somewhere to read current state, current turn, and current debate round
from without redesigning the shape then; Phase 2B itself does not
implement crash recovery.

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

## The two research roles

Two complementary skills use this infrastructure — same protocol, same
schemas, different bias:

```text
Claude Code:  .claude/skills/omni-frontier-architect/SKILL.md
Codex:        .agents/skills/omni-frontier-experimentalist/SKILL.md
```

`omni-frontier-architect` generates hypotheses (synthesis, architectural
leverage, cross-system reasoning). `omni-frontier-experimentalist`
falsifies them (adversarial testing, independent reproduction, counter-
hypotheses). Read the relevant one before starting a research session, not
this file alone. As of Phase 2A, only the skill definitions exist — there
is still no automatic Claude<->Codex exchange; see
`protocols/SAFETY_RULES.md`'s Phase 1 boundaries, which still apply.

## Core research loop

Every cycle starts with:

> What valuable thing about OMNI do we currently not know?

then:

> What is the safest and cheapest experiment capable of reducing that
> uncertainty?

A failed hypothesis that generates real evidence is a successful
experiment. A cycle that produces no code but corrects a wrong question is
a good cycle — see `protocols/EXPERIMENT_LIFECYCLE.md`.
