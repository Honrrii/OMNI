"""Immutable evidence contracts for the deterministic TestCube arbiter.

Collectors, not candidate agents, must supply these records. Validation checks
structure and identity; it cannot authenticate a measurement's origin.
"""
from __future__ import annotations

import json
import math
import re
from dataclasses import asdict, dataclass, field
from decimal import Decimal

from omni.autodev.packets import TestEvidence
from omni.autodev.protected_paths import (
    GLOB_METACHARACTERS,
    normalize_repo_relative_path,
)

VERDICTS = (
    "CANDIDATE_A_PREFERRED",
    "CANDIDATE_B_PREFERRED",
    "NO_VALID_CANDIDATE",
    "EVIDENCE_INCONCLUSIVE",
)
CORE_CHECKS = ("patch.apply", "git.diff_check", "build", "safety", "operations")
DIRECTIONS = ("lower", "higher")
_IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]*\Z")
_NUMBER = re.compile(r"-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?\Z")


def _text(value: str, name: str) -> None:
    if type(value) is not str or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")


def _identifier(value: str, name: str) -> None:
    _text(value, name)
    if not _IDENTIFIER.fullmatch(value):
        raise ValueError(f"{name} must be an ASCII identifier without whitespace")


def _count(value: int, name: str) -> None:
    if type(value) is not int or value < 0:
        raise ValueError(f"{name} must be a non-negative integer")


def _tuple(value: tuple, item_type: type, name: str) -> None:
    if type(value) is not tuple or any(type(item) is not item_type for item in value):
        raise ValueError(f"{name} must be a tuple of {item_type.__name__} records")


def _unique(values: tuple, name: str) -> None:
    if len(set(values)) != len(values):
        raise ValueError(f"duplicate {name}")


def _paths(values: tuple[str, ...], name: str, *, specs: bool = False) -> tuple[str, ...]:
    _tuple(values, str, name)
    normalized = []
    for value in values:
        if value != value.strip() or any(ord(char) < 32 or ord(char) == 127 for char in value):
            raise ValueError(f"{name} contains an ambiguous path")
        if not specs and any(char in value for char in GLOB_METACHARACTERS):
            raise ValueError(f"{name} must contain concrete paths, not globs")
        normalized.append(normalize_repo_relative_path(value))
    _unique(tuple(normalized), name)
    return tuple(sorted(normalized))


@dataclass(frozen=True)
class EvidenceIdentity:
    """Bind every observation to one evaluation, candidate slot, and patch."""

    evaluation_id: str
    candidate_id: str
    patch_ref: str

    def __post_init__(self) -> None:
        _identifier(self.evaluation_id, "evaluation_id")
        if type(self.candidate_id) is not str or self.candidate_id not in ("A", "B"):
            raise ValueError("candidate_id must be exactly A or B")
        _text(self.patch_ref, "patch_ref")


@dataclass(frozen=True)
class CheckEvidence:
    """A recorded command, never a command to execute.

    Exit code zero is success. Timeout/error has no exit code and cannot pass.
    Counts and duration are optional observations, not comparative scores.
    """

    identity: EvidenceIdentity
    check_id: str
    command: str
    exit_code: int | None
    evidence_ref: str
    outcome: str = "completed"
    passed: int | None = None
    failed: int | None = None
    skipped: int | None = None
    duration_seconds: float | int | None = None

    def __post_init__(self) -> None:
        if type(self.identity) is not EvidenceIdentity:
            raise ValueError("check identity must be EvidenceIdentity")
        _identifier(self.check_id, "check_id")
        if self.check_id not in CORE_CHECKS and not any(
            self.check_id.startswith(prefix) and len(self.check_id) > len(prefix)
            for prefix in ("test:", "validator:", "static:")
        ):
            raise ValueError("unknown check_id: use a core check or test:/validator:/static: name")
        _text(self.command, "command")
        _text(self.evidence_ref, "evidence_ref")
        if self.outcome not in ("completed", "timeout", "error"):
            raise ValueError("outcome must be completed, timeout, or error")
        if self.outcome == "completed":
            if type(self.exit_code) is not int:
                raise ValueError("completed check must carry an integer exit_code")
        elif self.exit_code is not None:
            raise ValueError("timeout/error check must not carry an exit_code")
        for name in ("passed", "failed", "skipped"):
            value = getattr(self, name)
            if value is not None:
                _count(value, name)
        if self.exit_code == 0 and self.failed not in (None, 0):
            raise ValueError("zero exit_code contradicts failed test count")
        duration = self.duration_seconds
        if duration is not None and (
            type(duration) not in (int, float)
            or duration < 0
            or (type(duration) is float and not math.isfinite(duration))
        ):
            raise ValueError("duration_seconds must be finite and non-negative")

    @property
    def succeeded(self) -> bool:
        return self.outcome == "completed" and self.exit_code == 0

    @classmethod
    def from_test_evidence(
        cls, record: TestEvidence, *, identity: EvidenceIdentity,
        check_id: str, evidence_ref: str,
    ) -> CheckEvidence:
        """Snapshot the existing mutable Auto Dev record, excluding its prose.

        Legacy TestEvidence does not enforce passed/failed versus exit code;
        this adapter rejects contradictions before crossing the arbiter boundary.
        """
        if type(record) is not TestEvidence:
            raise ValueError("record must be Auto Dev TestEvidence")
        if record.outcome not in ("passed", "failed", "timeout"):
            raise ValueError("unknown TestEvidence outcome")
        if record.outcome == "passed" and (type(record.exit_code) is not int or record.exit_code != 0):
            raise ValueError("passed TestEvidence requires exit_code zero")
        if record.outcome == "failed" and (type(record.exit_code) is not int or record.exit_code == 0):
            raise ValueError("failed TestEvidence requires a nonzero exit_code")
        return cls(
            identity=identity, check_id=check_id, command=record.command,
            exit_code=record.exit_code, evidence_ref=evidence_ref,
            outcome="timeout" if record.outcome == "timeout" else "completed",
        )


