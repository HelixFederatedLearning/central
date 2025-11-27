# app/routers/infer.py
from typing import List, Dict
from fastapi import APIRouter, Depends, File, UploadFile, HTTPException
from pydantic import BaseModel
from sqlmodel import Session

from ..db.session import get_session
from ..core.runtime import predict_bytes, CLASSES, get_loaded_model

router = APIRouter()

class InferLabelsOut(BaseModel):
    labels: List[str]

class InferOut(BaseModel):
    model_id: str
    version: str
    top_label: str
    top_index: int
    probabilities: Dict[str, float]


@router.get("/infer/labels", response_model=InferLabelsOut)
def labels():
    return InferLabelsOut(labels=CLASSES)


@router.post("/infer", response_model=InferOut)
async def infer(file: UploadFile = File(...), session: Session = Depends(get_session)):
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Please upload an image file")

    bytes_data = await file.read()
    probs, top_idx = predict_bytes(session, bytes_data)
    lm = get_loaded_model(session)

    # zip probs to labels
    out = {label: float(probs[i]) for i, label in enumerate(CLASSES)}
    return InferOut(
        model_id=lm.model_id,
        version=lm.version,
        top_label=CLASSES[top_idx],
        top_index=top_idx,
        probabilities=out,
    )
