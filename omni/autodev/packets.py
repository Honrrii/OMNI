"""
Structured production-packet contracts for OMNI Auto Dev (Phase 11+).

These dataclasses give the workflow described in
docs/agentic/production_protocol.md a concrete, serializable shape: a run
manifest, a task packet, an implementation handoff (carrying test
evidence), a review packet, a repair packet, and a closeout packet. See
docs/agentic/packet_contracts.md for what each one means and when it's
produced.

Unlike omni/autodev/models.py's plain skeleton dataclasses, these types are
validated contracts: bad verdicts, out-of-range repair cycles, and
timeout/exit-code mismatches raise ValueError at construction time. That
validation is deliberately close to the data it protects rather than a
separate ad hoc checker, because these packets are meant to be trusted
without re-deriving their invariants every time they're read.

This module only builds, validates, and (de)serializes packets. It does not
call a model API, launch Claude or Codex, commit, open a PR, or merge
anything — wiring these packets into an automated orchestrator is out of
scope here.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field

PACKET_VERSION = "0.1"

MAX_REPAIR_CYCLES = 2

REVIEW_VERDICTS = ("APPROVED", "CHANGES_REQUIRED", "BLOCKED")

TASK_READINESS_STATUSES = ("READY", "NOT_READY")

ACCEPTANCE_CRITERION_STATUSES = ("VERIFIED", "PARTIAL", "FAILED", "NOT_VERIFIED")

TEST_EVIDENCE_OUTCOMES = ("passed", "failed", "timeout")


# ---------------------------------------------------------------------------
# Run manifest
# ---------------------------------------------------------------------------


@dataclass
class RunManifest:
    """Environment snapshot recorded once at the start of a production run."""

    run_id: str
    created_at: str
    repo_root: str
    start_commit: str
    branch: str
    requested_operation: str
    dirty_state_summary: list[str] = field(default_factory=list)
    packet_version: str = PACKET_VERSION


# ---------------------------------------------------------------------------
# Task packet
# ---------------------------------------------------------------------------


@dataclass
class TaskPacket:
    """Bounded scope contract produced after issue-readiness evaluation."""

    task_id: str
    goal: str
    in_scope_paths: list[str] = field(default_factory=list)
    out_of_scope_paths: list[str] = field(default_factory=list)
    invariants: list[str] = field(default_factory=list)
    acceptance_criteria: list[str] = field(default_factory=list)
    required_evidence: list[str] = field(default_factory=list)
    risk_notes: list[str] = field(default_factory=list)
    readiness_status: str = "NOT_READY"
    packet_version: str = PACKET_VERSION

    def __post_init__(self) -> None:
        if self.readiness_status not in TASK_READINESS_STATUSES:
            raise ValueError(
                f"invalid readiness_status {self.readiness_status!r}; "
                f"must be one of {TASK_READINESS_STATUSES}"
            )


# ---------------------------------------------------------------------------
# Shared sub-shapes
# ---------------------------------------------------------------------------


@dataclass
class AcceptanceCriterionResult:
    """One acceptance criterion's evaluated status, with evidence."""

    criterion: str
    status: str
    evidence: str = ""

    def __post_init__(self) -> None:
        if self.status not in ACCEPTANCE_CRITERION_STATUSES:
            raise ValueError(
                f"invalid acceptance criterion status {self.status!r}; "
                f"must be one of {ACCEPTANCE_CRITERION_STATUSES}"
            )


@dataclass
class TestEvidence:
    """One command's execution record.

    A `timeout` outcome must never carry an exit code, and a `passed` or
    `failed` outcome must always carry one — a hung or truncated run is
    not a pass or an ordinary failure, and that distinction is enforced
    here rather than left to whoever writes the packet.
    """

    __test__ = False  # not a pytest test case; name matches the domain concept

    command: str
    working_dir: str
    outcome: str
    exit_code: int | None = None
    started_at: str | None = None
    completed_at: str | None = None
    output_summary: str = ""

    def __post_init__(self) -> None:
        if self.outcome not in TEST_EVIDENCE_OUTCOMES:
            raise ValueError(
                f"invalid test evidence outcome {self.outcome!r}; "
                f"must be one of {TEST_EVIDENCE_OUTCOMES}"
            )
        if self.outcome == "timeout" and self.exit_code is not None:
            raise ValueError("timeout evidence must not carry an exit code")
        if self.outcome in ("passed", "failed") and self.exit_code is None:
            raise ValueError(f"{self.outcome!r} evidence must carry an exit code")


@dataclass
class Finding:
    """One reviewer finding.

    `severity` follows the existing OMNI findings_projection vocabulary
    (docs/contracts/findings_projection.md): info, warning, error, blocker.
    Unknown values are tolerated, matching that contract's own tolerance,
    rather than validated against a closed set here.
    """

    summary: str
    severity: str
    location: str
    required_action: str


# ---------------------------------------------------------------------------
# Implementation handoff
# ---------------------------------------------------------------------------


