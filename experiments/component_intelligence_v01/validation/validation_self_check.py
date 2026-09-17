"""Test the human validator itself using canned outputs, not a CI implementation.

No candidate package is created/imported. This is not the candidate acceptance
command and cannot establish Component Intelligence correctness.
"""
from __future__ import annotations

import sys
sys.dont_write_bytecode = True

from copy import deepcopy
from types import SimpleNamespace

from component_intelligence_validation import (
    Checks, CheckFailure, canonical, check_result, input_facts, run_cases,
)
from fixtures_v01 import build_cases, provenance


def canned_output(case):
    """Shape-only stand-in assembled from the prewritten expected answers."""
    findings = []
    for index, wanted in enumerate(case.findings):
        findings.append(dict(id=f"fixture-finding-{index}", rule_id="adapter:fixture",
            state=case.results[wanted["requirement_id"]]["truth"], explanation="Synthetic checker exercise.",
            observed=deepcopy(wanted.get("observed", {"state": "synthetic"})), expected={"condition": "fixture"},
            provenance=[provenance()], **{key: deepcopy(value) for key, value in wanted.items() if key != "observed"}))
    for identifier, result in case.results.items():
        if not any(f["requirement_id"] == identifier for f in findings) and (
            result["truth"] != "TRUE" or result["coverage"] != "COVERED" or result["scope"] != "CLOSED" or result["applicability"] != "APPLIES"):
            findings.append(dict(id=f"explanation-{identifier}", requirement_id=identifier, rule_id="adapter:fixture",
                code="UNRESOLVED", state=result["truth"], explanation="Synthetic checker exercise.",
                components=[], interfaces=[], dependency_ids=result["dependency_ids"],
                observed={"state": result["truth"]}, expected={"state": "TRUE"}, provenance=[provenance()]))
    out = dict(verdict=case.verdict, requirement_results=deepcopy(case.results), findings=findings)
    if case.api == "evaluate_assembly":
        out["fact_results"] = deepcopy(input_facts(case.document))
        for identifier in case.fact_overrides:
            out["fact_results"][identifier]["epistemic"] = "ASSUMED"
            out["fact_results"][identifier]["provenance"]["category"] = "OMNI_HEURISTIC"
        out["cad_obligations"] = []
        requirements = {r["id"]: r for r in case.document["requirements"]}
        for request in case.document["cad_requests"]:
            out["cad_obligations"].append(dict(id=request["id"], target=request["target"], feature=request["feature"],
                provenance=[provenance()], source_requirements=request["prerequisites"],
                source_rules=sorted({requirements[r]["rule"] for r in request["prerequisites"]}),
                **deepcopy(case.cad[request["id"]])))
    return out


def validate_fixtures(cases):
    """Check wiring/references and variant vocabulary without solving engineering."""
    assert len({case.name for case in cases}) == len(cases)
    assert {n for case in cases for n in case.scenarios} == set(range(1, 18))
    for case in cases:
        doc = case.document
        canonical(doc)
        assert set(case.results) == {r["id"] for r in doc["requirements"]}
        ids = {c["id"] for c in doc["completions"]}
        assert len(ids) == len(doc["completions"])
        dependencies = {d["id"]: d for d in doc["dependencies"]}
        for c in doc["completions"]:
            for dep_id, choice in c["choices"].items():
                assert dep_id in dependencies
                assert choice in {o["id"] for o in dependencies[dep_id]["options"]}
        for r in doc["requirements"]:
            assert set(r["required_scopes"]) <= set(doc["scopes"])
            assert set(r["dependency_ids"]) <= set(dependencies)
            assert set(case.results[r["id"]]["completion_results"]) == ids
        if case.api == "evaluate_assembly":
            assert {c["family"] for c in doc["components"]} <= {
                "shaft", "bearing", "motor", "coupling", "transmission", "fastener", "structure", "linear_motion", "unmapped_family"}
            for pattern in doc["patterns"]:
                assert set(pattern["roles"]) <= {"shaft", "support", "structure", "retainer", "motor", "coupling",
                    "load", "pulley", "belt", "driven_pulley", "tensioner", "leadscrew", "nut", "carriage", "guide", "gear"}
            for c in doc["components"]:
                assert set(c["facts"]) <= {"diameter", "speed", "rotating", "bore", "speed_rating"}
            assert set(case.cad) == {r["id"] for r in doc["cad_requests"]}


def main():
    cases = build_cases()
    validate_fixtures(cases)
    originals = {case.name: canonical(case.document) for case in cases}
    checks = Checks()
    rejected = 0
    for case in cases:
        output = canned_output(case)
        check_result(case, output, checks)
        mutations = []
        wrong = deepcopy(output)
        wrong["verdict"] = "FAIL" if case.verdict != "FAIL" else "PASS"
        mutations.append(wrong)
        for identifier in case.results:
            for dimension in ("truth", "coverage", "scope", "applicability"):
                wrong = deepcopy(output)
                wrong["requirement_results"][identifier][dimension] = "CORRUPTED"
                mutations.append(wrong)
            wrong = deepcopy(output)
            wrong["requirement_results"][identifier]["completion_results"] = {"invented": {}}
            mutations.append(wrong)
        if output["findings"]:
            wrong = deepcopy(output)
            wrong["findings"] = []
            mutations.append(wrong)
        for index, obligation in enumerate(output.get("cad_obligations", [])):
            wrong = deepcopy(output)
            wrong["cad_obligations"][index]["status"] = "RELEASED" if obligation["status"] == "BLOCKED" else "BLOCKED"
            mutations.append(wrong)
            wrong = deepcopy(output)
            wrong["cad_obligations"][index]["known_dimensions"]["invented"] = {"value": 0, "units": "mm"}
            mutations.append(wrong)
        for identifier, fact in output.get("fact_results", {}).items():
            if fact["epistemic"] != "KNOWN":
                wrong = deepcopy(output)
                wrong["fact_results"][identifier].update(value=0, epistemic="KNOWN")
                mutations.append(wrong)
        for wrong in mutations:
            try:
                check_result(case, wrong)
            except CheckFailure:
                rejected += 1
            else:
                raise AssertionError("checker accepted deliberately corrupted output")
    # Exercise the same two-calls/input-immutability loop the candidate runner uses.
    for case in cases:
        stand_in = SimpleNamespace(**{case.api: lambda document, c=case: canned_output(c)})
        count, failures = run_cases(stand_in, [case])
        assert not failures, failures
        checks.count += count
    # Mutation and nondeterminism must be detected even for otherwise valid data.
    case = cases[0]
    def mutate(document):
        document["revision"] = "INTERMEDIATE"
        return canned_output(case)
    assert run_cases(SimpleNamespace(**{case.api: mutate}), [case])[1]
    calls = []
    def vary(document):
        calls.append(1)
        result = canned_output(case)
        result["unstable_metadata"] = len(calls)
        return result
    assert run_cases(SimpleNamespace(**{case.api: vary}), [case])[1]
    assert originals == {c.name: canonical(c.document) for c in cases}
    print(f"PASS validation-self-check: cases={len(cases)} scenarios=17 checks={checks.count} corruptions_rejected={rejected}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
