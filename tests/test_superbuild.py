"""Persistent real Git fixtures, real TestCube evidence, simulated human TTY.

No model clients or provider processes are invoked by these tests.
"""
from dataclasses import asdict, FrozenInstanceError, replace
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from test_testcube_collector import fixture_repo, git, patch_file, policy, snapshot
from omni.superbuild.models import (
    SuperBuildDecision, SuperBuildProject, SuperBuildWorkItem,
)
from omni.superbuild.workspace import (
    IntegrityError, ProjectBusy, RecoveryRequired, SuperBuildBox, verify_superbuild_project,
)
import omni.superbuild.workspace as machinery
from omni.testcube.candidate_models import CandidateTaskSpec, validate_candidate
from omni.testcube.collector_models import CollectionResult, canonical_bytes, digest


@pytest.fixture
def project(fixture_repo, tmp_path):
    source, base, _ = fixture_repo
    box = SuperBuildBox(tmp_path / "box")
    original = snapshot(source)
    state = box.create(project_id="SB-001", title="Synthetic cumulative project",
                       description="No model calls", source_repo=source, origin_commit=base)
    assert snapshot(source) == original
    return box, state, source, original


def make_work(state, work_id="WORK-001"):
    p = policy(state.accepted_project_commit, evaluation_id=work_id)
    p = replace(p, max_patch_bytes=128 * 1024, candidate_policy=replace(p.candidate_policy, forbidden_paths=("test_calc.py", "protected.txt"),
                                             max_touched_files=1, max_changed_lines=20))
    task = CandidateTaskSpec(work_id, "Synthetic fix", "Correct arithmetic", ("trusted test passes",),
        ("calc.py",), p.candidate_policy.forbidden_paths, ("focused",), (), ("test_calc.py",),
        state.accepted_project_commit, max_touched_files=1, max_changed_lines=20)
    return SuperBuildWorkItem(state.project_id, work_id, state.accepted_checkpoint,
                             state.accepted_project_commit, task, p)


def stage(project, tmp_path, *, state=None, work_id="WORK-001", old="a - b", a="a + b", b="a * b"):
    box, initial, _, _ = project
    state = state or initial
    box.add_work_item(make_work(state, work_id))
    box.advance(state.project_id, work_id, "READY")
    box.advance(state.project_id, work_id, "GENERATING")
    state = box.evaluate(state.project_id, work_id,
        patch_a=patch_file(tmp_path, work_id + "-A.diff", old=old, new=a),
        patch_b=patch_file(tmp_path, work_id + "-B.diff", old=old, new=b))
    assert state.work_items[-1].status == "AWAITING_HUMAN_DECISION"
    if work_id == "WORK-001":
        assert state.accepted_project_commit == initial.accepted_project_commit
    return state


def decision_args(box, state, choice="ACCEPT_A"):
    work = state.work_items[-1]
    bundle = box.root / state.project_id / "evidence" / work.work_item_id
    manifest = json.loads((bundle / "manifest.json").read_text())
    slot = choice[-1] if choice.startswith("ACCEPT_") else None
    return dict(project_id=state.project_id, work_item_id=work.work_item_id, decision=choice,
        operator="fixture-human", parent_checkpoint=state.accepted_checkpoint,
        parent_accepted_commit=state.accepted_project_commit,
        evidence_digest=digest((bundle / "manifest.json").read_bytes()),
        candidate_digest=digest((bundle / f"candidate-{slot}/evidence.json").read_bytes()) if slot else None,
        patch_digest=manifest["patch_sha256"][("A", "B").index(slot)] if slot else None)


@pytest.fixture
def human(monkeypatch):
    prompts = []
    def confirm(prompt):
        prompts.append(prompt)
        return prompt.splitlines()[-2]
    monkeypatch.setattr(machinery, "_read_confirmation", confirm)
    return prompts


def test_creation_origin_reload_isolation(project):
    box, state, source, original = project
    assert state.origin_commit == state.accepted_project_commit
    assert state.work_items == state.decisions == state.checkpoints == ()
    assert verify_superbuild_project(box.root, state.project_id) == state
    path = box.root / state.project_id
    model = SuperBuildProject(**json.loads((path / "project.json").read_text()))
    with pytest.raises(FrozenInstanceError):
        model.trusted_source_commit = "a" * 40
    assert Path(model.workspace_path).is_relative_to(box.root)
    assert not Path(model.workspace_path).is_relative_to(source)
    assert git(Path(model.workspace_path), "remote") == b""
    assert git(Path(model.workspace_path), "for-each-ref") == b""
    assert snapshot(source) == original
    with pytest.raises(ValueError, match="single-use"):
        box.create(project_id=state.project_id, title="x", description="x", source_repo=source, origin_commit=state.origin_commit)


