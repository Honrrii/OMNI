from __future__ import annotations

from backend.app.reliability.schemas import EvidenceRecord, ReliabilityGate


_GATE_SCORE = {
    "PASS": 1.0,
    "WARN": 0.6,
    "FAIL": 0.25,
    "BLOCKED": 0.1,
}

_EVIDENCE_CONFIDENCE_BONUS = {
    "high": 0.08,
    "medium": 0.03,
    "low": 0.0,
}


def compute_engineering_confidence(
    *,
    gates: list[ReliabilityGate],
    evidence: list[EvidenceRecord],
) -> float:
    if not gates:
        return 0.0

    gate_score = sum(_GATE_SCORE[gate.status] for gate in gates) / len(gates)

    if evidence:
        evidence_bonus = sum(
            _EVIDENCE_CONFIDENCE_BONUS[item.confidence] for item in evidence
        ) / len(evidence)
    else:
        evidence_bonus = 0.0

    blocker_penalty = 0.15 * sum(1 for gate in gates if gate.status == "BLOCKED")
    fail_penalty = 0.10 * sum(1 for gate in gates if gate.status == "FAIL")

    confidence = gate_score + evidence_bonus - blocker_penalty - fail_penalty

    return round(max(0.0, min(1.0, confidence)), 3)