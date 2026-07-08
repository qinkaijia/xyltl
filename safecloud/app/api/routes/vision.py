from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

from app.schemas.vision import VisionEvaluateRequest, VisionEvaluateResponse, VisionModeRequest, VisionModeResponse
from app.services import vision_service


router = APIRouter(prefix="/vision", tags=["vision"])


@router.post("/evaluate", response_model=VisionEvaluateResponse)
def evaluate(payload: VisionEvaluateRequest):
    return vision_service.evaluate(payload)


@router.get("/latest")
def latest_evaluation():
    latest = vision_service.latest_evaluation()
    if latest is None:
        raise HTTPException(status_code=404, detail="no vision result yet")
    return latest


@router.get("/latest-image")
def latest_image():
    image = vision_service.latest_image()
    if image is None:
        raise HTTPException(status_code=404, detail="no vision image yet")
    image_bytes, image_mime = image
    return Response(content=image_bytes, media_type=image_mime)


@router.get("/mode", response_model=VisionModeResponse)
def get_mode():
    return {"mode": vision_service.get_mode()}


@router.post("/mode", response_model=VisionModeResponse)
def set_mode(payload: VisionModeRequest):
    return {"mode": vision_service.set_mode(payload.mode)}
