"""
omnitorch_schemas.py
--------------------
Pydantic schemas for the OMNITorch ML inference subsystem.

Every OMNITorch model returns an OMNITorchResult regardless of the
underlying model architecture. This contract lets OMNI agents consume
ML output without caring which model produced it.
"""

from typing import List, Optional
from pydantic import BaseModel, Field


class OMNITorchPrediction(BaseModel):
    """Top prediction returned by an OMNITorch model."""

    label: str = Field(..., description="Human-readable class label.")
    index: int = Field(..., description="Class index in the model output layer.")
    confidence: float = Field(..., description="Raw confidence score (0.0 – 1.0).")
    confidence_percent: str = Field(
        ..., description="Confidence formatted as a percentage string, e.g. '86.94%'."
    )


class OMNITorchTopK(BaseModel):
    """One entry in the top-k prediction list."""

    label: str
    index: int
    confidence: float
    confidence_percent: str


class OMNITorchRuntime(BaseModel):
    """Runtime environment snapshot captured at inference time."""

    device: str = Field(..., description="Compute device used: 'cpu' or 'cuda'.")
    torch_version: str = Field(..., description="PyTorch version string.")
    cuda_available: bool = Field(..., description="Whether CUDA is available on this host.")
    inference_ms: Optional[float] = Field(
        None, description="Wall-clock inference time in milliseconds."
    )


class OMNITorchInterpretation(BaseModel):
    """
    OMNI-readable interpretation of the raw model prediction.

    This layer translates model output into engineering-relevant language
    that OMNI agents (Pluto, QaZ, Korva) can consume directly.
    """

    summary: str = Field(..., description="One-sentence plain-English summary of the result.")
    engineering_relevance: str = Field(
        ...,
        description="Why this result matters in an OMNI engineering context.",
    )
    limitations: str = Field(
        ...,
        description="What this model does NOT understand or where it should not be trusted.",
    )
    next_step: str = Field(
        ...,
        description="Recommended next action given this result.",
    )


class OMNITorchModelCard(BaseModel):
    """
    Static metadata about a registered OMNITorch model.

    Loaded from the model's .card.json file in the models/ directory.
    """

    model_name: str
    system_name: str = "OMNITorch"
    version: str
    task_type: str
    input_type: str
    framework: str
    classes: List[str]
    intended_use: str
    limitations: str
    future_replacement_targets: List[str]
    training_summary: str
    omni_relevance: str


class OMNITorchResult(BaseModel):
    """
    Standard OMNITorch inference result.

    All OMNITorch endpoints return this schema so OMNI agents and the
    frontend can consume any model without schema changes.
    """

    status: str = Field(..., description="'ok' or 'error'.")
    system: str = Field(default="OMNITorch", description="Always 'OMNITorch'.")
    task_type: str = Field(..., description="Task type, e.g. 'image_classification'.")
    model_name: str = Field(..., description="Registered model name.")
    prediction: OMNITorchPrediction
    top_k: List[OMNITorchTopK] = Field(default_factory=list)
    runtime: OMNITorchRuntime
    omni_interpretation: OMNITorchInterpretation
    provenance: dict = Field(
        default_factory=dict,
        description="Model card metadata or version info attached at inference time.",
    )
    error: Optional[str] = Field(None, description="Error message if status is 'error'.")
