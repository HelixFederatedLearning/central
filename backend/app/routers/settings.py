from fastapi import APIRouter, Depends
from sqlmodel import Session
from ..db.session import get_session
from ..db.models import Setting

router = APIRouter()

@router.get("/settings")
def get_settings(session: Session = Depends(get_session)):
    st = session.get(Setting, 1) or Setting()
    if st.id != 1:
        st.id = 1
        session.add(st); session.commit()
    return st

@router.post("/settings")
def update_settings(payload: Setting, session: Session = Depends(get_session)):
    payload.id = 1
    session.add(payload); session.commit()
    return payload
