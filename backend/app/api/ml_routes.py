from fastapi import APIRouter, File, HTTPException, UploadFile

from backend.app.ml.inference_service import (
    classify_uploaded_image,
    get_torch_status,
)


router = APIRouter()


@router.get("/status")
def ml_status():
    return get_torch_status()


@router.post("/classify-demo")
async def classify_demo(file: UploadFile = File(...)):
    allowed_extensions = (".png", ".jpg", ".jpeg", ".bmp", ".webp")

    filename = file.filename or ""

    if not filename.lower().endswith(allowed_extensions):
        raise HTTPException(
            status_code=400,
            detail=(
                "Unsupported file type. Please upload a normal image file "
                "such as .png, .jpg, .jpeg, .bmp, or .webp."
            ),
        )

    try:
        image_bytes = await file.read()
        result = classify_uploaded_image(image_bytes)

        return {
            "status": "ok",
            "filename": filename,
            "result": result,
        }

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Image classification failed: {str(exc)}",
        )