"""Human-owned contracts for the supervised, correctness-only first trial."""
from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import math

from omni.autodev.protected_paths import match_protected_path, spec_matches
from omni.testcube.collector_models import CollectorPolicy, canonical_bytes, digest
from omni.testcube.models import _identifier, _paths, _text, _tuple, _unique

CANDIDATE_SCHEMA = "omni.testcube.candidate.v1"
EDIT_SCHEMA = "omni.testcube.candidate-edit.v1"
MAX_PROPOSAL_BYTES = 128 * 1024
MAX_EDITS = 16
MAX_EDIT_TEXT_BYTES = 16 * 1024
MAX_TOTAL_EDIT_BYTES = 64 * 1024
TRIAL_SCHEMA = "omni.testcube.trial.v1"
TRIAL_OUTCOMES = ("GENERATION_FAILED", "COLLECTION_FAILED", "TRIAL_COMPLETE")
HIGH_RISK_CATEGORIES = (
    "benchmark_comparison", "safety_policy_redesign", "credential_auth_changes",
    "ci_secret_changes", "deployment", "dependency_upgrades", "large_refactor",
    "schema_migration", "destructive_data_changes",
)
# Concrete file scope only. The human also classifies the requested operation;
# these path guards do not pretend to infer intent from natural language.
FIRST_TRIAL_FORBIDDEN = (
    ".*", "**/.*", "tests/**", "**/conftest.py", "**/test_*.py", "test_*.py",
    "omni/testcube/**", "omni/frontier/**", "omni/autodev/**", "agents/**",
    "scripts/**", "**/*auth*", "**/*credential*", "**/*secret*", "**/*safety*",
    "**/*pluto*", "**/*deploy*", "**/*migration*", "**/*schema*", "**/*policy*",
    "*auth*", "*credential*", "*secret*", "*safety*", "*deploy*", "*migration*",
    "*schema*", "*policy*", "setup.py", "**/setup.py",
)


def strict_json(raw: bytes | str):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("duplicate JSON key")
            result[key] = value
        return result

    def constant(_):
        raise ValueError("nonfinite JSON value")

    def finite_float(value):
        number = float(value)
        if not math.isfinite(number):
            raise ValueError("nonfinite JSON value")
        return number

    return json.loads(raw, object_pairs_hook=pairs, parse_constant=constant, parse_float=finite_float)


