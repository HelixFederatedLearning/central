# app/core/bootstrap.py
from pathlib import Path
from datetime import datetime, timezone
from sqlmodel import Session, select
from ..db.models import Model, Setting
from .storage import sha256_file

def ensure_artifact_layout(model: Model) -> str:
    """Copy model file into store/models/<id>/global.pth so it's served via /artifacts."""
    from ..core.settings import settings
    models_root = settings.STORE_ROOT / "models"
    models_root.mkdir(parents=True, exist_ok=True)
    mdir = models_root / model.id
    mdir.mkdir(parents=True, exist_ok=True)
    target = mdir / "global.pth"
    src = Path(model.artifact_path)
    if not src.exists():
        raise FileNotFoundError(f"artifact missing on disk: {src}")
    if src.resolve() != target.resolve():
        target.write_bytes(src.read_bytes())
        model.artifact_path = str(target.resolve())
    return model.artifact_path

def bootstrap_from_store_current(session: Session) -> Model | None:
    """If store/current/global_current.pth exists, register it as current."""
    from ..core.settings import settings
    curp = settings.STORE_ROOT / "current" / "global_current.pth"
    if not curp.is_file():
        return None
    stamp = datetime.now(timezone.utc).strftime("bootstrap-%Y%m%d_%H%M%S")
    checksum = sha256_file(curp)
    m = Model(version=stamp, checksum=checksum, artifact_path=str(curp.resolve()), is_current=True)
    session.add(m); session.commit(); session.refresh(m)
    ensure_artifact_layout(m)
    st = session.get(Setting, 1) or Setting(id=1)
    st.current_model_id = m.id
    session.add(st); session.commit()
    return m

def promote_latest_if_missing(session: Session) -> Model | None:
    """If no current model set, promote newest Model row and mark as current."""
    st = session.get(Setting, 1) or Setting(id=1)
    if st.current_model_id:
        return session.get(Model, st.current_model_id)
    latest = session.exec(select(Model).order_by(Model.created_at.desc())).first()
    if latest is None:
        return None
    latest.is_current = True
    session.add(latest); session.commit()
    st.current_model_id = latest.id
    session.add(st); session.commit()
    ensure_artifact_layout(latest)
    return latest
