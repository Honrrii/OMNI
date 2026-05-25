from __future__ import annotations

from uuid import uuid4

from backend.app.omni_core.agent_protocol import (
    AgentContribution,
    AgentRole,
    MessageType,
)
from backend.app.omni_core.agent_communication import send_agent_message
from backend.app.omni_core.mission_state import MissionState


class AgentCouncil:
    def __init__(self, agents: dict):
        self.agents = agents

    def run(self, user_prompt: str) -> MissionState:
        mission_state = MissionState(
            mission_id=str(uuid4()),
            user_prompt=user_prompt,
        )

        # 1. Echo interprets rough mission.
        if "Echo" in self.agents:
            echo_output = self.agents["Echo"].run(mission_state)
            mission_state.add_contribution(echo_output)

        # 2. Specialist draft pass.
        for agent_name in ["Sky", "Isy", "Oli", "Pluto"]:
            if agent_name in self.agents:
                contribution = self.agents[agent_name].run(mission_state)
                mission_state.add_contribution(contribution)

        # 3. Cross-agent review.
        mission_state = self._cross_review(mission_state)

        # 4. Validation.
        if "QaZ" in self.agents:
            validation = self.agents["QaZ"].run(mission_state)
            mission_state.add_contribution(validation)

        # 5. Final synthesis.
        if "Korva" in self.agents:
            synthesis = self.agents["Korva"].run(mission_state)
            mission_state.add_contribution(synthesis)
            mission_state.final_report = synthesis.outputs

        return mission_state

    def _cross_review(self, mission_state: MissionState) -> MissionState:
        sky = mission_state.get_contribution(AgentRole.SKY)
        isy = mission_state.get_contribution(AgentRole.ISY)
        oli = mission_state.get_contribution(AgentRole.OLI)

        if sky and isy:
            mission_state = send_agent_message(
                mission_state=mission_state,
                sender=AgentRole.SKY,
                receiver=AgentRole.OLI,
                message_type=MessageType.REVIEW,
                summary="Robotics reviewed CAD morphology for motion compatibility.",
                conclusions=[
                    "CAD should preserve actuator clearance and sensor mounting space."
                ],
                constraints=[
                    "Body geometry must not block leg, wheel, or rotor motion."
                ],
                requests=[
                    "Revise CAD if motion components collide with the chassis."
                ],
            )

        if oli and isy:
            mission_state = send_agent_message(
                mission_state=mission_state,
                sender=AgentRole.KORVA,
                receiver=AgentRole.OLI,
                message_type=MessageType.REVIEW,
                summary="Electronics reviewed CAD morphology for PCB, battery, and wiring compatibility.",
                conclusions=[
                    "Mechanical layout must reserve internal electronics volume."
                ],
                constraints=[
                    "Include PCB mounting holes.",
                    "Reserve battery volume.",
                    "Add wire routing paths."
                ],
                requests=[
                    "Update CAD morphology to include electronics accommodations."
                ],
            )

        return mission_state