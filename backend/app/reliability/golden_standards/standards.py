from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List


@dataclass
class GoldenStandardCase:
    id: str
    name: str
    description: str
    payload: Dict[str, Any]
    expected_overall_status: str
    expected_gate_statuses: Dict[str, str]
    expected_min_confidence: float
    expected_max_confidence: float
    expected_blocker_count: int | None = None


GOLDEN_STANDARD_CASES: List[GoldenStandardCase] = [
    GoldenStandardCase(
        id="GS-ROVER-001",
        name="Palm-sized rover with valid power and mobility calculations",
        description=(
            "A rover mission with enough deterministic calculator context to avoid "
            "being blocked by missing mobility/power evidence."
        ),
        payload={
            "mission_text": (
                "Design a palm-sized autonomous rover with ROS2, camera perception, "
                "battery power, Fusion 360 CAD, and validation gates."
            ),
            "context": {
                "power_budget": {
                    "battery_voltage_v": 7.4,
                    "battery_capacity_mah": 2200,
                    "average_current_a": 1.2,
                    "peak_current_a": 3.0,
                },
                "rover_mobility": {
                    "mass_kg": 1.5,
                    "wheel_radius_m": 0.04,
                    "motor_stall_torque_nm": 0.4,
                    "motor_count": 4,
                    "drivetrain_efficiency": 0.75,
                    "target_incline_deg": 10.0,
                    "rolling_resistance_coeff": 0.03,
                    "safety_factor": 1.5,
                },
            },
        },
        expected_overall_status="WARN",
        expected_gate_statuses={
            "mission-requirements": "PASS",
            "artifact-presence": "WARN",
            "ros2-build-validation": "WARN",
            "omnitorch-visual-evidence": "WARN",
            "deterministic-calculations": "PASS",
        },
        expected_min_confidence=0.70,
        expected_max_confidence=0.95,
        expected_blocker_count=0,
    ),
    GoldenStandardCase(
        id="GS-ROVER-002",
        name="Palm-sized rover missing deterministic calculations",
        description=(
            "A rover mission without calculator context should remain blocked "
            "because rover missions require deterministic mobility/power checks."
        ),
        payload={
            "mission_text": (
                "Design a palm-sized autonomous rover with ROS2, camera perception, "
                "battery power, Fusion 360 CAD, and validation gates."
            )
        },
        expected_overall_status="BLOCKED",
        expected_gate_statuses={
            "mission-requirements": "PASS",
            "artifact-presence": "WARN",
            "ros2-build-validation": "WARN",
            "omnitorch-visual-evidence": "WARN",
            "deterministic-calculations": "BLOCKED",
        },
        expected_min_confidence=0.20,
        expected_max_confidence=0.60,
        expected_blocker_count=2,
    ),
        GoldenStandardCase(
        id="GS-DRONE-001",
        name="Quadcopter drone with sizing calculation warning",
        description=(
            "A quadcopter mission with deterministic sizing context should avoid "
            "being blocked, but should warn when estimated flight time is short."
        ),
        payload={
            "mission_text": (
                "Design a quadcopter drone with Fusion 360 CAD, ROS2 validation, "
                "camera payload, battery power, and OMNITorch visual review."
            ),
            "context": {
                "drone_sizing": {
                    "estimated_total_mass_g": 850,
                    "motor_count": 4,
                    "max_thrust_per_motor_g": 650,
                    "battery_capacity_mah": 2200,
                    "battery_voltage_v": 11.1,
                    "average_current_per_motor_a": 4.5,
                    "payload_mass_g": 120,
                }
            },
        },
        expected_overall_status="WARN",
        expected_gate_statuses={
            "mission-requirements": "PASS",
            "artifact-presence": "WARN",
            "ros2-build-validation": "WARN",
            "omnitorch-visual-evidence": "WARN",
            "deterministic-calculations": "WARN",
        },
        expected_min_confidence=0.60,
        expected_max_confidence=0.90,
        expected_blocker_count=0,
    ),
    GoldenStandardCase(
        id="GS-DRONE-002",
        name="Quadcopter drone missing sizing calculation",
        description=(
            "A drone mission without deterministic sizing context should remain "
            "blocked because mass, thrust, current draw, and flight time are unknown."
        ),
        payload={
            "mission_text": (
                "Design a quadcopter drone with Fusion 360 CAD, ROS2 validation, "
                "camera payload, battery power, and OMNITorch visual review."
            )
        },
        expected_overall_status="BLOCKED",
        expected_gate_statuses={
            "mission-requirements": "PASS",
            "artifact-presence": "WARN",
            "ros2-build-validation": "WARN",
            "omnitorch-visual-evidence": "WARN",
            "deterministic-calculations": "BLOCKED",
        },
        expected_min_confidence=0.20,
        expected_max_confidence=0.60,
        expected_blocker_count=2,
    ),
]