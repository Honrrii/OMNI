# Frontier Research Safety Rules (v0.1)

The isolation model and hard rules governing any Frontier Research session.
These apply on top of, not instead of, `docs/agentic/repository_invariants.md`
and `docs/agentic/stop_conditions.md` — this document adds research-specific
isolation; it does not relax anything already true of this repository.

## Phase 1 boundaries

This phase is architecture, protocol, schema, documentation, skill
construction, and tests for the framework itself. Explicitly out of scope,
and not to be described as implemented until it exists as reviewed code:

- an autonomous daemon or continuously running agent loop;
- automatic invocation of Codex;
- a self-prompting loop where Claude repeatedly re-prompts itself
  indefinitely;
- automated pushing or merging into trusted branches;
- an orchestrator that selects and drains a queue of experiments on its
  own.

A later phase may build the complementary Codex-side skill
(`omni-frontier-experimentalist`) and wire actual agent-to-agent exchange.
Building that is a deliberate, separately reviewed decision — not something
this phase's infrastructure should grow into on its own.

## Isolation model

Trusted branches are read-only from an autonomous research session:

```text
main
development
```

Disposable research work happens on prefixed branches:

```text
autonomous-lab/<experiment>
claude/<experiment>
codex/<experiment>
integration/<experiment>
```

`omni.frontier.safety.is_protected_branch` / `is_research_branch` classify
branch-name strings against this policy (see that module's docstrings for
exact rules — a bare prefix with no experiment slug, e.g. `"claude/"` alone,
does not count as a valid research branch).

Preferred isolation mechanism, in order of preference:

1. a separate Git worktree per agent, so a research session's working tree
   never shares state with a producer/reviewer session's working tree;
2. a separate agent branch per experiment (`claude/<experiment>`,
   `codex/<experiment>`);
3. an `integration/<experiment>` branch, controlled by orchestration logic
   (not yet built — see "Phase 1 boundaries"), as the only place a
   claude-branch and codex-branch result are combined;
4. trusted branches (`main`, `development`) treated as read-only from any
   autonomous research session — a human merges into them, a research
   session does not.

The research environment must be disposable: a failed experiment's branch
and worktree must be removable without damaging OMNI, and an archived
experiment (`../experiments/OMNI-FRONTIER-XXXX/`) preserves what was
learned independently of whether the branch survives.

## Hard rules

Canonical list: `omni.frontier.safety.HARD_SAFETY_RULES`.

- No force pushes.
- No deleting protected branches.
- No rewriting protected history.
- No weakening tests merely to obtain a green result.
- No silently modifying validation thresholds.
- No modifying `.git` configuration to bypass protections.
- No accessing secrets or credentials.
- No uncontrolled deployment.
- No automatically merging research results into trusted OMNI development.
- No treating one agent's claim as proof.
- No agent certifying its own implementation.
- Human approval required before promotion into normal OMNI development.

These mirror `docs/agentic/repository_invariants.md`'s existing rules
("implementation agents cannot approve their own work," "another agent's
verdict is not evidence") applied specifically to a research exchange
between two model-driven agents, where the temptation to accept a plausible
peer explanation without independent verification is exactly the failure
mode this document exists to block.

## Evidence discipline

For any claim that matters, prefer repository evidence over subjective
argument: source code, tests, generated artifacts, runtime results,
benchmark results, solver comparisons, logs, schemas, controlled
experiments, reproducible counterexamples. Where possible, require a
distinguishing experiment rather than accepting a plausible-sounding
explanation. Techniques to prefer, matched to what's being investigated:

- differential testing — run two implementations/paths on the same input,
  compare outputs;
- metamorphic testing — check a relation that should hold across related
  inputs, not just one input/output pair;
- adversarial inputs — inputs specifically constructed to break an
  assumption;
- counterexample construction — find one concrete case that falsifies a
  claim;
- controlled ablation — remove one factor, observe what changes;
- fault injection — deliberately break a dependency and observe the
  failure mode;
- property-based testing — check an invariant across generated inputs
  rather than one hand-picked case;
- sensitivity analysis — vary a parameter and measure how much the output
  actually moves;
- mutation testing — check whether tests would actually catch a
  deliberately introduced bug;
- cross-solver comparison — compare independently produced solutions to
  the same problem;
- counterfactual execution — ask what would have happened under a
  different input or code path;
- provenance tracing — follow a value back to where it was actually
  produced, rather than assuming it means what its field name implies;
- invariant discovery — find a property that appears to always hold, and
  try to break it;
- replay of historical failures — re-run a case that failed before and
  check whether it still does, and why;
- independent solution comparison — have two agents solve the same problem
  without seeing each other's approach, then compare.

## Never

- Never let one agent's claim of correctness substitute for independent
  verification — a plausible explanation from another model is not
  evidence, per `docs/agentic/repository_invariants.md`.
- Never let an agent certify its own implementation as reviewed or
  approved.
- Never treat a `CONFIRMED` conclusion as closing the question if a
  distinguishing experiment was never actually run.
- Never promote a frontier finding directly into `main`/`development` —
  promotion into normal OMNI development is a human decision, made through
  the existing Auto Dev production protocol (`docs/agentic/`), not an
  automatic merge from a research branch.
