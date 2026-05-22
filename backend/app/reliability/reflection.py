from __future__ import annotations

from typing import List

from backend.app.reliability.schemas import EvidenceRecord, ProvenanceRecord, ReliabilityGate


def build_reflection_notes(
    gates: List[ReliabilityGate],
    evidence: List[EvidenceRecord],
    provenance: List[ProvenanceRecord],
) -> List[str]:
    """
    Produce human-readable reflection notes from existing gate, evidence, and
    provenance data. All logic is deterministic — no LLM calls.

    Notes surface:
    - Blocked or failed gates that need attention
    - Evidence records flagged for human review
    - LLM-generated provenance claims with no backing calculation
    - Agents that failed or produced no structured output
    """
    notes: List[str] = []

    # Blocked / failed gates
    for gate in gates:
        if gate.status == "BLOCKED":
            notes.append(
                f"Gate '{gate.name}' is BLOCKED: {gate.summary} "
                "— resolve blockers before treating this mission as engineering-ready."
            )
        elif gate.status == "FAIL":
            notes.append(
                f"Gate '{gate.name}' FAILED: {gate.summary} "
                "— this gate must pass before any hardware use."
            )

    # Evidence requiring human review
    review_required = [e for e in evidence if e.human_review_required]
    if review_required:
        labels = ", ".join(e.label for e in review_required[:5])
        tail = f" (and {len(review_required) - 5} more)" if len(review_required) > 5 else ""
        notes.append(
            f"{len(review_required)} evidence record(s) require human review: {labels}{tail}."
        )

    # LLM-generated provenance with no backing calculation in evidence
    calculation_agent_ids = {
        e.source for e in evidence if e.evidence_type == "calculation"
    }
    llm_only_agents = [
        p for p in provenance
        if p.evidence_type == "llm_generated"
        and p.agent_id not in calculation_agent_ids
        and p.confidence != "high"
    ]
    if llm_only_agents:
        names = ", ".join(p.agent_name for p in llm_only_agents[:4])
        tail = f" (and {len(llm_only_agents) - 4} more)" if len(llm_only_agents) > 4 else ""
        notes.append(
            f"LLM-generated claims from {names}{tail} have no backing deterministic "
            "calculation. Treat these as provisional until verified."
        )

    # Agents that failed
    failed_agents = [p for p in provenance if p.details.get("agent_status") == "failed"]
    if failed_agents:
        names = ", ".join(p.agent_name for p in failed_agents)
        notes.append(
            f"The following agents failed during this mission and their outputs may be "
            f"incomplete or missing: {names}."
        )

    # Warn gates that carry blockers but weren't promoted to BLOCKED
    for gate in gates:
        if gate.status == "WARN" and gate.blockers:
            notes.append(
                f"Gate '{gate.name}' is WARN but carries unresolved blockers: "
                + "; ".join(gate.blockers[:3])
            )

    # Low-confidence provenance
    low_confidence = [p for p in provenance if p.confidence == "low"]
    if low_confidence:
        names = ", ".join(p.agent_name for p in low_confidence[:4])
        tail = f" (and {len(low_confidence) - 4} more)" if len(low_confidence) > 4 else ""
        notes.append(
            f"Low-confidence provenance from: {names}{tail}. "
            "Re-run these agents or supply additional evidence."
        )

    if not notes:
        notes.append(
            "No critical reflection flags detected. Continue with standard engineering "
            "validation before any hardware use."
        )

    return notes