@dataclass(frozen=True)
class MetricSpec:
    """Policy-owned metric identity, unit, direction, and measurement protocol.

    context_id identifies the workload, runner/environment, version, sampling,
    and aggregation protocol. No implicit unit conversion or noise threshold.
    """

    metric_id: str
    unit: str
    direction: str
    context_id: str

    def __post_init__(self) -> None:
        for name in ("metric_id", "unit", "context_id"):
            _identifier(getattr(self, name), name)
        if self.direction not in DIRECTIONS:
            raise ValueError("metric direction must be lower or higher")


@dataclass(frozen=True)
class Measurement:
    identity: EvidenceIdentity
    metric_id: str
    value: str | int | float
    unit: str
    context_id: str
    evidence_ref: str

    def __post_init__(self) -> None:
        if type(self.identity) is not EvidenceIdentity:
            raise ValueError("measurement identity must be EvidenceIdentity")
        for name in ("metric_id", "unit", "context_id"):
            _identifier(getattr(self, name), name)
        _text(self.evidence_ref, "evidence_ref")
        if type(self.value) not in (str, int, float):
            raise ValueError("measurement value must be a finite decimal number")
        value = str(self.value)
        if not _NUMBER.fullmatch(value):
            raise ValueError("measurement value must be a finite decimal number")
        # Store decimal text for JSON. Comparisons use Decimal without any
        # arithmetic, so neither binary rounding nor decimal context is a vote.
        try:
            number = Decimal(value)
        except ArithmeticError as exc:
            raise ValueError("invalid decimal measurement") from exc
        if not number.is_finite():
            raise ValueError("measurement value must be finite")
        object.__setattr__(self, "value", str(number))


@dataclass(frozen=True)
class CandidatePolicy:
    evaluation_id: str
    allowed_paths: tuple[str, ...]
    required_test_groups: tuple[str, ...]
    forbidden_paths: tuple[str, ...] = ()
    required_validators: tuple[str, ...] = ()
    required_static_checks: tuple[str, ...] = ()
    metrics: tuple[MetricSpec, ...] = ()
    max_touched_files: int | None = None
    max_changed_lines: int | None = None
    allow_no_tests: bool = False

    def __post_init__(self) -> None:
        _identifier(self.evaluation_id, "evaluation_id")
        if type(self.allow_no_tests) is not bool:
            raise ValueError("allow_no_tests must be a bool")
        for name in ("allowed_paths", "forbidden_paths"):
            object.__setattr__(self, name, _paths(getattr(self, name), name, specs=True))
        if not self.allowed_paths:
            raise ValueError("allowed_paths must explicitly enumerate scope (use '*' for all)")
        for name in ("required_test_groups", "required_validators", "required_static_checks"):
            values = getattr(self, name)
            _tuple(values, str, name)
            for value in values:
                _identifier(value, name)
            _unique(values, name)
            object.__setattr__(self, name, tuple(sorted(values)))
        if not self.required_test_groups and not self.allow_no_tests:
            raise ValueError("required_test_groups is empty without explicit allow_no_tests")
        _tuple(self.metrics, MetricSpec, "metrics")
        _unique(tuple(metric.metric_id for metric in self.metrics), "policy metric IDs")
        object.__setattr__(self, "metrics", tuple(sorted(self.metrics, key=lambda metric: metric.metric_id)))
        for name in ("max_touched_files", "max_changed_lines"):
            value = getattr(self, name)
            if value is not None:
                _count(value, name)

    @property
    def required_check_ids(self) -> tuple[str, ...]:
        return CORE_CHECKS + tuple(sorted(
            tuple(f"test:{name}" for name in self.required_test_groups)
            + tuple(f"validator:{name}" for name in self.required_validators)
            + tuple(f"static:{name}" for name in self.required_static_checks)
        ))


