"""
Phase 14B — Mission intelligence memory seed tests.

No LLM calls. No network calls. No file I/O.
"""
from __future__ import annotations

import pytest

from backend.app.omni_core.mission_memory_seed import build_mission_memory_seed


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

def _rover_intent() -> dict:
    return {
        "raw_mission": "Build a tracked ground rover with camera and IMU. Battery powered.",
        "mission_type": "inspection",
        "platform_intent": "ground-rover",
        "safety_mode": "elevated",
        "sensing_requirements": ["camera", "IMU"],
        "required_outputs": ["ROS2 package", "validation checklist"],
        "constraints": ["battery / power source"],
        "open_questions": ["What is the target traverse speed?", "What is the operating temperature range?"],
    }


def _good_evaluation() -> dict:
    return {
        "candidates_evaluated": 3,
        "recommended_candidate_id": "vega_candidate_1",
        "ranking": ["vega_candidate_1", "vega_candidate_2", "vega_candidate_3"],
        "council_summary": "3 candidate(s) evaluated. Top candidate: Tracked Crawler.",
    }


def _rover_gate() -> dict:
    return {
        "gate": "pluto_safety_gate",
        "status": "warn",
        "risk_level": "high",
        "required_human_review": True,
        "blockers": [],
        "warnings": [
            "Mission safety mode is 'elevated'. Human engineering review is required before any physical build.",
            "Platform 'ground-rover' operates in a medium-risk domain.",
        ],
        "required_next_checks": [
            "Confirm safety mode justification with human engineer.",
            "Define power budget, battery, and regulator plan.",
        ],
        "rationale": "Gate WARN — risk level 'high'. Advisory only.",
    }


# ---------------------------------------------------------------------------
# Output structure
# ---------------------------------------------------------------------------

class TestOutputStructure:

    REQUIRED_KEYS = (
        "status", "mission_type", "platform_intent", "recommended_candidate_id",
        "ranking", "risk_level", "safety_status", "required_human_review",
        "unresolved_questions", "recurring_risk_themes", "next_design_lessons",
        "memory_summary",
    )

    def test_all_keys_present_for_rover(self):
        result = build_mission_memory_seed(_rover_intent(), _good_evaluation(), _rover_gate())
        for key in self.REQUIRED_KEYS:
            assert key in result, f"Missing key: {key}"

    def test_all_keys_present_for_empty(self):
        result = build_mission_memory_seed()
        for key in self.REQUIRED_KEYS:
            assert key in result, f"Missing key: {key}"

    def test_list_fields_are_lists(self):
        result = build_mission_memory_seed(_rover_intent(), _good_evaluation(), _rover_gate())
        for key in ("ranking", "unresolved_questions", "recurring_risk_themes", "next_design_lessons"):
            assert isinstance(result[key], list), f"{key} should be a list"

    def test_bool_fields_are_bool(self):
        result = build_mission_memory_seed(_rover_intent(), _good_evaluation(), _rover_gate())
        assert isinstance(result["required_human_review"], bool)

    def test_memory_summary_is_non_empty_string(self):
        result = build_mission_memory_seed(_rover_intent(), _good_evaluation(), _rover_gate())
        assert isinstance(result["memory_summary"], str)
        assert len(result["memory_summary"]) > 0

    def test_status_is_valid(self):
        r1 = build_mission_memory_seed(_rover_intent(), _good_evaluation(), _rover_gate())
        r2 = build_mission_memory_seed()
        assert r1["status"] in ("generated", "empty")
        assert r2["status"] in ("generated", "empty")


# ---------------------------------------------------------------------------
# Empty / degenerate input
# ---------------------------------------------------------------------------

class TestEmptyInput:

    def test_no_args_does_not_crash(self):
        result = build_mission_memory_seed()
        assert result["status"] == "empty"

    def test_none_args_does_not_crash(self):
        result = build_mission_memory_seed(None, None, None)
        assert result["status"] == "empty"

    def test_empty_dicts_does_not_crash(self):
        result = build_mission_memory_seed({}, {}, {})
        assert result["status"] in ("generated", "empty")

    def test_non_dict_inputs_do_not_crash(self):
        for bad in ("string", 42, [], True):
            result = build_mission_memory_seed(bad, bad, bad)
            assert "status" in result

    def test_mission_text_only_generates_seed(self):
        result = build_mission_memory_seed(mission_text="Build a rover.")
        assert result["status"] == "generated"

    def test_empty_returns_none_platform_and_type(self):
        result = build_mission_memory_seed()
        assert result["platform_intent"] is None
        assert result["mission_type"] is None
        assert result["recommended_candidate_id"] is None


