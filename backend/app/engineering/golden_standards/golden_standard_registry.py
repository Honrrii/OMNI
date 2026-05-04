from dataclasses import dataclass, field
from typing import List, Dict


@dataclass
class GoldenStandard:
    """
    Defines an official OMNI benchmark mission.

    A Golden Standard is not just an example prompt.
    It is a repeatable backend benchmark used to test whether OMNI can:
    - understand a robotics mission
    - generate the correct artifact types
    - validate calculations and engineering assumptions
    - report missing data honestly
    """

    id: str
    name: str
    domain: str
    description: str
    required_artifacts: List[str] = field(default_factory=list)
    required_calculations: List[str] = field(default_factory=list)
    required_validation_checks: List[str] = field(default_factory=list)
    expected_outputs: List[str] = field(default_factory=list)
    safety_notes: List[str] = field(default_factory=list)


GOLDEN_STANDARDS: Dict[str, GoldenStandard] = {
    "GS1": GoldenStandard(
        id="GS1",
        name="Quadcopter Engineering Pipeline",
        domain="aerial_robotics",
        description=(
            "A grounded quadcopter drone benchmark used to validate OMNI's "
            "ability to reason about aerial robotics, thrust, mass, power, "
            "electronics, materials, CAD, ROS2 architecture, and safety limits."
        ),
        required_artifacts=[
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
        required_calculations=[
            "estimated_total_mass",
            "thrust_to_weight_ratio",
            "motor_thrust_margin",
            "battery_current_draw",
            "estimated_flight_time",
            "payload_margin",
            "center_of_mass_assessment",
        ],
        required_validation_checks=[
            "mass_budget_exists",
            "thrust_to_weight_ratio_exists",
            "thrust_to_weight_ratio_reasonable",
            "battery_capacity_exists",
            "flight_time_estimate_exists",
            "electronics_plan_exists",
            "materials_are_justified",
            "safety_limitations_stated",
            "assumptions_are_explicit",
        ],
        expected_outputs=[
            "structured mission requirements",
            "validated engineering assumptions",
            "generated CAD concept",
            "generated ROS2 plan",
            "generated KiCad planning artifact",
            "final validation summary",
        ],
        safety_notes=[
            "This benchmark is for engineering planning and simulation only.",
            "Real flight requires physical testing, certified components, and safety review.",
            "OMNI must not claim a drone design is flight-certified.",
        ],
    ),

    "GS2": GoldenStandard(
        id="GS2",
        name="Mini Autonomous Rover Engineering Pipeline",
        domain="ground_robotics",
        description=(
            "A grounded mini autonomous rover benchmark used to validate OMNI's "
            "ability to reason about ROS2, differential drive motion, sensors, "
            "motor torque, battery sizing, chassis materials, CAD, electronics, "
            "and simulation planning."
        ),
        required_artifacts=[
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
        required_calculations=[
            "estimated_total_mass",
            "wheel_radius",
            "required_motor_torque",
            "target_speed_estimate",
            "battery_runtime_estimate",
            "payload_margin",
        ],
        required_validation_checks=[
            "dimensions_exist",
            "mass_estimate_exists",
            "wheel_radius_exists",
            "motor_torque_estimate_exists",
            "battery_estimate_exists",
            "sensor_layout_exists",
            "ros2_architecture_exists",
            "simulation_plan_exists",
            "materials_are_justified",
            "assumptions_are_explicit",
        ],
        expected_outputs=[
            "structured mission requirements",
            "validated rover assumptions",
            "generated CAD concept",
            "generated ROS2 architecture",
            "generated electronics plan",
            "final validation summary",
        ],
        safety_notes=[
            "This benchmark is for educational robotics planning and simulation.",
            "Real-world operation requires testing of motors, batteries, wiring, and sensors.",
            "OMNI must report uncertainty when component data is missing.",
        ],
    ),
}


def list_golden_standards() -> List[GoldenStandard]:
    return list(GOLDEN_STANDARDS.values())


def get_golden_standard(standard_id: str) -> GoldenStandard:
    key = standard_id.upper()

    if key not in GOLDEN_STANDARDS:
        raise ValueError(f"Unknown Golden Standard ID: {standard_id}")

    return GOLDEN_STANDARDS[key]