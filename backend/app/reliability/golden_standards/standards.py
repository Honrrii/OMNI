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
]