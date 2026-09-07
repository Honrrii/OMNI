"""Trusted patch collection; no model, branch promotion, or candidate claims.

Detached copies have independent object stores and indexes. Candidate commands
see only read-only source/runtime mounts and disposable private scratch space.
"""
from __future__ import annotations

import json
import os
import platform
import re
import shutil
import stat
import sys
import time
from dataclasses import asdict, replace
from pathlib import Path

from backend.app.sandbox.execution import run_command
from omni.autodev.protected_paths import normalize_repo_relative_path, spec_matches
from omni.testcube.arbiter import evaluate
from omni.testcube.collector_models import (
    CollectionReceipt, CollectionResult, CollectorPolicy, CommandSpec,
    canonical_bytes, digest,
)
from omni.testcube.isolated_runner import CollectionError, run_isolated, write_new
from omni.testcube.models import (
    CandidateEvidence, CheckEvidence, EvidenceIdentity, Measurement,
    candidate_evidence_from_dict,
)

COLLECTOR_VERSION = "omni.testcube.collector.v1"
_FULL_SHA = re.compile(r"(?:[0-9a-f]{40}|[0-9a-f]{64})\Z")
_GIT_ENV = {
    "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": "/dev/null",
    "GIT_TERMINAL_PROMPT": "0", "GIT_NO_REPLACE_OBJECTS": "1",
    "GIT_ALLOW_PROTOCOL": "file", "GIT_OPTIONAL_LOCKS": "0",
}


def _read_regular(path: Path, limit: int, *, sync: bool = False) -> bytes:
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, "rb") as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_size > limit:
            raise CollectionError("artifact must be a bounded regular file")
        data = stream.read(limit + 1)
        if len(data) > limit:
            raise CollectionError("artifact exceeds configured limit")
        if sync:
            os.fsync(stream.fileno())
        return data


class _Git:
    def __init__(self, policy: CollectorPolicy, bundle: Path):
        self.policy = policy
        self.bundle = bundle
        self.sequence = 0

    def run(self, cwd: Path, *args: str, required: bool = True):
        self.sequence += 1
        argv = [
            "/usr/bin/git", "--no-optional-locks", "-c", "core.hooksPath=/dev/null",
            "-c", "core.fsmonitor=false", "-c", "core.autocrlf=false",
            "-c", "core.attributesFile=/dev/null", *args,
        ]
        start = time.perf_counter_ns()
        result = run_command(
            argv, cwd=cwd, env=_GIT_ENV, timeout=self.policy.git_timeout_seconds,
            max_output_bytes=self.policy.git_output_limit_bytes,
        )
        elapsed = time.perf_counter_ns() - start
        ref = f"git/command-{self.sequence:04d}.json"
        write_new(self.bundle / ref, canonical_bytes(result.to_dict() | {
            "cwd": str(cwd), "duration_ns": elapsed,
        }))
        if result.timed_out or result.output_limit_exceeded or result.launcher_error:
            raise CollectionError(f"Git observation incomplete: {ref}")
        if required and result.returncode != 0:
            raise CollectionError(f"Git operation failed: {ref}")
        return result, ref, elapsed

    def text(self, cwd: Path, *args: str) -> str:
        return self.run(cwd, *args)[0].stdout


def _source_snapshot(repo: Path, git: _Git) -> dict:
    git_dir = Path(git.text(repo, "rev-parse", "--absolute-git-dir").strip())
    # Do not archive configuration/remotes or the index itself: hash their
    # bytes. These may contain private URLs or other operator-owned metadata.
    metadata = {}
    for name in ("HEAD", "index", "config", "packed-refs"):
        path = git_dir / name
        metadata[name] = digest(_read_regular(path, 64 * 1024**2)) if path.exists() else None
    refs = git.text(repo, "for-each-ref", "--format=%(refname) %(objectname)")
    status = git.text(repo, "status", "--porcelain=v1", "-z", "--untracked-files=all")
    return {"head": git.text(repo, "rev-parse", "HEAD").strip(),
            "status_sha256": digest(status.encode()), "clean": not status,
            "refs_sha256": digest(refs.encode()), "metadata": metadata}


