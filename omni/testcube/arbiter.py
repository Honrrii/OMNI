"""Pure deterministic evaluation. AI proposes; deterministic code disposes.

No provider, execution, filesystem, Git, clock, or promotion capabilities.
"""
from __future__ import annotations

from decimal import Decimal

from omni.autodev.protected_paths import spec_matches
from omni.testcube.models import (
    ArbitrationResult,
    CandidateEvidence,
    CandidatePolicy,
    GateResult,
    MetricComparison,
)


def _gates(candidate: CandidateEvidence, policy: CandidatePolicy) -> tuple[GateResult, ...]:
    results = []
    checks = {check.check_id: check for check in candidate.checks}
    # Required gates first, then every additional observed check. An extra
    # regression failure must not disappear because only focused tests were required.
    ids = policy.required_check_ids
    ids += tuple(sorted(set(checks) - set(ids)))
    for check_id in ids:
        check = checks.get(check_id)
        if check is None:
            passed, reason, refs = False, "MISSING_CHECK", ()
        else:
            passed = check.succeeded
            reason = (
                "EXIT_ZERO" if passed else
                "TIMEOUT" if check.outcome == "timeout" else
                "EXECUTION_ERROR" if check.outcome == "error" else "NONZERO_EXIT"
            )
            refs = (check.evidence_ref,)
        details = (f"outcome={check.outcome}", f"exit_code={check.exit_code}") if check else ()
        results.append(GateResult(candidate.identity.candidate_id, check_id, passed, reason, refs, details))

    scope_refs = (candidate.scope_evidence_ref,) if candidate.scope_evidence_ref else ()
    forbidden = ()
    outside = ()
    if candidate.touched_files is not None:
        forbidden = tuple(path for path in candidate.touched_files if any(
            spec_matches(spec, path) for spec in policy.forbidden_paths
        ))
        outside = tuple(path for path in candidate.touched_files if not any(
            spec_matches(spec, path) for spec in policy.allowed_paths
        ))
    missing_scope = candidate.touched_files is None or not scope_refs
    scope_ok = not missing_scope and not forbidden and not outside
    scope_reason = (
        "MISSING_SCOPE_EVIDENCE" if missing_scope else
        "FORBIDDEN_PATH" if forbidden else "OUTSIDE_ALLOWED_PATHS" if outside else "SCOPE_VALID"
    )
    results.append(GateResult(
        candidate.identity.candidate_id, "scope.paths", scope_ok, scope_reason,
        scope_refs, tuple(sorted(set(forbidden + outside))),
    ))
    for gate, limit, actual in (
        ("scope.file_count", policy.max_touched_files,
         len(candidate.touched_files) if candidate.touched_files is not None else None),
        ("scope.changed_lines", policy.max_changed_lines, candidate.changed_lines),
    ):
        if limit is not None:
            ok = actual is not None and actual <= limit
            results.append(GateResult(
                candidate.identity.candidate_id, gate, ok,
                "MISSING_SCOPE_COUNT" if actual is None else "WITHIN_LIMIT" if ok else "SCOPE_LIMIT_EXCEEDED",
                scope_refs, (f"observed={actual}", f"limit={limit}"),
            ))
    results.append(GateResult(
        candidate.identity.candidate_id, "violations", not candidate.violations,
        "VIOLATIONS_REPORTED" if candidate.violations else "NO_REPORTED_VIOLATIONS",
        scope_refs, candidate.violations,
    ))
    return tuple(results)