@pytest.mark.parametrize("suffix", ["inside", "alias"])
def test_source_overlap_rejected(fixture_repo, tmp_path, suffix):
    source, base, _ = fixture_repo
    root = source / "box"
    if suffix == "alias":
        root = tmp_path / "link"
        root.symlink_to(source, target_is_directory=True)
    with pytest.raises(ValueError):
        SuperBuildBox(root).create(project_id="SB", title="x", description="x", source_repo=source, origin_commit=base)


def test_cannot_store_work_inside_real_omni():
    with pytest.raises(ValueError, match="outside trusted OMNI"):
        SuperBuildBox(Path(__file__).resolve().parents[1] / "outputs/superbuild")


@pytest.mark.parametrize("project_id", ["locks", "registry"])
def test_storage_names_cannot_be_project_ids(tmp_path, project_id):
    box = SuperBuildBox(tmp_path / "box")
    with pytest.raises(ValueError, match="reserved"):
        box.load(project_id)
    assert not box.root.exists()


def test_work_creation_parent_and_one_active(project):
    box, state, _, _ = project
    work = make_work(state)
    with pytest.raises(ValueError, match="wrong parent"):
        box.add_work_item(replace(work, parent_checkpoint="a" * 64))
    box.add_work_item(work)
    with pytest.raises(ValueError, match="one active"):
        box.add_work_item(make_work(state, "WORK-002"))
    with pytest.raises(ValueError):
        box.advance(state.project_id, work.work_item_id, "GENERATING")
    for status in ("ACCEPTED", "REJECTED", "AWAITING_HUMAN_DECISION", "EVALUATING"):
        with pytest.raises(ValueError, match="reserved"):
            box.advance(state.project_id, work.work_item_id, status)
    box.advance(state.project_id, work.work_item_id, "ABORTED")
    box.add_work_item(make_work(state, "WORK-002"))


@pytest.mark.parametrize("steps", [("ABORTED",), ("READY", "ABORTED"),
    ("READY", "GENERATING", "ABORTED"), ("READY", "GENERATING", "GENERATION_FAILED")])
def test_failure_lifecycle_persists_and_is_terminal(project, steps):
    box, initial, _, _ = project
    box.add_work_item(make_work(initial))
    for status in steps:
        state = box.advance(initial.project_id, "WORK-001", status)
        assert SuperBuildBox(box.root).load(initial.project_id) == state
        assert state.work_items[-1].status == status
        assert state.accepted_project_commit == initial.origin_commit
    with pytest.raises(ValueError, match="invalid transition"):
        box.advance(initial.project_id, "WORK-001", "READY")
    box.add_work_item(make_work(state, "WORK-002"))


def test_two_cumulative_acceptances_survive_new_process(project, tmp_path, human):
    box, initial, source, original = project
    awaiting = stage(project, tmp_path)
    args = decision_args(box, awaiting)
    first = box.decide(**args)
    assert len(human) == 1
    assert first.accepted_project_commit != initial.origin_commit
    assert first.work_items[-1].status == "ACCEPTED"
    assert first.checkpoints[-1].parent_accepted_commit == initial.origin_commit
    workspace = box.root / initial.project_id / "workspace"
    assert "a + b" in (workspace / "calc.py").read_text()
    message = git(workspace, "show", "-s", "--format=%B", "HEAD").decode()
    for value in (args["evidence_digest"], args["candidate_digest"], args["patch_digest"], args["parent_checkpoint"], "WORK-001"):
        assert value in message
    assert snapshot(source) == original
    reloaded = SuperBuildBox(box.root).load(initial.project_id)
    assert reloaded == first
    with pytest.raises(ValueError, match="wrong parent"):
        box.add_work_item(make_work(initial, "STALE"))
    second_pending = stage(project, tmp_path, state=reloaded, work_id="WORK-002", old="a + b", a="(a + b)", b="(a - b)")
    assert second_pending.work_items[-1].parent_accepted_commit == first.accepted_project_commit
    second = box.decide(**decision_args(box, second_pending))
    assert second.origin_commit == initial.origin_commit
    assert second.accepted_project_commit != first.accepted_project_commit
    assert second.checkpoints[-1].parent_accepted_commit == first.accepted_project_commit
    assert git(workspace, "rev-parse", "HEAD^").decode().strip() == first.accepted_project_commit
    assert "(a + b)" in (workspace / "calc.py").read_text()
    proc = subprocess.run([sys.executable, "-m", "omni.superbuild", "--root", str(box.root), "verify", initial.project_id],
                          capture_output=True, text=True, check=True)
    assert json.loads(proc.stdout)["accepted_project_commit"] == second.accepted_project_commit
    assert verify_superbuild_project(box.root, initial.project_id) == second
    assert snapshot(source) == original