def _tree_modes(raw: str) -> tuple[str, ...]:
    unsupported = []
    for item in raw.split("\0"):
        if not item:
            continue
        metadata, path = item.split("\t", 1)
        mode = metadata.split()[0]
        if mode not in ("100644", "100755"):
            unsupported.append(path)
    return tuple(sorted(unsupported))


def _changes(worktree: Path, base: str, git: _Git) -> dict:
    raw = git.text(worktree, "diff", "--cached", "--no-ext-diff", "--no-textconv",
                   "--name-status", "-z", "--find-renames", "--find-copies-harder", base, "--")
    fields = raw.split("\0")
    if fields[-1] != "":
        raise CollectionError("Git changed-path output is incomplete")
    fields.pop()
    changes, paths = [], set()
    offset = 0
    while offset < len(fields):
        kind = fields[offset]
        count = 2 if kind.startswith(("R", "C")) else 1
        if not re.fullmatch(r"(?:[AMDT]|[RC][0-9]{1,3})", kind) or offset + count >= len(fields):
            raise CollectionError("unknown Git changed-path record")
        names = fields[offset + 1:offset + 1 + count]
        for name in names:
            # Reject lossy filename decoding and normalization; Git paths in
            # the evidence must name the actual files, not aliases.
            if "\ufffd" in name or normalize_repo_relative_path(name) != name:
                raise CollectionError("Git path cannot be represented without normalization loss")
            paths.add(name)
        changes.append({"status": kind, "paths": names})
        offset += count + 1
    numstat = git.text(worktree, "diff", "--cached", "--no-ext-diff", "--no-textconv",
                      "--no-renames", "--numstat", "-z", base, "--")
    if numstat and not numstat.endswith("\0"):
        raise CollectionError("Git line-count output is incomplete")
    lines = 0
    binary = []
    for record in numstat.split("\0"):
        if not record:
            continue
        added, deleted, path = record.split("\t", 2)
        if path not in paths:
            raise CollectionError("Git line-count path disagrees with changed-path inventory")
        if added == deleted == "-":
            binary.append(path)
        elif added.isascii() and added.isdigit() and deleted.isascii() and deleted.isdigit():
            lines += int(added) + int(deleted)
        else:
            raise CollectionError("malformed Git line count")
    return {"touched_files": sorted(paths), "changes": changes,
            "changed_lines": None if binary else lines, "binary_paths": sorted(binary),
            "line_count_protocol": "git-numstat-no-renames-additions-plus-deletions"}


def _scope_violations(changes: dict, policy: CollectorPolicy) -> tuple[str, ...]:
    p = policy.candidate_policy
    paths = changes["touched_files"]
    violations = []
    if any(not any(spec_matches(spec, path) for spec in p.allowed_paths) for path in paths):
        violations.append("outside-allowed-paths")
    if any(any(spec_matches(spec, path) for spec in p.forbidden_paths) for path in paths):
        violations.append("forbidden-path")
    if p.max_touched_files is not None and len(paths) > p.max_touched_files:
        violations.append("file-count-limit")
    if p.max_changed_lines is not None and (changes["changed_lines"] is None or changes["changed_lines"] > p.max_changed_lines):
        violations.append("line-count-incomplete-or-exceeded")
    return tuple(violations)


def _observed_check(identity: EvidenceIdentity, check_id: str, observed) -> CheckEvidence:
    return CheckEvidence(
        identity, check_id, json.dumps(observed.argv), observed.exit_code,
        observed.evidence_ref, observed.outcome, duration_seconds=observed.duration_ns / 1e9,
    )


def _audit(identity: EvidenceIdentity, check_id: str, passed: bool, details: dict, bundle: Path) -> CheckEvidence:
    ref = f"candidate-{identity.candidate_id}/{check_id}.json"
    write_new(bundle / ref, canonical_bytes({"identity": asdict(identity), "passed": passed, **details}))
    return CheckEvidence(identity, check_id, f"collector:{check_id}", 0 if passed else 1, ref)


