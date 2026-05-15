"""
backend/app/engineering/design_intent_schema.py

OMNI Morphology Engine — Design Intent Schema
==============================================
Defines the structured MorphologyPlan output format.
This is the shared contract between the Morphology Engine
and all downstream generators (Fusion 360, KiCad, ROS2, validators).

Every mission produces exactly one MorphologyPlan.
All generators consume it. No generator should guess morphology.
"""

from __future__ import annotations
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

class ProjectFamily(str, Enum):
    """Top-level robot/machine classification."""
    BIO_INSPIRED_GROUND    = "bio_inspired_ground_robot"
    WHEELED_ROVER          = "wheeled_rover"
    QUADCOPTER_DRONE       = "quadcopter_drone"
    FIXED_WING_UAV         = "fixed_wing_uav"
    VTOL_UAV               = "vtol_uav"
    ROBOT_ARM              = "robot_arm"
    SENSOR_MODULE          = "sensor_module"
    HUMANOID               = "humanoid_robot"
    AQUATIC                = "aquatic_robot"
    UNKNOWN                = "unknown"


class LocomotionType(str, Enum):
    """Primary locomotion or actuation strategy."""
    LEGGED                 = "legged_or_appendage_mounted"
    WHEELED                = "wheeled"
    TRACKED                = "tracked"
    ROTARY_WING            = "rotary_wing_rotors"
    FIXED_WING             = "fixed_wing_aerodynamic"
    HYBRID_VTOL            = "hybrid_vtol"
    MANIPULATOR            = "manipulator_joints"
    STATIC                 = "static_no_locomotion"
    UNKNOWN                = "unknown"


class ScaleClass(str, Enum):
    """Physical size classification."""
    NANO                   = "nano"          # < 5cm
    MICRO                  = "micro"         # 5–15cm
    PALM_SIZED             = "palm_sized"    # 10–20cm
    TABLETOP               = "tabletop"      # 20–50cm
    FIELD                  = "field"         # 50cm–1.5m
    LARGE                  = "large"         # > 1.5m
    UNKNOWN                = "unknown"


class MorphologyConfidence(str, Enum):
    """How confident the planner is in the resolved plan."""
    HIGH                   = "high"       # Strong keyword match, single pattern
    MEDIUM                 = "medium"     # Partial match, reasonable inference
    LOW                    = "low"        # Weak signal, fallback used
    AMBIGUOUS              = "ambiguous"  # Multiple patterns competed


# ---------------------------------------------------------------------------
# Sub-models
# ---------------------------------------------------------------------------

class BodyPlan(BaseModel):
    """
    Structural layout of the machine's physical body.
    All generators use this to name, position, and connect major assemblies.
    """
    segments: list[str] = Field(
        default_factory=list,
        description=(
            "Ordered list of major structural segments. "
            "Examples: ['head_sensor_pod', 'thorax_electronics_core', 'abdomen_battery_module'] "
            "or ['fuselage', 'port_wing', 'starboard_wing', 'empennage']."
        )
    )
    required_features: list[str] = Field(
        default_factory=list,
        description=(
            "Features that MUST appear in CAD, electronics, and ROS2 outputs. "
            "Validators will FAIL if these are absent."
        )
    )
    avoid_features: list[str] = Field(
        default_factory=list,
        description=(
            "Features that must NOT appear in any output. "
            "Validators will FAIL if these are detected. "
            "Used to prevent morphology bleed (e.g., drone arms on an insect robot)."
        )
    )
    mounting_points: list[str] = Field(
        default_factory=list,
        description=(
            "Named mechanical attachment points. "
            "Examples: appendage mounts, wing attachment ribs, servo horns, wheel hubs."
        )
    )


class ElectronicsIntent(BaseModel):
    """
    Guides KiCad generator on where electronics live and what they connect to.
    Segment names must match BodyPlan.segments entries.
    """
    primary_pcb_location: str = Field(
        default="",
        description="Which body segment hosts the main PCB/electronics core."
    )
    battery_location: str = Field(
        default="",
        description="Which body segment holds the battery module."
    )
    sensor_connectors: list[str] = Field(
        default_factory=list,
        description="Named sensor connector banks and their host segments."
    )
    actuator_connectors: list[str] = Field(
        default_factory=list,
        description="Named actuator/motor/servo connector banks and their host segments."
    )
    power_rails: list[str] = Field(
        default_factory=list,
        description="Required voltage rails (e.g., '5V logic', '7.4V motor', '3.3V sensor')."
    )


class ROS2Intent(BaseModel):
    """
    Guides ROS2 generator on node naming, topic structure, and TF frame naming.
    Frame names must reflect BodyPlan.segments for consistent URDF linkage.
    """
    base_frame: str = Field(
        default="base_link",
        description="Root TF frame. Typically 'base_link' for ground robots, 'base_link' for UAVs."
    )
    recommended_frames: list[str] = Field(
        default_factory=list,
        description=(
            "TF frames derived from body segments. "
            "Examples: ['head_sensor_pod_link', 'thorax_link', 'left_front_appendage_link']."
        )
    )
    recommended_nodes: list[str] = Field(
        default_factory=list,
        description=(
            "ROS2 node names appropriate for this morphology. "
            "Examples: ['locomotion_controller', 'head_camera_node', 'battery_monitor']."
        )
    )
    recommended_topics: list[str] = Field(
        default_factory=list,
        description=(
            "ROS2 topic names appropriate for this morphology. "
            "Examples: ['/cmd_vel', '/head_camera/image_raw', '/battery_state']."
        )
    )


