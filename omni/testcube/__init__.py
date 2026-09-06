"""TestCube's model-independent, evidence-only arbitration API."""

from omni.testcube.arbiter import evaluate
from omni.testcube.models import (
    ArbitrationResult,
    CandidateEvidence,
    CandidatePolicy,
    CheckEvidence,
    EvidenceIdentity,
    Measurement,
    MetricSpec,
    candidate_evidence_from_dict,
    candidate_policy_from_dict,
)

__all__ = [
    "ArbitrationResult", "CandidateEvidence", "CandidatePolicy", "CheckEvidence",
    "EvidenceIdentity", "Measurement", "MetricSpec", "evaluate",
    "candidate_evidence_from_dict", "candidate_policy_from_dict",
]
