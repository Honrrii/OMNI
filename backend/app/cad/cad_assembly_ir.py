"""
OMNI CAD Assembly Intermediate Representation.

Defines structured data types that sit between the morphology planner and the
Fusion 360 geometry generator.  Every class is a pure Python dataclass.

Design rules:
- No LLM calls.
- No Fusion API imports.
- No file I/O.
- Deterministic: same inputs -> same output dict.
- Additive: adding new fields never breaks existing callers.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


# ─────────────────────────────────────────────────────────────
# Detail-level constants
# ─────────────────────────────────────────────────────────────

LOD0_SILHOUETTE             = "LOD0_silhouette"
LOD1_MORPHOLOGY             = "LOD1_morphology"
LOD2_MECHANICAL_PLACEHOLDERS = "LOD2_mechanical_placeholders"
LOD3_INTERNAL_ASSEMBLY      = "LOD3_internal_assembly"
LOD4_TRANSPARENT_CUTAWAY    = "LOD4_transparent_cutaway"

DETAIL_LEVELS = [
    LOD0_SILHOUETTE,
    LOD1_MORPHOLOGY,
    LOD2_MECHANICAL_PLACEHOLDERS,
    LOD3_INTERNAL_ASSEMBLY,
    LOD4_TRANSPARENT_CUTAWAY,
]

# ─────────────────────────────────────────────────────────────
# Visibility modes
# ─────────────────────────────────────────────────────────────

VISIBILITY_OPAQUE      = "opaque"
VISIBILITY_CUTAWAY     = "transparent_cutaway"
VISIBILITY_WIREFRAME   = "wireframe"


# ─────────────────────────────────────────────────────────────
# Sub-data types
# ─────────────────────────────────────────────────────────────

@dataclass
class MountingFeatureSpec:
    """One mounting boss, standoff pattern, or rail segment."""
    name: str
    feature_type: str               # "boss", "standoff", "rail", "slot", "hole_pattern"
    x_mm: float = 0.0
    y_mm: float = 0.0
    z_mm: float = 0.0
    diameter_mm: float = 6.0
    height_mm: float = 10.0
    count: int = 1
    spacing_x_mm: float = 0.0
    spacing_y_mm: float = 0.0
    notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "feature_type": self.feature_type,
            "x_mm": self.x_mm,
            "y_mm": self.y_mm,
            "z_mm": self.z_mm,
            "diameter_mm": self.diameter_mm,
            "height_mm": self.height_mm,
            "count": self.count,
            "spacing_x_mm": self.spacing_x_mm,
            "spacing_y_mm": self.spacing_y_mm,
            "notes": self.notes,
        }


@dataclass
class FastenerPatternSpec:
    """Array of screw / bolt markers."""
    name: str
    x_positions_mm: List[float] = field(default_factory=list)
    y_positions_mm: List[float] = field(default_factory=list)
    z_mm: float = 0.0
    diameter_mm: float = 3.2
    depth_mm: float = 6.0
    notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "x_positions_mm": self.x_positions_mm,
            "y_positions_mm": self.y_positions_mm,
            "z_mm": self.z_mm,
            "diameter_mm": self.diameter_mm,
            "depth_mm": self.depth_mm,
            "notes": self.notes,
        }


@dataclass
class PanelFeatureSpec:
    """One outer shell panel or cutaway surface."""
    name: str
    panel_type: str                 # "top_shell", "bottom_plate", "side_fairing", "nose_cap", "fin_panel"
    length_mm: float = 100.0
    width_mm: float = 60.0
    thickness_mm: float = 3.0
    x_mm: float = 0.0
    y_mm: float = 0.0
    z_mm: float = 0.0
    angle_deg: float = 0.0
    transparent: bool = False
    notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "panel_type": self.panel_type,
            "length_mm": self.length_mm,
            "width_mm": self.width_mm,
            "thickness_mm": self.thickness_mm,
            "x_mm": self.x_mm,
            "y_mm": self.y_mm,
            "z_mm": self.z_mm,
            "angle_deg": self.angle_deg,
            "transparent": self.transparent,
            "notes": self.notes,
        }


@dataclass
class StructuralFeatureSpec:
    """Rib, bulkhead, or cable corridor marker."""
    name: str
    feature_type: str               # "rib", "bulkhead", "cable_corridor", "spar"
    length_mm: float = 80.0
    width_mm: float = 4.0
    height_mm: float = 20.0
    x_mm: float = 0.0
    y_mm: float = 0.0
    z_mm: float = 0.0
    angle_deg: float = 0.0
    notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "feature_type": self.feature_type,
            "length_mm": self.length_mm,
            "width_mm": self.width_mm,
            "height_mm": self.height_mm,
            "x_mm": self.x_mm,
            "y_mm": self.y_mm,
            "z_mm": self.z_mm,
            "angle_deg": self.angle_deg,
            "notes": self.notes,
        }


@dataclass
class InternalVolumeSpec:
    """A reserved internal volume for a subsystem (electronics bay, battery bay, etc.)."""
    name: str
    subsystem: str                  # "battery", "electronics", "actuator", "fuel_cell", "payload"
    length_mm: float = 80.0
    width_mm: float = 50.0
    height_mm: float = 25.0
    x_mm: float = 0.0
    y_mm: float = 0.0
    z_mm: float = 10.0
    notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "subsystem": self.subsystem,
            "length_mm": self.length_mm,
            "width_mm": self.width_mm,
            "height_mm": self.height_mm,
            "x_mm": self.x_mm,
            "y_mm": self.y_mm,
            "z_mm": self.z_mm,
            "notes": self.notes,
        }


@dataclass
class MechanicalComponentSpec:
    """
    One mechanical component placeholder (motor, servo, battery, board, sensor, etc.).
    """
    name: str
    component_type: str             # from mechanical_component_library keys
    x_mm: float = 0.0
    y_mm: float = 0.0
    z_mm: float = 0.0
    angle_deg: float = 0.0
    length_mm: float = 0.0          # 0 = use library default
    width_mm: float = 0.0
    height_mm: float = 0.0
    label: str = ""
    notes: str = ""
    tags: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "component_type": self.component_type,
            "x_mm": self.x_mm,
            "y_mm": self.y_mm,
            "z_mm": self.z_mm,
            "angle_deg": self.angle_deg,
            "length_mm": self.length_mm,
            "width_mm": self.width_mm,
            "height_mm": self.height_mm,
            "label": self.label,
            "notes": self.notes,
            "tags": self.tags,
        }


@dataclass
class OuterShellSpec:
    """
    Outer shell / hull description.  Panels are individual PanelFeatureSpec items.
    """
    shell_type: str = "monocoque"   # "monocoque", "segmented", "exoskeleton", "fairing_set"
    visibility_mode: str = VISIBILITY_OPAQUE
    panels: List[PanelFeatureSpec] = field(default_factory=list)
    notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "shell_type": self.shell_type,
            "visibility_mode": self.visibility_mode,
            "panels": [p.to_dict() for p in self.panels],
            "notes": self.notes,
        }


@dataclass
class SubassemblySpec:
    """
    One logical subassembly zone (propulsion, sensor, power, compute, payload, etc.).
    """
    name: str
    zone: str                       # "propulsion", "power", "compute", "sensor", "payload", "structure"
    components: List[MechanicalComponentSpec] = field(default_factory=list)
    mounting_features: List[MountingFeatureSpec] = field(default_factory=list)
    fastener_patterns: List[FastenerPatternSpec] = field(default_factory=list)
    internal_volumes: List[InternalVolumeSpec] = field(default_factory=list)
    notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "zone": self.zone,
            "components": [c.to_dict() for c in self.components],
            "mounting_features": [m.to_dict() for m in self.mounting_features],
            "fastener_patterns": [f.to_dict() for f in self.fastener_patterns],
            "internal_volumes": [v.to_dict() for v in self.internal_volumes],
            "notes": self.notes,
        }


@dataclass
class DetailPassSpec:
    """
    One detail pass that is applied on top of the morphology geometry.
    Passes are ordered by index and applied sequentially.
    """
    pass_name: str
    pass_type: str                  # "shell", "internals", "structure", "fasteners", "labels"
    detail_level: str = LOD2_MECHANICAL_PLACEHOLDERS
    enabled: bool = True
    notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "pass_name": self.pass_name,
            "pass_type": self.pass_type,
            "detail_level": self.detail_level,
            "enabled": self.enabled,
            "notes": self.notes,
        }


# ─────────────────────────────────────────────────────────────
# Top-level AssemblySpec
# ─────────────────────────────────────────────────────────────

@dataclass
class AssemblySpec:
    """
    Complete assembly description consumed by the Fusion 360 generator.

    Hierarchy:
        AssemblySpec
        ├── OuterShellSpec          (outer panels / hull)
        ├── SubassemblySpec[]       (logical zones: power, compute, sensor …)
        │   ├── MechanicalComponentSpec[]
        │   ├── MountingFeatureSpec[]
        │   ├── FastenerPatternSpec[]
        │   └── InternalVolumeSpec[]
        ├── StructuralFeatureSpec[] (ribs, bulkheads, cable corridors)
        └── DetailPassSpec[]        (ordered rendering passes)
    """

    # Identity
    assembly_name: str = "omni_assembly"
    platform_type: str = "generic_robotic_platform"
    morphology_family: str = "generic_robotic_platform"
    detail_level: str = LOD2_MECHANICAL_PLACEHOLDERS
    visibility_mode: str = VISIBILITY_OPAQUE

    # Content
    outer_shell: OuterShellSpec = field(default_factory=OuterShellSpec)
    subassemblies: List[SubassemblySpec] = field(default_factory=list)
    structural_features: List[StructuralFeatureSpec] = field(default_factory=list)
    detail_passes: List[DetailPassSpec] = field(default_factory=list)

    # Metadata
    trait_sources: List[str] = field(default_factory=list)
    specialized_features: List[str] = field(default_factory=list)
    notes: str = ""

    # ── Convenience accessors ──────────────────────────────

    @property
    def all_components(self) -> List[MechanicalComponentSpec]:
        components: List[MechanicalComponentSpec] = []
        for sub in self.subassemblies:
            components.extend(sub.components)
        return components

    @property
    def component_count(self) -> int:
        return sum(len(sub.components) for sub in self.subassemblies)

    @property
    def structural_feature_count(self) -> int:
        return len(self.structural_features)

    @property
    def has_internals(self) -> bool:
        return self.detail_level in (
            LOD3_INTERNAL_ASSEMBLY,
            LOD4_TRANSPARENT_CUTAWAY,
        )

    @property
    def has_cutaway(self) -> bool:
        return self.visibility_mode == VISIBILITY_CUTAWAY

    # ── Serialisation ──────────────────────────────────────

    def to_dict(self) -> Dict[str, Any]:
        return {
            "assembly_name": self.assembly_name,
            "platform_type": self.platform_type,
            "morphology_family": self.morphology_family,
            "detail_level": self.detail_level,
            "visibility_mode": self.visibility_mode,
            "outer_shell": self.outer_shell.to_dict(),
            "subassemblies": [s.to_dict() for s in self.subassemblies],
            "structural_features": [f.to_dict() for f in self.structural_features],
            "detail_passes": [p.to_dict() for p in self.detail_passes],
            "component_count": self.component_count,
            "structural_feature_count": self.structural_feature_count,
            "trait_sources": self.trait_sources,
            "specialized_features": self.specialized_features,
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AssemblySpec":
        """Reconstruct from a plain dict (e.g. loaded from JSON)."""
        data = data or {}

        # Outer shell
        shell_data = data.get("outer_shell", {}) or {}
        panels = [
            PanelFeatureSpec(**{
                k: v for k, v in (p or {}).items()
                if k in PanelFeatureSpec.__dataclass_fields__
            })
            for p in shell_data.get("panels", [])
        ]
        outer_shell = OuterShellSpec(
            shell_type=shell_data.get("shell_type", "monocoque"),
            visibility_mode=shell_data.get("visibility_mode", VISIBILITY_OPAQUE),
            panels=panels,
            notes=shell_data.get("notes", ""),
        )

        # Subassemblies
        subassemblies: List[SubassemblySpec] = []
        for sub_data in data.get("subassemblies", []) or []:
            components = [
                MechanicalComponentSpec(**{
                    k: v for k, v in (c or {}).items()
                    if k in MechanicalComponentSpec.__dataclass_fields__
                })
                for c in sub_data.get("components", [])
            ]
            mounting = [
                MountingFeatureSpec(**{
                    k: v for k, v in (m or {}).items()
                    if k in MountingFeatureSpec.__dataclass_fields__
                })
                for m in sub_data.get("mounting_features", [])
            ]
            fasteners = [
                FastenerPatternSpec(**{
                    k: v for k, v in (f or {}).items()
                    if k in FastenerPatternSpec.__dataclass_fields__
                })
                for f in sub_data.get("fastener_patterns", [])
            ]
            volumes = [
                InternalVolumeSpec(**{
                    k: v for k, v in (v_data or {}).items()
                    if k in InternalVolumeSpec.__dataclass_fields__
                })
                for v_data in sub_data.get("internal_volumes", [])
            ]
            subassemblies.append(SubassemblySpec(
                name=sub_data.get("name", "subassembly"),
                zone=sub_data.get("zone", "structure"),
                components=components,
                mounting_features=mounting,
                fastener_patterns=fasteners,
                internal_volumes=volumes,
                notes=sub_data.get("notes", ""),
            ))

        # Structural features
        structural: List[StructuralFeatureSpec] = []
        for sf in data.get("structural_features", []) or []:
            structural.append(StructuralFeatureSpec(**{
                k: v for k, v in (sf or {}).items()
                if k in StructuralFeatureSpec.__dataclass_fields__
            }))

        # Detail passes
        passes: List[DetailPassSpec] = []
        for dp in data.get("detail_passes", []) or []:
            passes.append(DetailPassSpec(**{
                k: v for k, v in (dp or {}).items()
                if k in DetailPassSpec.__dataclass_fields__
            }))

        return cls(
            assembly_name=data.get("assembly_name", "omni_assembly"),
            platform_type=data.get("platform_type", "generic_robotic_platform"),
            morphology_family=data.get("morphology_family", "generic_robotic_platform"),
            detail_level=data.get("detail_level", LOD2_MECHANICAL_PLACEHOLDERS),
            visibility_mode=data.get("visibility_mode", VISIBILITY_OPAQUE),
            outer_shell=outer_shell,
            subassemblies=subassemblies,
            structural_features=structural,
            detail_passes=passes,
            trait_sources=list(data.get("trait_sources", []) or []),
            specialized_features=list(data.get("specialized_features", []) or []),
            notes=data.get("notes", ""),
        )
