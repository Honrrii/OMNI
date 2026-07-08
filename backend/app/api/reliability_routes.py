from fastapi import APIRouter, HTTPException

from backend.app.reliability.reliability_service import (
    get_reliability_status,
    run_reliability_review,
)
from backend.app.reliability.schemas import ReliabilityReport, ReliabilityReviewRequest


router = APIRouter()


@router.get("/status")
def reliability_status():
    return get_reliability_status()


@router.post("/review", response_model=ReliabilityReport)
def review_reliability(payload: ReliabilityReviewRequest):
    try:
        return run_reliability_review(payload)
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Reliability review failed: {exc}",
        )