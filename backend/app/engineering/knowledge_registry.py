"""
OMNI Phase 17A — Engineering Knowledge Registry foundation.

Deterministic, local, definition-only.
No LLM calls. No internet. No computation. No simulation launched.
No engineering validation implied. No fabrication claims.
Concept-stage reference only.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Safety wording injected into every entry's safety_notes
# ---------------------------------------------------------------------------

_CONCEPT_STAGE_NOTE = (
    "Concept-stage reference only. "
    "No engineering validation implied. "
    "No simulation launched. "
    "No fabrication claims. "
    "Do not use for design decisions without independent engineering review."
)

# ---------------------------------------------------------------------------
# Registry entries
# ---------------------------------------------------------------------------

_REGISTRY: List[Dict[str, Any]] = [
    # ── mechanical ──────────────────────────────────────────────────────────
    {
        "id": "mass_budget",
        "domain": "mechanical",
        "title": "Mass budget",
        "description": (
            "Concept-stage mass allocation across subsystems. "
            "Tracks estimated component masses against a target total. "
            "Abstract reference only — actual masses depend on detailed design."
        ),
        "required_inputs": ["target_mass_kg", "subsystem_mass_estimates"],
        "optional_inputs": ["margin_percent"],
        "computed_outputs": ["total_estimated_mass_kg", "margin_kg", "budget_status"],
        "unit_expectations": {"target_mass_kg": "kg", "subsystem_mass_estimates": "kg each"},
        "assumptions": [
            "Subsystem estimates are order-of-magnitude concept values.",
            "No detailed CAD geometry or material density calculation performed.",
            "Margin accounts for unestimated fasteners and wiring.",
        ],
        "missing_input_behavior": "do_not_compute",
        "confidence_rules": [
            "Confidence is LOW without detailed subsystem breakdowns.",
            "Concept-stage estimates may differ substantially from measured values.",
        ],
        "safety_notes": [
            _CONCEPT_STAGE_NOTE,
            "Mass budget alone does not determine structural adequacy.",
        ],
        "blocked_claims": [
            "validated", "certified", "safe", "airworthy", "flight-ready",
            "fabrication-ready", "deployment-ready", "production-ready",
        ],
    },
    {
        "id": "center_of_mass_check",
        "domain": "mechanical",
        "title": "Center of mass check",
        "description": (
            "Concept-stage estimate of system center of mass location "
            "relative to a reference point. "
            "Abstract reference only — no FEA or CAD geometry used."
        ),
        "required_inputs": ["subsystem_mass_estimates", "subsystem_positions_m"],
        "optional_inputs": ["reference_point_m"],
        "computed_outputs": ["estimated_com_x_m", "estimated_com_y_m", "estimated_com_z_m"],
        "unit_expectations": {"subsystem_positions_m": "m from reference"},
        "assumptions": [
            "Subsystem positions are concept-level approximations.",
            "No detailed geometry or density distribution modeled.",
        ],
        "missing_input_behavior": "do_not_compute",
        "confidence_rules": [
            "Confidence is LOW at concept stage.",
            "Actual COM depends on detailed component placement.",
        ],
        "safety_notes": [
            _CONCEPT_STAGE_NOTE,
            "COM estimate does not constitute a stability analysis.",
        ],
        "blocked_claims": [
            "validated", "certified", "safe", "airworthy", "flight-ready",
            "fabrication-ready", "deployment-ready", "production-ready",
        ],
    },
    # ── electrical ──────────────────────────────────────────────────────────
    {
        "id": "power_budget",
        "domain": "electrical",
        "title": "Power budget",
        "description": (
            "Concept-stage electrical power allocation across subsystems. "
            "Sums estimated consumption against a supply capacity. "
            "Abstract reference only — actual draw depends on detailed design."
        ),
        "required_inputs": ["supply_capacity_w", "subsystem_power_estimates_w"],
        "optional_inputs": ["efficiency_factor", "margin_percent"],
        "computed_outputs": ["total_estimated_draw_w", "margin_w", "budget_status"],
        "unit_expectations": {"supply_capacity_w": "W", "subsystem_power_estimates_w": "W each"},
        "assumptions": [
            "Estimates are peak or average concept values, not measured.",
            "Efficiency factor is a placeholder unless specified.",
            "No circuit simulation performed.",
        ],
        "missing_input_behavior": "do_not_compute",
        "confidence_rules": [
            "Confidence is LOW without hardware datasheets.",
            "Actual draw may differ under load or thermal conditions.",
        ],
        "safety_notes": [
            _CONCEPT_STAGE_NOTE,
            "Power budget does not substitute for electrical safety review.",
        ],
        "blocked_claims": [
            "validated", "certified", "safe", "airworthy", "flight-ready",
            "fabrication-ready", "deployment-ready", "production-ready",
        ],
    },
    {
        "id": "battery_runtime_estimate",
        "domain": "electrical",
        "title": "Battery runtime estimate",
        "description": (
            "Concept-stage estimate of battery runtime from capacity and "
            "average power draw. "
            "Abstract reference only — no circuit simulation performed."
        ),
        "required_inputs": ["battery_capacity_wh", "average_power_draw_w"],
        "optional_inputs": ["efficiency_factor", "depth_of_discharge_fraction"],
        "computed_outputs": ["estimated_runtime_h", "estimated_runtime_min"],
        "unit_expectations": {
            "battery_capacity_wh": "Wh",
            "average_power_draw_w": "W",
        },
        "assumptions": [
            "Runtime = (capacity × DoD × efficiency) / average_draw.",
            "Default DoD = 0.8, default efficiency = 0.9 if not provided.",
            "No battery chemistry or temperature modeled.",
        ],
        "missing_input_behavior": "do_not_compute",
        "confidence_rules": [
            "Confidence is LOW without hardware characterization.",
            "Actual runtime varies with temperature, load profile, and cell age.",
        ],
        "safety_notes": [
            _CONCEPT_STAGE_NOTE,
            "Runtime estimate does not account for battery degradation or thermal cutoff.",
        ],
        "blocked_claims": [
            "validated", "certified", "safe", "airworthy", "flight-ready",
            "fabrication-ready", "deployment-ready", "production-ready",
        ],
    },
    # ── robotics ────────────────────────────────────────────────────────────
    {
        "id": "torque_required_basic",
        "domain": "robotics",
        "title": "Torque required (basic)",
        "description": (
            "Concept-stage estimate of joint torque required to support a load "
            "at a given moment arm. "
            "Abstract reference only — no dynamics simulation performed."
        ),
        "required_inputs": ["load_kg", "moment_arm_m"],
        "optional_inputs": ["gravity_m_s2", "safety_multiplier"],
        "computed_outputs": ["required_torque_nm"],
        "unit_expectations": {"load_kg": "kg", "moment_arm_m": "m", "required_torque_nm": "Nm"},
        "assumptions": [
            "Static load only — no dynamic or acceleration loads modeled.",
            "Default gravity = 9.81 m/s².",
            "Default safety_multiplier = 1.0 unless provided.",
        ],
        "missing_input_behavior": "do_not_compute",
        "confidence_rules": [
            "Confidence is LOW — ignores friction, inertia, and dynamic effects.",
            "Actual required torque under motion may be substantially higher.",
        ],
        "safety_notes": [
            _CONCEPT_STAGE_NOTE,
            "Torque estimate does not constitute actuator selection guidance.",
        ],
        "blocked_claims": [
            "validated", "certified", "safe", "airworthy", "flight-ready",
            "fabrication-ready", "deployment-ready", "production-ready",
        ],
    },
    {
        "id": "urdf_visual_readiness",
        "domain": "robotics",
        "title": "URDF visual readiness",
        "description": (
            "Checks concept-stage readiness of a robot description for "
            "visual URDF export. "
            "Assesses whether required link and joint metadata are present. "
            "No URDF file generated or executed."
        ),
        "required_inputs": ["link_names", "joint_definitions"],
        "optional_inputs": ["mesh_references", "material_definitions"],
        "computed_outputs": ["readiness_score", "missing_fields", "readiness_status"],
        "unit_expectations": {},
        "assumptions": [
            "Readiness is assessed from metadata presence only.",
            "No URDF parser, RViz, or simulation launched.",
            "Mesh references are not fetched or verified.",
        ],
        "missing_input_behavior": "do_not_compute",
        "confidence_rules": [
            "Confidence is LOW — structural correctness requires URDF parsing.",
            "Readiness score is a concept-stage checklist, not a parse result.",
        ],
        "safety_notes": [
            _CONCEPT_STAGE_NOTE,
            "URDF readiness does not guarantee a parseable or simulatable description.",
        ],
        "blocked_claims": [
            "validated", "certified", "safe", "airworthy", "flight-ready",
            "fabrication-ready", "deployment-ready", "production-ready",
        ],
    },
    {
        "id": "sensor_coverage_check",
        "domain": "robotics",
        "title": "Sensor coverage check",
        "description": (
            "Concept-stage assessment of whether declared sensors provide "
            "nominal coverage for a stated mission area. "
            "Abstract reference only — no sensor simulation or ray casting performed."
        ),
        "required_inputs": ["sensor_list", "mission_area_description"],
        "optional_inputs": ["fov_degrees", "range_m"],
        "computed_outputs": ["coverage_assessment", "gap_warnings"],
        "unit_expectations": {"fov_degrees": "degrees", "range_m": "m"},
        "assumptions": [
            "Coverage is assessed qualitatively from sensor types listed.",
            "No ray casting, occlusion, or environment modeling performed.",
            "Sensor positions are conceptual, not from a placed model.",
        ],
        "missing_input_behavior": "do_not_compute",
        "confidence_rules": [
            "Confidence is LOW — actual coverage depends on placement and environment.",
            "Qualitative assessment only.",
        ],
        "safety_notes": [
            _CONCEPT_STAGE_NOTE,
            "Coverage check does not substitute for sensor simulation or field testing.",
        ],
        "blocked_claims": [
            "validated", "certified", "safe", "airworthy", "flight-ready",
            "fabrication-ready", "deployment-ready", "production-ready",
        ],
    },
    # ── aerospace_concept ───────────────────────────────────────────────────
    {
        "id": "thrust_to_weight_ratio",
        "domain": "aerospace_concept",
        "title": "Thrust-to-weight ratio",
        "description": (
            "Concept-stage estimate of thrust-to-weight ratio for a UAV or "
            "aerial platform concept. "
            "Abstract reference only — no aerodynamic or CFD simulation performed. "
            "Does not imply airworthiness."
        ),
        "required_inputs": ["total_thrust_n", "total_mass_kg"],
        "optional_inputs": ["gravity_m_s2"],
        "computed_outputs": ["thrust_to_weight_ratio", "hover_margin_ratio"],
        "unit_expectations": {"total_thrust_n": "N", "total_mass_kg": "kg"},
        "assumptions": [
            "Default gravity = 9.81 m/s².",
            "No aerodynamic effects, ground effect, or air density modeled.",
            "Thrust values are concept estimates, not measured.",
        ],
        "missing_input_behavior": "do_not_compute",
        "confidence_rules": [
            "Confidence is LOW — actual T/W depends on propeller efficiency and motor characterization.",
            "Concept-stage T/W is illustrative only.",
        ],
        "safety_notes": [
            _CONCEPT_STAGE_NOTE,
            "T/W ratio does not constitute a flight performance analysis.",
            "Does not imply airworthiness or flight readiness.",
        ],
        "blocked_claims": [
            "validated", "certified", "safe", "airworthy", "flight-ready",
            "fabrication-ready", "deployment-ready", "production-ready",
        ],
    },
    {
        "id": "thermal_risk_basic",
        "domain": "aerospace_concept",
        "title": "Thermal risk (basic)",
        "description": (
            "Concept-stage qualitative assessment of thermal risk from "
            "high-power components. "
            "Flags components that typically require thermal management. "
            "No thermal simulation or FEA performed."
        ),
        "required_inputs": ["component_list", "power_dissipation_estimates_w"],
        "optional_inputs": ["ambient_temp_c", "cooling_method"],
        "computed_outputs": ["thermal_risk_level", "flagged_components"],
        "unit_expectations": {"power_dissipation_estimates_w": "W", "ambient_temp_c": "°C"},
        "assumptions": [
            "Risk is assessed qualitatively from power estimates.",
            "No conduction, convection, or radiation modeled.",
            "Flagging thresholds are conservative concept-stage heuristics.",
        ],
        "missing_input_behavior": "do_not_compute",
        "confidence_rules": [
            "Confidence is LOW — actual thermal behavior requires simulation or measurement.",
            "Qualitative risk only.",
        ],
        "safety_notes": [
            _CONCEPT_STAGE_NOTE,
            "Thermal risk assessment does not substitute for thermal simulation or testing.",
        ],
        "blocked_claims": [
            "validated", "certified", "safe", "airworthy", "flight-ready",
            "fabrication-ready", "deployment-ready", "production-ready",
        ],
    },
    # ── simulation ──────────────────────────────────────────────────────────
    {
        "id": "gazebo_physics_readiness",
        "domain": "simulation",
        "title": "Gazebo physics readiness",
        "description": (
            "Concept-stage readiness assessment for Gazebo physics simulation. "
            "Checks whether required physics parameters are declared. "
            "No Gazebo instance launched or connected."
        ),
        "required_inputs": ["mass_kg", "inertia_tensor", "collision_geometry_type"],
        "optional_inputs": ["friction_coefficients", "damping_coefficients"],
        "computed_outputs": ["readiness_score", "missing_params", "readiness_status"],
        "unit_expectations": {"mass_kg": "kg", "inertia_tensor": "kg·m²"},
        "assumptions": [
            "Readiness assessed from metadata presence only.",
            "No Gazebo, ROS 2, or physics engine contacted.",
            "Inertia values are conceptual estimates.",
        ],
        "missing_input_behavior": "do_not_compute",
        "confidence_rules": [
            "Confidence is LOW — physics correctness requires simulation runs.",
            "Concept-stage checklist only.",
        ],
        "safety_notes": [
            _CONCEPT_STAGE_NOTE,
            "Physics readiness does not guarantee stable simulation behavior.",
        ],
        "blocked_claims": [
            "validated", "certified", "safe", "airworthy", "flight-ready",
            "fabrication-ready", "deployment-ready", "production-ready",
        ],
    },
    {
        "id": "simulation_readiness",
        "domain": "simulation",
        "title": "Simulation readiness",
        "description": (
            "Concept-stage overall readiness assessment for robot or platform simulation. "
            "Aggregates URDF visual readiness and Gazebo physics readiness signals. "
            "No simulation launched."
        ),
        "required_inputs": ["platform_description"],
        "optional_inputs": ["urdf_readiness_score", "gazebo_readiness_score"],
        "computed_outputs": ["overall_readiness_level", "readiness_notes"],
        "unit_expectations": {},
        "assumptions": [
            "Readiness is a qualitative aggregation of available signals.",
            "No simulation environment contacted.",
            "Score is concept-stage only.",
        ],
        "missing_input_behavior": "do_not_compute",
        "confidence_rules": [
            "Confidence is LOW without individual readiness scores.",
            "Simulation readiness does not guarantee that simulation will succeed.",
        ],
        "safety_notes": [
            _CONCEPT_STAGE_NOTE,
            "Simulation readiness does not substitute for actual simulation runs.",
        ],
        "blocked_claims": [
            "validated", "certified", "safe", "airworthy", "flight-ready",
            "fabrication-ready", "deployment-ready", "production-ready",
        ],
    },
    # ── safety ──────────────────────────────────────────────────────────────
    {
        "id": "safety_margin_review",
        "domain": "safety",
        "title": "Safety margin review",
        "description": (
            "Concept-stage review of declared safety margins across mechanical, "
            "electrical, and operational parameters. "
            "Flags margins below concept-stage thresholds. "
            "No engineering validation performed."
        ),
        "required_inputs": ["declared_margins"],
        "optional_inputs": ["target_margin_percent", "domain_scope"],
        "computed_outputs": ["margin_review_summary", "flagged_margins", "review_status"],
        "unit_expectations": {"declared_margins": "percent or ratio per parameter"},
        "assumptions": [
            "Margins are declared by the designer, not computed from analysis.",
            "Thresholds are conservative concept-stage heuristics.",
            "No simulation, FEA, or test data used.",
        ],
        "missing_input_behavior": "do_not_compute",
        "confidence_rules": [
            "Confidence is LOW — actual safety margins require engineering analysis.",
            "Concept-stage flagging only.",
        ],
        "safety_notes": [
            _CONCEPT_STAGE_NOTE,
            "Safety margin review does not constitute a safety case or hazard analysis.",
            "Does not imply that the system is safe for operation.",
        ],
        "blocked_claims": [
            "validated", "certified", "safe", "airworthy", "flight-ready",
            "fabrication-ready", "deployment-ready", "production-ready",
        ],
    },
]

# Build lookup index
_REGISTRY_BY_ID: Dict[str, Dict[str, Any]] = {e["id"]: e for e in _REGISTRY}


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def get_engineering_knowledge_registry() -> List[Dict[str, Any]]:
    """Return all registry entries (read-only copies)."""
    return [dict(e) for e in _REGISTRY]


def get_engineering_knowledge_entry(entry_id: str) -> Optional[Dict[str, Any]]:
    """
    Return a single registry entry by id, or None if not found.
    Returns a read-only copy.
    """
    entry = _REGISTRY_BY_ID.get(entry_id)
    return dict(entry) if entry is not None else None


def list_engineering_knowledge_entries(
    domain: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Return all entries, optionally filtered by domain.
    Returns read-only copies.
    """
    if domain is None:
        return [dict(e) for e in _REGISTRY]
    return [dict(e) for e in _REGISTRY if e["domain"] == domain]


