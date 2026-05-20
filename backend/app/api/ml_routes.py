"""
ml_routes.py
------------
FastAPI routes for the OMNITorch ML inference subsystem.

Endpoints:
    GET  /api/ml/status         — OMNITorch subsystem health check
    GET  /api/ml/models         — List registered models and their cards
    POST /api/ml/classify-demo  — Classify with the default demo model (backward compat)
    POST /api/ml/analyze-image  — Full OMNITorch inference with model selection
"""

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from backend.app.ml.omnitorch_service import (
    MAX_IMAGE_BYTES,
    analyze_image,
    get_model_list,
    get_status,
)

router = APIRouter()

ALLOWED_CONTENT_TYPES = {
    "image/png",
    "image/jpeg",
    "image/jpg",
    "image/webp",
    "image/bmp",
    "image/gif",
}


def _validate_upload(file: UploadFile) -> None:
    """
    Validate an uploaded file's content type.

    Raises:
        HTTPException 415: If the content type is not a supported image type.
    """
    if file.content_type and file.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=415,
            detail=(
                f"Unsupported file type: '{file.content_type}'. "
                f"OMNITorch accepts: {', '.join(sorted(ALLOWED_CONTENT_TYPES))}."
            ),
        )


@router.get("/status")
async def omnitorch_status():
    """
    OMNITorch subsystem health check.

    Returns runtime info: torch version, CUDA availability, device, and
    registered model summaries.
    """
    try:
        return get_status()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"OMNITorch status check failed: {exc}")


@router.get("/models")
async def list_omnitorch_models():
    """
    List all registered OMNITorch models with their metadata summaries.

    Returns model name, task type, version, and whether weights are available.
    """
    try:
        return {
            "system": "OMNITorch",
            "models": get_model_list(),
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to list OMNITorch models: {exc}")


@router.post("/classify-demo")
async def classify_demo(file: UploadFile = File(...)):
    """
    Classify an uploaded image using the default Fashion-MNIST demo model.

    Backward-compatible endpoint. New integrations should use /api/ml/analyze-image
    for model selection and the full OMNITorchResult schema.

    Accepts: PNG, JPEG, WEBP, BMP, GIF
    Max size: 10 MB
    """
    _validate_upload(file)

    image_bytes = await file.read()

    if len(image_bytes) == 0:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    if len(image_bytes) > MAX_IMAGE_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File exceeds the OMNITorch size limit of {MAX_IMAGE_BYTES // (1024*1024)} MB.",
        )

    try:
        result = analyze_image(image_bytes=image_bytes, model_name="fashion_mnist_mlp")
        return result.dict()
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"OMNITorch inference failed unexpectedly: {exc}",
        )


@router.post("/analyze-image")
async def analyze_image_endpoint(
    file: UploadFile = File(...),
    model_name: str = Form(default="fashion_mnist_mlp"),
):
    """
    Full OMNITorch inference endpoint with model selection.

    Upload an image and choose which registered OMNITorch model to run.
    Returns the complete OMNITorchResult schema including prediction,
    top-k results, runtime info, and OMNI interpretation.

    Accepts: PNG, JPEG, WEBP, BMP, GIF
    Max size: 10 MB
    """
    _validate_upload(file)

    image_bytes = await file.read()

    if len(image_bytes) == 0:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    if len(image_bytes) > MAX_IMAGE_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File exceeds the OMNITorch size limit of {MAX_IMAGE_BYTES // (1024*1024)} MB.",
        )

    try:
        result = analyze_image(image_bytes=image_bytes, model_name=model_name)
        return result.dict()
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"OMNITorch inference failed unexpectedly: {exc}",
        )
