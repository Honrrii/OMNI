"""
model_registry.py
-----------------
Registry of available OMNITorch models.

Each model entry maps a model name to its .pt weights file and its
.card.json metadata file. New models are registered here before they
can be used through the OMNITorch service layer.
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional


# Root of the ml/models/ directory, relative to this file.
_MODELS_DIR = Path(__file__).resolve().parent / "models"

# Registry: model_name -> { "weights": relative path, "card": relative path }
_REGISTRY: Dict[str, Dict[str, str]] = {
    "fashion_mnist_mlp": {
        "weights": "fashion_mnist_mlp.pt",
        "card": "fashion_mnist_mlp.card.json",
    },
    # Future models registered here:
    # "cad_morphology_reviewer": {
    #     "weights": "cad_morphology_reviewer.pt",
    #     "card": "cad_morphology_reviewer.card.json",
    # },
}


def list_models() -> List[str]:
    """Return the names of all registered OMNITorch models."""
    return list(_REGISTRY.keys())


def validate_model_exists(model_name: str) -> bool:
    """Return True if the model name is registered and its weights file exists."""
    if model_name not in _REGISTRY:
        return False
    weights_path = get_model_path(model_name)
    return weights_path is not None and weights_path.exists()


def get_model_path(model_name: str) -> Optional[Path]:
    """
    Return the absolute Path to the model's weights file.

    Returns None if the model is not registered.
    """
    if model_name not in _REGISTRY:
        return None
    return _MODELS_DIR / _REGISTRY[model_name]["weights"]


def get_model_card_path(model_name: str) -> Optional[Path]:
    """
    Return the absolute Path to the model's card JSON file.

    Returns None if the model is not registered.
    """
    if model_name not in _REGISTRY:
        return None
    return _MODELS_DIR / _REGISTRY[model_name]["card"]


def get_model_card(model_name: str) -> Optional[Dict[str, Any]]:
    """
    Load and return the model card dictionary for a registered model.

    Returns None if the model is not registered or the card file is missing.
    """
    card_path = get_model_card_path(model_name)
    if card_path is None or not card_path.exists():
        return None
    try:
        return json.loads(card_path.read_text(encoding="utf-8"))
    except Exception:
        return None


def list_model_summaries() -> List[Dict[str, Any]]:
    """
    Return a list of lightweight model summaries for the /api/ml/models endpoint.

    Each summary includes model name, task type, and whether the weights file exists.
    """
    summaries = []
    for name in _REGISTRY:
        card = get_model_card(name)
        weights_exist = validate_model_exists(name)
        summaries.append(
            {
                "model_name": name,
                "task_type": card.get("task_type", "unknown") if card else "unknown",
                "version": card.get("version", "unknown") if card else "unknown",
                "framework": card.get("framework", "unknown") if card else "unknown",
                "weights_available": weights_exist,
                "intended_use": card.get("intended_use", "") if card else "",
                "omni_relevance": card.get("omni_relevance", "") if card else "",
            }
        )
    return summaries
