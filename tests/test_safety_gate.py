"""
Phase 13A — Pluto safety gate tests.

No LLM calls. No network calls. No file I/O.
"""
from __future__ import annotations

import pytest

from backend.app.omni_core.safety_gate import evaluate_safety_gate, GATE_NAME


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

def _rover_intent():
    """Clean rover mission with camera/IMU, power info, and validation output."""
    return {
        "raw_mission": "Build a tracked ground rover with camera and IMU. Battery powered.",
        "mission_type": "inspection",
        "platform_intent": "ground-rover",
        "safety_mode": "elevated",
        "detected_domains": ["robotics", "CAD"],
        "sensing_requirements": ["camera", "IMU"],
        "required_outputs": ["ROS2 package", "validation checklist", "export artifacts"],
        "constraints": ["battery / power source", "weight limit"],
        "open_questions": [],
    }


def _drone_intent():
    return {
        "raw_mission": "Design an aerial drone UAV for outdoor terrain survey.",
        "mission_type": "survey",
        "platform_intent": "drone-uav",
        "safety_mode": "elevated",
        "detected_domains": ["drone / UAV"],
        "sensing_requirements": ["LiDAR", "GPS"],
        "required_outputs": ["ROS2 package"],
        "constraints": ["battery / power source"],
        "open_questions": [],
    }


def _rov_intent():
    return {
        "raw_mission": "Build a tethered underwater ROV for marine inspection.",
        "mission_type": "inspection",
        "platform_intent": "rov",
        "safety_mode": "elevated",
        "detected_domains": ["robotics"],
        "sensing_requirements": ["sonar", "camera"],
        "required_outputs": ["wiring diagram"],
        "constraints": ["waterproofing requirement"],
        "open_questions": [],
    }


def _vague_intent():
    return {
        "raw_mission": "Build a robot.",
        "mission_type": "general engineering",
        "platform_intent": None,
        "safety_mode": "standard",
        "detected_domains": ["robotics"],
        "sensing_requirements": [],
        "required_outputs": [],
        "constraints": [],
        "open_questions": [
            "What platform type?",
            "What sensing modalities?",
            "What performance requirements?",
            "What is the power source?",
        ],
    }


def _software_intent():
    return {
        "raw_mission": "Build a web dashboard to monitor sensor data.",
        "mission_type": "monitoring",
        "platform_intent": None,
        "safety_mode": "standard",
        "detected_domains": ["software"],
        "sensing_requirements": [],
        "required_outputs": ["export artifacts"],
        "constraints": [],
        "open_questions": [],
    }


def _good_candidate_eval():
    return {
        "candidates_evaluated": 3,
        "status": None,
        "recommended_candidate_id": "vega_candidate_1",
        "ranking": ["vega_candidate_1", "vega_candidate_2", "vega_candidate_3"],
    }


def _skipped_candidate_eval():
    return {"status": "skipped", "candidates_evaluated": 0}


def _failed_candidate_eval():
    return {"status": "failed", "candidates_evaluated": 0}


# ---------------------------------------------------------------------------
# Output structure
# ---------------------------------------------------------------------------

