"""
Phase 15A — AeroForge foundation tests.

No LLM calls. No network calls.
"""
from __future__ import annotations

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

PROPULSION_MISSION = (
    "Explore propulsion system architectures including turbine and jet engine "
    "concepts for a high-altitude research vehicle."
)

THERMAL_MATERIALS_MISSION = (
    "Analyze thermal protection and materials selection for an atmospheric reentry "
    "vehicle, including composite and ablative heat shield options."
)

ROCKET_MISSION = (
    "Design a rocket propulsion concept with nozzle and thrust analysis for a "
    "suborbital launch vehicle — concept stage only."
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _classify(mission_text="", mission_intent=None):
    from backend.app.aeroforge.foundation import classify_aeroforge_intent
    return classify_aeroforge_intent(mission_text=mission_text, mission_intent=mission_intent)


def _entry_gate(mission_text="", mission_intent=None, readiness=None):
    from backend.app.aeroforge.foundation import evaluate_aeroforge_entry_gate
    return evaluate_aeroforge_entry_gate(
        mission_text=mission_text,
        mission_intent=mission_intent,
        readiness=readiness,
    )


def _readiness(status: str) -> dict:
    return {"gate": "mission_intelligence_readiness", "status": status, "readiness_score": 0.8}


# ---------------------------------------------------------------------------
# Output shape — classify
# ---------------------------------------------------------------------------

class TestClassifyOutputShape:

    def test_module_field_is_aeroforge(self):
        r = _classify(ROVER_MISSION)
        assert r["module"] == "aeroforge"

    def test_status_is_valid(self):
        for mission in (ROVER_MISSION, DRONE_UAV_MISSION, AIRCRAFT_MISSION):
            r = _classify(mission)
            assert r["status"] in ("detected", "not_applicable", "blocked")

    def test_aerospace_detected_is_bool(self):
        r = _classify(ROVER_MISSION)
        assert isinstance(r["aerospace_detected"], bool)

    def test_aero_domains_is_list(self):
        r = _classify(DRONE_UAV_MISSION)
        assert isinstance(r["aero_domains"], list)

    def test_concept_stage_only_is_bool(self):
        r = _classify(DRONE_UAV_MISSION)
        assert isinstance(r["concept_stage_only"], bool)

    def test_prohibited_claims_is_list(self):
        r = _classify(DRONE_UAV_MISSION)
        assert isinstance(r["prohibited_claims"], list)

    def test_required_review_gates_is_list(self):
        r = _classify(DRONE_UAV_MISSION)
        assert isinstance(r["required_review_gates"], list)

    def test_allowed_outputs_is_list(self):
        r = _classify(DRONE_UAV_MISSION)
        assert isinstance(r["allowed_outputs"], list)

    def test_blocked_outputs_is_list(self):
        r = _classify(DRONE_UAV_MISSION)
        assert isinstance(r["blocked_outputs"], list)

    def test_rationale_is_non_empty_string(self):
        r = _classify(DRONE_UAV_MISSION)
        assert isinstance(r["rationale"], str)
        assert len(r["rationale"]) > 0

    def test_none_mission_text_does_not_crash(self):
        r = _classify(mission_text="")
        assert isinstance(r, dict)
        assert "status" in r


# ---------------------------------------------------------------------------
# Non-aerospace rover — not_applicable
# ---------------------------------------------------------------------------

class TestRoverNotApplicable:

    def test_rover_status_is_not_applicable(self):
        r = _classify(ROVER_MISSION)
        assert r["status"] == "not_applicable"

    def test_rover_aerospace_detected_false(self):
        r = _classify(ROVER_MISSION)
        assert r["aerospace_detected"] is False

    def test_rover_aero_domains_empty(self):
        r = _classify(ROVER_MISSION)
        assert r["aero_domains"] == []

    def test_rover_platform_hint_is_none(self):
        r = _classify(ROVER_MISSION)
        assert r["platform_hint"] is None

    def test_rover_concept_stage_only_false(self):
        r = _classify(ROVER_MISSION)
        assert r["concept_stage_only"] is False

    def test_rover_allowed_outputs_empty(self):
        r = _classify(ROVER_MISSION)
        assert r["allowed_outputs"] == []

    def test_rover_blocked_outputs_empty(self):
        r = _classify(ROVER_MISSION)
        assert r["blocked_outputs"] == []

    def test_rover_prohibited_claims_empty(self):
        r = _classify(ROVER_MISSION)
        assert r["prohibited_claims"] == []

    def test_empty_text_is_not_applicable(self):
        r = _classify(mission_text="")
        assert r["status"] == "not_applicable"
        assert r["aerospace_detected"] is False


# ---------------------------------------------------------------------------
# Drone/UAV mission
# ---------------------------------------------------------------------------

class TestDroneUAVDetection:

    def test_drone_uav_status_is_detected(self):
        r = _classify(DRONE_UAV_MISSION)
        assert r["status"] == "detected"

    def test_drone_uav_aerospace_detected_true(self):
        r = _classify(DRONE_UAV_MISSION)
        assert r["aerospace_detected"] is True

    def test_drone_uav_aero_domains_not_empty(self):
        r = _classify(DRONE_UAV_MISSION)
        assert len(r["aero_domains"]) > 0

    def test_drone_uav_airframe_detected(self):
        r = _classify(DRONE_UAV_MISSION)
        assert "airframe" in r["aero_domains"]

    def test_drone_uav_avionics_detected(self):
        r = _classify(DRONE_UAV_MISSION)
        assert "avionics" in r["aero_domains"]

    def test_drone_uav_platform_hint_is_drone(self):
        r = _classify(DRONE_UAV_MISSION)
        assert r["platform_hint"] == "drone-uav"

    def test_drone_uav_concept_stage_only_true(self):
        r = _classify(DRONE_UAV_MISSION)
        assert r["concept_stage_only"] is True

    def test_uav_keyword_alone_detects_aerospace(self):
        r = _classify("Design a UAV for remote sensing.")
        assert r["aerospace_detected"] is True

    def test_drone_keyword_alone_detects_aerospace(self):
        r = _classify("Build a drone with GPS navigation.")
        assert r["aerospace_detected"] is True


# ---------------------------------------------------------------------------
# Aircraft/wing/lift mission
# ---------------------------------------------------------------------------

class TestAircraftWingLiftDetection:

    def test_aircraft_status_detected(self):
        r = _classify(AIRCRAFT_MISSION)
        assert r["status"] == "detected"

    def test_aircraft_airframe_detected(self):
        r = _classify(AIRCRAFT_MISSION)
        assert "airframe" in r["aero_domains"]

    def test_aircraft_aerodynamics_detected(self):
        r = _classify(AIRCRAFT_MISSION)
        assert "aerodynamics" in r["aero_domains"]

    def test_wing_triggers_airframe(self):
        r = _classify("Design a wing profile for an experimental aircraft.")
        assert "airframe" in r["aero_domains"]

    def test_lift_triggers_aerodynamics(self):
        r = _classify("Analyze lift and drag coefficients for a wing design.")
        assert "aerodynamics" in r["aero_domains"]

    def test_drag_triggers_aerodynamics(self):
        r = _classify("Minimize drag on the airframe exterior.")
        assert "aerodynamics" in r["aero_domains"]

    def test_aircraft_platform_hint_fixed_wing(self):
        r = _classify("Design a fixed-wing aircraft airframe.")
        assert r["platform_hint"] == "fixed-wing-aircraft"

    def test_aerodynamics_keyword_detects(self):
        r = _classify("Study aerodynamics of high-speed vehicles.")
        assert "aerodynamics" in r["aero_domains"]


# ---------------------------------------------------------------------------
# Turbine/jet/propulsion mission
# ---------------------------------------------------------------------------

class TestPropulsionDetection:

    def test_propulsion_status_detected(self):
        r = _classify(PROPULSION_MISSION)
        assert r["status"] == "detected"

    def test_propulsion_domain_detected(self):
        r = _classify(PROPULSION_MISSION)
        assert "propulsion" in r["aero_domains"]

    def test_turbine_triggers_propulsion(self):
        r = _classify("Analyze a turbine blade design for compressor stages.")
        assert "propulsion" in r["aero_domains"]

    def test_jet_triggers_propulsion(self):
        r = _classify("Explore jet engine thermodynamic cycles.")
        assert "propulsion" in r["aero_domains"]

    def test_rocket_triggers_propulsion(self):
        r = _classify(ROCKET_MISSION)
        assert "propulsion" in r["aero_domains"]

    def test_rocket_platform_hint_launch_vehicle(self):
        r = _classify(ROCKET_MISSION)
        assert r["platform_hint"] == "launch-vehicle"

    def test_thrust_triggers_propulsion(self):
        r = _classify("Calculate thrust and nozzle exit velocity.")
        assert "propulsion" in r["aero_domains"]


# ---------------------------------------------------------------------------
# Thermal/materials mission
# ---------------------------------------------------------------------------

class TestThermalMaterialsDetection:

    def test_thermal_materials_status_detected(self):
        r = _classify(THERMAL_MATERIALS_MISSION)
        assert r["status"] == "detected"

    def test_thermal_domain_detected(self):
        r = _classify(THERMAL_MATERIALS_MISSION)
        assert "thermal" in r["aero_domains"]

    def test_materials_domain_detected(self):
        r = _classify(THERMAL_MATERIALS_MISSION)
        assert "materials" in r["aero_domains"]

    def test_heat_shield_triggers_thermal(self):
        r = _classify("Design a heat shield for atmospheric reentry.")
        assert "thermal" in r["aero_domains"]

    def test_composite_triggers_materials(self):
        r = _classify("Select composite materials for structural panels.")
        assert "materials" in r["aero_domains"]

    def test_ablative_triggers_both(self):
        r = _classify("Evaluate ablative coatings for the nose cone.")
        assert "thermal" in r["aero_domains"]
        assert "materials" in r["aero_domains"]

    def test_carbon_fiber_triggers_materials(self):
        r = _classify("Use carbon fiber panels for the fuselage skin.")
        assert "materials" in r["aero_domains"]


# ---------------------------------------------------------------------------
# Allowed outputs — concept stage only
# ---------------------------------------------------------------------------

class TestAllowedOutputs:

    def test_allowed_outputs_present_when_detected(self):
        r = _classify(AIRCRAFT_MISSION)
        assert len(r["allowed_outputs"]) > 0

    def test_allowed_outputs_contain_concept_taxonomy(self):
        r = _classify(AIRCRAFT_MISSION)
        combined = " ".join(r["allowed_outputs"]).lower()
        assert "concept" in combined

    def test_allowed_outputs_contain_simulation(self):
        r = _classify(AIRCRAFT_MISSION)
        combined = " ".join(r["allowed_outputs"]).lower()
        assert "simulation" in combined

    def test_allowed_outputs_contain_requirements(self):
        r = _classify(AIRCRAFT_MISSION)
        combined = " ".join(r["allowed_outputs"]).lower()
        assert "requirement" in combined

    def test_allowed_outputs_do_not_contain_fabrication_ready(self):
        r = _classify(AIRCRAFT_MISSION)
        combined = " ".join(r["allowed_outputs"]).lower()
        assert "fabrication-ready" not in combined

    def test_allowed_outputs_do_not_contain_flight_ready(self):
        r = _classify(AIRCRAFT_MISSION)
        combined = " ".join(r["allowed_outputs"]).lower()
        assert "flight-ready" not in combined

    def test_allowed_outputs_contain_safety_gap(self):
        r = _classify(AIRCRAFT_MISSION)
        combined = " ".join(r["allowed_outputs"]).lower()
        assert "safety" in combined or "validation" in combined

    def test_allowed_outputs_empty_when_not_applicable(self):
        r = _classify(ROVER_MISSION)
        assert r["allowed_outputs"] == []


# ---------------------------------------------------------------------------
# Blocked outputs — fabrication/flight-ready/airworthiness
# ---------------------------------------------------------------------------

class TestBlockedOutputs:

    def test_blocked_outputs_present_when_detected(self):
        r = _classify(AIRCRAFT_MISSION)
        assert len(r["blocked_outputs"]) > 0

    def test_blocked_contains_fabrication_ready(self):
        r = _classify(AIRCRAFT_MISSION)
        combined = " ".join(r["blocked_outputs"]).lower()
        assert "fabrication" in combined

    def test_blocked_contains_flight_ready(self):
        r = _classify(AIRCRAFT_MISSION)
        combined = " ".join(r["blocked_outputs"]).lower()
        assert "flight-ready" in combined

    def test_blocked_contains_airworthiness_claims(self):
        r = _classify(AIRCRAFT_MISSION)
        combined = " ".join(r["blocked_outputs"]).lower()
        assert "airworthiness" in combined

    def test_blocked_contains_safe_flight_claims(self):
        r = _classify(AIRCRAFT_MISSION)
        combined = " ".join(r["blocked_outputs"]).lower()
        assert "safe flight" in combined

    def test_blocked_contains_bypass_human_review(self):
        r = _classify(AIRCRAFT_MISSION)
        combined = " ".join(r["blocked_outputs"]).lower()
        assert "human" in combined

    def test_blocked_contains_bypass_regulatory(self):
        r = _classify(AIRCRAFT_MISSION)
        combined = " ".join(r["blocked_outputs"]).lower()
        assert "regulatory" in combined

    def test_blocked_outputs_empty_when_not_applicable(self):
        r = _classify(ROVER_MISSION)
        assert r["blocked_outputs"] == []


# ---------------------------------------------------------------------------
# Prohibited claims
# ---------------------------------------------------------------------------

class TestProhibitedClaims:

    def test_prohibited_claims_present_when_detected(self):
        r = _classify(AIRCRAFT_MISSION)
        assert len(r["prohibited_claims"]) > 0

    def test_prohibited_claims_include_airworthy(self):
        r = _classify(AIRCRAFT_MISSION)
        combined = " ".join(r["prohibited_claims"]).lower()
        assert "airworthy" in combined

    def test_prohibited_claims_include_safe_to_fly(self):
        r = _classify(AIRCRAFT_MISSION)
        combined = " ".join(r["prohibited_claims"]).lower()
        assert "safe to fly" in combined or "flight" in combined

    def test_prohibited_claims_empty_when_not_applicable(self):
        r = _classify(ROVER_MISSION)
        assert r["prohibited_claims"] == []


# ---------------------------------------------------------------------------
# Required review gates
# ---------------------------------------------------------------------------

class TestRequiredReviewGates:

    def test_required_gates_present_when_detected(self):
        r = _classify(AIRCRAFT_MISSION)
        assert len(r["required_review_gates"]) > 0

    def test_required_gates_mention_human(self):
        r = _classify(AIRCRAFT_MISSION)
        combined = " ".join(r["required_review_gates"]).lower()
        assert "human" in combined

    def test_required_gates_mention_regulatory(self):
        r = _classify(AIRCRAFT_MISSION)
        combined = " ".join(r["required_review_gates"]).lower()
        assert "regulatory" in combined

    def test_required_gates_empty_when_not_applicable(self):
        r = _classify(ROVER_MISSION)
        assert r["required_review_gates"] == []


# ---------------------------------------------------------------------------
# Entry gate — shape
# ---------------------------------------------------------------------------

class TestEntryGateOutputShape:

    def test_gate_field_is_aeroforge_entry_gate(self):
        r = _entry_gate(AIRCRAFT_MISSION)
        assert r["gate"] == "aeroforge_entry_gate"

    def test_status_is_valid(self):
        r = _entry_gate(AIRCRAFT_MISSION, readiness=_readiness("ready"))
        assert r["status"] in ("not_applicable", "blocked", "concept_stage_only")

    def test_aerospace_detected_is_bool(self):
        r = _entry_gate(AIRCRAFT_MISSION)
        assert isinstance(r["aerospace_detected"], bool)

    def test_human_review_required_is_bool(self):
        r = _entry_gate(AIRCRAFT_MISSION, readiness=_readiness("ready"))
        assert isinstance(r["human_review_required"], bool)

    def test_concept_stage_only_is_bool(self):
        r = _entry_gate(AIRCRAFT_MISSION, readiness=_readiness("ready"))
        assert isinstance(r["concept_stage_only"], bool)

    def test_blockers_is_list(self):
        r = _entry_gate(AIRCRAFT_MISSION, readiness=_readiness("ready"))
        assert isinstance(r["blockers"], list)

    def test_allowed_outputs_is_list(self):
        r = _entry_gate(AIRCRAFT_MISSION, readiness=_readiness("ready"))
        assert isinstance(r["allowed_outputs"], list)

    def test_blocked_outputs_is_list(self):
        r = _entry_gate(AIRCRAFT_MISSION, readiness=_readiness("ready"))
        assert isinstance(r["blocked_outputs"], list)

    def test_rationale_is_string(self):
        r = _entry_gate(AIRCRAFT_MISSION, readiness=_readiness("ready"))
        assert isinstance(r["rationale"], str)


# ---------------------------------------------------------------------------
# Entry gate — not_applicable for non-aerospace
# ---------------------------------------------------------------------------

class TestEntryGateNotApplicable:

    def test_rover_returns_not_applicable(self):
        r = _entry_gate(ROVER_MISSION, readiness=_readiness("ready"))
        assert r["status"] == "not_applicable"

    def test_rover_aerospace_detected_false(self):
        r = _entry_gate(ROVER_MISSION, readiness=_readiness("ready"))
        assert r["aerospace_detected"] is False

    def test_rover_human_review_false(self):
        r = _entry_gate(ROVER_MISSION, readiness=_readiness("ready"))
        assert r["human_review_required"] is False

    def test_rover_empty_allowed_outputs(self):
        r = _entry_gate(ROVER_MISSION, readiness=_readiness("ready"))
        assert r["allowed_outputs"] == []

    def test_empty_text_not_applicable(self):
        r = _entry_gate("", readiness=_readiness("ready"))
        assert r["status"] == "not_applicable"


# ---------------------------------------------------------------------------
# Entry gate — readiness blocked prevents AeroForge entry
# ---------------------------------------------------------------------------

class TestEntryGateBlockedByReadiness:

    def test_readiness_blocked_makes_gate_blocked(self):
        r = _entry_gate(AIRCRAFT_MISSION, readiness=_readiness("blocked"))
        assert r["status"] == "blocked"

    def test_readiness_blocked_aerospace_detected_true(self):
        r = _entry_gate(AIRCRAFT_MISSION, readiness=_readiness("blocked"))
        assert r["aerospace_detected"] is True

    def test_readiness_blocked_has_blockers(self):
        r = _entry_gate(AIRCRAFT_MISSION, readiness=_readiness("blocked"))
        assert len(r["blockers"]) >= 1

    def test_readiness_blocked_blocker_mentions_readiness(self):
        r = _entry_gate(AIRCRAFT_MISSION, readiness=_readiness("blocked"))
        combined = " ".join(r["blockers"]).lower()
        assert "readiness" in combined or "mission_intelligence" in combined

    def test_readiness_blocked_allowed_outputs_empty(self):
        r = _entry_gate(AIRCRAFT_MISSION, readiness=_readiness("blocked"))
        assert r["allowed_outputs"] == []

    def test_readiness_blocked_blocked_outputs_populated(self):
        r = _entry_gate(AIRCRAFT_MISSION, readiness=_readiness("blocked"))
        assert len(r["blocked_outputs"]) > 0

    def test_readiness_blocked_human_review_still_required(self):
        r = _entry_gate(AIRCRAFT_MISSION, readiness=_readiness("blocked"))
        assert r["human_review_required"] is True

    def test_readiness_blocked_rationale_mentions_blocked(self):
        r = _entry_gate(AIRCRAFT_MISSION, readiness=_readiness("blocked"))
        assert "blocked" in r["rationale"].lower()


# ---------------------------------------------------------------------------
# Entry gate — readiness ready/warn allows concept stage
# ---------------------------------------------------------------------------

class TestEntryGateAllowed:

    def test_readiness_ready_allows_concept_stage(self):
        r = _entry_gate(AIRCRAFT_MISSION, readiness=_readiness("ready"))
        assert r["status"] == "concept_stage_only"

    def test_readiness_warn_allows_concept_stage(self):
        r = _entry_gate(AIRCRAFT_MISSION, readiness=_readiness("warn"))
        assert r["status"] == "concept_stage_only"

    def test_concept_stage_only_true_when_allowed(self):
        r = _entry_gate(AIRCRAFT_MISSION, readiness=_readiness("ready"))
        assert r["concept_stage_only"] is True

    def test_allowed_when_ready_has_allowed_outputs(self):
        r = _entry_gate(AIRCRAFT_MISSION, readiness=_readiness("ready"))
        assert len(r["allowed_outputs"]) > 0

    def test_allowed_when_ready_has_blocked_outputs(self):
        r = _entry_gate(AIRCRAFT_MISSION, readiness=_readiness("ready"))
        assert len(r["blocked_outputs"]) > 0

    def test_allowed_when_ready_has_no_blockers(self):
        r = _entry_gate(AIRCRAFT_MISSION, readiness=_readiness("ready"))
        assert r["blockers"] == []

    def test_no_readiness_passed_still_works(self):
        r = _entry_gate(AIRCRAFT_MISSION, readiness=None)
        assert r["status"] in ("concept_stage_only", "blocked", "not_applicable")

    def test_unknown_readiness_status_does_not_block(self):
        r = _entry_gate(AIRCRAFT_MISSION, readiness={"status": "unknown"})
        assert r["status"] == "concept_stage_only"


# ---------------------------------------------------------------------------
# Human review required for aerospace
# ---------------------------------------------------------------------------

class TestHumanReviewRequired:

    def test_human_review_required_for_aircraft(self):
        r = _entry_gate(AIRCRAFT_MISSION, readiness=_readiness("ready"))
        assert r["human_review_required"] is True

    def test_human_review_required_for_drone(self):
        r = _entry_gate(DRONE_UAV_MISSION, readiness=_readiness("ready"))
        assert r["human_review_required"] is True

    def test_human_review_required_for_propulsion(self):
        r = _entry_gate(PROPULSION_MISSION, readiness=_readiness("warn"))
        assert r["human_review_required"] is True

    def test_human_review_required_even_when_blocked(self):
        r = _entry_gate(AIRCRAFT_MISSION, readiness=_readiness("blocked"))
        assert r["human_review_required"] is True

    def test_classify_required_gates_mention_human(self):
        r = _classify(DRONE_UAV_MISSION)
        combined = " ".join(r["required_review_gates"]).lower()
        assert "human" in combined


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------

class TestDeterminism:

    def test_classify_rover_deterministic(self):
        r1 = _classify(ROVER_MISSION)
        r2 = _classify(ROVER_MISSION)
        assert r1 == r2

    def test_classify_aircraft_deterministic(self):
        r1 = _classify(AIRCRAFT_MISSION)
        r2 = _classify(AIRCRAFT_MISSION)
        assert r1 == r2

    def test_classify_propulsion_deterministic(self):
        r1 = _classify(PROPULSION_MISSION)
        r2 = _classify(PROPULSION_MISSION)
        assert r1 == r2

    def test_entry_gate_deterministic(self):
        r1 = _entry_gate(AIRCRAFT_MISSION, readiness=_readiness("ready"))
        r2 = _entry_gate(AIRCRAFT_MISSION, readiness=_readiness("ready"))
        assert r1 == r2

    def test_entry_gate_blocked_deterministic(self):
        r1 = _entry_gate(AIRCRAFT_MISSION, readiness=_readiness("blocked"))
        r2 = _entry_gate(AIRCRAFT_MISSION, readiness=_readiness("blocked"))
        assert r1 == r2


# ---------------------------------------------------------------------------
# Rationale wording
# ---------------------------------------------------------------------------

class TestRationaleWording:

    def test_classify_rationale_mentions_concept_stage(self):
        r = _classify(AIRCRAFT_MISSION)
        assert "concept" in r["rationale"].lower()

    def test_classify_rationale_does_not_say_airworthy(self):
        r = _classify(AIRCRAFT_MISSION)
        assert "is airworthy" not in r["rationale"].lower()

    def test_classify_rationale_does_not_say_safe_to_fly(self):
        r = _classify(AIRCRAFT_MISSION)
        assert "safe to fly" not in r["rationale"].lower()

    def test_entry_gate_rationale_mentions_human_review(self):
        r = _entry_gate(AIRCRAFT_MISSION, readiness=_readiness("ready"))
        assert "human" in r["rationale"].lower()

    def test_entry_gate_rationale_mentions_regulatory(self):
        r = _entry_gate(AIRCRAFT_MISSION, readiness=_readiness("ready"))
        assert "regulatory" in r["rationale"].lower()

    def test_entry_gate_rationale_does_not_say_safe_to_fly(self):
        r = _entry_gate(AIRCRAFT_MISSION, readiness=_readiness("ready"))
        assert "safe to fly" not in r["rationale"].lower()

    def test_entry_gate_rationale_does_not_say_airworthy(self):
        r = _entry_gate(AIRCRAFT_MISSION, readiness=_readiness("ready"))
        assert "is airworthy" not in r["rationale"].lower()


# ---------------------------------------------------------------------------
# Supervisor wiring
# ---------------------------------------------------------------------------

class TestSupervisorWiring:

    def _enrich(self, mission_text, tmp_path, monkeypatch):
        import memory.memory_manager as mm
        monkeypatch.setattr(mm, "MEMORY_DIR", tmp_path / "memory")
        monkeypatch.setattr(mm, "MEMORY_FILE", tmp_path / "memory" / "omni_memory.json")

        from backend.app.omni_core.mission_state import MissionState
        from agents.supervisor import SupervisorAgent

        supervisor = SupervisorAgent()
        state = MissionState(mission_text=mission_text)
        return supervisor.enrich_artifacts_from_state(
            state=state,
            artifacts={},
            design_report="",
            revision_payload={},
            export_manifest={},
        )

    def test_rover_does_not_get_aeroforge_intent(self, tmp_path, monkeypatch):
        artifacts = self._enrich(ROVER_MISSION, tmp_path, monkeypatch)
        assert "aeroforge_intent" not in artifacts

    def test_rover_does_not_get_aeroforge_entry_gate(self, tmp_path, monkeypatch):
        artifacts = self._enrich(ROVER_MISSION, tmp_path, monkeypatch)
        assert "aeroforge_entry_gate" not in artifacts

    def test_drone_gets_aeroforge_intent(self, tmp_path, monkeypatch):
        artifacts = self._enrich(DRONE_UAV_MISSION, tmp_path, monkeypatch)
        assert "aeroforge_intent" in artifacts

    def test_drone_gets_aeroforge_entry_gate(self, tmp_path, monkeypatch):
        artifacts = self._enrich(DRONE_UAV_MISSION, tmp_path, monkeypatch)
        assert "aeroforge_entry_gate" in artifacts

    def test_drone_aeroforge_intent_has_correct_module(self, tmp_path, monkeypatch):
        artifacts = self._enrich(DRONE_UAV_MISSION, tmp_path, monkeypatch)
        assert artifacts["aeroforge_intent"]["module"] == "aeroforge"

    def test_drone_aeroforge_intent_aerospace_detected_true(self, tmp_path, monkeypatch):
        artifacts = self._enrich(DRONE_UAV_MISSION, tmp_path, monkeypatch)
        assert artifacts["aeroforge_intent"]["aerospace_detected"] is True

    def test_drone_entry_gate_has_correct_gate_name(self, tmp_path, monkeypatch):
        artifacts = self._enrich(DRONE_UAV_MISSION, tmp_path, monkeypatch)
        assert artifacts["aeroforge_entry_gate"]["gate"] == "aeroforge_entry_gate"

    def test_drone_entry_gate_status_valid(self, tmp_path, monkeypatch):
        artifacts = self._enrich(DRONE_UAV_MISSION, tmp_path, monkeypatch)
        assert artifacts["aeroforge_entry_gate"]["status"] in (
            "not_applicable", "blocked", "concept_stage_only"
        )

    def test_existing_artifacts_preserved_for_drone(self, tmp_path, monkeypatch):
        artifacts = self._enrich(DRONE_UAV_MISSION, tmp_path, monkeypatch)
        assert "mission_intent" in artifacts
        assert "pluto_safety_gate" in artifacts
        assert "mission_intelligence_readiness" in artifacts

    def test_aircraft_mission_gets_aeroforge(self, tmp_path, monkeypatch):
        artifacts = self._enrich(AIRCRAFT_MISSION, tmp_path, monkeypatch)
        assert "aeroforge_intent" in artifacts
        assert artifacts["aeroforge_intent"]["aerospace_detected"] is True
