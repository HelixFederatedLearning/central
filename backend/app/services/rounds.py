from sqlmodel import Session, select
from datetime import datetime, timedelta, timezone
from ..db.models import Round, Setting, Delta
from ..core.events import publish

def get_or_open_current_round(session: Session) -> Round:
    now = datetime.now(timezone.utc)
    r = session.exec(select(Round).where(Round.status == "collecting")).first()
    if r: return r
    setting = session.get(Setting, 1) or Setting()
    end = now + timedelta(minutes=setting.window_minutes)
    r = Round(window_start=now, window_end=end, status="collecting")
    session.add(r); session.commit(); session.refresh(r)
    return r

def close_round(session: Session, round_id: str):
    r = session.get(Round, round_id)
    if not r: return
    r.status = "aggregating"; session.add(r); session.commit()
    await_publish = {"type":"round_status","round_id":r.id,"status":"aggregating"}
    return await_publish

def count_kinds(session: Session, round_id: str):
    deltas = session.exec(select(Delta).where(Delta.round_id==round_id)).all()
    hosp = sum(1 for d in deltas if d.kind=="hospital")
    pat  = sum(1 for d in deltas if d.kind=="patient")
    return hosp, pat
