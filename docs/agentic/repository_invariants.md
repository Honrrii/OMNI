# OMNI Repository Invariants

Enforceable engineering rules for anyone — human or agent — working on OMNI
under the production protocol (`production_protocol.md`). These are rules
that can actually change a decision, not general advice. If a rule here
can't change what an agent does in a concrete situation, it doesn't belong
here.

## Process invariants

- **Inspect before abstracting.** Read the existing architecture for the
  area you're touching before adding a new abstraction, module, or pattern.
  OMNI already has several near-identical shapes (gate reports, finding
  projections, provenance records) — check whether one already fits before
  inventing another.
- **Unrelated dirty files are not yours to touch.** If the worktree has
  uncommitted changes you didn't make and weren't asked to address, leave
  them alone. Do not reset, discard, or silently fold them into your commit.
- **Generated files are not source files.** Anything under
  `outputs/omni_missions/`, `__pycache__/`, `*.pyc`, or another generated
  path must not be hand-edited or treated as a review target. Fix the
  generator, not the output.
- **Safety and non-weapon restrictions stay intact.** No component in this
  repository performs or certifies physical safety. The Pluto safety gate
  and reliability gates are deterministic, advisory aids for a human
  engineer — never a substitute for that human's judgment, and never to be
  described as a hard safety certification. Physical actions gated behind
  human approval (see `docs/OMNI_FORGE_ROADMAP.md`) stay gated behind human
  approval.
- **Deterministic enforcement belongs in Python, tests, schemas, or hooks.**
  If a rule must always hold, encode it where it cannot be talked past: a
  function, a test assertion, a schema constraint, a git hook. Do not rely
  on an agent remembering a rule from a prompt when it could instead fail to
  compile or fail a test.
- **Model judgment belongs in skills and review procedures.** Things that
  genuinely require reasoning about tradeoffs, architecture fit, or intent
  belong in skill instructions and review checklists — not hard-coded as
  brittle pattern-matching in application code.
- **Implementation agents cannot approve their own work.** The agent that
  wrote a change is not the agent that reviews it. A single agent producing
  and then self-approving a review verdict is not a review.
- **A test timeout is inconclusive, not a result.** A command that times out
  proves nothing about pass/fail. Report it as a timeout — duration, last
  visible progress, whether it reproduces — never as a pass or an ordinary
  failure.
- **Partial test output is not full-suite success.** Only claim what was
  actually observed. If a subset ran, report that subset; do not extrapolate
  to "the suite passes."
- **Architecture changes require explicit justification.** A change to a
  module boundary, a data shape used by more than one caller, or a core
  workflow needs a stated reason, not just a diff.
- **New dependencies require justification and tests.** Do not add a
  library to solve a problem the standard library or an existing in-repo
  utility already solves. Auto Dev's own modules are deliberately
  standard-library-only.
- **Another agent's verdict is not evidence.** A prior review, approval, or
  claim of correctness by another AI is not proof by itself. Cite the
  underlying fact (a test result, a line of code, a command's output) or
  re-verify it yourself.
- **Do not approve, or claim done, without looking.** Do not approve a
  change from its description alone without reading the diff. Do not assume
  tests passed without seeing their output. Do not treat a comment,
  docstring, or Markdown report as proof that the described behavior exists
  in code.

## Security invariants

- Never request, print, or reproduce contents of `.env` or `.env.example`,
  API keys, access tokens, SSH keys/credentials, user data, or log files
  that may contain secrets (`logs/backend.log`, `logs/frontend.log`).
- If a task appears to require exposing a secret to complete, that is a stop
  condition (`stop_conditions.md`), not a reason to proceed.

## Domain invariants (grounding for the above)

- OMNI is a **local-first modular monolith**: one FastAPI backend, one React
  frontend, one in-process supervisor agent loop. No message queue, no
  service mesh, no distributed workers. Do not introduce one of those merely
  for architectural novelty.
- Provenance has multiple distinct shapes across the codebase (reliability's
  live-built record, the mission graph's `ProvenanceRef`, the standalone
  harness's `provenance_record.json`, and the FastAPI export path's
  stage-based dossier). Treat any change that assumes two of these are
  interchangeable as a cross-domain risk to verify, not an assumption to
  make.
- The OMNI Sandbox is a standalone, tested harness that is **not** wired
  into the mission runtime or export pipeline, and is explicitly documented
  as not a security sandbox (`docs/contracts/sandbox.md`). Do not describe
  it as providing execution isolation for real tool calls until that
  hardening work is done and documented as such.
- Auto Dev (`omni/autodev/`) is currently non-autonomous by design: it
  matches a single path against protected-path policy, checks a local issue
  file, and scaffolds run directories. It does not scan a git diff, fetch
  GitHub issues, call a model, or call the GitHub API. Do not describe any
  of those as implemented until they exist as code with tests.
