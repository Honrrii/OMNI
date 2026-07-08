from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, List, Optional

from backend.app.reliability.evidence import build_evidence_summary, make_evidence
from backend.app.reliability.gates import (
    collect_blockers,
    collect_passed_checks,
    collect_required_next_tests,
    collect_warnings,
    compute_overall_status,
    make_gate,
)
from backend.app.reliability.provenance import build_provenance_from_mission_state
from backend.app.reliability.reflection import build_reflection_notes
from backend.app.reliability.schemas import (
    ProvenanceRecord,
    ReliabilityReport,
    ReliabilityReviewRequest,
)
from backend.app.reliability.scoring import compute_engineering_confidence

if TYPE_CHECKING:
    from backend.app.omni_core.mission_state import MissionState

from dataclasses import asdict

from backend.app.reliability.calculators.power_calculators import (
    PowerBudgetInput,
    estimate_power_budget,
)
from backend.app.reliability.calculators.rover_calculators import (
    RoverMobilityInput,
    estimate_rover_mobility,
)
from backend.app.reliability.calculators.drone_calculators import (
    DroneSizingInput,
    estimate_drone_sizing,
)


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

def _get_context_block(payload: ReliabilityReviewRequest) -> Dict[str, Any]:
    if not payload.context:
        return {}

    return payload.context


def _run_power_budget_if_available(
    payload: ReliabilityReviewRequest,
) -> Optional[Dict[str, Any]]:
    context = _get_context_block(payload)
    power_input = context.get("power_budget")

    if not power_input:
        return None

    result = estimate_power_budget(PowerBudgetInput(**power_input))

    return {
        "input": power_input,
        "result": asdict(result),
    }


def _run_rover_mobility_if_available(
    payload: ReliabilityReviewRequest,
) -> Optional[Dict[str, Any]]:
    context = _get_context_block(payload)
    rover_input = context.get("rover_mobility")

    if not rover_input:
        return None

    result = estimate_rover_mobility(RoverMobilityInput(**rover_input))

    return {
        "input": rover_input,
        "result": asdict(result),
    }

def _run_drone_sizing_if_available(
    payload: ReliabilityReviewRequest,
) -> Optional[Dict[str, Any]]:
    context = _get_context_block(payload)
    drone_input = context.get("drone_sizing")

    if not drone_input:
        return None

    result = estimate_drone_sizing(DroneSizingInput(**drone_input))

    return {
        "input": drone_input,
        "result": asdict(result),
    }

def _status_from_calculation(calculation_result: Dict[str, Any]) -> str:
    return calculation_result.get("result", {}).get("status", "WARN")

