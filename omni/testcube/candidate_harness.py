"""One supervised pair of patch proposals, then the approved collector/arbiter.

Providers never receive evidence constructors, collector commands, or a peer's
output. All mutable I/O belongs to an exclusive external trial directory.
"""
from __future__ import annotations

from dataclasses import asdict, replace
from pathlib import Path
from datetime import datetime, timezone
import os

from omni.testcube.candidate_models import (
    CandidateTaskSpec, CANDIDATE_SCHEMA, EDIT_SCHEMA, MAX_PROPOSAL_BYTES,
    TRIAL_SCHEMA, TrialReceipt, TrialResult, candidate_schema, validate_candidate, validate_edit_proposal,
)
from omni.testcube.candidate_providers import CandidateProvider, transport_prompt
from omni.testcube.edit_renderer import RendererFailure, render_edits
from omni.testcube.collector import (
    _Git, _FULL_SHA, _read_regular, _safe_artifact, _source_snapshot, _tree_modes,
    collect_and_evaluate, arbitrate_collected,
)
from omni.testcube.collector_models import CollectionReceipt, canonical_bytes, digest
from omni.testcube.isolated_runner import paths_overlap, runtime_base_prefix, write_new


def candidate_prompt(task: CandidateTaskSpec, base: str, slot: str, transport=EDIT_SCHEMA) -> str:
    return transport_prompt(transport) + "\nHuman-owned task and identity:\n" + canonical_bytes({
        "task": asdict(task), "base_commit": base, "candidate_id": slot,
    }).decode()


def _verify_generation_files(root, generations):
    for slot, record in zip(("A", "B"), generations):
        if record["candidate_id"] != slot or record["provider"] != {"A": "claude", "B": "codex"}[slot]:
            raise ValueError("generation identity changed")
        for name, suffix in (("proposal", "json"), ("patch", "diff")):
            if record.get(name + "_sha256") is None:
                continue
            raw = _read_regular(_safe_artifact(root, f"generation/candidate-{slot}/{name}.{suffix}"), 128 * 1024)
            if digest(raw) != record[name + "_sha256"] or len(raw) != record[name + "_size"]:
                raise ValueError("generation artifact disagrees with binding")


def verify_trial(receipt: TrialReceipt, policy):
    """Verify the retained manifest receipt and delegate evidence authenticity.

    As with collector receipts, the receipt must stay outside untrusted control.
    No signature or protection against a hostile host operator is claimed.
    """
    from omni.testcube.candidate_models import strict_json

    root = Path(receipt.trial_path)
    if root.resolve() != root or root.is_symlink():
        raise ValueError("trial path changed")
    raw = _read_regular(root / "manifest.json", 16 * 1024**2)
    if digest(raw) != receipt.manifest_sha256:
        raise ValueError("trial manifest changed")
    manifest = strict_json(raw)
    for ref, expected in manifest["artifacts"].items():
        if digest(_read_regular(_safe_artifact(root, ref), 16 * 1024**2)) != expected:
            raise ValueError("trial artifact changed")
    if manifest["schema_version"] != TRIAL_SCHEMA or manifest["human_review_required"] is not True:
        raise ValueError("invalid trial manifest")
    if manifest["outcome"] != "TRIAL_COMPLETE":
        return None
    _verify_generation_files(root, manifest["generations"])
    collected = dict(manifest["collector_receipt"])
    collected["patch_sha256"] = tuple(collected["patch_sha256"])
    collector_receipt = CollectionReceipt(**collected)
    if (collector_receipt.patch_sha256 != tuple(item["patch_sha256"] for item in manifest["generations"]) or
        collector_receipt.base_revision != manifest["base_commit"]):
        raise ValueError("generation and collection identities disagree")
    pinned = replace(policy, base_revision=manifest["base_commit"])
    result = arbitrate_collected(collector_receipt, pinned)
    if canonical_bytes(result.to_dict()) != canonical_bytes(manifest["arbitration"]):
        raise ValueError("trial verdict disagrees with collector")
    return result


