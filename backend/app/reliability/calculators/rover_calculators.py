from __future__ import annotations

from dataclasses import dataclass
import math


@dataclass
class RoverMobilityInput:
    mass_kg: float
    wheel_radius_m: float
    motor_stall_torque_nm: float
    motor_count: int
    drivetrain_efficiency: float = 0.75
    target_incline_deg: float = 10.0
    rolling_resistance_coeff: float = 0.03
    safety_factor: float = 1.5


@dataclass
class RoverMobilityResult:
    required_force_n: float
    required_wheel_torque_nm: float
    available_total_torque_nm: float
    torque_margin: float
    status: str
    warnings: list[str]


def estimate_rover_mobility(payload: RoverMobilityInput) -> RoverMobilityResult:
    warnings: list[str] = []

    if payload.mass_kg <= 0:
        raise ValueError("mass_kg must be greater than zero.")

    if payload.wheel_radius_m <= 0:
        raise ValueError("wheel_radius_m must be greater than zero.")

    if payload.motor_stall_torque_nm <= 0:
        raise ValueError("motor_stall_torque_nm must be greater than zero.")

    if payload.motor_count <= 0:
        raise ValueError("motor_count must be greater than zero.")

    if not 0 < payload.drivetrain_efficiency <= 1:
        raise ValueError("drivetrain_efficiency must be between 0 and 1.")

    gravity = 9.81
    incline_rad = math.radians(payload.target_incline_deg)

    incline_force_n = payload.mass_kg * gravity * math.sin(incline_rad)
    rolling_force_n = (
        payload.rolling_resistance_coeff
        * payload.mass_kg
        * gravity
        * math.cos(incline_rad)
    )

    required_force_n = (incline_force_n + rolling_force_n) * payload.safety_factor
    required_wheel_torque_nm = required_force_n * payload.wheel_radius_m

    available_total_torque_nm = (
        payload.motor_stall_torque_nm
        * payload.motor_count
        * payload.drivetrain_efficiency
    )

    torque_margin = available_total_torque_nm / required_wheel_torque_nm

    status = "PASS"

    if torque_margin < 2.0:
        status = "WARN"
        warnings.append("Torque margin is below 2.0. Rover may struggle under load.")

    if torque_margin < 1.0:
        status = "FAIL"
        warnings.append("Available torque is below required torque.")

    return RoverMobilityResult(
        required_force_n=round(required_force_n, 3),
        required_wheel_torque_nm=round(required_wheel_torque_nm, 3),
        available_total_torque_nm=round(available_total_torque_nm, 3),
        torque_margin=round(torque_margin, 3),
        status=status,
        warnings=warnings,
    )