def list_engineering_domains() -> List[str]:
    """Return a sorted list of unique domain names present in the registry."""
    return sorted({e["domain"] for e in _REGISTRY})


def select_engineering_knowledge_for_platform(
    platform_intent: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Return the subset of entries relevant to the given platform intent.

    Platform classification:
    - UAV / aerial:       thrust_to_weight_ratio, mass_budget, power_budget,
                          battery_runtime_estimate, thermal_risk_basic,
                          simulation_readiness, safety_margin_review
    - Rover / ground:     torque_required_basic, mass_budget, power_budget,
                          battery_runtime_estimate, sensor_coverage_check,
                          simulation_readiness, safety_margin_review
    - Manipulator / arm:  torque_required_basic, mass_budget, power_budget,
                          urdf_visual_readiness, gazebo_physics_readiness,
                          simulation_readiness, safety_margin_review
    - Unknown / None:     mass_budget, power_budget, sensor_coverage_check,
                          safety_margin_review, simulation_readiness
    """
    p = (platform_intent or "").lower().strip()

    if any(kw in p for kw in ("drone", "uav", "quadcopter", "aerial", "multirotor", "vtol", "rotor")):
        ids = [
            "thrust_to_weight_ratio",
            "mass_budget",
            "power_budget",
            "battery_runtime_estimate",
            "thermal_risk_basic",
            "simulation_readiness",
            "safety_margin_review",
        ]
    elif any(kw in p for kw in ("rover", "crawler", "ground", "wheeled", "tracked")):
        ids = [
            "torque_required_basic",
            "mass_budget",
            "power_budget",
            "battery_runtime_estimate",
            "sensor_coverage_check",
            "simulation_readiness",
            "safety_margin_review",
        ]
    elif any(kw in p for kw in ("arm", "manipulator", "gripper")):
        ids = [
            "torque_required_basic",
            "mass_budget",
            "power_budget",
            "urdf_visual_readiness",
            "gazebo_physics_readiness",
            "simulation_readiness",
            "safety_margin_review",
        ]
    else:
        ids = [
            "mass_budget",
            "power_budget",
            "sensor_coverage_check",
            "safety_margin_review",
            "simulation_readiness",
        ]

    return [dict(_REGISTRY_BY_ID[i]) for i in ids if i in _REGISTRY_BY_ID]