def _collect_candidate(
    slot: str, worktree: Path, patch: bytes, patch_hash: str, base: str,
    policy: CollectorPolicy, bundle: Path, git: _Git,
) -> CandidateEvidence:
    identity = EvidenceIdentity(policy.candidate_policy.evaluation_id, slot,
                                f"testcube:{policy.candidate_policy.evaluation_id}:{base}:{patch_hash}")
    root = bundle / f"candidate-{slot}"
    patch_path = root / "patch.diff"
    write_new(patch_path, patch)
    write_new(root / "patch.sha256", (patch_hash + "\n").encode())
    checks = []
    if not patch.startswith(b"diff --git ") or b"\0" in patch:
        apply = _audit(identity, "patch.apply", False, {"reason": "unsupported-patch-format"}, bundle)
    else:
        result, ref, duration = git.run(worktree, "apply", "--index", "--binary",
                                        "--whitespace=nowarn", "--", str(patch_path), required=False)
        apply = CheckEvidence(identity, "patch.apply", json.dumps(result.command), result.returncode,
                              ref, duration_seconds=duration / 1e9)
    checks.append(apply)
    changes = _changes(worktree, base, git)
    scope_ref = f"candidate-{slot}/changed-paths.json"
    write_new(bundle / scope_ref, canonical_bytes(changes | {"identity": asdict(identity), "base_revision": base}))
    result, ref, duration = git.run(worktree, "diff", "--cached", "--check", base, "--", required=False)
    checks.append(CheckEvidence(identity, "git.diff_check", json.dumps(result.command), result.returncode,
                                ref, duration_seconds=duration / 1e9))
    # Validate concrete paths/counts through the approved evidence contract
    # before any candidate command can run (e.g. reject control chars/globs).
    candidate = CandidateEvidence(identity, tuple(checks), touched_files=tuple(changes["touched_files"]),
                                  changed_lines=changes["changed_lines"], scope_evidence_ref=scope_ref)
    violations = _scope_violations(changes, policy)
    unsupported = _tree_modes(git.text(worktree, "ls-files", "--stage", "-z"))
    if unsupported:
        violations += ("symlink-or-submodule",)
    # Source is read-only during commands. Check its full index tree plus Git
    # metadata before and after: candidate execution never gets a writable Git.
    index_tree = git.text(worktree, "write-tree").strip()
    before = _source_snapshot(worktree, git)
    checks.append(_audit(identity, "safety", not violations, {
        "violations": list(violations), "unsupported_paths": list(unsupported),
        "source_mount": "read-only", "git_metadata": "masked",
    }, bundle))
    if apply.succeeded and not violations:
        for command in policy.commands:
            observed = run_isolated(worktree, policy, command, bundle,
                                    f"candidate-{slot}/checks/{command.check_id}")
            checks.append(_observed_check(identity, command.check_id, observed))
    after = _source_snapshot(worktree, git)
    if before != after or git.text(worktree, "write-tree").strip() != index_tree:
        raise CollectionError("candidate checkout or Git metadata changed during execution")
    if git.text(worktree, "diff", "--name-only", "-z"):
        raise CollectionError("candidate tracked content changed during execution")
    checks.append(_audit(identity, "operations", True, {
        "mechanism": "bubblewrap-readonly-source-masked-git-private-pid-network-namespaces",
        "index_tree": index_tree, "checkout_unchanged": True,
        "candidate_commands_executed": apply.succeeded and not violations,
        "base_revision": base,
    }, bundle))
    return replace(candidate, checks=tuple(checks), violations=violations)


