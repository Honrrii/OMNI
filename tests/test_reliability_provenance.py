"""
Tests for OMNI Reflection & Provenance Core v0.1 — backend foundation only.

Covers:
- ProvenanceRecord schema construction and validation
- build_provenance_from_mission_state with synthetic MissionState data
- build_reflection_notes with synthetic gates / evidence / provenance
"""
from __future__ import annotations

import pytest

from backend.app.omni_core.mission_state import AgentRecord, MissionState
from backend.app.reliability.provenance import build_provenance_from_mission_state
from backend.app.reliability.reflection import build_reflection_notes
from backend.app.reliability.schemas import (
    EvidenceRecord,
    ProvenanceRecord,
    ReliabilityGate,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_gate(gate_id: str, status: str, **kwargs) -> ReliabilityGate:
    return ReliabilityGate(
        id=gate_id,
        name=gate_id.replace("-", " ").title(),
        status=status,
        summary=f"Summary for {gate_id}",
        **kwargs,
    )


def _make_evidence(label: str, evidence_type: str, status: str, human_review: bool = False) -> EvidenceRecord:
    return EvidenceRecord(
        id=f"test-{label[:8]}",
        label=label,
        evidence_type=evidence_type,
        source="test",
        status=status,
        confidence="medium",
        human_review_required=human_review,
    )


def _make_provenance(agent_id: str, confidence: str = "medium", status: str = "completed") -> ProvenanceRecord:
    return ProvenanceRecord(
        agent_id=agent_id,
        agent_name=agent_id.title(),
        claim=f"{agent_id} produced output.",
        evidence_type="llm_generated",
        confidence=confidence,
        human_review_required=True,
        details={"agent_status": status},
    )


# ---------------------------------------------------------------------------
# ProvenanceRecord schema
# ---------------------------------------------------------------------------

class TestProvenanceRecordSchema:
    def test_minimal_construction(self):
        record = ProvenanceRecord(
            agent_id="korva",
            agent_name="Korva (Robotics Systems)",
            claim="Designed ROS2 node topology for rover.",
            evidence_type="llm_generated",
        )
        assert record.agent_id == "korva"
        assert record.confidence == "medium"
        assert record.human_review_required is True

    def test_all_fields(self):
        record = ProvenanceRecord(
            agent_id="pluto",
            agent_name="Pluto (Validation)",
            claim="Flagged missing torque calculation.",
            evidence_type="llm_generated",
            confidence="high",
            timestamp="2026-05-22T00:00:00+00:00",
            human_review_required=True,
            details={"agent_status": "completed"},
        )
        assert record.confidence == "high"
        assert record.timestamp == "2026-05-22T00:00:00+00:00"

    def test_invalid_confidence_rejected(self):
        with pytest.raises(Exception):
            ProvenanceRecord(
                agent_id="x",
                agent_name="X",
                claim="test",
                evidence_type="llm_generated",
                confidence="ultra",  # invalid
            )

    def test_invalid_evidence_type_rejected(self):
        with pytest.raises(Exception):
            ProvenanceRecord(
                agent_id="x",
                agent_name="X",
                claim="test",
                evidence_type="magic_oracle",  # invalid
            )


# ---------------------------------------------------------------------------
# build_provenance_from_mission_state
# ---------------------------------------------------------------------------

class TestBuildProvenanceFromMissionState:
    def _make_state_with_agents(self, agents: dict[str, dict]) -> MissionState:
        state = MissionState(mission_text="Test rover mission for provenance.")
        for agent_id, config in agents.items():
            state.start_agent(agent_id, agent_id.title())
            if config.get("fail"):
                state.fail_agent(agent_id, config.get("error", "unknown error"))
            else:
                state.finish_agent(
                    agent_id,
                    raw_output=config.get("raw", ""),
                    parsed_output=config.get("parsed", {}),
                )
        return state

    def test_empty_state_returns_empty_list(self):
        state = MissionState(mission_text="Empty mission.")
        result = build_provenance_from_mission_state(state)
        assert result == []

    def test_single_completed_agent(self):
        state = self._make_state_with_agents({
            "korva": {"parsed": {"mission_summary": "Rover with ROS2 navigation."}}
        })
        records = build_provenance_from_mission_state(state)
        assert len(records) == 1
        r = records[0]
        assert r.agent_id == "korva"
        assert "Korva" in r.agent_name
        assert r.evidence_type == "llm_generated"
        assert r.confidence == "medium"
        assert "Rover with ROS2 navigation." in r.claim

    def test_failed_agent_gets_low_confidence(self):
        state = self._make_state_with_agents({
            "oli": {"fail": True, "error": "LLM timeout"}
        })
        records = build_provenance_from_mission_state(state)
        assert len(records) == 1
        r = records[0]
        assert r.confidence == "low"
        assert r.human_review_required is True
        assert r.details["agent_status"] == "failed"

    def test_pluto_always_requires_human_review(self):
        state = self._make_state_with_agents({
            "pluto": {"parsed": {"safety_notes": "Check motor torque limits."}}
        })
        records = build_provenance_from_mission_state(state)
        assert records[0].human_review_required is True

    def test_multiple_agents_all_captured(self):
        state = self._make_state_with_agents({
            "echo": {"parsed": {"summary": "Palm-sized rover mission."}},
            "korva": {"parsed": {"ros2_plan": "Differential drive setup."}},
            "pluto": {"fail": True, "error": "Context too long"},
        })
        records = build_provenance_from_mission_state(state)
        assert len(records) == 3
        agent_ids = {r.agent_id for r in records}
        assert agent_ids == {"echo", "korva", "pluto"}

    def test_agent_with_no_parsed_output(self):
        state = self._make_state_with_agents({
            "isy": {"parsed": {}}
        })
        records = build_provenance_from_mission_state(state)
        assert len(records) == 1
        assert "no structured output" in records[0].claim

    def test_unknown_agent_id_gets_defaults(self):
        state = self._make_state_with_agents({
            "future_agent_x": {"parsed": {"result": "Some output."}}
        })
        records = build_provenance_from_mission_state(state)
        assert len(records) == 1
        r = records[0]
        assert r.evidence_type == "llm_generated"
        assert r.agent_name == "future_agent_x"

    def test_timestamp_captured_from_finished_at(self):
        state = self._make_state_with_agents({
            "sky": {"parsed": {"summary": "Drone mission."}}
        })
        records = build_provenance_from_mission_state(state)
        assert records[0].timestamp is not None


# ---------------------------------------------------------------------------
# build_reflection_notes
# ---------------------------------------------------------------------------

class TestBuildReflectionNotes:
    def test_clean_mission_returns_no_critical_flags(self):
        # No provenance, no flagged evidence, only a PASS gate — nothing to surface.
        gates = [_make_gate("mission-requirements", "PASS")]
        evidence = [_make_evidence("Mission text OK", "user_provided", "PASS", human_review=False)]
        notes = build_reflection_notes(gates, evidence, provenance=[])
        assert len(notes) == 1
        assert "No critical" in notes[0]

    def test_blocked_gate_produces_note(self):
        gates = [_make_gate("deterministic-calculations", "BLOCKED")]
        notes = build_reflection_notes(gates, [], [])
        assert any("BLOCKED" in n for n in notes)
        assert any("deterministic-calculations".replace("-", " ").title() in n or "Deterministic" in n for n in notes)

    def test_failed_gate_produces_note(self):
        gates = [_make_gate("ros2-build-validation", "FAIL")]
        notes = build_reflection_notes(gates, [], [])
        assert any("FAILED" in n for n in notes)

    def test_human_review_evidence_produces_note(self):
        evidence = [
            _make_evidence("LLM CAD claim", "llm_generated", "WARN", human_review=True),
            _make_evidence("OMNITorch result", "omnitorch_inference", "WARN", human_review=True),
        ]
        notes = build_reflection_notes([], evidence, [])
        assert any("human review" in n.lower() for n in notes)

    def test_llm_provenance_with_no_calculation_produces_note(self):
        provenance = [_make_provenance("korva", confidence="medium")]
        evidence = []  # no calculation evidence
        notes = build_reflection_notes([], evidence, provenance)
        assert any("provisional" in n.lower() for n in notes)

    def test_failed_agent_produces_note(self):
        provenance = [_make_provenance("pluto", confidence="low", status="failed")]
        notes = build_reflection_notes([], [], provenance)
        assert any("failed" in n.lower() for n in notes)

    def test_low_confidence_provenance_produces_note(self):
        provenance = [_make_provenance("isy", confidence="low")]
        notes = build_reflection_notes([], [], provenance)
        assert any("low-confidence" in n.lower() or "Low-confidence" in n for n in notes)

    def test_warn_gate_with_blockers_produces_note(self):
        gate = _make_gate("artifact-presence", "WARN", blockers=["No artifacts yet."])
        notes = build_reflection_notes([gate], [], [])
        assert any("blocker" in n.lower() or "Blocker" in n for n in notes)

    def test_multiple_issues_all_surfaced(self):
        gates = [
            _make_gate("mission-requirements", "PASS"),
            _make_gate("deterministic-calculations", "BLOCKED"),
            _make_gate("ros2-build-validation", "FAIL"),
        ]
        evidence = [_make_evidence("Needs review", "llm_generated", "WARN", human_review=True)]
        provenance = [_make_provenance("korva")]
        notes = build_reflection_notes(gates, evidence, provenance)
        statuses = " ".join(notes)
        assert "BLOCKED" in statuses
        assert "FAILED" in statuses
        assert "human review" in statuses.lower()

    def test_returns_list_of_strings(self):
        notes = build_reflection_notes([], [], [])
        assert isinstance(notes, list)
        assert all(isinstance(n, str) for n in notes)
