"""
Phase 14E — Mission intelligence readiness gate tests.

No LLM calls. No network calls.
"""
from __future__ import annotations

from typing import Any, Dict

import pytest


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

def _make_full_artifacts() -> Dict[str, Any]:
    """Complete, valid mission intelligence artifact stack."""
    return {
        "mission_intent": {
            "raw_mission": "Build a tracked rover for inspection of steel surfaces.",
            "mission_type": "inspection",
            "platform_intent": "ground-rover",
            "detected_domains": ["robotics"],
            "sensing_requirements": ["camera", "IMU"],
            "constraints": ["battery / power source"],
            "safety_mode": "elevated",
            "open_questions": [],
            "required_outputs": ["ROS2 package", "CAD model", "validation checklist"],
            "mobility_requirements": ["tracked locomotion"],
        },
        "design_candidates": [
            {"id": "vega_candidate_1", "name": "Tracked Crawler"},
            {"id": "vega_candidate_2", "name": "Wheeled Rover"},
        ],
        "candidate_evaluation": {
            "candidates_evaluated": 2,
            "recommended_candidate_id": "vega_candidate_1",
            "ranking": ["vega_candidate_1", "vega_candidate_2"],
            "evaluations": [],
            "council_summary": "2 candidate(s) evaluated.",
            "open_questions": [],
        },
        "pluto_safety_gate": {
            "gate": "pluto_safety_gate",
            "status": "warn",
            "risk_level": "medium",
            "blockers": [],
            "warnings": ["Mission safety mode is 'elevated'."],
            "required_human_review": True,
            "required_next_checks": ["Confirm safety mode justification."],
            "rationale": (
                "Gate WARN — risk level 'medium'. 1 warning(s). "
                "Resolved platform: ground-rover. This gate is advisory."
            ),
        },
        "mission_memory_seed": {
            "status": "generated",
            "mission_type": "inspection",
            "platform_intent": "ground-rover",
            "recommended_candidate_id": "vega_candidate_1",
            "memory_summary": "Mission type 'inspection' targeting platform 'ground-rover'.",
        },
        "mission_memory_persistence": {
            "status": "saved",
        },
    }


def _call(artifacts=None, export_result=None, mission_text=""):
    from backend.app.omni_core.intelligence_readiness import evaluate_mission_intelligence_readiness
    return evaluate_mission_intelligence_readiness(
        artifacts=artifacts,
        export_result=export_result,
        mission_text=mission_text,
    )


# ---------------------------------------------------------------------------
# Gate output shape
# ---------------------------------------------------------------------------

class TestGateOutputShape:

    def test_gate_field_is_correct(self):
        result = _call(artifacts=_make_full_artifacts())
        assert result["gate"] == "mission_intelligence_readiness"

    def test_status_is_valid_value(self):
        result = _call(artifacts=_make_full_artifacts())
        assert result["status"] in ("ready", "warn", "blocked")

    def test_readiness_score_is_float_in_range(self):
        result = _call(artifacts=_make_full_artifacts())
        assert isinstance(result["readiness_score"], float)
        assert 0.0 <= result["readiness_score"] <= 1.0

    def test_present_artifacts_is_list(self):
        result = _call(artifacts=_make_full_artifacts())
        assert isinstance(result["present_artifacts"], list)

    def test_missing_artifacts_is_list(self):
        result = _call(artifacts=_make_full_artifacts())
        assert isinstance(result["missing_artifacts"], list)

    def test_warnings_is_list(self):
        result = _call(artifacts=_make_full_artifacts())
        assert isinstance(result["warnings"], list)

    def test_blockers_is_list(self):
        result = _call(artifacts=_make_full_artifacts())
        assert isinstance(result["blockers"], list)

    def test_next_actions_is_list(self):
        result = _call(artifacts=_make_full_artifacts())
        assert isinstance(result["next_actions"], list)

    def test_rationale_is_non_empty_string(self):
        result = _call(artifacts=_make_full_artifacts())
        assert isinstance(result["rationale"], str)
        assert len(result["rationale"]) > 0

    def test_empty_artifacts_returns_dict(self):
        result = _call(artifacts={})
        assert isinstance(result, dict)
        assert "gate" in result

    def test_none_artifacts_returns_dict(self):
        result = _call(artifacts=None)
        assert isinstance(result, dict)
        assert "gate" in result


# ---------------------------------------------------------------------------
# Complete stack
# ---------------------------------------------------------------------------

