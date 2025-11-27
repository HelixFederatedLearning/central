from pathlib import Path
from .settings import settings
import shutil, hashlib

def save_delta(round_id: str, client_id: str, filename: str, fileobj) -> Path:
    dst = settings.STORE_ROOT / "deltas" / round_id / client_id
    dst.mkdir(parents=True, exist_ok=True)
    out = dst / filename
    with open(out, "wb") as f:
        shutil.copyfileobj(fileobj, f)
    return out

def save_model(artifact_bytes: bytes, name: str) -> Path:
    path = settings.STORE_ROOT / "models" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as f:
        f.write(artifact_bytes)
    return path

def set_current_global(path: Path):
    cur = settings.STORE_ROOT / "current" / "global_current.pth"
    shutil.copy2(path, cur)

def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()