@dataclass(frozen=True)
class CandidateEvidence:
    identity: EvidenceIdentity
    checks: tuple[CheckEvidence, ...] = ()
    measurements: tuple[Measurement, ...] = ()
    touched_files: tuple[str, ...] | None = None
    changed_lines: int | None = None
    violations: tuple[str, ...] = ()
    scope_evidence_ref: str | None = None

    def __post_init__(self) -> None:
        if type(self.identity) is not EvidenceIdentity:
            raise ValueError("candidate identity must be EvidenceIdentity")
        for name, record_type, key in (
            ("checks", CheckEvidence, "check_id"),
            ("measurements", Measurement, "metric_id"),
        ):
            values = getattr(self, name)
            _tuple(values, record_type, name)
            _unique(tuple(getattr(value, key) for value in values), name)
            for value in values:
                if value.identity != self.identity:
                    raise ValueError(f"{name} identity does not match candidate/patch/evaluation")
            object.__setattr__(self, name, tuple(sorted(values, key=lambda value: getattr(value, key))))
        if self.touched_files is not None:
            object.__setattr__(self, "touched_files", _paths(self.touched_files, "touched_files"))
        if self.changed_lines is not None:
            _count(self.changed_lines, "changed_lines")
        _tuple(self.violations, str, "violations")
        for violation in self.violations:
            _identifier(violation, "violation code")
        _unique(self.violations, "violation codes")
        object.__setattr__(self, "violations", tuple(sorted(self.violations)))
        if self.scope_evidence_ref is not None:
            _text(self.scope_evidence_ref, "scope_evidence_ref")


@dataclass(frozen=True)
class GateResult:
    candidate_id: str
    gate_id: str
    passed: bool
    reason: str
    evidence_refs: tuple[str, ...] = ()
    details: tuple[str, ...] = ()


@dataclass(frozen=True)
class MetricComparison:
    metric_id: str
    unit: str
    direction: str
    context_id: str
    a_value: str | None
    b_value: str | None
    relation: str
    reason: str
    evidence_refs: tuple[str, ...]


@dataclass(frozen=True)
class ArbitrationResult:
    verdict: str
    winning_candidate: str | None
    winning_artifact_ref: str | None
    policy: CandidatePolicy
    candidates: tuple[EvidenceIdentity, EvidenceIdentity]
    mandatory_gate_results: tuple[GateResult, ...]
    metric_comparisons: tuple[MetricComparison, ...]
    comparison_reasons: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    human_review_required: bool = field(default=True, init=False)
    schema_version: str = field(default="omni.testcube.arbitration.v1", init=False)

    def to_dict(self) -> dict:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True, allow_nan=False, indent=2) + "\n"


def candidate_evidence_from_dict(data: dict) -> CandidateEvidence:
    """Reconstruct a JSON-shaped record; unknown fields and bad records raise."""
    payload = dict(data)
    payload["identity"] = EvidenceIdentity(**payload["identity"])
    for name, record_type in (("checks", CheckEvidence), ("measurements", Measurement)):
        if type(payload.get(name, ())) not in (list, tuple):
            raise ValueError(f"{name} must be an array")
        records = []
        for item in payload.get(name, ()):
            record = dict(item)
            record["identity"] = EvidenceIdentity(**record["identity"])
            records.append(record_type(**record))
        payload[name] = tuple(records)
    for name in ("touched_files", "violations"):
        if name in payload and payload[name] is not None:
            if type(payload[name]) not in (list, tuple):
                raise ValueError(f"{name} must be an array")
            payload[name] = tuple(payload[name])
    return CandidateEvidence(**payload)


def candidate_policy_from_dict(data: dict) -> CandidatePolicy:
    payload = dict(data)
    for name in (
        "allowed_paths", "forbidden_paths", "required_test_groups",
        "required_validators", "required_static_checks", "metrics",
    ):
        if name in payload:
            if type(payload[name]) not in (list, tuple):
                raise ValueError(f"{name} must be an array")
            payload[name] = tuple(payload[name])
    payload["metrics"] = tuple(MetricSpec(**item) for item in payload.get("metrics", ()))
    return CandidatePolicy(**payload)
