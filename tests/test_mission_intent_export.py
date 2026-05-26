"""
Phase 12B — Mission intent export integration tests.

Tests that export_manager writes mission_intent_report.json and returns
the correct cortex.mission_intent summary, with failure containment.

No LLM calls. No network calls.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _make_mission_result(
    mission: str = "Build a magnetic tracked rover for metal surface inspection.",
    result_id: str = "phase12b-test",
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


def _precomputed_intent(mission: str) -> dict:
    from backend.app.omni_core.mission_intent import compile_mission_intent
    return compile_mission_intent(mission)


# ---------------------------------------------------------------------------
# _write_mission_intent helper — direct unit tests
# ---------------------------------------------------------------------------

class TestWriteMissionIntentHelper:

    def test_writes_report_json_from_precomputed_intent(self, tmp_path):
        from backend.app.export.export_manager import _write_mission_intent
        mission = "Build a magnetic tracked rover for metal surface inspection."
        intent = _precomputed_intent(mission)
        mission_result = _make_mission_result(
            mission=mission,
            artifacts={"mission_intent": intent},
        )
        result = _write_mission_intent(tmp_path, mission_result, mission)
        assert (tmp_path / "mission_intent_report.json").exists()
        assert result["status"] == "compiled"

    def test_writes_report_json_on_demand_when_no_artifact(self, tmp_path):
        from backend.app.export.export_manager import _write_mission_intent
        mission = "Build a magnetic tracked rover for metal surface inspection."
        mission_result = _make_mission_result(mission=mission, artifacts={})
        result = _write_mission_intent(tmp_path, mission_result, mission)
        assert (tmp_path / "mission_intent_report.json").exists()
        assert result["status"] == "compiled"

    def test_return_summary_keys_present(self, tmp_path):
        from backend.app.export.export_manager import _write_mission_intent
        mission = "Build a magnetic tracked rover for metal surface inspection."
        mission_result = _make_mission_result(mission=mission, artifacts={})
        result = _write_mission_intent(tmp_path, mission_result, mission)
        for key in ("status", "report_path", "mission_type", "platform_intent",
                    "detected_domain_count", "open_question_count"):
            assert key in result, f"Missing return key: {key}"

    def test_mission_type_is_string(self, tmp_path):
        from backend.app.export.export_manager import _write_mission_intent
        mission = "Build a magnetic tracked rover for metal surface inspection."
        mission_result = _make_mission_result(mission=mission, artifacts={})
        result = _write_mission_intent(tmp_path, mission_result, mission)
        assert isinstance(result["mission_type"], str)

    def test_platform_intent_is_string_for_rover_mission(self, tmp_path):
        from backend.app.export.export_manager import _write_mission_intent
        mission = "Build a magnetic tracked rover for metal surface inspection."
        mission_result = _make_mission_result(mission=mission, artifacts={})
        result = _write_mission_intent(tmp_path, mission_result, mission)
        assert result["platform_intent"] == "ground-rover"

    def test_detected_domain_count_is_int(self, tmp_path):
        from backend.app.export.export_manager import _write_mission_intent
        mission = "Build a magnetic tracked rover for metal surface inspection."
        mission_result = _make_mission_result(mission=mission, artifacts={})
        result = _write_mission_intent(tmp_path, mission_result, mission)
        assert isinstance(result["detected_domain_count"], int)

    def test_open_question_count_is_int(self, tmp_path):
        from backend.app.export.export_manager import _write_mission_intent
        mission = "Build a magnetic tracked rover for metal surface inspection."
        mission_result = _make_mission_result(mission=mission, artifacts={})
        result = _write_mission_intent(tmp_path, mission_result, mission)
        assert isinstance(result["open_question_count"], int)

    def test_report_json_is_valid_json(self, tmp_path):
        from backend.app.export.export_manager import _write_mission_intent
        mission = "Build a magnetic tracked rover for metal surface inspection."
        mission_result = _make_mission_result(mission=mission, artifacts={})
        _write_mission_intent(tmp_path, mission_result, mission)
        report = json.loads((tmp_path / "mission_intent_report.json").read_text())
        assert isinstance(report, dict)

    def test_report_json_has_required_fields(self, tmp_path):
        from backend.app.export.export_manager import _write_mission_intent
        mission = "Build a magnetic tracked rover for metal surface inspection."
        mission_result = _make_mission_result(mission=mission, artifacts={})
        _write_mission_intent(tmp_path, mission_result, mission)
        report = json.loads((tmp_path / "mission_intent_report.json").read_text())
        for key in ("mission_type", "platform_intent", "required_outputs", "open_questions"):
            assert key in report, f"Missing field in report JSON: {key}"

    def test_precomputed_intent_preferred_over_on_demand(self, tmp_path):
        """If artifacts["mission_intent"] is present and valid, use it; don't recompile."""
        from backend.app.export.export_manager import _write_mission_intent
        precomputed = _precomputed_intent(
            "Build a magnetic tracked rover for metal surface inspection."
        )
        # Provide a different mission_text so on-demand would produce a different result
        mission_result = _make_mission_result(
            mission="some completely different vague task",
            artifacts={"mission_intent": precomputed},
        )
        result = _write_mission_intent(
            tmp_path, mission_result,
            "some completely different vague task"
        )
        # Should still use precomputed (ground-rover) not on-demand (None)
        assert result["platform_intent"] == "ground-rover"

    def test_invalid_precomputed_intent_falls_back_to_on_demand(self, tmp_path):
        """A stored intent with no mission_type triggers on-demand recompilation."""
        from backend.app.export.export_manager import _write_mission_intent
        mission = "Build an aerial drone UAV for outdoor survey."
        bad_artifact = {"something_else": True}  # no mission_type key
        mission_result = _make_mission_result(
            mission=mission,
            artifacts={"mission_intent": bad_artifact},
        )
        result = _write_mission_intent(tmp_path, mission_result, mission)
        assert result["status"] == "compiled"
        assert result["platform_intent"] == "drone-uav"


