"""
Phase 14A — Mission intelligence stack integration tests.

Proves that compile_mission_intent, evaluate_design_candidates,
evaluate_safety_gate, and export_mission_files work together correctly
on a deterministic fixture mission.

No LLM calls. No network calls.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

import pytest

# ---------------------------------------------------------------------------
# Fixture mission
# ---------------------------------------------------------------------------

STACK_MISSION = (
    "Design three candidate concepts for a palm-sized magnetic inspection crawler "
    "that can traverse vertical steel surfaces, collect camera and IMU data, use "
    "onboard battery power, and produce ROS2 architecture, CAD concept geometry, "
    "validation checks, candidate evaluation, mission intent, and Pluto safety gate review."
)

# Augmented version: user mission + appended knowledge context with extra sensors.
AUGMENTED_STACK_MISSION = (
    STACK_MISSION
    + "\n\nOMNI LOCAL KNOWLEDGE CONTEXT\n\n"
    "Selected knowledge domains:\n- sensors: sensor guide\n\n"
    "Relevant retrieved knowledge excerpts:\n\n"
    "[Knowledge Hit 1]\nDomain: sensors\nSource: sensor_guide.pdf\n"
    "Excerpt: LiDAR provides depth maps. Radar and GPS are used for outdoor "
    "navigation. Depth sensors and sonar enable underwater operation.\n\n"
    "Instruction to OMNI Agent Council:\n"
    "Use the local knowledge context as grounding material.\n"
)


def _make_candidates():
    from agents.design_candidates import normalize_candidates
    return normalize_candidates([
        {
            "name": "Magnetic Tracked Crawler",
            "concept": "Low-profile tracked platform with magnetic adhesion pads",
            "platform": "ground-rover",
            "mobility_type": "tracked",
            "morphology_notes": "Wide low-profile chassis with magnetic track segments",
            "key_components": ["magnetic tracks", "IMU", "camera", "motor driver", "LiPo battery"],
            "strengths": ["stable on vertical steel", "low center of gravity"],
            "risks": ["limited speed on curved surfaces"],
            "required_validation": ["torque calculation", "adhesion force test", "power budget"],
            "assumptions": [],
            "recommended": True,
        },
        {
            "name": "Wheeled Magnetic Rover",
            "concept": "Wheeled platform with magnetic wheel hubs",
            "platform": "ground-rover",
            "mobility_type": "wheeled",
            "morphology_notes": "Compact differential drive with magnetic wheel cores",
            "key_components": ["magnetic wheels", "encoder", "IMU", "camera"],
            "strengths": ["faster traverse speed"],
            "risks": ["slip risk on steep inclines"],
            "required_validation": ["slip test", "power budget"],
            "assumptions": [],
            "recommended": False,
        },
        {
            "name": "Legged Climbing Robot",
            "concept": "Hexapod with suction/magnetic feet",
            "platform": "hexapod",
            "mobility_type": "legged",
            "morphology_notes": "Six-legged frame with adhesion feet",
            "key_components": ["servos", "IMU", "suction pump", "camera"],
            "strengths": ["steps over obstacles and welds"],
            "risks": ["complex gait control", "high power draw"],
            "required_validation": ["gait simulation", "adhesion test"],
            "assumptions": [],
            "recommended": False,
        },
    ])


def _make_mission_result(candidates, artifacts_extra: Dict[str, Any] | None = None) -> Dict[str, Any]:
    arts: Dict[str, Any] = {
        "design_candidates": candidates,
        "design_alternatives": {
            "owner": "Vega",
            "content": "Three candidate concepts for the magnetic inspection crawler.",
            "candidates": candidates,
        },
    }
    if artifacts_extra:
        arts.update(artifacts_extra)
    return {
        "mission": STACK_MISSION,
        "result_id": "phase14a-stack-test",
        "final_report": "",
        "final_decision": "",
        "agents": {},
        "artifacts": arts,
        "validation": {},
        "critique": {},
        "revision": {},
        "status": "complete",
    }


# ---------------------------------------------------------------------------
# Unit: compile_mission_intent on fixture mission
# ---------------------------------------------------------------------------

class TestMissionIntentOnFixture:

    def test_platform_intent_is_ground_rover(self):
        from backend.app.omni_core.mission_intent import compile_mission_intent
        result = compile_mission_intent(STACK_MISSION)
        assert result["platform_intent"] == "ground-rover"

    def test_camera_in_sensing_requirements(self):
        from backend.app.omni_core.mission_intent import compile_mission_intent
        result = compile_mission_intent(STACK_MISSION)
        assert "camera" in result["sensing_requirements"]

    def test_imu_in_sensing_requirements(self):
        from backend.app.omni_core.mission_intent import compile_mission_intent
        result = compile_mission_intent(STACK_MISSION)
        assert "IMU" in result["sensing_requirements"]

    def test_ros2_in_required_outputs(self):
        from backend.app.omni_core.mission_intent import compile_mission_intent
        result = compile_mission_intent(STACK_MISSION)
        assert "ROS2 package" in result["required_outputs"]

    def test_cad_in_required_outputs(self):
        from backend.app.omni_core.mission_intent import compile_mission_intent
        result = compile_mission_intent(STACK_MISSION)
        assert "CAD model" in result["required_outputs"]

    def test_validation_in_required_outputs(self):
        from backend.app.omni_core.mission_intent import compile_mission_intent
        result = compile_mission_intent(STACK_MISSION)
        assert "validation checklist" in result["required_outputs"]

    def test_battery_in_constraints(self):
        from backend.app.omni_core.mission_intent import compile_mission_intent
        result = compile_mission_intent(STACK_MISSION)
        assert "battery / power source" in result["constraints"]

    def test_safety_mode_elevated(self):
        from backend.app.omni_core.mission_intent import compile_mission_intent
        result = compile_mission_intent(STACK_MISSION)
        assert result["safety_mode"] == "elevated"

    def test_mission_type_is_inspection(self):
        from backend.app.omni_core.mission_intent import compile_mission_intent
        result = compile_mission_intent(STACK_MISSION)
        assert result["mission_type"] == "inspection"


# ---------------------------------------------------------------------------
# Regression: augmented mission only extracts user sensors
# ---------------------------------------------------------------------------

class TestAugmentedMissionCleanInput:

    def test_platform_still_ground_rover_under_augmentation(self):
        from backend.app.omni_core.mission_intent import compile_mission_intent
        result = compile_mission_intent(AUGMENTED_STACK_MISSION)
        assert result["platform_intent"] == "ground-rover"

    def test_camera_extracted_not_lidar(self):
        from backend.app.omni_core.mission_intent import compile_mission_intent
        result = compile_mission_intent(AUGMENTED_STACK_MISSION)
        assert "camera" in result["sensing_requirements"]
        assert "LiDAR" not in result["sensing_requirements"]

    def test_imu_extracted_not_radar(self):
        from backend.app.omni_core.mission_intent import compile_mission_intent
        result = compile_mission_intent(AUGMENTED_STACK_MISSION)
        assert "IMU" in result["sensing_requirements"]
        assert "radar" not in result["sensing_requirements"]

    def test_gps_not_extracted_from_knowledge_context(self):
        from backend.app.omni_core.mission_intent import compile_mission_intent
        result = compile_mission_intent(AUGMENTED_STACK_MISSION)
        assert "GPS" not in result["sensing_requirements"]

    def test_sonar_not_extracted_from_knowledge_context(self):
        from backend.app.omni_core.mission_intent import compile_mission_intent
        result = compile_mission_intent(AUGMENTED_STACK_MISSION)
        assert "sonar" not in result["sensing_requirements"]

    def test_raw_mission_does_not_contain_knowledge_marker(self):
        from backend.app.omni_core.mission_intent import compile_mission_intent
        result = compile_mission_intent(AUGMENTED_STACK_MISSION)
        assert "OMNI LOCAL KNOWLEDGE CONTEXT" not in result["raw_mission"]


# ---------------------------------------------------------------------------
# Unit: candidate evaluation on fixture candidates
# ---------------------------------------------------------------------------

class TestCandidateEvaluationOnFixture:

    def test_evaluates_three_candidates(self):
        from agents.candidate_evaluator import evaluate_design_candidates
        candidates = _make_candidates()
        result = evaluate_design_candidates(candidates, mission_text=STACK_MISSION)
        assert result["candidates_evaluated"] == 3

    def test_recommended_candidate_id_present(self):
        from agents.candidate_evaluator import evaluate_design_candidates
        candidates = _make_candidates()
        result = evaluate_design_candidates(candidates, mission_text=STACK_MISSION)
        assert isinstance(result["recommended_candidate_id"], str)
        assert result["recommended_candidate_id"].startswith("vega_candidate_")

    def test_ranking_has_three_entries(self):
        from agents.candidate_evaluator import evaluate_design_candidates
        candidates = _make_candidates()
        result = evaluate_design_candidates(candidates, mission_text=STACK_MISSION)
        assert len(result["ranking"]) == 3

    def test_recommended_id_is_top_ranked(self):
        from agents.candidate_evaluator import evaluate_design_candidates
        candidates = _make_candidates()
        result = evaluate_design_candidates(candidates, mission_text=STACK_MISSION)
        assert result["recommended_candidate_id"] == result["ranking"][0]

    def test_all_evaluations_have_required_scores(self):
        from agents.candidate_evaluator import evaluate_design_candidates
        candidates = _make_candidates()
        result = evaluate_design_candidates(candidates, mission_text=STACK_MISSION)
        for ev in result["evaluations"]:
            for key in ("sky_score", "isy_score", "korva_score", "oli_score",
                        "pluto_score", "qaz_score", "overall_score"):
                assert key in ev
                assert 0.0 <= ev[key] <= 1.0

    def test_tracked_crawler_beats_legged_walker(self):
        from agents.candidate_evaluator import evaluate_design_candidates
        candidates = _make_candidates()
        result = evaluate_design_candidates(candidates, mission_text=STACK_MISSION)
        by_id = {ev["id"]: ev for ev in result["evaluations"]}
        tracked = by_id.get("vega_candidate_1")
        legged = by_id.get("vega_candidate_3")
        assert tracked is not None and legged is not None
        assert tracked["overall_score"] > legged["overall_score"]


# ---------------------------------------------------------------------------
# Unit: safety gate on fixture intent + evaluation
# ---------------------------------------------------------------------------

class TestSafetyGateOnFixture:

    def _intent(self):
        from backend.app.omni_core.mission_intent import compile_mission_intent
        return compile_mission_intent(STACK_MISSION)

    def _evaluation(self):
        from agents.candidate_evaluator import evaluate_design_candidates
        return evaluate_design_candidates(_make_candidates(), mission_text=STACK_MISSION)

    def test_status_is_valid(self):
        from backend.app.omni_core.safety_gate import evaluate_safety_gate
        result = evaluate_safety_gate(self._intent(), self._evaluation())
        assert result["status"] in ("passed", "warn", "blocked")

    def test_required_human_review_is_true(self):
        from backend.app.omni_core.safety_gate import evaluate_safety_gate
        result = evaluate_safety_gate(self._intent(), self._evaluation())
        assert result["required_human_review"] is True

    def test_risk_level_is_not_low(self):
        from backend.app.omni_core.safety_gate import evaluate_safety_gate
        result = evaluate_safety_gate(self._intent(), self._evaluation())
        # Physical robot with elevated safety mode cannot be low risk
        assert result["risk_level"] in ("medium", "high")

    def test_no_blockers_for_well_specified_mission(self):
        from backend.app.omni_core.safety_gate import evaluate_safety_gate
        result = evaluate_safety_gate(self._intent(), self._evaluation())
        assert result["blockers"] == []

    def test_rationale_mentions_advisory(self):
        from backend.app.omni_core.safety_gate import evaluate_safety_gate
        result = evaluate_safety_gate(self._intent(), self._evaluation())
        assert "advisory" in result["rationale"].lower()

    def test_gate_name_correct(self):
        from backend.app.omni_core.safety_gate import evaluate_safety_gate, GATE_NAME
        result = evaluate_safety_gate(self._intent(), self._evaluation())
        assert result["gate"] == GATE_NAME

    def test_stack_is_deterministic(self):
        from backend.app.omni_core.safety_gate import evaluate_safety_gate
        r1 = evaluate_safety_gate(self._intent(), self._evaluation())
        r2 = evaluate_safety_gate(self._intent(), self._evaluation())
        assert r1 == r2


# ---------------------------------------------------------------------------
# Integration: export writes all three report files
# ---------------------------------------------------------------------------

class TestExportIntegration:

    def _export(self, tmp_path):
        import backend.app.export.export_manager as em
        import pytest
        monkeypatch = pytest.MonkeyPatch()
        monkeypatch.setattr(em, "OUTPUT_ROOT", tmp_path / "omni_missions")

        from backend.app.omni_core.mission_intent import compile_mission_intent
        from agents.candidate_evaluator import evaluate_design_candidates
        from backend.app.omni_core.safety_gate import evaluate_safety_gate

        candidates = _make_candidates()
        intent = compile_mission_intent(STACK_MISSION)
        evaluation = evaluate_design_candidates(candidates, mission_text=STACK_MISSION)
        gate = evaluate_safety_gate(intent, evaluation)

        mission_result = _make_mission_result(candidates, artifacts_extra={
            "mission_intent": intent,
            "candidate_evaluation": evaluation,
            "pluto_safety_gate": gate,
        })

        result = em.export_mission_files(mission_result, validate_ros2=False)
        monkeypatch.undo()
        return result

    def test_export_writes_mission_intent_report(self, tmp_path):
        result = self._export(tmp_path)
        assert (Path(result["export_dir"]) / "mission_intent_report.json").exists()

    def test_export_writes_candidate_evaluation_report(self, tmp_path):
        result = self._export(tmp_path)
        assert (Path(result["export_dir"]) / "candidate_evaluation_report.json").exists()

    def test_export_writes_pluto_safety_gate_report(self, tmp_path):
        result = self._export(tmp_path)
        assert (Path(result["export_dir"]) / "pluto_safety_gate_report.json").exists()

    def test_export_status_is_exported(self, tmp_path):
        result = self._export(tmp_path)
        assert result["status"] == "exported"

    def test_cortex_mission_intent_summary_present(self, tmp_path):
        result = self._export(tmp_path)
        mi = result["cortex"]["mission_intent"]
        assert mi["status"] == "compiled"
        assert mi["platform_intent"] == "ground-rover"

    def test_cortex_candidate_evaluation_summary_present(self, tmp_path):
        result = self._export(tmp_path)
        ce = result["cortex"]["candidate_evaluation"]
        assert ce["status"] == "evaluated"
        assert ce["candidates_evaluated"] == 3
        assert isinstance(ce["recommended_candidate_id"], str)

    def test_cortex_pluto_safety_gate_summary_present(self, tmp_path):
        result = self._export(tmp_path)
        sg = result["cortex"]["pluto_safety_gate"]
        assert sg["status"] in ("passed", "warn", "blocked")
        assert sg["required_human_review"] is True

    def test_mission_intent_report_json_valid(self, tmp_path):
        result = self._export(tmp_path)
        report = json.loads(
            (Path(result["export_dir"]) / "mission_intent_report.json").read_text()
        )
        assert report["platform_intent"] == "ground-rover"
        assert "camera" in report["sensing_requirements"]
        assert "IMU" in report["sensing_requirements"]

    def test_candidate_evaluation_report_json_valid(self, tmp_path):
        result = self._export(tmp_path)
        report = json.loads(
            (Path(result["export_dir"]) / "candidate_evaluation_report.json").read_text()
        )
        assert report["candidates_evaluated"] == 3
        assert len(report["evaluations"]) == 3

    def test_pluto_safety_gate_report_json_valid(self, tmp_path):
        result = self._export(tmp_path)
        report = json.loads(
            (Path(result["export_dir"]) / "pluto_safety_gate_report.json").read_text()
        )
        assert "status" in report
        assert "risk_level" in report
        assert "blockers" in report
        assert "warnings" in report
        assert "required_human_review" in report
        assert "required_next_checks" in report
        assert "rationale" in report

    def test_all_three_reports_in_files_list(self, tmp_path):
        result = self._export(tmp_path)
        files = result["files"]
        assert any("mission_intent_report.json" in f for f in files)
        assert any("candidate_evaluation_report.json" in f for f in files)
        assert any("pluto_safety_gate_report.json" in f for f in files)

    def test_graph_review_key_preserved(self, tmp_path):
        result = self._export(tmp_path)
        assert "graph_review" in result

    def test_design_understanding_key_preserved(self, tmp_path):
        result = self._export(tmp_path)
        assert "design_understanding" in result["cortex"]


# ---------------------------------------------------------------------------
# Integration: stack consistency — intent feeds gate, evaluation feeds gate
# ---------------------------------------------------------------------------

class TestStackConsistency:

    def test_platform_in_intent_matches_expected(self):
        from backend.app.omni_core.mission_intent import compile_mission_intent
        intent = compile_mission_intent(STACK_MISSION)
        assert intent["platform_intent"] == "ground-rover"

    def test_gate_uses_intent_platform(self):
        from backend.app.omni_core.mission_intent import compile_mission_intent
        from backend.app.omni_core.safety_gate import evaluate_safety_gate
        intent = compile_mission_intent(STACK_MISSION)
        gate = evaluate_safety_gate(mission_intent=intent)
        # ground-rover is a medium-risk platform — gate should reflect this
        assert gate["risk_level"] in ("medium", "high")

    def test_candidate_ids_are_stable_across_calls(self):
        candidates1 = _make_candidates()
        candidates2 = _make_candidates()
        ids1 = [c["id"] for c in candidates1]
        ids2 = [c["id"] for c in candidates2]
        assert ids1 == ids2

    def test_full_stack_is_deterministic(self):
        from backend.app.omni_core.mission_intent import compile_mission_intent
        from agents.candidate_evaluator import evaluate_design_candidates
        from backend.app.omni_core.safety_gate import evaluate_safety_gate

        def run():
            candidates = _make_candidates()
            intent = compile_mission_intent(STACK_MISSION)
            evaluation = evaluate_design_candidates(candidates, mission_text=STACK_MISSION)
            gate = evaluate_safety_gate(intent, evaluation)
            return intent, evaluation, gate

        i1, e1, g1 = run()
        i2, e2, g2 = run()
        assert i1 == i2
        assert e1 == e2
        assert g1 == g2

    def test_skipped_candidates_degrades_gate_warning(self):
        """When no candidates are evaluated, gate should add a candidate warning."""
        from backend.app.omni_core.mission_intent import compile_mission_intent
        from backend.app.omni_core.safety_gate import evaluate_safety_gate
        intent = compile_mission_intent(STACK_MISSION)
        gate = evaluate_safety_gate(
            mission_intent=intent,
            candidate_evaluation={"status": "skipped", "candidates_evaluated": 0},
        )
        combined = " ".join(gate["warnings"]).lower()
        assert "skipped" in combined or "candidate" in combined

    def test_augmented_mission_same_gate_result_as_clean(self):
        """Gate outcome must be identical whether or not knowledge context is appended."""
        from backend.app.omni_core.mission_intent import compile_mission_intent
        from backend.app.omni_core.safety_gate import evaluate_safety_gate
        from agents.candidate_evaluator import evaluate_design_candidates

        candidates = _make_candidates()
        intent_clean = compile_mission_intent(STACK_MISSION)
        intent_aug   = compile_mission_intent(AUGMENTED_STACK_MISSION)
        evaluation   = evaluate_design_candidates(candidates, mission_text=STACK_MISSION)

        gate_clean = evaluate_safety_gate(intent_clean, evaluation)
        gate_aug   = evaluate_safety_gate(intent_aug,   evaluation)

        assert gate_clean["status"]                == gate_aug["status"]
        assert gate_clean["risk_level"]            == gate_aug["risk_level"]
        assert gate_clean["required_human_review"] == gate_aug["required_human_review"]
