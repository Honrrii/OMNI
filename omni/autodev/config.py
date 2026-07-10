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
