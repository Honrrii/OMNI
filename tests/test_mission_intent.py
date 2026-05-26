"""
Phase 12A — Deterministic mission intent compiler tests.

No LLM calls. No network calls. No file I/O.
"""
from __future__ import annotations

import pytest

from backend.app.omni_core.mission_intent import compile_mission_intent


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

ROVER_MISSION = (
    "Build a magnetic tracked ground rover for metal surface inspection. "
    "It should carry a camera and IMU. Export ROS2 packages and CAD model. "
    "Needs validation checklist. Battery powered, weight and size constrained."
)

DRONE_MISSION = (
    "Design an aerial drone UAV for outdoor terrain survey. "
    "Equip with LiDAR and GPS. Generate ROS2 nav2 package and simulation."
)

ROV_MISSION = (
    "Build a tethered underwater ROV for marine inspection. "
    "Include sonar and camera. Produce wiring diagram and validation checklist."
)

VAGUE_MISSION = "Build a robot."

EMPTY_MISSION = ""


# ---------------------------------------------------------------------------
# Output structure
# ---------------------------------------------------------------------------

class TestOutputStructure:

    REQUIRED_KEYS = (
        "raw_mission", "mission_type", "platform_intent", "detected_domains",
        "operating_environment", "mobility_requirements", "sensing_requirements",
        "required_outputs", "success_criteria", "constraints", "assumptions",
        "open_questions", "safety_mode",
    )

    def test_all_keys_present_for_rover(self):
        result = compile_mission_intent(ROVER_MISSION)
        for key in self.REQUIRED_KEYS:
            assert key in result, f"Missing key: {key}"

    def test_all_keys_present_for_empty(self):
        result = compile_mission_intent(EMPTY_MISSION)
        for key in self.REQUIRED_KEYS:
            assert key in result, f"Missing key: {key}"

    def test_non_string_input_returns_valid_structure(self):
        for bad in (None, 42, [], {}):
            result = compile_mission_intent(bad)
            for key in self.REQUIRED_KEYS:
                assert key in result, f"Missing key '{key}' for input {bad!r}"

    def test_list_fields_are_lists(self):
        result = compile_mission_intent(ROVER_MISSION)
        for key in ("detected_domains", "operating_environment", "mobility_requirements",
                    "sensing_requirements", "required_outputs", "success_criteria",
                    "constraints", "assumptions", "open_questions"):
            assert isinstance(result[key], list), f"{key} should be a list"

    def test_string_fields_are_strings(self):
        result = compile_mission_intent(ROVER_MISSION)
        assert isinstance(result["mission_type"], str)
        assert isinstance(result["safety_mode"], str)
        assert isinstance(result["raw_mission"], str)

    def test_platform_intent_is_string_or_none(self):
        result = compile_mission_intent(ROVER_MISSION)
        assert result["platform_intent"] is None or isinstance(result["platform_intent"], str)

    def test_raw_mission_preserved(self):
        result = compile_mission_intent(ROVER_MISSION)
        assert result["raw_mission"] == ROVER_MISSION


# ---------------------------------------------------------------------------
# Platform resolution
# ---------------------------------------------------------------------------

class TestPlatformResolution:

    def test_rover_mission_resolves_ground_rover(self):
        result = compile_mission_intent(ROVER_MISSION)
        assert result["platform_intent"] == "ground-rover"

    def test_drone_mission_resolves_drone_uav(self):
        result = compile_mission_intent(DRONE_MISSION)
        assert result["platform_intent"] == "drone-uav"

    def test_rov_mission_resolves_rov(self):
        result = compile_mission_intent(ROV_MISSION)
        assert result["platform_intent"] == "rov"

    def test_hexapod_mission_resolves_hexapod(self):
        result = compile_mission_intent("Design a hexapod walker with legged locomotion.")
        assert result["platform_intent"] == "hexapod"

    def test_auv_mission_resolves_auv(self):
        result = compile_mission_intent("Build an autonomous submarine AUV for ocean mapping.")
        assert result["platform_intent"] == "auv"

    def test_vague_mission_platform_is_none(self):
        result = compile_mission_intent(VAGUE_MISSION)
        assert result["platform_intent"] is None

    def test_empty_mission_platform_is_none(self):
        result = compile_mission_intent(EMPTY_MISSION)
        assert result["platform_intent"] is None


# ---------------------------------------------------------------------------
# Sensing requirements
# ---------------------------------------------------------------------------

class TestSensingRequirements:

    def test_camera_detected_in_rover_mission(self):
        result = compile_mission_intent(ROVER_MISSION)
        assert "camera" in result["sensing_requirements"]

    def test_imu_detected_in_rover_mission(self):
        result = compile_mission_intent(ROVER_MISSION)
        assert "IMU" in result["sensing_requirements"]

    def test_lidar_detected_in_drone_mission(self):
        result = compile_mission_intent(DRONE_MISSION)
        assert "LiDAR" in result["sensing_requirements"]

    def test_gps_detected_in_drone_mission(self):
        result = compile_mission_intent(DRONE_MISSION)
        assert "GPS" in result["sensing_requirements"]

    def test_sonar_detected_in_rov_mission(self):
        result = compile_mission_intent(ROV_MISSION)
        assert "sonar" in result["sensing_requirements"]

    def test_no_false_sensing_in_empty_mission(self):
        result = compile_mission_intent(EMPTY_MISSION)
        assert result["sensing_requirements"] == []