@dataclass(frozen=True)
class CandidateTaskSpec:
    task_id: str
    title: str
    objective: str
    acceptance_criteria: tuple[str, ...]
    allowed_paths: tuple[str, ...]
    forbidden_paths: tuple[str, ...]
    required_tests: tuple[str, ...]
    required_validators: tuple[str, ...]
    validation_paths: tuple[str, ...]
    base_revision: str
    change_kind: str = "small_bugfix"
    risk_categories: tuple[str, ...] = ()
    max_touched_files: int = 3
    max_changed_lines: int = 100

    def __post_init__(self):
        _identifier(self.task_id, "task_id")
        for name in ("title", "objective", "base_revision"):
            _text(getattr(self, name), name)
        if self.base_revision.startswith("-") or "\0" in self.base_revision:
            raise ValueError("invalid base revision")
        for name in ("acceptance_criteria", "required_tests", "required_validators", "risk_categories"):
            values = getattr(self, name)
            _tuple(values, str, name)
            _unique(values, name)
            for value in values:
                _text(value, name)
            if name in ("required_tests", "required_validators"):
                for value in values:
                    _identifier(value, name)
                object.__setattr__(self, name, tuple(sorted(values)))
        if not self.acceptance_criteria or not self.required_tests or not self.validation_paths:
            raise ValueError("criteria, required tests and protected validation paths are mandatory")
        for name in ("allowed_paths", "validation_paths", "forbidden_paths"):
            object.__setattr__(self, name, _paths(getattr(self, name), name, specs=name == "forbidden_paths"))
        if self.change_kind != "small_bugfix" or self.risk_categories:
            raise ValueError("first trial permits only human-classified small bug fixes without high-risk operations")
        if not self.allowed_paths or len(self.allowed_paths) > 3:
            raise ValueError("first trial requires 1..3 concrete allowed files")
        for path in self.allowed_paths:
            if (not path.endswith(".py") or match_protected_path(path) or
                any(spec_matches(rule, path.lower()) for rule in FIRST_TRIAL_FORBIDDEN) or
                any(spec_matches(rule, path) for rule in self.forbidden_paths) or
                path in self.validation_paths):
                raise ValueError("file is ineligible for a first trial")
        for name, maximum in (("max_touched_files", 3), ("max_changed_lines", 100)):
            if type(getattr(self, name)) is not int or not 1 <= getattr(self, name) <= maximum:
                raise ValueError(f"{name} exceeds first-trial bounds")
        if len(canonical_bytes(asdict(self))) > 128 * 1024:
            raise ValueError("task specification too large")

    @property
    def sha256(self):
        return digest(canonical_bytes(asdict(self)))

    def validate_policy(self, policy: CollectorPolicy):
        p = policy.candidate_policy
        if p.metrics or policy.benchmarks:
            raise ValueError("first-trial comparative metrics and benchmarks are disabled")
        if policy.max_patch_bytes > 128 * 1024:
            raise ValueError("first-trial patch limit must not exceed 128 KiB")
        if (p.evaluation_id != self.task_id or p.allowed_paths != self.allowed_paths or
            p.forbidden_paths != self.forbidden_paths or p.required_test_groups != self.required_tests or
            p.required_validators != self.required_validators or policy.base_revision != self.base_revision or
            p.max_touched_files != self.max_touched_files or p.max_changed_lines != self.max_changed_lines):
            raise ValueError("task and collector policy disagree")
        if set(p.required_check_ids) - {"patch.apply", "git.diff_check", "safety", "operations"} != {c.check_id for c in policy.commands}:
            raise ValueError("every required trusted command must be configured before generation")
        if any(not any(spec_matches(rule, path) for rule in self.forbidden_paths) for path in self.validation_paths):
            raise ValueError("validation paths must be explicitly forbidden to candidates")


def task_from_dict(data):
    data = dict(data)
    for name in ("acceptance_criteria", "allowed_paths", "forbidden_paths", "required_tests",
                 "required_validators", "validation_paths", "risk_categories"):
        if name in data:
            if type(data[name]) is not list:
                raise ValueError("task arrays must be JSON lists")
            data[name] = tuple(data[name])
    return CandidateTaskSpec(**data)


def candidate_schema(transport=CANDIDATE_SCHEMA):
    properties = {
        "schema_version": {"type": "string", "enum": [CANDIDATE_SCHEMA]},
        "summary": {"type": "string"}, "patch": {"type": "string", "minLength": 1},
        "assumptions": {"type": "array", "items": {"type": "string"}},
        "limitations": {"type": "array", "items": {"type": "string"}},
    }
    if transport == EDIT_SCHEMA:
        properties["schema_version"]["enum"] = [EDIT_SCHEMA]
        del properties["patch"]
        properties["edits"] = {
            "type": "array", "minItems": 1, "maxItems": MAX_EDITS,
            "items": {"type": "object", "additionalProperties": False,
                      "required": ["path", "before", "after"],
                      "properties": {"path": {"type": "string", "minLength": 1},
                                     "before": {"type": "string", "minLength": 1, "maxLength": MAX_EDIT_TEXT_BYTES},
                                     "after": {"type": "string", "maxLength": MAX_EDIT_TEXT_BYTES}}},
        }
    elif transport != CANDIDATE_SCHEMA:
        raise ValueError("unknown candidate transport")
    return {"type": "object", "additionalProperties": False,
            "properties": properties, "required": list(properties)}