class TestCompleteStack:

    def test_complete_stack_returns_ready_or_warn(self):
        result = _call(artifacts=_make_full_artifacts())
        assert result["status"] in ("ready", "warn")

    def test_complete_stack_has_high_readiness_score(self):
        result = _call(artifacts=_make_full_artifacts())
        assert result["readiness_score"] >= 0.7

    def test_complete_stack_score_is_1_0(self):
        result = _call(artifacts=_make_full_artifacts())
        assert result["readiness_score"] == 1.0

    def test_complete_stack_has_no_blockers(self):
        result = _call(artifacts=_make_full_artifacts())
        assert result["blockers"] == []

    def test_complete_stack_mission_intent_in_present(self):
        result = _call(artifacts=_make_full_artifacts())
        assert "mission_intent" in result["present_artifacts"]

    def test_complete_stack_platform_intent_in_present(self):
        result = _call(artifacts=_make_full_artifacts())
        assert "mission_intent.platform_intent" in result["present_artifacts"]

    def test_complete_stack_pluto_gate_in_present(self):
        result = _call(artifacts=_make_full_artifacts())
        assert "pluto_safety_gate" in result["present_artifacts"]

    def test_complete_stack_memory_seed_in_present(self):
        result = _call(artifacts=_make_full_artifacts())
        assert "mission_memory_seed" in result["present_artifacts"]

    def test_complete_stack_memory_persistence_in_present(self):
        result = _call(artifacts=_make_full_artifacts())
        assert "mission_memory_persistence" in result["present_artifacts"]


# ---------------------------------------------------------------------------
# Missing mission_intent — blocker
# ---------------------------------------------------------------------------

class TestMissingMissionIntent:

    def test_missing_mission_intent_status_is_blocked(self):
        result = _call(artifacts={})
        assert result["status"] == "blocked"

    def test_missing_mission_intent_has_blocker(self):
        result = _call(artifacts={})
        assert len(result["blockers"]) >= 1

    def test_missing_mission_intent_blocker_mentions_artifact(self):
        result = _call(artifacts={})
        combined = " ".join(result["blockers"]).lower()
        assert "mission_intent" in combined

    def test_missing_mission_intent_in_missing_artifacts(self):
        result = _call(artifacts={})
        assert "mission_intent" in result["missing_artifacts"]

    def test_missing_mission_intent_score_is_low(self):
        result = _call(artifacts={})
        assert result["readiness_score"] < 0.5

    def test_missing_mission_intent_has_next_action(self):
        result = _call(artifacts={})
        assert len(result["next_actions"]) >= 1


# ---------------------------------------------------------------------------
# Missing platform_intent — blocker
# ---------------------------------------------------------------------------

class TestMissingPlatformIntent:

    def _artifacts_no_platform(self):
        arts = _make_full_artifacts()
        arts["mission_intent"] = {
            "raw_mission": "Build an inspection robot.",
            "mission_type": "inspection",
            "platform_intent": None,
            "safety_mode": "standard",
            "open_questions": [],
        }
        # Provide a pluto gate so only platform_intent triggers the blocker.
        return arts

    def test_missing_platform_intent_status_is_blocked(self):
        result = _call(artifacts=self._artifacts_no_platform())
        assert result["status"] == "blocked"

    def test_missing_platform_intent_has_blocker(self):
        result = _call(artifacts=self._artifacts_no_platform())
        assert len(result["blockers"]) >= 1

    def test_missing_platform_intent_blocker_mentions_platform(self):
        result = _call(artifacts=self._artifacts_no_platform())
        combined = " ".join(result["blockers"]).lower()
        assert "platform" in combined

    def test_missing_platform_intent_in_missing_artifacts(self):
        result = _call(artifacts=self._artifacts_no_platform())
        assert "mission_intent.platform_intent" in result["missing_artifacts"]

    def test_mission_intent_still_present(self):
        result = _call(artifacts=self._artifacts_no_platform())
        assert "mission_intent" in result["present_artifacts"]


# ---------------------------------------------------------------------------
# Missing candidate_evaluation — warning
# ---------------------------------------------------------------------------

