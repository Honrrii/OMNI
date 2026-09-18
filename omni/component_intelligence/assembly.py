"""Mechanical assembly adapter for OMNI Component Intelligence v0.1."""

from __future__ import annotations

from copy import deepcopy
import json

from .contract import evaluate_contract


TRUSTED_PROVENANCE = {
    "STANDARD",
    "MANUFACTURER",
    "HANDBOOK",
    "OMNI_VALIDATED",
}

SUPPORTED_TYPES = {
    "fastener": {"bolt", "retaining_ring"},
    "shaft": {"round_shaft"},
    "bearing": {"radial_bearing"},
    "coupling": {"rigid_coupling"},
    "transmission": {"spur_gear", "pulley", "belt"},
    "motor": {"rotary_motor"},
    "linear_motion": {
        "leadscrew",
        "nut",
        "carriage",
        "linear_guide",
        "tensioner",
    },
    "structure": {"housing"},
}

PATTERN_EDGES = {
    "supported_shaft": [
        ("support", "supports", "shaft"),
        ("structure", "houses", "support"),
    ],
    "motor_to_shaft": [
        ("motor", "drives", "coupling"),
        ("coupling", "drives", "shaft"),
        ("support", "supports", "shaft"),
        ("structure", "houses", "support"),
        ("shaft", "drives", "load"),
    ],
    "motor_to_leadscrew_stage": [
        ("motor", "drives", "coupling"),
        ("coupling", "drives", "leadscrew"),
        ("support", "supports", "leadscrew"),
        ("leadscrew", "drives", "nut"),
        ("nut", "attached_to", "carriage"),
        ("guide", "guides", "carriage"),
    ],
    "belt_drive": [
        ("motor", "drives", "pulley"),
        ("pulley", "drives", "belt"),
        ("belt", "drives", "driven_pulley"),
        ("driven_pulley", "drives", "shaft"),
        ("support", "supports", "shaft"),
        ("tensioner", "tensions", "belt"),
    ],
    "geared_output": [
        ("motor", "drives", "gear"),
        ("gear", "drives", "shaft"),
        ("support", "supports", "shaft"),
        ("shaft", "drives", "load"),
    ],
}


def _closed(document: dict, scope: str) -> bool:
    return document.get("scopes", {}).get(scope) == "CLOSED"


def _absence_truth(document: dict, scope: str) -> str:
    return "FALSE" if _closed(document, scope) else "UNKNOWN"


def _indexes(document: dict):
    components = {
        item["id"]: item
        for item in document.get("components", [])
        if isinstance(item, dict) and isinstance(item.get("id"), str)
    }
    interfaces = {
        item["id"]: item
        for item in document.get("interfaces", [])
        if isinstance(item, dict) and isinstance(item.get("id"), str)
    }
    patterns = {
        item["id"]: item
        for item in document.get("patterns", [])
        if isinstance(item, dict) and isinstance(item.get("id"), str)
    }

    relationships = [
        item
        for item in document.get("relationships", [])
        if isinstance(item, dict)
    ]

    raw_facts = {}
    fact_owner = {}

    for component_id, component in components.items():
        for fact in component.get("facts", {}).values():
            if not isinstance(fact, dict):
                continue
            identifier = fact.get("id")
            if isinstance(identifier, str):
                raw_facts[identifier] = fact
                fact_owner[identifier] = component_id

    return (
        components,
        interfaces,
        relationships,
        patterns,
        raw_facts,
        fact_owner,
    )


def _project_facts(raw_facts: dict):
    projected = {}
    rejected_trust = set()

    for identifier in sorted(raw_facts):
        item = deepcopy(raw_facts[identifier])
        provenance = item.get("provenance")

        if isinstance(provenance, dict):
            if (
                provenance.get("origin") == "MODEL"
                and provenance.get("category") in TRUSTED_PROVENANCE
            ):
                rejected_trust.add(identifier)

                provenance = deepcopy(provenance)
                provenance["category"] = "OMNI_HEURISTIC"
                item["provenance"] = provenance

                if item.get("value") is None:
                    item["epistemic"] = "UNKNOWN"
                    item["value"] = None
                else:
                    item["epistemic"] = "ASSUMED"

        projected[identifier] = item

    return projected, rejected_trust


