"""
Data model stubs for the OMNI Auto Dev skeleton.

These are simple dataclasses describing the shape of a future Auto Dev
campaign. They hold data only — no validation, no I/O, no model calls.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class AutoDevSafetyRule:
    """A single protected-area or non-goal boundary Auto Dev must respect."""

    name: str
    description: str


@dataclass
class AutoDevValidationPlan:
    """Placeholder for the validation commands a campaign would eventually run."""

    commands: list[str] = field(default_factory=list)


@dataclass
class AutoDevTask:
    """A single planned unit of work within a campaign."""

    name: str
    description: str
    status: str = "planned"


@dataclass
class AutoDevCampaign:
    """A named grouping of planned tasks, safety rules, and a validation plan."""

    name: str
    description: str
    tasks: list[AutoDevTask] = field(default_factory=list)
    safety_rules: list[AutoDevSafetyRule] = field(default_factory=list)
    validation_plan: AutoDevValidationPlan = field(default_factory=AutoDevValidationPlan)


@dataclass
class AutoDevDryRunSummary:
    """What a dry run reports: skeleton status and disabled capabilities."""

    status: str = "skeleton only"
    network_enabled: bool = False
    llm_calls_enabled: bool = False
    github_api_enabled: bool = False
    autonomous_execution_enabled: bool = False
    planned_future_layers: list[str] = field(default_factory=list)


@dataclass
class AutoDevRunState:
    """Metadata for one local Auto Dev run directory (STATE.json contents)."""

    issue_number: int
    issue_title: str
    branch: str
    implementer: str = "claude"
    reviewer: str = "codex"
    status: str = "planned"
    human_approval_required: bool = True


@dataclass
class AutoDevIssueReadiness:
    """Result of checking a local issue body file for required Auto Dev sections."""

    verdict: str
    present_sections: list[str] = field(default_factory=list)
    missing_sections: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass
class AutoDevProtectedPathRule:
    """A single protected path glob pattern and why it requires human review."""

    pattern: str
    reason: str
