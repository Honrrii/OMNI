# OMNI CI

OMNI CI is a small, inspectable safety foundation for branch verification. It does not deploy, publish, merge, delete branches, or use credentials.

## GitHub Actions

The `.github/workflows/omni-ci.yml` workflow runs on `push` and `pull_request`.

It has two jobs:

- Backend Python tests: checks out the repo, sets up Python 3.10, upgrades pip, installs `requirements.txt` and `backend/requirements.txt` when present, then runs `python -m pytest tests`.
- Frontend build: checks out the repo, sets up Node 20, runs `npm ci` in `frontend/`, then runs `npm run build`.

The workflow uses read-only repository permissions and intentionally contains no deployment or publishing steps.

The pytest step sets `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`. This keeps ROS2 or other globally installed pytest plugins from breaking the run (on machines with ROS2 Humble, the autoloaded `launch` plugins import `lark` at startup and crash pytest before collection even begins). The flag is an environment shield only — it is not what scopes collection.

CI intentionally targets OMNI's curated `tests/` suite. It does not collect copied knowledge/reference sources under `knowledge/ros2_sources/` or generated mission artifacts under `outputs/omni_missions/`.

## Collection Scoping

Collection scope is defined in `pytest.ini` at the repository root, not by per-command flags:

- `testpaths = tests` makes a bare `python -m pytest` collect only the curated suite.
- `norecursedirs` excludes `knowledge`, `outputs`, `archive`, `experiments`, `avengers_env`, `frontend`, and `node_modules`, so collection can never escape into copied ROS2 sources or generated mission artifacts (which carry uninstallable dependencies such as `lark` and `psutil`, plus duplicate test basenames that cause import-mismatch errors).

Zero collected tests is a failure, not a pass. pytest exits with code 5 when it collects nothing, and both runners treat any non-zero exit as FAIL; the local runner additionally prints an explicit zero-collection message. If the Python tests step reports zero collected, the curated `tests/` suite is missing or empty on the branch under test — fix the branch, do not relax the runner.

## Local CI

Run local CI from the repository root:

```bash
python scripts/omni_ci_local.py
```

The local script prints an `OMNI Local CI` report and runs:

- `git status --short`
- `git diff --check`
- `python -m pytest tests`
- `npm run build` for `frontend/` when `frontend/package.json` exists

Git status is informational. Whitespace checks, Python tests, and the frontend build must pass for the script to return exit code 0.

Local pytest also runs with `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1` so developer machines with ROS2 or other global pytest plugins get the same isolated behavior as GitHub Actions.

The local pytest command matches GitHub Actions and only collects the curated `tests/` suite. Reference material and generated mission outputs are outside this core CI surface.

## Safe Review Model

GitHub Actions verifies branches after they are pushed. OMNI should eventually be able to read GitHub status checks and report whether a branch is ready for human review.

OMNI must never auto-merge without human approval.

Safe flow:

```text
OMNI prepares -> local checks run -> GitHub verifies -> Henry approves
```