@dataclass
class ImplementationHandoff:
    """What the producer reports when implementation is done."""

    task_id: str
    files_changed: list[str] = field(default_factory=list)
    acceptance_criterion_results: list[AcceptanceCriterionResult] = field(default_factory=list)
    commands_run: list[str] = field(default_factory=list)
    test_results: list[TestEvidence] = field(default_factory=list)
    deviations: list[str] = field(default_factory=list)
    known_limitations: list[str] = field(default_factory=list)
    reviewer_attention_areas: list[str] = field(default_factory=list)
    packet_version: str = PACKET_VERSION


# ---------------------------------------------------------------------------
# Review packet
# ---------------------------------------------------------------------------


@dataclass
class ReviewPacket:
    """The independent reviewer's structured verdict."""

    task_id: str
    verdict: str
    acceptance_criterion_results: list[AcceptanceCriterionResult] = field(default_factory=list)
    findings: list[Finding] = field(default_factory=list)
    commands_run: list[str] = field(default_factory=list)
    unverified_claims: list[str] = field(default_factory=list)
    packet_version: str = PACKET_VERSION

    def __post_init__(self) -> None:
        if self.verdict not in REVIEW_VERDICTS:
            raise ValueError(
                f"invalid review verdict {self.verdict!r}; must be one of {REVIEW_VERDICTS}"
            )


# ---------------------------------------------------------------------------
# Repair packet
# ---------------------------------------------------------------------------


@dataclass
class RepairPacket:
    """A narrowly scoped fix request after a CHANGES_REQUIRED verdict.

    `review_cycle` must fall within 1..MAX_REPAIR_CYCLES — v0.1 allows at
    most two repair cycles (docs/agentic/production_protocol.md).
    """

    review_cycle: int
    required_actions: list[str] = field(default_factory=list)
    allowed_repair_scope: list[str] = field(default_factory=list)
    prohibited_scope: list[str] = field(default_factory=list)
    evidence_needed: list[str] = field(default_factory=list)
    packet_version: str = PACKET_VERSION

    def __post_init__(self) -> None:
        if not (1 <= self.review_cycle <= MAX_REPAIR_CYCLES):
            raise ValueError(
                f"invalid review_cycle {self.review_cycle!r}; "
                f"must be between 1 and {MAX_REPAIR_CYCLES}"
            )


# ---------------------------------------------------------------------------
# Closeout packet
# ---------------------------------------------------------------------------


@dataclass
class CloseoutPacket:
    """End-of-run record. Recommends a PR; never creates, merges, or pushes one."""

    task_id: str
    final_verdict: str
    completed_acceptance_criteria: list[str] = field(default_factory=list)
    final_test_evidence: list[TestEvidence] = field(default_factory=list)
    remaining_limitations: list[str] = field(default_factory=list)
    commit_sha: str = ""
    branch: str = ""
    recommended_pr_title: str = ""
    recommended_pr_body: str = ""
    human_approval_required: bool = True
    packet_version: str = PACKET_VERSION

    def __post_init__(self) -> None:
        if self.final_verdict not in REVIEW_VERDICTS:
            raise ValueError(
                f"invalid final_verdict {self.final_verdict!r}; "
                f"must be one of {REVIEW_VERDICTS}"
            )
        if not self.human_approval_required:
            raise ValueError(
                "human_approval_required must be True in v0.1 — no automatic merge"
            )


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------


def to_dict(packet: object) -> dict:
    """Convert any packet dataclass (including nested ones) to a plain dict."""
    return asdict(packet)


def to_json(packet: object) -> str:
    return json.dumps(to_dict(packet), indent=2) + "\n"


def run_manifest_from_dict(data: dict) -> RunManifest:
    return RunManifest(**data)


def task_packet_from_dict(data: dict) -> TaskPacket:
    return TaskPacket(**data)


def _acceptance_results_from_list(items: list[dict]) -> list[AcceptanceCriterionResult]:
    return [AcceptanceCriterionResult(**item) for item in items]


def _test_evidence_from_list(items: list[dict]) -> list[TestEvidence]:
    return [TestEvidence(**item) for item in items]


def implementation_handoff_from_dict(data: dict) -> ImplementationHandoff:
    payload = dict(data)
    payload["acceptance_criterion_results"] = _acceptance_results_from_list(
        payload.get("acceptance_criterion_results", [])
    )
    payload["test_results"] = _test_evidence_from_list(payload.get("test_results", []))
    return ImplementationHandoff(**payload)


def review_packet_from_dict(data: dict) -> ReviewPacket:
    payload = dict(data)
    payload["acceptance_criterion_results"] = _acceptance_results_from_list(
        payload.get("acceptance_criterion_results", [])
    )
    payload["findings"] = [Finding(**item) for item in payload.get("findings", [])]
    return ReviewPacket(**payload)


def repair_packet_from_dict(data: dict) -> RepairPacket:
    return RepairPacket(**data)


def closeout_packet_from_dict(data: dict) -> CloseoutPacket:
    payload = dict(data)
    payload["final_test_evidence"] = _test_evidence_from_list(payload.get("final_test_evidence", []))
    return CloseoutPacket(**payload)