def _requirement_provenance(requirement: dict) -> list[dict]:
    provenance = requirement.get("provenance")
    if isinstance(provenance, dict):
        return [deepcopy(provenance)]

    return [{
        "category": "USER_PROVIDED",
        "origin": "HUMAN",
        "source_ref": "component-intelligence:v0.1",
    }]


def _draft_finding(
    requirement: dict,
    code: str,
    *,
    components=(),
    interfaces=(),
    dependencies=(),
    observed=None,
    expected=None,
    state="UNKNOWN",
):
    return {
        "requirement_id": requirement["id"],
        "rule_id": str(requirement.get("rule", "assembly")),
        "code": code,
        "state": state,
        "components": sorted(set(components)),
        "interfaces": sorted(set(interfaces)),
        "dependency_ids": sorted(set(dependencies)),
        "observed": deepcopy(observed or {"state": state}),
        "expected": deepcopy(expected or {"state": "RESOLVED"}),
        "explanation": f"{requirement['id']}: {code}",
        "provenance": _requirement_provenance(requirement),
    }


def _finalize_findings(drafts: list[dict]) -> list[dict]:
    ordered = sorted(
        drafts,
        key=lambda item: (
            item["requirement_id"],
            item["code"],
            tuple(item["components"]),
            tuple(item["interfaces"]),
            json.dumps(item["observed"], sort_keys=True, default=str),
        ),
    )

    counters = {}
    result = []

    for item in ordered:
        key = (item["requirement_id"], item["code"])
        counters[key] = counters.get(key, 0) + 1

        finalized = deepcopy(item)
        finalized["id"] = (
            f"{item['requirement_id']}::{item['code']}"
            f"::assembly::{counters[key]}"
        )
        result.append(finalized)

    return result


def _component_fact(
    components: dict,
    fact_results: dict,
    component_id: str,
    property_name: str,
):
    component = components.get(component_id)
    if not component:
        return None

    raw = component.get("facts", {}).get(property_name)
    if not isinstance(raw, dict):
        return None

    identifier = raw.get("id")
    if not isinstance(identifier, str):
        return None

    return fact_results.get(identifier)


def _parameter_refs(
    requirement: dict,
    components: dict,
    interfaces: dict,
    patterns: dict,
):
    params = requirement.get("parameters", {})
    component_ids = []
    interface_ids = []

    for key in ("component", "shaft", "bearing"):
        value = params.get(key)
        if isinstance(value, str):
            component_ids.append(value)

    interface_id = params.get("interface")
    if isinstance(interface_id, str):
        interface_ids.append(interface_id)
        interface = interfaces.get(interface_id)
        if interface:
            component_ids.extend(interface.get("participants", []))

    pattern_id = params.get("pattern")
    if isinstance(pattern_id, str):
        pattern = patterns.get(pattern_id)
        if pattern:
            component_ids.extend(pattern.get("roles", {}).values())

    return sorted(set(component_ids)), sorted(set(interface_ids))


def _transform_antecedent(expression, fact_results: dict):
    if not isinstance(expression, dict):
        return {"op": "literal", "truth": "UNKNOWN"}

    op = expression.get("op")

    if op == "fact":
        identifier = expression.get("fact_id")
        fact = fact_results.get(identifier)

        if (
            isinstance(fact, dict)
            and fact.get("epistemic") == "KNOWN"
            and type(fact.get("value")) is bool
        ):
            truth = "TRUE" if fact["value"] else "FALSE"
        else:
            truth = "UNKNOWN"

        return {"op": "literal", "truth": truth}

    result = deepcopy(expression)

    if op in {"and", "or"}:
        result["args"] = [
            _transform_antecedent(item, fact_results)
            for item in expression.get("args", [])
        ]

    elif op in {"forall", "exists", "cardinality"}:
        result["items"] = [
            _transform_antecedent(item, fact_results)
            for item in expression.get("items", [])
        ]

    return result


