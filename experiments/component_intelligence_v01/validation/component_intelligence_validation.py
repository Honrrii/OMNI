"""Explicit human-owned validation runner. Not part of default pytest discovery.

No candidate implementation lives here. Run inside TestCube's read-only,
network-isolated, time/output-bounded collector for untrusted candidate code.
"""
from __future__ import annotations

import sys
sys.dont_write_bytecode = True

from contextlib import redirect_stderr, redirect_stdout
from copy import deepcopy
import importlib
import json
import math
import os
from pathlib import Path

from fixtures_v01 import build_cases
from verify_frozen_spec import EXPECTED_SHA256, observed_sha256

VERDICTS = {"PASS", "WARN", "FAIL", "UNKNOWN"}
TRUTHS = {"TRUE", "FALSE", "UNKNOWN"}
COVERAGES = {"COVERED", "UNCOVERED", "UNKNOWN"}
APPLICABILITIES = {"APPLIES", "NOT_APPLICABLE", "UNDETERMINED"}
PROVENANCE = {"STANDARD", "MANUFACTURER", "HANDBOOK", "OMNI_VALIDATED", "OMNI_HEURISTIC", "USER_PROVIDED"}
TRUSTED = {"STANDARD", "MANUFACTURER", "HANDBOOK", "OMNI_VALIDATED"}


class CheckFailure(Exception):
    pass


class Checks:
    def __init__(self):
        self.count = 0

    def require(self, condition, label):
        self.count += 1
        if not condition:
            raise CheckFailure(label)

    def equal(self, actual, expected, label):
        if type(expected) in (bool, type(None)):
            self.require(type(actual) is type(expected) and actual == expected, label)
        else:
            self.require(actual == expected, label)

    def subset(self, actual, expected, label):
        if type(expected) is dict:
            self.require(type(actual) is dict, label + ": object required")
            for key, value in expected.items():
                self.require(key in actual, label + ": missing field " + key)
                self.subset(actual[key], value, label + "." + key)
        else:
            self.equal(actual, expected, label)


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=True, allow_nan=False, separators=(",", ":"))


def json_value(value, checks):
    if type(value) is dict:
        checks.require(all(type(key) is str for key in value), "JSON object keys must be strings")
        for item in value.values():
            json_value(item, checks)
    elif type(value) is list:
        for item in value:
            json_value(item, checks)
    else:
        checks.require(type(value) in (str, int, float, bool, type(None)), "non-JSON output value")
        if type(value) is float:
            checks.require(math.isfinite(value), "nonfinite output value")


def check_provenance(items, checks):
    checks.require(type(items) is list and bool(items), "nonempty provenance list required")
    for item in items:
        checks.require(type(item) is dict, "provenance object required")
        checks.require(item.get("category") in PROVENANCE, "unsupported provenance category")
        checks.require(item.get("origin") in ("HUMAN", "MODEL"), "provenance origin missing")
        checks.require(type(item.get("source_ref")) is str and bool(item["source_ref"].strip()), "provenance source missing")
        checks.require(not (item["origin"] == "MODEL" and item["category"] in TRUSTED), "model-origin fact promoted to trusted provenance")


def input_facts(document):
    return {fact["id"]: fact for component in document.get("components", []) for fact in component["facts"].values()}


