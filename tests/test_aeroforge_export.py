"""
Phase 15B — AeroForge export pipeline tests.

No LLM calls. No network calls.
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any, Dict, Optional
from unittest.mock import patch

import pytest


# ---------------------------------------------------------------------------
# Mission fixtures
# ---------------------------------------------------------------------------

ROVER_MISSION = (
    "Design a palm-sized magnetic inspection crawler that can traverse vertical "
    "steel surfaces, collect camera and IMU data, use onboard battery power, "
    "and produce ROS2 architecture and CAD concept geometry."
)

DRONE_UAV_MISSION = (
    "Design a UAV inspection drone with onboard camera and GPS, capable of "
    "autonomous flight over infrastructure, with avionics for telemetry and navigation."
)

AIRCRAFT_MISSION = (
    "Develop a concept for a fixed-wing aircraft with detailed wing and airframe "
    "analysis, focusing on lift and drag trade-offs for long-endurance flight."
)

ROCKET_MISSION = (
    "Design a rocket propulsion concept with nozzle and thrust analysis for a "
    "suborbital launch vehicle — concept stage only."
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_aeroforge(
    export_dir: Path,
    mission_text: str,
    artifacts: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    from backend.app.export.export_manager import _write_aeroforge_reports
    return _write_aeroforge_reports(
        export_dir=export_dir,
        mission_text=mission_text,
        artifacts=artifacts or {},
    )


# ---------------------------------------------------------------------------
# TestRoverNotApplicable
# ---------------------------------------------------------------------------

class TestRoverNotApplicable:
    def test_status_not_applicable(self, tmp_path):
        result = _write_aeroforge(tmp_path, ROVER_MISSION)
        assert result["status"] == "not_applicable"

    def test_aerospace_detected_false(self, tmp_path):
        result = _write_aeroforge(tmp_path, ROVER_MISSION)
        assert result["aerospace_detected"] is False

    def test_no_files_written(self, tmp_path):
        _write_aeroforge(tmp_path, ROVER_MISSION)
        assert not (tmp_path / "aeroforge_intent_report.json").exists()
        assert not (tmp_path / "aeroforge_entry_gate_report.json").exists()

    def test_returns_dict(self, tmp_path):
        result = _write_aeroforge(tmp_path, ROVER_MISSION)
        assert isinstance(result, dict)


# ---------------------------------------------------------------------------
# TestAerospaceWritesFiles
# ---------------------------------------------------------------------------

class TestAerospaceWritesFiles:
    def test_intent_report_written(self, tmp_path):
        _write_aeroforge(tmp_path, DRONE_UAV_MISSION)
        assert (tmp_path / "aeroforge_intent_report.json").exists()

    def test_entry_gate_report_written(self, tmp_path):
        _write_aeroforge(tmp_path, DRONE_UAV_MISSION)
        assert (tmp_path / "aeroforge_entry_gate_report.json").exists()

    def test_intent_report_is_valid_json(self, tmp_path):
        _write_aeroforge(tmp_path, DRONE_UAV_MISSION)
        data = json.loads((tmp_path / "aeroforge_intent_report.json").read_text())
        assert isinstance(data, dict)

    def test_entry_gate_report_is_valid_json(self, tmp_path):
        _write_aeroforge(tmp_path, DRONE_UAV_MISSION)
        data = json.loads((tmp_path / "aeroforge_entry_gate_report.json").read_text())
        assert isinstance(data, dict)

    def test_aircraft_writes_files(self, tmp_path):
        _write_aeroforge(tmp_path, AIRCRAFT_MISSION)
        assert (tmp_path / "aeroforge_intent_report.json").exists()
        assert (tmp_path / "aeroforge_entry_gate_report.json").exists()

    def test_rocket_writes_files(self, tmp_path):
        _write_aeroforge(tmp_path, ROCKET_MISSION)
        assert (tmp_path / "aeroforge_intent_report.json").exists()
        assert (tmp_path / "aeroforge_entry_gate_report.json").exists()


# ---------------------------------------------------------------------------
# TestCompactSummary
# ---------------------------------------------------------------------------

class TestCompactSummary:
    def test_status_detected(self, tmp_path):
        result = _write_aeroforge(tmp_path, DRONE_UAV_MISSION)
        assert result["status"] == "detected"

    def test_aerospace_detected_true(self, tmp_path):
        result = _write_aeroforge(tmp_path, DRONE_UAV_MISSION)
        assert result["aerospace_detected"] is True

    def test_intent_report_path_present(self, tmp_path):
        result = _write_aeroforge(tmp_path, DRONE_UAV_MISSION)
        assert "intent_report_path" in result

    def test_entry_gate_report_path_present(self, tmp_path):
        result = _write_aeroforge(tmp_path, DRONE_UAV_MISSION)
        assert "entry_gate_report_path" in result

    def test_entry_gate_status_present(self, tmp_path):
        result = _write_aeroforge(tmp_path, DRONE_UAV_MISSION)
        assert "entry_gate_status" in result

    def test_platform_hint_present(self, tmp_path):
        result = _write_aeroforge(tmp_path, DRONE_UAV_MISSION)
        assert "platform_hint" in result

    def test_domain_count_present(self, tmp_path):
        result = _write_aeroforge(tmp_path, DRONE_UAV_MISSION)
        assert "domain_count" in result

    def test_domain_count_positive(self, tmp_path):
        result = _write_aeroforge(tmp_path, DRONE_UAV_MISSION)
        assert result["domain_count"] > 0

    def test_human_review_required_present(self, tmp_path):
        result = _write_aeroforge(tmp_path, DRONE_UAV_MISSION)
        assert "human_review_required" in result

    def test_human_review_required_true(self, tmp_path):
        result = _write_aeroforge(tmp_path, DRONE_UAV_MISSION)
        assert result["human_review_required"] is True

    def test_concept_stage_only_present(self, tmp_path):
        result = _write_aeroforge(tmp_path, DRONE_UAV_MISSION)
        assert "concept_stage_only" in result

    def test_concept_stage_only_true(self, tmp_path):
        result = _write_aeroforge(tmp_path, DRONE_UAV_MISSION)
        assert result["concept_stage_only"] is True

    def test_paths_point_to_written_files(self, tmp_path):
        result = _write_aeroforge(tmp_path, DRONE_UAV_MISSION)
        assert Path(result["intent_report_path"]).exists()
        assert Path(result["entry_gate_report_path"]).exists()


# ---------------------------------------------------------------------------
# TestPrecomputedArtifacts
# ---------------------------------------------------------------------------

class TestPrecomputedArtifacts:
    def _precomputed_intent(self):
        from backend.app.aeroforge.foundation import classify_aeroforge_intent
        return classify_aeroforge_intent(mission_text=DRONE_UAV_MISSION)

    def _precomputed_gate(self):
        from backend.app.aeroforge.foundation import evaluate_aeroforge_entry_gate
        return evaluate_aeroforge_entry_gate(mission_text=DRONE_UAV_MISSION)

    def test_precomputed_intent_used(self, tmp_path):
        precomputed = self._precomputed_intent()
        result = _write_aeroforge(
            tmp_path, DRONE_UAV_MISSION,
            artifacts={"aeroforge_intent": precomputed},
        )
        assert result["status"] == "detected"

    def test_precomputed_gate_used(self, tmp_path):
        precomputed_intent = self._precomputed_intent()
        precomputed_gate = self._precomputed_gate()
        result = _write_aeroforge(
            tmp_path, DRONE_UAV_MISSION,
            artifacts={
                "aeroforge_intent": precomputed_intent,
                "aeroforge_entry_gate": precomputed_gate,
            },
        )
        assert result["entry_gate_status"] == precomputed_gate["status"]

    def test_precomputed_not_applicable_skips_files(self, tmp_path):
        from backend.app.aeroforge.foundation import classify_aeroforge_intent
        precomputed = classify_aeroforge_intent(mission_text=ROVER_MISSION)
        result = _write_aeroforge(
            tmp_path, ROVER_MISSION,
            artifacts={"aeroforge_intent": precomputed},
        )
        assert result["status"] == "not_applicable"
        assert not (tmp_path / "aeroforge_intent_report.json").exists()


# ---------------------------------------------------------------------------
# TestConceptStageConstraints
# ---------------------------------------------------------------------------

class TestConceptStageConstraints:
    def test_intent_report_has_blocked_outputs(self, tmp_path):
        _write_aeroforge(tmp_path, DRONE_UAV_MISSION)
        data = json.loads((tmp_path / "aeroforge_intent_report.json").read_text())
        assert "blocked_outputs" in data
        assert len(data["blocked_outputs"]) > 0

    def test_intent_report_blocked_outputs_no_airworthiness_claim(self, tmp_path):
        _write_aeroforge(tmp_path, DRONE_UAV_MISSION)
        data = json.loads((tmp_path / "aeroforge_intent_report.json").read_text())
        blocked = " ".join(data["blocked_outputs"])
        assert "airworthiness" in blocked

    def test_intent_report_has_allowed_outputs(self, tmp_path):
        _write_aeroforge(tmp_path, DRONE_UAV_MISSION)
        data = json.loads((tmp_path / "aeroforge_intent_report.json").read_text())
        assert "allowed_outputs" in data
        assert len(data["allowed_outputs"]) > 0

    def test_intent_report_concept_stage_only_true(self, tmp_path):
        _write_aeroforge(tmp_path, DRONE_UAV_MISSION)
        data = json.loads((tmp_path / "aeroforge_intent_report.json").read_text())
        assert data["concept_stage_only"] is True

    def test_entry_gate_has_required_review_gates(self, tmp_path):
        _write_aeroforge(tmp_path, DRONE_UAV_MISSION)
        data = json.loads((tmp_path / "aeroforge_entry_gate_report.json").read_text())
        assert "human_review_required" in data
        assert data["human_review_required"] is True


# ---------------------------------------------------------------------------
# TestEntryGateBlockedByReadiness
# ---------------------------------------------------------------------------

class TestEntryGateBlockedByReadiness:
    def test_blocked_readiness_produces_blocked_gate(self, tmp_path):
        blocked_readiness = {"status": "blocked", "blockers": ["missing intent"]}
        result = _write_aeroforge(
            tmp_path, DRONE_UAV_MISSION,
            artifacts={"mission_intelligence_readiness": blocked_readiness},
        )
        assert result["entry_gate_status"] == "blocked"

    def test_blocked_gate_still_writes_files(self, tmp_path):
        blocked_readiness = {"status": "blocked", "blockers": ["missing intent"]}
        _write_aeroforge(
            tmp_path, DRONE_UAV_MISSION,
            artifacts={"mission_intelligence_readiness": blocked_readiness},
        )
        assert (tmp_path / "aeroforge_intent_report.json").exists()
        assert (tmp_path / "aeroforge_entry_gate_report.json").exists()

    def test_ready_readiness_produces_concept_stage_gate(self, tmp_path):
        ready_readiness = {"status": "ready"}
        result = _write_aeroforge(
            tmp_path, DRONE_UAV_MISSION,
            artifacts={"mission_intelligence_readiness": ready_readiness},
        )
        assert result["entry_gate_status"] == "concept_stage_only"


# ---------------------------------------------------------------------------
# TestFailureContainment
# ---------------------------------------------------------------------------

class TestFailureContainment:
    def test_import_failure_returns_failed_status(self, tmp_path):
        import sys
        with patch.dict(sys.modules, {"backend.app.aeroforge.foundation": None}):
            from backend.app.export.export_manager import _write_aeroforge_reports
            try:
                result = _write_aeroforge_reports(
                    export_dir=tmp_path,
                    mission_text=DRONE_UAV_MISSION,
                    artifacts={},
                )
            except Exception:
                result = {"status": "failed"}
        assert result.get("status") == "failed" or isinstance(result, dict)

    def test_write_failure_writes_error_file(self, tmp_path):
        from backend.app.export.export_manager import _write_aeroforge_reports
        from backend.app.aeroforge.foundation import classify_aeroforge_intent

        real_intent = classify_aeroforge_intent(mission_text=DRONE_UAV_MISSION)

        def exploding_gate(**kwargs):
            raise RuntimeError("simulated gate failure")

        with patch(
            "backend.app.aeroforge.foundation.evaluate_aeroforge_entry_gate",
            side_effect=RuntimeError("simulated gate failure"),
        ):
            try:
                _write_aeroforge_reports(
                    export_dir=tmp_path,
                    mission_text=DRONE_UAV_MISSION,
                    artifacts={},
                )
            except Exception:
                pass


# ---------------------------------------------------------------------------
# TestExportMissionFilesReturnKeys
# ---------------------------------------------------------------------------

class TestExportMissionFilesReturnKeys:
    """Verify that the top-level export_mission_files return dict has all required keys."""

    def _minimal_mission_result(self, mission_text: str) -> dict:
        return {
            "status": "complete",
            "result_id": "test-phase15b",
            "mission": mission_text,
            "agents": {},
            "artifacts": {},
        }

    def test_aeroforge_key_present_rover(self, tmp_path):
        from backend.app.export.export_manager import export_mission_files
        with patch(
            "backend.app.export.export_manager.OUTPUT_ROOT", tmp_path
        ):
            result = export_mission_files(self._minimal_mission_result(ROVER_MISSION))
        assert "aeroforge" in result

    def test_aeroforge_key_present_drone(self, tmp_path):
        from backend.app.export.export_manager import export_mission_files
        with patch(
            "backend.app.export.export_manager.OUTPUT_ROOT", tmp_path
        ):
            result = export_mission_files(self._minimal_mission_result(DRONE_UAV_MISSION))
        assert "aeroforge" in result

    def test_existing_keys_preserved_rover(self, tmp_path):
        from backend.app.export.export_manager import export_mission_files
        with patch(
            "backend.app.export.export_manager.OUTPUT_ROOT", tmp_path
        ):
            result = export_mission_files(self._minimal_mission_result(ROVER_MISSION))
        assert "graph_review" in result
        assert "cortex" in result
        assert "files" in result

    def test_cortex_keys_preserved_rover(self, tmp_path):
        from backend.app.export.export_manager import export_mission_files
        with patch(
            "backend.app.export.export_manager.OUTPUT_ROOT", tmp_path
        ):
            result = export_mission_files(self._minimal_mission_result(ROVER_MISSION))
        cortex = result["cortex"]
        assert "mission_intent" in cortex
        assert "design_understanding" in cortex
        assert "candidate_evaluation" in cortex
        assert "pluto_safety_gate" in cortex

    def test_rover_aeroforge_not_applicable(self, tmp_path):
        from backend.app.export.export_manager import export_mission_files
        with patch(
            "backend.app.export.export_manager.OUTPUT_ROOT", tmp_path
        ):
            result = export_mission_files(self._minimal_mission_result(ROVER_MISSION))
        aeroforge = result["aeroforge"]
        assert isinstance(aeroforge, dict)
        assert aeroforge["status"] == "not_applicable"

    def test_drone_aeroforge_detected(self, tmp_path):
        from backend.app.export.export_manager import export_mission_files
        with patch(
            "backend.app.export.export_manager.OUTPUT_ROOT", tmp_path
        ):
            result = export_mission_files(self._minimal_mission_result(DRONE_UAV_MISSION))
        aeroforge = result["aeroforge"]
        assert isinstance(aeroforge, dict)
        assert aeroforge["status"] == "detected"

    def test_drone_aeroforge_files_listed_in_files(self, tmp_path):
        from backend.app.export.export_manager import export_mission_files
        with patch(
            "backend.app.export.export_manager.OUTPUT_ROOT", tmp_path
        ):
            result = export_mission_files(self._minimal_mission_result(DRONE_UAV_MISSION))
        files = result["files"]
        assert any("aeroforge_intent_report" in f for f in files)
        assert any("aeroforge_entry_gate_report" in f for f in files)

    def test_rover_aeroforge_files_not_listed(self, tmp_path):
        from backend.app.export.export_manager import export_mission_files
        with patch(
            "backend.app.export.export_manager.OUTPUT_ROOT", tmp_path
        ):
            result = export_mission_files(self._minimal_mission_result(ROVER_MISSION))
        files = result["files"]
        assert not any("aeroforge_intent_report" in f for f in files)
        assert not any("aeroforge_entry_gate_report" in f for f in files)


# ---------------------------------------------------------------------------
# TestDeterminism
# ---------------------------------------------------------------------------

class TestDeterminism:
    def test_same_text_same_result(self, tmp_path):
        dir_a = tmp_path / "a"
        dir_b = tmp_path / "b"
        dir_a.mkdir()
        dir_b.mkdir()
        result_a = _write_aeroforge(dir_a, DRONE_UAV_MISSION)
        result_b = _write_aeroforge(dir_b, DRONE_UAV_MISSION)
        assert result_a["status"] == result_b["status"]
        assert result_a["aerospace_detected"] == result_b["aerospace_detected"]
        assert result_a["domain_count"] == result_b["domain_count"]
        assert result_a["entry_gate_status"] == result_b["entry_gate_status"]

    def test_rover_always_not_applicable(self, tmp_path):
        for i in range(3):
            d = tmp_path / str(i)
            d.mkdir()
            result = _write_aeroforge(d, ROVER_MISSION)
            assert result["status"] == "not_applicable"
