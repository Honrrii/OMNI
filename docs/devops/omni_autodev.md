# OMNI Auto Dev

OMNI Auto Dev is a planned system for scoping and tracking multi-step engineering
campaigns. This document describes the Phase 11 core skeleton only.

## What exists today

* `omni/autodev/models.py` — plain dataclasses describing the shape of a future
  campaign: `AutoDevCampaign`, `AutoDevTask`, `AutoDevSafetyRule`,
  `AutoDevValidationPlan`, `AutoDevDryRunSummary`. No validation logic yet.
* `omni/autodev/config.py` — default lists: `DEFAULT_PROTECTED_AREAS`,
  `DEFAULT_NON_GOALS`, `DEFAULT_VALIDATION_COMMANDS`. Plain data, not
  enforcement.
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

## Planned future layers

Later phases may add, in order:

1. Campaign YAML loading
2. Issue readiness scoring
3. Handoff packet generation
4. Validation result tracking
5. Protected path checks

Each of these is a separate, reviewed change — not part of this skeleton.
