from fastapi import APIRouter, HTTPException

from app.schemas.evaluate import EvaluateRequest, EvaluateResponse
from app.services import analyzer_service


router = APIRouter(prefix="/evaluate", tags=["evaluate"])


@router.post("", response_model=EvaluateResponse)
def evaluate(payload: EvaluateRequest):
    return analyzer_service.evaluate(payload)


@router.get("/latest")
def latest_evaluation():
    latest = analyzer_service.latest_evaluation()
    if latest is None:
        raise HTTPException(status_code=404, detail="no evaluation result yet")
    return latest
