from __future__ import annotations

from typing import Any, Dict, List
from pydantic import BaseModel, Field

from backend.app.omni_core.agent_protocol import (
    AgentContribution,
    AgentMessage,
    AgentRole,
)


class MissionState(BaseModel):
    mission_id: str
    user_prompt: str

    interpreted_goal: str = ""
    project_type: str = "unknown"
    target_domain: str = "robotics"

    requirements: List[str] = Field(default_factory=list)
    constraints: List[str] = Field(default_factory=list)
    decisions: List[str] = Field(default_factory=list)
    risks: List[str] = Field(default_factory=list)
    blockers: List[str] = Field(default_factory=list)
    open_questions: List[str] = Field(default_factory=list)

    contributions: Dict[str, AgentContribution] = Field(default_factory=dict)
    messages: List[AgentMessage] = Field(default_factory=list)

    artifacts: Dict[str, Any] = Field(default_factory=dict)
    final_report: Dict[str, Any] = Field(default_factory=dict)

    def add_contribution(self, contribution: AgentContribution) -> None:
        self.contributions[contribution.agent.value] = contribution

        self.risks.extend(contribution.risks)
        self.constraints.extend(contribution.constraints)
        self.open_questions.extend(contribution.open_questions)

    def add_message(self, message: AgentMessage) -> None:
        self.messages.append(message)

        self.risks.extend(message.risks)
        self.constraints.extend(message.constraints)
        self.blockers.extend(message.blockers)

    def get_contribution(self, agent: AgentRole) -> AgentContribution | None:
        return self.contributions.get(agent.value)