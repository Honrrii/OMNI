"""Versioned learning API, separate from the compatible v0.1 demo routes."""
from contextlib import asynccontextmanager
from functools import lru_cache
from typing import Literal
from urllib.parse import unquote
import threading

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from starlette.concurrency import run_in_threadpool

from backend.app.ml.lab_schemas import DatasetRequest, TrainingRequest, EvaluationRequest, InferenceRequest
from backend.app.ml.lab_service import LearningLab
from backend.app.ml.lab_store import LabError, LabStore, MAX_IMAGE_BYTES, default_root


_instance_lock = threading.Lock()


@lru_cache(maxsize=1)
def _cached_lab():
    return LearningLab(LabStore(default_root()))


def get_lab():
    with _instance_lock:
        return _cached_lab()


@asynccontextmanager
async def lifespan(app):
    yield
    if _cached_lab.cache_info().currsize:
        await run_in_threadpool(get_lab().close)
        _cached_lab.cache_clear()


router = APIRouter(lifespan=lifespan)


def call(operation, *args):
    try:
        return operation(*args)
    except LabError as exc:
        raise HTTPException(status_code=exc.status, detail=str(exc)) from exc


@router.post("/images", status_code=201)
async def upload_image(request: Request, lab: LearningLab = Depends(get_lab)):
    """Raw image body avoids unbounded multipart spool storage; filename is display-only."""
    media_type = request.headers.get("content-type", "").split(";")[0]
    if media_type not in {"image/png", "image/jpeg", "image/webp"}:
        raise HTTPException(415, "Upload a PNG, JPEG or WebP image.")
    data = bytearray()
    async for chunk in request.stream():
        if len(data) + len(chunk) > MAX_IMAGE_BYTES:
            raise HTTPException(413, "Maximum image size is 10 MiB.")
        data.extend(chunk)
    return await run_in_threadpool(call, lab.store.intake, bytes(data),
                                   unquote(request.headers.get("x-image-name", "image")), media_type)


@router.get("/images/{image_id}/{artifact}")
def image_artifact(image_id: str, artifact: Literal["original", "thumbnail", "preprocessed"], lab: LearningLab = Depends(get_lab)):
    record = call(lab.store.get, "images", image_id)
    metadata = record[artifact]
    data = call(lab.store.read_artifact, "images", image_id, metadata["filename"], metadata["sha256"])
    return Response(data, media_type=record["media_type"] if artifact == "original" else "image/png",
                    headers={"X-Content-Type-Options": "nosniff", "ETag": f'"{metadata["sha256"]}"',
                             "Cache-Control": "private, max-age=31536000, immutable",
                             **({"Content-Disposition": 'attachment; filename="original-image"'} if artifact == "original" else {})})


@router.post("/datasets", status_code=201)
def create_dataset(request: DatasetRequest, lab: LearningLab = Depends(get_lab)):
    return call(lab.store.create_dataset, request)


@router.post("/training", status_code=202)
def train(request: TrainingRequest, lab: LearningLab = Depends(get_lab)):
    return call(lab.submit, request)


@router.post("/evaluations", status_code=201)
def evaluate(request: EvaluationRequest, lab: LearningLab = Depends(get_lab)):
    return call(lab.evaluate, request)


@router.post("/inferences", status_code=201)
def infer(request: InferenceRequest, lab: LearningLab = Depends(get_lab)):
    return call(lab.infer, request)


@router.get("/{collection}")
def list_records(collection: Literal["images", "datasets", "jobs", "models", "evaluations", "inferences"], lab: LearningLab = Depends(get_lab)):
    return {"items": call(lab.store.list, collection)}


@router.get("/{collection}/{identity}")
def get_record(collection: Literal["images", "datasets", "jobs", "models", "evaluations", "inferences"], identity: str, lab: LearningLab = Depends(get_lab)):
    return call(lab.store.get, collection, identity)
