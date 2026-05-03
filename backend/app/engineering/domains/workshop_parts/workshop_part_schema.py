from typing import List, Optional
from pydantic import BaseModel, Field


class WorkshopPartSpec(BaseModel):
    """
    Structured specification for simple printable workshop parts.

    Examples:
    - Raspberry Pi camera mount
    - ESP32 enclosure
    - tool holder
    - cable clip
    - breadboard organizer
    """

    part_type: str = "unknown"
    material: str = "PLA"
    fabrication_method: str = "fdm_3d_printing"

    mounting_style: Optional[str] = None
    target_device: Optional[str] = None
    angle_degrees: Optional[float] = None

    design_features: List[str] = Field(default_factory=list)
    missing_requirements: List[str] = Field(default_factory=list)
    safety_notes: List[str] = Field(default_factory=list)