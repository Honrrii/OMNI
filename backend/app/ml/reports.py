"""
reports.py
----------
Converts raw OMNITorch model predictions into OMNI-readable interpretations.

This layer is the bridge between raw ML output (label + confidence) and the
OMNI engineering language that agents like Pluto, QaZ, and Korva can consume.

When a new model is added, a new interpreter function is registered here.
"""

from typing import Any, Dict


def build_interpretation(
    model_name: str,
    label: str,
    confidence: float,
    model_card: Dict[str, Any],
) -> Dict[str, str]:
    """
    Build an OMNI-readable interpretation for a model prediction.

    Args:
        model_name: Registered model name used to select the interpreter.
        label: Top predicted class label.
        confidence: Raw confidence score (0.0 – 1.0).
        model_card: Loaded model card dictionary.

    Returns:
        Dictionary with keys: summary, engineering_relevance, limitations, next_step.
    """
    interpreters = {
        "fashion_mnist_mlp": _interpret_fashion_mnist,
    }

    interpreter = interpreters.get(model_name, _interpret_generic)
    return interpreter(label, confidence, model_card)


def _interpret_fashion_mnist(
    label: str,
    confidence: float,
    model_card: Dict[str, Any],
) -> Dict[str, str]:
    """Interpreter for the Fashion-MNIST demo model."""
    confidence_pct = f"{confidence * 100:.1f}%"
    limitations = model_card.get(
        "limitations",
        "This is a demo model. It does not understand engineering artifacts.",
    )

    if confidence >= 0.90:
        certainty_note = "High confidence prediction."
    elif confidence >= 0.65:
        certainty_note = "Moderate confidence — the image may be ambiguous."
    else:
        certainty_note = (
            "Low confidence. The image likely does not match this model's training domain."
        )

    return {
        "summary": (
            f"The uploaded image was classified as '{label}' "
            f"with {confidence_pct} confidence. {certainty_note}"
        ),
        "engineering_relevance": (
            "This is an OMNITorch demo result. The Fashion-MNIST classifier validates "
            "that the OMNITorch inference pipeline is working correctly. It does not "
            "contribute to any engineering decision in OMNI's current state."
        ),
        "limitations": limitations,
        "next_step": (
            "Replace this model with a CAD morphology reviewer, robot component classifier, "
            "or sensor anomaly detector to produce engineering-relevant OMNITorch results."
        ),
    }


def _interpret_generic(
    label: str,
    confidence: float,
    model_card: Dict[str, Any],
) -> Dict[str, str]:
    """Fallback interpreter for models without a dedicated interpreter."""
    confidence_pct = f"{confidence * 100:.1f}%"
    intended_use = model_card.get("intended_use", "Unknown intended use.")
    limitations = model_card.get("limitations", "No limitations documented.")

    return {
        "summary": (
            f"OMNITorch classified the input as '{label}' with {confidence_pct} confidence."
        ),
        "engineering_relevance": intended_use,
        "limitations": limitations,
        "next_step": (
            "Review the model card to determine whether this result is relevant "
            "to the current OMNI mission phase."
        ),
    }
