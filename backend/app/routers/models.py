# # # app/routers/models.py
# # from datetime import datetime
# # from typing import Optional

# # from fastapi import APIRouter, Depends, HTTPException
# # from pydantic import BaseModel
# # from sqlmodel import Session

# # from ..db.session import get_session
# # from ..db.models import Model, Setting
# # from ..core.settings import settings
# # from ..core.bootstrap import (
# #     bootstrap_from_store_current,
# #     promote_latest_if_missing,
# #     ensure_artifact_layout,
# # )

# # router = APIRouter()


# # class ModelOut(BaseModel):
# #     id: str
# #     version: str
# #     checksum: str
# #     created_at: datetime
# #     url: str


# # @router.get("/models/current", response_model=ModelOut)
# # def get_current(session: Session = Depends(get_session)):
# #     # 1) Try explicit current pointer
# #     st = session.get(Setting, 1)
# #     cur: Optional[Model] = None
# #     if st and st.current_model_id:
# #         cur = session.get(Model, st.current_model_id)

# #     # 2) If not set, try bootstrapping from store/current/global_current.pth
# #     if cur is None:
# #         cur = bootstrap_from_store_current(session)

# #     # 3) If still none, promote the newest aggregated model (if any)
# #     if cur is None:
# #         cur = promote_latest_if_missing(session)

# #     if cur is None:
# #         raise HTTPException(status_code=404, detail="No current model")

# #     # Ensure the file is being served under /artifacts/<id>/global.pth
# #     ensure_artifact_layout(cur)

# #     return ModelOut(
# #         id=cur.id,
# #         version=cur.version,
# #         checksum=cur.checksum,
# #         created_at=cur.created_at,
# #         url=f"/artifacts/{cur.id}/global.pth",
# #     )

# # app/routers/models.py
# from fastapi import APIRouter, Depends, HTTPException
# from pydantic import BaseModel
# from sqlmodel import Session
# from pathlib import Path

# from ..db.session import get_session
# from ..db.models import Model, Setting
# from ..core.settings import settings
# from ..core.bootstrap import bootstrap_from_store_current

# router = APIRouter()

# class ModelOut(BaseModel):
#     id: str
#     version: str
#     checksum: str
#     created_at: str
#     url: str
#     onnx_url: str | None = None

# @router.get("/models/current", response_model=ModelOut)
# def get_current(session: Session = Depends(get_session)):
#     st = session.get(Setting, 1)
#     cur = session.get(Model, st.current_model_id) if (st and st.current_model_id) else None
#     if not cur:
#         cur = bootstrap_from_store_current(session)
#         if not cur:
#             raise HTTPException(404, "No current model")

#     models_dir = settings.STORE_ROOT / "models"
#     rel_dir = cur.id  # served as /artifacts/<id>/
#     pth_url = f"/artifacts/{rel_dir}/global.pth"

#     # try a few common names for ONNX
#     candidates = ["model.onnx", "global.onnx", "central.onnx"]
#     onnx_url = None
#     for name in candidates:
#         p = models_dir / rel_dir / name
#         if p.is_file():
#             onnx_url = f"/artifacts/{rel_dir}/{name}"
#             break

#     return ModelOut(
#         id=str(cur.id),
#         version=cur.version,
#         checksum=cur.checksum,
#         created_at=cur.created_at.isoformat(),
#         url=pth_url,
#         onnx_url=onnx_url,
#     )

# app/routers/models.py
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select
from pathlib import Path
import shutil
import os

from ..db.session import get_session
from ..db.models import Model, Setting
from ..core.settings import settings
from ..core.bootstrap import bootstrap_from_store_current
from ..core.storage import sha256_file

router = APIRouter()


class ModelOut(BaseModel):
  id: str
  version: str
  checksum: str
  created_at: str
  url: str
  onnx_url: str | None = None


# ---------- helpers ----------

def _models_root() -> Path:
  return settings.STORE_ROOT / "models"

def _canonical_dir(model_id: str) -> Path:
  return _models_root() / model_id

def _canonical_pth(model_id: str) -> Path:
  return _canonical_dir(model_id) / "global.pth"

def _first_existing(path_list):
  for p in path_list:
    p = Path(p)
    if p.is_file():
      return p
  return None

def _discover_any_pth_under_models() -> tuple[Path, str] | None:
  """
  Look for any *.pth file under store/models/** and return (file_path, model_id_dir_name).
  Preference order:
    1) store/models/<id>/global.pth
    2) any *.pth directly under store/models/<id>/
    3) any *.pth under deeper subdirs (e.g., model_YYYYmmdd_*)
  """
  root = _models_root()
  if not root.exists():
    return None

  # 1) exact canonical matches
  for d in root.iterdir():
    if d.is_dir():
      p = d / "global.pth"
      if p.is_file():
        return p, d.name

  # 2) any *.pth one level deep
  for d in root.iterdir():
    if d.is_dir():
      candidates = sorted(d.glob("*.pth"))
      if candidates:
        return candidates[0], d.name

  # 3) any *.pth at deeper levels
  for p in root.rglob("*.pth"):
    # closest <id> dir above it (immediate child of root)
    try:
      rel = p.relative_to(root)
      model_id = rel.parts[0]  # top-level directory name
      return p, model_id
    except Exception:
      continue

  return None