def test_accept_b(project, tmp_path, human):
    box, initial, source, original = project
    pending = stage(project, tmp_path, a="a * b", b="a + b")
    result = box.decide(**decision_args(box, pending, "ACCEPT_B"))
    assert result.checkpoints[-1].candidate_slot == "B"
    assert result.accepted_project_commit != initial.origin_commit
    assert snapshot(source) == original


@pytest.mark.parametrize("choice,status", [("DEFER", "AWAITING_HUMAN_DECISION"), ("REJECT_BOTH", "REJECTED")])
def test_defer_and_reject(project, tmp_path, human, choice, status):
    box, initial, _, _ = project
    pending = stage(project, tmp_path)
    result = box.decide(**decision_args(box, pending, choice))
    assert result.accepted_project_commit == initial.origin_commit
    assert result.work_items[-1].status == status
    assert result.decisions[-1].decision == choice
    assert result.checkpoints == ()
    assert box.load(initial.project_id) == result
    if choice == "DEFER":
        accepted = box.decide(**decision_args(box, result))
        assert [d.decision for d in accepted.decisions] == ["DEFER", "ACCEPT_A"]


def test_invalid_candidate_cannot_be_accepted(project, tmp_path, human):
    box, _, _, _ = project
    pending = stage(project, tmp_path)
    with pytest.raises(ValueError, match="gate-invalid"):
        box.decide(**decision_args(box, pending, "ACCEPT_B"))
    assert not human


@pytest.mark.parametrize("field", ["evidence_digest", "candidate_digest", "patch_digest", "parent_checkpoint", "parent_accepted_commit"])
def test_wrong_bindings_rejected_before_confirmation(project, tmp_path, human, field):
    box, _, _, _ = project
    pending = stage(project, tmp_path)
    args = decision_args(box, pending)
    args[field] = "a" * len(args[field])
    with pytest.raises(ValueError):
        box.decide(**args)
    assert not human
    assert box.load(pending.project_id) == pending


def test_model_cannot_authorize_decision(project, tmp_path, monkeypatch):
    box, _, _, _ = project
    pending = stage(project, tmp_path)
    args = decision_args(box, pending)
    monkeypatch.setattr(machinery, "_read_confirmation", lambda _: json.dumps(args))
    with pytest.raises(ValueError, match="confirmation"):
        box.decide(**args)
    with pytest.raises(TypeError):
        box.decide(**args, authority="model")
    with pytest.raises(ValueError):
        validate_candidate(args, 128 * 1024)
    assert box.load(pending.project_id) == pending


@pytest.mark.parametrize("field,value", [("authority", "model"), ("decision", "APPROVED"), ("selected_candidate", "B"),
    ("evidence_digest", "bad"), ("operator", ""), ("timestamp", "yesterday"), ("project_id", "../escape")])
def test_decision_strict_schema(field, value):
    data = dict(project_id="SB", work_item_id="WORK", parent_checkpoint="a" * 64, parent_accepted_commit="a" * 40,
                evidence_digest="b" * 64, decision="ACCEPT_A", selected_candidate="A", candidate_digest="c" * 64,
                patch_digest="d" * 64, operator="human", timestamp="2026-09-14T12:00:00+00:00")
    with pytest.raises(ValueError):
        SuperBuildDecision(**(data | {field: value}))


@pytest.mark.parametrize("target", ["manifest", "origin", "patch", "candidate", "evidence", "decision", "input", "message", "history-extra", "history-missing"])
def test_durable_tampering_fails_closed(project, tmp_path, human, target):
    box, initial, source, original = project
    pending = stage(project, tmp_path)
    box.decide(**decision_args(box, pending))
    root = box.root / initial.project_id
    if target == "manifest":
        path = root / "manifest.json"
        data = json.loads(path.read_text())
        data["state"]["accepted_project_commit"] = initial.origin_commit
        path.write_bytes(canonical_bytes(data))
    elif target == "origin":
        path = root / "project.json"
        data = json.loads(path.read_text())
        data["trusted_source_commit"] = "a" * 40
        path.write_bytes(canonical_bytes(data))
    elif target in ("patch", "candidate", "evidence"):
        names = {"patch": "candidate-A/patch.diff", "candidate": "candidate-A/evidence.json", "evidence": "manifest.json"}
        path = root / "evidence/WORK-001" / names[target]
        path.write_bytes(path.read_bytes() + b" ")
    elif target == "decision":
        path = next(p for p in (root / "records").iterdir() if json.loads(p.read_text())["kind"] == "decision")
        data = json.loads(path.read_text())
        data["payload"]["operator"] = "forged"
        path.write_bytes(canonical_bytes(data))
    elif target in ("input", "message"):
        path = root / "inputs/WORK-001" / ("A" if target == "input" else "commit-message")
        path.write_bytes(path.read_bytes() + b"tamper")
    elif target == "history-extra":
        (root / "records/99999999.json").write_text("{}")
    else:
        (root / "records/00000000.json").unlink()
    with pytest.raises(IntegrityError):
        box.load(initial.project_id)
    assert snapshot(source) == original