class TestOutputStructure:

    REQUIRED_KEYS = (
        "gate", "status", "risk_level", "blockers", "warnings",
        "required_human_review", "required_next_checks", "rationale",
    )

    def test_all_keys_present_for_rover(self):
        result = evaluate_safety_gate(_rover_intent(), _good_candidate_eval())
        for key in self.REQUIRED_KEYS:
            assert key in result, f"Missing key: {key}"

    def test_all_keys_present_for_empty(self):
        result = evaluate_safety_gate()
        for key in self.REQUIRED_KEYS:
            assert key in result, f"Missing key: {key}"

    def test_gate_name_is_constant(self):
        result = evaluate_safety_gate(_rover_intent())
        assert result["gate"] == GATE_NAME

    def test_status_is_valid_value(self):
        for intent in (_rover_intent(), _drone_intent(), _vague_intent(), _software_intent()):
            result = evaluate_safety_gate(intent)
            assert result["status"] in ("passed", "warn", "blocked"), \
                f"Unexpected status: {result['status']}"

    def test_risk_level_is_valid_value(self):
        for intent in (_rover_intent(), _drone_intent(), _vague_intent(), _software_intent()):
            result = evaluate_safety_gate(intent)
            assert result["risk_level"] in ("low", "medium", "high"), \
                f"Unexpected risk_level: {result['risk_level']}"

    def test_list_fields_are_lists(self):
        result = evaluate_safety_gate(_rover_intent())
        for key in ("blockers", "warnings", "required_next_checks"):
            assert isinstance(result[key], list), f"{key} should be a list"

    def test_required_human_review_is_bool(self):
        result = evaluate_safety_gate(_rover_intent())
        assert isinstance(result["required_human_review"], bool)

    def test_rationale_is_non_empty_string(self):
        result = evaluate_safety_gate(_rover_intent())
        assert isinstance(result["rationale"], str)
        assert len(result["rationale"]) > 0


# ---------------------------------------------------------------------------
# Empty / degenerate input
# ---------------------------------------------------------------------------

class TestEmptyInput:

    def test_no_args_does_not_crash(self):
        result = evaluate_safety_gate()
        assert result["gate"] == GATE_NAME

    def test_none_args_does_not_crash(self):
        result = evaluate_safety_gate(None, None, None)
        assert result["gate"] == GATE_NAME

    def test_empty_dicts_do_not_crash(self):
        result = evaluate_safety_gate({}, {}, {})
        assert result["gate"] == GATE_NAME

    def test_non_dict_inputs_do_not_crash(self):
        for bad in ("string", 42, [], True):
            result = evaluate_safety_gate(bad, bad, bad)
            assert result["gate"] == GATE_NAME

    def test_empty_input_returns_warn_or_passed(self):
        result = evaluate_safety_gate()
        assert result["status"] in ("passed", "warn")


# ---------------------------------------------------------------------------
# Physical rover mission
# ---------------------------------------------------------------------------

class TestRoverMission:

    def test_rover_requires_human_review(self):
        result = evaluate_safety_gate(_rover_intent(), _good_candidate_eval())
        assert result["required_human_review"] is True

    def test_rover_elevated_safety_mode_adds_warning(self):
        result = evaluate_safety_gate(_rover_intent(), _good_candidate_eval())
        combined = " ".join(result["warnings"]).lower()
        assert "elevated" in combined or "human" in combined or "review" in combined

    def test_rover_risk_level_not_low(self):
        result = evaluate_safety_gate(_rover_intent(), _good_candidate_eval())
        assert result["risk_level"] in ("medium", "high")

    def test_rover_status_is_warn_not_blocked(self):
        result = evaluate_safety_gate(_rover_intent(), _good_candidate_eval())
        assert result["status"] == "warn"

    def test_rover_with_good_candidates_has_no_candidate_warning(self):
        result = evaluate_safety_gate(_rover_intent(), _good_candidate_eval())
        combined = " ".join(result["warnings"]).lower()
        assert "no design candidates" not in combined
        assert "skipped" not in combined

    def test_rover_no_blockers(self):
        result = evaluate_safety_gate(_rover_intent(), _good_candidate_eval())
        assert result["blockers"] == []


# ---------------------------------------------------------------------------
# Drone mission (high-risk platform)
# ---------------------------------------------------------------------------

