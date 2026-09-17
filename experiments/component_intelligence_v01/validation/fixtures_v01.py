"""Human-owned inputs and explicit expectations, never a candidate evaluator.

Fixture names/scenario numbers/expectations are NOT passed to the candidate.
All copies are in memory. No discovery, randomness, filesystem or network I/O.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field


@dataclass
class Case:
    name: str
    api: str
    document: dict
    verdict: str
    results: dict
    scenarios: tuple[int, ...] = ()
    findings: list[dict] = field(default_factory=list)
    cad: dict = field(default_factory=dict)
    # Only model-origin facts differ from their input projection.
    fact_overrides: dict = field(default_factory=dict)


def provenance(category="USER_PROVIDED", origin="HUMAN"):
    return {"category": category, "origin": origin, "source_ref": "validation:generic-v01"}


def fact(identifier, value, units="mm", state="KNOWN", category="USER_PROVIDED", origin="HUMAN"):
    return dict(id=identifier, value=value, units=units, epistemic=state,
                provenance=provenance(category, origin))


def literal(value="TRUE"):
    return {"op": "literal", "truth": value}


def observation(values, dependency_ids=()):
    return {"op": "observation", "dependency_ids": list(dependency_ids),
            "by_completion": {key: {"truth": truth, "coverage": coverage}
                              for key, (truth, coverage) in values.items()}}


def expected(truth="TRUE", coverage="COVERED", scope="CLOSED", applicability="APPLIES",
             completions=None, dependency_ids=()):
    return dict(applicability=applicability, truth=truth, coverage=coverage, scope=scope,
                dependency_ids=list(dependency_ids), completion_results=completions or {
                    "base": dict(applicability=applicability, truth=truth, coverage=coverage)})


def requirement(identifier="required", predicate=None, mandatory=True, antecedent=None,
                scopes=("relationships",), dependency_ids=()):
    return dict(id=identifier, mandatory=mandatory, antecedent=antecedent or literal(),
                predicate=predicate or literal(), required_scopes=list(scopes),
                dependency_ids=list(dependency_ids), provenance=provenance())


def contract(*requirements):
    return dict(revision="FINAL", revision_id="fixed-revision-not-a-scope-proof",
                scopes={"requirements": "CLOSED", "relationships": "CLOSED"},
                required_scopes=["requirements", "relationships"], dependencies=[],
                completions=[dict(id="base", choices={})], requirements=list(requirements))


def finding(requirement_id, code, components=(), interfaces=(), dependencies=(), observed=None):
    result = dict(requirement_id=requirement_id, code=code, components=list(components),
                  interfaces=list(interfaces), dependency_ids=list(dependencies))
    if observed is not None:
        result["observed"] = observed
    return result


def logical_cases():
    cases = []
    # Exhaustive top-level truth/coverage matrix, with independently fixed truth.
    for truth in ("TRUE", "FALSE", "UNKNOWN"):
        for coverage in ("COVERED", "UNCOVERED", "UNKNOWN"):
            pred = observation({"base": (truth, coverage)})
            verdict = "FAIL" if truth == "FALSE" else "PASS" if truth == "TRUE" and coverage == "COVERED" else "UNKNOWN"
            cases.append(Case(f"mandatory-{truth}-{coverage}", "evaluate_contract",
                contract(requirement(predicate=pred)), verdict, {"required": expected(truth, coverage)}))
    base = contract(requirement())
    for state in ("FALSE", "UNKNOWN"):
        doc = contract(requirement(), requirement("advice", literal(state), mandatory=False))
        cases.append(Case(f"advisory-{state}", "evaluate_contract", doc, "WARN",
                          {"required": expected(), "advice": expected(state)}))
    cases.append(Case("advisory-covered-true", "evaluate_contract",
        contract(requirement(), requirement("advice", mandatory=False)), "PASS",
        {"required": expected(), "advice": expected()}))
    doc = contract(requirement("advice", mandatory=False))
    cases.append(Case("no-mandatory-contract", "evaluate_contract", doc, "UNKNOWN", {"advice": expected()}))
    cases.append(Case("empty-contract", "evaluate_contract", contract(), "UNKNOWN", {}))
    doc = deepcopy(base)
    doc["revision"] = "INTERMEDIATE"
    cases.append(Case("intermediate-valid", "evaluate_contract", doc, "UNKNOWN", {"required": expected()}))
    doc = deepcopy(base)
    doc["scopes"]["relationships"] = "OPEN"
    cases.append(Case("open-no-defect", "evaluate_contract", doc, "UNKNOWN",
                      {"required": expected(scope="OPEN")}, (12,),
                      [finding("required", "OPEN_SCOPE")]))
    # FALSE has priority over every unresolved release condition and advice.
    doc = contract(requirement(predicate=literal("FALSE")), requirement("unresolved", literal("UNKNOWN")))
    doc["revision"] = "INTERMEDIATE"
    doc["scopes"]["relationships"] = "OPEN"
    cases.append(Case("false-precedes-unknown-open-intermediate", "evaluate_contract", doc, "FAIL",
                      {"required": expected("FALSE", scope="OPEN"),
                       "unresolved": expected("UNKNOWN", scope="OPEN")}))
    for antecedent, app in (("FALSE", "NOT_APPLICABLE"), ("UNKNOWN", "UNDETERMINED")):
        req = requirement("conditional", literal("FALSE"), antecedent=literal(antecedent))
        doc = contract(requirement(), req)
        value = expected("UNKNOWN", applicability=app)
        cases.append(Case(f"applicability-{antecedent}", "evaluate_contract", doc,
                          "PASS" if antecedent == "FALSE" else "UNKNOWN",
                          {"required": expected(), "conditional": value},
                          findings=[finding("conditional", "NOT_APPLICABLE" if antecedent == "FALSE" else "UNDETERMINED_APPLICABILITY")]))
    excluded = requirement(antecedent=literal("FALSE"))
    cases.append(Case("mandatory-entirely-excluded", "evaluate_contract", contract(excluded), "UNKNOWN",
                      {"required": expected("UNKNOWN", applicability="NOT_APPLICABLE")}))
    # Strong three-valued conjunction/disjunction. Coverage is independent data.
    table = [("TRUE", "TRUE", "TRUE", "TRUE"), ("TRUE", "FALSE", "FALSE", "TRUE"),
             ("TRUE", "UNKNOWN", "UNKNOWN", "TRUE"), ("FALSE", "FALSE", "FALSE", "FALSE"),
             ("FALSE", "UNKNOWN", "FALSE", "UNKNOWN"), ("UNKNOWN", "UNKNOWN", "UNKNOWN", "UNKNOWN")]
    for left, right, conjunction, disjunction in table:
        for op, truth in (("and", conjunction), ("or", disjunction)):
            pred = dict(op=op, args=[literal(left), literal(right)])
            verdict = {"TRUE": "PASS", "FALSE": "FAIL", "UNKNOWN": "UNKNOWN"}[truth]
            cases.append(Case(f"{op}-{left}-{right}", "evaluate_contract", contract(requirement(predicate=pred)),
                              verdict, {"required": expected(truth)}))
    doc = contract(requirement(predicate=dict(op="or", args=[literal("FALSE"), literal("TRUE")])))
    cases.append(Case("alternative-B-valid", "evaluate_contract", doc, "PASS", {"required": expected()}, (6,)))
    # Quantifier/cardinality expectations are literal tables, not a reference solver.
    rows = [
        ("forall", [], "CLOSED", None, None, "TRUE"),
        ("exists", [], "CLOSED", None, None, "FALSE"),
        ("forall", [], "OPEN", None, None, "UNKNOWN"),
        ("exists", [], "OPEN", None, None, "UNKNOWN"),
        ("forall", ["TRUE"], "OPEN", None, None, "UNKNOWN"),
        ("forall", ["FALSE"], "OPEN", None, None, "FALSE"),
        ("exists", ["TRUE"], "OPEN", None, None, "TRUE"),
        ("exists", ["FALSE", "TRUE"], "CLOSED", None, None, "TRUE"),
        ("forall", ["TRUE", "UNKNOWN"], "CLOSED", None, None, "UNKNOWN"),
        ("cardinality", [], "CLOSED", 0, 1, "TRUE"),
        ("cardinality", [], "CLOSED", 1, 1, "FALSE"),
        ("cardinality", ["TRUE", "FALSE"], "CLOSED", 1, 1, "TRUE"),
        ("cardinality", ["TRUE", "TRUE"], "CLOSED", 1, 1, "FALSE"),
        ("cardinality", ["TRUE", "UNKNOWN"], "CLOSED", 1, 1, "UNKNOWN"),
        ("cardinality", ["TRUE", "UNKNOWN"], "CLOSED", 1, 3, "TRUE"),
        ("cardinality", ["FALSE", "FALSE", "TRUE"], "CLOSED", 1, None, "TRUE"),
        ("cardinality", ["TRUE"], "OPEN", 1, 1, "UNKNOWN"),
    ]
    for index, (op, items, scope, minimum, maximum, truth) in enumerate(rows):
        pred = dict(op=op, scope="relationships", items=[literal(item) for item in items])
        if op == "cardinality":
            pred.update(min=minimum, max=maximum)
        doc = contract(requirement(predicate=pred))
        doc["scopes"]["relationships"] = scope
        verdict = "FAIL" if truth == "FALSE" else "UNKNOWN" if truth == "UNKNOWN" or scope == "OPEN" else "PASS"
        scenarios = (13,) if index == 1 else (9,) if index == 9 else ()
        cases.append(Case(f"quantifier-{index:02d}-{op}", "evaluate_contract", doc, verdict,
                          {"required": expected(truth, scope=scope)}, scenarios))
    universal = requirement("all-supports-valid", dict(op="forall", scope="relationships", items=[]))
    existence = requirement("support-exists", dict(op="exists", scope="relationships", items=[]))
    cases.append(Case("vacuity-not-existence", "evaluate_contract", contract(universal, existence), "FAIL",
                      {"all-supports-valid": expected(), "support-exists": expected("FALSE")}, (14,)))
    # One JOINT choice, two members. Never generate A/B member cross-products.
    dep = dict(id="classification", kind="JOINT", members=["type", "rule"], options=[
        dict(id="A", values={"type": "A", "rule": "rule-A"}),
        dict(id="B", values={"type": "B", "rule": "rule-B"})])
    completions = [dict(id="case-A", choices={"classification": "A"}),
                   dict(id="case-B", choices={"classification": "B"})]
    left = observation({"case-A": ("TRUE", "COVERED"), "case-B": ("FALSE", "COVERED")}, ["classification"])
    right = observation({"case-A": ("FALSE", "COVERED"), "case-B": ("TRUE", "COVERED")}, ["classification"])
    def correlated(reqs):
        doc = contract(*reqs)
        doc.update(dependencies=[deepcopy(dep)], completions=deepcopy(completions))
        return doc
    def per(a, b, coverage="COVERED"):
        return {key: dict(applicability="APPLIES", truth=value, coverage=coverage)
                for key, value in (("case-A", a), ("case-B", b))}
    combined = requirement("joint-alternatives", dict(op="or", args=[left, right]), dependency_ids=["classification"])
    other = requirement("same-choice-again", dict(op="or", args=[right, left]), dependency_ids=["classification"])
    result = expected(completions=per("TRUE", "TRUE"), dependency_ids=["classification"])
    cases.append(Case("joint-domain-no-cartesian-expansion", "evaluate_contract", correlated([combined, other]),
        "PASS", {"joint-alternatives": result, "same-choice-again": deepcopy(result)}, (11,)))
    separate = [requirement("left", left, dependency_ids=["classification"]),
                requirement("right", right, dependency_ids=["classification"])]
    cases.append(Case("shared-dependency-mixed-requirements", "evaluate_contract", correlated(separate), "UNKNOWN",
        {"left": expected("UNKNOWN", completions=per("TRUE", "FALSE"), dependency_ids=["classification"]),
         "right": expected("UNKNOWN", completions=per("FALSE", "TRUE"), dependency_ids=["classification"])}, (11,)))
    combined_false = requirement(predicate=dict(op="and", args=[left, right]), dependency_ids=["classification"])
    cases.append(Case("joint-conjunction-disproven", "evaluate_contract", correlated([combined_false]), "FAIL",
        {"required": expected("FALSE", completions=per("FALSE", "FALSE"), dependency_ids=["classification"])}))
    crossed_left = observation({"case-A": ("TRUE", "UNCOVERED"), "case-B": ("FALSE", "COVERED")}, ["classification"])
    crossed_right = observation({"case-A": ("FALSE", "COVERED"), "case-B": ("TRUE", "UNCOVERED")}, ["classification"])
    crossed = requirement(predicate=dict(op="or", args=[crossed_left, crossed_right]), dependency_ids=["classification"])
    cases.append(Case("crossed-truth-coverage", "evaluate_contract", correlated([crossed]), "UNKNOWN",
        {"required": expected(coverage="UNCOVERED", completions=per("TRUE", "TRUE", "UNCOVERED"), dependency_ids=["classification"])},
        (17,), [finding("required", "UNCOVERED_RULE", dependencies=["classification"])]))
    mixed_cov = observation({"case-A": ("TRUE", "COVERED"), "case-B": ("TRUE", "UNCOVERED")}, ["classification"])
    cases.append(Case("finite-coverage-disagrees", "evaluate_contract",
        correlated([requirement(predicate=mixed_cov, dependency_ids=["classification"])]), "UNKNOWN",
        {"required": expected(coverage="UNKNOWN", completions={
            "case-A": dict(applicability="APPLIES", truth="TRUE", coverage="COVERED"),
            "case-B": dict(applicability="APPLIES", truth="TRUE", coverage="UNCOVERED")}, dependency_ids=["classification"])}))
    for kind in ("FINITE", "UNBOUNDED"):
        doc = contract(requirement(dependency_ids=["unresolved"]))
        doc["dependencies"] = [dict(id="unresolved", kind=kind, members=["choice"], options=[])]
        cases.append(Case(f"unresolved-{kind.lower()}", "evaluate_contract", doc, "UNKNOWN",
            {"required": expected("UNKNOWN", dependency_ids=["unresolved"])},
            findings=[finding("required", "UNRESOLVED_DEPENDENCY", dependencies=["unresolved"])]))
    doc = correlated([requirement(predicate=left, dependency_ids=["classification"])])
    doc["dependencies"][0].update(kind="FINITE", members=["type"], options=[
        dict(id="A", values={"type": "A"}), dict(id="B", values={"type": "B"})])
    cases.append(Case("finite-domain-disagreement", "evaluate_contract", doc, "UNKNOWN",
        {"required": expected("UNKNOWN", completions=per("TRUE", "FALSE"), dependency_ids=["classification"])}))
    # NOT_APPLICABLE needs a false antecedent in EVERY admissible completion.
    doc = correlated([requirement("conditional", antecedent=left)])
    doc["requirements"][0]["dependency_ids"] = ["classification"]
    cases.append(Case("conditional-mixed-completions", "evaluate_contract", doc, "UNKNOWN",
        {"conditional": expected("UNKNOWN", applicability="UNDETERMINED", dependency_ids=["classification"], completions={
            "case-A": dict(applicability="APPLIES", truth="TRUE", coverage="COVERED"),
            "case-B": dict(applicability="NOT_APPLICABLE", truth="UNKNOWN", coverage="COVERED")})}))
    return cases


def component(identifier, family, subtype, facts=None):
    return dict(id=identifier, family=family, subtype=subtype, facts=facts or {}, provenance=provenance())


def relationship(identifier, kind, source, target, interface=None):
    return dict(id=identifier, kind=kind, source=source, target=target, interface=interface, provenance=provenance())


def mechanical_requirement(identifier, rule, parameters, scopes=("components", "interfaces", "relationships", "rules"), mandatory=True):
    return dict(id=identifier, rule=rule, parameters=parameters, mandatory=mandatory,
                antecedent=literal(), required_scopes=list(scopes), dependency_ids=[],
                coverage="COVERED", provenance=provenance())


def assembly():
    components = [component("shaft", "shaft", "round_shaft", {"diameter": fact("shaft-diameter", 10),
                  "speed": fact("shaft-speed", 100, "rpm"), "rotating": fact("shaft-rotating", True, None)}),
        component("bearing", "bearing", "radial_bearing", {"bore": fact("bearing-bore", 10),
                  "speed_rating": fact("bearing-rating", 200, "rpm")}),
        component("housing", "structure", "housing"), component("retainer", "fastener", "retaining_ring"),
        component("motor", "motor", "rotary_motor"),
        component("coupling", "coupling", "rigid_coupling", {"bore": fact("coupling-bore", 10)}),
        component("load", "transmission", "spur_gear")]
    interfaces = [dict(id="seat", kind="shaft_to_bearing", participants=["shaft", "bearing"],
                       dimensions={"shaft_diameter": "shaft-diameter", "bearing_bore": "bearing-bore"}, provenance=provenance()),
                  dict(id="coupled", kind="shaft_to_coupling", participants=["shaft", "coupling"],
                       dimensions={"shaft_diameter": "shaft-diameter", "coupling_bore": "coupling-bore"}, provenance=provenance())]
    relationships = [relationship("support", "supports", "bearing", "shaft", "seat"),
        relationship("mount", "houses", "housing", "bearing"), relationship("retention", "retains", "retainer", "shaft"),
        relationship("drive-in", "drives", "motor", "coupling"), relationship("drive-out", "drives", "coupling", "shaft", "coupled"),
        relationship("load-link", "drives", "shaft", "load")]
    patterns = [dict(id="supported", kind="supported_shaft", roles=dict(shaft="shaft", support="bearing",
                    structure="housing", retainer="retainer"), provenance=provenance()),
                dict(id="drive", kind="motor_to_shaft", roles=dict(motor="motor", coupling="coupling", shaft="shaft",
                    support="bearing", structure="housing", load="load"), provenance=provenance())]
    reqs = [mechanical_requirement("bore", "shaft_bearing_bore", {"interface": "seat"}),
            mechanical_requirement("coupling-fit", "shaft_coupling_bore", {"interface": "coupled"}),
            mechanical_requirement("support-required", "shaft_support", {"shaft": "shaft"}),
            mechanical_requirement("retention-required", "shaft_retention", {"shaft": "shaft"}),
            mechanical_requirement("speed", "bearing_speed", {"shaft": "shaft", "bearing": "bearing"}),
            mechanical_requirement("drive-required", "pattern", {"pattern": "drive"}),
            mechanical_requirement("supported-required", "pattern", {"pattern": "supported"}),
            mechanical_requirement("type-known", "component_type", {"component": "shaft"})]
    return dict(revision="FINAL", revision_id="immutable-but-not-complete", components=components,
        interfaces=interfaces, relationships=relationships, patterns=patterns, requirements=reqs,
        scopes={key: "CLOSED" for key in ("components", "interfaces", "relationships", "requirements", "rules")},
        required_scopes=["components", "interfaces", "relationships", "requirements", "rules"],
        dependencies=[], completions=[dict(id="base", choices={})],
        cad_requests=[dict(id="seat-feature", target="shaft", feature="bearing_seat",
            dimension_inputs={"diameter": "shaft-diameter"}, prerequisites=["bore", "support-required"],
            provenance=provenance())])


def by_id(items, identifier):
    return next(item for item in items if item["id"] == identifier)


def assembly_case(name, doc, verdict="PASS", changes=None, scenarios=(), findings=(), cad_status="RELEASED", unresolved=()):
    results = {req["id"]: expected() for req in doc["requirements"]}
    results.update(changes or {})
    known = {"diameter": dict(value=10, units="mm", fact_id="shaft-diameter")}
    return Case(name, "evaluate_assembly", doc, verdict, results, scenarios, list(findings),
        {"seat-feature": dict(status=cad_status, known_dimensions=known, unresolved_inputs=list(unresolved))})


def assembly_cases():
    cases = [assembly_case("fully-valid-final", assembly(), scenarios=(16,))]
    doc = assembly()
    doc.update(components=[], interfaces=[], relationships=[])
    # Keep human requirements AND patterns: absence cannot erase either.
    changes = {req["id"]: expected("FALSE") for req in doc["requirements"]}
    changes["speed"] = expected("UNKNOWN")
    changes["type-known"] = expected("FALSE")
    cases.append(assembly_case("entire-drive-absent", doc, "FAIL", changes, (1, 10),
        [finding("drive-required", "MISSING_COMPONENT", ["motor"])], "BLOCKED", ["bore", "support-required", "shaft-diameter"]))
    cases[-1].cad["seat-feature"]["known_dimensions"] = {}
    for relation, affected, scenario, code in (
        ("support", ("support-required", "drive-required", "supported-required"), (2,), "MISSING_RELATIONSHIP"),
        ("retention", ("retention-required", "supported-required"), (), "MISSING_RELATIONSHIP"),
        ("drive-out", ("drive-required",), (), "MISSING_RELATIONSHIP"),
    ):
        doc = assembly()
        doc["relationships"] = [r for r in doc["relationships"] if r["id"] != relation]
        blocked = relation == "support"
        cases.append(assembly_case(f"missing-{relation}", doc, "FAIL",
            {key: expected("FALSE") for key in affected}, scenario,
            [finding(affected[0], code, ["shaft"])], "BLOCKED" if blocked else "RELEASED",
            ["support-required"] if blocked else []))
    for part, key, req, feature, scenario in (("bearing", "bore", "bore", "seat", (4,)),
                                              ("coupling", "bore", "coupling-fit", "coupled", ())):
        doc = assembly()
        by_id(doc["components"], part)["facts"][key]["value"] = 12
        cases.append(assembly_case(f"{part}-bore-mismatch", doc, "FAIL", {req: expected("FALSE")}, scenario,
            [finding(req, "DIMENSION_MISMATCH", ["shaft", part], [feature])],
            "BLOCKED" if req == "bore" else "RELEASED", ["bore"] if req == "bore" else []))
    for state in ("UNKNOWN", "ASSUMED"):
        doc = assembly()
        rating = by_id(doc["components"], "bearing")["facts"]["speed_rating"]
        rating.update(epistemic=state, value=None if state == "UNKNOWN" else 200)
        cases.append(assembly_case(f"bearing-rating-{state.lower()}", doc, "UNKNOWN", {"speed": expected("UNKNOWN")},
            (3,) if state == "UNKNOWN" else (), [finding("speed", "MISSING_FACT" if state == "UNKNOWN" else "ASSUMED_FACT", ["bearing"],
                observed={"bearing-rating": deepcopy(rating)})]))
    doc = assembly()
    by_id(doc["components"], "bearing")["facts"].pop("speed_rating")
    cases.append(assembly_case("bearing-rating-omitted", doc, "UNKNOWN", {"speed": expected("UNKNOWN")}, (3,),
                               [finding("speed", "MISSING_FACT", ["bearing"])]))
    doc = assembly()
    by_id(doc["components"], "shaft")["subtype"] = "unmapped_mystery"
    # Isolate the type rule: no assumptions about how internal rule cascades are presented.
    doc["requirements"] = [by_id(doc["requirements"], "type-known")]
    doc["cad_requests"] = []
    case = assembly_case("unknown-component-type", doc, "UNKNOWN", {"type-known": expected("UNKNOWN", "UNCOVERED")}, (7,),
        [finding("type-known", "UNKNOWN_COMPONENT_TYPE", ["shaft"])])
    case.cad = {}
    cases.append(case)
    doc = assembly()
    by_id(doc["requirements"], "bore")["coverage"] = "UNCOVERED"
    cases.append(assembly_case("mandatory-rule-uncovered", doc, "UNKNOWN", {"bore": expected("UNKNOWN", "UNCOVERED")}, (8,),
        [finding("bore", "UNCOVERED_RULE", ["shaft", "bearing"], ["seat"])], "BLOCKED", ["bore"]))
    doc = assembly()
    doc["scopes"]["relationships"] = "OPEN"
    cases.append(assembly_case("open-relationship-inventory", doc, "UNKNOWN",
        {req["id"]: expected(scope="OPEN") for req in doc["requirements"]}, (12,),
        [finding("support-required", "OPEN_SCOPE", ["shaft"])], "BLOCKED", ["scope:relationships"]))
    doc = assembly()
    diameter = by_id(doc["components"], "shaft")["facts"]["diameter"]
    diameter.update(epistemic="UNKNOWN", value=None)
    case = assembly_case("unknown-cad-dimension", doc, "UNKNOWN",
        {"bore": expected("UNKNOWN"), "coupling-fit": expected("UNKNOWN")}, (15,),
        [finding("bore", "MISSING_FACT", ["shaft"], ["seat"])], "BLOCKED", ["bore", "shaft-diameter"])
    case.cad["seat-feature"]["known_dimensions"] = {}
    cases.append(case)
    # All six source categories are preserved; no fabricated commercial data.
    for category in ("STANDARD", "MANUFACTURER", "HANDBOOK", "OMNI_VALIDATED", "OMNI_HEURISTIC", "USER_PROVIDED"):
        doc = assembly()
        by_id(doc["components"], "shaft")["facts"]["diameter"]["provenance"] = provenance(category)
        cases.append(assembly_case(f"provenance-{category.lower()}", doc))
    for category in ("STANDARD", "MANUFACTURER", "HANDBOOK", "OMNI_VALIDATED"):
        for agreements in (1, 2, 7):
            doc = assembly()
            value = by_id(doc["components"], "bearing")["facts"]["speed_rating"]
            value["provenance"] = dict(category=category, origin="MODEL", source_ref="model:proposal", agreement_count=agreements)
            case = assembly_case(f"model-agreement-{agreements}-not-{category.lower()}", doc, "UNKNOWN", {"speed": expected("UNKNOWN")},
                                 findings=[finding("speed", "UNTRUSTED_PROVENANCE", ["bearing"])])
            sanitized = dict(id=value["id"], units=value["units"], provenance={
                key: item for key, item in value["provenance"].items() if key != "category"})
            case.fact_overrides = {value["id"]: sanitized}
            cases.append(case)
    # Required pattern tests use explicit roles/edges, no vendor ratings.
    for kind in ("belt_drive", "motor_to_leadscrew_stage", "geared_output"):
        doc = assembly()
        extra = []
        links = []
        if kind == "belt_drive":
            extra = [component("pulley", "transmission", "pulley"), component("belt", "transmission", "belt"),
                     component("driven-pulley", "transmission", "pulley"), component("tensioner", "linear_motion", "tensioner")]
            roles = dict(motor="motor", pulley="pulley", belt="belt", driven_pulley="driven-pulley", shaft="shaft",
                         support="bearing", tensioner="tensioner")
            links = [("motor", "drives", "pulley"), ("pulley", "drives", "belt"),
                     ("belt", "drives", "driven-pulley"), ("driven-pulley", "drives", "shaft"),
                     ("tensioner", "tensions", "belt")]
            missing_edge = ("tensioner", "tensions", "belt")
        elif kind == "motor_to_leadscrew_stage":
            extra = [component("screw", "linear_motion", "leadscrew"), component("nut", "linear_motion", "nut"),
                     component("carriage", "linear_motion", "carriage"), component("guide", "linear_motion", "linear_guide")]
            roles = dict(motor="motor", coupling="coupling", leadscrew="screw", support="bearing", nut="nut",
                         carriage="carriage", guide="guide")
            links = [("coupling", "drives", "screw"), ("bearing", "supports", "screw"),
                     ("screw", "drives", "nut"), ("nut", "attached_to", "carriage"), ("guide", "guides", "carriage")]
            missing_edge = ("bearing", "supports", "screw")
        else:
            extra = [component("gear", "transmission", "spur_gear")]
            roles = dict(motor="motor", gear="gear", shaft="shaft", support="bearing", load="load")
            links = [("motor", "drives", "gear"), ("gear", "drives", "shaft")]
            missing_edge = ("gear", "drives", "shaft")
        doc["components"].extend(extra)
        doc["relationships"].extend(relationship(f"pattern-edge-{i}", verb, start, end) for i, (start, verb, end) in enumerate(links))
        doc["patterns"].append(dict(id="additional-pattern", kind=kind, roles=roles, provenance=provenance()))
        doc["requirements"].append(mechanical_requirement("pattern-required", "pattern", {"pattern": "additional-pattern"}))
        cases.append(assembly_case(f"valid-{kind}", doc))
        broken = deepcopy(doc)
        broken["relationships"] = [r for r in broken["relationships"]
                                   if (r["source"], r["kind"], r["target"]) != missing_edge]
        cases.append(assembly_case(f"missing-edge-{kind}", broken, "FAIL", {"pattern-required": expected("FALSE")},
            (5,) if kind == "belt_drive" else (), [finding("pattern-required", "MISSING_RELATIONSHIP", [missing_edge[2]])]))
    # Independent mission existence requirement survives deletion even if patterns disappear.
    doc = assembly()
    doc.update(components=[], interfaces=[], relationships=[], patterns=[], cad_requests=[])
    doc["requirements"] = [mechanical_requirement("mission-drive", "component_exists", {"family": "motor", "minimum": 1})]
    case = assembly_case("deleted-objects-cannot-erase-mission", doc, "FAIL", {"mission-drive": expected("FALSE")}, (10, 1),
                         [finding("mission-drive", "MISSING_COMPONENT")])
    case.cad = {}
    cases.append(case)
    # CAD gates isolate all specified blocker dimensions via an independent prerequisite.
    for gate in ("truth", "applicability", "coverage-unknown", "dependency", "intermediate"):
        doc = assembly()
        req = by_id(doc["requirements"], "bore")
        changes = {}
        if gate == "truth":
            by_id(doc["components"], "bearing")["facts"]["bore"].update(value=None, epistemic="UNKNOWN")
            changes["bore"] = expected("UNKNOWN")
        elif gate == "applicability":
            req["antecedent"] = literal("UNKNOWN")
            changes["bore"] = expected("UNKNOWN", applicability="UNDETERMINED")
        elif gate == "coverage-unknown":
            req["coverage"] = "UNKNOWN"
            changes["bore"] = expected("UNKNOWN", "UNKNOWN")
        elif gate == "dependency":
            doc["dependencies"] = [dict(id="fit-choice", kind="UNBOUNDED", members=["fit"], options=[])]
            req["dependency_ids"] = ["fit-choice"]
            changes["bore"] = expected("UNKNOWN", dependency_ids=["fit-choice"])
        else:
            doc["revision"] = "INTERMEDIATE"
        cases.append(assembly_case(f"cad-gate-{gate}", doc, "UNKNOWN", changes,
            cad_status="BLOCKED", unresolved=["revision"] if gate == "intermediate" else ["bore"]))
    for state in ("false", "unknown", "missing"):
        doc = assembly()
        rotation = by_id(doc["components"], "shaft")["facts"]["rotating"]
        rotation.update(value=False if state == "false" else None, epistemic="KNOWN" if state == "false" else "UNKNOWN")
        observed = {rotation["id"]: deepcopy(rotation)}
        if state == "missing":
            by_id(doc["components"], "shaft")["facts"].pop("rotating")
            observed = {"missing_fact": "shaft-rotating"}
        req = by_id(doc["requirements"], "support-required")
        req["antecedent"] = {"op": "fact", "fact_id": "shaft-rotating"}
        doc["requirements"] = [mechanical_requirement("shaft-exists", "component_exists", {"family": "shaft", "minimum": 1}), req]
        doc["cad_requests"] = []
        app = "NOT_APPLICABLE" if state == "false" else "UNDETERMINED"
        case = assembly_case(f"rotation-antecedent-{state}", doc, "PASS" if state == "false" else "UNKNOWN",
            {"support-required": expected("UNKNOWN", applicability=app)}, findings=[finding("support-required",
                "NOT_APPLICABLE" if state == "false" else "UNDETERMINED_APPLICABILITY", ["shaft"], observed=observed)])
        case.cad = {}
        cases.append(case)
    doc = assembly()
    by_id(doc["components"], "shaft")["facts"]["speed"]["value"] = 0
    by_id(doc["components"], "bearing")["facts"]["speed_rating"].update(value=None, epistemic="UNKNOWN")
    cases.append(assembly_case("zero-speed-does-not-resolve-unknown-rating", doc, "UNKNOWN", {"speed": expected("UNKNOWN")},
                               findings=[finding("speed", "MISSING_FACT", ["bearing"])]))
    doc = assembly()
    req = mechanical_requirement("unknown-rule", "unregistered_custom_rule", {"interface": "seat"})
    doc.update(requirements=[req], cad_requests=[])
    case = assembly_case("unregistered-rule-is-not-covered", doc, "UNKNOWN", {"unknown-rule": expected("UNKNOWN", "UNCOVERED")},
        (8,), [finding("unknown-rule", "UNCOVERED_RULE", ["shaft", "bearing"], ["seat"])])
    case.cad = {}
    cases.append(case)
    families = [("fastener", "bolt"), ("shaft", "round_shaft"), ("bearing", "radial_bearing"),
                ("coupling", "rigid_coupling"), ("transmission", "pulley"), ("motor", "rotary_motor"),
                ("linear_motion", "linear_guide"), ("structure", "housing"), ("unmapped_family", "mystery")]
    for family, subtype in families:
        doc = assembly()
        doc["components"].append(component("extra-component", family, subtype))
        doc.update(requirements=[mechanical_requirement("registered-type", "component_type", {"component": "extra-component"})], cad_requests=[])
        unknown = family == "unmapped_family"
        case = assembly_case(f"family-{family}", doc, "UNKNOWN" if unknown else "PASS",
            {"registered-type": expected("UNKNOWN", "UNCOVERED")} if unknown else {},
            findings=[finding("registered-type", "UNKNOWN_COMPONENT_TYPE", ["extra-component"])] if unknown else [])
        case.cad = {}
        cases.append(case)
    return cases


def _rename(value, mapping, *, keyed=False, field=None):
    """Rename references, never role names, fact names, types or rule vocabulary."""
    constants = {"op", "truth", "coverage", "applicability", "scope", "epistemic", "units",
                 "category", "origin", "source_ref", "revision", "revision_id", "family",
                 "subtype", "kind", "rule", "code", "feature", "state", "explanation"}
    keyed_maps = {"by_completion", "completion_results", "choices", "observed"}
    if isinstance(value, dict):
        return {(mapping.get(key, key) if keyed else key):
                _rename(item, mapping, keyed=key in keyed_maps, field=key)
                for key, item in value.items()}
    if isinstance(value, list):
        return [_rename(item, mapping, field=field) for item in value]
    if isinstance(value, str) and field not in constants:
        return mapping.get(value, value)
    return value


def variants(cases):
    selected = {"fully-valid-final", "bearing-bore-mismatch", "unknown-cad-dimension",
                "missing-support", "open-relationship-inventory", "joint-domain-no-cartesian-expansion",
                "crossed-truth-coverage", "vacuity-not-existence", "deleted-objects-cannot-erase-mission"}
    result = []
    for case in cases:
        if case.name not in selected:
            continue
        identifiers = set(case.results)
        for key in ("components", "interfaces", "relationships", "patterns", "dependencies", "completions", "cad_requests"):
            identifiers.update(item["id"] for item in case.document.get(key, []))
        for comp in case.document.get("components", []):
            identifiers.update(f["id"] for f in comp["facts"].values())
        for offset in (17, 53):
            mapping = {old: f"opaque-{offset + i * 7}" for i, old in enumerate(sorted(identifiers))}
            doc = _rename(case.document, mapping)
            for key in ("components", "interfaces", "relationships", "patterns", "requirements", "completions", "cad_requests"):
                if key in doc:
                    doc[key].reverse()
            for comp in doc.get("components", []):
                comp["facts"] = dict(reversed(list(comp["facts"].items())))
            result.append(Case(f"{case.name}-renamed-{offset}", case.api, doc, case.verdict,
                _rename(case.results, mapping, keyed=True), case.scenarios, _rename(case.findings, mapping),
                _rename(case.cad, mapping, keyed=True), _rename(case.fact_overrides, mapping, keyed=True)))
    return result


def build_cases():
    cases = logical_cases() + assembly_cases()
    cases.extend(variants(cases))
    return cases
