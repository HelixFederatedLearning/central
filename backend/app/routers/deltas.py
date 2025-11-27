from fastapi import APIRouter, UploadFile, File, Form, Depends
from sqlmodel import Session
from uuid import uuid4

from ..db.session import get_session
from ..db.models import Delta
from ..services.rounds import get_or_open_current_round
from ..core.storage import save_delta
from ..core.events import publish

router = APIRouter()

@router.post("/deltas")
async def post_delta(
    client_id: str = Form(...),
    kind: str = Form(...),                 # "hospital" | "patient"
    num_examples: int = Form(...),
    model_arch: str = Form("tv_effnet_b3"),
    sd_keys_hash: str = Form(""),
    delta: UploadFile = File(...),
    session: Session = Depends(get_session),
):
    rnd = get_or_open_current_round(session)
    delta_id = str(uuid4())
    path = save_delta(rnd.id, client_id, f"{delta_id}.pt", delta.file)

    row = Delta(round_id=rnd.id, client_id=client_id, kind=kind,
                num_examples=num_examples, blob_path=str(path),
                sd_keys_hash=sd_keys_hash, model_arch=model_arch)
    session.add(row); session.commit()

    await publish({"type":"delta_received","client_id":client_id,"kind":kind,"round_id":rnd.id,"n":num_examples})
    return {"ok": True, "delta_id": delta_id, "round_id": rnd.id}