@pytest.mark.parametrize("mode", ["dirty", "ignored", "wrong-head", "index-flag", "config", "symlink", "gitlink", "same-stat"])
def test_workspace_tamper(project, mode):
    box, initial, _, _ = project
    root = box.root / initial.project_id
    tree = root / "workspace"
    if mode == "dirty":
        (tree / "untracked").write_text("tamper")
    elif mode == "ignored":
        (tree / ".git/info").mkdir(exist_ok=True)
        (tree / ".git/info/exclude").write_text("hidden\n")
        (tree / "hidden").write_text("tamper")
    elif mode == "wrong-head":
        git(tree, "-c", "user.name=fixture", "-c", "user.email=fixture@example.invalid", "commit", "--allow-empty", "-m", "rogue")
    elif mode == "index-flag":
        git(tree, "update-index", "--assume-unchanged", "calc.py")
    elif mode == "config":
        git(tree, "config", "core.filemode", "false")
    elif mode == "symlink":
        (tree / "calc.py").unlink()
        (tree / "calc.py").symlink_to("/tmp")
    elif mode == "gitlink":
        (tree / ".git/objects/info/alternates").write_text("/tmp\n")
    else:
        file = tree / "calc.py"
        info = file.stat()
        file.write_text(file.read_text().replace("a - b", "a * b"))
        os.utime(file, ns=(info.st_atime_ns, info.st_mtime_ns))
    with pytest.raises(IntegrityError):
        box.load(initial.project_id)


def test_concurrent_mutation_rejected(project):
    box, state, _, _ = project
    with box._lock(state.project_id):
        with pytest.raises(ProjectBusy):
            SuperBuildBox(box.root).add_work_item(make_work(state))
        proc = subprocess.run([sys.executable, "-m", "omni.superbuild", "--root", str(box.root), "verify", state.project_id],
                              capture_output=True, text=True)
        assert proc.returncode != 0 and "ProjectBusy" in proc.stderr
    assert box.load(state.project_id) == state


@pytest.mark.parametrize("stage_name", ["before_candidate_application", "during_candidate_application", "after_patch_before_commit",
                                      "after_commit_before_manifest", "after_manifest_update"])
def test_crash_fail_closed(project, tmp_path, human, monkeypatch, stage_name):
    box, initial, source, original = project
    pending = stage(project, tmp_path)
    def crash(observed):
        if observed == stage_name:
            if observed == "during_candidate_application":
                # Simulate an interrupted Git write with only worktree bytes changed.
                (box.root / initial.project_id / "workspace/calc.py").write_text("partially applied\n")
            os._exit(73)  # no Python finally blocks; OS releases the flock
    monkeypatch.setattr(machinery, "_fault", crash)
    args = decision_args(box, pending)
    pid = os.fork()
    if pid == 0:
        try:
            box.decide(**args)
        finally:
            os._exit(74)  # reaching here means the intended crash was missed
    _, status = os.waitpid(pid, 0)
    assert os.waitstatus_to_exitcode(status) == 73
    assert (box.root / initial.project_id / "transaction.json").is_file()
    with pytest.raises(RecoveryRequired):
        SuperBuildBox(box.root).load(initial.project_id)
    with pytest.raises(RecoveryRequired):
        box.advance(initial.project_id, "WORK-001", "ABORTED")
    assert snapshot(source) == original


def test_ancestry_and_evaluated_tree_checked_independently(project, tmp_path, human):
    box, initial, _, _ = project
    pending = stage(project, tmp_path)
    result = box.decide(**decision_args(box, pending))
    root = box.root / initial.project_id
    project_model = SuperBuildProject(**json.loads((root / "project.json").read_text()))
    records = [json.loads(p.read_text()) for p in sorted((root / "records").iterdir())]
    # Even if a trusted caller recomputed journal hashes, semantic verification
    # independently rejects a real Git commit without the required parent/tree.
    last = records[-1]
    last["payload"]["accepted_project_commit"] = initial.origin_commit
    with pytest.raises(ValueError, match="ancestry"):
        box._replay(project_model, records)
    records[-1]["payload"]["accepted_project_commit"] = result.accepted_project_commit
    decision = result.decisions[-1]
    with pytest.raises(ValueError, match="evaluated candidate"):
        box._verify_commit_patch(project_model, result.work_items[-1], decision, initial.origin_commit)


