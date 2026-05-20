from __future__ import annotations

from typing import Any, Dict, Optional

from backend.app.reliability.evidence import build_evidence_summary, make_evidence
from backend.app.reliability.gates import (
    collect_blockers,
    collect_passed_checks,
    collect_required_next_tests,
    collect_warnings,
    compute_overall_status,
    make_gate,
)
from backend.app.reliability.schemas import ReliabilityReport, ReliabilityReviewRequest
from backend.app.reliability.scoring import compute_engineering_confidence


def get_reliability_status() -> Dict[str, Any]:
    return {
        "system": "OMNI Reliability Core",
        "version": "0.1.0",
        "status": "online",
        "purpose": (
            "Converts OMNI outputs into evidence-labeled engineering reliability "
            "reports with pass/warn/fail/blocked gates."
        ),
        "implemented_layers": [
            "reliability schemas",
            "evidence records",
            "provenance labels",
            "gate statuses",
            "baseline scoring",
        ],
        "next_layers": [
            "deterministic drone/rover/power calculators",
            "golden standard regression runner",
            "OMNITorch CAD visual review integration",
            "frontend reliability dashboard",
        ],
    }


def detect_mission_domain(mission_text: str) -> str:
    text = mission_text.lower()

    if any(term in text for term in ["quadcopter", "hexacopter", "drone", "uav"]):
        return "drone"

    if any(term in text for term in ["rover", "ugv", "wheeled robot", "tracked robot"]):
        return "rover"

    if any(term in text for term in ["arm", "manipulator", "gripper", "joint torque"]):
        return "manipulator"

    if any(term in text for term in ["pcb", "kicad", "circuit", "power rail"]):
        return "electronics"

    if any(term in text for term in ["fusion", "cad", "enclosure", "morphology"]):
        return "cad"

    return "general_robotics"