# ---------------------------------------------------------------------------
# Required outputs
# ---------------------------------------------------------------------------

class TestRequiredOutputs:

    def test_ros2_package_detected_in_rover_mission(self):
        result = compile_mission_intent(ROVER_MISSION)
        assert "ROS2 package" in result["required_outputs"]

    def test_cad_model_detected_in_rover_mission(self):
        result = compile_mission_intent(ROVER_MISSION)
        assert "CAD model" in result["required_outputs"]

    def test_validation_checklist_detected_in_rover_mission(self):
        result = compile_mission_intent(ROVER_MISSION)
        assert "validation checklist" in result["required_outputs"]

    def test_export_artifacts_detected_in_rover_mission(self):
        result = compile_mission_intent(ROVER_MISSION)
        assert "export artifacts" in result["required_outputs"]

    def test_ros2_detected_in_drone_mission(self):
        result = compile_mission_intent(DRONE_MISSION)
        assert "ROS2 package" in result["required_outputs"]

    def test_simulation_detected_in_drone_mission(self):
        result = compile_mission_intent(DRONE_MISSION)
        assert "simulation environment" in result["required_outputs"]

    def test_wiring_diagram_detected_in_rov_mission(self):
        result = compile_mission_intent(ROV_MISSION)
        assert "wiring diagram" in result["required_outputs"]

    def test_no_false_outputs_in_empty_mission(self):
        result = compile_mission_intent(EMPTY_MISSION)
        assert result["required_outputs"] == []


# ---------------------------------------------------------------------------
# Open questions
# ---------------------------------------------------------------------------

class TestOpenQuestions:

    def test_vague_mission_has_open_questions(self):
        result = compile_mission_intent(VAGUE_MISSION)
        assert len(result["open_questions"]) > 0

    def test_vague_mission_asks_about_platform(self):
        result = compile_mission_intent(VAGUE_MISSION)
        combined = " ".join(result["open_questions"]).lower()
        assert "platform" in combined

    def test_empty_mission_has_open_questions(self):
        result = compile_mission_intent(EMPTY_MISSION)
        assert len(result["open_questions"]) > 0

    def test_vague_short_mission_flagged_in_open_questions(self):
        result = compile_mission_intent("Make a robot.")
        combined = " ".join(result["open_questions"]).lower()
        assert "short" in combined or "detail" in combined or "description" in combined

    def test_fully_specified_mission_fewer_questions_than_vague(self):
        vague = compile_mission_intent(VAGUE_MISSION)
        full = compile_mission_intent(ROVER_MISSION)
        assert len(full["open_questions"]) < len(vague["open_questions"])

    def test_mission_without_sensing_asks_sensing_question(self):
        result = compile_mission_intent("Build a rover that drives around.")
        combined = " ".join(result["open_questions"]).lower()
        assert "sensing" in combined or "sensor" in combined or "imu" in combined

    def test_mission_without_power_asks_power_question(self):
        result = compile_mission_intent("Build a rover that drives around.")
        combined = " ".join(result["open_questions"]).lower()
        assert "power" in combined or "energy" in combined or "battery" in combined


# ---------------------------------------------------------------------------
# Mobility requirements
# ---------------------------------------------------------------------------

class TestMobilityRequirements:

    def test_tracked_detected_in_rover_mission(self):
        result = compile_mission_intent(ROVER_MISSION)
        assert "tracked locomotion" in result["mobility_requirements"]

    def test_magnetic_adhesion_detected_in_rover_mission(self):
        result = compile_mission_intent(ROVER_MISSION)
        assert "magnetic adhesion" in result["mobility_requirements"]

    def test_aerial_detected_in_drone_mission(self):
        result = compile_mission_intent(DRONE_MISSION)
        assert any("aerial" in m for m in result["mobility_requirements"])

    def test_underwater_propulsion_detected_in_rov_mission(self):
        result = compile_mission_intent(ROV_MISSION)
        assert any("underwater" in m for m in result["mobility_requirements"])


# ---------------------------------------------------------------------------
# Detected domains
# ---------------------------------------------------------------------------

