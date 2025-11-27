from sqlmodel import SQLModel, create_engine, Session
from ..core.settings import settings

engine = create_engine(settings.DB_URL, echo=False, connect_args={"check_same_thread": False})

def init_db():
    SQLModel.metadata.create_all(engine)

def get_session():
    with Session(engine) as s:
        yield s
