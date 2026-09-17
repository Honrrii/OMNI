"""Contract evaluation for OMNI Component Intelligence v0.1."""

from __future__ import annotations

from copy import deepcopy

from .logic import collect_dependency_ids, evaluate_expression


def _dependency_resolved(identifier: str, dependencies: dict[str, dict]) -> bool:
    declaration = dependencies.get(identifier)
    if not isinstance(declaration, dict):
        return False

    kind = declaration.get("kind")

    if kind == "UNBOUNDED":
        return False

    if kind in {"FINITE", "JOINT"}:
        options = declaration.get("options", [])
        return isinstance(options, list) and bool(options)

    return False


def _aggregate_applicability(values: list[str]) -> str:
    if values and all(value == "APPLIES" for value in values):
        return "APPLIES"
    if values and all(value == "NOT_APPLICABLE" for value in values):
        return "NOT_APPLICABLE"
    return "UNDETERMINED"


def _aggregate_truth(values: list[str]) -> str:
    if values and all(value == "TRUE" for value in values):
        return "TRUE"
    if values and all(value == "FALSE" for value in values):
        return "FALSE"
    return "UNKNOWN"


def _aggregate_coverage(values: list[str]) -> str:
    if values and all(value == values[0] for value in values):
        return values[0]
    return "UNKNOWN"


def _scope_state(requirement: dict, scopes: dict[str, str]) -> str:
    return (
        "OPEN"
        if any(
            scopes.get(scope_id, "OPEN") != "CLOSED"
            for scope_id in requirement.get("required_scopes", [])
        )
        else "CLOSED"
    )


def _provenance(requirement: dict) -> list[dict]:
    value = requirement.get("provenance")
    if isinstance(value, dict):
        return [deepcopy(value)]

    # The frozen fixtures provide requirement provenance. This fallback merely
    # keeps malformed external input inspectable.
    return [{
        "category": "USER_PROVIDED",
        "origin": "HUMAN",
        "source_ref": "component-intelligence:v0.1",
    }]


def _finding(
    requirement: dict,
    code: str,
    *,
    state: str,
    observed: dict,
    expected: dict,
    dependency_ids: list[str] | None = None,
) -> dict:
    identifier = requirement["id"]

    return {
        "id": f"{identifier}::{code}",
        "requirement_id": identifier,
        "rule_id": "logical_contract",
        "code": code,
        "state": state,
        "components": [],
        "interfaces": [],
        "observed": observed,
        "expected": expected,
        "explanation": f"{identifier}: {code}",
        "provenance": _provenance(requirement),
        "dependency_ids": sorted(set(dependency_ids or [])),
    }


