"""
OMNI CAD Morphology Intermediate Representation.

This module defines the structured data types that sit between a natural-language
mission prompt and the actual Fusion 360 / CadQuery geometry generator.

The morphology IR captures:
- What kind of robot this is (family)
- How the body is oriented in space (posture, Z-stack)
- How the body is segmented (head / thorax / abdomen, fuselage, hull, etc.)
- Where appendages attach and how they angle
- Hard negatives — shapes the generator must NOT produce
- A quality checklist for the morphology gate

Design rule:
This module contains ONLY data structures and pure helper functions.
No LLM calls, no file I/O, no imports from OMNI internals.
It can be imported anywhere without side effects.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Tuple


# Supported morphology families.
MORPHOLOGY_FAMILIES = [
    "insectoid_legged_robot",
    "hexapod_robot",
    "quadruped_robot",
    "tracked_rover",
    "wheeled_rover",
    "aerial_drone",
    "sensor_pod",
    "manipulator_arm",
    "sci_fi_walker",
    "generic_robotic_platform",
]

# Supported body postures.
BODY_POSTURES = [
    "standing",     # body elevated above ground on legs/stilts
    "low_slung",    # body close to ground (tanks, tracked rovers)
    "aerial",       # body not in ground contact (drones)
    "mounted",      # body fixed to a surface / wall / arm
    "flat",         # minimal height, pancake layout (simple plates)
]

# Supported symmetry strategies.
SYMMETRY_STRATEGIES = [
    "bilateral",    # left-right mirror (most legged robots)
    "radial_n",     # n-way radial (drones: 4-way, 6-way, etc.)
    "none",         # asymmetric
]


@dataclass
class BodySegment:
    """One logical section of the robot body, such as head, thorax, abdomen, hull, or fuselage."""

    name: str
    length_mm: float = 80.0
    width_mm: float = 50.0
    height_mm: float = 20.0
    z_base_mm: float = 0.0
    label: str = ""
    notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BodySegment":
        return cls(
            name=str(data.get("name", "body")),
            length_mm=float(data.get("length_mm", 80.0)),
            width_mm=float(data.get("width_mm", 50.0)),
            height_mm=float(data.get("height_mm", 20.0)),
            z_base_mm=float(data.get("z_base_mm", 0.0)),
            label=str(data.get("label", "")),
            notes=str(data.get("notes", "")),
        )


@dataclass
class Appendage:
    """One appendage: leg, arm, antenna, sensor stalk, fin, wheel module, etc."""

    name: str
    appendage_type: str
    attach_x_mm: float = 0.0
    attach_y_mm: float = 0.0
    attach_z_mm: float = 0.0
    angle_deg: float = 0.0
    tilt_deg: float = 30.0
    length_mm: float = 60.0
    width_mm: float = 8.0
    height_mm: float = 8.0
    ground_contact: bool = False
    foot_radius_mm: float = 5.0
    notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "type": self.appendage_type,
            "appendage_type": self.appendage_type,
            "attach": [self.attach_x_mm, self.attach_y_mm, self.attach_z_mm],
            "attach_x_mm": self.attach_x_mm,
            "attach_y_mm": self.attach_y_mm,
            "attach_z_mm": self.attach_z_mm,
            "angle_deg": self.angle_deg,
            "tilt_deg": self.tilt_deg,
            "length_mm": self.length_mm,
            "width_mm": self.width_mm,
            "height_mm": self.height_mm,
            "ground_contact": self.ground_contact,
            "foot_radius_mm": self.foot_radius_mm,
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Appendage":
        attach = data.get("attach", [0.0, 0.0, 0.0]) or [0.0, 0.0, 0.0]
        if not isinstance(attach, (list, tuple)) or len(attach) < 3:
            attach = [0.0, 0.0, 0.0]
        return cls(
            name=str(data.get("name", "appendage")),
            appendage_type=str(data.get("appendage_type", data.get("type", "appendage"))),
            attach_x_mm=float(data.get("attach_x_mm", attach[0])),
            attach_y_mm=float(data.get("attach_y_mm", attach[1])),
            attach_z_mm=float(data.get("attach_z_mm", attach[2])),
            angle_deg=float(data.get("angle_deg", 0.0)),
            tilt_deg=float(data.get("tilt_deg", 30.0)),
            length_mm=float(data.get("length_mm", 60.0)),
            width_mm=float(data.get("width_mm", 8.0)),
            height_mm=float(data.get("height_mm", 8.0)),
            ground_contact=bool(data.get("ground_contact", False)),
            foot_radius_mm=float(data.get("foot_radius_mm", 5.0)),
            notes=str(data.get("notes", "")),
        )


@dataclass
class AnchorPoint:
    """A named attachment / mounting point on the body."""

    name: str
    x_mm: float = 0.0
    y_mm: float = 0.0
    z_mm: float = 0.0
    purpose: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AnchorPoint":
        return cls(
            name=str(data.get("name", "anchor")),
            x_mm=float(data.get("x_mm", data.get("x", 0.0))),
            y_mm=float(data.get("y_mm", data.get("y", 0.0))),
            z_mm=float(data.get("z_mm", data.get("z", 0.0))),
            purpose=str(data.get("purpose", "")),
        )


@dataclass
class VerticalStructure:
    """Rules that govern Z-axis layout of the concept model."""

    leg_ground_clearance_mm: float = 30.0
    body_elevation_mm: float = 40.0
    legs_extend_downward: bool = True
    body_elevated_above_ground: bool = True
    use_segmented_z_heights: bool = True
    notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Optional[Dict[str, Any]]) -> "VerticalStructure":
        data = data or {}
        return cls(
            leg_ground_clearance_mm=float(data.get("leg_ground_clearance_mm", 30.0)),
            body_elevation_mm=float(data.get("body_elevation_mm", 40.0)),
            legs_extend_downward=bool(data.get("legs_extend_downward", True)),
            body_elevated_above_ground=bool(data.get("body_elevated_above_ground", True)),
            use_segmented_z_heights=bool(data.get("use_segmented_z_heights", True)),
            notes=str(data.get("notes", "")),
        )


@dataclass
class MorphologySpec:
    """Complete morphology intermediate representation for one mission."""

    morphology_family: str = "generic_robotic_platform"
    body_posture: str = "standing"
    silhouette: str = "compact-mechanical"
    symmetry_strategy: str = "bilateral"

    primary_segments: List[BodySegment] = field(default_factory=list)
    appendages: List[Appendage] = field(default_factory=list)
    appendage_count: int = 0
    anchor_points: List[AnchorPoint] = field(default_factory=list)
    vertical_structure: VerticalStructure = field(default_factory=VerticalStructure)

    fabrication_hints: List[str] = field(default_factory=list)
    allowed_primitive_shapes: List[str] = field(default_factory=list)
    hard_negatives: List[str] = field(default_factory=list)
    quality_checklist: List[str] = field(default_factory=list)
    source_mission_keywords: List[str] = field(default_factory=list)
    notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "morphology_family": self.morphology_family,
            "body_posture": self.body_posture,
            "silhouette": self.silhouette,
            "symmetry_strategy": self.symmetry_strategy,
            "appendage_count": self.appendage_count,
            "primary_segments": [segment.to_dict() for segment in self.primary_segments],
            "appendages": [appendage.to_dict() for appendage in self.appendages],
            "anchor_points": [anchor.to_dict() for anchor in self.anchor_points],
            "vertical_structure": self.vertical_structure.to_dict(),
            "fabrication_hints": list(self.fabrication_hints),
            "allowed_primitive_shapes": list(self.allowed_primitive_shapes),
            "hard_negatives": list(self.hard_negatives),
            "quality_checklist": list(self.quality_checklist),
            "source_mission_keywords": list(self.source_mission_keywords),
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MorphologySpec":
        spec = cls(
            morphology_family=str(data.get("morphology_family", "generic_robotic_platform")),
            body_posture=str(data.get("body_posture", "standing")),
            silhouette=str(data.get("silhouette", "compact-mechanical")),
            symmetry_strategy=str(data.get("symmetry_strategy", "bilateral")),
            appendage_count=int(data.get("appendage_count", 0)),
            primary_segments=[BodySegment.from_dict(x) for x in data.get("primary_segments", [])],
            appendages=[Appendage.from_dict(x) for x in data.get("appendages", [])],
            anchor_points=[AnchorPoint.from_dict(x) for x in data.get("anchor_points", [])],
            vertical_structure=VerticalStructure.from_dict(data.get("vertical_structure", {})),
            fabrication_hints=list(data.get("fabrication_hints", [])),
            allowed_primitive_shapes=list(data.get("allowed_primitive_shapes", [])),
            hard_negatives=list(data.get("hard_negatives", [])),
            quality_checklist=list(data.get("quality_checklist", [])),
            source_mission_keywords=list(data.get("source_mission_keywords", [])),
            notes=str(data.get("notes", "")),
        )
        if spec.appendage_count == 0 and spec.appendages:
            spec.appendage_count = len(spec.appendages)
        return spec

    def count_appendages(self, appendage_type: Optional[str] = None) -> int:
        if appendage_type is None:
            return len(self.appendages)
        return sum(1 for app in self.appendages if app.appendage_type == appendage_type)

    def z_span_mm(self) -> float:
        if not self.primary_segments:
            return 0.0
        z_values = [segment.z_base_mm for segment in self.primary_segments]
        return max(z_values) - min(z_values)

    def is_legged(self) -> bool:
        return self.morphology_family in {
            "insectoid_legged_robot",
            "hexapod_robot",
            "quadruped_robot",
            "sci_fi_walker",
        }
