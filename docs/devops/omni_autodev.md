# OMNI Auto Dev

OMNI Auto Dev is a planned system for scoping and tracking multi-step engineering
campaigns. This document describes the current local, non-autonomous tooling only.

For the canonical, provider-neutral production workflow, invariants, and
packet lifecycle that this tooling is meant to eventually support, see
`docs/agentic/` (`production_protocol.md`, `repository_invariants.md`,
`packet_contracts.md`). This document does not duplicate that content — it
documents what the current CLI and modules actually do.

## What exists today

* `omni/autodev/models.py` — plain dataclasses describing the shape of a future
  campaign: `AutoDevCampaign`, `AutoDevTask`, `AutoDevSafetyRule`,
  `AutoDevValidationPlan`, `AutoDevDryRunSummary`. No validation logic yet.
* `omni/autodev/config.py` — default lists: `DEFAULT_PROTECTED_AREAS`,
  `DEFAULT_NON_GOALS`, `DEFAULT_VALIDATION_COMMANDS`,
  `DEFAULT_REQUIRED_ISSUE_SECTIONS`, and `DEFAULT_PROTECTED_PATH_RULES`.
  Plain data, not enforcement.
* `omni/autodev/issue_readiness.py` — deterministic heading-text matching
  that checks a local issue body file for the required Auto Dev sections.
* `omni/autodev/protected_paths.py` — matches a single path string against
  the protected path patterns. No git diff scanning or changed-file
  enforcement yet.
* `omni/autodev/packets.py` — structured, validated production packet
  contracts (run manifest, task packet, implementation handoff, test
  evidence, review packet, repair packet, closeout packet). See
  `docs/agentic/packet_contracts.md` for what each one means. This module
  builds and validates packets only — it does not call a model, launch an
  agent, commit, or open a PR.
* `scripts/omni_autodev.py` — a CLI with `--help` and `--dry-run`. The
  dry run prints a skeleton-only summary and does not touch the network,
  call a model, or call the GitHub API.

Run it:

```bash
python scripts/omni_autodev.py --help
python scripts/omni_autodev.py --dry-run
```

## Non-goals (this phase)

This skeleton intentionally does **not**:

* Fetch GitHub issues
* Route work to agents
* Run validation commands
* Track metrics in a ledger
* Render a frontend panel
* Make network calls, LLM calls, or GitHub API calls
* Execute anything autonomously

## Run directory and role packets

Auto Dev can also scaffold a local, file-based run directory for one issue.
This is a coordination aid a human uses when copying work between an
implementer AI (e.g. Claude) and a reviewer AI (e.g. Codex) — it does not
launch either agent or talk to GitHub.

```bash
python scripts/omni_autodev.py init-run --issue 60 --title "..." --dry-run
python scripts/omni_autodev.py init-run --issue 60 --title "..." \
  --branch "omni/phase11-autodev-run-directory-role-packets" \
  --implementer claude --reviewer codex
```

This creates:

```text
artifacts/autodev/runs/issue-60/
├── STATE.json             # issue number, title, branch, implementer, reviewer, status, human approval requirement
├── IMPLEMENTER_PACKET.md   # paste into the implementer AI's session
├── REVIEWER_PACKET.md      # paste into the reviewer AI's session
├── IMPLEMENTER_REPORT.md   # implementer fills in when done
├── REVIEW_REPORT.md        # reviewer fills in when done
└── README.md               # explains this run directory's workflow
```

Every step (creating the directory, pasting packets, filling in reports) is
done by a human. Nothing here starts an agent, fetches an issue, or executes
code automatically.

## Local issue readiness checker

Before scaffolding a run, a human can check whether an issue body (saved
locally as Markdown/text — Auto Dev does not fetch it from GitHub) has the
sections an implementer/reviewer packet needs.

```bash
python scripts/omni_autodev.py check-issue --file /tmp/omni_issue_ready.md
```

Required sections (matched by markdown heading text, case-insensitively;
`Out of Scope / Non-goals` also accepts `Out of Scope` or `Non-goals` alone):

```text
Goal
Scope
Out of Scope / Non-goals
Expected Files
Acceptance Criteria
Validation Commands
Stop Conditions
Final Report
```

The verdict is `READY` when every required section is present, or
`NEEDS_DETAIL` when any are missing — output lists each section's status plus
the missing ones by name. A missing input file is a clear, nonzero-exit CLI
error, not a `NEEDS_DETAIL` verdict. This checker only reads a local file; it
never fetches from GitHub, calls a model, or uses the `gh` CLI.

## Protected path policy

Auto Dev defines which paths need dedicated human review before any future
layer touches them. This is policy data plus a single-path matcher — it does
not scan a git diff or enforce anything against a real change set yet.

```bash
python scripts/omni_autodev.py protected-paths
```

Lists each protected glob pattern and the reason it's protected (sandbox,
frontend, ML model code, ROS export, Visual Bay, mission graph). To check one
path in code:

```python
from omni.autodev.protected_paths import match_protected_path

match_protected_path("backend/app/sandbox/limited_launcher.py")  # -> AutoDevProtectedPathRule(...)
match_protected_path("omni/autodev/config.py")                   # -> None
match_protected_path("../escape.py")                             # -> raises ValueError
```

`match_protected_path` fails closed on invalid input (empty, `.`, `..`, an
absolute or drive-qualified path, a UNC path, or anything containing a `..`
component) — it raises `ValueError` rather than returning an ordinary
unprotected `None`. See `docs/agentic/packet_contracts.md`'s "one shared
repository-relative path contract" for the full normalization and matching
rules, which this module also exposes as `normalize_repo_relative_path` and
`spec_matches` for reuse elsewhere in Auto Dev.

## Production packet contracts

`omni/autodev/packets.py` defines validated dataclasses for the packets a
production run under `docs/agentic/production_protocol.md` produces:
`RunManifest`, `TaskPacket`, `ImplementationHandoff`, `TestEvidence`,
`ReviewPacket`, `RepairPacket`, `CloseoutPacket`. They validate at
construction (verdicts, repair-cycle bounds, timeout representation) and
round-trip through `to_dict`/`to_json` plus the module's `*_from_dict`
functions. See `docs/agentic/packet_contracts.md` for semantics and
lifecycle.

This is contract data only. Nothing in this module writes a packet into a
run directory automatically, calls a model, launches Claude or Codex,
commits, or opens a PR — wiring these packets into the run-directory
scaffold (`run_layout.py`) and into an actual orchestrator remain future,
separately reviewed changes.

## Planned future layers

Later phases may add, in order:

1. Campaign YAML loading
2. Wiring packet contracts (`packets.py`) into run-directory generation and
   an actual implementer/reviewer handoff flow
3. Validation result tracking
4. Changed-file protected-path enforcement (git diff scanning against this policy)

Each of these is a separate, reviewed change — not part of this skeleton.