def _relationship_exists(
    relationships: list[dict],
    components: dict,
    source: str,
    kind: str,
    target: str,
) -> bool:
    if source not in components or target not in components:
        return False

    return any(
        item.get("source") == source
        and item.get("kind") == kind
        and item.get("target") == target
        and item.get("source") in components
        and item.get("target") in components
        for item in relationships
    )


def _evaluate_interface_rule(
    requirement: dict,
    document: dict,
    components: dict,
    interfaces: dict,
    fact_results: dict,
    left_role: str,
    right_role: str,
):
    params = requirement.get("parameters", {})
    identifier = params.get("interface")
    interface = interfaces.get(identifier)

    if interface is None:
        return _absence_truth(document, "interfaces"), "COVERED", []

    participants = [
        value for value in interface.get("participants", [])
        if isinstance(value, str)
    ]

    missing_components = [
        value for value in participants if value not in components
    ]

    if missing_components:
        finding = _draft_finding(
            requirement,
            "MISSING_COMPONENT",
            components=missing_components,
            interfaces=[identifier],
            observed={"missing_components": missing_components},
            expected={"components": "PRESENT"},
            state=_absence_truth(document, "components"),
        )
        return _absence_truth(document, "components"), "COVERED", [finding]

    dimensions = interface.get("dimensions", {})
    left_id = dimensions.get(left_role)
    right_id = dimensions.get(right_role)

    for fact_id in (left_id, right_id):
        fact = fact_results.get(fact_id)

        if not isinstance(fact, dict):
            finding = _draft_finding(
                requirement,
                "MISSING_FACT",
                components=participants,
                interfaces=[identifier],
                observed={"missing_fact": fact_id or "unspecified"},
                expected={"epistemic": "KNOWN"},
            )
            return "UNKNOWN", "COVERED", [finding]

        if fact.get("epistemic") != "KNOWN":
            code = (
                "ASSUMED_FACT"
                if fact.get("epistemic") == "ASSUMED"
                else "MISSING_FACT"
            )
            finding = _draft_finding(
                requirement,
                code,
                components=participants,
                interfaces=[identifier],
                observed={fact_id: deepcopy(fact)},
                expected={"epistemic": "KNOWN"},
            )
            return "UNKNOWN", "COVERED", [finding]

    left = fact_results[left_id]
    right = fact_results[right_id]

    if left.get("value") == right.get("value"):
        return "TRUE", "COVERED", []

    finding = _draft_finding(
        requirement,
        "DIMENSION_MISMATCH",
        components=participants,
        interfaces=[identifier],
        observed={
            left_id: deepcopy(left),
            right_id: deepcopy(right),
        },
        expected={"nominal_dimensions": "EQUAL"},
        state="FALSE",
    )
    return "FALSE", "COVERED", [finding]


