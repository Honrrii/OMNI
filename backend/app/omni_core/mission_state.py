# backend/app/core/mission_state.py

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class AgentRecord:
    agent_id: str
    agent_name: str
    raw_output: Optional[str] = None
    parsed_output: Dict[str, Any] = field(default_factory=dict)
    status: str = "pending"
    errors: List[str] = field(default_factory=list)
    started_at: Optional[str] = None
    finished_at: Optional[str] = None


@dataclass
class MissionState:
    mission_text: str
    mission_id: str = field(default_factory=lambda: str(uuid4()))
    status: str = "created"

    created_at: str = field(default_factory=utc_now_iso)
    updated_at: str = field(default_factory=utc_now_iso)

    agent_records: Dict[str, AgentRecord] = field(default_factory=dict)

    structured_outputs: Dict[str, Any] = field(default_factory=dict)
    synthesis_input: Dict[str, Any] = field(default_factory=dict)
    synthesized_artifacts: Dict[str, Any] = field(default_factory=dict)

    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)

    metadata: Dict[str, Any] = field(default_factory=dict)

    def touch(self) -> None:
        self.updated_at = utc_now_iso()

    def set_status(self, status: str) -> None:
        self.status = status
        self.touch()

    def start_agent(self, agent_id: str, agent_name: str) -> None:
        self.agent_records[agent_id] = AgentRecord(
            agent_id=agent_id,
            agent_name=agent_name,
            status="running",
            started_at=utc_now_iso(),
        )
        self.touch()

    def finish_agent(
        self,
        agent_id: str,
        raw_output: str,
        parsed_output: Dict[str, Any],
    ) -> None:
        record = self.agent_records.get(agent_id)

        if record is None:
            record = AgentRecord(agent_id=agent_id, agent_name=agent_id)

        record.raw_output = raw_output
        record.parsed_output = parsed_output
        record.status = "completed"
        record.finished_at = utc_now_iso()

        self.agent_records[agent_id] = record
        self.structured_outputs[agent_id] = parsed_output
        self.touch()

    def fail_agent(self, agent_id: str, error: str, raw_output: Optional[str] = None) -> None:
        record = self.agent_records.get(agent_id)

        if record is None:
            record = AgentRecord(agent_id=agent_id, agent_name=agent_id)

        record.status = "failed"
        record.errors.append(error)
        record.raw_output = raw_output
        record.finished_at = utc_now_iso()

        self.agent_records[agent_id] = record
        self.errors.append(f"{agent_id}: {error}")
        self.touch()

    def add_warning(self, warning: str) -> None:
        self.warnings.append(warning)
        self.touch()

    def add_error(self, error: str) -> None:
        self.errors.append(error)
        self.touch()

    def build_synthesis_input(self) -> Dict[str, Any]:
        """
        The ArtifactSynthesizer should eventually consume this instead of loose agent strings.
        """
        self.synthesis_input = {
            "mission_id": self.mission_id,
            "mission_text": self.mission_text,
            "agent_outputs": self.structured_outputs,
            "warnings": self.warnings,
            "errors": self.errors,
            "metadata": self.metadata,
        }
        self.touch()
        return self.synthesis_input

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)