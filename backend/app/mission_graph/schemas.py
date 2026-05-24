"""
Mission Knowledge Graph v0.1 — Pydantic schemas.

Every major object has an id.
Relationships are represented by ids, not duplicated nested objects.
Missing fields default safely.
"""
from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Leaf models
# ---------------------------------------------------------------------------

class Requirement(BaseModel):
    id: str
    text: str
    source: str = ""
    status: Literal["unverified", "verified", "failed"] = "unverified"


class BodyRegion(BaseModel):
    id: str
    name: str
    description: str = ""


class Morphology(BaseModel):
    id: str
    source: str = ""
    description: str = ""
    body_region_ids: List[str] = Field(default_factory=list)


class Ros2Node(BaseModel):
    id: str
    name: str
    purpose: str = ""
    publishes_to: List[str] = Field(default_factory=list)   # topic names
    subscribes_to: List[str] = Field(default_factory=list)  # topic names
    services: List[str] = Field(default_factory=list)
    parameters: List[str] = Field(default_factory=list)


class Ros2Topic(BaseModel):
    id: str
    name: str
    publishers: List[str] = Field(default_factory=list)   # Ros2Node ids
    subscribers: List[str] = Field(default_factory=list)  # Ros2Node ids


class PowerRail(BaseModel):
    id: str
    label: str
    voltage_hint: str = ""
    current_hint: str = ""


class DataBus(BaseModel):
    id: str
    label: str
    protocol: str = ""


class Component(BaseModel):
    id: str
    name: str
    type: str = ""
    role: str = ""
    power_notes: str = ""
    interface: str = ""
    body_region_id: Optional[str] = None
    ros2_topic_id: Optional[str] = None
    power_rail_id: Optional[str] = None
    data_bus_id: Optional[str] = None


class CadFeature(BaseModel):
    id: str
    step: str = ""
    purpose: str = ""
    geometry: str = ""
    parameters: List[str] = Field(default_factory=list)
    body_region_id: Optional[str] = None


class PhysicsSubsystem(BaseModel):
    id: str
    name: str
    purpose: str = ""
    inputs: List[str] = Field(default_factory=list)
    outputs: List[str] = Field(default_factory=list)
    notes: List[str] = Field(default_factory=list)


class ValidationCheck(BaseModel):
    id: str
    name: str
    status: Literal["PASS", "WARNING", "FAIL", "UNKNOWN"] = "UNKNOWN"
    source: str = ""
    notes: str = ""


class GeneratedFile(BaseModel):
    id: str
    path: str
    file_type: str = ""
    source: str = ""


class ProvenanceRef(BaseModel):
    id: str
    agent_id: str
    agent_name: str
    status: str = "unknown"
    source: str = ""
    evidence_type: str = "llm_generated"
    human_review_required: bool = True


class ConsistencyWarning(BaseModel):
    id: str
    code: str
    severity: Literal["error", "warning", "info"] = "warning"
    message: str
    related_ids: List[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Root graph
# ---------------------------------------------------------------------------

class MissionKnowledgeGraph(BaseModel):
    graph_id: str
    schema_version: str = "0.1"
    generated_at: str
    mission_id: Optional[str] = None
    mission_text: str = ""
    platform: str = ""
    requirements: List[Requirement] = Field(default_factory=list)
    morphology: List[Morphology] = Field(default_factory=list)
    body_regions: List[BodyRegion] = Field(default_factory=list)
    ros2_nodes: List[Ros2Node] = Field(default_factory=list)
    ros2_topics: List[Ros2Topic] = Field(default_factory=list)
    components: List[Component] = Field(default_factory=list)
    power_rails: List[PowerRail] = Field(default_factory=list)
    data_buses: List[DataBus] = Field(default_factory=list)
    cad_features: List[CadFeature] = Field(default_factory=list)
    physics_subsystems: List[PhysicsSubsystem] = Field(default_factory=list)
    validation_checks: List[ValidationCheck] = Field(default_factory=list)
    generated_files: List[GeneratedFile] = Field(default_factory=list)
    provenance: List[ProvenanceRef] = Field(default_factory=list)
    next_artifacts: List[str] = Field(default_factory=list)
    consistency_warnings: List[ConsistencyWarning] = Field(default_factory=list)