def test_collection_failure_durable_and_no_retry(project, tmp_path, monkeypatch):
    box, initial, _, _ = project
    box.add_work_item(make_work(initial))
    box.advance(initial.project_id, "WORK-001", "READY")
    box.advance(initial.project_id, "WORK-001", "GENERATING")
    monkeypatch.setattr(machinery, "collect_and_evaluate", lambda **kw: CollectionResult("COLLECTION_FAILED", None, None, ("fixture failure",)))
    path = patch_file(tmp_path, "patch.diff")
    state = box.evaluate(initial.project_id, "WORK-001", patch_a=path, patch_b=path)
    assert state.work_items[-1].status == "EVIDENCE_FAILED"
    assert state.accepted_project_commit == initial.origin_commit
    assert box.load(initial.project_id) == state
    with pytest.raises(ValueError, match="invalid transition"):
        box.evaluate(initial.project_id, "WORK-001", patch_a=path, patch_b=path)


def test_artifact_changed_during_human_pause_rejected(project, tmp_path, monkeypatch):
    box, initial, _, _ = project
    pending = stage(project, tmp_path)
    args = decision_args(box, pending)
    def confirm(prompt):
        patch = box.root / initial.project_id / "evidence/WORK-001/candidate-A/patch.diff"
        patch.write_bytes(patch.read_bytes() + b"tamper")
        return prompt.splitlines()[-2]
    monkeypatch.setattr(machinery, "_read_confirmation", confirm)
    with pytest.raises(Exception, match="hash mismatch"):
        box.decide(**args)
    assert git(box.root / initial.project_id / "workspace", "rev-parse", "HEAD").decode().strip() == initial.origin_commit


@pytest.mark.parametrize("invalid", ["json-duplicate", "schema", "checkpoint-without-decision", "invalid-history-transition", "manifest-with-new-checksum"])
def test_manifest_schema_and_semantic_history(project, invalid):
    box, initial, _, _ = project
    root = box.root / initial.project_id
    if invalid == "json-duplicate":
        (root / "manifest.json").write_text('{"schema_version": "a", "schema_version": "b"}')
    elif invalid == "schema":
        path = root / "project.json"
        data = json.loads(path.read_text())
        data["schema_version"] = "future-unknown"
        path.write_bytes(canonical_bytes(data))
    elif invalid == "manifest-with-new-checksum":
        path = root / "manifest.json"
        data = json.loads(path.read_text())
        data["state"]["origin_commit"] = "a" * 40
        path.write_bytes(canonical_bytes(data))
        anchor_path = box._anchor(initial.project_id)
        anchor = json.loads(anchor_path.read_text())
        anchor["manifest_digest"] = digest(path.read_bytes())
        anchor_path.write_bytes(canonical_bytes(anchor))
    else:
        box.add_work_item(make_work(initial))
        project_model, records, _ = box._load(initial.project_id)
        if invalid == "checkpoint-without-decision":
            from omni.superbuild.models import SuperBuildCheckpoint
            payload = asdict(SuperBuildCheckpoint(initial.project_id, "WORK-001", initial.accepted_checkpoint,
                initial.origin_commit, initial.origin_commit, "A", "a" * 64, "b" * 64, "c" * 64, "d" * 64))
            kind = "checkpoint"
        else:
            kind, payload = "transition", dict(work_item_id="WORK-001", **{"from": "PENDING", "to": "GENERATING"})
        records.append(dict(sequence=len(records), previous=digest(canonical_bytes(records[-1])), kind=kind, payload=payload))
        with pytest.raises(ValueError):
            box._replay(project_model, records)
        return
    with pytest.raises(IntegrityError):
        box.load(initial.project_id)


def test_no_terminal_cannot_accept(project, tmp_path, monkeypatch):
    box, _, _, _ = project
    pending = stage(project, tmp_path)
    def no_terminal(_):
        raise OSError("no controlling terminal")
    monkeypatch.setattr(machinery, "_read_confirmation", no_terminal)
    with pytest.raises(OSError, match="no controlling terminal"):
        box.decide(**decision_args(box, pending))
    assert box.load(pending.project_id) == pending