def _evaluate_pattern(
    requirement: dict,
    document: dict,
    components: dict,
    relationships: list[dict],
    patterns: dict,
):
    pattern_id = requirement.get("parameters", {}).get("pattern")
    pattern = patterns.get(pattern_id)

    if pattern is None:
        truth = (
            "FALSE"
            if _closed(document, "components")
            and _closed(document, "relationships")
            else "UNKNOWN"
        )
        return truth, "COVERED", []

    kind = pattern.get("kind")
    roles = pattern.get("roles", {})

    edge_spec = list(PATTERN_EDGES.get(kind, []))

    if kind == "supported_shaft" and "retainer" in roles:
        edge_spec.append(("retainer", "retains", "shaft"))

    if kind not in PATTERN_EDGES:
        finding = _draft_finding(
            requirement,
            "UNCOVERED_RULE",
            observed={"pattern_kind": kind},
            expected={"pattern_kind": "REGISTERED"},
        )
        return "UNKNOWN", "UNCOVERED", [finding]

    for source_role, verb, target_role in edge_spec:
        source = roles.get(source_role)
        target = roles.get(target_role)

        missing = []

        if not isinstance(source, str) or source not in components:
            if isinstance(source, str):
                missing.append(source)
            else:
                missing.append(source_role)

        if not isinstance(target, str) or target not in components:
            if isinstance(target, str):
                missing.append(target)
            else:
                missing.append(target_role)

        if missing:
            truth = _absence_truth(document, "components")
            finding = _draft_finding(
                requirement,
                "MISSING_COMPONENT",
                components=missing,
                observed={"missing_components": missing},
                expected={"components": "PRESENT"},
                state=truth,
            )
            return truth, "COVERED", [finding]

        if not _relationship_exists(
            relationships,
            components,
            source,
            verb,
            target,
        ):
            truth = _absence_truth(document, "relationships")
            finding = _draft_finding(
                requirement,
                "MISSING_RELATIONSHIP",
                components=[target],
                observed={
                    "source": source,
                    "kind": verb,
                    "target": target,
                },
                expected={"relationship": "PRESENT"},
                state=truth,
            )
            return truth, "COVERED", [finding]

    return "TRUE", "COVERED", []