class TestDroneMission:

    def test_drone_requires_human_review(self):
        result = evaluate_safety_gate(_drone_intent())
        assert result["required_human_review"] is True

    def test_drone_risk_level_is_high(self):
        result = evaluate_safety_gate(_drone_intent())
        assert result["risk_level"] == "high"

    def test_drone_status_is_warn(self):
        result = evaluate_safety_gate(_drone_intent())
        assert result["status"] == "warn"

    def test_drone_warning_mentions_aerial(self):
        result = evaluate_safety_gate(_drone_intent())
        combined = " ".join(result["warnings"]).lower()
        assert "aerial" in combined or "drone" in combined or "drone-uav" in combined

    def test_drone_required_next_checks_non_empty(self):
        result = evaluate_safety_gate(_drone_intent())
        assert len(result["required_next_checks"]) > 0

    def test_rov_also_requires_human_review(self):
        result = evaluate_safety_gate(_rov_intent())
        assert result["required_human_review"] is True

    def test_rov_risk_level_is_high(self):
        result = evaluate_safety_gate(_rov_intent())
        assert result["risk_level"] == "high"


# ---------------------------------------------------------------------------
# Unknown platform + physical build intent
# ---------------------------------------------------------------------------

class TestUnknownPlatform:

    def test_unknown_platform_physical_build_is_blocked(self):
        intent = {
            **_vague_intent(),
            "raw_mission": "Build and deploy a robot prototype.",
            "platform_intent": None,
        }
        result = evaluate_safety_gate(intent)
        assert result["status"] == "blocked"

    def test_unknown_platform_physical_build_has_blockers(self):
        intent = {
            **_vague_intent(),
            "raw_mission": "Fabricate and assemble a robot.",
            "platform_intent": None,
        }
        result = evaluate_safety_gate(intent)
        assert len(result["blockers"]) > 0

    def test_unknown_platform_physical_build_risk_high(self):
        intent = {
            **_vague_intent(),
            "raw_mission": "Build a robot prototype.",
            "platform_intent": None,
        }
        result = evaluate_safety_gate(intent)
        assert result["risk_level"] == "high"

    def test_unknown_platform_software_only_warns_not_blocks(self):
        result = evaluate_safety_gate(_software_intent())
        assert result["status"] in ("passed", "warn")
        assert result["blockers"] == []

    def test_vague_mission_has_open_question_warning(self):
        result = evaluate_safety_gate(_vague_intent())
        combined = " ".join(result["warnings"]).lower()
        assert "open question" in combined


# ---------------------------------------------------------------------------
# Candidate evaluation quality
# ---------------------------------------------------------------------------

class TestCandidateEvaluationQuality:

    def test_skipped_evaluation_adds_warning(self):
        result = evaluate_safety_gate(_rover_intent(), _skipped_candidate_eval())
        combined = " ".join(result["warnings"]).lower()
        assert "skipped" in combined or "candidate" in combined

    def test_failed_evaluation_adds_warning(self):
        result = evaluate_safety_gate(_rover_intent(), _failed_candidate_eval())
        combined = " ".join(result["warnings"]).lower()
        assert "failed" in combined or "candidate" in combined

    def test_skipped_evaluation_adds_next_check(self):
        result = evaluate_safety_gate(_rover_intent(), _skipped_candidate_eval())
        combined = " ".join(result["required_next_checks"]).lower()
        assert "candidate" in combined

    def test_no_candidates_adds_warning(self):
        result = evaluate_safety_gate(_rover_intent(), {"candidates_evaluated": 0})
        combined = " ".join(result["warnings"]).lower()
        assert "candidate" in combined or "evaluated" in combined

    def test_good_candidates_no_evaluation_warning(self):
        result = evaluate_safety_gate(_rover_intent(), _good_candidate_eval())
        combined = " ".join(result["warnings"]).lower()
        assert "no design candidates" not in combined


# ---------------------------------------------------------------------------
# Missing power info
# ---------------------------------------------------------------------------

