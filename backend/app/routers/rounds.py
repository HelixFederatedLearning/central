# app/routers/rounds.py
from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from uuid import uuid4
from datetime import datetime, timezone
from pathlib import Path
import shutil
import torch

from ..db.session import get_session
from ..db.models import Round, Delta, Model, Setting
from ..core.settings import settings
from ..core.storage import sha256_file, set_current_global
from ..core.events import publish
from ..services.aggregate import load_delta_blobs, typed_aggregate




router = APIRouter()


# ---------- helpers ----------

def _ensure_round(session: Session, rid: str) -> Round:
    r = session.get(Round, rid)
    if not r:
        raise HTTPException(status_code=404, detail="Round not found")
    return r


def _list_rounds(session: Session) -> list[Round]:
    q = select(Round).order_by(Round.created_at.desc())
    return list(session.exec(q))


# ---------- routes ----------

@router.get("/rounds")
def list_rounds(session: Session = Depends(get_session)):
    rows = _list_rounds(session)
    return [
        {
            "id": r.id,
            "status": r.status,
            "created_at": r.created_at,
            "closed_at": r.closed_at,
        }
        for r in rows
    ]


@router.get("/rounds/{round_id}")
def get_round(round_id: str, session: Session = Depends(get_session)):
    r = _ensure_round(session, round_id)
    q = select(Delta).where(Delta.round_id == r.id).order_by(Delta.created_at.asc())
    deltas = list(session.exec(q))
    return {
        "id": r.id,
        "status": r.status,
        "created_at": r.created_at,
        "closed_at": r.closed_at,
        "deltas": [
            {
                "id": d.id,
                "client_id": d.client_id,
                "kind": d.kind,
                "num_examples": d.num_examples,
                "created_at": d.created_at,
                "blob_path": d.blob_path,
                "model_arch": d.model_arch,
            }
            for d in deltas
        ],
    }


@router.post("/rounds/{round_id}/aggregate")
def aggregate(round_id: str, session: Session = Depends(get_session)):
    """
    Aggregate all deltas in this round, produce a new global model, publish it, set as current.
    - Backbone params are averaged across hospitals+patients (weighted by num_examples)
    - Head params are averaged across hospitals only (weighted by num_examples)
    """
    r = _ensure_round(session, round_id)

    # fetch deltas
    q = select(Delta).where(Delta.round_id == r.id)
    deltas = list(session.exec(q))
    if not deltas:
        raise HTTPException(status_code=400, detail="No deltas in this round")

    # get current model state
    st = session.get(Setting, 1)
    if not st or not st.current_model_id:
        raise HTTPException(status_code=400, detail="No current model set")
    cur = session.get(Model, st.current_model_id)
    if not cur:
        raise HTTPException(status_code=400, detail="Current model row missing")

    cur_sd = torch.load(cur.artifact_path, map_location="cpu", weights_only=False)
    if "model" not in cur_sd or not isinstance(cur_sd["model"], dict):
        raise HTTPException(status_code=400, detail="Current model checkpoint missing 'model' state dict")
    global_sd: dict[str, torch.Tensor] = {k: v for k, v in cur_sd["model"].items()}

    # separate hospital/patient deltas and load blobs
    hosp_bb, hosp_hd, w_h = [], [], []
    pat_bb, w_p = [], []

    for d in deltas:
        bb, hd = load_delta_blobs(d.blob_path)
        if d.kind == "hospital":
            if bb:
                hosp_bb.append(bb)
                w_h.append(float(d.num_examples or 0))
            if hd:
                hosp_hd.append(hd)
        else:
            # patient: only backbone
            if bb:
                pat_bb.append(bb)
                w_p.append(float(d.num_examples or 0))

    if not hosp_bb and not pat_bb and not hosp_hd:
        raise HTTPException(status_code=400, detail="No usable delta tensors in round")

    # aggregate typed
    new_sd = typed_aggregate(
        global_sd=global_sd,
        hospital_bb=hosp_bb,
        hospital_hd=hosp_hd,
        patient_bb=pat_bb,
        w_hosp=w_h if w_h else [1.0 for _ in hosp_bb],
        w_pat=w_p if w_p else [1.0 for _ in pat_bb],
    )

    # assemble checkpoint object
    ckpt = {"model": new_sd, "meta": {"base": cur.version, "round_id": r.id, "ts": datetime.now(timezone.utc).isoformat()}}

    # create a new model id and persist artifact into served location
    model_id = str(uuid4())
    out_dir = Path(settings.STORE_ROOT) / "models" / model_id
    out_dir.mkdir(parents=True, exist_ok=True)
    out_g = out_dir / "global.pth"
    torch.save(ckpt, out_g)

    # update symbolic/current copy (optional convenience)
    cur_sym = Path(settings.STORE_ROOT) / "current" / "global_current.pth"
    cur_sym.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(out_g, cur_sym)

    # DB row for new model
    version = f"drfl-b3-{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
    chksum = sha256_file(out_g)
    m = Model(
        id=model_id,
        version=version,
        artifact_path=str(out_g.resolve()),
        checksum=chksum,
        is_current=True,
    )
    session.add(m)
    session.commit()
    session.refresh(m)

    # set as current in settings
    st.current_model_id = m.id
    session.add(st)
    session.commit()

    # close the round
    r.status = "closed"
    r.closed_at = datetime.now(timezone.utc)
    session.add(r)
    session.commit()

    # live event
    try:
        # served under /artifacts/<model_id>/global.pth (StaticFiles mount to STORE_ROOT/models)
        awaitable = publish({
            "type": "model_published",
            "model_id": m.id,
            "version": m.version,
            "checksum": m.checksum,
            "url": f"/artifacts/{m.id}/global.pth",
        })
        # publish is async; if it's a normal async def, schedule it; if it is sync, this is a no-op
        if hasattr(awaitable, "__await__"):
            import anyio
            anyio.from_thread.run(awaitable)  # run in thread if not in async context
    except Exception:
        # Don't fail aggregation if SSE fails
        pass

    return {
        "ok": True,
        "model_id": m.id,
        "version": m.version,
        "checksum": m.checksum,
        "url": f"/artifacts/{m.id}/global.pth",
    }
def _list_rounds(session: Session) -> list[Round]:
    q = select(Round).order_by(Round.created_at.desc())
    return list(session.exec(q))

@router.get("/rounds")
def list_rounds(session: Session = Depends(get_session)):
    rows = _list_rounds(session)
    out = []
    for r in rows:
        # some DBs may not have these attrs yet, so use getattr fallback
        ws = getattr(r, "window_start", None) or r.created_at
        we = getattr(r, "window_end", None) or r.closed_at
        out.append(
            {
                "id": r.id,
                "status": r.status,
                "created_at": r.created_at,
                "closed_at": r.closed_at,
                "window_start": ws,
                "window_end": we,
                "num_hospital": getattr(r, "num_hospital", None),
                "num_patient": getattr(r, "num_patient", None),
            }
        )
    return out