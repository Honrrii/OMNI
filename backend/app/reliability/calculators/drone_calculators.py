from __future__ import annotations

from dataclasses import dataclass


@dataclass
class DroneSizingInput:
    estimated_total_mass_g: float
    motor_count: int
    max_thrust_per_motor_g: float
    battery_capacity_mah: float
    battery_voltage_v: float
    average_current_per_motor_a: float
    payload_mass_g: float = 0.0
    target_thrust_to_weight_ratio: float = 2.0
    safety_factor: float = 1.15


@dataclass
class DroneSizingResult:
    total_mass_g: float
    total_available_thrust_g: float
    thrust_to_weight_ratio: float
    thrust_margin: float
    estimated_current_draw_a: float
    battery_energy_wh: float
    estimated_flight_time_minutes: float
    payload_fraction: float
    status: str
    warnings: list[str]


def estimate_drone_sizing(payload: DroneSizingInput) -> DroneSizingResult:
    warnings: list[str] = []

    if payload.estimated_total_mass_g <= 0:
        raise ValueError("estimated_total_mass_g must be greater than zero.")

    if payload.motor_count <= 0:
        raise ValueError("motor_count must be greater than zero.")

    if payload.max_thrust_per_motor_g <= 0:
        raise ValueError("max_thrust_per_motor_g must be greater than zero.")

    if payload.battery_capacity_mah <= 0:
        raise ValueError("battery_capacity_mah must be greater than zero.")

    if payload.battery_voltage_v <= 0:
        raise ValueError("battery_voltage_v must be greater than zero.")

    if payload.average_current_per_motor_a <= 0:
        raise ValueError("average_current_per_motor_a must be greater than zero.")

    total_mass_g = payload.estimated_total_mass_g
    total_available_thrust_g = payload.motor_count * payload.max_thrust_per_motor_g

    thrust_to_weight_ratio = total_available_thrust_g / total_mass_g
    thrust_margin = thrust_to_weight_ratio / payload.target_thrust_to_weight_ratio

    estimated_current_draw_a = (
        payload.motor_count
        * payload.average_current_per_motor_a
        * payload.safety_factor
    )

    capacity_ah = payload.battery_capacity_mah / 1000.0
    battery_energy_wh = payload.battery_voltage_v * capacity_ah
    estimated_flight_time_minutes = (capacity_ah / estimated_current_draw_a) * 60.0

    payload_fraction = payload.payload_mass_g / total_mass_g if total_mass_g else 0.0

    status = "PASS"

    if thrust_to_weight_ratio < payload.target_thrust_to_weight_ratio:
        status = "FAIL"
        warnings.append(
            "Thrust-to-weight ratio is below target. Drone may not have enough thrust margin."
        )
    elif thrust_to_weight_ratio < payload.target_thrust_to_weight_ratio * 1.2:
        status = "WARN"
        warnings.append(
            "Thrust-to-weight ratio is only slightly above target. Add thrust margin."
        )

    if estimated_flight_time_minutes < 5:
        status = "FAIL"
        warnings.append("Estimated flight time is under 5 minutes.")
    elif estimated_flight_time_minutes < 8 and status != "FAIL":
        status = "WARN"
        warnings.append("Estimated flight time is under 8 minutes.")

    if payload.payload_mass_g > 0 and payload_fraction > 0.35:
        if status != "FAIL":
            status = "WARN"
        warnings.append("Payload mass is more than 35% of total mass.")

    return DroneSizingResult(
        total_mass_g=round(total_mass_g, 3),
        total_available_thrust_g=round(total_available_thrust_g, 3),
        thrust_to_weight_ratio=round(thrust_to_weight_ratio, 3),
        thrust_margin=round(thrust_margin, 3),
        estimated_current_draw_a=round(estimated_current_draw_a, 3),
        battery_energy_wh=round(battery_energy_wh, 3),
        estimated_flight_time_minutes=round(estimated_flight_time_minutes, 2),
        payload_fraction=round(payload_fraction, 3),
        status=status,
        warnings=warnings,
    )