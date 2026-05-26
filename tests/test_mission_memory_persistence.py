"""
Phase 14C — Mission memory seed persistence tests.

No LLM calls. No network calls.
"""
from __future__ import annotations

import json
import pytest
from pathlib import Path

import memory.memory_manager as mm
from memory.memory_manager import (
    add_mission_memory_seed,
    get_recent_memory_seeds,
    add_mission_to_memory,
    get_recent_memory,
    load_memory,
    clear_memory,
)


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def isolated_memory(tmp_path, monkeypatch):
    """Redirect all memory I/O to a temp directory for every test."""
    mem_dir = tmp_path / "memory"
    mem_file = mem_dir / "omni_memory.json"
    monkeypatch.setattr(mm, "MEMORY_DIR", mem_dir)
    monkeypatch.setattr(mm, "MEMORY_FILE", mem_file)
    return mem_dir


def _rover_seed() -> dict:
    return {
        "status": "generated",
        "mission_type": "inspection",
        "platform_intent": "ground-rover",
        "recommended_candidate_id": "vega_candidate_1",
        "ranking": ["vega_candidate_1", "vega_candidate_2"],
        "risk_level": "high",
        "safety_status": "warn",
        "required_human_review": True,
        "unresolved_questions": ["What is the traverse speed?"],
        "recurring_risk_themes": ["Mission safety mode is 'elevated'"],
        "next_design_lessons": ["Define power budget and regulator plan."],
        "memory_summary": (
            "Mission type 'inspection' targeting platform 'ground-rover'. "
            "Recommended design candidate: vega_candidate_1. "
            "Pluto safety gate: warn, risk level high. Human review required. "
            "1 unresolved question(s) remain."
        ),
    }


def _drone_seed() -> dict:
    return {
        "status": "generated",
        "mission_type": "aerial_survey",
        "platform_intent": "drone-uav",
        "recommended_candidate_id": "vega_candidate_2",
        "ranking": ["vega_candidate_2"],
        "risk_level": "high",
        "safety_status": "blocked",
        "required_human_review": True,
        "unresolved_questions": [],
        "recurring_risk_themes": ["High-risk UAV platform"],
        "next_design_lessons": ["Obtain flight permits before testing."],
        "memory_summary": (
            "Mission type 'aerial_survey' targeting platform 'drone-uav'. "
            "Recommended design candidate: vega_candidate_2. "
            "Pluto safety gate: blocked, risk level high. Human review required."
        ),
    }


# ---------------------------------------------------------------------------
# Core write behaviour
# ---------------------------------------------------------------------------

class TestAddMissionMemorySeed:

    def test_returns_true_on_success(self):
        assert add_mission_memory_seed(_rover_seed(), mission="Build a rover.") is True

    def test_record_appears_in_memory_file(self, tmp_path):
        add_mission_memory_seed(_rover_seed(), mission="Build a rover.")
        data = load_memory()
        seeds = data.get("memory_seeds", [])
        assert len(seeds) == 1

    def test_record_has_type_field(self):
        add_mission_memory_seed(_rover_seed(), mission="Build a rover.")
        seed = load_memory()["memory_seeds"][0]
        assert seed["type"] == "mission_memory_seed"

    def test_record_has_timestamp(self):
        add_mission_memory_seed(_rover_seed(), mission="Build a rover.")
        seed = load_memory()["memory_seeds"][0]
        assert isinstance(seed["timestamp"], str)
        assert len(seed["timestamp"]) > 0

    def test_record_has_mission(self):
        add_mission_memory_seed(_rover_seed(), mission="Build a rover.")
        seed = load_memory()["memory_seeds"][0]
        assert "Build a rover." in seed["mission"]

    def test_compact_fields_written(self):
        add_mission_memory_seed(_rover_seed(), mission="Build a rover.")
        seed = load_memory()["memory_seeds"][0]
        assert seed["mission_type"] == "inspection"
        assert seed["platform_intent"] == "ground-rover"
        assert seed["recommended_candidate_id"] == "vega_candidate_1"
        assert seed["risk_level"] == "high"
        assert seed["safety_status"] == "warn"
        assert seed["required_human_review"] is True

    def test_list_fields_preserved(self):
        add_mission_memory_seed(_rover_seed(), mission="Build a rover.")
        seed = load_memory()["memory_seeds"][0]
        assert isinstance(seed["unresolved_questions"], list)
        assert isinstance(seed["recurring_risk_themes"], list)
        assert isinstance(seed["next_design_lessons"], list)

    def test_memory_summary_written(self):
        add_mission_memory_seed(_rover_seed(), mission="Build a rover.")
        seed = load_memory()["memory_seeds"][0]
        assert "ground-rover" in seed["memory_summary"]

    def test_no_raw_report_fields_written(self):
        add_mission_memory_seed(_rover_seed(), mission="Build a rover.")
        seed = load_memory()["memory_seeds"][0]
        forbidden = {"raw_report", "design_understanding", "mission_graph", "artifacts", "ranking"}
        assert not forbidden.intersection(set(seed.keys()))


