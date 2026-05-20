"""
inference_service.py
--------------------
Backward-compatibility wrapper around the OMNITorch service layer.

Existing callers that use classify_uploaded_image(image_bytes) continue
to work without changes. New code should call omnitorch_service.analyze_image()
directly to get the full OMNITorchResult schema.
"""

from typing import Any, Dict

from backend.app.ml.omnitorch_service import DEFAULT_MODEL, analyze_image


def classify_uploaded_image(image_bytes: bytes) -> Dict[str, Any]:
    """
    Classify an image using the default OMNITorch model.

    This function preserves the original interface used by ml_routes.py
    and any other callers. It returns a dictionary rather than a Pydantic
    model so existing JSON serialization paths are unaffected.

    For full OMNITorchResult access, call omnitorch_service.analyze_image() directly.

    Args:
        image_bytes: Raw bytes of the uploaded image file.

    Returns:
        Dictionary representation of OMNITorchResult.

    Raises:
        ValueError: For invalid images.
        RuntimeError: For model loading failures.
    """
    result = analyze_image(image_bytes=image_bytes, model_name=DEFAULT_MODEL)
    return result.dict()
