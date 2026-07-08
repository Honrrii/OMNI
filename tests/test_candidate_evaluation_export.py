"""
Phase 11D — Candidate evaluation export integration tests.

Tests that export_manager writes candidate_evaluation_report.json and
returns the correct summary, with failure containment.

No LLM calls. No network calls.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from agents.design_candidates import normalize_candidates


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _make_mission_result(
    mission: str = "Build a tracked ground rover for metal inspection.",
    result_id: str = "phase11d-test",
    artifacts: dict | None = None,
) -> dict:
    return {
        "mission": mission,
        "result_id": result_id,
        "final_report": "",
        "final_decision": "",
        "agents": {},
        "artifacts": artifacts or {},
        "validation": {},
        "critique": {},
        "revision": {},
        "status": "complete",
    }


def _candidate_fixtures():
    return normalize_candidates([
        {
            "name": "Tracked Crawler",
            "concept": "Magnetic tracked platform",
            "platform": "ground-rover",
            "mobility_type": "tracked",
            "morphology_notes": "Low-profile wide chassis",
            "key_components": ["magnetic tracks", "IMU", "camera"],
            "strengths": ["stable on metal"],
            "risks": [],
            "required_validation": ["torque calc"],
            "assumptions": [],
            "recommended": True,
        },
        {
            "name": "Wheeled Rover",
            "concept": "Fast wheeled platform",
            "platform": "ground-rover",
            "mobility_type": "wheeled",
            "morphology_notes": "Compact differential drive",
            "key_components": ["wheels", "encoder"],
            "strengths": ["fast"],
            "risks": ["slip on steep grade"],
            "required_validation": [],
            "assumptions": [],
            "recommended": False,
        },
        {
            "name": "Legged Walker",
            "concept": "Hexapod walker",
            "platform": "hexapod",
            "mobility_type": "legged",
            "morphology_notes": "Six-legged frame",
            "key_components": ["servos", "IMU"],
            "strengths": ["steps over obstacles"],
            "risks": ["complex gait control"],
            "required_validation": ["gait simulation"],
            "assumptions": [],
            "recommended": False,
        },
    ])


def _precomputed_evaluation(candidates):
    from agents.candidate_evaluator import evaluate_design_candidates
    return evaluate_design_candidates(candidates, mission_text="test mission")


# ---------------------------------------------------------------------------
# _write_candidate_evaluation helper — direct unit tests
# ---------------------------------------------------------------------------

class TestWriteCandidateEvaluationHelper:

    def test_writes_report_json_from_precomputed_evaluation(self, tmp_path):
        from backend.app.export.export_manager import _write_candidate_evaluation
        candidates = _candidate_fixtures()
        evaluation = _precomputed_evaluation(candidates)
        mission_result = _make_mission_result(artifacts={
            "candidate_evaluation": evaluation,
            "design_candidates": candidates,
        })
        result = _write_candidate_evaluation(tmp_path, mission_result, "test mission")
        assert (tmp_path / "candidate_evaluation_report.json").exists()
        assert result["status"] == "evaluated"

    def test_writes_report_json_from_design_candidates_only(self, tmp_path):
        from backend.app.export.export_manager import _write_candidate_evaluation
        candidates = _candidate_fixtures()
        mission_result = _make_mission_result(artifacts={"design_candidates": candidates})
        result = _write_candidate_evaluation(tmp_path, mission_result, "test mission")
        assert (tmp_path / "candidate_evaluation_report.json").exists()
        assert result["status"] == "evaluated"

    def test_writes_skipped_when_no_candidates(self, tmp_path):
        from backend.app.export.export_manager import _write_candidate_evaluation
        mission_result = _make_mission_result(artifacts={})
        result = _write_candidate_evaluation(tmp_path, mission_result, "test mission")
        assert (tmp_path / "candidate_evaluation_report.json").exists()
        assert result["status"] == "skipped"
        assert result["candidates_evaluated"] == 0
        assert result["recommended_candidate_id"] is None
        assert result["ranking"] == []

    def test_return_summary_keys_present(self, tmp_path):
        from backend.app.export.export_manager import _write_candidate_evaluation
        candidates = _candidate_fixtures()
        mission_result = _make_mission_result(artifacts={"design_candidates": candidates})
        result = _write_candidate_evaluation(tmp_path, mission_result, "test mission")
        for key in ("status", "report_path", "candidates_evaluated",
                    "recommended_candidate_id", "ranking"):
            assert key in result, f"Missing return key: {key}"

    def test_evaluated_count_matches_candidates(self, tmp_path):
        from backend.app.export.export_manager import _write_candidate_evaluation
        candidates = _candidate_fixtures()
        mission_result = _make_mission_result(artifacts={"design_candidates": candidates})
        result = _write_candidate_evaluation(tmp_path, mission_result, "test mission")
        assert result["candidates_evaluated"] == 3

    def test_ranking_is_list_of_ids(self, tmp_path):
        from backend.app.export.export_manager import _write_candidate_evaluation
        candidates = _candidate_fixtures()
        mission_result = _make_mission_result(artifacts={"design_candidates": candidates})
        result = _write_candidate_evaluation(tmp_path, mission_result, "test mission")
        assert isinstance(result["ranking"], list)
        assert len(result["ranking"]) == 3
        for cid in result["ranking"]:
            assert cid.startswith("vega_candidate_")

    def test_recommended_candidate_id_is_string(self, tmp_path):
        from backend.app.export.export_manager import _write_candidate_evaluation
        candidates = _candidate_fixtures()
        mission_result = _make_mission_result(artifacts={"design_candidates": candidates})
        result = _write_candidate_evaluation(tmp_path, mission_result, "test mission")
        assert isinstance(result["recommended_candidate_id"], str)

    def test_report_json_is_valid_json(self, tmp_path):
        from backend.app.export.export_manager import _write_candidate_evaluation
        candidates = _candidate_fixtures()
        mission_result = _make_mission_result(artifacts={"design_candidates": candidates})
        _write_candidate_evaluation(tmp_path, mission_result, "test mission")
        report = json.loads((tmp_path / "candidate_evaluation_report.json").read_text())
        assert isinstance(report, dict)

    def test_report_json_has_evaluations_list(self, tmp_path):
        from backend.app.export.export_manager import _write_candidate_evaluation
        candidates = _candidate_fixtures()
        mission_result = _make_mission_result(artifacts={"design_candidates": candidates})
        _write_candidate_evaluation(tmp_path, mission_result, "test mission")
        report = json.loads((tmp_path / "candidate_evaluation_report.json").read_text())
        assert "evaluations" in report
        assert len(report["evaluations"]) == 3

    def test_precomputed_evaluation_preferred_over_on_demand(self, tmp_path):
        """If both candidate_evaluation and design_candidates are present, use precomputed."""
        from backend.app.export.export_manager import _write_candidate_evaluation
        candidates = _candidate_fixtures()
        precomputed = _precomputed_evaluation(candidates)
        # Corrupt design_candidates so on-demand evaluation would differ
        mission_result = _make_mission_result(artifacts={
            "candidate_evaluation": precomputed,
            "design_candidates": [],  # empty — would produce 0 on-demand
        })
        result = _write_candidate_evaluation(tmp_path, mission_result, "test mission")
        # Should still use precomputed (3 candidates) not on-demand (0)
        assert result["candidates_evaluated"] == 3

    def test_empty_design_candidates_list_writes_skipped(self, tmp_path):
        from backend.app.export.export_manager import _write_candidate_evaluation
        mission_result = _make_mission_result(artifacts={"design_candidates": []})
        result = _write_candidate_evaluation(tmp_path, mission_result, "test mission")
        assert result["status"] == "skipped"


# ---------------------------------------------------------------------------
# export_mission_files integration tests
# ---------------------------------------------------------------------------

class TestExportMissionFilesIntegration:

    def test_export_writes_candidate_evaluation_report_from_candidates(self, tmp_path, monkeypatch):
        import backend.app.export.export_manager as em
        monkeypatch.setattr(em, "OUTPUT_ROOT", tmp_path / "omni_missions")
        candidates = _candidate_fixtures()
        mission_result = _make_mission_result(artifacts={"design_candidates": candidates})
        result = em.export_mission_files(mission_result, validate_ros2=False)
        export_dir = Path(result["export_dir"])
        assert (export_dir / "candidate_evaluation_report.json").exists()

    def test_export_writes_candidate_evaluation_report_from_precomputed(self, tmp_path, monkeypatch):
        import backend.app.export.export_manager as em
        monkeypatch.setattr(em, "OUTPUT_ROOT", tmp_path / "omni_missions")
        candidates = _candidate_fixtures()
        evaluation = _precomputed_evaluation(candidates)
        mission_result = _make_mission_result(artifacts={
            "candidate_evaluation": evaluation,
            "design_candidates": candidates,
        })
        result = em.export_mission_files(mission_result, validate_ros2=False)
        export_dir = Path(result["export_dir"])
        assert (export_dir / "candidate_evaluation_report.json").exists()

    def test_export_return_has_cortex_candidate_evaluation_key(self, tmp_path, monkeypatch):
        import backend.app.export.export_manager as em
        monkeypatch.setattr(em, "OUTPUT_ROOT", tmp_path / "omni_missions")
        candidates = _candidate_fixtures()
        mission_result = _make_mission_result(artifacts={"design_candidates": candidates})
        result = em.export_mission_files(mission_result, validate_ros2=False)
        assert "cortex" in result
        assert "candidate_evaluation" in result["cortex"]

    def test_export_candidate_evaluation_status_evaluated(self, tmp_path, monkeypatch):
        import backend.app.export.export_manager as em
        monkeypatch.setattr(em, "OUTPUT_ROOT", tmp_path / "omni_missions")
        candidates = _candidate_fixtures()
        mission_result = _make_mission_result(artifacts={"design_candidates": candidates})
        result = em.export_mission_files(mission_result, validate_ros2=False)
        ce = result["cortex"]["candidate_evaluation"]
        assert ce["status"] == "evaluated"
        assert ce["candidates_evaluated"] == 3
        assert isinstance(ce["recommended_candidate_id"], str)
        assert isinstance(ce["ranking"], list)

    def test_export_missing_candidates_does_not_break_export(self, tmp_path, monkeypatch):
        import backend.app.export.export_manager as em
        monkeypatch.setattr(em, "OUTPUT_ROOT", tmp_path / "omni_missions")
        mission_result = _make_mission_result(artifacts={})
        result = em.export_mission_files(mission_result, validate_ros2=False)
        assert result["status"] == "exported"
        ce = result["cortex"]["candidate_evaluation"]
        assert ce["status"] == "skipped"

    def test_export_evaluator_failure_is_contained(self, tmp_path, monkeypatch):
        """If evaluate_design_candidates raises, export still completes with failed status."""
        import backend.app.export.export_manager as em
        import agents.candidate_evaluator as ace
        monkeypatch.setattr(em, "OUTPUT_ROOT", tmp_path / "omni_missions")

        def _explode(*args, **kwargs):
            raise RuntimeError("evaluator deliberately exploded")

        monkeypatch.setattr(ace, "evaluate_design_candidates", _explode)

        candidates = _candidate_fixtures()
        mission_result = _make_mission_result(artifacts={"design_candidates": candidates})
        result = em.export_mission_files(mission_result, validate_ros2=False)

        assert result["status"] == "exported"
        ce = result["cortex"]["candidate_evaluation"]
        assert ce["status"] == "failed"
        assert "error" in ce

    def test_export_candidate_evaluation_report_in_files_list(self, tmp_path, monkeypatch):
        import backend.app.export.export_manager as em
        monkeypatch.setattr(em, "OUTPUT_ROOT", tmp_path / "omni_missions")
        candidates = _candidate_fixtures()
        mission_result = _make_mission_result(artifacts={"design_candidates": candidates})
        result = em.export_mission_files(mission_result, validate_ros2=False)
        files = result["files"]
        assert any("candidate_evaluation_report.json" in f for f in files)

    def test_export_preserves_graph_review_key(self, tmp_path, monkeypatch):
        """Adding candidate_evaluation must not remove graph_review from return dict."""
        import backend.app.export.export_manager as em
        monkeypatch.setattr(em, "OUTPUT_ROOT", tmp_path / "omni_missions")
        mission_result = _make_mission_result()
        result = em.export_mission_files(mission_result, validate_ros2=False)
        assert "graph_review" in result

    def test_export_preserves_design_understanding_key(self, tmp_path, monkeypatch):
        """cortex.design_understanding must still be present alongside candidate_evaluation."""
        import backend.app.export.export_manager as em
        monkeypatch.setattr(em, "OUTPUT_ROOT", tmp_path / "omni_missions")
        mission_result = _make_mission_result()
        result = em.export_mission_files(mission_result, validate_ros2=False)
        assert "design_understanding" in result["cortex"]

    def test_export_design_understanding_report_still_written(self, tmp_path, monkeypatch):
        import backend.app.export.export_manager as em
        monkeypatch.setattr(em, "OUTPUT_ROOT", tmp_path / "omni_missions")
        mission_result = _make_mission_result(
            mission="Build a rover for terrain survey."
        )
        result = em.export_mission_files(mission_result, validate_ros2=False)
        export_dir = Path(result["export_dir"])
        assert (export_dir / "design_understanding_report.json").exists()
