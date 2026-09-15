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

from omni.autodev.protected_paths import (
    GLOB_METACHARACTERS,
    normalize_repo_relative_path,
    spec_matches,
)

PACKET_VERSION = "0.1"

MAX_REPAIR_CYCLES = 2

REVIEW_VERDICTS = ("APPROVED", "CHANGES_REQUIRED", "BLOCKED")

TASK_READINESS_STATUSES = ("READY", "NOT_READY")

ACCEPTANCE_CRITERION_STATUSES = ("VERIFIED", "PARTIAL", "FAILED", "NOT_VERIFIED")

TEST_EVIDENCE_OUTCOMES = ("passed", "failed", "timeout")


def _require_nonempty(value: str, field_name: str, packet_name: str) -> None:
    if not value or not value.strip():
        raise ValueError(f"{packet_name}.{field_name} must be a non-empty string")


def _require_packet_version(value: str, packet_name: str) -> None:
    if value != PACKET_VERSION:
        raise ValueError(
            f"{packet_name}.packet_version {value!r} does not match the current "
            f"PACKET_VERSION {PACKET_VERSION!r} — a version bump is a deliberate "
            f"change to omni/autodev/packets.py, not something a packet can drift into"
        )


def _require_no_duplicate_criteria(
    results: list[AcceptanceCriterionResult], packet_name: str
) -> None:
    seen: set[str] = set()
    for result in results:
        trimmed = result.criterion.strip()
        if trimmed in seen:
            raise ValueError(
                f"{packet_name}.acceptance_criterion_results has a duplicate "
                f"criterion {trimmed!r} (compared after trimming whitespace) "
                f"— each criterion must map to exactly one result"
            )
        seen.add(trimmed)


def _require_nonempty_list_items(items: list[str], packet_name: str, field_name: str) -> None:
    for item in items:
        if not item or not item.strip():
            raise ValueError(
                f"{packet_name}.{field_name} must not contain empty or "
                f"whitespace-only strings"
            )