def _evaluate_rule(
    requirement: dict,
    document: dict,
    components: dict,
    interfaces: dict,
    relationships: list[dict],
    patterns: dict,
    fact_results: dict,
    raw_facts: dict,
    rejected_trust: set[str],
):
    rule = requirement.get("rule")
    params = requirement.get("parameters", {})

    if rule == "shaft_bearing_bore":
        return _evaluate_interface_rule(
            requirement,
            document,
            components,
            interfaces,
            fact_results,
            "shaft_diameter",
            "bearing_bore",
        )

    if rule == "shaft_coupling_bore":
        return _evaluate_interface_rule(
            requirement,
            document,
            components,
            interfaces,
            fact_results,
            "shaft_diameter",
            "coupling_bore",
        )

    if rule in {"shaft_support", "shaft_retention"}:
        shaft = params.get("shaft")

        if shaft not in components:
            truth = _absence_truth(document, "components")
            finding = _draft_finding(
                requirement,
                "MISSING_COMPONENT",
                components=[shaft] if isinstance(shaft, str) else [],
                observed={"missing_component": shaft},
                expected={"component": "PRESENT"},
                state=truth,
            )
            return truth, "COVERED", [finding]

        verb = "supports" if rule == "shaft_support" else "retains"

        found = any(
            item.get("kind") == verb
            and item.get("target") == shaft
            and item.get("source") in components
            for item in relationships
        )

        if found:
            return "TRUE", "COVERED", []

        truth = _absence_truth(document, "relationships")
        finding = _draft_finding(
            requirement,
            "MISSING_RELATIONSHIP",
            components=[shaft],
            observed={"kind": verb, "target": shaft},
            expected={"relationship": "PRESENT"},
            state=truth,
        )
        return truth, "COVERED", [finding]

    if rule == "bearing_speed":
        shaft_id = params.get("shaft")
        bearing_id = params.get("bearing")

        shaft = components.get(shaft_id)
        bearing = components.get(bearing_id)

        if shaft is None or bearing is None:
            missing = [
                identifier
                for identifier, item in (
                    (shaft_id, shaft),
                    (bearing_id, bearing),
                )
                if item is None and isinstance(identifier, str)
            ]
            finding = _draft_finding(
                requirement,
                "MISSING_FACT",
                components=missing,
                observed={"missing_components": missing},
                expected={"speed_evidence": "KNOWN"},
            )
            return "UNKNOWN", "COVERED", [finding]

        speed = _component_fact(
            components,
            fact_results,
            shaft_id,
            "speed",
        )
        rating = _component_fact(
            components,
            fact_results,
            bearing_id,
            "speed_rating",
        )

        for fact, component_id, property_name in (
            (speed, shaft_id, "speed"),
            (rating, bearing_id, "speed_rating"),
        ):
            if fact is None:
                finding = _draft_finding(
                    requirement,
                    "MISSING_FACT",
                    components=[component_id],
                    observed={"missing_fact": property_name},
                    expected={"epistemic": "KNOWN"},
                )
                return "UNKNOWN", "COVERED", [finding]

            fact_id = fact["id"]

            if fact_id in rejected_trust:
                raw = raw_facts[fact_id]
                finding = _draft_finding(
                    requirement,
                    "UNTRUSTED_PROVENANCE",
                    components=[component_id],
                    observed={fact_id: deepcopy(raw)},
                    expected={"provenance": "ADMISSIBLE"},
                )
                return "UNKNOWN", "COVERED", [finding]

            if fact.get("epistemic") != "KNOWN":
                code = (
                    "ASSUMED_FACT"
                    if fact.get("epistemic") == "ASSUMED"
                    else "MISSING_FACT"
                )
                finding = _draft_finding(
                    requirement,
                    code,
                    components=[component_id],
                    observed={fact_id: deepcopy(fact)},
                    expected={"epistemic": "KNOWN"},
                )
                return "UNKNOWN", "COVERED", [finding]

        return (
            ("TRUE", "COVERED", [])
            if speed["value"] <= rating["value"]
            else ("FALSE", "COVERED", [])
        )

    if rule == "component_type":
        component_id = params.get("component")
        component = components.get(component_id)

        if component is None:
            truth = _absence_truth(document, "components")
            finding = _draft_finding(
                requirement,
                "MISSING_COMPONENT",
                components=[component_id]
                if isinstance(component_id, str)
                else [],
                observed={"missing_component": component_id},
                expected={"component": "PRESENT"},
                state=truth,
            )
            return truth, "COVERED", [finding]

        family = component.get("family")
        subtype = component.get("subtype")

        if subtype in SUPPORTED_TYPES.get(family, set()):
            return "TRUE", "COVERED", []

        finding = _draft_finding(
            requirement,
            "UNKNOWN_COMPONENT_TYPE",
            components=[component_id],
            observed={"family": family, "subtype": subtype},
            expected={"type": "REGISTERED"},
        )
        return "UNKNOWN", "UNCOVERED", [finding]

    if rule == "component_exists":
        family = params.get("family")
        minimum = params.get("minimum", 1)

        count = sum(
            component.get("family") == family
            for component in components.values()
        )

        if count >= minimum:
            return "TRUE", "COVERED", []

        truth = _absence_truth(document, "components")
        finding = _draft_finding(
            requirement,
            "MISSING_COMPONENT",
            observed={
                "family": family,
                "observed_count": count,
            },
            expected={
                "minimum": minimum,
            },
            state=truth,
        )
        return truth, "COVERED", [finding]

    if rule == "pattern":
        return _evaluate_pattern(
            requirement,
            document,
            components,
            relationships,
            patterns,
        )

    component_refs, interface_refs = _parameter_refs(
        requirement,
        components,
        interfaces,
        patterns,
    )

    finding = _draft_finding(
        requirement,
        "UNCOVERED_RULE",
        components=component_refs,
        interfaces=interface_refs,
        observed={"rule": rule},
        expected={"rule": "REGISTERED"},
    )
    return "UNKNOWN", "UNCOVERED", [finding]


def _apply_coverage(
    requirement: dict,
    truth: str,
    coverage: str,
):
    declared = requirement.get("coverage", "COVERED")

    if declared == "UNCOVERED":
        return "UNKNOWN", "UNCOVERED"

    if declared == "UNKNOWN":
        return "UNKNOWN", "UNKNOWN"

    if coverage != "COVERED":
        return "UNKNOWN", coverage

    return truth, coverage