# ---------------------------------------------------------------------------
# File and directory creation
# ---------------------------------------------------------------------------

class TestDirectoryAndFileCreation:

    def test_memory_dir_created_if_missing(self, tmp_path):
        mem_dir = tmp_path / "memory"
        assert not mem_dir.exists()
        add_mission_memory_seed(_rover_seed(), mission="Build a rover.")
        assert mem_dir.exists()

    def test_memory_file_created_if_missing(self, tmp_path):
        mem_file = tmp_path / "memory" / "omni_memory.json"
        assert not mem_file.exists()
        add_mission_memory_seed(_rover_seed(), mission="Build a rover.")
        assert mem_file.exists()

    def test_memory_file_is_valid_json(self, tmp_path):
        add_mission_memory_seed(_rover_seed(), mission="Build a rover.")
        mem_file = tmp_path / "memory" / "omni_memory.json"
        content = json.loads(mem_file.read_text())
        assert isinstance(content, dict)


# ---------------------------------------------------------------------------
# Deduplication
# ---------------------------------------------------------------------------

class TestDeduplication:

    def test_duplicate_seed_not_appended(self):
        seed = _rover_seed()
        add_mission_memory_seed(seed, mission="Build a rover.")
        add_mission_memory_seed(seed, mission="Build a rover.")
        seeds = load_memory()["memory_seeds"]
        assert len(seeds) == 1

    def test_second_add_returns_false_for_duplicate(self):
        seed = _rover_seed()
        add_mission_memory_seed(seed, mission="Build a rover.")
        result = add_mission_memory_seed(seed, mission="Build a rover.")
        assert result is False

    def test_different_mission_text_not_deduped(self):
        seed = _rover_seed()
        add_mission_memory_seed(seed, mission="Build rover A.")
        add_mission_memory_seed(seed, mission="Build rover B.")
        seeds = load_memory()["memory_seeds"]
        assert len(seeds) == 2

    def test_different_summary_not_deduped(self):
        s1 = {**_rover_seed(), "memory_summary": "Summary A."}
        s2 = {**_rover_seed(), "memory_summary": "Summary B."}
        add_mission_memory_seed(s1, mission="Build a rover.")
        add_mission_memory_seed(s2, mission="Build a rover.")
        seeds = load_memory()["memory_seeds"]
        assert len(seeds) == 2


# ---------------------------------------------------------------------------
# Cap enforcement
# ---------------------------------------------------------------------------

class TestCapEnforcement:

    def test_seeds_capped_at_100(self):
        for i in range(110):
            seed = {**_rover_seed(), "memory_summary": f"Summary {i}."}
            add_mission_memory_seed(seed, mission=f"Mission {i}.")
        seeds = load_memory()["memory_seeds"]
        assert len(seeds) == 100

    def test_oldest_seeds_evicted_when_capped(self):
        for i in range(110):
            seed = {**_rover_seed(), "memory_summary": f"Summary {i}."}
            add_mission_memory_seed(seed, mission=f"Mission {i}.")
        seeds = load_memory()["memory_seeds"]
        summaries = [s["memory_summary"] for s in seeds]
        assert "Summary 0." not in summaries
        assert "Summary 109." in summaries

    def test_most_recent_100_are_kept(self):
        for i in range(105):
            seed = {**_rover_seed(), "memory_summary": f"Summary {i}."}
            add_mission_memory_seed(seed, mission=f"Mission {i}.")
        seeds = load_memory()["memory_seeds"]
        summaries = [s["memory_summary"] for s in seeds]
        for i in range(5, 105):
            assert f"Summary {i}." in summaries


# ---------------------------------------------------------------------------
# get_recent_memory_seeds
# ---------------------------------------------------------------------------

class TestGetRecentMemorySeeds:

    def test_returns_list(self):
        result = get_recent_memory_seeds()
        assert isinstance(result, list)

    def test_returns_empty_when_no_seeds(self):
        assert get_recent_memory_seeds() == []

    def test_returns_written_seeds(self):
        add_mission_memory_seed(_rover_seed(), mission="Build a rover.")
        result = get_recent_memory_seeds(n=5)
        assert len(result) == 1
        assert result[0]["platform_intent"] == "ground-rover"

    def test_respects_n_limit(self):
        for i in range(10):
            seed = {**_rover_seed(), "memory_summary": f"Summary {i}."}
            add_mission_memory_seed(seed, mission=f"Mission {i}.")
        result = get_recent_memory_seeds(n=3)
        assert len(result) == 3

    def test_returns_newest_last(self):
        for i in range(5):
            seed = {**_rover_seed(), "memory_summary": f"Summary {i}."}
            add_mission_memory_seed(seed, mission=f"Mission {i}.")
        result = get_recent_memory_seeds(n=5)
        assert result[-1]["memory_summary"] == "Summary 4."
        assert result[0]["memory_summary"] == "Summary 0."

    def test_n_larger_than_stored_returns_all(self):
        add_mission_memory_seed(_rover_seed(), mission="Build a rover.")
        result = get_recent_memory_seeds(n=50)
        assert len(result) == 1