def evaluate_contract(document: dict) -> dict:
    scopes = document.get("scopes", {})
    dependency_map = {
        item["id"]: item
        for item in document.get("dependencies", [])
        if isinstance(item, dict) and isinstance(item.get("id"), str)
    }

    completions = sorted(
        [
            item
            for item in document.get("completions", [])
            if isinstance(item, dict) and isinstance(item.get("id"), str)
        ],
        key=lambda item: item["id"],
    )

    requirements = sorted(
        [
            item
            for item in document.get("requirements", [])
            if isinstance(item, dict) and isinstance(item.get("id"), str)
        ],
        key=lambda item: item["id"],
    )

    requirement_results: dict[str, dict] = {}
    findings: list[dict] = []
    metadata: dict[str, dict] = {}

    for requirement in requirements:
        identifier = requirement["id"]
        antecedent = requirement.get(
            "antecedent",
            {"op": "literal", "truth": "TRUE"},
        )
        predicate = requirement.get(
            "predicate",
            {"op": "literal", "truth": "UNKNOWN"},
        )

        declared_dependencies = set(requirement.get("dependency_ids", []))
        antecedent_dependencies = collect_dependency_ids(antecedent)
        predicate_dependencies = collect_dependency_ids(predicate)

        all_dependencies = sorted(
            declared_dependencies
            | antecedent_dependencies
            | predicate_dependencies
        )

        unresolved_all = sorted(
            dep
            for dep in all_dependencies
            if not _dependency_resolved(dep, dependency_map)
        )

        unresolved_antecedent = sorted(
            dep
            for dep in antecedent_dependencies
            if not _dependency_resolved(dep, dependency_map)
        )

        completion_results: dict[str, dict] = {}

        for completion in completions:
            completion_id = completion["id"]

            antecedent_result = evaluate_expression(
                antecedent,
                completion_id,
                scopes,
            )

            predicate_result = evaluate_expression(
                predicate,
                completion_id,
                scopes,
            )

            if unresolved_antecedent:
                applicability = "UNDETERMINED"
            elif (
                antecedent_result.truth == "TRUE"
                and antecedent_result.coverage == "COVERED"
            ):
                applicability = "APPLIES"
            elif (
                antecedent_result.truth == "FALSE"
                and antecedent_result.coverage == "COVERED"
            ):
                applicability = "NOT_APPLICABLE"
            else:
                applicability = "UNDETERMINED"

            truth = predicate_result.truth

            if applicability != "APPLIES":
                truth = "UNKNOWN"
            elif unresolved_all:
                truth = "UNKNOWN"

            completion_results[completion_id] = {
                "applicability": applicability,
                "truth": truth,
                "coverage": predicate_result.coverage,
            }

        applicability_values = [
            item["applicability"]
            for item in completion_results.values()
        ]

        applicability = _aggregate_applicability(applicability_values)

        if applicability == "APPLIES":
            truth = _aggregate_truth(
                [item["truth"] for item in completion_results.values()]
            )
        else:
            truth = "UNKNOWN"

        coverage = _aggregate_coverage(
            [item["coverage"] for item in completion_results.values()]
        )

        scope = _scope_state(requirement, scopes)

        result = {
            "applicability": applicability,
            "truth": truth,
            "coverage": coverage,
            "scope": scope,
            "dependency_ids": all_dependencies,
            "completion_results": completion_results,
        }

        requirement_results[identifier] = result

        metadata[identifier] = {
            "mandatory": bool(requirement.get("mandatory", True)),
            "unresolved_dependencies": unresolved_all,
        }

        if unresolved_all:
            findings.append(
                _finding(
                    requirement,
                    "UNRESOLVED_DEPENDENCY",
                    state="UNKNOWN",
                    observed={
                        "unresolved_dependencies": unresolved_all,
                    },
                    expected={
                        "dependencies": "RESOLVED",
                    },
                    dependency_ids=unresolved_all,
                )
            )

        if applicability == "NOT_APPLICABLE":
            findings.append(
                _finding(
                    requirement,
                    "NOT_APPLICABLE",
                    state=applicability,
                    observed={
                        "applicability": applicability,
                    },
                    expected={
                        "applicability": "APPLIES",
                    },
                    dependency_ids=all_dependencies,
                )
            )

        elif applicability == "UNDETERMINED":
            findings.append(
                _finding(
                    requirement,
                    "UNDETERMINED_APPLICABILITY",
                    state=applicability,
                    observed={
                        "applicability": applicability,
                    },
                    expected={
                        "applicability": "APPLIES",
                    },
                    dependency_ids=all_dependencies,
                )
            )

        if scope == "OPEN":
            open_scopes = sorted(
                scope_id
                for scope_id in requirement.get("required_scopes", [])
                if scopes.get(scope_id, "OPEN") != "CLOSED"
            )

            findings.append(
                _finding(
                    requirement,
                    "OPEN_SCOPE",
                    state=scope,
                    observed={
                        "open_scopes": open_scopes,
                    },
                    expected={
                        "required_scopes": "CLOSED",
                    },
                    dependency_ids=all_dependencies,
                )
            )

        if applicability == "APPLIES":
            if truth == "FALSE":
                findings.append(
                    _finding(
                        requirement,
                        "REQUIREMENT_FALSE",
                        state=truth,
                        observed={
                            "truth": truth,
                        },
                        expected={
                            "truth": "TRUE",
                        },
                        dependency_ids=all_dependencies,
                    )
                )

            elif truth == "UNKNOWN":
                findings.append(
                    _finding(
                        requirement,
                        "UNKNOWN_TRUTH",
                        state=truth,
                        observed={
                            "truth": truth,
                        },
                        expected={
                            "truth": "TRUE",
                        },
                        dependency_ids=all_dependencies,
                    )
                )

            if coverage == "UNCOVERED":
                findings.append(
                    _finding(
                        requirement,
                        "UNCOVERED_RULE",
                        state=coverage,
                        observed={
                            "coverage": coverage,
                        },
                        expected={
                            "coverage": "COVERED",
                        },
                        dependency_ids=all_dependencies,
                    )
                )

            elif coverage == "UNKNOWN":
                findings.append(
                    _finding(
                        requirement,
                        "UNKNOWN_COVERAGE",
                        state=coverage,
                        observed={
                            "coverage": coverage,
                        },
                        expected={
                            "coverage": "COVERED",
                        },
                        dependency_ids=all_dependencies,
                    )
                )

    # Stable ordering regardless of input list ordering.
    findings.sort(
        key=lambda item: (
            item["requirement_id"],
            item["code"],
            item["id"],
        )
    )

    mandatory_ids = [
        requirement["id"]
        for requirement in requirements
        if requirement.get("mandatory", True)
    ]

    advisory_ids = [
        requirement["id"]
        for requirement in requirements
        if not requirement.get("mandatory", True)
    ]

    # A proven mandatory FALSE outranks every unresolved release condition.
    if any(
        requirement_results[identifier]["applicability"] == "APPLIES"
        and requirement_results[identifier]["truth"] == "FALSE"
        for identifier in mandatory_ids
    ):
        verdict = "FAIL"

    else:
        unknown = False

        if not mandatory_ids:
            unknown = True

        if document.get("revision") != "FINAL":
            unknown = True

        if any(
            scopes.get(scope_id, "OPEN") != "CLOSED"
            for scope_id in document.get("required_scopes", [])
        ):
            unknown = True

        if mandatory_ids and all(
            requirement_results[identifier]["applicability"]
            == "NOT_APPLICABLE"
            for identifier in mandatory_ids
        ):
            unknown = True

        for identifier in mandatory_ids:
            result = requirement_results[identifier]

            if metadata[identifier]["unresolved_dependencies"]:
                unknown = True

            if result["applicability"] == "UNDETERMINED":
                unknown = True

            elif result["applicability"] == "APPLIES":
                if result["truth"] != "TRUE":
                    unknown = True
                if result["coverage"] != "COVERED":
                    unknown = True
                if result["scope"] != "CLOSED":
                    unknown = True

        if unknown:
            verdict = "UNKNOWN"

        elif any(
            requirement_results[identifier]["applicability"] == "APPLIES"
            and (
                requirement_results[identifier]["truth"] != "TRUE"
                or requirement_results[identifier]["coverage"] != "COVERED"
                or requirement_results[identifier]["scope"] != "CLOSED"
            )
            for identifier in advisory_ids
        ):
            verdict = "WARN"

        else:
            verdict = "PASS"

    return {
        "verdict": verdict,
        "requirement_results": requirement_results,
        "findings": findings,
    }