def _cad_provenance(
    request: dict,
    requirements: dict,
    fact_results: dict,
):
    items = []

    if isinstance(request.get("provenance"), dict):
        items.append(deepcopy(request["provenance"]))

    for identifier in request.get("prerequisites", []):
        requirement = requirements.get(identifier)
        if requirement and isinstance(requirement.get("provenance"), dict):
            items.append(deepcopy(requirement["provenance"]))

    for fact_id in request.get("dimension_inputs", {}).values():
        fact = fact_results.get(fact_id)
        if fact and isinstance(fact.get("provenance"), dict):
            items.append(deepcopy(fact["provenance"]))

    unique = {}
    for item in items:
        unique[json.dumps(item, sort_keys=True)] = item

    return [unique[key] for key in sorted(unique)]


def _cad_obligations(
    document: dict,
    result: dict,
    fact_results: dict,
):
    requirements = {
        item["id"]: item
        for item in document.get("requirements", [])
        if isinstance(item, dict) and isinstance(item.get("id"), str)
    }

    obligations = []

    for request in sorted(
        document.get("cad_requests", []),
        key=lambda item: item.get("id", ""),
    ):
        unresolved = set()
        known_dimensions = {}

        if document.get("revision") != "FINAL":
            unresolved.add("revision")

        for scope_id in document.get("required_scopes", []):
            if document.get("scopes", {}).get(scope_id) != "CLOSED":
                unresolved.add(f"scope:{scope_id}")

        for requirement_id in request.get("prerequisites", []):
            requirement_result = result["requirement_results"].get(
                requirement_id
            )

            if not requirement_result:
                unresolved.add(requirement_id)
                continue

            if not (
                requirement_result["applicability"] == "APPLIES"
                and requirement_result["truth"] == "TRUE"
                and requirement_result["coverage"] == "COVERED"
                and requirement_result["scope"] == "CLOSED"
            ):
                unresolved.add(requirement_id)

        for role, fact_id in request.get(
            "dimension_inputs",
            {},
        ).items():
            fact = fact_results.get(fact_id)

            if (
                isinstance(fact, dict)
                and fact.get("epistemic") == "KNOWN"
            ):
                known_dimensions[role] = {
                    "value": fact.get("value"),
                    "units": fact.get("units"),
                    "fact_id": fact_id,
                }
            else:
                unresolved.add(fact_id)

        prerequisites = request.get("prerequisites", [])

        source_rules = [
            requirements[identifier]["rule"]
            for identifier in prerequisites
            if identifier in requirements
        ]

        obligations.append({
            "id": request["id"],
            "target": request["target"],
            "feature": request["feature"],
            "status": "RELEASED" if not unresolved else "BLOCKED",
            "known_dimensions": known_dimensions,
            "unresolved_inputs": sorted(unresolved),
            "provenance": _cad_provenance(
                request,
                requirements,
                fact_results,
            ),
            "source_requirements": list(prerequisites),
            "source_rules": source_rules,
        })

    return obligations


