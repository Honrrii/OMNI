"""
omnitorch_service.py
--------------------
Main OMNITorch service layer.

Handles model loading (cached), image preprocessing, inference, and
result packaging into the standard OMNITorchResult schema.

This is the single entry point for all OMNITorch inference. The API
routes call this service; they do not interact with PyTorch directly.
"""

import io
import time
from pathlib import Path
from typing import Any, Dict, Optional

import torch
import torch.nn.functional as F
from PIL import Image, UnidentifiedImageError
from torchvision import transforms

from backend.app.ml.fashion_mnist_model import FashionMNISTClassifier
from backend.app.ml.model_registry import (
    get_model_card,
    get_model_path,
    list_model_summaries,
    validate_model_exists,
)
from backend.app.ml.omnitorch_schemas import (
    OMNITorchInterpretation,
    OMNITorchPrediction,
    OMNITorchResult,
    OMNITorchRuntime,
    OMNITorchTopK,
)
from backend.app.ml.reports import build_interpretation


# ---------------------------------------------------------------------------
# Model cache — loaded once per process, not per request.
# ---------------------------------------------------------------------------
_model_cache: Dict[str, Any] = {}


def _get_device() -> torch.device:
    """Return CUDA device if available, otherwise CPU."""
    return torch.device("cuda" if torch.cuda.is_available() else "cpu")


def _load_model(model_name: str) -> Any:
    """
    Load and cache a registered OMNITorch model.

    Raises:
        ValueError: If the model is not registered or weights are missing.
        RuntimeError: If the model file cannot be loaded.
    """
    if model_name in _model_cache:
        return _model_cache[model_name]

    if not validate_model_exists(model_name):
        raise ValueError(
            f"OMNITorch model '{model_name}' is not registered or weights file is missing."
        )

    weights_path = get_model_path(model_name)
    device = _get_device()

    # Model architecture is currently hard-wired to FashionMNISTModel.
    # When new architectures are added, a factory lookup goes here.
    model = FashionMNISTClassifier()

    try:
        state = torch.load(str(weights_path), map_location=device)
        model.load_state_dict(state)
    except Exception as exc:
        raise RuntimeError(
            f"Failed to load OMNITorch model weights from {weights_path}: {exc}"
        ) from exc

    model.to(device)
    model.eval()
    _model_cache[model_name] = model
    return model


def _build_transform() -> transforms.Compose:
    """Return the standard preprocessing pipeline for Fashion-MNIST images."""
    return transforms.Compose(
        [
            transforms.Grayscale(num_output_channels=1),
            transforms.Resize((28, 28)),
            transforms.ToTensor(),
        ]
    )


def _load_image(image_bytes: bytes) -> Image.Image:
    """
    Decode raw image bytes into a PIL Image.

    Raises:
        ValueError: If the bytes cannot be decoded as an image.
    """
    try:
        img = Image.open(io.BytesIO(image_bytes))
        img.verify()
        # Re-open after verify() since verify() exhausts the stream.
        img = Image.open(io.BytesIO(image_bytes)).convert("L")
        return img
    except UnidentifiedImageError as exc:
        raise ValueError(f"Uploaded file is not a recognizable image: {exc}") from exc
    except Exception as exc:
        raise ValueError(f"Could not open image: {exc}") from exc


# ---------------------------------------------------------------------------
# Public service interface
# ---------------------------------------------------------------------------

FASHION_MNIST_CLASSES = [
    "T-shirt/top",
    "Trouser",
    "Pullover",
    "Dress",
    "Coat",
    "Sandal",
    "Shirt",
    "Sneaker",
    "Bag",
    "Ankle boot",
]

DEFAULT_MODEL = "fashion_mnist_mlp"
MAX_IMAGE_BYTES = 10 * 1024 * 1024  # 10 MB hard limit
TOP_K = 3