def check_result(case, result, checks=None):
    checks = checks or Checks()
    checks.require(type(result) is dict, "result must be a JSON object")
    json_value(result, checks)
    checks.require(result.get("verdict") in VERDICTS, "invalid verdict")
    checks.equal(result["verdict"], case.verdict, "wrong top-level verdict")
    checks.require(type(result.get("requirement_results")) is dict, "requirement_results map required")
    checks.equal(set(result["requirement_results"]), set(case.results), "human requirements were added/dropped/renamed")
    completions = {item["id"] for item in case.document["completions"]}
    for identifier, wanted in case.results.items():
        item = result["requirement_results"][identifier]
        checks.require(type(item) is dict, "requirement result must be an object")
        checks.require(item.get("applicability") in APPLICABILITIES, "missing applicability dimension")
        checks.require(item.get("truth") in TRUTHS, "missing truth dimension")
        checks.require(item.get("coverage") in COVERAGES, "missing coverage dimension")
        checks.require(item.get("scope") in ("CLOSED", "OPEN"), "missing scope dimension")
        checks.require(type(item.get("completion_results")) is dict, "per-completion observations required")
        checks.equal(set(item["completion_results"]), completions, "completion IDs changed or Cartesian-expanded")
        checks.subset(item, wanted, "requirement " + identifier)
    checks.require(type(result.get("findings")) is list, "findings list required")
    ids = set()
    for item in result["findings"]:
        checks.require(type(item) is dict, "finding must be an object")
        for key in ("id", "requirement_id", "rule_id", "code", "state", "explanation"):
            checks.require(type(item.get(key)) is str and bool(item[key].strip()), "finding missing " + key)
        checks.require(item["id"] not in ids, "duplicate finding ID")
        ids.add(item["id"])
        checks.require(item["requirement_id"] in case.results, "finding requirement untraceable")
        for key in ("components", "interfaces", "dependency_ids"):
            checks.require(type(item.get(key)) is list and all(type(v) is str for v in item[key]), "finding missing references: " + key)
        checks.require("observed" in item and "expected" in item, "finding evidence/expectation missing")
        checks.require(type(item["observed"]) is dict and bool(item["observed"]), "finding observed evidence missing")
        checks.require(type(item["expected"]) is dict and bool(item["expected"]), "finding expected condition missing")
        check_provenance(item.get("provenance"), checks)
    for wanted in case.findings:
        # Code/requirement choose the finding; wording and internal rule IDs are free.
        matched = [item for item in result["findings"] if item.get("requirement_id") == wanted["requirement_id"] and item.get("code") == wanted["code"]]
        checks.require(bool(matched), "required finding missing: " + wanted["code"])
        matching = False
        for item in matched:
            if all(set(wanted.get(key, [])) <= set(item.get(key, [])) for key in ("components", "interfaces", "dependency_ids")):
                if "observed" in wanted:
                    checks.subset(item["observed"], wanted["observed"], "finding observation")
                matching = True
                break
        checks.require(matching, "finding lacks affected entities/dependencies")
    # Even cases without a named finding expectation must explain unresolved/failing requirements.
    for identifier, item in result["requirement_results"].items():
        if item["truth"] != "TRUE" or item["coverage"] != "COVERED" or item["scope"] != "CLOSED" or item["applicability"] != "APPLIES":
            checks.require(any(f["requirement_id"] == identifier for f in result["findings"]), "non-true requirement has no explanation")
    if case.api == "evaluate_assembly":
        check_assembly(case, result, checks)
    return checks.count


def check_assembly(case, result, checks):
    facts = input_facts(case.document)
    wanted_facts = deepcopy(facts)
    wanted_facts.update(case.fact_overrides)
    checks.require(type(result.get("fact_results")) is dict, "inspectable fact_results required")
    checks.equal(set(result["fact_results"]), set(facts), "facts invented or omitted")
    for identifier, wanted in wanted_facts.items():
        actual = result["fact_results"][identifier]
        checks.subset(actual, wanted, "fact " + identifier)
        checks.require("value" in actual, "fact value missing")
        if facts[identifier]["provenance"]["origin"] == "MODEL":
            checks.require(actual.get("epistemic") in ("ASSUMED", "UNKNOWN"), "model consensus promoted to KNOWN")
            if actual.get("epistemic") == "ASSUMED":
                checks.equal(actual["value"], facts[identifier]["value"], "model proposal value was invented")
        checks.require(actual.get("epistemic") in ("KNOWN", "UNKNOWN", "ASSUMED"), "invalid epistemic state")
        check_provenance([actual.get("provenance")], checks)
        if actual["epistemic"] == "UNKNOWN":
            checks.require(actual["value"] is None, "UNKNOWN replaced by numeric/default value")
    obligations = result.get("cad_obligations")
    checks.require(type(obligations) is list, "cad_obligations list required")
    checks.require(all(type(o) is dict and type(o.get("id")) is str for o in obligations), "invalid CAD obligation")
    by_id = {item["id"]: item for item in obligations}
    checks.equal(len(by_id), len(obligations), "duplicate CAD request IDs")
    checks.equal(set(by_id), {item["id"] for item in case.document["cad_requests"]}, "CAD requests dropped or fabricated")
    requirements = {r["id"]: r for r in case.document["requirements"]}
    for request in case.document["cad_requests"]:
        item = by_id[request["id"]]
        checks.subset(item, {"target": request["target"], "feature": request["feature"]}, "CAD target/feature")
        checks.require(item.get("status") in ("RELEASED", "BLOCKED"), "invalid CAD release status")
        checks.require(type(item.get("known_dimensions")) is dict, "CAD dimensions missing")
        checks.require(type(item.get("unresolved_inputs")) is list, "CAD unresolved inputs missing")
        checks.require(type(item.get("source_requirements")) is list, "CAD source requirements missing")
        checks.equal(set(item["source_requirements"]), set(request["prerequisites"]), "CAD requirement provenance lost")
        checks.require(type(item.get("source_rules")) is list and all(type(v) is str and v for v in item["source_rules"]), "CAD rule references missing")
        checks.equal(set(item["source_rules"]), {requirements[r]["rule"] for r in request["prerequisites"]}, "CAD rule provenance lost")
        check_provenance(item.get("provenance"), checks)
        wanted = case.cad[request["id"]]
        checks.equal(item["status"], wanted["status"], "wrong CAD release gate")
        checks.equal(item["known_dimensions"], wanted["known_dimensions"], "invented or incorrect CAD geometry")
        checks.require(set(wanted["unresolved_inputs"]) <= set(item["unresolved_inputs"]), "CAD blockers omitted")
        if item["status"] == "BLOCKED":
            checks.require(bool(item["unresolved_inputs"]), "blocked CAD lacks unresolved input")
        else:
            checks.require(not item["unresolved_inputs"], "released CAD has unresolved inputs")
            checks.equal(case.document["revision"], "FINAL", "intermediate CAD release")
            for identifier in request["prerequisites"]:
                prereq = result["requirement_results"][identifier]
                checks.subset(prereq, dict(truth="TRUE", applicability="APPLIES", coverage="COVERED", scope="CLOSED"), "unresolved CAD prerequisite")
            for reference in request["dimension_inputs"].values():
                checks.require(reference in result["fact_results"] and result["fact_results"][reference]["epistemic"] == "KNOWN", "CAD released unknown dimension")


