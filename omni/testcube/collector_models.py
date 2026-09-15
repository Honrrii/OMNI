"""Trusted, immutable configuration for TestCube evidence collection."""
from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path

from backend.app.sandbox.resource_policy import ResourceLimits
from omni.testcube.models import CandidatePolicy, CORE_CHECKS, _identifier, _tuple, _unique

COLLECTOR_OUTCOMES = ("EVIDENCE_COMPLETE", "CANDIDATE_INVALID", "COLLECTION_FAILED")


def canonical_bytes(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, allow_nan=False, indent=2) + "\n").encode("utf-8")


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


@dataclass(frozen=True)
class CommandSpec:
    check_id: str
    argv: tuple[str, ...]
    timeout_seconds: float = 30.0
    output_limit_bytes: int = 128 * 1024

    def __post_init__(self) -> None:
        _identifier(self.check_id, "check_id")
        _tuple(self.argv, str, "argv")
        if not self.argv or any(not arg or "\0" in arg for arg in self.argv):
            raise ValueError("argv must be nonempty, with nonempty NUL-free arguments")
        if not self.argv[0].startswith(("/usr/bin/", "/runtime/bin/")):
            raise ValueError("executable must be in trusted /usr/bin or /runtime/bin")
        if ".." in Path(self.argv[0]).parts:
            raise ValueError("executable must not traverse paths")
        if type(self.timeout_seconds) not in (int, float) or not math.isfinite(self.timeout_seconds) or not 0 < self.timeout_seconds <= 3600:
            raise ValueError("timeout_seconds must be finite, positive, and <= 3600")
        if type(self.output_limit_bytes) is not int or not 1 <= self.output_limit_bytes <= 8 * 1024 * 1024:
            raise ValueError("output_limit_bytes must be within 1..8388608")


@dataclass(frozen=True)
class BenchmarkSpec:
    """Parent-measured elapsed time, median of an odd number of fresh runs."""

    metric_id: str
    command: CommandSpec
    samples: int = 3

    def __post_init__(self) -> None:
        _identifier(self.metric_id, "metric_id")
        if type(self.command) is not CommandSpec:
            raise ValueError("benchmark command must be CommandSpec")
        if type(self.samples) is not int or self.samples not in (1, 3, 5, 7, 9):
            raise ValueError("samples must be one of 1, 3, 5, 7, 9")


@dataclass(frozen=True)
class CollectorPolicy:
    candidate_policy: CandidatePolicy
    base_revision: str
    runtime_root: str
    commands: tuple[CommandSpec, ...]
    benchmarks: tuple[BenchmarkSpec, ...] = ()
    max_patch_bytes: int = 2 * 1024 * 1024
    git_timeout_seconds: int = 60
    git_output_limit_bytes: int = 8 * 1024 * 1024
    resource_limits: ResourceLimits = ResourceLimits(
        cpu_seconds=60, address_space_bytes=2 * 1024**3,
        file_size_bytes=64 * 1024**2, open_files=256,
    )

    def __post_init__(self) -> None:
        if type(self.candidate_policy) is not CandidatePolicy:
            raise ValueError("candidate_policy must be CandidatePolicy")
        if type(self.base_revision) is not str or not self.base_revision or self.base_revision.startswith("-") or "\0" in self.base_revision:
            raise ValueError("base_revision must be an explicit Git revision")
        if type(self.runtime_root) is not str or not Path(self.runtime_root).is_absolute():
            raise ValueError("runtime_root must be an absolute trusted virtualenv directory")
        _tuple(self.commands, CommandSpec, "commands")
        _unique(tuple(command.check_id for command in self.commands), "command IDs")
        required = self.candidate_policy.required_check_ids
        for command in self.commands:
            if command.check_id not in required or command.check_id in set(CORE_CHECKS) - {"build"}:
                raise ValueError("commands may implement only configured build/test/validator/static checks")
        object.__setattr__(self, "commands", tuple(sorted(self.commands, key=lambda command: command.check_id)))
        _tuple(self.benchmarks, BenchmarkSpec, "benchmarks")
        _unique(tuple(spec.metric_id for spec in self.benchmarks), "benchmark IDs")
        metrics = {spec.metric_id: spec for spec in self.candidate_policy.metrics}
        for benchmark in self.benchmarks:
            spec = metrics.get(benchmark.metric_id)
            if spec is None or spec.direction != "lower" or spec.unit != "ms":
                raise ValueError("collector benchmarks require a configured lower-is-better metric in ms")
        object.__setattr__(self, "benchmarks", tuple(sorted(self.benchmarks, key=lambda spec: spec.metric_id)))
        for name, maximum in (("max_patch_bytes", 16 * 1024**2),
                              ("git_output_limit_bytes", 64 * 1024**2), ("git_timeout_seconds", 600)):
            value = getattr(self, name)
            if type(value) is not int or not 1 <= value <= maximum:
                raise ValueError(f"{name} must be within 1..{maximum}")
        if type(self.resource_limits) is not ResourceLimits:
            raise ValueError("resource_limits must be ResourceLimits")
        limits = self.resource_limits
        if any(getattr(limits, name) is None or getattr(limits, name) <= 0 for name in
               ("cpu_seconds", "address_space_bytes", "file_size_bytes", "open_files")):
            raise ValueError("CPU, address-space, file-size and descriptor limits are mandatory")
        if limits.process_count is not None or limits.core_size_bytes != 0:
            raise ValueError("process_count is unsupported; core dumps must be disabled")

    def to_dict(self) -> dict:
        return asdict(self)

    @property
    def sha256(self) -> str:
        return digest(canonical_bytes(self.to_dict()))


@dataclass(frozen=True)
class CollectionReceipt:
    """Retain outside the bundle: hash verification is not a digital signature."""

    bundle_path: str
    manifest_sha256: str
    evaluation_id: str
    base_revision: str
    policy_sha256: str
    patch_sha256: tuple[str, str]


@dataclass(frozen=True)
class CollectionResult:
    outcome: str
    receipt: CollectionReceipt | None
    arbitration: object | None
    errors: tuple[str, ...] = ()
