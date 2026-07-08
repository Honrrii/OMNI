from __future__ import annotations

from collections import Counter
from typing import Any, Dict
from uuid import uuid4

from backend.app.reliability.schemas import (
    EvidenceConfidence,
    EvidenceRecord,
    EvidenceSummary,
    EvidenceType,
    GateStatus,
)


def make_evidence(
    *,
    label: str,
    evidence_type: EvidenceType,
    source: str,
    status: GateStatus = "WARN",
    confidence: EvidenceConfidence = "medium",
    details: Dict[str, Any] | None = None,
    human_review_required: bool = False,
) -> EvidenceRecord:
    prefix = evidence_type.replace("_", "-")

    return EvidenceRecord(
        id=f"{prefix}-{uuid4().hex[:8]}",
        label=label,
        evidence_type=evidence_type,
        source=source,
        status=status,
        confidence=confidence,
        details=details or {},
        human_review_required=human_review_required,
    )


def build_evidence_summary(evidence: list[EvidenceRecord]) -> EvidenceSummary:
    type_counts = Counter(item.evidence_type for item in evidence)
    status_counts = Counter(item.status for item in evidence)

    return EvidenceSummary(
        total_evidence_records=len(evidence),
        by_type=dict(type_counts),
        by_status=dict(status_counts),
        high_confidence_records=sum(1 for item in evidence if item.confidence == "high"),
        human_review_required=any(item.human_review_required for item in evidence),
    )