def get_status() -> Dict[str, Any]:
    """
    Return OMNITorch subsystem health status.

    Does not load any model; only reports runtime environment.
    """
    return {
        "system": "OMNITorch",
        "status": "online",
        "torch_version": torch.__version__,
        "cuda_available": torch.cuda.is_available(),
        "device": str(_get_device()),
        "registered_models": list_model_summaries(),
        "safety_note": (
            "OMNITorch is an ML inference subsystem. "
            "Results are not engineering decisions. "
            "Human review is required before acting on any OMNITorch output."
        ),
    }


def get_model_list() -> list:
    """Return a list of model summaries from the registry."""
    return list_model_summaries()


def analyze_image(
    image_bytes: bytes,
    model_name: str = DEFAULT_MODEL,
    top_k: int = TOP_K,
) -> OMNITorchResult:
    """
    Run OMNITorch inference on uploaded image bytes.

    Args:
        image_bytes: Raw bytes of the uploaded image file.
        model_name: Registered model name to use for inference.
        top_k: Number of top predictions to include in the result.

    Returns:
        OMNITorchResult with prediction, runtime, and OMNI interpretation.

    Raises:
        ValueError: For invalid images or unknown model names.
        RuntimeError: For model loading failures.
    """
    if len(image_bytes) > MAX_IMAGE_BYTES:
        raise ValueError(
            f"Image exceeds the OMNITorch size limit of {MAX_IMAGE_BYTES // (1024 * 1024)} MB."
        )

    model_card = get_model_card(model_name) or {}
    classes = model_card.get("classes", FASHION_MNIST_CLASSES)
    task_type = model_card.get("task_type", "image_classification")

    model = _load_model(model_name)
    device = _get_device()
    transform = _build_transform()

    img = _load_image(image_bytes)
    tensor = transform(img).unsqueeze(0).to(device)

    start_time = time.perf_counter()
    with torch.no_grad():
        logits = model(tensor)
        probabilities = F.softmax(logits, dim=1)
    elapsed_ms = (time.perf_counter() - start_time) * 1000

    probs_list = probabilities[0].tolist()
    top_indices = sorted(range(len(probs_list)), key=lambda i: probs_list[i], reverse=True)

    best_idx = top_indices[0]
    best_label = classes[best_idx] if best_idx < len(classes) else f"class_{best_idx}"
    best_conf = probs_list[best_idx]

    prediction = OMNITorchPrediction(
        label=best_label,
        index=best_idx,
        confidence=round(best_conf, 6),
        confidence_percent=f"{best_conf * 100:.2f}%",
    )

    top_k_results = []
    for rank_idx in top_indices[:top_k]:
        conf = probs_list[rank_idx]
        lbl = classes[rank_idx] if rank_idx < len(classes) else f"class_{rank_idx}"
        top_k_results.append(
            OMNITorchTopK(
                label=lbl,
                index=rank_idx,
                confidence=round(conf, 6),
                confidence_percent=f"{conf * 100:.2f}%",
            )
        )

    runtime = OMNITorchRuntime(
        device=str(device),
        torch_version=torch.__version__,
        cuda_available=torch.cuda.is_available(),
        inference_ms=round(elapsed_ms, 2),
    )

    interpretation_data = build_interpretation(
        model_name=model_name,
        label=best_label,
        confidence=best_conf,
        model_card=model_card,
    )

    interpretation = OMNITorchInterpretation(
        summary=interpretation_data["summary"],
        engineering_relevance=interpretation_data["engineering_relevance"],
        limitations=interpretation_data["limitations"],
        next_step=interpretation_data["next_step"],
    )

    provenance = {
        "model_name": model_name,
        "model_version": model_card.get("version", "unknown"),
        "card_path": str(
            Path(__file__).resolve().parent / "models" / f"{model_name}.card.json"
        ),
        "review_required_before_hardware_use": model_card.get(
            "review_required_before_hardware_use", True
        ),
    }

    return OMNITorchResult(
        status="ok",
        system="OMNITorch",
        task_type=task_type,
        model_name=model_name,
        prediction=prediction,
        top_k=top_k_results,
        runtime=runtime,
        omni_interpretation=interpretation,
        provenance=provenance,
    )