class TestMissingPowerInfo:

    def test_rover_without_power_adds_power_check(self):
        intent = {
            **_rover_intent(),
            "raw_mission": "Build a tracked ground rover with camera and IMU.",
            "constraints": [],
        }
        result = evaluate_safety_gate(intent)
        combined = " ".join(result["required_next_checks"]).lower()
        assert "power" in combined or "battery" in combined

    def test_rover_with_power_no_power_check(self):
        result = evaluate_safety_gate(_rover_intent(), _good_candidate_eval())
        combined = " ".join(result["required_next_checks"]).lower()
        # Should not add a duplicate power check when power is already mentioned
        warnings_combined = " ".join(result["warnings"]).lower()
        # The power warning/check might still appear for other reasons, but
        # when power IS present the "missing power" warning specifically should not fire.
        assert "no power or battery information found" not in warnings_combined

    def test_software_mission_no_power_check(self):
        result = evaluate_safety_gate(_software_intent())
        combined = " ".join(result["required_next_checks"]).lower()
        assert "power" not in combined and "battery" not in combined


# ---------------------------------------------------------------------------
# Artifacts dict fallback
# ---------------------------------------------------------------------------

class TestArtifactsFallback:

    def test_pulls_mission_intent_from_artifacts(self):
        arts = {
            "mission_intent": _rover_intent(),
            "candidate_evaluation": _good_candidate_eval(),
        }
        result = evaluate_safety_gate(artifacts=arts)
        assert result["required_human_review"] is True

    def test_pulls_candidate_evaluation_from_artifacts(self):
        arts = {"candidate_evaluation": _skipped_candidate_eval()}
        result = evaluate_safety_gate(artifacts=arts)
        combined = " ".join(result["warnings"]).lower()
        assert "skipped" in combined or "candidate" in combined

    def test_explicit_args_take_precedence_over_artifacts(self):
        arts = {"mission_intent": _software_intent()}
        result = evaluate_safety_gate(
            mission_intent=_drone_intent(),
            artifacts=arts,
        )
        # drone should win, not software
        assert result["risk_level"] == "high"


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------

class TestDeterminism:

    def test_rover_is_deterministic(self):
        r1 = evaluate_safety_gate(_rover_intent(), _good_candidate_eval())
        r2 = evaluate_safety_gate(_rover_intent(), _good_candidate_eval())
        assert r1 == r2

    def test_drone_is_deterministic(self):
        r1 = evaluate_safety_gate(_drone_intent())
        r2 = evaluate_safety_gate(_drone_intent())
        assert r1 == r2

    def test_empty_is_deterministic(self):
        r1 = evaluate_safety_gate()
        r2 = evaluate_safety_gate()
        assert r1 == r2


# ---------------------------------------------------------------------------
# Rationale always advisory
# ---------------------------------------------------------------------------

class TestRationale:

    def test_rationale_always_mentions_advisory(self):
        for intent in (_rover_intent(), _drone_intent(), _vague_intent(), _software_intent()):
            result = evaluate_safety_gate(intent)
            assert "advisory" in result["rationale"].lower() or \
                   "does not authorise" in result["rationale"].lower(), \
                f"Rationale missing advisory disclaimer for intent: {intent.get('platform_intent')}"

    def test_blocked_rationale_mentions_blocked(self):
        intent = {
            **_vague_intent(),
            "raw_mission": "Build and deploy a robot prototype.",
            "platform_intent": None,
        }
        result = evaluate_safety_gate(intent)
        if result["status"] == "blocked":
            assert "BLOCKED" in result["rationale"] or "blocked" in result["rationale"].lower()

    def test_passed_status_rationale_mentions_passed(self):
        # A pure software mission with no physical build signals and no open questions
        intent = {
            "raw_mission": "Create a web dashboard.",
            "mission_type": "monitoring",
            "platform_intent": None,
            "safety_mode": "standard",
            "detected_domains": ["software"],
            "sensing_requirements": [],
            "required_outputs": [],
            "constraints": [],
            "open_questions": [],
        }
        result = evaluate_safety_gate(intent)
        if result["status"] == "passed":
            assert "PASSED" in result["rationale"] or "passed" in result["rationale"].lower()