def _compare(
    a: CandidateEvidence, b: CandidateEvidence, policy: CandidatePolicy,
) -> tuple[MetricComparison, ...]:
    a_metrics = {metric.metric_id: metric for metric in a.measurements}
    b_metrics = {metric.metric_id: metric for metric in b.measurements}
    results = []
    for spec in policy.metrics:
        left, right = a_metrics.get(spec.metric_id), b_metrics.get(spec.metric_id)
        reason = "COMPARABLE"
        relation = "INCOMPARABLE"
        if left is None or right is None:
            reason = "MISSING_MEASUREMENT"
        elif left.unit != spec.unit or right.unit != spec.unit:
            reason = "UNIT_MISMATCH"
        elif left.context_id != spec.context_id or right.context_id != spec.context_id:
            reason = "CONTEXT_MISMATCH"
        else:
            av, bv = Decimal(left.value), Decimal(right.value)
            if av == bv:
                relation = "EQUAL"
            elif (av < bv) == (spec.direction == "lower"):
                relation = "A_BETTER"
            else:
                relation = "B_BETTER"
        results.append(MetricComparison(
            spec.metric_id, spec.unit, spec.direction, spec.context_id,
            left.value if left else None, right.value if right else None,
            relation, reason,
            tuple(metric.evidence_ref for metric in (left, right) if metric is not None),
        ))
    return tuple(results)


def evaluate(
    *, candidate_a: CandidateEvidence, candidate_b: CandidateEvidence, policy: CandidatePolicy,
) -> ArbitrationResult:
    """Evaluate two bound evidence snapshots under an explicitly supplied policy.

    Malformed inputs/identity mismatches raise ValueError. Missing required
    gates invalidate a candidate. Missing/incompatible comparison measurements
    prevent dominance when both candidates pass their gates.
    """
    if type(policy) is not CandidatePolicy:
        raise ValueError("policy must be CandidatePolicy")
    for candidate, slot in ((candidate_a, "A"), (candidate_b, "B")):
        if type(candidate) is not CandidateEvidence:
            raise ValueError("candidate must be CandidateEvidence")
        if candidate.identity.candidate_id != slot:
            raise ValueError(f"candidate_{slot.lower()} must contain candidate {slot}")
        if candidate.identity.evaluation_id != policy.evaluation_id:
            raise ValueError("candidate evaluation_id does not match policy")

    a_gates = _gates(candidate_a, policy)
    b_gates = _gates(candidate_b, policy)
    a_valid, b_valid = all(gate.passed for gate in a_gates), all(gate.passed for gate in b_gates)
    winner = None
    comparisons = ()
    if not a_valid and not b_valid:
        verdict, reasons = "NO_VALID_CANDIDATE", ("BOTH_FAILED_MANDATORY_GATES",)
    elif a_valid != b_valid:
        winner = "A" if a_valid else "B"
        verdict, reasons = f"CANDIDATE_{winner}_PREFERRED", ("ONLY_VALID_CANDIDATE",)
    else:
        comparisons = _compare(candidate_a, candidate_b, policy)
        relations = {comparison.relation for comparison in comparisons}
        if "INCOMPARABLE" in relations:
            reasons = ("COMPARISON_EVIDENCE_INCOMPLETE",)
        elif "A_BETTER" in relations and "B_BETTER" not in relations:
            winner, reasons = "A", ("PARETO_DOMINANCE",)
        elif "B_BETTER" in relations and "A_BETTER" not in relations:
            winner, reasons = "B", ("PARETO_DOMINANCE",)
        elif "A_BETTER" in relations and "B_BETTER" in relations:
            reasons = ("METRIC_TRADEOFF",)
        else:
            reasons = ("ALL_METRICS_EQUAL" if comparisons else "NO_COMPARATIVE_METRICS",)
        verdict = f"CANDIDATE_{winner}_PREFERRED" if winner else "EVIDENCE_INCONCLUSIVE"

    refs = tuple(sorted({
        ref for item in a_gates + b_gates + comparisons for ref in item.evidence_refs
    }))
    winning_artifact = (
        candidate_a.identity.patch_ref if winner == "A" else
        candidate_b.identity.patch_ref if winner == "B" else None
    )
    return ArbitrationResult(
        verdict, winner, winning_artifact, policy,
        (candidate_a.identity, candidate_b.identity), a_gates + b_gates,
        comparisons, reasons, refs,
    )