def _ensure_checksum(session: Session, m: Model, file_path: Path):
  try:
    c = sha256_file(str(file_path))
  except Exception as e:
    raise HTTPException(status_code=500, detail=f"Failed to hash model: {e}")
  if not getattr(m, "checksum", None) or m.checksum != c:
    m.checksum = c
    session.add(m)
    session.commit()
    session.refresh(m)
  return c

def _normalize_layout(session: Session, m: Model) -> tuple[str, str | None]:
  """
  Ensure there is a canonical file at:
      /artifacts/<model_id>/global.pth
  If not, try to:
    - copy from m.artifact_path (if valid)
    - or use any *.pth found under store/models/<m.id>/
    - else raise 404
  Also backfill checksum.
  """
  models_dir = _models_root()
  models_dir.mkdir(parents=True, exist_ok=True)

  cdir = _canonical_dir(str(m.id))
  cdir.mkdir(parents=True, exist_ok=True)
  target = _canonical_pth(str(m.id))

  # Try to materialize canonical file
  if not target.is_file():
    # source preference: DB artifact_path
    src = Path(getattr(m, "artifact_path", "")) if getattr(m, "artifact_path", None) else None
    picked = None
    if src and src.is_file():
      picked = src
    else:
      # any *.pth in the model-id dir
      first = _first_existing(list((cdir).glob("*.pth")))
      if first:
        picked = first
      else:
        # any *.pth under the model id dir recursively
        nested = next(cdir.rglob("*.pth"), None)
        if nested:
          picked = nested

    if not picked:
      # Last chance: search anywhere in store/models and adopt it (fixes empty DB / moved files)
      discovered = _discover_any_pth_under_models()
      if discovered:
        picked, model_id_guess = discovered
        # If discovered belongs to a different id, switch the model to that id's folder by moving file in place
        if model_id_guess != str(m.id):
          # copy into our canonical folder
          try:
            shutil.copyfile(picked, target)
          except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to copy discovered model: {e}")
        else:
          try:
            shutil.copyfile(picked, target)
          except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to normalize model file: {e}")
      else:
        raise HTTPException(status_code=404, detail="Current model artifact not found in store")

    # If we had a source, copy it
    if not target.is_file() and picked:
      try:
        shutil.copyfile(picked, target)
      except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to copy model artifact into store: {e}")

  # sync DB path to canonical
  canonical_path = str(target)
  if getattr(m, "artifact_path", None) != canonical_path:
    m.artifact_path = canonical_path
    session.add(m)
    session.commit()
    session.refresh(m)

  # checksum
  checksum = _ensure_checksum(session, m, target)

  # onnx sidecar
  onnx_url = None
  for name in ("model.onnx", "global.onnx", "central.onnx"):
    p = cdir / name
    if p.is_file():
      onnx_url = f"/artifacts/{m.id}/{name}"
      break

  return f"/artifacts/{m.id}/global.pth", onnx_url


# ---------- endpoint ----------

@router.get("/models/current", response_model=ModelOut)
def get_current(session: Session = Depends(get_session)):
  # 1) Try via Setting
  st = session.get(Setting, 1)
  cur = session.get(Model, st.current_model_id) if (st and st.current_model_id) else None

  # 2) Try bootstrap helper (your original behavior)
  if not cur:
    cur = bootstrap_from_store_current(session)

  # 3) If still nothing, try to discover any .pth under store/models and create a Model row
  if not cur:
    found = _discover_any_pth_under_models()
    if not found:
      raise HTTPException(404, "No current model")
    pth, model_id_guess = found
    # create or reuse a Model row with this id-like directory
    cur = Model(version="bootstrap", artifact_path=str(pth))
    session.add(cur)
    session.commit()
    session.refresh(cur)
    # ensure Setting row exists and points to this model
    if not st:
      st = Setting(id=1, current_model_id=cur.id)
      session.add(st)
    else:
      st.current_model_id = cur.id
      session.add(st)
    session.commit()
    session.refresh(st)

  # 4) Normalize layout, backfill checksum, return stable URLs
  pth_url, onnx_url = _normalize_layout(session, cur)

  return ModelOut(
    id=str(cur.id),
    version=cur.version,
    checksum=cur.checksum,
    created_at=cur.created_at.isoformat(),
    url=pth_url,
    onnx_url=onnx_url,
  )