def evaluate_assembly(document: dict) -> dict:
    (
        components,
        interfaces,
        relationships,
        patterns,
        raw_facts,
        fact_owner,
    ) = _indexes(document)

    fact_results, rejected_trust = _project_facts(raw_facts)

    logical_requirements = []
    specific_findings = []

    for requirement in document.get("requirements", []):
        truth, coverage, rule_findings = _evaluate_rule(
            requirement,
            document,
            components,
            interfaces,
            relationships,
            patterns,
            fact_results,
            raw_facts,
            rejected_trust,
        )

        declared_coverage = requirement.get(
            "coverage",
            "COVERED",
        )

        if declared_coverage == "COVERED":
            specific_findings.extend(rule_findings)

        elif declared_coverage == "UNCOVERED":
            component_refs, interface_refs = _parameter_refs(
                requirement,
                components,
                interfaces,
                patterns,
            )
            specific_findings.append(
                _draft_finding(
                    requirement,
                    "UNCOVERED_RULE",
                    components=component_refs,
                    interfaces=interface_refs,
                    observed={
                        "coverage": declared_coverage,
                        "rule": requirement.get("rule"),
                    },
                    expected={"coverage": "COVERED"},
                )
            )

        truth, coverage = _apply_coverage(
            requirement,
            truth,
            coverage,
        )

        antecedent = _transform_antecedent(
            requirement.get(
                "antecedent",
                {"op": "literal", "truth": "TRUE"},
            ),
            fact_results,
        )

        per_completion = {
            item["id"]: {
                "truth": truth,
                "coverage": coverage,
            }
            for item in document.get("completions", [])
        }

        logical_requirements.append({
            "id": requirement["id"],
            "mandatory": requirement.get("mandatory", True),
            "antecedent": antecedent,
            "predicate": {
                "op": "observation",
                "dependency_ids": [],
                "by_completion": per_completion,
            },
            "required_scopes": list(
                requirement.get("required_scopes", [])
            ),
            "dependency_ids": list(
                requirement.get("dependency_ids", [])
            ),
            "provenance": deepcopy(
                requirement.get("provenance")
            ),
        })

    logical_document = {
        "revision": document.get("revision"),
        "revision_id": document.get("revision_id"),
        "scopes": deepcopy(document.get("scopes", {})),
        "required_scopes": list(
            document.get("required_scopes", [])
        ),
        "dependencies": deepcopy(
            document.get("dependencies", [])
        ),
        "completions": deepcopy(
            document.get("completions", [])
        ),
        "requirements": logical_requirements,
    }

    result = evaluate_contract(logical_document)

    requirements_by_id = {
        item["id"]: item
        for item in document.get("requirements", [])
    }

    for identifier, requirement_result in result[
        "requirement_results"
    ].items():
        requirement = requirements_by_id[identifier]

        if requirement_result["scope"] == "OPEN":
            component_refs, interface_refs = _parameter_refs(
                requirement,
                components,
                interfaces,
                patterns,
            )

            open_scopes = sorted(
                scope_id
                for scope_id in requirement.get(
                    "required_scopes",
                    [],
                )
                if document.get("scopes", {}).get(
                    scope_id
                ) != "CLOSED"
            )

            specific_findings.append(
                _draft_finding(
                    requirement,
                    "OPEN_SCOPE",
                    components=component_refs,
                    interfaces=interface_refs,
                    observed={"open_scopes": open_scopes},
                    expected={"required_scopes": "CLOSED"},
                    state="OPEN",
                )
            )

        original_antecedent = requirement.get(
            "antecedent",
            {"op": "literal", "truth": "TRUE"},
        )

        if original_antecedent.get("op") == "fact":
            fact_id = original_antecedent.get("fact_id")
            fact = fact_results.get(fact_id)
            owner = fact_owner.get(fact_id)

            component_refs, _ = _parameter_refs(
                requirement,
                components,
                interfaces,
                patterns,
            )
            affected_components = (
                [owner] if owner else component_refs
            )

            if (
                requirement_result["applicability"]
                == "NOT_APPLICABLE"
            ):
                observed = (
                    {fact_id: deepcopy(fact)}
                    if fact is not None
                    else {"missing_fact": fact_id}
                )

                specific_findings.append(
                    _draft_finding(
                        requirement,
                        "NOT_APPLICABLE",
                        components=affected_components,
                        observed=observed,
                        expected={"applicability": "APPLIES"},
                        state="NOT_APPLICABLE",
                    )
                )

            elif (
                requirement_result["applicability"]
                == "UNDETERMINED"
            ):
                observed = (
                    {fact_id: deepcopy(fact)}
                    if fact is not None
                    else {"missing_fact": fact_id}
                )

                specific_findings.append(
                    _draft_finding(
                        requirement,
                        "UNDETERMINED_APPLICABILITY",
                        components=affected_components,
                        observed=observed,
                        expected={"applicability": "APPLIES"},
                        state="UNDETERMINED",
                    )
                )

    result["findings"] = sorted(
        result["findings"]
        + _finalize_findings(specific_findings),
        key=lambda item: (
            item["requirement_id"],
            item["code"],
            item["id"],
        ),
    )

    result["fact_results"] = fact_results
    result["cad_obligations"] = _cad_obligations(
        document,
        result,
        fact_results,
    )

    return result
