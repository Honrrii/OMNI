# OMNI Test Matrix

Maps change categories to the validation OMNI actually has today. Commands
below are the repository's real commands (`pytest.ini`,
`.github/workflows/omni-ci.yml`, `scripts/omni_ci_local.py`,
`docs/devops/omni_ci.md`) — do not invent a command that doesn't exist in
this repo.

All Python test runs in this repo use:

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest tests -q
```

The env var shields the run from globally installed pytest plugins (e.g.
ROS2's `launch` plugin autoloading `lark`); it does not scope collection.
Collection scope comes from `pytest.ini` (`testpaths = tests`, plus
`norecursedirs` excluding `knowledge/`, `outputs/`, `archive/`,
`experiments/`, `avengers_env/`, `frontend/`, `node_modules/`). Zero
collected tests is a failure (`pytest` exit code 5), never a pass.

| Change category | Required validation |
| --- | --- |
| Documentation-only (`docs/**`, `*.md`) | `git diff --check`; confirm no code/behavior claims were introduced without a source to back them. No test run required unless the doc documents a command — then run that command once to confirm it's accurate. |
| Data-model changes (`omni/autodev/models.py`, `omni/autodev/packets.py`, backend Pydantic/dataclass schemas) | Targeted tests for the changed module (e.g. `tests/test_autodev_structure.py`, `tests/test_autodev_packets.py`) plus any test that imports the changed shape. Check serialization round-trip if the type is serialized anywhere. |
| CLI changes (`scripts/omni_autodev.py`, other `scripts/*.py`) | `tests/test_autodev_structure.py` and the specific CLI test file for the touched subcommand (e.g. `tests/test_autodev_protected_paths.py` for `protected-paths`). Manually run `--help` and the changed subcommand at least once. |
| Auto Dev policy changes (`omni/autodev/config.py`, `omni/autodev/protected_paths.py`) | `tests/test_autodev_protected_paths.py`, `tests/test_autodev_structure.py`, and `docs/devops/omni_autodev.md` accuracy check. |
| Packet-schema changes (`omni/autodev/packets.py` and `docs/agentic/packet_contracts.md`) | `tests/test_autodev_packets.py` in full (valid creation, required-field rejection, serialization round-trip, version stability, invalid-verdict rejection, invalid-repair-cycle rejection, timeout evidence representation, no shared mutable defaults, compatibility with `run_layout.py`/`AutoDevRunState`). |
| Backend changes (`backend/app/**`) | `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest tests -q` (curated suite covers mission graph, reliability, safety gate, sandbox, export, engineering, candidate evaluation). Identify and run the specific `tests/test_*.py` file(s) covering the touched module before running the full suite. |
| Frontend changes (`frontend/**`) | `npm run build` from `frontend/` (matches CI's `frontend-build` job). For behavior changes, drive the feature in a browser and capture a screenshot — see `docs/agentic/packet_contracts.md`'s implementation-handoff evidence requirements. |
| Cross-layer changes (touch both `backend/app/**` and `frontend/**`, or change a shape both sides depend on) | Both the backend and frontend validation above, plus a manual check that field names agree on both sides (no shared schema-generation step exists — see `repository_map.md`). |
| Any change (baseline) | `git status --short`, `git diff --check`, `git diff --stat` before committing. |
| Full local CI | `python scripts/omni_ci_local.py` — runs `git status --short`, `git diff --check`, the curated pytest suite, and the frontend build when `frontend/package.json` exists. Whitespace, Python tests, and the frontend build must pass for exit code 0; git status is informational only. |

## Timeout handling

If a validation command times out:

- Record the timeout duration, the last visible test/location before the
  hang, and whether it reproduces on a second run.
- Report the result as **inconclusive**, never as a pass or an ordinary
  failure.
- Do not narrow scope or add `-k`/`--timeout` flags to make a timeout
  disappear without first identifying why the run is slow or hanging.
