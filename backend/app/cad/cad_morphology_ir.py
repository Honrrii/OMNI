"""
OMNI CAD Morphology Intermediate Representation.

This module defines the structured data types that sit between a natural-language
mission prompt and the actual Fusion 360 / CadQuery geometry generator.

Design rule:
This module contains only data structures and pure helper functions.
No LLM calls, no file I/O, no imports from OMNI internals.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List


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
    "wall_climbing_robot",
    "serpentine_robot",
    "aquatic_glider_robot",
    "winged_uav",
    "crustacean_walker",
    "cephalopod_soft_robot",
    "armored_rover",
    "jumping_robot",
    "biomorphic_micro_uav",
    "hybrid_creature_robot",
    "biomorphic_generic_robot",
    "generic_robotic_platform",
]

BODY_POSTURES = [
    "standing",
    "low_slung",
    "aerial",
    "mounted",
    "flat",
    "segmented_chain",
    "aquatic",
    "crouched",
    "soft_radial",
]

SYMMETRY_STRATEGIES = [
    "bilateral",
    "radial_n",
    "none",
]


@dataclass
class BodySegment:
    """One logical section of the robot body."""

    name: str
    length_mm: float = 80.0
    width_mm: float = 50.0
    height_mm: float = 20.0
    z_base_mm: float = 0.0
    label: str = ""
    notes: str = ""


@dataclass
class Appendage:
    """One appendage: leg, wing, fin, arm, antenna, sensor stalk, etc."""

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


@dataclass
class AnchorPoint:
    """A named attachment or mounting point on the body."""

    name: str
    x_mm: float = 0.0
    y_mm: float = 0.0
    z_mm: float = 0.0
    purpose: str = ""


@dataclass
class VerticalStructure:
    """Rules governing Z-axis height layout."""

    leg_ground_clearance_mm: float = 30.0
    body_elevation_mm: float = 40.0
    legs_extend_downward: bool = True
    body_elevated_above_ground: bool = True
    use_segmented_z_heights: bool = True
    notes: str = ""


@dataclass
class MorphologySpec:
    """
    Complete morphology intermediate representation for one mission.

    The CAD generator consumes this instead of reasoning directly from raw
    mission text. This helps prevent flat-plate, drone, rover, or insect-only
    fallbacks when the prompt requests a different creature-inspired form.
    """

    # Identity
    morphology_family: str = "generic_robotic_platform"
    body_posture: str = "standing"
    silhouette: str = "compact-mechanical"
    symmetry_strategy: str = "bilateral"

    # Body
    primary_segments: List[BodySegment] = field(default_factory=list)

    # Appendages
    appendages: List[Appendage] = field(default_factory=list)
    appendage_count: int = 0

    # Anchor points
    anchor_points: List[AnchorPoint] = field(default_factory=list)

    # Vertical rules
    vertical_structure: VerticalStructure = field(default_factory=VerticalStructure)

    # Fabrication / primitive hints
    fabrication_hints: List[str] = field(default_factory=list)
    allowed_primitive_shapes: List[str] = field(default_factory=list)

    # Hard negatives
    hard_negatives: List[str] = field(default_factory=list)

    # Biomorphic / creature-inspired design context
    morphology_archetype: str = ""
    bio_inspiration: Dict[str, Any] = field(default_factory=dict)
    locomotion_strategy: Dict[str, Any] = field(default_factory=dict)
    specialized_features: List[str] = field(default_factory=list)
    cad_rules: List[str] = field(default_factory=list)

    # Quality / metadata
    quality_checklist: List[str] = field(default_factory=list)
    source_mission_keywords: List[str] = field(default_factory=list)
    notes: str = ""

    # ─────────────────────────────────────────────────────────
    # Compatibility / query helpers used by quality gates
    # ─────────────────────────────────────────────────────────
    def count_appendages(self, appendage_type: str | None = None) -> int:
        """
        Count appendages, optionally filtering by appendage_type.

        Example:
            spec.count_appendages("leg")
        """
        if appendage_type is None:
            return len(self.appendages)

        target = str(appendage_type or "").lower()
        return sum(
            1
            for appendage in self.appendages
            if str(appendage.appendage_type or "").lower() == target
        )

    def count_ground_contact_appendages(self, appendage_type: str | None = None) -> int:
        """
        Count appendages that have ground_contact=True, optionally filtered by type.
        """
        if appendage_type is None:
            return sum(1 for appendage in self.appendages if appendage.ground_contact)

        target = str(appendage_type or "").lower()
        return sum(
            1
            for appendage in self.appendages
            if appendage.ground_contact
            and str(appendage.appendage_type or "").lower() == target
        )

    def segment_names(self) -> List[str]:
        """Return body segment names as lowercase strings."""
        return [str(segment.name or "").lower() for segment in self.primary_segments]

    def has_segment(self, name: str) -> bool:
        """Return True if a body segment with this name exists."""
        target = str(name or "").lower()
        return any(target == segment_name for segment_name in self.segment_names())

    def has_segment_containing(self, token: str) -> bool:
        """Return True if any segment name contains the requested token."""
        target = str(token or "").lower()
        return any(target in segment_name for segment_name in self.segment_names())

    def z_span_mm(self) -> float:
        """Return the Z-base span across body segments."""
        if not self.primary_segments:
            return 0.0
        z_values = [float(segment.z_base_mm) for segment in self.primary_segments]
        return max(z_values) - min(z_values)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to a plain dict for JSON export and prompt injection."""

        def _seg(s: BodySegment) -> Dict[str, Any]:
            return {
                "name": s.name,
                "length_mm": s.length_mm,
                "width_mm": s.width_mm,
                "height_mm": s.height_mm,
                "z_base_mm": s.z_base_mm,
                "label": s.label,
                "notes": s.notes,
            }

        def _app(a: Appendage) -> Dict[str, Any]:
            return {
                "name": a.name,
                "type": a.appendage_type,
                "appendage_type": a.appendage_type,
                "attach": [a.attach_x_mm, a.attach_y_mm, a.attach_z_mm],
                "attach_x_mm": a.attach_x_mm,
                "attach_y_mm": a.attach_y_mm,
                "attach_z_mm": a.attach_z_mm,
                "angle_deg": a.angle_deg,
                "tilt_deg": a.tilt_deg,
                "length_mm": a.length_mm,
                "width_mm": a.width_mm,
                "height_mm": a.height_mm,
                "ground_contact": a.ground_contact,
                "foot_radius_mm": a.foot_radius_mm,
                "notes": a.notes,
            }

        def _anc(p: AnchorPoint) -> Dict[str, Any]:
            return {
                "name": p.name,
                "x_mm": p.x_mm,
                "y_mm": p.y_mm,
                "z_mm": p.z_mm,
                "purpose": p.purpose,
            }

        vs = self.vertical_structure

        return {
            "morphology_family": self.morphology_family,
            "body_posture": self.body_posture,
            "silhouette": self.silhouette,
            "symmetry_strategy": self.symmetry_strategy,
            "appendage_count": self.appendage_count,
            "primary_segments": [_seg(s) for s in self.primary_segments],
            "appendages": [_app(a) for a in self.appendages],
            "anchor_points": [_anc(p) for p in self.anchor_points],
            "vertical_structure": {
                "leg_ground_clearance_mm": vs.leg_ground_clearance_mm,
                "body_elevation_mm": vs.body_elevation_mm,
                "legs_extend_downward": vs.legs_extend_downward,
                "body_elevated_above_ground": vs.body_elevated_above_ground,
                "use_segmented_z_heights": vs.use_segmented_z_heights,
                "notes": vs.notes,
            },
            "fabrication_hints": self.fabrication_hints,
            "allowed_primitive_shapes": self.allowed_primitive_shapes,
            "hard_negatives": self.hard_negatives,
            "morphology_archetype": self.morphology_archetype,
            "bio_inspiration": self.bio_inspiration,
            "locomotion_strategy": self.locomotion_strategy,
            "specialized_features": self.specialized_features,
            "cad_rules": self.cad_rules,
            "quality_checklist": self.quality_checklist,
            "source_mission_keywords": self.source_mission_keywords,
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MorphologySpec":
        """Reconstruct from a plain dict loaded from JSON."""

        def _num(value: Any, fallback: float) -> float:
            try:
                return float(value)
            except Exception:
                return fallback

        def _bool(value: Any, fallback: bool = False) -> bool:
            if isinstance(value, bool):
                return value
            if value is None:
                return fallback
            return str(value).strip().lower() in {"true", "1", "yes", "y"}

        data = data or {}

        spec = cls(
            morphology_family=data.get("morphology_family", "generic_robotic_platform"),
            body_posture=data.get("body_posture", "standing"),
            silhouette=data.get("silhouette", "compact-mechanical"),
            symmetry_strategy=data.get("symmetry_strategy", "bilateral"),
            appendage_count=int(data.get("appendage_count", 0) or 0),
            fabrication_hints=list(data.get("fabrication_hints", []) or []),
            allowed_primitive_shapes=list(data.get("allowed_primitive_shapes", []) or []),
            hard_negatives=list(data.get("hard_negatives", []) or []),
            morphology_archetype=data.get("morphology_archetype", ""),
            bio_inspiration=dict(data.get("bio_inspiration", {}) or {}),
            locomotion_strategy=dict(data.get("locomotion_strategy", {}) or {}),
            specialized_features=list(data.get("specialized_features", []) or []),
            cad_rules=list(data.get("cad_rules", []) or []),
            quality_checklist=list(data.get("quality_checklist", []) or []),
            source_mission_keywords=list(data.get("source_mission_keywords", []) or []),
            notes=data.get("notes", ""),
        )

        for item in data.get("primary_segments", []) or []:
            spec.primary_segments.append(
                BodySegment(
                    name=item.get("name", "body"),
                    length_mm=_num(item.get("length_mm", 80), 80),
                    width_mm=_num(item.get("width_mm", 50), 50),
                    height_mm=_num(item.get("height_mm", 20), 20),
                    z_base_mm=_num(item.get("z_base_mm", 0), 0),
                    label=item.get("label", ""),
                    notes=item.get("notes", ""),
                )
            )

        for item in data.get("appendages", []) or []:
            attach = item.get("attach", [0, 0, 0])
            if not isinstance(attach, (list, tuple)) or len(attach) != 3:
                attach = [
                    item.get("attach_x_mm", 0),
                    item.get("attach_y_mm", 0),
                    item.get("attach_z_mm", 0),
                ]

            spec.appendages.append(
                Appendage(
                    name=item.get("name", "appendage"),
                    appendage_type=item.get("appendage_type", item.get("type", "leg")),
                    attach_x_mm=_num(attach[0], 0),
                    attach_y_mm=_num(attach[1], 0),
                    attach_z_mm=_num(attach[2], 0),
                    angle_deg=_num(item.get("angle_deg", 0), 0),
                    tilt_deg=_num(item.get("tilt_deg", 30), 30),
                    length_mm=_num(item.get("length_mm", 60), 60),
                    width_mm=_num(item.get("width_mm", 8), 8),
                    height_mm=_num(item.get("height_mm", 8), 8),
                    ground_contact=_bool(item.get("ground_contact", False), False),
                    foot_radius_mm=_num(item.get("foot_radius_mm", 5), 5),
                    notes=item.get("notes", ""),
                )
            )

        for item in data.get("anchor_points", []) or []:
            spec.anchor_points.append(
                AnchorPoint(
                    name=item.get("name", "anchor"),
                    x_mm=_num(item.get("x_mm", 0), 0),
                    y_mm=_num(item.get("y_mm", 0), 0),
                    z_mm=_num(item.get("z_mm", 0), 0),
                    purpose=item.get("purpose", ""),
                )
            )

        vs = data.get("vertical_structure", {}) or {}
        spec.vertical_structure = VerticalStructure(
            leg_ground_clearance_mm=_num(vs.get("leg_ground_clearance_mm", 30), 30),
            body_elevation_mm=_num(vs.get("body_elevation_mm", 40), 40),
            legs_extend_downward=_bool(vs.get("legs_extend_downward", True), True),
            body_elevated_above_ground=_bool(vs.get("body_elevated_above_ground", True), True),
            use_segmented_z_heights=_bool(vs.get("use_segmented_z_heights", True), True),
            notes=vs.get("notes", ""),
        )

        if spec.appendage_count == 0 and spec.appendages:
            spec.appendage_count = len(spec.appendages)

        return spec