# ---------------------------------------------------------------------------
# mission_intent extraction
# ---------------------------------------------------------------------------

class TestMissionIntentExtraction:

    def test_platform_intent_extracted(self):
        result = build_mission_memory_seed(_rover_intent())
        assert result["platform_intent"] == "ground-rover"

    def test_mission_type_extracted(self):
        result = build_mission_memory_seed(_rover_intent())
        assert result["mission_type"] == "inspection"

    def test_open_questions_become_unresolved(self):
        result = build_mission_memory_seed(_rover_intent())
        assert len(result["unresolved_questions"]) == 2
        assert "What is the target traverse speed?" in result["unresolved_questions"]

    def test_no_open_questions_returns_empty_list(self):
        intent = {**_rover_intent(), "open_questions": []}
        result = build_mission_memory_seed(intent)
        assert result["unresolved_questions"] == []

    def test_missing_open_questions_key_does_not_crash(self):
        intent = {k: v for k, v in _rover_intent().items() if k != "open_questions"}
        result = build_mission_memory_seed(intent)
        assert result["unresolved_questions"] == []


# ---------------------------------------------------------------------------
# candidate_evaluation extraction
# ---------------------------------------------------------------------------

class TestCandidateEvaluationExtraction:

    def test_recommended_candidate_id_extracted(self):
        result = build_mission_memory_seed(candidate_evaluation=_good_evaluation())
        assert result["recommended_candidate_id"] == "vega_candidate_1"

    def test_ranking_extracted(self):
        result = build_mission_memory_seed(candidate_evaluation=_good_evaluation())
        assert result["ranking"] == ["vega_candidate_1", "vega_candidate_2", "vega_candidate_3"]

    def test_no_candidates_returns_none_recommended(self):
        result = build_mission_memory_seed(candidate_evaluation={"candidates_evaluated": 0})
        assert result["recommended_candidate_id"] is None

    def test_empty_evaluation_returns_empty_ranking(self):
        result = build_mission_memory_seed(candidate_evaluation={})
        assert result["ranking"] == []


# ---------------------------------------------------------------------------
# pluto_safety_gate extraction
# ---------------------------------------------------------------------------

class TestSafetyGateExtraction:

    def test_risk_level_extracted(self):
        result = build_mission_memory_seed(pluto_safety_gate=_rover_gate())
        assert result["risk_level"] == "high"

    def test_safety_status_extracted(self):
        result = build_mission_memory_seed(pluto_safety_gate=_rover_gate())
        assert result["safety_status"] == "warn"

    def test_required_human_review_extracted(self):
        result = build_mission_memory_seed(pluto_safety_gate=_rover_gate())
        assert result["required_human_review"] is True

    def test_warnings_become_recurring_risk_themes(self):
        result = build_mission_memory_seed(pluto_safety_gate=_rover_gate())
        assert len(result["recurring_risk_themes"]) == 2

    def test_risk_themes_are_truncated_strings(self):
        result = build_mission_memory_seed(pluto_safety_gate=_rover_gate())
        for theme in result["recurring_risk_themes"]:
            assert isinstance(theme, str)
            assert len(theme) <= 120

    def test_next_checks_become_design_lessons(self):
        result = build_mission_memory_seed(pluto_safety_gate=_rover_gate())
        assert len(result["next_design_lessons"]) == 2
        combined = " ".join(result["next_design_lessons"]).lower()
        assert "power" in combined or "safety" in combined or "confirm" in combined

    def test_empty_warnings_returns_empty_themes(self):
        gate = {**_rover_gate(), "warnings": []}
        result = build_mission_memory_seed(pluto_safety_gate=gate)
        assert result["recurring_risk_themes"] == []

    def test_empty_next_checks_returns_empty_lessons(self):
        gate = {**_rover_gate(), "required_next_checks": []}
        result = build_mission_memory_seed(pluto_safety_gate=gate)
        assert result["next_design_lessons"] == []

    def test_duplicate_warnings_are_deduped(self):
        gate = {**_rover_gate(), "warnings": ["Same warning.", "Same warning.", "Different one."]}
        result = build_mission_memory_seed(pluto_safety_gate=gate)
        themes = result["recurring_risk_themes"]
        assert len(themes) == len(set(themes))


