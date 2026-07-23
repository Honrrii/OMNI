"""
Phase 11+ guard: OMNI Auto Dev structured production-packet contracts
(omni/autodev/packets.py) validate correctly, serialize round-trip, cap
repair cycles, and represent timeouts distinctly from pass/fail. No
network, no LLM calls, no GitHub API, no autonomous execution — these
tests only exercise plain dataclasses.
"""
from __future__ import annotations

import json

import pytest

from omni.autodev.packets import (
    MAX_REPAIR_CYCLES,
    PACKET_VERSION,
    AcceptanceCriterionResult,
    CloseoutPacket,
    Finding,
    ImplementationHandoff,
    RepairPacket,
    ReviewPacket,
    RunManifest,
    TaskPacket,
    TestEvidence,
    closeout_packet_from_dict,
    implementation_handoff_from_dict,
    repair_packet_from_dict,
    review_packet_from_dict,
    run_manifest_from_dict,
    task_packet_from_dict,
    to_dict,
    to_json,
    validate_repair_within_task_scope,
)


# ---------------------------------------------------------------------------
# Valid packet creation
# ---------------------------------------------------------------------------


def test_run_manifest_constructs_with_defaults():
    manifest = RunManifest(
        run_id="run-61",
        created_at="2026-07-22T00:00:00Z",
        repo_root="/repo",
        start_commit="abc123",
        branch="omni/agentic-production-cleanup",
        requested_operation="init-run",
    )
    assert manifest.dirty_state_summary == []
    assert manifest.packet_version == PACKET_VERSION


def test_task_packet_constructs_when_ready():
    task = TaskPacket(
        task_id="task-1",
        goal="Add structured packet contracts",
        acceptance_criteria=["Packets validate", "Packets serialize"],
        readiness_status="READY",
    )
    assert task.readiness_status == "READY"
    assert task.in_scope_paths == []


def test_implementation_handoff_and_review_packet_construct():
    handoff = ImplementationHandoff(
        task_id="task-1",
        files_changed=["omni/autodev/packets.py"],
        acceptance_criterion_results=[
            AcceptanceCriterionResult(criterion="Packets validate", status="VERIFIED")
        ],
        test_results=[
            TestEvidence(
                command="pytest tests/test_autodev_packets.py",
                working_dir="/repo",
                outcome="passed",
                exit_code=0,
            )
        ],
    )
    assert handoff.deviations == []

    review = ReviewPacket(
        task_id="task-1",
        verdict="APPROVED",
        findings=[
            Finding(
                summary="Looks good",
                severity="info",
                location="omni/autodev/packets.py",
                required_action="none",
            )
        ],
    )
    assert review.verdict == "APPROVED"


def test_repair_and_closeout_packets_construct():
    repair = RepairPacket(review_cycle=1, required_actions=["fix X"])
    assert repair.review_cycle == 1

    closeout = CloseoutPacket(task_id="task-1", final_verdict="APPROVED")
    assert closeout.human_approval_required is True


# ---------------------------------------------------------------------------
# Required-field rejection
# ---------------------------------------------------------------------------


def test_task_packet_rejects_missing_required_fields():
    with pytest.raises(TypeError):
        TaskPacket()  # missing task_id, goal


def test_review_packet_rejects_missing_required_fields():
    with pytest.raises(TypeError):
        ReviewPacket(task_id="task-1")  # missing verdict


def test_test_evidence_rejects_missing_required_fields():
    with pytest.raises(TypeError):
        TestEvidence(command="pytest", working_dir="/repo")  # missing outcome


# ---------------------------------------------------------------------------
# Serialization and deserialization
# ---------------------------------------------------------------------------


def test_task_packet_round_trips_through_dict():
    task = TaskPacket(
        task_id="task-1",
        goal="Do the thing",
        in_scope_paths=["a.py"],
        out_of_scope_paths=["b.py"],
        acceptance_criteria=["a.py does the thing"],
        readiness_status="READY",
    )
    restored = task_packet_from_dict(to_dict(task))
    assert restored == task


def test_run_manifest_round_trips_through_json():
    manifest = RunManifest(
        run_id="run-1",
        created_at="2026-07-22T00:00:00Z",
        repo_root="/repo",
        start_commit="abc123",
        branch="main",
        requested_operation="init-run",
        dirty_state_summary=["M foo.py"],
    )
    payload = json.loads(to_json(manifest))
    restored = run_manifest_from_dict(payload)
    assert restored == manifest


