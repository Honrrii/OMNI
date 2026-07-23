"""
Default configuration values for the OMNI Auto Dev skeleton.

These are plain lists, not enforcement logic. Nothing in this module reads
or writes files, calls a model, or reaches the network.
"""
from __future__ import annotations

# Areas Auto Dev must not touch unless only referenced in docs/examples.
# Mirrors the standing OMNI workflow constraints used elsewhere in the repo
# (see scripts/omni_handoff_packet.py DEFAULT_FORBIDDEN).
DEFAULT_PROTECTED_AREAS: list[str] = [
    "Sandbox implementation (backend/app/sandbox/**)",
    "UI / frontend",
    "ML model code",
    "ROS export",
    "Visual Bay",
    "Mission graph",
]

# Capabilities this skeleton intentionally does not implement yet.
DEFAULT_NON_GOALS: list[str] = [
    "GitHub issue fetching",
    "Agent routing",
    "Validation command runners",
    "Metrics ledgers",
    "Frontend panels",
    "Network access",
    "LLM calls",
    "GitHub API calls",
    "Autonomous execution",
]

# Commands a future validation layer would eventually run. Not executed by
# this skeleton; kept here only as a planning placeholder.
DEFAULT_VALIDATION_COMMANDS: list[str] = [
    "PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest tests -q",
]

# Default AI roles for a local Auto Dev run. Names only — no agent is
# launched by this skeleton.
DEFAULT_IMPLEMENTER: str = "claude"
DEFAULT_REVIEWER: str = "codex"
DEFAULT_RUN_STATUS: str = "planned"

# Where local run directories are created by default.
DEFAULT_RUNS_ROOT: str = "artifacts/autodev/runs"

# Filenames every run directory scaffold must contain.
RUN_TEMPLATE_FILENAMES: list[str] = [
    "STATE.json",
    "IMPLEMENTER_PACKET.md",
    "REVIEWER_PACKET.md",
    "IMPLEMENTER_REPORT.md",
    "REVIEW_REPORT.md",
    "README.md",
]

# Sections a local issue body file must contain to be considered "ready" for
# an Auto Dev run. Each entry pairs a canonical name with recognized heading
# aliases (matched case-insensitively, whitespace-normalized).
DEFAULT_REQUIRED_ISSUE_SECTIONS: list[tuple[str, list[str]]] = [
    ("Goal", ["Goal", "Goals"]),
    ("Scope", ["Scope"]),
    (
        "Out of Scope / Non-goals",
        ["Out of Scope / Non-goals", "Out of Scope", "Non-goals", "Non Goals"],
    ),
    ("Expected Files", ["Expected Files"]),
    ("Acceptance Criteria", ["Acceptance Criteria"]),
    ("Validation Commands", ["Validation Commands"]),
    ("Stop Conditions", ["Stop Conditions"]),
    ("Final Report", ["Final Report"]),
]

# Path glob patterns Auto Dev must not touch without dedicated human review,
# paired with the reason each area is protected. Patterns are matched with
# fnmatch against repo-relative, forward-slash paths (no git diff scanning
# or changed-file enforcement here — that is a future layer).
DEFAULT_PROTECTED_PATH_RULES: list[tuple[str, str]] = [
    (
        "backend/app/sandbox/**",
        "Sandbox implementation — process isolation and resource limits; "
        "changes need dedicated security review.",
    ),
    (
        "frontend/**",
        "UI / frontend — outside Auto Dev's backend scope; requires human "
        "frontend review.",
    ),
    (
        "backend/app/ml/**",
        "ML model code — model behavior changes need domain review.",
    ),
    (
        "backend/app/ros/**",
        "ROS export — robotics interop surface; changes need domain review.",
    ),
    (
        "frontend/src/components/VisualBay*",
        "Visual Bay — visualization surface; outside Auto Dev's scope.",
    ),
    (
        "backend/app/mission_graph/**",
        "Mission graph — core mission orchestration; changes need "
        "dedicated review.",
    ),
]
