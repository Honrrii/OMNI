"""
Phase 13B — Pluto safety gate export integration tests.

Tests that export_manager writes pluto_safety_gate_report.json and returns
the correct cortex.pluto_safety_gate summary, with failure containment.

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
    result_id: str = "phase13b-test",
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


def _rover_intent() -> dict:
    return {
        "raw_mission": "Build a tracked ground rover with camera and IMU. Battery powered.",
        "mission_type": "inspection",
        "platform_intent": "ground-rover",
        "safety_mode": "elevated",
        "detected_domains": ["robotics", "CAD"],
        "sensing_requirements": ["camera", "IMU"],
        "required_outputs": ["ROS2 package", "validation checklist"],
        "constraints": ["battery / power source"],
        "open_questions": [],
    }


def _precomputed_gate(mission_intent: dict) -> dict:
    from backend.app.omni_core.safety_gate import evaluate_safety_gate
    return evaluate_safety_gate(mission_intent=mission_intent)


# ---------------------------------------------------------------------------
# _write_pluto_safety_gate helper — direct unit tests
# ---------------------------------------------------------------------------

class TestWritePlutoSafetyGateHelper:

    def test_writes_report_json_from_precomputed_gate(self, tmp_path):
        from backend.app.export.export_manager import _write_pluto_safety_gate
        intent = _rover_intent()
        gate = _precomputed_gate(intent)
        mission_result = _make_mission_result(artifacts={
            "mission_intent": intent,
            "pluto_safety_gate": gate,
        })
        result = _write_pluto_safety_gate(tmp_path, mission_result)
        assert (tmp_path / "pluto_safety_gate_report.json").exists()
        assert result["status"] in ("passed", "warn", "blocked")

    def test_writes_report_json_on_demand_from_mission_intent(self, tmp_path):
        from backend.app.export.export_manager import _write_pluto_safety_gate
        intent = _rover_intent()
        mission_result = _make_mission_result(artifacts={"mission_intent": intent})
        result = _write_pluto_safety_gate(tmp_path, mission_result)
        assert (tmp_path / "pluto_safety_gate_report.json").exists()
        assert result["status"] in ("passed", "warn", "blocked")

    def test_writes_report_json_with_empty_artifacts(self, tmp_path):
        from backend.app.export.export_manager import _write_pluto_safety_gate
        mission_result = _make_mission_result(artifacts={})
        result = _write_pluto_safety_gate(tmp_path, mission_result)
        assert (tmp_path / "pluto_safety_gate_report.json").exists()
        assert result["status"] in ("passed", "warn", "blocked")

    def test_return_summary_keys_present(self, tmp_path):
        from backend.app.export.export_manager import _write_pluto_safety_gate
        mission_result = _make_mission_result(artifacts={"mission_intent": _rover_intent()})
        result = _write_pluto_safety_gate(tmp_path, mission_result)
        for key in ("status", "report_path", "risk_level", "required_human_review",
                    "blocker_count", "warning_count", "next_check_count"):
            assert key in result, f"Missing return key: {key}"

    def test_risk_level_is_string(self, tmp_path):
        from backend.app.export.export_manager import _write_pluto_safety_gate
        mission_result = _make_mission_result(artifacts={"mission_intent": _rover_intent()})
        result = _write_pluto_safety_gate(tmp_path, mission_result)
        assert isinstance(result["risk_level"], str)

    def test_required_human_review_is_bool(self, tmp_path):
        from backend.app.export.export_manager import _write_pluto_safety_gate
        mission_result = _make_mission_result(artifacts={"mission_intent": _rover_intent()})
        result = _write_pluto_safety_gate(tmp_path, mission_result)
        assert isinstance(result["required_human_review"], bool)

    def test_counts_are_ints(self, tmp_path):
        from backend.app.export.export_manager import _write_pluto_safety_gate
        mission_result = _make_mission_result(artifacts={"mission_intent": _rover_intent()})
        result = _write_pluto_safety_gate(tmp_path, mission_result)
        for key in ("blocker_count", "warning_count", "next_check_count"):
            assert isinstance(result[key], int), f"{key} should be int"

    def test_report_json_is_valid_json(self, tmp_path):
        from backend.app.export.export_manager import _write_pluto_safety_gate
        mission_result = _make_mission_result(artifacts={"mission_intent": _rover_intent()})
        _write_pluto_safety_gate(tmp_path, mission_result)
        report = json.loads((tmp_path / "pluto_safety_gate_report.json").read_text())
        assert isinstance(report, dict)

    def test_report_json_has_required_fields(self, tmp_path):
        from backend.app.export.export_manager import _write_pluto_safety_gate
        mission_result = _make_mission_result(artifacts={"mission_intent": _rover_intent()})
        _write_pluto_safety_gate(tmp_path, mission_result)
        report = json.loads((tmp_path / "pluto_safety_gate_report.json").read_text())
        for key in ("status", "risk_level", "blockers", "warnings",
                    "required_human_review", "required_next_checks", "rationale"):
            assert key in report, f"Missing field in report JSON: {key}"

    def test_precomputed_gate_preferred_over_on_demand(self, tmp_path):
        """If artifacts["pluto_safety_gate"] is present and valid, use it."""
        from backend.app.export.export_manager import _write_pluto_safety_gate
        precomputed = _precomputed_gate(_rover_intent())
        # Provide an empty mission_intent so on-demand would produce different result
        mission_result = _make_mission_result(artifacts={
            "pluto_safety_gate": precomputed,
            "mission_intent": {},
        })
        result = _write_pluto_safety_gate(tmp_path, mission_result)
        # Precomputed gate had rover platform → risk_level should be high/medium
        assert result["risk_level"] in ("medium", "high")

    def test_invalid_precomputed_gate_falls_back_to_on_demand(self, tmp_path):
        """Stored dict without 'gate' key triggers on-demand evaluation."""
        from backend.app.export.export_manager import _write_pluto_safety_gate
        mission_result = _make_mission_result(artifacts={
            "pluto_safety_gate": {"something_else": True},  # missing gate key
            "mission_intent": _rover_intent(),
        })
        result = _write_pluto_safety_gate(tmp_path, mission_result)
        assert result["status"] in ("passed", "warn", "blocked")

    def test_rover_mission_requires_human_review(self, tmp_path):
        from backend.app.export.export_manager import _write_pluto_safety_gate
        mission_result = _make_mission_result(artifacts={"mission_intent": _rover_intent()})
        result = _write_pluto_safety_gate(tmp_path, mission_result)
        assert result["required_human_review"] is True


# ---------------------------------------------------------------------------
# export_mission_files integration tests
# ---------------------------------------------------------------------------

class TestExportMissionFilesIntegration:

    def test_export_writes_pluto_safety_gate_report_on_demand(self, tmp_path, monkeypatch):
        import backend.app.export.export_manager as em
        monkeypatch.setattr(em, "OUTPUT_ROOT", tmp_path / "omni_missions")
        mission_result = _make_mission_result(artifacts={})
        result = em.export_mission_files(mission_result, validate_ros2=False)
        export_dir = Path(result["export_dir"])
        assert (export_dir / "pluto_safety_gate_report.json").exists()

    def test_export_writes_pluto_safety_gate_report_from_precomputed(self, tmp_path, monkeypatch):
        import backend.app.export.export_manager as em
        monkeypatch.setattr(em, "OUTPUT_ROOT", tmp_path / "omni_missions")
        intent = _rover_intent()
        gate = _precomputed_gate(intent)
        mission_result = _make_mission_result(artifacts={
            "mission_intent": intent,
            "pluto_safety_gate": gate,
        })
        result = em.export_mission_files(mission_result, validate_ros2=False)
        export_dir = Path(result["export_dir"])
        assert (export_dir / "pluto_safety_gate_report.json").exists()

    def test_export_return_has_cortex_pluto_safety_gate_key(self, tmp_path, monkeypatch):
        import backend.app.export.export_manager as em
        monkeypatch.setattr(em, "OUTPUT_ROOT", tmp_path / "omni_missions")
        mission_result = _make_mission_result(artifacts={})
        result = em.export_mission_files(mission_result, validate_ros2=False)
        assert "cortex" in result
        assert "pluto_safety_gate" in result["cortex"]

    def test_export_pluto_safety_gate_summary_fields(self, tmp_path, monkeypatch):
        import backend.app.export.export_manager as em
        monkeypatch.setattr(em, "OUTPUT_ROOT", tmp_path / "omni_missions")
        mission_result = _make_mission_result(
            mission="Build a magnetic tracked rover for metal surface inspection.",
            artifacts={},
        )
        result = em.export_mission_files(mission_result, validate_ros2=False)
        sg = result["cortex"]["pluto_safety_gate"]
        assert sg["status"] in ("passed", "warn", "blocked")
        assert sg["risk_level"] in ("low", "medium", "high")
        assert isinstance(sg["required_human_review"], bool)
        assert isinstance(sg["blocker_count"], int)
        assert isinstance(sg["warning_count"], int)
        assert isinstance(sg["next_check_count"], int)

    def test_export_evaluator_failure_is_contained(self, tmp_path, monkeypatch):
        """If evaluate_safety_gate raises, export still completes with failed status."""
        import backend.app.export.export_manager as em
        import backend.app.omni_core.safety_gate as sg_mod
        monkeypatch.setattr(em, "OUTPUT_ROOT", tmp_path / "omni_missions")

        def _explode(*args, **kwargs):
            raise RuntimeError("safety gate deliberately exploded")

        monkeypatch.setattr(sg_mod, "evaluate_safety_gate", _explode)

        mission_result = _make_mission_result(artifacts={})
        result = em.export_mission_files(mission_result, validate_ros2=False)

        assert result["status"] == "exported"
        sg = result["cortex"]["pluto_safety_gate"]
        assert sg["status"] == "failed"
        assert "error" in sg

    def test_export_evaluator_failure_writes_failed_json(self, tmp_path, monkeypatch):
        import backend.app.export.export_manager as em
        import backend.app.omni_core.safety_gate as sg_mod
        monkeypatch.setattr(em, "OUTPUT_ROOT", tmp_path / "omni_missions")

        def _explode(*args, **kwargs):
            raise RuntimeError("safety gate deliberately exploded")

        monkeypatch.setattr(sg_mod, "evaluate_safety_gate", _explode)

        mission_result = _make_mission_result(artifacts={})
        result = em.export_mission_files(mission_result, validate_ros2=False)
        export_dir = Path(result["export_dir"])
        assert (export_dir / "pluto_safety_gate_report.json").exists()
        report = json.loads((export_dir / "pluto_safety_gate_report.json").read_text())
        assert report["status"] == "failed"

    def test_export_pluto_safety_gate_in_files_list(self, tmp_path, monkeypatch):
        import backend.app.export.export_manager as em
        monkeypatch.setattr(em, "OUTPUT_ROOT", tmp_path / "omni_missions")
        mission_result = _make_mission_result(artifacts={})
        result = em.export_mission_files(mission_result, validate_ros2=False)
        assert any("pluto_safety_gate_report.json" in f for f in result["files"])

    def test_export_preserves_graph_review_key(self, tmp_path, monkeypatch):
        import backend.app.export.export_manager as em
        monkeypatch.setattr(em, "OUTPUT_ROOT", tmp_path / "omni_missions")
        result = em.export_mission_files(_make_mission_result(), validate_ros2=False)
        assert "graph_review" in result

    def test_export_preserves_design_understanding_key(self, tmp_path, monkeypatch):
        import backend.app.export.export_manager as em
        monkeypatch.setattr(em, "OUTPUT_ROOT", tmp_path / "omni_missions")
        result = em.export_mission_files(_make_mission_result(), validate_ros2=False)
        assert "design_understanding" in result["cortex"]

    def test_export_preserves_candidate_evaluation_key(self, tmp_path, monkeypatch):
        import backend.app.export.export_manager as em
        monkeypatch.setattr(em, "OUTPUT_ROOT", tmp_path / "omni_missions")
        result = em.export_mission_files(_make_mission_result(), validate_ros2=False)
        assert "candidate_evaluation" in result["cortex"]

    def test_export_preserves_mission_intent_key(self, tmp_path, monkeypatch):
        import backend.app.export.export_manager as em
        monkeypatch.setattr(em, "OUTPUT_ROOT", tmp_path / "omni_missions")
        result = em.export_mission_files(_make_mission_result(), validate_ros2=False)
        assert "mission_intent" in result["cortex"]