def test_implementation_handoff_round_trips_with_nested_types():
    handoff = ImplementationHandoff(
        task_id="task-1",
        files_changed=["x.py"],
        acceptance_criterion_results=[
            AcceptanceCriterionResult(criterion="c1", status="VERIFIED", evidence="test output")
        ],
        test_results=[
            TestEvidence(command="pytest", working_dir="/repo", outcome="failed", exit_code=1)
        ],
    )
    restored = implementation_handoff_from_dict(to_dict(handoff))
    assert restored == handoff
    assert isinstance(restored.acceptance_criterion_results[0], AcceptanceCriterionResult)
    assert isinstance(restored.test_results[0], TestEvidence)


def test_review_packet_round_trips_with_nested_types():
    review = ReviewPacket(
        task_id="task-1",
        verdict="CHANGES_REQUIRED",
        findings=[
            Finding(summary="bug", severity="error", location="x.py:10", required_action="fix it")
        ],
        unverified_claims=["claims tests pass, no output shown"],
    )
    restored = review_packet_from_dict(to_dict(review))
    assert restored == review
    assert isinstance(restored.findings[0], Finding)


def test_repair_packet_round_trips_through_dict():
    repair = RepairPacket(review_cycle=2, required_actions=["address finding 1"])
    restored = repair_packet_from_dict(to_dict(repair))
    assert restored == repair


def test_closeout_packet_round_trips_with_nested_test_evidence():
    closeout = CloseoutPacket(
        task_id="task-1",
        final_verdict="APPROVED",
        completed_acceptance_criteria=["c1"],
        final_test_evidence=[
            TestEvidence(command="pytest", working_dir="/repo", outcome="passed", exit_code=0)
        ],
        commit_sha="abc123",
        branch="main",
        recommended_pr_title="Add packet contracts",
    )
    restored = closeout_packet_from_dict(to_dict(closeout))
    assert restored == closeout
    assert isinstance(restored.final_test_evidence[0], TestEvidence)


# ---------------------------------------------------------------------------
# Stable packet-version behavior
# ---------------------------------------------------------------------------


def test_all_packet_types_default_to_current_packet_version():
    task = TaskPacket(task_id="t", goal="g")
    handoff = ImplementationHandoff(task_id="t")
    review = ReviewPacket(task_id="t", verdict="APPROVED")
    repair = RepairPacket(review_cycle=1)
    closeout = CloseoutPacket(task_id="t", final_verdict="APPROVED")
    manifest = RunManifest(
        run_id="r", created_at="now", repo_root="/repo", start_commit="c", branch="b",
        requested_operation="op",
    )
    for packet in (task, handoff, review, repair, closeout, manifest):
        assert packet.packet_version == PACKET_VERSION == "0.1"


# ---------------------------------------------------------------------------
# Invalid verdict / readiness / status rejection
# ---------------------------------------------------------------------------


def test_review_packet_rejects_invalid_verdict():
    with pytest.raises(ValueError):
        ReviewPacket(task_id="task-1", verdict="LGTM")


def test_closeout_packet_rejects_invalid_final_verdict():
    with pytest.raises(ValueError):
        CloseoutPacket(task_id="task-1", final_verdict="LGTM")


def test_task_packet_rejects_invalid_readiness_status():
    with pytest.raises(ValueError):
        TaskPacket(task_id="task-1", goal="g", readiness_status="MAYBE")


def test_acceptance_criterion_result_rejects_invalid_status():
    with pytest.raises(ValueError):
        AcceptanceCriterionResult(criterion="c1", status="LOOKS_FINE")


# ---------------------------------------------------------------------------
# Invalid repair-cycle rejection
# ---------------------------------------------------------------------------


def test_repair_packet_rejects_zero_review_cycle():
    with pytest.raises(ValueError):
        RepairPacket(review_cycle=0)


def test_repair_packet_rejects_review_cycle_beyond_max():
    with pytest.raises(ValueError):
        RepairPacket(review_cycle=MAX_REPAIR_CYCLES + 1)


def test_repair_packet_accepts_every_cycle_up_to_max():
    for cycle in range(1, MAX_REPAIR_CYCLES + 1):
        RepairPacket(review_cycle=cycle)


# ---------------------------------------------------------------------------
# Timeout evidence representation
# ---------------------------------------------------------------------------


def test_test_evidence_timeout_has_no_exit_code():
    evidence = TestEvidence(
        command="pytest tests -q",
        working_dir="/repo",
        outcome="timeout",
        output_summary="hung after collecting 40 items",
    )
    assert evidence.exit_code is None