class TestMissingCandidateEvaluation:

    def _artifacts_no_ce(self):
        arts = _make_full_artifacts()
        arts.pop("candidate_evaluation", None)
        arts.pop("design_candidates", None)
        return arts

    def test_missing_ce_status_is_warn(self):
        result = _call(artifacts=self._artifacts_no_ce())
        assert result["status"] in ("warn", "blocked")

    def test_missing_ce_has_warning(self):
        result = _call(artifacts=self._artifacts_no_ce())
        combined = " ".join(result["warnings"]).lower()
        assert "candidate" in combined

    def test_missing_ce_in_missing_artifacts(self):
        result = _call(artifacts=self._artifacts_no_ce())
        assert "candidate_evaluation" in result["missing_artifacts"]

    def test_missing_ce_no_blocker_for_nonphysical_mission(self):
        arts = _make_full_artifacts()
        arts.pop("candidate_evaluation", None)
        arts.pop("design_candidates", None)
        # Make it non-physical and non-blocker-triggering
        arts["mission_intent"]["platform_intent"] = "ground-rover"
        result = _call(artifacts=arts, mission_text="")
        # candidate_evaluation is a warning, not blocker
        ce_in_blockers = any("candidate" in b.lower() for b in result["blockers"])
        assert not ce_in_blockers


# ---------------------------------------------------------------------------
# Missing Pluto gate — blocker for physical missions
# ---------------------------------------------------------------------------

class TestMissingPlutoGate:

    def _physical_arts_no_gate(self):
        arts = _make_full_artifacts()
        arts.pop("pluto_safety_gate", None)
        return arts

    def test_missing_pluto_blocks_physical_mission(self):
        result = _call(
            artifacts=self._physical_arts_no_gate(),
            mission_text="Build a tracked rover.",
        )
        assert result["status"] == "blocked"

    def test_missing_pluto_has_blocker_for_physical(self):
        result = _call(
            artifacts=self._physical_arts_no_gate(),
            mission_text="Build a tracked rover.",
        )
        combined = " ".join(result["blockers"]).lower()
        assert "pluto" in combined or "safety gate" in combined

    def test_pluto_gate_in_missing_artifacts(self):
        result = _call(
            artifacts=self._physical_arts_no_gate(),
            mission_text="Build a tracked rover.",
        )
        assert "pluto_safety_gate" in result["missing_artifacts"]

    def test_missing_pluto_non_physical_mission_no_pluto_blocker(self):
        arts = {
            "mission_intent": {
                "raw_mission": "Write a software report.",
                "mission_type": "general engineering",
                "platform_intent": None,
                "safety_mode": "standard",
                "open_questions": [],
            },
            "candidate_evaluation": {
                "candidates_evaluated": 1,
                "recommended_candidate_id": "vega_candidate_1",
            },
            "mission_memory_seed": {"status": "generated"},
            "mission_memory_persistence": {"status": "saved"},
        }
        result = _call(artifacts=arts, mission_text="Write a software report.")
        # pluto missing is NOT a blocker for non-physical mission
        pluto_blockers = [b for b in result["blockers"] if "pluto" in b.lower() or "safety gate" in b.lower()]
        assert pluto_blockers == []


# ---------------------------------------------------------------------------
# Pluto blocked status — blocks readiness
# ---------------------------------------------------------------------------

class TestPlutoBlockedStatus:

    def _artifacts_pluto_blocked(self):
        arts = _make_full_artifacts()
        arts["pluto_safety_gate"] = {
            "gate": "pluto_safety_gate",
            "status": "blocked",
            "risk_level": "high",
            "blockers": ["Platform type is unknown but mission appears to involve physical hardware."],
            "warnings": [],
            "required_human_review": True,
            "required_next_checks": ["Identify platform before safety analysis."],
            "rationale": "Gate BLOCKED (1 blocker(s)). This gate is advisory.",
        }
        return arts

    def test_pluto_blocked_makes_readiness_blocked(self):
        result = _call(artifacts=self._artifacts_pluto_blocked())
        assert result["status"] == "blocked"

    def test_pluto_blocked_appears_in_blockers(self):
        result = _call(artifacts=self._artifacts_pluto_blocked())
        combined = " ".join(result["blockers"]).lower()
        assert "blocked" in combined

    def test_pluto_gate_still_present_in_present_artifacts(self):
        result = _call(artifacts=self._artifacts_pluto_blocked())
        assert "pluto_safety_gate" in result["present_artifacts"]

    def test_pluto_blocked_has_next_action(self):
        result = _call(artifacts=self._artifacts_pluto_blocked())
        combined = " ".join(result["next_actions"]).lower()
        assert "pluto" in combined or "blocker" in combined or "gate" in combined


# ---------------------------------------------------------------------------
# Missing memory seed — warning
# ---------------------------------------------------------------------------

