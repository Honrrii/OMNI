from __future__ import annotations

from dataclasses import dataclass


@dataclass
class PowerBudgetInput:
    battery_voltage_v: float
    battery_capacity_mah: float
    average_current_a: float
    peak_current_a: float | None = None
    safety_factor: float = 1.25


@dataclass
class PowerBudgetResult:
    battery_energy_wh: float
    estimated_runtime_minutes: float
    safety_adjusted_current_a: float
    peak_current_a: float | None
    status: str
    warnings: list[str]


def estimate_power_budget(payload: PowerBudgetInput) -> PowerBudgetResult:
    warnings: list[str] = []

    if payload.battery_voltage_v <= 0:
        raise ValueError("battery_voltage_v must be greater than zero.")

    if payload.battery_capacity_mah <= 0:
        raise ValueError("battery_capacity_mah must be greater than zero.")

    if payload.average_current_a <= 0:
        raise ValueError("average_current_a must be greater than zero.")

    capacity_ah = payload.battery_capacity_mah / 1000.0
    battery_energy_wh = payload.battery_voltage_v * capacity_ah

    safety_adjusted_current_a = payload.average_current_a * payload.safety_factor
    runtime_hours = capacity_ah / safety_adjusted_current_a
    estimated_runtime_minutes = runtime_hours * 60.0

    status = "PASS"

    if estimated_runtime_minutes < 10:
        status = "WARN"
        warnings.append("Estimated runtime is under 10 minutes.")

    if estimated_runtime_minutes < 5:
        status = "FAIL"
        warnings.append("Estimated runtime is under 5 minutes and likely impractical.")

    if payload.peak_current_a is not None:
        if payload.peak_current_a < payload.average_current_a:
            status = "WARN"
            warnings.append("Peak current is lower than average current, which is suspicious.")

    return PowerBudgetResult(
        battery_energy_wh=round(battery_energy_wh, 3),
        estimated_runtime_minutes=round(estimated_runtime_minutes, 2),
        safety_adjusted_current_a=round(safety_adjusted_current_a, 3),
        peak_current_a=payload.peak_current_a,
        status=status,
        warnings=warnings,
    )