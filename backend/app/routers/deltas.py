# from __future__ import annotations

# from datetime import datetime, timezone
# from uuid import uuid4

# from fastapi import APIRouter, UploadFile, File, Form, Depends
# from sqlmodel import Session

# from ..db.session import get_session
# from ..db.models import Delta
# from ..services.rounds import get_or_open_current_round
# from ..core.storage import save_delta
# from ..core.events import publish

# router = APIRouter()


# @router.post("/deltas")
# async def post_delta(
#     client_id: str = Form(...),
#     kind: str = Form(...),                 # "hospital" | "patient"
#     num_examples: int = Form(...),
#     model_arch: str = Form("tv_effnet_b3"),
#     sd_keys_hash: str = Form(""),
#     delta: UploadFile = File(...),
#     session: Session = Depends(get_session),
# ):
#     rnd = get_or_open_current_round(session)
#     delta_id = str(uuid4())
#     path = save_delta(rnd.id, client_id, f"{delta_id}.pt", delta.file)

#     row = Delta(
#         round_id=rnd.id,
#         client_id=client_id,
#         kind=kind,
#         num_examples=num_examples,
#         blob_path=str(path),
#         sd_keys_hash=sd_keys_hash,
#         model_arch=model_arch,
#     )
#     session.add(row)
#     session.commit()

#     # 👇 THIS is what the Dashboard.tsx expects
#     now_iso = datetime.now(timezone.utc).isoformat()
#     await publish({
#         "type": "delta_received",
#         "client_id": client_id,
#         "kind": kind,
#         "round_id": rnd.id,
#         "num_examples": num_examples,
#         "received_at": now_iso,
#     })

#     return {"ok": True, "delta_id": delta_id, "round_id": rnd.id}
# app/routers/deltas.py
# from fastapi import APIRouter, UploadFile, File, Form, Depends
# from sqlmodel import Session
# from uuid import uuid4
# from datetime import datetime, timezone

# from ..db.session import get_session
# from ..db.models import Delta
# from ..services.rounds import get_or_open_current_round
# from ..core.storage import save_delta
# from ..core.events import publish

# router = APIRouter()


# @router.post("/deltas")
# async def post_delta(
#     client_id: str = Form(...),
#     kind: str = Form(...),                 # "hospital" | "patient"
#     num_examples: int = Form(...),
#     model_arch: str = Form("tv_effnet_b3"),
#     sd_keys_hash: str = Form(""),
#     delta: UploadFile = File(...),
#     session: Session = Depends(get_session),
# ):
#     """
#     Receive a delta from a client (hospital/patient), attach it to the
#     current open round, persist the blob + DB row, and emit an SSE event
#     that the Dashboard/FedEventsProvider understands.
#     """
#     # Get or create the current round
#     rnd = get_or_open_current_round(session)

#     # Persist the delta blob under store/deltas/<round>/<client>/<delta_id>.pt
#     delta_id = str(uuid4())
#     path = save_delta(rnd.id, client_id, f"{delta_id}.pt", delta.file)

#     # DB row
#     row = Delta(
#         round_id=rnd.id,
#         client_id=client_id,
#         kind=kind,
#         num_examples=num_examples,
#         blob_path=str(path),
#         sd_keys_hash=sd_keys_hash,
#         model_arch=model_arch,
#     )
#     session.add(row)
#     session.commit()

#     # Timestamp for UI
#     now_iso = datetime.now(timezone.utc).isoformat()

#     # 🔴 This payload shape must match the TS types (DeltaReceivedEvt) used in
#     #     - src/state/FedEventsProvider.tsx
#     #     - src/pages/Dashboard.tsx
#     #
#     # Dashboard expects:
#     #   type: "delta_received"
#     #   client_id: string
#     #   kind: "hospital" | "patient"
#     #   round_id: string
#     #   num_examples: number
#     #   received_at: string (ISO)
#     await publish(
#         {
#             "type": "delta_received",
#             "client_id": client_id,
#             "kind": kind,
#             "round_id": rnd.id,
#             "num_examples": num_examples,
#             "received_at": now_iso,
#         }
#     )

#     return {"ok": True, "delta_id": delta_id, "round_id": rnd.id}
# app/routers/deltas.py
from fastapi import APIRouter, UploadFile, File, Form, Depends
from sqlmodel import Session
from uuid import uuid4
from datetime import datetime, timezone

from ..db.session import get_session
from ..db.models import Delta
from ..services.rounds import get_or_open_current_round
from ..core.storage import save_delta
from ..core.events import publish   # <-- IMPORTANT: from core.events

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
    """
    Receive a delta from a client, attach to the current open round,
    persist the blob + DB row, and emit an SSE event that the Dashboard understands.
    """
    # 1) Get or create open round
    rnd = get_or_open_current_round(session)

    # 2) Save delta blob
    delta_id = str(uuid4())
    path = save_delta(rnd.id, client_id, f"{delta_id}.pt", delta.file)

    # 3) Insert DB row
    row = Delta(
        round_id=rnd.id,
        client_id=client_id,
        kind=kind,
        num_examples=num_examples,
        blob_path=str(path),
        sd_keys_hash=sd_keys_hash,
        model_arch=model_arch,
    )
    session.add(row)
    session.commit()

    # 4) Emit SSE event (shape matches FedEventsProvider / Dashboard types)
    now_iso = datetime.now(timezone.utc).isoformat()

    await publish(
        {
            "type": "delta_received",
            "client_id": client_id,
            "kind": kind,
            "round_id": rnd.id,
            "num_examples": num_examples,
            "received_at": now_iso,
        }
    )

    return {"ok": True, "delta_id": delta_id, "round_id": rnd.id}