class TestMissingMemorySeed:

    def _artifacts_no_seed(self):
        arts = _make_full_artifacts()
        arts.pop("mission_memory_seed", None)
        arts.pop("mission_memory_persistence", None)
        return arts

    def test_missing_memory_seed_warns(self):
        result = _call(artifacts=self._artifacts_no_seed())
        combined = " ".join(result["warnings"]).lower()
        assert "memory" in combined or "seed" in combined

    def test_missing_memory_seed_not_a_blocker(self):
        result = _call(artifacts=self._artifacts_no_seed())
        seed_blockers = [b for b in result["blockers"] if "memory" in b.lower() or "seed" in b.lower()]
        assert seed_blockers == []

    def test_missing_memory_seed_in_missing_artifacts(self):
        result = _call(artifacts=self._artifacts_no_seed())
        assert "mission_memory_seed" in result["missing_artifacts"]

    def test_missing_memory_seed_status_is_warn_not_blocked(self):
        result = _call(artifacts=self._artifacts_no_seed())
        # Only warnings — should be warn (not blocked) unless other blockers exist
        assert result["status"] in ("warn",)


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------

class TestDeterminism:

    def test_full_stack_output_is_deterministic(self):
        arts = _make_full_artifacts()
        r1 = _call(artifacts=arts, mission_text="Build a rover.")
        r2 = _call(artifacts=arts, mission_text="Build a rover.")
        assert r1 == r2

    def test_empty_artifacts_output_is_deterministic(self):
        r1 = _call(artifacts={}, mission_text="Build something.")
        r2 = _call(artifacts={}, mission_text="Build something.")
        assert r1 == r2

    def test_partial_stack_output_is_deterministic(self):
        arts = {
            "mission_intent": {
                "raw_mission": "Build a robot.",
                "platform_intent": "hexapod",
                "safety_mode": "standard",
                "open_questions": [],
            },
        }
        r1 = _call(artifacts=arts, mission_text="Build a robot.")
        r2 = _call(artifacts=arts, mission_text="Build a robot.")
        assert r1 == r2


# ---------------------------------------------------------------------------
# Rationale wording
# ---------------------------------------------------------------------------

class TestRationaleWording:

    def test_rationale_does_not_say_safe_to_build(self):
        for arts in [_make_full_artifacts(), {}, None]:
            result = _call(artifacts=arts)
            assert "safe to build" not in result["rationale"].lower()

    def test_rationale_mentions_software_phase(self):
        result = _call(artifacts=_make_full_artifacts())
        assert "software phase" in result["rationale"].lower()

    def test_rationale_does_not_claim_engineering_validation(self):
        result = _call(artifacts=_make_full_artifacts())
        # Must say it does NOT do engineering validation, not claim it does.
        assert "not engineering validation" in result["rationale"].lower()

    def test_rationale_mentions_artifact_completeness(self):
        result = _call(artifacts=_make_full_artifacts())
        assert "artifact completeness" in result["rationale"].lower()

    def test_blocked_rationale_mentions_blockers(self):
        result = _call(artifacts={})
        assert "blocked" in result["rationale"].lower()

    def test_warn_rationale_mentions_warnings(self):
        arts = _make_full_artifacts()
        arts.pop("mission_memory_seed", None)
        arts.pop("mission_memory_persistence", None)
        result = _call(artifacts=arts)
        if result["status"] == "warn":
            assert "warning" in result["rationale"].lower()


# ---------------------------------------------------------------------------
# Optional artifacts (graph_review, design_understanding)
# ---------------------------------------------------------------------------

class TestOptionalArtifacts:

    def test_graph_review_in_present_if_in_artifacts(self):
        arts = _make_full_artifacts()
        arts["graph_review"] = {"status": "reviewed", "issue_count": 0}
        result = _call(artifacts=arts)
        assert "graph_review" in result["present_artifacts"]

    def test_design_understanding_in_present_if_in_export(self):
        arts = _make_full_artifacts()
        exp = {"cortex": {"design_understanding": {"status": "evaluated"}}}
        result = _call(artifacts=arts, export_result=exp)
        assert "design_understanding" in result["present_artifacts"]

    def test_graph_review_absence_does_not_cause_blocker(self):
        result = _call(artifacts=_make_full_artifacts())
        graph_blockers = [b for b in result["blockers"] if "graph" in b.lower()]
        assert graph_blockers == []

    def test_graph_review_absence_does_not_cause_warning(self):
        result = _call(artifacts=_make_full_artifacts())
        graph_warnings = [w for w in result["warnings"] if "graph" in w.lower()]
        assert graph_warnings == []


