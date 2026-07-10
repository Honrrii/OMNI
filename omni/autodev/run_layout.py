"""
Local file-based run directory layout for OMNI Auto Dev.

Builds the on-disk scaffold (STATE.json plus implementer/reviewer packet and
report templates) that a human uses to coordinate Claude/Codex work by hand.
This module only renders strings and writes local files — it never launches
an agent, calls a model, or reaches the network or GitHub API.
"""
from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from omni.autodev.config import DEFAULT_RUNS_ROOT, RUN_TEMPLATE_FILENAMES
from omni.autodev.models import AutoDevRunState


def default_run_dir(issue_number: int) -> Path:
    return Path(DEFAULT_RUNS_ROOT) / f"issue-{issue_number}"


def render_state_json(state: AutoDevRunState) -> str:
    return json.dumps(asdict(state), indent=2) + "\n"


def render_implementer_packet(state: AutoDevRunState) -> str:
    return (
        f"# Implementer Packet — Issue {state.issue_number}: {state.issue_title}\n\n"
        f"Role: implementer ({state.implementer})\n"
        f"Branch: {state.branch}\n"
        f"Reviewer: {state.reviewer}\n"
        f"Status: {state.status}\n"
        f"Human approval required before merge: {state.human_approval_required}\n\n"
        "## Your role\n\n"
        "You are the implementer agent for this run. Make the scoped code change "
        "described by this issue on the branch above, then fill in "
        "IMPLEMENTER_REPORT.md when you are done.\n\n"
        "## Scope\n\n"
        "(Fill in: paste the issue scope and any non-goals or forbidden areas here "
        "before handing this packet to the implementer.)\n\n"
        "## Rules\n\n"
        "- Do not merge or push without explicit human approval.\n"
        "- Do not expand scope beyond what is written above.\n"
        "- Record what changed and why in IMPLEMENTER_REPORT.md.\n"
    )


def render_reviewer_packet(state: AutoDevRunState) -> str:
    return (
        f"# Reviewer Packet — Issue {state.issue_number}: {state.issue_title}\n\n"
        f"Role: reviewer ({state.reviewer})\n"
        f"Branch: {state.branch}\n"
        f"Implementer: {state.implementer}\n"
        f"Status: {state.status}\n"
        f"Human approval required before merge: {state.human_approval_required}\n\n"
        "## Your role\n\n"
        "You are the reviewer agent for this run. Review the implementer's change "
        "on the branch above for correctness, scope creep, and safety, then fill "
        "in REVIEW_REPORT.md.\n\n"
        "## What to check\n\n"
        "- Does the change match the scope in IMPLEMENTER_PACKET.md?\n"
        "- Are any forbidden or protected areas touched?\n"
        "- Do the tests pass?\n\n"
        "## Rules\n\n"
        "- Do not merge or push without explicit human approval.\n"
        "- Record findings in REVIEW_REPORT.md.\n"
    )


def render_implementer_report(state: AutoDevRunState) -> str:
    return (
        f"# Implementer Report — Issue {state.issue_number}\n\n"
        "Status: (fill in)\n\n"
        "## Summary of changes\n\n"
        "(fill in)\n\n"
        "## Test results\n\n"
        "(fill in)\n\n"
        "## Risks / follow-ups\n\n"
        "(fill in)\n"
    )


def render_review_report(state: AutoDevRunState) -> str:
    return (
        f"# Review Report — Issue {state.issue_number}\n\n"
        "Verdict: (fill in: approve / changes requested)\n\n"
        "## Findings\n\n"
        "(fill in)\n\n"
        "## Scope check\n\n"
        "(fill in)\n"
    )


def render_readme(state: AutoDevRunState) -> str:
    return (
        f"# Auto Dev Run — Issue {state.issue_number}: {state.issue_title}\n\n"
        "This directory is a local, file-based coordination scaffold for one Auto "
        "Dev run. It does not launch agents, fetch GitHub issues, or execute "
        "anything on its own — it only holds the packets and reports a human "
        "copies between an implementer AI and a reviewer AI.\n\n"
        "## Files\n\n"
        "- `STATE.json` — run metadata (issue, branch, implementer, reviewer, "
        "status, human approval requirement).\n"
        "- `IMPLEMENTER_PACKET.md` — paste into the implementer AI's session.\n"
        "- `REVIEWER_PACKET.md` — paste into the reviewer AI's session.\n"
        "- `IMPLEMENTER_REPORT.md` — implementer fills this in when done.\n"
        "- `REVIEW_REPORT.md` — reviewer fills this in when done.\n\n"
        "## Workflow\n\n"
        "1. Human creates this run directory with `omni_autodev.py init-run`.\n"
        "2. Human pastes IMPLEMENTER_PACKET.md into the implementer AI.\n"
        "3. Implementer AI does the work and fills in IMPLEMENTER_REPORT.md.\n"
        "4. Human pastes REVIEWER_PACKET.md (plus the implementer's diff/report) "
        "into the reviewer AI.\n"
        "5. Reviewer AI fills in REVIEW_REPORT.md.\n"
        "6. Human reviews both reports and approves or requests changes.\n\n"
        "No step in this workflow is automatic. A human drives every handoff.\n"
    )


_RENDERERS = {
    "STATE.json": render_state_json,
    "IMPLEMENTER_PACKET.md": render_implementer_packet,
    "REVIEWER_PACKET.md": render_reviewer_packet,
    "IMPLEMENTER_REPORT.md": render_implementer_report,
    "REVIEW_REPORT.md": render_review_report,
    "README.md": render_readme,
}


def build_run_files(state: AutoDevRunState) -> dict[str, str]:
    """Map of filename -> rendered content for a run directory. Writes nothing."""
    return {name: _RENDERERS[name](state) for name in RUN_TEMPLATE_FILENAMES}


class AutoDevRunConflictError(FileExistsError):
    """Raised when write_run_files would overwrite an existing run file.

    Run directories hold fillable human/AI reports and editable packets, so
    a rerun must never silently clobber them.
    """

    def __init__(self, run_dir: Path, existing: list[Path]):
        self.run_dir = run_dir
        self.existing = existing
        names = ", ".join(path.name for path in existing)
        super().__init__(f"refusing to overwrite existing file(s) in {run_dir}: {names}")


def write_run_files(run_dir: Path, files: dict[str, str]) -> list[Path]:
    """Write the given filename->content map into run_dir, creating it if needed.

    Refuses to overwrite: if any target file already exists, nothing is
    written and AutoDevRunConflictError is raised naming the conflicting
    file(s).
    """
    existing = [run_dir / name for name in files if (run_dir / name).exists()]
    if existing:
        raise AutoDevRunConflictError(run_dir, existing)

    run_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for name, content in files.items():
        path = run_dir / name
        path.write_text(content, encoding="utf-8")
        written.append(path)
    return written
