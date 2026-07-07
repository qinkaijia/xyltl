from fastapi import APIRouter

from app.schemas.evaluate import EvaluateRequest, EvaluateResponse
from app.services import analyzer_service


router = APIRouter(prefix="/evaluate", tags=["evaluate"])


@router.post("", response_model=EvaluateResponse)
def evaluate(payload: EvaluateRequest):
    return analyzer_service.evaluate(payload)