def run_supervised_trial(*, task: CandidateTaskSpec, source_repo: Path, output_root: Path,
                         policy, providers: tuple[CandidateProvider, CandidateProvider],
                         candidate_transport=EDIT_SCHEMA) -> TrialResult:
    root = None
    git = None
    before = None
    base = None
    collection = None
    generations = []
    provider_metadata = []
    outcome = "GENERATION_FAILED"
    error = ""
    try:
        candidate_schema(candidate_transport)
        task.validate_policy(policy)
        if (type(providers) is not tuple or len(providers) != 2 or
            any(type(p) is not CandidateProvider for p in providers) or
            tuple(p.provider for p in providers) != ("claude", "codex") or
            providers[0].live != providers[1].live or any(p.calls or p.preflight_result for p in providers)):
            raise ValueError("fresh Claude/A and Codex/B providers in the same mode required")
        source = Path(source_repo).resolve(strict=True)
        output = Path(output_root).resolve(strict=True)
        runtime = Path(policy.runtime_root).resolve(strict=True)
        if (source == output or source in output.parents or output in source.parents or
            runtime == output or runtime in output.parents or output in runtime.parents or
            source in (Path("/"), Path("/tmp"), Path("/run")) or
            output in (Path("/"), Path("/tmp"), Path("/run")) or
            Path("/usr") in output.parents or Path("/run") in source.parents):
            raise ValueError("source, runtime and external output roots must have safe disjoint locations")
        if (str(runtime) != policy.runtime_root or runtime == Path("/") or
            not (runtime / "pyvenv.cfg").is_file() or not (runtime / "bin/python").is_file() or
            source == runtime or runtime in source.parents or Path("/usr") in source.parents):
            raise ValueError("invalid or exposed trusted runtime/source")
        runtime_base = runtime_base_prefix(policy.runtime_root)
        if runtime_base is not None and any(paths_overlap(path, Path(runtime_base)) for path in (source, output)):
            raise ValueError("source and output must not overlap the runtime's base Python mount")
        candidate_root = output / task.task_id
        candidate_root.mkdir(mode=0o700)
        root = candidate_root
        write_new(root / "task.json", canonical_bytes(asdict(task)))
        write_new(root / "requested-policy.json", canonical_bytes(policy.to_dict()))
        git = _Git(policy, root)
        if Path(git.text(source, "rev-parse", "--show-toplevel").strip()).resolve() != source:
            raise ValueError("source must be the repository root")
        before = _source_snapshot(source, git)
        base = git.text(source, "rev-parse", "--verify", "--end-of-options", f"{task.base_revision}^{{commit}}").strip()
        # Read-only live inspection must see exactly the commit being tested.
        # Older commits require a separately prepared trusted checkout.
        if not before["clean"] or not _FULL_SHA.fullmatch(base) or before["head"] != base:
            raise ValueError("source must be clean and HEAD must equal the pinned task base")
        if _tree_modes(git.text(source, "ls-tree", "-r", "-z", base)):
            raise ValueError("base contains collector-unsupported symlinks/submodules")
        inventory = git.text(source, "ls-files", "-v", "-z").split("\0")
        if inventory[-1] != "" or any(not item.startswith("H ") for item in inventory[:-1]):
            raise ValueError("source has unsupported assume-unchanged/skip-worktree index flags")
        tracked = {item[2:] for item in inventory[:-1]}
        for path in task.validation_paths + task.allowed_paths:
            target = source / path
            if path not in tracked or target.resolve() != target or not target.is_file():
                raise ValueError("first-trial source and validation paths must be existing regular files")
        pinned = replace(policy, base_revision=base)
        write_new(root / "base.json", canonical_bytes({"requested": task.base_revision, "commit": base}))
        write_new(root / "collector-policy.json", canonical_bytes(pinned.to_dict()))
        for provider in providers:
            preflight = provider.preflight(source, output)
            provider_metadata.append({"provider": provider.provider, "live": provider.live,
                                      "config": asdict(provider.config), "preflight": asdict(preflight)})
        ready = all(p.preflight_result.ready for p in providers)
        write_new(root / "providers.json", canonical_bytes({"status": "DUAL_READY" if ready else "DUAL_PREFLIGHT_FAILED",
                                                            "providers": provider_metadata}))
        if not ready:
            raise ValueError("both provider preflights must be ready")
        # No peer output is in a prompt. Live process namespaces also mask the
        # entire output root and have private temporary storage and process views.
        for slot, provider in zip(("A", "B"), providers):
            if _source_snapshot(source, git) != before:
                raise ValueError("trusted source changed before provider invocation")
            generation = root / "generation" / f"candidate-{slot}"
            prompt = candidate_prompt(task, base, slot, candidate_transport)
            write_new(generation / "prompt.txt", prompt.encode())
            started = datetime.now(timezone.utc).isoformat()
            result, classification, argv = provider.generate(prompt, source, transport=candidate_transport)
            record = {"candidate_id": slot, "provider": provider.provider,
                      "provider_version": provider.preflight_result.provider_version,
                      "task_id": task.task_id, "task_sha256": task.sha256, "base_commit": base,
                      "call_number": provider.calls, "started_at": started,
                      "duration_seconds": result.duration_seconds, "exit_code": result.returncode, "cwd": str(source),
                      "classification": classification, "argv": argv,
                      "candidate_transport": candidate_transport,
                      "proposal_sha256": None, "proposal_size": None,
                      "prompt_sha256": digest(prompt.encode()), "patch_sha256": None, "patch_size": None}
            # Bounded stdout is audit data only. Do not archive stderr/auth output.
            raw = result.stdout.encode()[:provider.output_limit]
            write_new(generation / "raw-output.json", raw)
            patch = None
            if classification == "SUCCESS":
                try:
                    if candidate_transport == EDIT_SCHEMA:
                        if len(raw) > MAX_PROPOSAL_BYTES:
                            raise ValueError("structured output exceeds proposal byte limit")
                        proposal = validate_edit_proposal(provider.decode(raw))
                        write_new(generation / "proposal.json", proposal)
                        record.update(proposal_sha256=digest(proposal), proposal_size=len(proposal))
                        patch = render_edits(proposal=proposal, task=task, policy=policy,
                            source=source, base=base, source_snapshot=before, git=git, scratch_parent=output)
                    else:
                        patch = validate_candidate(provider.decode(raw), policy.max_patch_bytes)
                    record.update(patch_sha256=digest(patch), patch_size=len(patch))
                except RendererFailure:
                    record["classification"] = "RENDERER_FAILURE"
                except (ValueError, TypeError, UnicodeError):
                    record["classification"] = "INVALID_OUTPUT"
            if patch is not None:
                write_new(generation / "patch.diff", patch)
                # Syntax-only Git parsing: --numstat disables patch application.
                # Applicability, scope and correctness remain collector gates.
                if candidate_transport == CANDIDATE_SCHEMA:
                    syntax = git.run(source, "apply", "--numstat", "-z", "--",
                                     str(generation / "patch.diff"), required=False)[0]
                    if syntax.returncode != 0:
                        record["classification"] = "INVALID_OUTPUT"
            write_new(generation / "generation.json", canonical_bytes(record))
            generations.append(record)
            if _source_snapshot(source, git) != before:
                raise ValueError("trusted source changed during generation")
        if any(item["classification"] != "SUCCESS" for item in generations):
            raise ValueError("candidate generation failed; no collector invocation")
        _verify_generation_files(root, generations)
        patches = [root / "generation" / f"candidate-{slot}" / "patch.diff" for slot in ("A", "B")]
        hashes = tuple(item["patch_sha256"] for item in generations)
        if tuple(digest(_read_regular(path, policy.max_patch_bytes)) for path in patches) != hashes:
            raise ValueError("generation patch changed before collection")
        outcome = "COLLECTION_FAILED"
        evidence_root = root / "collection"
        evidence_root.mkdir(mode=0o700)
        collection = collect_and_evaluate(source_repo=source, patch_a=patches[0], patch_b=patches[1],
                                          policy=pinned, output_root=evidence_root)
        if collection.outcome == "COLLECTION_FAILED" or collection.receipt is None or collection.arbitration is None:
            raise ValueError("collector infrastructure failure")
        if (collection.receipt.patch_sha256 != hashes or collection.receipt.base_revision != base or
            tuple(digest(_read_regular(path, policy.max_patch_bytes)) for path in patches) != hashes):
            raise ValueError("collector snapshot disagrees with generation patch identity")
        # Re-verify through the collector's authoritative authenticity seam.
        if arbitrate_collected(collection.receipt, pinned) != collection.arbitration:
            raise ValueError("collector verdict changed")
        outcome = "TRIAL_COMPLETE"
    except Exception as exc:
        # Never promote exception strings from subprocesses or provider prose.
        error = f"{outcome}: {type(exc).__name__}"
    finally:
        if before is not None:
            try:
                after = _source_snapshot(source, git)
                unchanged = after == before
                write_new(root / "source-integrity.json", canonical_bytes({"before": before, "after": after, "unchanged": unchanged}))
                if not unchanged:
                    outcome, error = "GENERATION_FAILED", "trusted repository integrity failure"
            except Exception:
                outcome, error = "GENERATION_FAILED", "trusted repository integrity observation failed"
    if error and outcome == "TRIAL_COMPLETE":
        outcome = "COLLECTION_FAILED"
    if outcome != "TRIAL_COMPLETE" and collection is not None:
        collection = replace(collection, arbitration=None)
    receipt = None
    if root is not None:
        try:
            artifacts = {}
            for path in sorted(root.rglob("*")):
                relative = path.relative_to(root)
                if relative.parts[0] == "collection":
                    continue
                if path.is_symlink():
                    raise ValueError("trial artifact symlink")
                if path.is_file():
                    artifacts[str(relative)] = digest(_read_regular(path, 16 * 1024**2, sync=True))
                elif path.is_dir():
                    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
                    try:
                        os.fsync(fd)
                    finally:
                        os.close(fd)
            manifest = {"schema_version": TRIAL_SCHEMA, "trial_id": task.task_id,
                        "candidate_transport": candidate_transport,
                        "task_sha256": task.sha256, "base_commit": base,
                        "providers": provider_metadata, "generations": generations,
                        "collector_receipt": asdict(collection.receipt) if collection and collection.receipt else None,
                        "collector_outcome": collection.outcome if collection else None,
                        "arbitration": collection.arbitration.to_dict() if collection and collection.arbitration else None,
                        "outcome": outcome, "error": error, "artifacts": artifacts,
                        "human_review_required": True, "automatic_promotion": False}
            raw = canonical_bytes(manifest)
            write_new(root / "manifest.json", raw)
            fd = os.open(root.parent, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(fd)
            finally:
                os.close(fd)
            receipt = TrialReceipt(str(root), digest(raw))
            verify_trial(receipt, policy)
        except Exception:
            outcome, error = "COLLECTION_FAILED", "trial archive publication/verification failed"
            if collection:
                collection = replace(collection, arbitration=None)
    return TrialResult(outcome, receipt, collection, error)