def run_reliability_review(
    payload: ReliabilityReviewRequest,
    mission_state: Optional["MissionState"] = None,
) -> ReliabilityReport:
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

        if task_type == "image_classification":
            gate_status = "WARN"
            evidence_status = "WARN"
            summary = (
                "OMNITorch result was provided, but the current image classification demo "
                "is not engineering-specific."
            )
            warnings = [
                "Fashion-MNIST predictions must not be treated as CAD or robotics evidence."
            ]
            required_next_tests = [
                "Replace demo image classifier with CAD visual review or robotics model."
            ]

        elif task_type == "cad_visual_review":
            result_status = payload.omnitorch_result.get("status", "WARN")
            visual_review = payload.omnitorch_result.get("visual_review", {})

            if result_status in {"PASS", "WARN", "FAIL", "BLOCKED"}:
                evidence_status = result_status
                gate_status = result_status
            else:
                evidence_status = "WARN"
                gate_status = "WARN"

            if visual_review.get("flatness_warning"):
                summary = "OMNITorch CAD review detected severe flatness risk."
            elif visual_review.get("planar_morphology_warning"):
                summary = "OMNITorch CAD review detected broad planar morphology risk."
            else:
                summary = "OMNITorch CAD review did not detect major visual morphology risk."

            warnings = visual_review.get("recommendations", []) if gate_status == "WARN" else []

            required_next_tests = (
                ["Revise CAD morphology and re-run OMNITorch CAD visual review."]
                if gate_status == "WARN"
                else []
            )

        else:
            gate_status = "WARN"
            evidence_status = "WARN"
            summary = (
                f"OMNITorch result with task_type '{task_type}' was provided, "
                "but this task type is not fully supported by Reliability Core yet."
            )
            warnings = [
                "Review OMNITorch output manually before using it as engineering evidence."
            ]
            required_next_tests = []

        item = make_evidence(
            label="OMNITorch result provided",
            evidence_type="omnitorch_inference",
            source=system_name,
            status=evidence_status,
            confidence="medium",
            details=payload.omnitorch_result,
            human_review_required=True,
        )
        evidence.append(item)

        gates.append(
            make_gate(
                gate_id="omnitorch-visual-evidence",
                name="OMNITorch Visual Evidence",
                status=gate_status,
                summary=summary,
                evidence_ids=[item.id],
                warnings=warnings,
                required_next_tests=required_next_tests,
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

    calculation_evidence_ids: list[str] = []
    calculation_warnings: list[str] = []
    calculation_blockers: list[str] = []
    calculation_next_tests: list[str] = []

    power_calculation = None
    rover_calculation = None
    drone_calculation = None

    try:
        power_calculation = _run_power_budget_if_available(payload)
    except Exception as exc:
        item = make_evidence(
            label="Power budget calculation failed",
            evidence_type="calculation",
            source="power_calculators.estimate_power_budget",
            status="FAIL",
            confidence="high",
            details={"error": str(exc)},
            human_review_required=True,
        )
        evidence.append(item)
        calculation_evidence_ids.append(item.id)
        calculation_warnings.append(f"Power budget calculation failed: {exc}")

    try:
        rover_calculation = _run_rover_mobility_if_available(payload)
    except Exception as exc:
        item = make_evidence(
            label="Rover mobility calculation failed",
            evidence_type="calculation",
            source="rover_calculators.estimate_rover_mobility",
            status="FAIL",
            confidence="high",
            details={"error": str(exc)},
            human_review_required=True,
        )
        evidence.append(item)
        calculation_evidence_ids.append(item.id)
        calculation_warnings.append(f"Rover mobility calculation failed: {exc}")

    try:
        drone_calculation = _run_drone_sizing_if_available(payload)
    except Exception as exc:
        item = make_evidence(
            label="Drone sizing calculation failed",
            evidence_type="calculation",
            source="drone_calculators.estimate_drone_sizing",
            status="FAIL",
            confidence="high",
            details={"error": str(exc)},
            human_review_required=True,
        )
        evidence.append(item)
        calculation_evidence_ids.append(item.id)
        calculation_warnings.append(f"Drone sizing calculation failed: {exc}")

    if power_calculation:
        power_status = _status_from_calculation(power_calculation)

        item = make_evidence(
            label="Power budget calculation completed",
            evidence_type="calculation",
            source="power_calculators.estimate_power_budget",
            status=power_status,
            confidence="high",
            details=power_calculation,
            human_review_required=True,
        )
        evidence.append(item)
        calculation_evidence_ids.append(item.id)

        for warning in power_calculation["result"].get("warnings", []):
            calculation_warnings.append(f"Power budget: {warning}")

    if rover_calculation:
        rover_status = _status_from_calculation(rover_calculation)

        item = make_evidence(
            label="Rover mobility calculation completed",
            evidence_type="calculation",
            source="rover_calculators.estimate_rover_mobility",
            status=rover_status,
            confidence="high",
            details=rover_calculation,
            human_review_required=True,
        )
        evidence.append(item)
        calculation_evidence_ids.append(item.id)

        for warning in rover_calculation["result"].get("warnings", []):
            calculation_warnings.append(f"Rover mobility: {warning}")

    if drone_calculation:
        drone_status = _status_from_calculation(drone_calculation)

        item = make_evidence(
            label="Drone sizing calculation completed",
            evidence_type="calculation",
            source="drone_calculators.estimate_drone_sizing",
            status=drone_status,
            confidence="high",
            details=drone_calculation,
            human_review_required=True,
        )
        evidence.append(item)
        calculation_evidence_ids.append(item.id)

        for warning in drone_calculation["result"].get("warnings", []):
            calculation_warnings.append(f"Drone sizing: {warning}")

    if mission_domain == "drone":
        if not drone_calculation:
            item = make_evidence(
                label="Drone deterministic engineering calculation missing",
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
                        "Drone missions require deterministic mass, thrust, current draw, "
                        "and flight-time calculations before high engineering confidence "
                        "can be assigned."
                    ),
                    evidence_ids=[item.id],
                    blockers=[
                        "No deterministic drone sizing calculation was provided."
                    ],
                    required_next_tests=[
                        "Run drone sizing calculator.",
                        "Record mass, motor count, thrust per motor, battery capacity, voltage, and current assumptions.",
                    ],
                )
            )

        else:
            calculation_statuses = [
                evidence_item.status
                for evidence_item in evidence
                if evidence_item.id in calculation_evidence_ids
            ]

            if "FAIL" in calculation_statuses:
                gate_status = "FAIL"
                summary = "One or more deterministic drone calculations failed."
            elif "WARN" in calculation_statuses:
                gate_status = "WARN"
                summary = "Deterministic drone sizing calculation completed with warnings."
            else:
                gate_status = "PASS"
                summary = "Deterministic drone sizing calculation passed."

            gates.append(
                make_gate(
                    gate_id="deterministic-calculations",
                    name="Deterministic Engineering Calculations",
                    status=gate_status,
                    summary=summary,
                    evidence_ids=calculation_evidence_ids,
                    warnings=calculation_warnings,
                    blockers=calculation_blockers,
                    required_next_tests=calculation_next_tests,
                )
            )

    elif mission_domain == "rover":
        missing_required_calculations = []

        if not power_calculation:
            missing_required_calculations.append("power budget")

        if not rover_calculation:
            missing_required_calculations.append("rover mobility")

        if missing_required_calculations:
            calculation_next_tests.append(
                "Provide rover_mobility and power_budget inputs in the reliability review context."
            )

        if not calculation_evidence_ids:
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
                        "Rover missions require deterministic power and mobility calculations "
                        "before high engineering confidence can be assigned."
                    ),
                    evidence_ids=[item.id],
                    blockers=[
                        "No deterministic rover mobility or power budget calculation was provided."
                    ],
                    required_next_tests=[
                        "Run rover mobility calculator.",
                        "Run power budget calculator.",
                        "Record assumptions used by each calculator.",
                    ],
                )
            )

        else:
            calculation_statuses = [
                evidence_item.status
                for evidence_item in evidence
                if evidence_item.id in calculation_evidence_ids
            ]

            if "FAIL" in calculation_statuses:
                gate_status = "FAIL"
                summary = "One or more deterministic rover calculations failed."
            elif missing_required_calculations:
                gate_status = "WARN"
                summary = (
                    "Some deterministic rover calculations were provided, but the review "
                    f"is missing: {', '.join(missing_required_calculations)}."
                )
            elif "WARN" in calculation_statuses:
                gate_status = "WARN"
                summary = "Deterministic rover calculations completed with warnings."
            else:
                gate_status = "PASS"
                summary = "Deterministic rover power and mobility calculations passed."

            gates.append(
                make_gate(
                    gate_id="deterministic-calculations",
                    name="Deterministic Engineering Calculations",
                    status=gate_status,
                    summary=summary,
                    evidence_ids=calculation_evidence_ids,
                    warnings=calculation_warnings,
                    blockers=calculation_blockers,
                    required_next_tests=calculation_next_tests,
                )
            )

    elif mission_domain in calculation_required_domains:
        item = make_evidence(
            label="Domain-specific deterministic calculation missing",
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
        if power_calculation:
            gates.append(
                make_gate(
                    gate_id="deterministic-calculations",
                    name="Deterministic Engineering Calculations",
                    status="PASS",
                    summary="Power budget calculation was provided.",
                    evidence_ids=calculation_evidence_ids,
                    warnings=calculation_warnings,
                    required_next_tests=calculation_next_tests,
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
                    required_next_tests=[
                        "Add a domain-specific calculator if the mission becomes hardware-specific."
                    ],
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

    provenance: List[ProvenanceRecord] = (
        build_provenance_from_mission_state(mission_state)
        if mission_state is not None
        else []
    )

    reflection_notes = build_reflection_notes(gates, evidence, provenance)

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
        provenance=provenance,
        reflection_notes=reflection_notes,
    )