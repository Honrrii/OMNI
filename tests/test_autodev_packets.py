"""
Phase 11+ guard: OMNI Auto Dev structured production-packet contracts
(omni/autodev/packets.py) validate correctly, serialize round-trip, cap
repair cycles, bind repairs to their task, enforce path-scope semantics,
represent timeouts distinctly from pass/fail, and require meaningful
evidence for an approved closeout. No network, no LLM calls, no GitHub
API, no autonomous execution — these tests only exercise plain dataclasses.
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
from omni.autodev.protected_paths import spec_matches


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
    repair = RepairPacket(task_id="task-1", review_cycle=1, required_actions=["fix X"])
    assert repair.review_cycle == 1
    assert repair.task_id == "task-1"

    closeout = CloseoutPacket(task_id="task-1", final_verdict="BLOCKED")
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


def test_repair_packet_rejects_missing_task_id():
    with pytest.raises(TypeError):
        RepairPacket(review_cycle=1)  # missing task_id


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
    repair = RepairPacket(task_id="task-1", review_cycle=2, required_actions=["address finding 1"])
    restored = repair_packet_from_dict(to_dict(repair))
    assert restored == repair
    assert restored.task_id == "task-1"


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
        recommended_pr_body="Implements the structured packet contracts.",
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
    repair = RepairPacket(task_id="t", review_cycle=1)
    closeout = CloseoutPacket(task_id="t", final_verdict="BLOCKED")
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
        RepairPacket(task_id="t", review_cycle=0)


def test_repair_packet_rejects_review_cycle_beyond_max():
    with pytest.raises(ValueError):
        RepairPacket(task_id="t", review_cycle=MAX_REPAIR_CYCLES + 1)


def test_repair_packet_accepts_every_cycle_up_to_max():
    for cycle in range(1, MAX_REPAIR_CYCLES + 1):
        RepairPacket(task_id="t", review_cycle=cycle)


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

    repair_a = RepairPacket(task_id="a", review_cycle=1)
    repair_b = RepairPacket(task_id="b", review_cycle=1)
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
# mismatch, duplicate acceptance-criterion identity. See
# docs/agentic/packet_contracts.md.
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
        CloseoutPacket(task_id="", final_verdict="BLOCKED")


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
        RepairPacket(task_id="t", review_cycle=1, packet_version="9.9")
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


# ---------------------------------------------------------------------------
# Repair cycle 2 (Codex review), Finding 1: acceptance-criterion identity is
# a validated, trimmed string — empty, whitespace-only, and duplicate (after
# trimming) entries are all rejected, for both TaskPacket.acceptance_criteria
# (plain strings) and AcceptanceCriterionResult.criterion (a result record).
# ---------------------------------------------------------------------------


def test_task_packet_acceptance_criteria_rejects_empty_string_entry():
    with pytest.raises(ValueError):
        TaskPacket(task_id="t", goal="g", acceptance_criteria=[""])


def test_task_packet_acceptance_criteria_rejects_whitespace_only_entry():
    with pytest.raises(ValueError):
        TaskPacket(task_id="t", goal="g", acceptance_criteria=["   "])


def test_task_packet_acceptance_criteria_rejects_mixed_valid_and_empty():
    with pytest.raises(ValueError):
        TaskPacket(task_id="t", goal="g", acceptance_criteria=["criterion", ""])


def test_task_packet_acceptance_criteria_rejects_duplicate_after_trimming():
    with pytest.raises(ValueError):
        TaskPacket(task_id="t", goal="g", acceptance_criteria=["criterion", " criterion "])


def test_task_packet_acceptance_criteria_accepts_distinct_valid_entries():
    task = TaskPacket(
        task_id="t", goal="g", acceptance_criteria=["criterion one", "criterion two"]
    )
    assert task.acceptance_criteria == ["criterion one", "criterion two"]


def test_acceptance_criterion_result_rejects_empty_criterion_direct_construction():
    with pytest.raises(ValueError):
        AcceptanceCriterionResult(criterion="", status="VERIFIED")


def test_acceptance_criterion_result_rejects_whitespace_criterion_direct_construction():
    with pytest.raises(ValueError):
        AcceptanceCriterionResult(criterion="   ", status="VERIFIED")


def test_implementation_handoff_rejects_duplicate_result_criteria_after_trimming():
    with pytest.raises(ValueError):
        ImplementationHandoff(
            task_id="t",
            acceptance_criterion_results=[
                AcceptanceCriterionResult(criterion="c1", status="VERIFIED"),
                AcceptanceCriterionResult(criterion=" c1 ", status="FAILED"),
            ],
        )


def test_review_packet_rejects_duplicate_result_criteria_after_trimming():
    with pytest.raises(ValueError):
        ReviewPacket(
            task_id="t",
            verdict="APPROVED",
            acceptance_criterion_results=[
                AcceptanceCriterionResult(criterion="c1", status="VERIFIED"),
                AcceptanceCriterionResult(criterion=" c1 ", status="VERIFIED"),
            ],
        )


def test_acceptance_criterion_result_validation_applies_through_deserialization():
    payload = to_dict(
        ImplementationHandoff(
            task_id="t",
            acceptance_criterion_results=[
                AcceptanceCriterionResult(criterion="c1", status="VERIFIED")
            ],
        )
    )
    payload["acceptance_criterion_results"][0]["criterion"] = "   "
    with pytest.raises(ValueError):
        implementation_handoff_from_dict(payload)


# ---------------------------------------------------------------------------
# Repair cycle 2, Finding 2: path-scope semantics. TaskPacket in/out-of-scope
# fields are literal/prefix/glob scope specifications; RepairPacket.
# allowed_repair_scope must be concrete repository-relative paths.
# ---------------------------------------------------------------------------


def test_repair_packet_rejects_glob_in_allowed_repair_scope():
    with pytest.raises(ValueError):
        RepairPacket(task_id="t", review_cycle=1, allowed_repair_scope=["omni/autodev/**"])


def test_repair_packet_rejects_malformed_path_in_allowed_repair_scope():
    with pytest.raises(ValueError):
        RepairPacket(task_id="t", review_cycle=1, allowed_repair_scope=["../escape.py"])
    with pytest.raises(ValueError):
        RepairPacket(task_id="t", review_cycle=1, allowed_repair_scope=["/absolute/path.py"])


def test_repair_packet_accepts_concrete_windows_separated_path():
    repair = RepairPacket(
        task_id="t", review_cycle=1, allowed_repair_scope=["omni\\autodev\\packets.py"]
    )
    assert repair.allowed_repair_scope == ["omni\\autodev\\packets.py"]  # preserved verbatim


def _scoped_task_and_repair(*, in_scope=(), out_of_scope=(), candidate):
    task = TaskPacket(
        task_id="t", goal="g", in_scope_paths=list(in_scope), out_of_scope_paths=list(out_of_scope)
    )
    repair = RepairPacket(task_id="t", review_cycle=1, allowed_repair_scope=[candidate])
    return task, repair


def test_scope_glob_in_scope_allows_descendant():
    task, repair = _scoped_task_and_repair(
        in_scope=["omni/autodev/**"], candidate="omni/autodev/packets.py"
    )
    validate_repair_within_task_scope(repair, task)  # does not raise


def test_scope_glob_out_of_scope_rejects_descendant():
    task, repair = _scoped_task_and_repair(
        out_of_scope=["frontend/**"], candidate="frontend/src/App.jsx"
    )
    with pytest.raises(ValueError):
        validate_repair_within_task_scope(repair, task)


def test_scope_directory_prefix_in_scope_allows_descendant():
    task, repair = _scoped_task_and_repair(
        in_scope=["omni/autodev"], candidate="omni/autodev/packets.py"
    )
    validate_repair_within_task_scope(repair, task)  # does not raise


def test_scope_literal_in_scope_allows_exact_match():
    task, repair = _scoped_task_and_repair(
        in_scope=["omni/autodev/packets.py"], candidate="omni/autodev/packets.py"
    )
    validate_repair_within_task_scope(repair, task)  # does not raise


def test_scope_glob_in_scope_rejects_lookalike_sibling_directory():
    task, repair = _scoped_task_and_repair(
        in_scope=["omni/autodev/**"], candidate="omni/autodev_extra/file.py"
    )
    with pytest.raises(ValueError):
        validate_repair_within_task_scope(repair, task)


def test_scope_glob_out_of_scope_allows_lookalike_sibling_directory():
    task, repair = _scoped_task_and_repair(
        out_of_scope=["frontend/**"], candidate="frontendish/file.py"
    )
    validate_repair_within_task_scope(repair, task)  # does not raise


def test_spec_matches_directly_for_the_same_six_scenarios():
    assert spec_matches("omni/autodev/**", "omni/autodev/packets.py") is True
    assert spec_matches("frontend/**", "frontend/src/App.jsx") is True
    assert spec_matches("omni/autodev", "omni/autodev/packets.py") is True
    assert spec_matches("omni/autodev/packets.py", "omni/autodev/packets.py") is True
    assert spec_matches("omni/autodev/**", "omni/autodev_extra/file.py") is False
    assert spec_matches("frontend/**", "frontendish/file.py") is False


def test_validate_repair_within_task_scope_accepts_subset_of_in_scope_paths():
    task = TaskPacket(
        task_id="t",
        goal="g",
        in_scope_paths=["a.py", "b.py"],
        out_of_scope_paths=["c.py"],
    )
    repair = RepairPacket(task_id="t", review_cycle=1, allowed_repair_scope=["a.py"])
    validate_repair_within_task_scope(repair, task)  # does not raise


def test_validate_repair_within_task_scope_rejects_path_outside_in_scope():
    task = TaskPacket(task_id="t", goal="g", in_scope_paths=["a.py"])
    repair = RepairPacket(task_id="t", review_cycle=1, allowed_repair_scope=["z.py"])
    with pytest.raises(ValueError):
        validate_repair_within_task_scope(repair, task)


def test_validate_repair_within_task_scope_rejects_out_of_scope_path():
    task = TaskPacket(task_id="t", goal="g", out_of_scope_paths=["backend/app/sandbox/**"])
    repair = RepairPacket(
        task_id="t", review_cycle=1, allowed_repair_scope=["backend/app/sandbox/file.py"]
    )
    with pytest.raises(ValueError):
        validate_repair_within_task_scope(repair, task)


def test_validate_repair_within_task_scope_allows_any_path_when_in_scope_unspecified():
    task = TaskPacket(task_id="t", goal="g")
    repair = RepairPacket(task_id="t", review_cycle=1, allowed_repair_scope=["anything.py"])
    validate_repair_within_task_scope(repair, task)  # does not raise: unconstrained task


# ---------------------------------------------------------------------------
# Repair cycle 2, Finding 3: a repair packet is bound to its task by task_id.
# ---------------------------------------------------------------------------


def test_repair_packet_rejects_empty_task_id():
    with pytest.raises(ValueError):
        RepairPacket(task_id="", review_cycle=1)


def test_repair_packet_rejects_whitespace_task_id():
    with pytest.raises(ValueError):
        RepairPacket(task_id="   ", review_cycle=1)


def test_validate_repair_within_task_scope_accepts_matching_task_id():
    task = TaskPacket(task_id="task-1", goal="g")
    repair = RepairPacket(task_id="task-1", review_cycle=1)
    validate_repair_within_task_scope(repair, task)  # does not raise


def test_validate_repair_within_task_scope_rejects_different_task_id():
    task = TaskPacket(task_id="task-1", goal="g")
    repair = RepairPacket(task_id="task-2", review_cycle=1)
    with pytest.raises(ValueError):
        validate_repair_within_task_scope(repair, task)


def test_validate_repair_within_task_scope_checks_identity_before_path_containment():
    # Paths would satisfy containment (in_scope_paths permits it), but the
    # task_id mismatch must still be what's reported: identity is checked
    # first, so this must raise on the task_id mismatch, not silently pass
    # on paths.
    task = TaskPacket(task_id="task-1", goal="g", in_scope_paths=["a.py"])
    repair = RepairPacket(task_id="task-2", review_cycle=1, allowed_repair_scope=["a.py"])
    with pytest.raises(ValueError, match="task_id"):
        validate_repair_within_task_scope(repair, task)


def test_repair_packet_task_id_round_trips_through_dict():
    repair = RepairPacket(task_id="task-1", review_cycle=1, allowed_repair_scope=["a.py"])
    restored = repair_packet_from_dict(to_dict(repair))
    assert restored.task_id == "task-1"
    assert restored == repair


def test_repair_packet_from_dict_validates_task_id():
    payload = to_dict(RepairPacket(task_id="task-1", review_cycle=1))
    payload["task_id"] = ""
    with pytest.raises(ValueError):
        repair_packet_from_dict(payload)


# ---------------------------------------------------------------------------
# Repair cycle 2, Finding 5: an APPROVED closeout requires meaningful
# completion evidence; human_approval_required must be exactly True.
# ---------------------------------------------------------------------------


def _minimal_approved_closeout(**overrides) -> CloseoutPacket:
    kwargs = dict(
        task_id="t",
        final_verdict="APPROVED",
        completed_acceptance_criteria=["criterion one"],
        final_test_evidence=[
            TestEvidence(command="pytest", working_dir="/repo", outcome="passed", exit_code=0)
        ],
        commit_sha="abc123",
        branch="main",
        recommended_pr_title="Title",
        recommended_pr_body="Body",
    )
    kwargs.update(overrides)
    return CloseoutPacket(**kwargs)


def test_closeout_packet_minimal_valid_approved():
    closeout = _minimal_approved_closeout()
    assert closeout.final_verdict == "APPROVED"


def test_closeout_packet_approved_rejects_empty_branch():
    with pytest.raises(ValueError):
        _minimal_approved_closeout(branch="")


def test_closeout_packet_approved_rejects_empty_commit_sha():
    with pytest.raises(ValueError):
        _minimal_approved_closeout(commit_sha="")


def test_closeout_packet_approved_rejects_empty_completed_criteria():
    with pytest.raises(ValueError):
        _minimal_approved_closeout(completed_acceptance_criteria=[])


def test_closeout_packet_approved_rejects_whitespace_criterion():
    with pytest.raises(ValueError):
        _minimal_approved_closeout(completed_acceptance_criteria=["   "])


def test_closeout_packet_approved_rejects_empty_final_test_evidence():
    with pytest.raises(ValueError):
        _minimal_approved_closeout(final_test_evidence=[])


def test_closeout_packet_approved_rejects_timeout_evidence():
    with pytest.raises(ValueError):
        _minimal_approved_closeout(
            final_test_evidence=[
                TestEvidence(
                    command="pytest", working_dir="/repo", outcome="timeout",
                    output_summary="hung",
                )
            ]
        )


def test_closeout_packet_approved_rejects_empty_pr_title():
    with pytest.raises(ValueError):
        _minimal_approved_closeout(recommended_pr_title="")


def test_closeout_packet_approved_rejects_empty_pr_body():
    with pytest.raises(ValueError):
        _minimal_approved_closeout(recommended_pr_body="")


def test_closeout_packet_rejects_human_approval_required_false():
    with pytest.raises(ValueError):
        CloseoutPacket(task_id="t", final_verdict="BLOCKED", human_approval_required=False)


def test_closeout_packet_rejects_human_approval_required_truthy_int():
    with pytest.raises(ValueError):
        CloseoutPacket(task_id="t", final_verdict="BLOCKED", human_approval_required=1)


def test_closeout_packet_rejects_human_approval_required_truthy_string():
    with pytest.raises(ValueError):
        CloseoutPacket(task_id="t", final_verdict="BLOCKED", human_approval_required="yes")


def test_closeout_packet_accepts_human_approval_required_true():
    closeout = CloseoutPacket(task_id="t", final_verdict="BLOCKED", human_approval_required=True)
    assert closeout.human_approval_required is True


def test_closeout_packet_non_approved_does_not_require_completion_evidence():
    for verdict in ("CHANGES_REQUIRED", "BLOCKED"):
        closeout = CloseoutPacket(task_id="t", final_verdict=verdict)
        assert closeout.branch == ""
        assert closeout.commit_sha == ""
        assert closeout.completed_acceptance_criteria == []
        assert closeout.final_test_evidence == []


def test_closeout_packet_approved_evidence_requirements_apply_through_deserialization():
    payload = to_dict(_minimal_approved_closeout())
    payload["branch"] = ""
    with pytest.raises(ValueError):
        closeout_packet_from_dict(payload)


def test_closeout_packet_approved_round_trips_with_full_evidence():
    closeout = _minimal_approved_closeout()
    restored = closeout_packet_from_dict(to_dict(closeout))
    assert restored == closeout