# ---------------------------------------------------------------------------
# Top-level MorphologyPlan
# ---------------------------------------------------------------------------

class MorphologyPlan(BaseModel):
    """
    OMNI Morphology Plan — the shared physical intent contract.

    Produced by: morphology_planner.py
    Consumed by: fusion360_script_generator, kicad_project_generator,
                 ros2_package_generator, export_manager, validators.

    Written to: artifacts/morphology_plan.json in every mission export.
    """

    # Identity
    morphology_id: str = Field(
        description=(
            "Unique slug for this morphology. "
            "Examples: 'segmented_insect_robot', 'fixed_wing_uav', 'wheeled_rover'."
        )
    )
    project_family: ProjectFamily = Field(
        description="Top-level machine classification."
    )
    display_name: str = Field(
        default="",
        description="Human-readable name for reports and UI display."
    )
    description: str = Field(
        default="",
        description="One-sentence description of this morphology for report headers."
    )

    # Physical properties
    scale: ScaleClass = Field(
        default=ScaleClass.UNKNOWN,
        description="Physical size classification."
    )
    locomotion_type: LocomotionType = Field(
        default=LocomotionType.UNKNOWN,
        description="Primary locomotion strategy."
    )

    # Structural plan
    body_plan: BodyPlan = Field(
        default_factory=BodyPlan,
        description="Structural layout — segments, features, mounts."
    )

    # Generator-specific intent
    electronics_intent: ElectronicsIntent = Field(
        default_factory=ElectronicsIntent,
        description="Guides KiCad generator on electronics placement."
    )
    ros2_intent: ROS2Intent = Field(
        default_factory=ROS2Intent,
        description="Guides ROS2 generator on nodes, topics, and TF frames."
    )

    # Planner metadata
    confidence: MorphologyConfidence = Field(
        default=MorphologyConfidence.LOW,
        description="Planner's confidence in this resolution."
    )
    matched_pattern: str = Field(
        default="",
        description="Name of the pattern from morphology_pattern_library that was matched."
    )
    matched_keywords: list[str] = Field(
        default_factory=list,
        description="Keywords from the mission text that triggered this pattern."
    )
    warnings: list[str] = Field(
        default_factory=list,
        description=(
            "Non-fatal planner warnings. "
            "Examples: ambiguous scale, multiple competing patterns, "
            "missing locomotion signal."
        )
    )

    # -------------------------------------------------------------------
    # Convenience helpers used by generators
    # -------------------------------------------------------------------

    def to_fusion_context(self) -> dict:
        """
        Returns a flat dict for injection into the Fusion 360 script generator.
        Replaces the old 'project_type' string with rich morphology context.
        """
        return {
            "morphology_id":    self.morphology_id,
            "project_family":   self.project_family.value,
            "display_name":     self.display_name,
            "scale":            self.scale.value,
            "locomotion_type":  self.locomotion_type.value,
            "body_segments":    self.body_plan.segments,
            "required_features": self.body_plan.required_features,
            "avoid_features":   self.body_plan.avoid_features,
            "mounting_points":  self.body_plan.mounting_points,
        }

    def to_kicad_context(self) -> dict:
        """
        Returns a flat dict for injection into the KiCad project generator.
        """
        return {
            "morphology_id":        self.morphology_id,
            "project_family":       self.project_family.value,
            "primary_pcb_location": self.electronics_intent.primary_pcb_location,
            "battery_location":     self.electronics_intent.battery_location,
            "sensor_connectors":    self.electronics_intent.sensor_connectors,
            "actuator_connectors":  self.electronics_intent.actuator_connectors,
            "power_rails":          self.electronics_intent.power_rails,
            "body_segments":        self.body_plan.segments,
        }

    def to_ros2_context(self) -> dict:
        """
        Returns a flat dict for injection into the ROS2 package generator.
        """
        return {
            "morphology_id":        self.morphology_id,
            "project_family":       self.project_family.value,
            "base_frame":           self.ros2_intent.base_frame,
            "recommended_frames":   self.ros2_intent.recommended_frames,
            "recommended_nodes":    self.ros2_intent.recommended_nodes,
            "recommended_topics":   self.ros2_intent.recommended_topics,
            "locomotion_type":      self.locomotion_type.value,
        }

    def to_validator_context(self) -> dict:
        """
        Returns the full validation contract for downstream validators.
        Validators use required_features and avoid_features for PASS/FAIL checks.
        """
        return {
            "morphology_id":        self.morphology_id,
            "project_family":       self.project_family.value,
            "body_segments":        self.body_plan.segments,
            "required_features":    self.body_plan.required_features,
            "avoid_features":       self.body_plan.avoid_features,
            "mounting_points":      self.body_plan.mounting_points,
            "confidence":           self.confidence.value,
            "warnings":             self.warnings,
        }