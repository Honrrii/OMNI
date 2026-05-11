from backend.app.omni_core.agent_protocol import (
    AgentMessage,
    AgentRole,
    MessageType,
)
from backend.app.omni_core.mission_state import MissionState


def send_agent_message(
    mission_state: MissionState,
    sender: AgentRole,
    receiver: AgentRole | str,
    message_type: MessageType,
    summary: str,
    task: str | None = None,
    conclusions: list[str] | None = None,
    assumptions: list[str] | None = None,
    constraints: list[str] | None = None,
    risks: list[str] | None = None,
    requests: list[str] | None = None,
    blockers: list[str] | None = None,
    artifacts: dict | None = None,
    confidence: float = 0.75,
) -> MissionState:
    message = AgentMessage(
        mission_id=mission_state.mission_id,
        sender=sender,
        receiver=receiver,
        message_type=message_type,
        summary=summary,
        task=task,
        conclusions=conclusions or [],
        assumptions=assumptions or [],
        constraints=constraints or [],
        risks=risks or [],
        requests=requests or [],
        blockers=blockers or [],
        artifacts=artifacts or {},
        confidence=confidence,
    )

    mission_state.add_message(message)
    return mission_state