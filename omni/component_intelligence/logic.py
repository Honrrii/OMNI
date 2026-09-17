"""Pure logical semantics for OMNI Component Intelligence v0.1."""

from __future__ import annotations

from dataclasses import dataclass


TRUTHS = {"TRUE", "FALSE", "UNKNOWN"}
COVERAGES = {"COVERED", "UNCOVERED", "UNKNOWN"}


@dataclass(frozen=True)
class EvalResult:
    truth: str
    coverage: str
    dependency_ids: tuple[str, ...] = ()


def _all_coverage(values: list[str]) -> str:
    if not values:
        return "COVERED"
    if all(value == "COVERED" for value in values):
        return "COVERED"
    if any(value == "UNCOVERED" for value in values):
        return "UNCOVERED"
    return "UNKNOWN"


def _and_truth(values: list[str]) -> str:
    if not values:
        return "TRUE"
    if any(value == "FALSE" for value in values):
        return "FALSE"
    if all(value == "TRUE" for value in values):
        return "TRUE"
    return "UNKNOWN"


def _or_truth(values: list[str]) -> str:
    if not values:
        return "FALSE"
    if any(value == "TRUE" for value in values):
        return "TRUE"
    if all(value == "FALSE" for value in values):
        return "FALSE"
    return "UNKNOWN"


def _or_coverage(children: list[EvalResult], truth: str) -> str:
    if truth != "TRUE":
        return _all_coverage([child.coverage for child in children])

    witnesses = [child for child in children if child.truth == "TRUE"]
    if any(child.coverage == "COVERED" for child in witnesses):
        return "COVERED"
    if any(child.coverage == "UNKNOWN" for child in witnesses):
        return "UNKNOWN"
    return "UNCOVERED"


def collect_dependency_ids(expression: dict | None) -> set[str]:
    if not isinstance(expression, dict):
        return set()

    result = set(expression.get("dependency_ids", []))
    op = expression.get("op")

    if op in {"and", "or"}:
        for child in expression.get("args", []):
            result.update(collect_dependency_ids(child))

    elif op in {"forall", "exists", "cardinality"}:
        for child in expression.get("items", []):
            result.update(collect_dependency_ids(child))

    return result


def evaluate_expression(
    expression: dict,
    completion_id: str,
    scopes: dict[str, str],
) -> EvalResult:
    if not isinstance(expression, dict):
        return EvalResult("UNKNOWN", "UNCOVERED")

    op = expression.get("op")

    if op == "literal":
        truth = expression.get("truth", "UNKNOWN")
        if truth not in TRUTHS:
            truth = "UNKNOWN"
        return EvalResult(
            truth=truth,
            coverage="COVERED",
            dependency_ids=tuple(sorted(expression.get("dependency_ids", []))),
        )

    if op == "observation":
        dependencies = tuple(sorted(set(expression.get("dependency_ids", []))))
        observation = expression.get("by_completion", {}).get(completion_id)

        if not isinstance(observation, dict):
            return EvalResult("UNKNOWN", "UNKNOWN", dependencies)

        truth = observation.get("truth", "UNKNOWN")
        coverage = observation.get("coverage", "UNKNOWN")

        if truth not in TRUTHS:
            truth = "UNKNOWN"
        if coverage not in COVERAGES:
            coverage = "UNKNOWN"

        return EvalResult(truth, coverage, dependencies)

    if op in {"and", "or"}:
        children = [
            evaluate_expression(child, completion_id, scopes)
            for child in expression.get("args", [])
        ]

        dependencies = tuple(
            sorted(
                set(expression.get("dependency_ids", []))
                | {
                    dep
                    for child in children
                    for dep in child.dependency_ids
                }
            )
        )

        if op == "and":
            truth = _and_truth([child.truth for child in children])
            coverage = _all_coverage([child.coverage for child in children])
        else:
            truth = _or_truth([child.truth for child in children])
            coverage = _or_coverage(children, truth)

        return EvalResult(truth, coverage, dependencies)

    if op in {"forall", "exists"}:
        children = [
            evaluate_expression(child, completion_id, scopes)
            for child in expression.get("items", [])
        ]

        dependencies = tuple(
            sorted(
                set(expression.get("dependency_ids", []))
                | {
                    dep
                    for child in children
                    for dep in child.dependency_ids
                }
            )
        )

        scope_state = scopes.get(expression.get("scope"), "OPEN")
        child_truths = [child.truth for child in children]

        if scope_state == "CLOSED":
            truth = (
                _and_truth(child_truths)
                if op == "forall"
                else _or_truth(child_truths)
            )
        elif op == "forall":
            truth = "FALSE" if any(value == "FALSE" for value in child_truths) else "UNKNOWN"
        else:
            truth = "TRUE" if any(value == "TRUE" for value in child_truths) else "UNKNOWN"

        if op == "exists":
            coverage = _or_coverage(children, truth)
        else:
            coverage = _all_coverage([child.coverage for child in children])

        return EvalResult(truth, coverage, dependencies)

    if op == "cardinality":
        children = [
            evaluate_expression(child, completion_id, scopes)
            for child in expression.get("items", [])
        ]

        dependencies = tuple(
            sorted(
                set(expression.get("dependency_ids", []))
                | {
                    dep
                    for child in children
                    for dep in child.dependency_ids
                }
            )
        )

        minimum = expression.get("min", 0)
        maximum = expression.get("max")
        scope_state = scopes.get(expression.get("scope"), "OPEN")

        lower = sum(child.truth == "TRUE" for child in children)
        unknown = sum(child.truth == "UNKNOWN" for child in children)
        upper = lower + unknown

        if maximum is not None and minimum > maximum:
            truth = "FALSE"

        elif scope_state == "CLOSED":
            if lower >= minimum and (maximum is None or upper <= maximum):
                truth = "TRUE"
            elif upper < minimum:
                truth = "FALSE"
            elif maximum is not None and lower > maximum:
                truth = "FALSE"
            else:
                truth = "UNKNOWN"

        else:
            # OPEN scope means additional unseen members may exist.
            if maximum is not None and lower > maximum:
                truth = "FALSE"
            elif maximum is None and lower >= minimum:
                truth = "TRUE"
            else:
                truth = "UNKNOWN"

        coverage = _all_coverage([child.coverage for child in children])
        return EvalResult(truth, coverage, dependencies)

    return EvalResult(
        "UNKNOWN",
        "UNCOVERED",
        tuple(sorted(expression.get("dependency_ids", []))),
    )