def test_test_evidence_timeout_rejects_exit_code():
    with pytest.raises(ValueError):
        TestEvidence(command="pytest", working_dir="/repo", outcome="timeout", exit_code=0)


def test_test_evidence_passed_requires_exit_code():
    with pytest.raises(ValueError):
        TestEvidence(command="pytest", working_dir="/repo", outcome="passed")


def test_test_evidence_failed_requires_exit_code():
    with pytest.raises(ValueError):
        TestEvidence(command="pytest", working_dir="/repo", outcome="failed")


def test_test_evidence_rejects_unknown_outcome():
    with pytest.raises(ValueError):
        TestEvidence(command="pytest", working_dir="/repo", outcome="flaky", exit_code=0)


# ---------------------------------------------------------------------------
# No accidental use of mutable shared defaults
# ---------------------------------------------------------------------------


def test_list_fields_are_not_shared_between_instances():
    task_a = TaskPacket(task_id="a", goal="g")
    task_b = TaskPacket(task_id="b", goal="g")
    task_a.in_scope_paths.append("only-a.py")
    assert task_b.in_scope_paths == []

    handoff_a = ImplementationHandoff(task_id="a")
    handoff_b = ImplementationHandoff(task_id="b")
    handoff_a.files_changed.append("only-a.py")
    handoff_a.test_results.append(
        TestEvidence(command="pytest", working_dir="/repo", outcome="passed", exit_code=0)
    )
    assert handoff_b.files_changed == []
    assert handoff_b.test_results == []

    repair_a = RepairPacket(review_cycle=1)
    repair_b = RepairPacket(review_cycle=1)
    repair_a.required_actions.append("only-a")
    assert repair_b.required_actions == []


# ---------------------------------------------------------------------------
# Compatibility with existing Auto Dev role packets and run directories
# ---------------------------------------------------------------------------


def test_run_manifest_coexists_with_existing_run_directory(tmp_path):
    from omni.autodev.config import RUN_TEMPLATE_FILENAMES
    from omni.autodev.models import AutoDevRunState
    from omni.autodev.run_layout import build_run_files, write_run_files

    state = AutoDevRunState(issue_number=61, issue_title="Packet contracts", branch="b")
    run_dir = tmp_path / "issue-61"
    write_run_files(run_dir, build_run_files(state))

    manifest = RunManifest(
        run_id="run-61",
        created_at="2026-07-22T00:00:00Z",
        repo_root=str(tmp_path),
        start_commit="abc123",
        branch=state.branch,
        requested_operation="init-run",
    )
    manifest_path = run_dir / "RUN_MANIFEST.json"
    manifest_path.write_text(to_json(manifest), encoding="utf-8")

    assert manifest_path.name not in RUN_TEMPLATE_FILENAMES
    for name in RUN_TEMPLATE_FILENAMES:
        assert (run_dir / name).exists()
    assert json.loads(manifest_path.read_text(encoding="utf-8"))["branch"] == state.branch


def test_task_packet_out_of_scope_paths_align_with_protected_path_matcher():
    from omni.autodev.protected_paths import match_protected_path

    task = TaskPacket(
        task_id="task-1",
        goal="Touch only omni/autodev",
        in_scope_paths=["omni/autodev/packets.py"],
        out_of_scope_paths=["backend/app/sandbox/**", "frontend/**"],
        acceptance_criteria=["packets.py adds no protected-path touches"],
        readiness_status="READY",
    )
    assert match_protected_path(task.in_scope_paths[0]) is None
    assert match_protected_path("backend/app/sandbox/limited_launcher.py") is not None


# ---------------------------------------------------------------------------
# Repair cycle 1 (Codex review): required-string emptiness, packet-version
# mismatch, duplicate acceptance-criterion identity, and repair-scope
# containment. See docs/agentic/packet_contracts.md.
# ---------------------------------------------------------------------------


def test_task_packet_rejects_empty_task_id_and_goal():
    with pytest.raises(ValueError):
        TaskPacket(task_id="", goal="g")
    with pytest.raises(ValueError):
        TaskPacket(task_id="   ", goal="g")
    with pytest.raises(ValueError):
        TaskPacket(task_id="t", goal="")


