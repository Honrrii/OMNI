from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


GateStatus = Literal["PASS", "WARN", "FAIL", "BLOCKED"]

ProvenanceConfidence = Literal["low", "medium", "high"]

EvidenceType = Literal[
    "user_provided",
    "llm_generated",
    "calculation",
    "simulation",
    "build_test",
    "uploaded_file",
    "omnitorch_inference",
    "local_knowledge",
    "missing_evidence",
]

EvidenceConfidence = Literal["low", "medium", "high"]


class EvidenceRecord(BaseModel):
    id: str
    label: str
    evidence_type: EvidenceType
    source: str
    status: GateStatus = "WARN"
    confidence: EvidenceConfidence = "medium"
    details: Dict[str, Any] = Field(default_factory=dict)
    human_review_required: bool = False


class ReliabilityGate(BaseModel):
    id: str
    name: str
    status: GateStatus
    summary: str
    evidence_ids: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    blockers: List[str] = Field(default_factory=list)
    required_next_tests: List[str] = Field(default_factory=list)


class EvidenceSummary(BaseModel):
    total_evidence_records: int = 0
    by_type: Dict[str, int] = Field(default_factory=dict)
    by_status: Dict[str, int] = Field(default_factory=dict)
    high_confidence_records: int = 0
    human_review_required: bool = False


class ProvenanceRecord(BaseModel):
    agent_id: str
    agent_name: str
    claim: str
    evidence_type: EvidenceType
    confidence: ProvenanceConfidence = "medium"
    timestamp: Optional[str] = None
    human_review_required: bool = True
    details: Dict[str, Any] = Field(default_factory=dict)


class ReliabilityReviewRequest(BaseModel):
    mission_text: str
    mission_result: Optional[Dict[str, Any]] = None
    export_result: Optional[Dict[str, Any]] = None
    omnitorch_result: Optional[Dict[str, Any]] = None
    context: Optional[Dict[str, Any]] = None


class ReliabilityReport(BaseModel):
    system: str = "OMNI Reliability Core"
    version: str = "0.1.0"

    overall_status: GateStatus
    engineering_confidence: float = Field(ge=0.0, le=1.0)

    mission_domain: str
    summary: str

    gates: List[ReliabilityGate] = Field(default_factory=list)
    evidence: List[EvidenceRecord] = Field(default_factory=list)
    evidence_summary: EvidenceSummary

    passed_checks: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    blockers: List[str] = Field(default_factory=list)
    required_next_tests: List[str] = Field(default_factory=list)
    recommendations: List[str] = Field(default_factory=list)

    provenance: List[ProvenanceRecord] = Field(default_factory=list)
    reflection_notes: List[str] = Field(default_factory=list)