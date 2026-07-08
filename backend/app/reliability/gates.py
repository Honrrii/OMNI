from __future__ import annotations

from backend.app.reliability.schemas import GateStatus, ReliabilityGate


_STATUS_PRIORITY: dict[GateStatus, int] = {
    "PASS": 0,
    "WARN": 1,
    "FAIL": 2,
    "BLOCKED": 3,
}


def make_gate(
    *,
    gate_id: str,
    name: str,
    status: GateStatus,
    summary: str,
    evidence_ids: list[str] | None = None,
    warnings: list[str] | None = None,
    blockers: list[str] | None = None,
    required_next_tests: list[str] | None = None,
) -> ReliabilityGate:
    return ReliabilityGate(
        id=gate_id,
        name=name,
        status=status,
        summary=summary,
        evidence_ids=evidence_ids or [],
        warnings=warnings or [],
        blockers=blockers or [],
        required_next_tests=required_next_tests or [],
    )


def compute_overall_status(gates: list[ReliabilityGate]) -> GateStatus:
    if not gates:
        return "BLOCKED"

    return max(gates, key=lambda gate: _STATUS_PRIORITY[gate.status]).status


def collect_passed_checks(gates: list[ReliabilityGate]) -> list[str]:
    return [gate.summary for gate in gates if gate.status == "PASS"]


def collect_warnings(gates: list[ReliabilityGate]) -> list[str]:
    warnings: list[str] = []

    for gate in gates:
        if gate.status == "WARN":
            warnings.append(gate.summary)
        warnings.extend(gate.warnings)

    return warnings


def collect_blockers(gates: list[ReliabilityGate]) -> list[str]:
    blockers: list[str] = []

    for gate in gates:
        if gate.status == "BLOCKED":
            blockers.append(gate.summary)
        blockers.extend(gate.blockers)

    return blockers


def collect_required_next_tests(gates: list[ReliabilityGate]) -> list[str]:
    tests: list[str] = []

    for gate in gates:
        tests.extend(gate.required_next_tests)

    seen: set[str] = set()
    unique_tests: list[str] = []

    for test in tests:
        if test not in seen:
            seen.add(test)
            unique_tests.append(test)

    return unique_tests