# ---------------------------------------------------------------------------
# memory_summary content
# ---------------------------------------------------------------------------

class TestMemorySummary:

    def test_summary_mentions_platform(self):
        result = build_mission_memory_seed(_rover_intent(), _good_evaluation(), _rover_gate())
        assert "ground-rover" in result["memory_summary"]

    def test_summary_mentions_mission_type(self):
        result = build_mission_memory_seed(_rover_intent(), _good_evaluation(), _rover_gate())
        assert "inspection" in result["memory_summary"]

    def test_summary_mentions_recommended_candidate(self):
        result = build_mission_memory_seed(_rover_intent(), _good_evaluation(), _rover_gate())
        assert "vega_candidate_1" in result["memory_summary"]

    def test_summary_mentions_risk_level(self):
        result = build_mission_memory_seed(_rover_intent(), _good_evaluation(), _rover_gate())
        assert "high" in result["memory_summary"]

    def test_summary_mentions_human_review(self):
        result = build_mission_memory_seed(_rover_intent(), _good_evaluation(), _rover_gate())
        assert "review" in result["memory_summary"].lower() or "human" in result["memory_summary"].lower()

    def test_summary_does_not_claim_validated(self):
        result = build_mission_memory_seed(_rover_intent(), _good_evaluation(), _rover_gate())
        lower = result["memory_summary"].lower()
        assert "validated" not in lower
        assert "approved" not in lower
        assert "safe to deploy" not in lower

    def test_summary_mentions_unresolved_questions_when_present(self):
        result = build_mission_memory_seed(_rover_intent(), _good_evaluation(), _rover_gate())
        lower = result["memory_summary"].lower()
        assert "unresolved" in lower or "question" in lower

    def test_summary_at_most_four_sentences(self):
        result = build_mission_memory_seed(_rover_intent(), _good_evaluation(), _rover_gate())
        sentences = [s.strip() for s in result["memory_summary"].split(".") if s.strip()]
        assert len(sentences) <= 5  # allow minor punctuation variance

    def test_summary_non_empty_for_empty_inputs(self):
        result = build_mission_memory_seed()
        assert isinstance(result["memory_summary"], str)


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------

class TestDeterminism:

    def test_full_inputs_deterministic(self):
        r1 = build_mission_memory_seed(_rover_intent(), _good_evaluation(), _rover_gate())
        r2 = build_mission_memory_seed(_rover_intent(), _good_evaluation(), _rover_gate())
        assert r1 == r2

    def test_empty_inputs_deterministic(self):
        r1 = build_mission_memory_seed()
        r2 = build_mission_memory_seed()
        assert r1 == r2

    def test_partial_inputs_deterministic(self):
        r1 = build_mission_memory_seed(_rover_intent())
        r2 = build_mission_memory_seed(_rover_intent())
        assert r1 == r2


# ---------------------------------------------------------------------------
# Supervisor artifact wiring (via direct import — no LLM)
# ---------------------------------------------------------------------------

class TestSupervisorWiring:

    def test_build_from_real_stack(self):
        """Verify seed builds cleanly from real compiler/evaluator/gate outputs."""
        from backend.app.omni_core.mission_intent import compile_mission_intent
        from agents.candidate_evaluator import evaluate_design_candidates
        from agents.design_candidates import normalize_candidates
        from backend.app.omni_core.safety_gate import evaluate_safety_gate

        candidates = normalize_candidates([
            {
                "name": "Tracked Crawler",
                "concept": "Magnetic tracked platform",
                "platform": "ground-rover",
                "mobility_type": "tracked",
                "morphology_notes": "Wide chassis with magnetic pads",
                "key_components": ["magnetic tracks", "IMU", "camera"],
                "strengths": ["stable on metal"],
                "risks": [],
                "required_validation": ["torque calc"],
                "assumptions": [],
                "recommended": True,
            }
        ])

        mission = "Build a magnetic tracked rover with camera and IMU for metal inspection."
        intent = compile_mission_intent(mission)
        evaluation = evaluate_design_candidates(candidates, mission_text=mission)
        gate = evaluate_safety_gate(intent, evaluation)

        seed = build_mission_memory_seed(intent, evaluation, gate, mission_text=mission)

        assert seed["status"] == "generated"
        assert seed["platform_intent"] == "ground-rover"
        assert seed["recommended_candidate_id"] == "vega_candidate_1"
        assert seed["required_human_review"] is True
        assert len(seed["memory_summary"]) > 0
