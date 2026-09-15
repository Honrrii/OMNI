"""Strict immutable records. Deserializing a decision confers no authority."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import re

from omni.testcube.candidate_models import CandidateTaskSpec, task_from_dict
from omni.testcube.collector_models import CollectorPolicy, CommandSpec
from omni.testcube.models import candidate_policy_from_dict
from backend.app.sandbox.resource_policy import ResourceLimits

SCHEMA = "omni.superbuild.v0"
POLICY = "human-terminal-acceptance;manual-external-promotion"
TRANSITIONS = {
    "PENDING": ("READY", "ABORTED"),
    "READY": ("GENERATING", "ABORTED"),
    "GENERATING": ("EVALUATING", "GENERATION_FAILED", "ABORTED"),
    "EVALUATING": ("AWAITING_HUMAN_DECISION", "EVIDENCE_FAILED", "ABORTED"),
    "AWAITING_HUMAN_DECISION": ("ACCEPTED", "REJECTED", "ABORTED"),
    "ACCEPTED": (), "REJECTED": (), "ABORTED": (),
    "GENERATION_FAILED": (), "EVIDENCE_FAILED": (),
}
TERMINAL = frozenset(k for k, v in TRANSITIONS.items() if not v)


def require(ok, message):
    if not ok:
        raise ValueError(message)


def identifier(value):
    require(type(value) is str and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,79}", value), "invalid identifier")


def sha(value, length=64):
    require(type(value) is str and re.fullmatch(r"[0-9a-f]{%d}" % length, value), "invalid digest/commit")


def text(value):
    require(type(value) is str and value.strip() and not any(ord(c) < 32 for c in value), "invalid text")


def timestamp(value):
    text(value)
    require(value.endswith("+00:00") and datetime.fromisoformat(value).utcoffset().total_seconds() == 0,
            "timestamp must be UTC")


def transition(old, new):
    require(type(old) is str and type(new) is str and new in TRANSITIONS.get(old, ()),
            f"invalid transition: {old} -> {new}")


@dataclass(frozen=True)
class SuperBuildProject:
    project_id: str
    title: str
    description: str
    trusted_source_commit: str
    trusted_source_path: str
    workspace_path: str
    created_at: str
    workspace_config_digest: str
    policy: str = POLICY
    schema_version: str = SCHEMA

    def __post_init__(self):
        identifier(self.project_id)
        text(self.title)
        text(self.description)
        sha(self.trusted_source_commit, 40)
        sha(self.workspace_config_digest)
        timestamp(self.created_at)
        require(self.policy == POLICY and self.schema_version == SCHEMA, "unsupported project policy/schema")
        for path in (self.trusted_source_path, self.workspace_path):
            require(type(path) is str and Path(path).is_absolute(), "absolute workspace/source required")

    @property
    def origin_commit(self):
        return self.trusted_source_commit


@dataclass(frozen=True)
class SuperBuildWorkItem:
    project_id: str
    work_item_id: str
    parent_checkpoint: str
    parent_accepted_commit: str
    task: CandidateTaskSpec
    collector_policy: CollectorPolicy
    status: str = "PENDING"

    def __post_init__(self):
        identifier(self.project_id)
        identifier(self.work_item_id)
        sha(self.parent_checkpoint)
        sha(self.parent_accepted_commit, 40)
        require(type(self.task) is CandidateTaskSpec and type(self.collector_policy) is CollectorPolicy,
                "trusted task/policy records required")
        self.task.validate_policy(self.collector_policy)
        require(not any(p.startswith("omni/superbuild/") for p in self.task.allowed_paths),
                "Super-Build control plane is outside candidate scope")
        require(self.task.task_id == self.work_item_id and self.task.base_revision == self.parent_accepted_commit,
                "task identity/parent mismatch")
        require(type(self.status) is str and self.status in TRANSITIONS, "invalid work status")


@dataclass(frozen=True)
class SuperBuildDecision:
    project_id: str
    work_item_id: str
    parent_checkpoint: str
    parent_accepted_commit: str
    evidence_digest: str
    decision: str
    selected_candidate: str | None
    candidate_digest: str | None
    patch_digest: str | None
    operator: str
    timestamp: str
    authority: str = "human-terminal"

    def __post_init__(self):
        identifier(self.project_id)
        identifier(self.work_item_id)
        for value in (self.parent_checkpoint, self.evidence_digest):
            sha(value)
        sha(self.parent_accepted_commit, 40)
        text(self.operator)
        timestamp(self.timestamp)
        require(self.authority == "human-terminal", "model decisions are not authoritative")
        require(type(self.decision) is str and self.decision in ("ACCEPT_A", "ACCEPT_B", "REJECT_BOTH", "DEFER"),
                "invalid decision")
        slot = self.decision[-1] if self.decision.startswith("ACCEPT_") else None
        require(self.selected_candidate == slot, "decision/slot mismatch")
        if slot:
            sha(self.candidate_digest)
            sha(self.patch_digest)
        else:
            require(self.candidate_digest is None and self.patch_digest is None, "nonacceptance cannot select artifacts")


@dataclass(frozen=True)
class SuperBuildCheckpoint:
    project_id: str
    work_item_id: str
    parent_checkpoint: str
    parent_accepted_commit: str
    accepted_project_commit: str
    candidate_slot: str
    candidate_digest: str
    patch_digest: str
    evidence_digest: str
    decision_digest: str

    def __post_init__(self):
        identifier(self.project_id)
        identifier(self.work_item_id)
        for value in (self.parent_checkpoint, self.candidate_digest, self.patch_digest,
                      self.evidence_digest, self.decision_digest):
            sha(value)
        for value in (self.parent_accepted_commit, self.accepted_project_commit):
            sha(value, 40)
        require(self.candidate_slot in ("A", "B"), "invalid candidate slot")


@dataclass(frozen=True)
class SuperBuildState:
    project_id: str
    origin_commit: str
    accepted_project_commit: str
    accepted_checkpoint: str
    work_items: tuple[SuperBuildWorkItem, ...]
    checkpoints: tuple[SuperBuildCheckpoint, ...]
    decisions: tuple[SuperBuildDecision, ...]

    def __post_init__(self):
        identifier(self.project_id)
        sha(self.origin_commit, 40)
        sha(self.accepted_project_commit, 40)
        sha(self.accepted_checkpoint)
        for values, cls in ((self.work_items, SuperBuildWorkItem), (self.checkpoints, SuperBuildCheckpoint),
                            (self.decisions, SuperBuildDecision)):
            require(type(values) is tuple and all(type(v) is cls and v.project_id == self.project_id for v in values),
                    "invalid state records")
        require(len({w.work_item_id for w in self.work_items}) == len(self.work_items), "duplicate work item")
        require(sum(w.status not in TERMINAL for w in self.work_items) <= 1, "one active work item required")


def policy_from_dict(data):
    data = dict(data)
    data["candidate_policy"] = candidate_policy_from_dict(data["candidate_policy"])
    data["commands"] = tuple(CommandSpec(**(c | {"argv": tuple(c["argv"])})) for c in data["commands"])
    require(data["benchmarks"] == [], "benchmarks are outside v0 scope")
    data["benchmarks"] = ()
    data["resource_limits"] = ResourceLimits(**data["resource_limits"])
    return CollectorPolicy(**data)


def work_from_dict(data):
    return SuperBuildWorkItem(**(data | {"task": task_from_dict(data["task"]),
        "collector_policy": policy_from_dict(data["collector_policy"])}))