class TestDetectedDomains:

    def test_ros2_domain_detected_in_rover_mission(self):
        result = compile_mission_intent(ROVER_MISSION)
        assert "ROS2" in result["detected_domains"]

    def test_cad_domain_detected_in_rover_mission(self):
        result = compile_mission_intent(ROVER_MISSION)
        assert "CAD" in result["detected_domains"]

    def test_drone_domain_detected_in_drone_mission(self):
        result = compile_mission_intent(DRONE_MISSION)
        assert "drone / UAV" in result["detected_domains"]

    def test_inspection_domain_detected_in_rover_mission(self):
        result = compile_mission_intent(ROVER_MISSION)
        assert "inspection / NDT" in result["detected_domains"]

    def test_empty_mission_has_empty_domains(self):
        result = compile_mission_intent(EMPTY_MISSION)
        assert result["detected_domains"] == []


# ---------------------------------------------------------------------------
# Operating environment
# ---------------------------------------------------------------------------

class TestOperatingEnvironment:

    def test_metal_surface_env_detected_in_rover_mission(self):
        result = compile_mission_intent(ROVER_MISSION)
        assert "metal surface / ferromagnetic" in result["operating_environment"]

    def test_outdoor_env_detected_in_drone_mission(self):
        result = compile_mission_intent(DRONE_MISSION)
        assert "outdoor" in result["operating_environment"]

    def test_underwater_env_detected_in_rov_mission(self):
        result = compile_mission_intent(ROV_MISSION)
        assert "underwater" in result["operating_environment"]

    def test_marine_env_detected_in_rov_mission(self):
        result = compile_mission_intent(ROV_MISSION)
        assert "marine environment" in result["operating_environment"]


# ---------------------------------------------------------------------------
# Safety mode
# ---------------------------------------------------------------------------

class TestSafetyMode:

    def test_rover_mission_elevated_safety(self):
        result = compile_mission_intent(ROVER_MISSION)
        assert result["safety_mode"] == "elevated"

    def test_aerial_mission_elevated_safety(self):
        result = compile_mission_intent(DRONE_MISSION)
        assert result["safety_mode"] == "elevated"

    def test_underwater_mission_elevated_safety(self):
        result = compile_mission_intent(ROV_MISSION)
        assert result["safety_mode"] == "elevated"

    def test_benign_software_mission_standard_safety(self):
        result = compile_mission_intent("Build a web dashboard to monitor sensor data.")
        assert result["safety_mode"] == "standard"

    def test_empty_mission_standard_safety(self):
        result = compile_mission_intent(EMPTY_MISSION)
        assert result["safety_mode"] == "standard"


# ---------------------------------------------------------------------------
# Constraints
# ---------------------------------------------------------------------------

class TestConstraints:

    def test_battery_constraint_detected_in_rover_mission(self):
        result = compile_mission_intent(ROVER_MISSION)
        assert "battery / power source" in result["constraints"]

    def test_weight_constraint_detected_in_rover_mission(self):
        result = compile_mission_intent(ROVER_MISSION)
        assert "weight limit" in result["constraints"]

    def test_size_constraint_detected_in_rover_mission(self):
        result = compile_mission_intent(ROVER_MISSION)
        assert "size constraint" in result["constraints"]

    def test_no_false_constraints_in_empty_mission(self):
        result = compile_mission_intent(EMPTY_MISSION)
        assert result["constraints"] == []


# ---------------------------------------------------------------------------
# Mission type
# ---------------------------------------------------------------------------

class TestMissionType:

    def test_inspection_mission_type_for_rover(self):
        result = compile_mission_intent(ROVER_MISSION)
        assert result["mission_type"] == "inspection"

    def test_survey_mission_type_for_drone(self):
        result = compile_mission_intent(DRONE_MISSION)
        assert result["mission_type"] == "survey"

    def test_general_engineering_for_vague_mission(self):
        result = compile_mission_intent(VAGUE_MISSION)
        assert result["mission_type"] == "general engineering"

    def test_mapping_mission_type(self):
        result = compile_mission_intent("Build a robot that maps the environment autonomously.")
        assert result["mission_type"] == "mapping"


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------

class TestDeterminism:

    def test_rover_result_is_deterministic(self):
        r1 = compile_mission_intent(ROVER_MISSION)
        r2 = compile_mission_intent(ROVER_MISSION)
        assert r1 == r2

    def test_drone_result_is_deterministic(self):
        r1 = compile_mission_intent(DRONE_MISSION)
        r2 = compile_mission_intent(DRONE_MISSION)
        assert r1 == r2

    def test_empty_result_is_deterministic(self):
        r1 = compile_mission_intent(EMPTY_MISSION)
        r2 = compile_mission_intent(EMPTY_MISSION)
        assert r1 == r2


# ---------------------------------------------------------------------------
# Assumptions always present
# ---------------------------------------------------------------------------

class TestAssumptions:

    def test_assumptions_always_non_empty(self):
        for text in (ROVER_MISSION, DRONE_MISSION, ROV_MISSION, VAGUE_MISSION, EMPTY_MISSION):
            result = compile_mission_intent(text)
            assert len(result["assumptions"]) > 0, f"No assumptions for: {text!r}"

    def test_assumptions_mention_concept_stage(self):
        result = compile_mission_intent(ROVER_MISSION)
        combined = " ".join(result["assumptions"]).lower()
        assert "concept" in combined
