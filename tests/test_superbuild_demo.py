"""Pinned testcube-v1 demonstration, in disposable clones; zero providers.

This is a synthetic operator test, not a real engineering run or approval.
The TTY is simulated only by pytest's test fixture, never by production code.
"""
from dataclasses import asdict
import json
from pathlib import Path
import sys

from test_superbuild import decision_args, human
from test_testcube_collector import git
from omni.superbuild import SuperBuildBox, verify_superbuild_project
from omni.superbuild.models import SuperBuildWorkItem
from omni.superbuild.workspace import _Git as ProjectGit
from omni.testcube.candidate_models import CandidateTaskSpec, validate_edit_proposal, EDIT_SCHEMA
from omni.testcube.collector import _Git, _source_snapshot
from omni.testcube.collector_models import CollectorPolicy, CommandSpec, canonical_bytes
from omni.testcube.edit_renderer import render_edits
from omni.testcube.models import CandidatePolicy

BASE = "5fe6db20df83e1945c1163288201ab16ba2109ca"


def test_pinned_testcube_v1_two_step_demonstration(tmp_path, human):
    trusted = Path(__file__).resolve().parents[1]
    observer = ProjectGit()
    before = _source_snapshot(trusted, observer)
    tag = git(trusted, "rev-parse", "refs/tags/testcube-v1")
    source = tmp_path / "frozen-source"
    git(tmp_path, "clone", "--no-local", "--no-hardlinks", "--no-checkout", "--", str(trusted), str(source))
    git(source, "checkout", "--detach", BASE)
    frozen_before = _source_snapshot(source, observer)
    box = SuperBuildBox(tmp_path / "projects")
    state = box.create(project_id="SUPERBUILD-DEMO", title="Pinned v1 synthetic demonstration",
        description="Two harmless source comment changes, no model invocations", source_repo=source, origin_commit=BASE)
    assert state.accepted_project_commit == BASE
    commits = [BASE]
    path = "memory/memory_manager.py"
    original = "MAX_SUMMARY_CHARS = 1400"
    for number in (1, 2):
        work_id = f"DEMO-00{number}"
        marker = f"# Super-Build synthetic accepted step {number}"
        prior = "# Super-Build synthetic accepted step 1"
        command = f"from pathlib import Path; s=Path('{path}').read_text(); compile(s, '{path}', 'exec'); assert {marker!r} in s"
        if number == 2:
            command += f"; assert {prior!r} in s"
        commands = (
            CommandSpec("build", ("/runtime/bin/python", "-c", f"compile(open('{path}').read(), '{path}', 'exec')")),
            CommandSpec("test:synthetic", ("/runtime/bin/python", "-c", command)),
        )
        policy = CollectorPolicy(CandidatePolicy(work_id, (path,), ("synthetic",), forbidden_paths=("tests/**",),
            max_touched_files=1, max_changed_lines=10), state.accepted_project_commit, str(Path(sys.prefix).resolve()),
            commands, max_patch_bytes=128 * 1024)
        task = CandidateTaskSpec(work_id, "Harmless synthetic comment", "Demonstrate cumulative isolated state",
            ("synthetic comment retained",), (path,), ("tests/**",), ("synthetic",), (), ("tests/test_testcube_arbiter.py",),
            state.accepted_project_commit, max_touched_files=1, max_changed_lines=10)
        box.add_work_item(SuperBuildWorkItem(state.project_id, work_id, state.accepted_checkpoint,
                                            state.accepted_project_commit, task, policy))
        box.advance(state.project_id, work_id, "READY")
        box.advance(state.project_id, work_id, "GENERATING")
        workspace = box.root / state.project_id / "workspace"
        if number == 2:
            assert prior in (workspace / path).read_text()
            assert git(workspace, "rev-parse", "HEAD").decode().strip() == commits[1]
        patches = []
        for slot in ("A", "B"):
            audit = tmp_path / f"render-{work_id}-{slot}"
            audit.mkdir()
            renderer_git = _Git(policy, audit)
            proposal = validate_edit_proposal(dict(schema_version=EDIT_SCHEMA, summary="synthetic", assumptions=[], limitations=[],
                edits=[dict(path=path, before=original, after=(marker if slot == "A" else "# unselected synthetic B") + "\n" + original)]))
            patch = render_edits(proposal=proposal, task=task, policy=policy, source=workspace,
                base=state.accepted_project_commit, source_snapshot=_source_snapshot(workspace, renderer_git),
                git=renderer_git, scratch_parent=audit)
            patch_path = tmp_path / f"{work_id}-{slot}.diff"
            patch_path.write_bytes(patch)
            patches.append(patch_path)
        awaiting = box.evaluate(state.project_id, work_id, patch_a=patches[0], patch_b=patches[1])
        assert awaiting.accepted_project_commit == commits[-1]
        assert awaiting.work_items[-1].status == "AWAITING_HUMAN_DECISION"
        state = box.decide(**decision_args(box, awaiting))
        commits.append(state.accepted_project_commit)
        state = SuperBuildBox(box.root).load(state.project_id)
        assert _source_snapshot(source, observer) == frozen_before
        assert _source_snapshot(trusted, observer) == before
        assert git(trusted, "rev-parse", "refs/tags/testcube-v1") == tag
    assert len(set(commits)) == 3
    assert state.origin_commit == BASE
    assert verify_superbuild_project(box.root, state.project_id) == state
    report = dict(starting_checkpoint=BASE, accepted_commits=commits, trusted_source_unchanged=True,
        tag_preserved=True, second_work_item_builds_on_first=True, reload_verified=True,
        real_claude_calls=0, real_codex_calls=0, decisions=[asdict(d) for d in state.decisions])
    (tmp_path / "demonstration.json").write_bytes(canonical_bytes(report))
    print(json.dumps(report, sort_keys=True))