def test_run_manifest_rejects_empty_required_fields():
    with pytest.raises(ValueError):
        RunManifest(
            run_id="",
            created_at="now",
            repo_root="/repo",
            start_commit="c",
            branch="b",
            requested_operation="op",
        )
    with pytest.raises(ValueError):
        RunManifest(
            run_id="r",
            created_at="",
            repo_root="/repo",
            start_commit="c",
            branch="b",
            requested_operation="op",
        )


def test_implementation_handoff_and_review_packet_reject_empty_task_id():
    with pytest.raises(ValueError):
        ImplementationHandoff(task_id="")
    with pytest.raises(ValueError):
        ReviewPacket(task_id="", verdict="APPROVED")


def test_closeout_packet_rejects_empty_task_id():
    with pytest.raises(ValueError):
        CloseoutPacket(task_id="", final_verdict="APPROVED")


def test_task_packet_ready_without_acceptance_criteria_is_rejected():
    with pytest.raises(ValueError):
        TaskPacket(task_id="t", goal="g", readiness_status="READY")


def test_task_packet_not_ready_without_acceptance_criteria_is_allowed():
    task = TaskPacket(task_id="t", goal="g", readiness_status="NOT_READY")
    assert task.acceptance_criteria == []


def test_packet_version_mismatch_is_rejected_on_every_top_level_packet():
    with pytest.raises(ValueError):
        TaskPacket(task_id="t", goal="g", packet_version="9.9")
    with pytest.raises(ValueError):
        RunManifest(
            run_id="r", created_at="now", repo_root="/repo", start_commit="c",
            branch="b", requested_operation="op", packet_version="9.9",
        )
    with pytest.raises(ValueError):
        ImplementationHandoff(task_id="t", packet_version="9.9")
    with pytest.raises(ValueError):
        ReviewPacket(task_id="t", verdict="APPROVED", packet_version="9.9")
    with pytest.raises(ValueError):
        RepairPacket(review_cycle=1, packet_version="9.9")
    with pytest.raises(ValueError):
        CloseoutPacket(task_id="t", final_verdict="APPROVED", packet_version="9.9")


def test_packet_version_mismatch_is_rejected_on_deserialization():
    payload = to_dict(TaskPacket(task_id="t", goal="g"))
    payload["packet_version"] = "9.9"
    with pytest.raises(ValueError):
        task_packet_from_dict(payload)


def test_implementation_handoff_rejects_duplicate_acceptance_criteria():
    with pytest.raises(ValueError):
        ImplementationHandoff(
            task_id="t",
            acceptance_criterion_results=[
                AcceptanceCriterionResult(criterion="c1", status="VERIFIED"),
                AcceptanceCriterionResult(criterion="c1", status="FAILED"),
            ],
        )


def test_review_packet_rejects_duplicate_acceptance_criteria():
    with pytest.raises(ValueError):
        ReviewPacket(
            task_id="t",
            verdict="APPROVED",
            acceptance_criterion_results=[
                AcceptanceCriterionResult(criterion="c1", status="VERIFIED"),
                AcceptanceCriterionResult(criterion="c1", status="VERIFIED"),
            ],
        )


def test_validate_repair_within_task_scope_accepts_subset_of_in_scope_paths():
    task = TaskPacket(
        task_id="t",
        goal="g",
        in_scope_paths=["a.py", "b.py"],
        out_of_scope_paths=["c.py"],
    )
    repair = RepairPacket(review_cycle=1, allowed_repair_scope=["a.py"])
    validate_repair_within_task_scope(repair, task)  # does not raise


def test_validate_repair_within_task_scope_rejects_path_outside_in_scope():
    task = TaskPacket(task_id="t", goal="g", in_scope_paths=["a.py"])
    repair = RepairPacket(review_cycle=1, allowed_repair_scope=["z.py"])
    with pytest.raises(ValueError):
        validate_repair_within_task_scope(repair, task)


def test_validate_repair_within_task_scope_rejects_out_of_scope_path():
    task = TaskPacket(task_id="t", goal="g", out_of_scope_paths=["backend/app/sandbox/**"])
    repair = RepairPacket(review_cycle=1, allowed_repair_scope=["backend/app/sandbox/**"])
    with pytest.raises(ValueError):
        validate_repair_within_task_scope(repair, task)


def test_validate_repair_within_task_scope_allows_any_path_when_in_scope_unspecified():
    task = TaskPacket(task_id="t", goal="g")
    repair = RepairPacket(review_cycle=1, allowed_repair_scope=["anything.py"])
    validate_repair_within_task_scope(repair, task)  # does not raise: unconstrained task
