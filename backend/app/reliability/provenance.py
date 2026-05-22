from __future__ import annotations

from typing import TYPE_CHECKING, List

from backend.app.reliability.schemas import EvidenceType, ProvenanceRecord

if TYPE_CHECKING:
    from backend.app.omni_core.mission_state import MissionState

_AGENT_EVIDENCE_TYPE_MAP: dict[str, EvidenceType] = {
    "echo": "llm_generated",
    "korva": "llm_generated",
    "sky": "llm_generated",
    "qaz": "llm_generated",
    "oli": "llm_generated",
    "isy": "llm_generated",
    "pluto": "llm_generated",
    "omni": "llm_generated",
    "vega": "llm_generated",
}

_AGENT_DISPLAY_NAMES: dict[str, str] = {
    "echo": "Echo (Mission Interpreter)",
    "korva": "Korva (Robotics Systems)",
    "sky": "Sky (Drone & Autonomous Systems)",
    "qaz": "Qaz (CAD & Forge)",
    "oli": "Oli (Code & Implementation)",
    "isy": "Isy (Research & Documentation)",
    "pluto": "Pluto (Validation & Safety)",
    "omni": "OMNI (Central Command)",
    "vega": "Vega (Design)",
}

_HUMAN_REVIEW_ALWAYS: frozenset[str] = frozenset({"pluto", "qaz", "omni"})


def _infer_claim(agent_id: str, parsed_output: dict) -> str:
    """
    Build a one-sentence provenance claim from an agent's parsed output.
    Falls back to a generic claim if no recognizable keys are present.
    """
    if not parsed_output:
        return f"Agent {agent_id} completed with no structured output."

    if "error" in parsed_output:
        return f"Agent {agent_id} reported an error: {str(parsed_output['error'])[:120]}"

    known_keys = [
        "mission_summary", "summary", "result", "ros2_plan", "cad_plan",
        "validation_notes", "safety_notes", "design_notes", "research_notes",
        "final_synthesis", "artifacts", "report",
    ]

    for key in known_keys:
        value = parsed_output.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()[:200]
        if isinstance(value, list) and value:
            return str(value[0])[:200]
        if isinstance(value, dict) and value:
            first_val = next(iter(value.values()), None)
            if isinstance(first_val, str) and first_val.strip():
                return first_val.strip()[:200]

    first_key = next(iter(parsed_output))
    first_val = parsed_output[first_key]
    return f"{agent_id} output [{first_key}]: {str(first_val)[:160]}"


def build_provenance_from_mission_state(state: "MissionState") -> List[ProvenanceRecord]:
    """
    Extract a ProvenanceRecord for every agent that ran in a MissionState.

    Reads agent_records (populated by MissionState.finish_agent / fail_agent)
    and produces one record per agent. Does not call any LLM or external service.
    """
    records: List[ProvenanceRecord] = []

    for agent_id, agent_record in state.agent_records.items():
        normalized_id = agent_id.lower().strip()

        evidence_type: EvidenceType = _AGENT_EVIDENCE_TYPE_MAP.get(
            normalized_id, "llm_generated"
        )

        display_name = _AGENT_DISPLAY_NAMES.get(normalized_id, agent_id)

        parsed = agent_record.parsed_output or {}
        claim = _infer_claim(agent_id, parsed)

        if agent_record.status == "failed":
            confidence = "low"
            human_review_required = True
        elif agent_record.status == "completed":
            confidence = "medium"
            human_review_required = normalized_id in _HUMAN_REVIEW_ALWAYS
        else:
            confidence = "low"
            human_review_required = True

        details: dict = {"agent_status": agent_record.status}
        if agent_record.errors:
            details["errors"] = agent_record.errors

        records.append(
            ProvenanceRecord(
                agent_id=agent_id,
                agent_name=display_name,
                claim=claim,
                evidence_type=evidence_type,
                confidence=confidence,
                timestamp=agent_record.finished_at or agent_record.started_at,
                human_review_required=human_review_required,
                details=details,
            )
        )

    return records
