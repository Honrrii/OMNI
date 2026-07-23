# OMNI Repository Map

Provider-neutral orientation for an implementation or review agent. This is
a map of stable, high-level areas — not a file-by-file description. Read the
actual source, tests, and diff of anything you touch; this document only
tells you where to look.

## Backend

- Entry point: `backend/app/main.py` (FastAPI app; mounts mission, reliability,
  ML, and Visual Bay routers).
- Mission runtime core: `backend/app/omni_core/` (`mission_state.py`,
  `mission_intent.py`, `llm_router.py`, `safety_gate.py`).
- Domain subsystems, each its own package under `backend/app/`:
  `mission_graph/`, `reliability/` (+ `reliability/calculators/`), `export/`,
  `visual_bay/`, `concept_dossier/`, `engineering/`, `aeroforge/`, `cad/`,
  `electronics/`, `ml/`, `ros/`, `sandbox/`, `validators/`, `generators/`.
- The FastAPI mission runtime has no database dependency. Mission results
  are written to the local filesystem (`outputs/omni_missions/`).

## Frontend

- `frontend/` — React/Vite app, independent build (`npm run build`).
- `frontend/src/api/` — shared API client helpers. Some components call
  `fetch` directly, so check both `frontend/src/api/` and
  `frontend/src/components/*.jsx` when tracing API usage.
- `frontend/src/components/` — one panel per backend export surface (mission
  graph review, mission intent, reliability, candidate evaluation, Visual
  Bay, Concept Dossier, AeroForge, Forge, simulation, operator brief, etc.).
  There is no shared schema-generation step between backend models and the
  frontend — verify field names by hand when a change touches both sides.

## Mission pipeline

- Orchestration: `agents/supervisor.py` (`SupervisorAgent`) runs the
  specialist agents against a shared `MissionState`, then artifact synthesis,
  final report, validation, and memory write.
- Specialist agent wrappers: `agents/*.py`, each calling
  `backend/app/omni_core/llm_router.py`.
- Deterministic mission intent extraction (no LLM, no network):
  `backend/app/omni_core/mission_intent.py`.
- Mission graph build/review/validate is deterministic and file-I/O
  tolerant: `backend/app/mission_graph/{builder,reviewer,validators,schemas}.py`.
- Provenance is not a single shape in this codebase — there are multiple
  provenance representations produced by different code paths
  (`reliability/provenance.py`, `mission_graph/builder.py`,
  `omni_harness.py`, `generators/mission_report_generator.py`). Do not
  assume a provenance file from one path is interchangeable with another
  without checking the actual field shape.

## Auto Dev

- `omni/autodev/` and `scripts/omni_autodev.py` — a deliberately
  non-autonomous local toolkit: policy data (`config.py`), data shapes
  (`models.py`), a local issue-readiness checker (`issue_readiness.py`), a
  run-directory/role-packet scaffolder (`run_layout.py`), a single-path
  protected-path matcher (`protected_paths.py`), and structured production
  packet contracts (`packets.py`). None of it fetches GitHub issues, calls a
  model, calls the GitHub API, or launches an agent.
- See `docs/devops/omni_autodev.md` for the current CLI surface and
  `production_protocol.md` / `packet_contracts.md` in this directory for the
  workflow these pieces are meant to support.

## Validation and reliability

- Reliability gates: `backend/app/reliability/reliability_service.py`
  produces a `ReliabilityReport` of gates with status
  `PASS`/`WARN`/`FAIL`/`BLOCKED`, backed by deterministic calculators under
  `reliability/calculators/`.
- Safety gate: `backend/app/omni_core/safety_gate.py` — deterministic and
  advisory, not a hard blocker and not a substitute for human judgment.
- The OMNI Sandbox (`backend/app/sandbox/`, `docs/contracts/sandbox.md`) is a
  standalone, tested check/execution harness. It is not wired into the
  mission runtime or export pipeline, and it is explicitly documented as not
  a security sandbox.
- Findings projection (`docs/contracts/findings_projection.md`,
  `mission_graph/finding_projection.py`, `engineering/finding_projection.py`)
  is an additive, read-only normalized view over existing gate/graph reports
  — it does not enforce anything itself.

## Export systems

- `backend/app/export/export_manager.py` writes a mission's artifact tree to
  `outputs/omni_missions/<slug>/`: mission JSON/report, mission graph and
  graph review, reliability/design/candidate/intent reports, the Visual Bay
  manifest, Engineering Brain reports, the Concept Dossier manifest, and
  (when aerospace intent is detected) AeroForge reports.
- The export path's file names are not guaranteed to match what
  `mission_graph/builder.py` expects when re-reading a completed export
  folder — treat any change that assumes export and graph-builder file
  contracts are identical as an integration risk to verify, not an
  assumption.

## Tests

- `tests/` is the curated suite; collection scope is set in `pytest.ini`
  (`testpaths = tests`, plus `norecursedirs` excluding `knowledge/`,
  `outputs/`, `archive/`, `experiments/`, `avengers_env/`, `frontend/`,
  `node_modules/`). Nothing outside `tests/` is part of the enforced suite.
- Auto Dev tests: `tests/test_autodev_*.py`.
- Run tests with `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest tests -q`
  (see `test_matrix.md` for scoped subsets and the reason for the env var).

## Documentation

- `docs/agentic/` (this directory) — canonical, provider-neutral production
  workflow documentation. Single source of truth for the agentic production
  process.
- `docs/devops/` — operational docs for specific tools (`omni_ci.md`,
  `omni_autodev.md`, `codex_claude_handoff.md`). These describe what a
  specific script does; they defer to `docs/agentic/` for workflow/process.
- `docs/contracts/` — data-shape contracts for specific subsystems
  (`sandbox.md`, `findings_projection.md`).
- Provider entry files (`CLAUDE.md`, `AGENTS.md`) at the repo root are thin
  role pointers into `docs/agentic/` — they are not a second copy of this
  map.

## Generated artifacts

- `outputs/omni_missions/<slug>/` — per-mission export trees. Generated, not
  source. Excluded from test collection.
- `artifacts/autodev/runs/issue-<N>/` — local Auto Dev run-directory
  scaffolds (`STATE.json`, role packets, reports). Human/AI-editable working
  files, not generated-and-disposable — `run_layout.py` refuses to overwrite
  existing files in a run directory for this reason.
- `__pycache__/`, `*.pyc` — never source; never edit or review these.