class QuietOutput:
    """Discard candidate chatter without buffering it or writing a file."""
    def write(self, text):
        return len(text)

    def flush(self):
        pass


def read_only_audit(event, args):
    """Defensive Python API guard, NOT a substitute for TestCube isolation."""
    if event == "open":
        _, mode, flags = args
        if (isinstance(mode, str) and any(char in mode for char in "wax+")) or (
            isinstance(flags, int) and flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND)):
            raise PermissionError("validation is read-only")
    if event.startswith(("socket.", "subprocess.", "os.exec", "os.spawn", "os.posix_spawn")) or event in (
        "os.system", "os.fork", "os.forkpty", "os.remove", "os.rename", "os.mkdir", "os.rmdir",
        "os.link", "os.symlink", "os.chmod", "os.chown", "os.truncate", "os.utime"):
        raise PermissionError("validation prohibits external execution, network and filesystem mutation")


def run_cases(candidate, cases):
    checks = Checks()
    failed = []
    for case in cases:
        try:
            function = getattr(candidate, case.api)
            first = None
            for _ in range(2):
                document = deepcopy(case.document)
                with redirect_stdout(QuietOutput()), redirect_stderr(QuietOutput()):
                    result = function(document)
                checks.equal(canonical(document), canonical(case.document), "candidate mutated input document")
                check_result(case, result, checks)
                encoded = canonical(result)
                if first is None:
                    first = encoded
                else:
                    checks.equal(encoded, first, "identical input produced nondeterministic output")
        except BaseException as exc:
            # Candidate exception prose/output is neither stable nor trusted evidence.
            detail = str(exc) if isinstance(exc, CheckFailure) else type(exc).__name__
            failed.append((case.name, detail))
    return checks.count, failed


def main() -> int:
    try:
        if observed_sha256() != EXPECTED_SHA256:
            print("FAIL frozen-spec: hash mismatch")
            return 1
        cases = build_cases()
    except Exception as exc:
        print(f"FAIL validation-setup: {type(exc).__name__}")
        return 1
    # Resolve the pinned checkout containing this script, not an installed peer package.
    root = Path(__file__).resolve().parents[3]
    sys.path.insert(0, str(root))
    sys.addaudithook(read_only_audit)
    try:
        with redirect_stdout(QuietOutput()), redirect_stderr(QuietOutput()):
            candidate = importlib.import_module("omni.component_intelligence")
    except ModuleNotFoundError as exc:
        reason = "missing package omni.component_intelligence" if exc.name == "omni.component_intelligence" else "candidate import dependency unavailable"
        print(f"FAIL candidate-api: {reason}; {len(cases)} cases not run")
        return 1
    except BaseException as exc:
        print(f"FAIL candidate-api: import raised {type(exc).__name__}; {len(cases)} cases not run")
        return 1
    missing = [name for name in ("evaluate_contract", "evaluate_assembly") if not callable(getattr(candidate, name, None))]
    if missing:
        print(f"FAIL candidate-api: missing callable(s) {','.join(missing)}; {len(cases)} cases not run")
        return 1
    count, failures = run_cases(candidate, cases)
    for name, detail in failures:
        print(f"FAIL {name}: {detail}")
    print(f"{'FAIL' if failures else 'PASS'} component-intelligence-v01: cases={len(cases)} passed={len(cases)-len(failures)} failed={len(failures)} checks={count}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