# ---------------------------------------------------------------------------
# Supervisor wiring
# ---------------------------------------------------------------------------

class TestSupervisorWiring:

    def test_supervisor_attaches_mission_intelligence_readiness(self, tmp_path, monkeypatch):
        import memory.memory_manager as mm
        monkeypatch.setattr(mm, "MEMORY_DIR", tmp_path / "memory")
        monkeypatch.setattr(mm, "MEMORY_FILE", tmp_path / "memory" / "omni_memory.json")

        from backend.app.omni_core.mission_state import MissionState
        from agents.supervisor import SupervisorAgent

        supervisor = SupervisorAgent()
        state = MissionState(mission_text="Build a tracked rover for inspection.")

        artifacts = supervisor.enrich_artifacts_from_state(
            state=state,
            artifacts={},
            design_report="",
            revision_payload={},
            export_manifest={},
        )

        assert "mission_intelligence_readiness" in artifacts

    def test_supervisor_mir_has_gate_name(self, tmp_path, monkeypatch):
        import memory.memory_manager as mm
        monkeypatch.setattr(mm, "MEMORY_DIR", tmp_path / "memory")
        monkeypatch.setattr(mm, "MEMORY_FILE", tmp_path / "memory" / "omni_memory.json")

        from backend.app.omni_core.mission_state import MissionState
        from agents.supervisor import SupervisorAgent

        supervisor = SupervisorAgent()
        state = MissionState(mission_text="Build a tracked rover for inspection.")

        artifacts = supervisor.enrich_artifacts_from_state(
            state=state,
            artifacts={},
            design_report="",
            revision_payload={},
            export_manifest={},
        )

        mir = artifacts["mission_intelligence_readiness"]
        assert mir["gate"] == "mission_intelligence_readiness"

    def test_supervisor_mir_has_valid_status(self, tmp_path, monkeypatch):
        import memory.memory_manager as mm
        monkeypatch.setattr(mm, "MEMORY_DIR", tmp_path / "memory")
        monkeypatch.setattr(mm, "MEMORY_FILE", tmp_path / "memory" / "omni_memory.json")

        from backend.app.omni_core.mission_state import MissionState
        from agents.supervisor import SupervisorAgent

        supervisor = SupervisorAgent()
        state = MissionState(mission_text="Build a tracked rover for inspection.")

        artifacts = supervisor.enrich_artifacts_from_state(
            state=state,
            artifacts={},
            design_report="",
            revision_payload={},
            export_manifest={},
        )

        mir = artifacts["mission_intelligence_readiness"]
        assert mir["status"] in ("ready", "warn", "blocked")

    def test_supervisor_mir_has_readiness_score(self, tmp_path, monkeypatch):
        import memory.memory_manager as mm
        monkeypatch.setattr(mm, "MEMORY_DIR", tmp_path / "memory")
        monkeypatch.setattr(mm, "MEMORY_FILE", tmp_path / "memory" / "omni_memory.json")

        from backend.app.omni_core.mission_state import MissionState
        from agents.supervisor import SupervisorAgent

        supervisor = SupervisorAgent()
        state = MissionState(mission_text="Build a tracked rover for inspection.")

        artifacts = supervisor.enrich_artifacts_from_state(
            state=state,
            artifacts={},
            design_report="",
            revision_payload={},
            export_manifest={},
        )

        mir = artifacts["mission_intelligence_readiness"]
        assert "readiness_score" in mir
        assert 0.0 <= mir["readiness_score"] <= 1.0

    def test_supervisor_mir_does_not_block_existing_artifacts(self, tmp_path, monkeypatch):
        """Adding readiness gate must not remove other artifacts."""
        import memory.memory_manager as mm
        monkeypatch.setattr(mm, "MEMORY_DIR", tmp_path / "memory")
        monkeypatch.setattr(mm, "MEMORY_FILE", tmp_path / "memory" / "omni_memory.json")

        from backend.app.omni_core.mission_state import MissionState
        from agents.supervisor import SupervisorAgent

        supervisor = SupervisorAgent()
        state = MissionState(mission_text="Build a tracked rover for inspection.")

        artifacts = supervisor.enrich_artifacts_from_state(
            state=state,
            artifacts={},
            design_report="",
            revision_payload={},
            export_manifest={},
        )

        assert "mission_intent" in artifacts
        assert "pluto_safety_gate" in artifacts
        assert "mission_memory_seed" in artifacts
        assert "mission_memory_persistence" in artifacts
