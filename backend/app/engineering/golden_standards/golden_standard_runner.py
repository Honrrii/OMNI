from pathlib import Path
from typing import Any, Dict

from backend.app.engineering.mission_schema import EngineeringMission
from backend.app.engineering.validation_engine import validate_mission


PROJECT_ROOT = Path(__file__).resolve().parents[4]


def load_prompt(relative_path: str) -> str:
    """
    Load an official Golden Standard prompt from the examples folder.
    """

    prompt_path = PROJECT_ROOT / relative_path

    if not prompt_path.exists():
        raise FileNotFoundError(f"Prompt file not found: {prompt_path}")

    return prompt_path.read_text(encoding="utf-8").strip()


def build_gs1_mission() -> EngineeringMission:
    """
    Build the official GS1 Quadcopter benchmark mission.
    """

    return EngineeringMission(
        mission_text=load_prompt("examples/golden_standards/gs1_quadcopter/prompt.txt"),
        project_type="robotics",
        target_domain="aerial_robotics",
        requested_outputs=[
            "requirements_report",
            "mass_budget",
            "thrust_calculation_report",
            "power_and_battery_report",
            "flight_time_estimate",
            "materials_recommendation",
            "kicad_electronics_plan",
            "ros2_architecture_plan",
            "cad_concept_script",
            "validation_report",
            "provenance_record",
        ],
        requires_cad=True,
        requires_simulation=True,
        requires_fabrication_plan=False,
        requires_safety_review=True,
        requires_human_approval=True,
    )


def build_gs2_mission() -> EngineeringMission:
    """
    Build the official GS2 Autonomous Rover benchmark mission.
    """

    return EngineeringMission(
        mission_text=load_prompt("examples/golden_standards/gs2_autonomous_rover/prompt.txt"),
        project_type="robotics",
        target_domain="ground_robotics",
        requested_outputs=[
            "requirements_report",
            "mechanical_layout",
            "motor_torque_report",
            "battery_estimate",
            "sensor_layout_plan",
            "materials_recommendation",
            "kicad_electronics_plan",
            "ros2_node_architecture",
            "urdf_or_simulation_plan",
            "cad_concept_script",
            "validation_report",
            "provenance_record",
        ],
        requires_cad=True,
        requires_simulation=True,
        requires_fabrication_plan=False,
        requires_safety_review=True,
        requires_human_approval=True,
    )


def build_gs1_sample_result() -> Dict[str, Any]:
    """
    Temporary sample GS1 result.

    This is not the final OMNI generator output.
    It exists so the benchmark runner can test the Golden Standard validation path.
    """

    return {
        "artifacts": {
            "requirements_report": {},
            "mass_budget": {},
            "thrust_calculation_report": {},
            "power_and_battery_report": {},
            "flight_time_estimate": {},
            "materials_recommendation": {},
            "kicad_electronics_plan": {},
            "ros2_architecture_plan": {},
            "cad_concept_script": {},
            "validation_report": {},
            "provenance_record": {},
        },
        "calculations": {
            "estimated_total_mass": 1.2,
            "thrust_to_weight_ratio": 2.1,
            "motor_thrust_margin": "available but approximate",
            "battery_current_draw": "estimated",
            "estimated_flight_time": "8 minutes",
            "payload_margin": "estimated",
            "center_of_mass_assessment": "centered near frame midpoint",
        },
        "validation": {
            "mass_budget_exists": True,
            "thrust_to_weight_ratio_exists": True,
            "thrust_to_weight_ratio_reasonable": True,
            "battery_capacity_exists": True,
            "flight_time_estimate_exists": True,
            "electronics_plan_exists": True,
            "materials_are_justified": True,
            "safety_limitations_stated": True,
            "assumptions_are_explicit": True,
        },
    }


def build_gs2_sample_result() -> Dict[str, Any]:
    """
    Temporary sample GS2 result.

    This is not the final OMNI generator output.
    It exists so the benchmark runner can test the Golden Standard validation path.
    """

    return {
        "artifacts": {
            "requirements_report": {},
            "mechanical_layout": {},
            "motor_torque_report": {},
            "battery_estimate": {},
            "sensor_layout_plan": {},
            "materials_recommendation": {},
            "kicad_electronics_plan": {},
            "ros2_node_architecture": {},
            "urdf_or_simulation_plan": {},
            "cad_concept_script": {},
            "validation_report": {},
            "provenance_record": {},
        },
        "calculations": {
            "estimated_total_mass": 2.5,
            "wheel_radius": 0.04,
            "required_motor_torque": "estimated",
            "target_speed_estimate": "0.5 m/s",
            "battery_runtime_estimate": "45 minutes",
            "payload_margin": "estimated",
        },
        "validation": {
            "dimensions_exist": True,
            "mass_estimate_exists": True,
            "wheel_radius_exists": True,
            "motor_torque_estimate_exists": True,
            "battery_estimate_exists": True,
            "sensor_layout_exists": True,
            "ros2_architecture_exists": True,
            "simulation_plan_exists": True,
            "materials_are_justified": True,
            "assumptions_are_explicit": True,
        },
    }


def run_benchmark(name: str, mission: EngineeringMission, mission_result: Dict[str, Any]) -> Dict[str, Any]:
    """
    Run one Golden Standard benchmark through the main validation engine.
    """

    print("=" * 88)
    print(f"Running {name}")
    print("=" * 88)

    report = validate_mission(mission, mission_result)

    print(f"Overall Status: {report['status']}")
    print(f"Golden Standard ID: {report['golden_standard_id']}")
    print()

    if report.get("golden_standard_summary"):
        print(report["golden_standard_summary"])
    else:
        print("No Golden Standard summary generated.")

    print()
    return report


def main() -> None:
    """
    Run all official OMNI Golden Standard benchmark checks.
    """

    gs1_report = run_benchmark(
        name="GS1 — Quadcopter Engineering Pipeline",
        mission=build_gs1_mission(),
        mission_result=build_gs1_sample_result(),
    )

    gs2_report = run_benchmark(
        name="GS2 — Mini Autonomous Rover Engineering Pipeline",
        mission=build_gs2_mission(),
        mission_result=build_gs2_sample_result(),
    )

    print("=" * 88)
    print("Golden Standard Benchmark Summary")
    print("=" * 88)
    print(
        f"GS1: {gs1_report['golden_standard_report']['status']} "
        f"({gs1_report['golden_standard_report']['score']})"
    )
    print(
        f"GS2: {gs2_report['golden_standard_report']['status']} "
        f"({gs2_report['golden_standard_report']['score']})"
    )


if __name__ == "__main__":
    main()