def _get_ros2_validation(export_result: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not export_result:
        return None

    export_block = export_result.get("export")

    if isinstance(export_block, dict) and export_block.get("ros2_validation"):
        return export_block.get("ros2_validation")

    if export_result.get("ros2_validation"):
        return export_result.get("ros2_validation")

    return None


def _has_mission_artifacts(mission_result: Optional[Dict[str, Any]]) -> bool:
    if not mission_result:
        return False

    artifact_keys = [
        "artifacts",
        "final_synthesis",
        "final_report",
        "final_decision",
        "response",
        "result",
    ]

    return any(key in mission_result and mission_result.get(key) for key in artifact_keys)


def run_reliability_review(payload: ReliabilityReviewRequest) -> ReliabilityReport:
    mission_text = payload.mission_text.strip()
    mission_domain = detect_mission_domain(mission_text)

    evidence = []
    gates = []

    # Gate 1: mission requirements
    if len(mission_text) >= 20:
        item = make_evidence(
            label="Mission text provided",
            evidence_type="user_provided",
            source="ReliabilityReviewRequest.mission_text",
            status="PASS",
            confidence="medium",
            details={"mission_length": len(mission_text), "detected_domain": mission_domain},
        )
        evidence.append(item)

        gates.append(
            make_gate(
                gate_id="mission-requirements",
                name="Mission Requirements",
                status="PASS",
                summary="Mission text is present and can be evaluated.",
                evidence_ids=[item.id],
            )
        )
    else:
        item = make_evidence(
            label="Mission text missing or too short",
            evidence_type="missing_evidence",
            source="ReliabilityReviewRequest.mission_text",
            status="BLOCKED",
            confidence="high",
        )
        evidence.append(item)

        gates.append(
            make_gate(
                gate_id="mission-requirements",
                name="Mission Requirements",
                status="BLOCKED",
                summary="Mission text is missing or too short for engineering review.",
                evidence_ids=[item.id],
                blockers=["Provide a specific mission objective before running reliability review."],
            )
        )

    # Gate 2: generated artifact presence
    if _has_mission_artifacts(payload.mission_result):
        item = make_evidence(
            label="Mission artifacts detected",
            evidence_type="llm_generated",
            source="mission_result",
            status="PASS",
            confidence="medium",
            human_review_required=True,
        )
        evidence.append(item)

        gates.append(
            make_gate(
                gate_id="artifact-presence",
                name="Generated Artifact Presence",
                status="PASS",
                summary="OMNI mission artifacts are present for review.",
                evidence_ids=[item.id],
            )
        )
    else:
        item = make_evidence(
            label="No mission artifacts provided to reliability review",
            evidence_type="missing_evidence",
            source="mission_result",
            status="WARN",
            confidence="medium",
        )
        evidence.append(item)

        gates.append(
            make_gate(
                gate_id="artifact-presence",
                name="Generated Artifact Presence",
                status="WARN",
                summary="No mission artifacts were provided, so reliability review is limited.",
                evidence_ids=[item.id],
                warnings=["Run an OMNI mission and pass mission_result into the reliability review."],
            )
        )

    # Gate 3: ROS2/export validation
    ros2_validation = _get_ros2_validation(payload.export_result)

    if ros2_validation:
        passed = bool(ros2_validation.get("passed"))

        item = make_evidence(
            label="ROS2 export validation detected",
            evidence_type="build_test",
            source="export_result.ros2_validation",
            status="PASS" if passed else "FAIL",
            confidence="high",
            details=ros2_validation,
        )
        evidence.append(item)

        gates.append(
            make_gate(
                gate_id="ros2-build-validation",
                name="ROS2 Build Validation",
                status="PASS" if passed else "FAIL",
                summary=(
                    "ROS2 generated package validation passed."
                    if passed
                    else "ROS2 generated package validation did not pass."
                ),
                evidence_ids=[item.id],
                warnings=[] if passed else ["Inspect ROS2 validation report paths and failed checks."],
                required_next_tests=[] if passed else ["Re-run colcon build and launch smoke checks."],
            )
        )
    else:
        item = make_evidence(
            label="ROS2 validation not provided",
            evidence_type="missing_evidence",
            source="export_result",
            status="WARN",
            confidence="medium",
        )
        evidence.append(item)

        gates.append(
            make_gate(
                gate_id="ros2-build-validation",
                name="ROS2 Build Validation",
                status="WARN",
                summary="No ROS2 build/export validation evidence was provided.",
                evidence_ids=[item.id],
                warnings=["Export the mission and run ROS2 validation for stronger reliability scoring."],
                required_next_tests=["Run OMNI export and ROS2 package validation."],
            )
        )

    # Gate 4: OMNITorch evidence
    if payload.omnitorch_result:
        task_type = payload.omnitorch_result.get("task_type", "unknown")
        system_name = payload.omnitorch_result.get("system", "unknown")

        is_demo_classifier = task_type == "image_classification"

        item = make_evidence(
            label="OMNITorch result provided",
            evidence_type="omnitorch_inference",
            source=system_name,
            status="WARN" if is_demo_classifier else "PASS",
            confidence="medium",
            details=payload.omnitorch_result,
            human_review_required=True,
        )
        evidence.append(item)

        gates.append(
            make_gate(
                gate_id="omnitorch-visual-evidence",
                name="OMNITorch Visual Evidence",
                status="WARN" if is_demo_classifier else "PASS",
                summary=(
                    "OMNITorch result was provided, but current image classification demo "
                    "is not engineering-specific."
                    if is_demo_classifier
                    else "OMNITorch engineering-specific visual evidence was provided."
                ),
                evidence_ids=[item.id],
                warnings=(
                    ["Fashion-MNIST predictions must not be treated as CAD or robotics evidence."]
                    if is_demo_classifier
                    else []
                ),
                required_next_tests=(
                    ["Replace demo image classifier with CAD visual review or robotics model."]
                    if is_demo_classifier
                    else []
                ),
            )
        )
    else:
        item = make_evidence(
            label="No OMNITorch result provided",
            evidence_type="missing_evidence",
            source="omnitorch_result",
            status="WARN",
            confidence="low",
        )
        evidence.append(item)

        gates.append(
            make_gate(
                gate_id="omnitorch-visual-evidence",
                name="OMNITorch Visual Evidence",
                status="WARN",
                summary="No OMNITorch visual evidence was included in this reliability review.",
                evidence_ids=[item.id],
                required_next_tests=["Run OMNITorch CAD visual review when available."],
            )
        )

    # Gate 5: deterministic engineering calculations
    calculation_required_domains = {"drone", "rover", "manipulator", "electronics"}

    if mission_domain in calculation_required_domains:
        item = make_evidence(
            label="Deterministic engineering calculation missing",
            evidence_type="missing_evidence",
            source="engineering_calculators",
            status="BLOCKED",
            confidence="high",
        )
        evidence.append(item)

        gates.append(
            make_gate(
                gate_id="deterministic-calculations",
                name="Deterministic Engineering Calculations",
                status="BLOCKED",
                summary=(
                    f"{mission_domain} missions require deterministic calculations before "
                    "high engineering confidence can be assigned."
                ),
                evidence_ids=[item.id],
                blockers=[
                    "No deterministic mass, power, torque, thrust, or runtime calculation was provided."
                ],
                required_next_tests=[
                    "Run domain-specific engineering calculators.",
                    "Record assumptions used by each calculator.",
                ],
            )
        )
    else:
        item = make_evidence(
            label="No domain-specific deterministic calculator required yet",
            evidence_type="missing_evidence",
            source="engineering_calculators",
            status="WARN",
            confidence="medium",
        )
        evidence.append(item)

        gates.append(
            make_gate(
                gate_id="deterministic-calculations",
                name="Deterministic Engineering Calculations",
                status="WARN",
                summary="No deterministic calculator was run for this mission yet.",
                evidence_ids=[item.id],
                required_next_tests=["Add a domain-specific calculator if the mission becomes hardware-specific."],
            )
        )

    evidence_summary = build_evidence_summary(evidence)
    overall_status = compute_overall_status(gates)
    confidence = compute_engineering_confidence(gates=gates, evidence=evidence)

    blockers = collect_blockers(gates)
    warnings = collect_warnings(gates)
    next_tests = collect_required_next_tests(gates)
    passed_checks = collect_passed_checks(gates)

    recommendations = [
        "Treat LLM-generated design claims as provisional until backed by calculation, build test, simulation, or uploaded evidence.",
        "Use deterministic calculators for power, mass, torque, thrust, runtime, and structural estimates.",
        "Use OMNITorch for visual inspection, but require engineering-specific models or rules before trusting visual conclusions.",
    ]

    summary = (
        f"Reliability review completed for domain '{mission_domain}'. "
        f"Overall status: {overall_status}. "
        f"Engineering confidence: {confidence:.2f}."
    )

    return ReliabilityReport(
        overall_status=overall_status,
        engineering_confidence=confidence,
        mission_domain=mission_domain,
        summary=summary,
        gates=gates,
        evidence=evidence,
        evidence_summary=evidence_summary,
        passed_checks=passed_checks,
        warnings=warnings,
        blockers=blockers,
        required_next_tests=next_tests,
        recommendations=recommendations,
    )