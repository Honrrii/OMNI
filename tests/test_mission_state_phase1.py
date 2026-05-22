"""
Phase 1 tests: canonical MissionState is used by supervisor, and serialization
round-trips correctly including nested next_artifacts data.
"""
from __future__ import annotations

import json

import agents.supervisor as supervisor_module
from backend.app.omni_core.mission_state import MissionState as CanonicalMissionState


# ---------------------------------------------------------------------------
# Identity: supervisor must use the canonical class, not the inline fallback
# ---------------------------------------------------------------------------

def test_supervisor_uses_canonical_mission_state():
    assert supervisor_module.MissionState is CanonicalMissionState, (
        "supervisor.MissionState is not the canonical class from "
        "backend.app.omni_core.mission_state — inline fallback may still be active."
    )


# ---------------------------------------------------------------------------
# Serialization: to_dict() round-trip
# ---------------------------------------------------------------------------

def _make_state() -> CanonicalMissionState:
    state = CanonicalMissionState(mission_text="Design a palm-sized rover with ROS2.")
    return state


def test_to_dict_contains_required_top_level_keys():
    state = _make_state()
    d = state.to_dict()
    required = {
        "mission_id", "mission_text", "status", "created_at", "updated_at",
        "agent_records", "structured_outputs", "synthesis_input",
        "synthesized_artifacts", "warnings", "errors", "metadata",
    }
    assert required <= d.keys(), f"Missing keys: {required - d.keys()}"


def test_to_dict_is_json_serializable():
    state = _make_state()
    state.start_agent("korva", "Korva")
    state.finish_agent(
        "korva",
        raw_output="raw text",
        parsed_output={"hardware_architecture_summary": "Differential drive PCB."},
    )
    d = state.to_dict()
    # Must not raise
    json.dumps(d)


def test_to_dict_preserves_next_artifacts_in_structured_outputs():
    """
    next_artifacts lives inside an agent's structured output under
    handoff_to_artifact_synthesis, not as a top-level MissionState field.
    Verify it survives finish_agent() → to_dict() intact.
    """
    sky_output = {
        "agent_id": "sky",
        "role": "robotics_software_architecture",
        "ros2_package_plan": {"package_name": "omni_rover", "nodes": []},
        "handoff_to_artifact_synthesis": {
            "ros2_node_graph_notes": ["4-wheel differential drive"],
            "test_checklist_notes": ["colcon build", "ros2 launch smoke test"],
            "next_artifacts": ["ros2_node_graph.json", "test_checklist.md"],
        },
    }

    state = _make_state()
    state.start_agent("sky", "Sky")
    state.finish_agent("sky", raw_output="raw sky", parsed_output=sky_output)

    d = state.to_dict()

    # agent_records stores AgentRecord dataclasses; asdict() converts them to dicts
    sky_record = d["agent_records"]["sky"]
    assert isinstance(sky_record, dict), "agent_records entry should be a dict after to_dict()"

    recovered_parsed = sky_record["parsed_output"]
    handoff = recovered_parsed.get("handoff_to_artifact_synthesis", {})
    assert handoff.get("next_artifacts") == ["ros2_node_graph.json", "test_checklist.md"], (
        f"next_artifacts did not survive to_dict(): {handoff}"
    )

    # Also present in structured_outputs (the shortcut path)
    assert d["structured_outputs"]["sky"]["handoff_to_artifact_synthesis"]["next_artifacts"] == [
        "ros2_node_graph.json",
        "test_checklist.md",
    ]


def test_to_dict_next_artifacts_across_multiple_agents():
    """
    Verify next_artifacts from oli and korva also survive round-trip.
    """
    oli_output = {
        "handoff_to_artifact_synthesis": {
            "next_artifacts": ["fusion360_concept.json", "component_layout.json"],
        },
    }
    korva_output = {
        "handoff_to_artifact_synthesis": {
            "next_artifacts": ["hardware_architecture.json"],
        },
    }

    state = _make_state()
    state.start_agent("oli", "Oli")
    state.finish_agent("oli", raw_output="", parsed_output=oli_output)
    state.start_agent("korva", "Korva")
    state.finish_agent("korva", raw_output="", parsed_output=korva_output)

    d = state.to_dict()

    oli_artifacts = (
        d["structured_outputs"]["oli"]["handoff_to_artifact_synthesis"]["next_artifacts"]
    )
    korva_artifacts = (
        d["structured_outputs"]["korva"]["handoff_to_artifact_synthesis"]["next_artifacts"]
    )

    assert oli_artifacts == ["fusion360_concept.json", "component_layout.json"]
    assert korva_artifacts == ["hardware_architecture.json"]


def test_failed_agent_record_survives_to_dict():
    state = _make_state()
    state.start_agent("pluto", "Pluto")
    state.fail_agent("pluto", "LLM timeout")

    d = state.to_dict()
    pluto_record = d["agent_records"]["pluto"]
    assert pluto_record["status"] == "failed"
    assert "LLM timeout" in pluto_record["errors"]
    assert "pluto: LLM timeout" in d["errors"]


def test_build_synthesis_input_is_json_serializable():
    state = _make_state()
    state.start_agent("sky", "Sky")
    state.finish_agent("sky", raw_output="raw", parsed_output={"ros2_plan": "diff drive"})

    synth = state.build_synthesis_input()
    json.dumps(synth)
    assert synth["mission_text"] == "Design a palm-sized rover with ROS2."
    assert "sky" in synth["agent_outputs"]
