from typing import Any, Dict, List
from pydantic import BaseModel, Field


class CADParameterPlan(BaseModel):
    """
    Generic CAD parameter plan for OMNI Forge.

    This does not generate geometry yet.
    It prepares structured dimensions, assumptions, features, and print notes
    that a future Fusion 360 / CadQuery / FreeCAD generator can consume.
    """

    part_type: str
    cad_backend: str = "cadquery_or_fusion360"
    units: str = "mm"

    parameters: Dict[str, Any] = Field(default_factory=dict)
    design_features: List[str] = Field(default_factory=list)
    manufacturing_notes: List[str] = Field(default_factory=list)
    assumptions: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)

    ready_for_script_generation: bool = False