# ---------------------------------------------------------------------------
# export_mission_files integration tests
# ---------------------------------------------------------------------------

class TestExportMissionFilesIntegration:

    def test_export_writes_mission_intent_report_on_demand(self, tmp_path, monkeypatch):
        import backend.app.export.export_manager as em
        monkeypatch.setattr(em, "OUTPUT_ROOT", tmp_path / "omni_missions")
        mission_result = _make_mission_result(artifacts={})
        result = em.export_mission_files(mission_result, validate_ros2=False)
        export_dir = Path(result["export_dir"])
        assert (export_dir / "mission_intent_report.json").exists()

    def test_export_writes_mission_intent_report_from_precomputed(self, tmp_path, monkeypatch):
        import backend.app.export.export_manager as em
        monkeypatch.setattr(em, "OUTPUT_ROOT", tmp_path / "omni_missions")
        mission = "Build a magnetic tracked rover for metal surface inspection."
        intent = _precomputed_intent(mission)
        mission_result = _make_mission_result(
            mission=mission,
            artifacts={"mission_intent": intent},
        )
        result = em.export_mission_files(mission_result, validate_ros2=False)
        export_dir = Path(result["export_dir"])
        assert (export_dir / "mission_intent_report.json").exists()

    def test_export_return_has_cortex_mission_intent_key(self, tmp_path, monkeypatch):
        import backend.app.export.export_manager as em
        monkeypatch.setattr(em, "OUTPUT_ROOT", tmp_path / "omni_missions")
        mission_result = _make_mission_result(artifacts={})
        result = em.export_mission_files(mission_result, validate_ros2=False)
        assert "cortex" in result
        assert "mission_intent" in result["cortex"]

    def test_export_mission_intent_status_compiled(self, tmp_path, monkeypatch):
        import backend.app.export.export_manager as em
        monkeypatch.setattr(em, "OUTPUT_ROOT", tmp_path / "omni_missions")
        mission_result = _make_mission_result(artifacts={})
        result = em.export_mission_files(mission_result, validate_ros2=False)
        mi = result["cortex"]["mission_intent"]
        assert mi["status"] == "compiled"
        assert isinstance(mi["mission_type"], str)
        assert isinstance(mi["detected_domain_count"], int)
        assert isinstance(mi["open_question_count"], int)

    def test_export_mission_intent_platform_intent_for_rover(self, tmp_path, monkeypatch):
        import backend.app.export.export_manager as em
        monkeypatch.setattr(em, "OUTPUT_ROOT", tmp_path / "omni_missions")
        mission = "Build a magnetic tracked rover for metal surface inspection."
        mission_result = _make_mission_result(mission=mission, artifacts={})
        result = em.export_mission_files(mission_result, validate_ros2=False)
        mi = result["cortex"]["mission_intent"]
        assert mi["platform_intent"] == "ground-rover"

    def test_export_compiler_failure_is_contained(self, tmp_path, monkeypatch):
        """If compile_mission_intent raises, export still completes with failed status."""
        import backend.app.export.export_manager as em
        import backend.app.omni_core.mission_intent as mic
        monkeypatch.setattr(em, "OUTPUT_ROOT", tmp_path / "omni_missions")

        def _explode(*args, **kwargs):
            raise RuntimeError("compiler deliberately exploded")

        monkeypatch.setattr(mic, "compile_mission_intent", _explode)

        mission_result = _make_mission_result(artifacts={})
        result = em.export_mission_files(mission_result, validate_ros2=False)

        assert result["status"] == "exported"
        mi = result["cortex"]["mission_intent"]
        assert mi["status"] == "failed"
        assert "error" in mi

    def test_export_compiler_failure_writes_failed_json(self, tmp_path, monkeypatch):
        import backend.app.export.export_manager as em
        import backend.app.omni_core.mission_intent as mic
        monkeypatch.setattr(em, "OUTPUT_ROOT", tmp_path / "omni_missions")

        def _explode(*args, **kwargs):
            raise RuntimeError("compiler deliberately exploded")

        monkeypatch.setattr(mic, "compile_mission_intent", _explode)

        mission_result = _make_mission_result(artifacts={})
        result = em.export_mission_files(mission_result, validate_ros2=False)
        export_dir = Path(result["export_dir"])
        assert (export_dir / "mission_intent_report.json").exists()
        report = json.loads((export_dir / "mission_intent_report.json").read_text())
        assert report["status"] == "failed"

    def test_export_mission_intent_report_in_files_list(self, tmp_path, monkeypatch):
        import backend.app.export.export_manager as em
        monkeypatch.setattr(em, "OUTPUT_ROOT", tmp_path / "omni_missions")
        mission_result = _make_mission_result(artifacts={})
        result = em.export_mission_files(mission_result, validate_ros2=False)
        assert any("mission_intent_report.json" in f for f in result["files"])

    def test_export_preserves_graph_review_key(self, tmp_path, monkeypatch):
        import backend.app.export.export_manager as em
        monkeypatch.setattr(em, "OUTPUT_ROOT", tmp_path / "omni_missions")
        mission_result = _make_mission_result()
        result = em.export_mission_files(mission_result, validate_ros2=False)
        assert "graph_review" in result

    def test_export_preserves_design_understanding_key(self, tmp_path, monkeypatch):
        import backend.app.export.export_manager as em
        monkeypatch.setattr(em, "OUTPUT_ROOT", tmp_path / "omni_missions")
        mission_result = _make_mission_result()
        result = em.export_mission_files(mission_result, validate_ros2=False)
        assert "design_understanding" in result["cortex"]

    def test_export_preserves_candidate_evaluation_key(self, tmp_path, monkeypatch):
        import backend.app.export.export_manager as em
        monkeypatch.setattr(em, "OUTPUT_ROOT", tmp_path / "omni_missions")
        mission_result = _make_mission_result()
        result = em.export_mission_files(mission_result, validate_ros2=False)
        assert "candidate_evaluation" in result["cortex"]