def _collect_benchmarks(candidates: list[CandidateEvidence], trees: list[Path], policy: CollectorPolicy, bundle: Path) -> list[CandidateEvidence]:
    metrics = {metric.metric_id: metric for metric in policy.candidate_policy.metrics}
    measurements = [[], []]
    for benchmark in policy.benchmarks:
        spec = metrics[benchmark.metric_id]
        samples = [[], []]
        eligible = [not candidate.violations and all(check.succeeded for check in candidate.checks)
                    and set(policy.candidate_policy.required_check_ids) <= {check.check_id for check in candidate.checks}
                    for candidate in candidates]
        for index in range(benchmark.samples):
            for slot, candidate in enumerate(candidates):
                if not eligible[slot]:
                    continue
                observation = run_isolated(trees[slot], policy, benchmark.command, bundle,
                    f"candidate-{candidate.identity.candidate_id}/benchmarks/{spec.metric_id}/sample-{index:02d}")
                samples[slot].append(observation)
        for slot, candidate in enumerate(candidates):
            observed = samples[slot]
            complete = len(observed) == benchmark.samples and all(item.outcome == "completed" and item.exit_code == 0 for item in observed)
            ref = f"candidate-{candidate.identity.candidate_id}/benchmarks/{spec.metric_id}/summary.json"
            write_new(bundle / ref, canonical_bytes({
                "identity": asdict(candidate.identity), "spec": asdict(spec),
                "protocol": asdict(benchmark), "complete": complete,
                "samples": [asdict(item) for item in observed],
                "measurement_source": "collector-perf-counter-ns-including-isolation-overhead",
            }))
            if complete:
                duration = sorted(item.duration_ns for item in observed)[len(observed) // 2]
                value = f"{duration // 1000000}.{duration % 1000000:06d}"
                measurements[slot].append(Measurement(candidate.identity, spec.metric_id, value,
                                                       spec.unit, spec.context_id, ref))
    return [replace(candidate, measurements=tuple(measurements[index])) for index, candidate in enumerate(candidates)]


def _safe_artifact(bundle: Path, relative: str) -> Path:
    if type(relative) is not str or normalize_repo_relative_path(relative) != relative:
        raise CollectionError("noncanonical artifact reference")
    current = bundle
    for part in Path(relative).parts:
        current = current / part
        if current.is_symlink():
            raise CollectionError("symlink in evidence bundle")
    return current


def arbitrate_collected(receipt: CollectionReceipt, policy: CollectorPolicy):
    """Verify against a retained trusted receipt, then call the unchanged arbiter."""
    try:
        bundle = Path(receipt.bundle_path)
        if bundle.is_symlink() or bundle.resolve() != bundle:
            raise CollectionError("bundle path changed")
        raw = _read_regular(bundle / "manifest.json", 16 * 1024**2)
        if digest(raw) != receipt.manifest_sha256:
            raise CollectionError("manifest hash mismatch")
        manifest = json.loads(raw)
        if (manifest["schema_version"] != COLLECTOR_VERSION or
            manifest["evaluation_id"] != receipt.evaluation_id or
            manifest["base_revision"] != receipt.base_revision or
            manifest["policy_sha256"] != receipt.policy_sha256 or
            receipt.policy_sha256 != policy.sha256 or
            manifest["patch_sha256"] != list(receipt.patch_sha256)):
            raise CollectionError("collection receipt identity mismatch")
        for ref, expected in manifest["artifacts"].items():
            if digest(_read_regular(_safe_artifact(bundle, ref), 64 * 1024**2)) != expected:
                raise CollectionError(f"artifact hash mismatch: {ref}")
        if digest(_read_regular(bundle / "policy.json", 16 * 1024**2)) != policy.sha256:
            raise CollectionError("policy artifact mismatch")
        candidates = []
        for index, slot in enumerate(("A", "B")):
            patch = _read_regular(bundle / f"candidate-{slot}/patch.diff", policy.max_patch_bytes)
            if digest(patch) != receipt.patch_sha256[index]:
                raise CollectionError("patch digest mismatch")
            data = json.loads(_read_regular(bundle / f"candidate-{slot}/evidence.json", 16 * 1024**2))
            evidence = candidate_evidence_from_dict(data)
            expected = EvidenceIdentity(receipt.evaluation_id, slot,
                f"testcube:{receipt.evaluation_id}:{receipt.base_revision}:{receipt.patch_sha256[index]}")
            if evidence.identity != expected:
                raise CollectionError("candidate evidence identity mismatch")
            for ref in (evidence.scope_evidence_ref,) + tuple(check.evidence_ref for check in evidence.checks) + tuple(item.evidence_ref for item in evidence.measurements):
                if ref not in manifest["artifacts"]:
                    raise CollectionError("unbound evidence artifact reference")
            candidates.append(evidence)
        return evaluate(candidate_a=candidates[0], candidate_b=candidates[1], policy=policy.candidate_policy)
    except CollectionError:
        raise
    except Exception as exc:
        raise CollectionError("evidence reconstruction failed") from exc


def cleanup_collection(receipt: CollectionReceipt, policy: CollectorPolicy) -> None:
    """Remove only the collector-owned disposable copies, after durable evidence."""
    arbitrate_collected(receipt, policy)
    bundle = Path(receipt.bundle_path)
    trees = bundle / "worktrees"
    if trees.is_symlink() or trees.resolve() != trees or trees.parent != bundle:
        raise CollectionError("unsafe cleanup target")
    try:
        if not shutil.rmtree.avoids_symlink_attacks:
            raise CollectionError("safe cleanup unavailable")
        shutil.rmtree(trees)
        write_new(bundle / "cleanup.json", canonical_bytes({"status": "REMOVED_DISPOSABLE_COPIES", "evidence_preserved": True}))
    except Exception as exc:
        raise CollectionError("cleanup failed; durable evidence retained") from exc


def collect_and_evaluate(
    *, source_repo: Path, patch_a: Path, patch_b: Path, policy: CollectorPolicy,
    output_root: Path, cleanup: bool = False,
) -> CollectionResult:
    """Collect two external patches. Infrastructure failure never becomes a verdict.

    The output root must be outside the source repository and operator-owned.
    Each evaluation ID is single-use. By default copies are retained for review.
    """
    bundle = None
    receipt = None
    try:
        if type(policy) is not CollectorPolicy or type(cleanup) is not bool:
            raise CollectionError("invalid collector configuration")
        source = Path(source_repo).resolve(strict=True)
        output = Path(output_root).resolve(strict=True)
        runtime = Path(policy.runtime_root).resolve(strict=True)
        if source == output or source in output.parents or output in source.parents:
            raise CollectionError("output root must be disjoint from source repository")
        if runtime == output or runtime in output.parents or output in runtime.parents or output == Path("/usr") or Path("/usr") in output.parents:
            raise CollectionError("output root must not overlap exposed runtime mounts")
        if source == runtime or runtime in source.parents or source == Path("/usr") or Path("/usr") in source.parents:
            raise CollectionError("source must not be inside an exposed runtime mount")
        if runtime == Path("/") or not (runtime / "pyvenv.cfg").is_file() or not (runtime / "bin/python").is_file():
            raise CollectionError("runtime_root must name a trusted Python virtualenv")
        if str(runtime) != policy.runtime_root:
            raise CollectionError("runtime_root must be canonical, not a mutable symlink alias")
        evaluation_id = policy.candidate_policy.evaluation_id
        candidate_bundle = output / evaluation_id
        candidate_bundle.mkdir(mode=0o700)
        bundle = candidate_bundle
        write_new(bundle / "policy.json", canonical_bytes(policy.to_dict()))
        git = _Git(policy, bundle)
        if Path(git.text(source, "rev-parse", "--show-toplevel").strip()).resolve() != source:
            raise CollectionError("source_repo is not a repository root")
        before = _source_snapshot(source, git)
        if not before["clean"]:
            raise CollectionError("source checkout is not clean")
        base = git.text(source, "rev-parse", "--verify", "--end-of-options", f"{policy.base_revision}^{{commit}}").strip()
        if not _FULL_SHA.fullmatch(base):
            raise CollectionError("base did not resolve to a full immutable commit")
        if _tree_modes(git.text(source, "ls-tree", "-r", "-z", base)):
            raise CollectionError("base contains unsupported symlinks or submodules")
        patches = [_read_regular(Path(path), policy.max_patch_bytes) for path in (patch_a, patch_b)]
        hashes = tuple(digest(patch) for patch in patches)
        trees = []
        (bundle / "worktrees").mkdir(mode=0o700)
        for slot in ("A", "B"):
            tree = bundle / "worktrees" / slot
            git.run(bundle, "clone", "--no-local", "--no-hardlinks", "--no-checkout", "--", str(source), str(tree))
            git.run(tree, "config", "--remove-section", "remote.origin")
            git.run(tree, "checkout", "--detach", base)
            if (git.text(tree, "rev-parse", "HEAD").strip() != base or
                Path(git.text(tree, "rev-parse", "--show-toplevel").strip()) != tree or
                git.text(tree, "status", "--porcelain=v1", "-z", "--untracked-files=all")):
                raise CollectionError("detached candidate setup is not clean at the pinned base")
            if git.run(tree, "symbolic-ref", "-q", "HEAD", required=False)[0].returncode != 1:
                raise CollectionError("candidate checkout is not detached")
            trees.append(tree)
        # Preflight the same isolation boundary before touching any patch. A
        # failed kernel namespace/launcher setup is infrastructure failure.
        probe = CommandSpec("preflight", ("/runtime/bin/python", "-I", "--version"))
        observation = run_isolated(trees[0], policy, probe, bundle, "environment/runtime")
        if observation.exit_code != 0:
            raise CollectionError("runtime preflight failed")
        bubblewrap = run_command(["/usr/bin/bwrap", "--version"], cwd=bundle,
                                  timeout=10, max_output_bytes=4096)
        if bubblewrap.returncode != 0 or bubblewrap.timed_out or bubblewrap.output_limit_exceeded:
            raise CollectionError("cannot identify Bubblewrap version")
        environment = {"python": sys.version, "platform": platform.platform(),
                       "bubblewrap": bubblewrap.stdout.strip(),
                       "collector_code_revision": git.text(Path(__file__).resolve().parents[2], "rev-parse", "HEAD").strip(),
                       "git": git.text(source, "--version").strip(),
                       "base_revision": base, "runtime_root": str(runtime),
                       "runtime_interpreter_sha256": digest(_read_regular((runtime / "bin/python").resolve(), 64 * 1024**2)),
                       "collector_version": COLLECTOR_VERSION,
                       "collector_code": {path.name: digest(path.read_bytes()) for path in sorted(Path(__file__).parent.glob("*.py"))}}
        write_new(bundle / "environment.json", canonical_bytes(environment))
        candidates = [_collect_candidate(slot, trees[index], patches[index], hashes[index], base,
                                         policy, bundle, git) for index, slot in enumerate(("A", "B"))]
        candidates = _collect_benchmarks(candidates, trees, policy, bundle)
        for index, candidate in enumerate(candidates):
            if git.text(trees[index], "diff", "--name-only", "-z"):
                raise CollectionError("candidate source changed during benchmarks")
            write_new(bundle / f"candidate-{candidate.identity.candidate_id}/evidence.json", canonical_bytes(asdict(candidate)))
        after = _source_snapshot(source, git)
        if after != before:
            raise CollectionError("trusted source repository changed")
        write_new(bundle / "source-integrity.json", canonical_bytes({"before": before, "after": after, "unchanged": True}))
        artifacts = {}
        for path in sorted(bundle.rglob("*")):
            relative = path.relative_to(bundle)
            if relative.parts[0] == "worktrees":
                continue
            if path.is_symlink():
                raise CollectionError("unexpected artifact symlink")
            if path.is_file():
                artifacts[str(relative)] = digest(_read_regular(path, 64 * 1024**2, sync=True))
                fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
                try:
                    os.fsync(fd)
                finally:
                    os.close(fd)
        manifest = {"schema_version": COLLECTOR_VERSION, "evaluation_id": evaluation_id,
                    "base_revision": base, "policy_sha256": policy.sha256,
                    "patch_sha256": list(hashes), "patch_sizes": [len(patch) for patch in patches],
                    "artifacts": artifacts, "status": "COLLECTED", "human_review_required": True}
        raw = canonical_bytes(manifest)
        write_new(bundle / "manifest.json", raw)
        receipt = CollectionReceipt(str(bundle), digest(raw), evaluation_id, base, policy.sha256, hashes)
        arbitration = arbitrate_collected(receipt, policy)
        write_new(bundle / "arbitration-result.json", arbitration.to_json().encode())
        if cleanup:
            cleanup_collection(receipt, policy)
        outcome = "EVIDENCE_COMPLETE" if all(gate.passed for gate in arbitration.mandatory_gate_results) else "CANDIDATE_INVALID"
        return CollectionResult(outcome, receipt, arbitration)
    except Exception as exc:
        # Do not expose arbitrary exception text (tool output may contain
        # candidate prose). Only our fixed infrastructure classifications pass.
        reason = str(exc) if isinstance(exc, CollectionError) else f"collector infrastructure exception: {type(exc).__name__}"
        if bundle is not None:
            try:
                write_new(bundle / "collection-failure.json", canonical_bytes({"outcome": "COLLECTION_FAILED", "reason": reason}))
            except Exception:
                reason += "; failure artifact could not be written"
        return CollectionResult("COLLECTION_FAILED", receipt, None, (reason,))