def _require_valid_criteria_list(criteria: list[str], packet_name: str, field_name: str) -> None:
    """Every criterion must be non-empty/non-whitespace, and no two criteria
    may be the same after trimming. A validated, trimmed criterion string is
    the criterion identity for packet version 0.1 — there is no separate
    criterion-ID model.
    """
    _require_nonempty_list_items(criteria, packet_name, field_name)
    seen: set[str] = set()
    for criterion in criteria:
        trimmed = criterion.strip()
        if trimmed in seen:
            raise ValueError(
                f"{packet_name}.{field_name} has a duplicate criterion "
                f"{trimmed!r} (compared after trimming whitespace)"
            )
        seen.add(trimmed)


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

    def __post_init__(self) -> None:
        for name in ("run_id", "created_at", "repo_root", "start_commit", "branch", "requested_operation"):
            _require_nonempty(getattr(self, name), name, "RunManifest")
        _require_packet_version(self.packet_version, "RunManifest")


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
        _require_nonempty(self.task_id, "task_id", "TaskPacket")
        _require_nonempty(self.goal, "goal", "TaskPacket")
        _require_packet_version(self.packet_version, "TaskPacket")
        if self.readiness_status not in TASK_READINESS_STATUSES:
            raise ValueError(
                f"invalid readiness_status {self.readiness_status!r}; "
                f"must be one of {TASK_READINESS_STATUSES}"
            )
        # Element-level validity (no empty/whitespace-only entries, no
        # duplicates after trimming) applies regardless of readiness — a
        # NOT_READY task may have zero criteria, but any criteria it does
        # carry must already be meaningful.
        _require_valid_criteria_list(self.acceptance_criteria, "TaskPacket", "acceptance_criteria")
        if self.readiness_status == "READY" and not self.acceptance_criteria:
            raise ValueError(
                "TaskPacket.acceptance_criteria must be non-empty when "
                "readiness_status is READY — a task ready for implementation "
                "needs at least one acceptance criterion to be traceable"
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
        _require_nonempty(self.criterion, "criterion", "AcceptanceCriterionResult")
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

    def __post_init__(self) -> None:
        _require_nonempty(self.task_id, "task_id", "ImplementationHandoff")
        _require_packet_version(self.packet_version, "ImplementationHandoff")
        _require_no_duplicate_criteria(self.acceptance_criterion_results, "ImplementationHandoff")


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
        _require_nonempty(self.task_id, "task_id", "ReviewPacket")
        _require_packet_version(self.packet_version, "ReviewPacket")
        if self.verdict not in REVIEW_VERDICTS:
            raise ValueError(
                f"invalid review verdict {self.verdict!r}; must be one of {REVIEW_VERDICTS}"
            )
        _require_no_duplicate_criteria(self.acceptance_criterion_results, "ReviewPacket")


# ---------------------------------------------------------------------------
# Repair packet
# ---------------------------------------------------------------------------


@dataclass
class RepairPacket:
    """A narrowly scoped fix request after a CHANGES_REQUIRED verdict.

    `review_cycle` must fall within 1..MAX_REPAIR_CYCLES — v0.1 allows at
    most two repair cycles (docs/agentic/production_protocol.md). `task_id`
    binds this repair to the task it repairs — see
    `validate_repair_within_task_scope`, which checks it against a
    `TaskPacket` before path containment is even considered.

    `allowed_repair_scope` must contain **concrete repository-relative
    paths only** (see `omni.autodev.protected_paths.normalize_repo_relative_path`),
    not glob patterns — unlike `TaskPacket.in_scope_paths`/
    `out_of_scope_paths`, which may be literal paths, directory prefixes, or
    globs. This deliberately avoids attempting general pattern-to-pattern
    set containment.
    """

    task_id: str
    review_cycle: int
    required_actions: list[str] = field(default_factory=list)
    allowed_repair_scope: list[str] = field(default_factory=list)
    prohibited_scope: list[str] = field(default_factory=list)
    evidence_needed: list[str] = field(default_factory=list)
    packet_version: str = PACKET_VERSION

    def __post_init__(self) -> None:
        _require_nonempty(self.task_id, "task_id", "RepairPacket")
        _require_packet_version(self.packet_version, "RepairPacket")
        if not (1 <= self.review_cycle <= MAX_REPAIR_CYCLES):
            raise ValueError(
                f"invalid review_cycle {self.review_cycle!r}; "
                f"must be between 1 and {MAX_REPAIR_CYCLES}"
            )
        for path in self.allowed_repair_scope:
            if any(ch in path for ch in GLOB_METACHARACTERS):
                raise ValueError(
                    f"RepairPacket.allowed_repair_scope entry {path!r} contains a "
                    f"glob metacharacter — allowed_repair_scope must be concrete "
                    f"repository-relative paths only, not patterns"
                )
            # Raises ValueError on malformed/absolute/drive-qualified/UNC/
            # repository-escaping input; the normalized form is not stored
            # back onto the field (allowed_repair_scope is preserved exactly
            # as given), this call is purely for its fail-closed validation.
            normalize_repo_relative_path(path)


def validate_repair_within_task_scope(repair: RepairPacket, task: TaskPacket) -> None:
    """Reject a repair packet that does not belong to `task`, or whose
    allowed scope reaches outside it.

    Identity is checked first: `repair.task_id` must match `task.task_id`
    (compared after trimming). A repair packet must not validate against an
    unrelated task merely because its paths happen to fit — path
    containment is only meaningful once identity is confirmed.

    Path containment then applies OMNI's shared scope-matching contract
    (`omni.autodev.protected_paths.spec_matches`) to each entry of
    `repair.allowed_repair_scope`:

    1. If any `task.out_of_scope_paths` specification matches the path,
       reject — out-of-scope rules take precedence.
    2. If `task.in_scope_paths` is non-empty, the path must match at least
       one of its specifications.
    3. If `task.in_scope_paths` is empty, scope is intentionally
       unconstrained (the task packet did not enumerate a boundary), so any
       path not caught by rule 1 is allowed.

    This is intentionally a standalone check rather than a `RepairPacket`
    constructor rule: a `RepairPacket` can be constructed and inspected on
    its own (e.g. while drafting it), but re-review must not accept one that
    fails this check against the task it repairs.
    """
    if repair.task_id.strip() != task.task_id.strip():
        raise ValueError(
            f"RepairPacket.task_id {repair.task_id!r} does not match "
            f"TaskPacket.task_id {task.task_id!r} — a repair packet must not "
            f"be validated against an unrelated task"
        )

    for path in repair.allowed_repair_scope:
        for spec in task.out_of_scope_paths:
            if spec_matches(spec, path):
                raise ValueError(
                    f"RepairPacket.allowed_repair_scope contains {path!r}, which "
                    f"matches TaskPacket {task.task_id!r}'s out_of_scope_paths "
                    f"specification {spec!r}"
                )
        if task.in_scope_paths and not any(
            spec_matches(spec, path) for spec in task.in_scope_paths
        ):
            raise ValueError(
                f"RepairPacket.allowed_repair_scope contains {path!r}, which does "
                f"not match any of TaskPacket {task.task_id!r}'s in_scope_paths "
                f"specifications"
            )


# ---------------------------------------------------------------------------
# Closeout packet
# ---------------------------------------------------------------------------


@dataclass
class CloseoutPacket:
    """End-of-run record. Recommends a PR; never creates, merges, or pushes one.

    An `APPROVED` closeout requires meaningful completion evidence (branch,
    commit, completed criteria, non-timeout test evidence, recommended PR
    title/body) — see `__post_init__`. A `CHANGES_REQUIRED` or `BLOCKED`
    closeout only needs to be structurally valid; it does not need to look
    like finished, approved work.
    """

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
        _require_nonempty(self.task_id, "task_id", "CloseoutPacket")
        _require_packet_version(self.packet_version, "CloseoutPacket")
        if self.final_verdict not in REVIEW_VERDICTS:
            raise ValueError(
                f"invalid final_verdict {self.final_verdict!r}; "
                f"must be one of {REVIEW_VERDICTS}"
            )
        # `is not True` (not `not self.human_approval_required` or `!=
        # True`) deliberately: truthy non-bools like 1 or "yes" must be
        # rejected too, not silently accepted because they're truthy. Since
        # True is a bool singleton, `X is True` already implies
        # `type(X) is bool` — no separate type check is needed.
        if self.human_approval_required is not True:
            raise ValueError(
                "CloseoutPacket.human_approval_required must be exactly True "
                f"in v0.1 — no automatic merge; got {self.human_approval_required!r} "
                f"({type(self.human_approval_required).__name__})"
            )
        if self.final_verdict == "APPROVED":
            self._require_approved_evidence()

    def _require_approved_evidence(self) -> None:
        _require_nonempty(self.branch, "branch", "CloseoutPacket (APPROVED)")
        _require_nonempty(self.commit_sha, "commit_sha", "CloseoutPacket (APPROVED)")
        _require_nonempty(
            self.recommended_pr_title, "recommended_pr_title", "CloseoutPacket (APPROVED)"
        )
        _require_nonempty(
            self.recommended_pr_body, "recommended_pr_body", "CloseoutPacket (APPROVED)"
        )
        if not self.completed_acceptance_criteria:
            raise ValueError(
                "CloseoutPacket.completed_acceptance_criteria must be non-empty "
                "when final_verdict is APPROVED"
            )
        _require_nonempty_list_items(
            self.completed_acceptance_criteria,
            "CloseoutPacket (APPROVED)",
            "completed_acceptance_criteria",
        )
        if not self.final_test_evidence:
            raise ValueError(
                "CloseoutPacket.final_test_evidence must be non-empty when "
                "final_verdict is APPROVED"
            )
        for evidence in self.final_test_evidence:
            # TestEvidence.outcome is restricted to passed/failed/timeout
            # (see TEST_EVIDENCE_OUTCOMES). "timeout" is the only
            # inconclusive outcome representable in this contract — an
            # inconclusive result must never support an APPROVED closeout.
            if evidence.outcome not in ("passed", "failed"):
                raise ValueError(
                    "CloseoutPacket.final_test_evidence must not contain a "
                    f"{evidence.outcome!r} outcome when final_verdict is APPROVED "
                    "— an inconclusive result cannot support approval"
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
