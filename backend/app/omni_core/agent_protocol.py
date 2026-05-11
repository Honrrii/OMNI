from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class AgentRole(str, Enum):
    ECHO = "Echo"
    SUPERVISOR = "Omni"
    ROBOTICS = "Sky"
    CAD = "Isy"
    ELECTRONICS = "Oli"
    RESEARCH = "Pluto"
    VALIDATION = "QaZ"
    SYNTHESIS = "Korva"


class MessageType(str, Enum):
    TASK = "task"
    FINDING = "finding"
    HANDOFF = "handoff"
    REVIEW = "review"
    REVISION_REQUEST = "revision_request"
    DECISION = "decision"
    BLOCKER = "blocker"
    FINAL = "final"


class AgentMessage(BaseModel):
    mission_id: str
    sender: AgentRole
    receiver: AgentRole | str
    message_type: MessageType

    summary: str
    task: Optional[str] = None

    conclusions: List[str] = Field(default_factory=list)
    assumptions: List[str] = Field(default_factory=list)
    constraints: List[str] = Field(default_factory=list)
    risks: List[str] = Field(default_factory=list)
    requests: List[str] = Field(default_factory=list)
    blockers: List[str] = Field(default_factory=list)

    artifacts: Dict[str, Any] = Field(default_factory=dict)
    confidence: float = 0.75


class AgentContribution(BaseModel):
    agent: AgentRole
    mission_id: str
    domain: str

    summary: str
    outputs: Dict[str, Any] = Field(default_factory=dict)

    assumptions: List[str] = Field(default_factory=list)
    constraints: List[str] = Field(default_factory=list)
    risks: List[str] = Field(default_factory=list)
    open_questions: List[str] = Field(default_factory=list)
    requested_reviews: List[AgentRole] = Field(default_factory=list)

    confidence: float = 0.75