# ---------------------------------------------------------------------------
# Failure safety
# ---------------------------------------------------------------------------

class TestFailureSafety:

    def test_empty_seed_status_returns_false(self):
        assert add_mission_memory_seed({"status": "empty"}) is False

    def test_non_dict_seed_returns_false(self):
        for bad in (None, "string", 42, [], True):
            assert add_mission_memory_seed(bad) is False

    def test_non_dict_seed_does_not_crash(self):
        for bad in (None, "string", 42, [], True):
            result = add_mission_memory_seed(bad)
            assert result in (True, False)

    def test_no_mission_arg_does_not_crash(self):
        result = add_mission_memory_seed(_rover_seed())
        assert result is True

    def test_get_recent_seeds_does_not_crash_on_bad_file(self, tmp_path):
        mem_file = tmp_path / "memory" / "omni_memory.json"
        mem_file.parent.mkdir(parents=True, exist_ok=True)
        mem_file.write_text("not json at all {{{{")
        result = get_recent_memory_seeds()
        assert isinstance(result, list)

    def test_write_failure_returns_false(self, monkeypatch):
        def _bad_save(data):
            raise OSError("disk full")
        monkeypatch.setattr(mm, "save_memory", _bad_save)
        result = add_mission_memory_seed(_rover_seed(), mission="Build a rover.")
        assert result is False


# ---------------------------------------------------------------------------
# Existing memory functions unaffected
# ---------------------------------------------------------------------------

class TestExistingFunctionsUnaffected:

    def test_add_mission_to_memory_still_works(self):
        add_mission_to_memory("Old mission text.", "Old summary.")
        memory = load_memory()
        assert len(memory["missions"]) == 1
        assert "Old mission text." in memory["missions"][0]["mission"]

    def test_get_recent_memory_still_works(self):
        add_mission_to_memory("Old mission.", "Old summary.")
        result = get_recent_memory(n=5)
        assert isinstance(result, str)
        assert "Old mission." in result

    def test_seeds_and_missions_coexist(self):
        add_mission_to_memory("Old mission.", "Old summary.")
        add_mission_memory_seed(_rover_seed(), mission="New rover mission.")
        memory = load_memory()
        assert len(memory["missions"]) == 1
        assert len(memory["memory_seeds"]) == 1

    def test_seeds_dont_overwrite_missions(self):
        add_mission_to_memory("Mission A.", "Summary A.")
        add_mission_to_memory("Mission B.", "Summary B.")
        add_mission_memory_seed(_rover_seed(), mission="Seed mission.")
        memory = load_memory()
        assert len(memory["missions"]) == 2

    def test_missions_dont_overwrite_seeds(self):
        add_mission_memory_seed(_rover_seed(), mission="Seed mission.")
        add_mission_to_memory("Classic mission.", "Classic summary.")
        memory = load_memory()
        assert len(memory["memory_seeds"]) == 1


# ---------------------------------------------------------------------------
# Supervisor persistence flag
# ---------------------------------------------------------------------------

class TestSupervisorPersistenceFlag:

    def test_supervisor_wires_persistence_flag(self):
        """Verify enrich_artifacts_from_state sets mission_memory_persistence."""
        from backend.app.omni_core.mission_state import MissionState

        # Import SupervisorAgent without triggering LLM calls.
        from agents.supervisor import SupervisorAgent

        supervisor = SupervisorAgent()
        state = MissionState(mission_text="Build a tracked rover for inspection.")

        # Build minimal artifacts (no LLM — deterministic path only).
        artifacts = supervisor.enrich_artifacts_from_state(
            state=state,
            artifacts={},
            design_report="",
            revision_payload={},
            export_manifest={},
        )

        assert "mission_memory_persistence" in artifacts
        assert artifacts["mission_memory_persistence"]["status"] in (
            "saved", "skipped", "failed"
        )

    def test_persistence_status_saved_for_generated_seed(self):
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

        seed = artifacts.get("mission_memory_seed", {})
        persistence = artifacts.get("mission_memory_persistence", {})

        if seed.get("status") == "generated":
            assert persistence["status"] == "saved"

    def test_persistence_flag_is_not_full_seed(self):
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

        flag = artifacts["mission_memory_persistence"]
        # Flag should be tiny — just a status, no heavy payload.
        assert "status" in flag
        assert "memory_summary" not in flag
        assert "recurring_risk_themes" not in flag
