# from sqlmodel import Session, select
# from datetime import datetime, timedelta, timezone
# from ..db.models import Round, Setting, Delta
# from ..core.events import publish

# def get_or_open_current_round(session: Session) -> Round:
#     now = datetime.now(timezone.utc)
#     r = session.exec(select(Round).where(Round.status == "collecting")).first()
#     if r: return r
#     setting = session.get(Setting, 1) or Setting()
#     end = now + timedelta(minutes=setting.window_minutes)
#     r = Round(window_start=now, window_end=end, status="collecting")
#     session.add(r); session.commit(); session.refresh(r)
#     return r

# def close_round(session: Session, round_id: str):
#     r = session.get(Round, round_id)
#     if not r: return
#     r.status = "aggregating"; session.add(r); session.commit()
#     await_publish = {"type":"round_status","round_id":r.id,"status":"aggregating"}
#     return await_publish

# def count_kinds(session: Session, round_id: str):
#     deltas = session.exec(select(Delta).where(Delta.round_id==round_id)).all()
#     hosp = sum(1 for d in deltas if d.kind=="hospital")
#     pat  = sum(1 for d in deltas if d.kind=="patient")
#     return hosp, pat

# app/services/rounds.py
from __future__ import annotations

import asyncio
from datetime import datetime, timezone, timedelta
from sqlmodel import Session, select

from ..db.models import Round, Setting
from ..core.settings import settings
from ..core.events import publish as sse_publish


def _get_window_minutes(session: Session) -> int:
    st = session.get(Setting, 1)
    if st is not None and getattr(st, "window_minutes", None) is not None:
        try:
            return int(st.window_minutes)
        except Exception:
            pass
    return int(settings.WINDOW_MINUTES)


def _compute_window_end(created_at: datetime, window_minutes: int) -> datetime:
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    return created_at + timedelta(minutes=window_minutes)


def _emit_round_opened_sse(round_id: str, opened_at: datetime, window_minutes: int) -> None:
    payload = {
        "type": "round_opened",
        "round_id": round_id,
        "opened_at": opened_at.isoformat(),
        "window_minutes": int(window_minutes),
    }
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(sse_publish(payload))
    except RuntimeError:
        # best-effort only
        pass


def get_or_open_current_round(session: Session) -> Round:
    now = datetime.now(timezone.utc)
    win = _get_window_minutes(session)

    q = (
        select(Round)
        .where(Round.status == "open")
        .order_by(Round.created_at.desc())
    )
    cur = session.exec(q).first()

    if cur is not None:
        end = _compute_window_end(cur.created_at, win)
        if now < end:
            return cur

        cur.status = "closed"
        cur.closed_at = now
        session.add(cur)
        session.commit()

    # create new round
    r = Round(status="open", created_at=now)
    session.add(r)
    session.commit()
    session.refresh(r)

    _emit_round_opened_sse(r.id, r.created_at, win)
    return r
