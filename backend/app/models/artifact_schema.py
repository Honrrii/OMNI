from pydantic import BaseModel
from typing import List, Optional


class ROS2Node(BaseModel):
    id: str
    label: str
    type: str
    description: Optional[str] = None


class ROS2Edge(BaseModel):
    source: str
    target: str
    topic: str
    message_type: Optional[str] = None


class ROS2NodeGraph(BaseModel):
    nodes: List[ROS2Node]
    edges: List[ROS2Edge]


class ComponentTreeItem(BaseModel):
    name: str
    category: str
    purpose: str
    children: Optional[List["ComponentTreeItem"]] = []


class BlueprintZone(BaseModel):
    zone: str
    component: str
    placement: str
    notes: str


class RiskItem(BaseModel):
    risk: str
    severity: str
    likelihood: str
    mitigation: str
    owner: str


class TestChecklistItem(BaseModel):
    subsystem: str
    test: str
    success_criteria: str
    safety_note: str
    status: str = "pending"


class ApprovalGate(BaseModel):
    gate: str
    required_decision: str
    reason: str
    status: str = "needs_review"


class NextArtifact(BaseModel):
    name: str
    artifact_type: str
    purpose: str
    generated_by: str


class MissionArtifacts(BaseModel):
    ros2_node_graph: ROS2NodeGraph
    component_tree: List[ComponentTreeItem]
    blueprint_plan: List[BlueprintZone]
    risk_matrix: List[RiskItem]
    test_checklist: List[TestChecklistItem]
    approval_gates: List[ApprovalGate]
    next_artifacts: List[NextArtifact]


class MissionResponse(BaseModel):
    mission: str
    status: str
    agents: dict
    final_report: str
    artifacts: Optional[MissionArtifacts] = None