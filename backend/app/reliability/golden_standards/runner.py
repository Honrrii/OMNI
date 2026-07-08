from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, List

from backend.app.reliability.golden_standards.standards import (
    GOLDEN_STANDARD_CASES,
    GoldenStandardCase,
)
from backend.app.reliability.reliability_service import run_reliability_review
from backend.app.reliability.schemas import ReliabilityReviewRequest


def _model_to_dict(value: Any) -> Dict[str, Any]:
    if hasattr(value, "model_dump"):
        return value.model_dump()

    if hasattr(value, "dict"):
        return value.dict()

    raise TypeError(f"Cannot convert value of type {type(value)} to dict.")


def _gate_status_map(report_dict: Dict[str, Any]) -> Dict[str, str]:
    return {
        gate["id"]: gate["status"]
        for gate in report_dict.get("gates", [])
    }


def evaluate_case(case: GoldenStandardCase) -> Dict[str, Any]:
    failures: List[str] = []

    request = ReliabilityReviewRequest(**case.payload)
    report = run_reliability_review(request)
    report_dict = _model_to_dict(report)

    actual_overall_status = report_dict["overall_status"]
    actual_confidence = report_dict["engineering_confidence"]
    actual_gate_statuses = _gate_status_map(report_dict)
    actual_blocker_count = len(report_dict.get("blockers", []))

    if actual_overall_status != case.expected_overall_status:
        failures.append(
            f"Expected overall_status={case.expected_overall_status}, "
            f"got {actual_overall_status}."
        )

    if not (case.expected_min_confidence <= actual_confidence <= case.expected_max_confidence):
        failures.append(
            f"Expected engineering_confidence between "
            f"{case.expected_min_confidence} and {case.expected_max_confidence}, "
            f"got {actual_confidence}."
        )

    for gate_id, expected_status in case.expected_gate_statuses.items():
        actual_status = actual_gate_statuses.get(gate_id)

        if actual_status != expected_status:
            failures.append(
                f"Gate '{gate_id}' expected {expected_status}, got {actual_status}."
            )

    if case.expected_blocker_count is not None:
        if actual_blocker_count != case.expected_blocker_count:
            failures.append(
                f"Expected blocker count {case.expected_blocker_count}, "
                f"got {actual_blocker_count}."
            )

    return {
        "id": case.id,
        "name": case.name,
        "description": case.description,
        "passed": len(failures) == 0,
        "failures": failures,
        "expected": {
            "overall_status": case.expected_overall_status,
            "gate_statuses": case.expected_gate_statuses,
            "min_confidence": case.expected_min_confidence,
            "max_confidence": case.expected_max_confidence,
            "blocker_count": case.expected_blocker_count,
        },
        "actual": {
            "overall_status": actual_overall_status,
            "engineering_confidence": actual_confidence,
            "gate_statuses": actual_gate_statuses,
            "blocker_count": actual_blocker_count,
        },
        "report": report_dict,
    }


def run_golden_standards() -> Dict[str, Any]:
    case_results = [evaluate_case(case) for case in GOLDEN_STANDARD_CASES]

    passed_count = sum(1 for result in case_results if result["passed"])
    failed_count = len(case_results) - passed_count

    overall_passed = failed_count == 0

    return {
        "system": "OMNI Reliability Golden Standards",
        "version": "0.1.0",
        "passed": overall_passed,
        "total_cases": len(case_results),
        "passed_cases": passed_count,
        "failed_cases": failed_count,
        "cases": case_results,
    }


def write_report(report: Dict[str, Any]) -> Path:
    output_dir = Path("outputs") / "reliability_golden_standards"
    output_dir.mkdir(parents=True, exist_ok=True)

    output_path = output_dir / "latest_report.json"

    output_path.write_text(
        json.dumps(report, indent=2),
        encoding="utf-8",
    )

    return output_path


def main() -> int:
    report = run_golden_standards()
    output_path = write_report(report)

    print("OMNI Reliability Golden Standards")
    print("---------------------------------")
    print(f"Total cases:  {report['total_cases']}")
    print(f"Passed cases: {report['passed_cases']}")
    print(f"Failed cases: {report['failed_cases']}")
    print(f"Report path:  {output_path}")

    for case in report["cases"]:
        status = "PASS" if case["passed"] else "FAIL"
        print(f"\n[{status}] {case['id']} — {case['name']}")

        if case["failures"]:
            for failure in case["failures"]:
                print(f"  - {failure}")

    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())