def validate_edit_proposal(data) -> bytes:
    """Validate exactly one version; return the canonical audit proposal.

    Path authority and original-base matching are independently enforced by
    the renderer. JSON whitespace/envelope size is bounded before decoding.
    """
    if type(data) is not dict or set(data) != set(candidate_schema(EDIT_SCHEMA)["properties"]):
        raise ValueError("proposal fields do not match strict schema")
    if data["schema_version"] != EDIT_SCHEMA or type(data["summary"]) is not str:
        raise ValueError("invalid proposal schema/version")
    for name in ("assumptions", "limitations"):
        if type(data[name]) is not list or any(type(item) is not str for item in data[name]):
            raise ValueError("invalid proposal audit context")
    for text in [data["summary"], *data["assumptions"], *data["limitations"]]:
        text.encode("utf-8", errors="strict")
        if "\0" in text:
            raise ValueError("NUL-containing proposal context")
    edits = data["edits"]
    if type(edits) is not list or not 1 <= len(edits) <= MAX_EDITS:
        raise ValueError("edit count exceeds bounds")
    seen, totals = set(), [0, 0]
    for edit in edits:
        if (type(edit) is not dict or set(edit) != {"path", "before", "after"} or
            any(type(value) is not str or "\0" in value for value in edit.values())):
            raise ValueError("invalid edit fields/types or NUL")
        edit["path"].encode("utf-8", errors="strict")
        if not edit["path"] or not edit["before"]:
            raise ValueError("empty path or before text")
        key = (edit["path"], edit["before"], edit["after"])
        if key in seen:
            raise ValueError("duplicate edit")
        seen.add(key)
        for index, name in enumerate(("before", "after")):
            size = len(edit[name].encode("utf-8", errors="strict"))
            totals[index] += size
            if size > MAX_EDIT_TEXT_BYTES or totals[index] > MAX_TOTAL_EDIT_BYTES:
                raise ValueError("edit text exceeds byte bounds")
    proposal = canonical_bytes(data | {"edits": sorted(edits, key=lambda e: (e["path"], e["before"], e["after"]))})
    if len(proposal) > MAX_PROPOSAL_BYTES:
        raise ValueError("oversized proposal")
    return proposal


def validate_candidate(data, max_patch_bytes: int) -> bytes:
    if type(data) is not dict or set(data) != set(candidate_schema()["properties"]):
        raise ValueError("candidate fields do not match strict schema")
    if data["schema_version"] != CANDIDATE_SCHEMA or type(data["summary"]) is not str:
        raise ValueError("invalid candidate schema/version")
    for name in ("assumptions", "limitations"):
        if type(data[name]) is not list or any(type(item) is not str for item in data[name]):
            raise ValueError("invalid candidate audit context")
    if type(data["patch"]) is not str:
        raise ValueError("patch must be text")
    patch = data["patch"].encode("utf-8", errors="strict")
    if not patch.startswith(b"diff --git ") or b"\0" in patch or len(patch) > max_patch_bytes:
        raise ValueError("unsupported, empty, NUL-containing or oversized patch")
    return patch


@dataclass(frozen=True)
class TrialReceipt:
    trial_path: str
    manifest_sha256: str


@dataclass(frozen=True)
class TrialResult:
    outcome: str
    receipt: TrialReceipt | None = None
    collection: object | None = None
    error: str = ""

    def __post_init__(self):
        if self.outcome not in TRIAL_OUTCOMES:
            raise ValueError("invalid trial outcome")
        arbitration = getattr(self.collection, "arbitration", None)
        if self.outcome == "TRIAL_COMPLETE":
            if type(self.receipt) is not TrialReceipt or arbitration is None or self.error:
                raise ValueError("complete trial requires durable receipt and arbitration without errors")
        elif arbitration is not None:
            raise ValueError("failed trial cannot return a recommendation")
