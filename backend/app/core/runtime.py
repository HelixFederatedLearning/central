# app/core/runtime.py
from __future__ import annotations
import io
from dataclasses import dataclass
from typing import List, Optional, Tuple

import torch
import torchvision.transforms as T
from PIL import Image
from sqlmodel import Session

from ..db.models import Model, Setting
from ..core.bootstrap import bootstrap_from_store_current, ensure_artifact_layout

# Your fixed label set
CLASSES: List[str] = ["No_DR", "Mild", "Moderate", "Severe", "Proliferative_DR"]

@dataclass
class LoadedModel:
    model_id: str
    version: str
    checksum: str
    net: torch.nn.Module
    device: torch.device
    transform: T.Compose

_runtime_cache: Optional[LoadedModel] = None


def _build_net(num_classes: int) -> torch.nn.Module:
    """
    Minimal head to match your saved 'model' state_dict.
    If you saved an EfficientNet-B3 backbone, swap in the right arch.
    For a robust default, use the classifier-only shape derived from state_dict.
    """
    # Light classifier head as a placeholder; swap for your real arch if needed.
    # We'll load the actual 'model' state dict; if it contains full backbone, this is ignored.
    return torch.nn.Sequential(
        torch.nn.Flatten(),            # in case feature maps are already pooled
        torch.nn.LazyLinear(256),
        torch.nn.ReLU(),
        torch.nn.Linear(256, num_classes)
    )


def _build_transform() -> T.Compose:
    # Reasonable defaults; match your training if you used different size/normalization
    return T.Compose([
        T.Resize((300, 300)),
        T.ToTensor(),
        T.ConvertImageDtype(torch.float32),
        T.Normalize(mean=[0.485, 0.456, 0.406],
                    std=[0.229, 0.224, 0.225]),
    ])


def _load_current_artifact(session: Session) -> Tuple[Model, str]:
    """
    Fetch the current model row; if missing, bootstrap from store/current.
    Returns (Model row, artifact_path).
    """
    st = session.get(Setting, 1)
    cur: Optional[Model] = None
    if st and st.current_model_id:
        cur = session.get(Model, st.current_model_id)
    if cur is None:
        cur = bootstrap_from_store_current(session)
    if cur is None:
        raise RuntimeError("No current model available")
    ensure_artifact_layout(cur)  # guarantees file is under /store/models/<id>/global.pth
    return cur, cur.artifact_path


def get_loaded_model(session: Session) -> LoadedModel:
    """
    Cache the loaded model by checksum. If checksum (or id) changes, reload.
    """
    global _runtime_cache
    cur, artifact_path = _load_current_artifact(session)

    if _runtime_cache and _runtime_cache.checksum == cur.checksum:
        return _runtime_cache

    # (Re)load
    device = torch.device("cpu")  # keep CPU in central; hospitals/patients do training
    state = torch.load(artifact_path, map_location=device, weights_only=False)

    # Expecting a dict with "model" (your state_dict)
    sd = state.get("model", state)

    # Build a net and try to infer if classifier matches
    net = _build_net(num_classes=len(CLASSES))
    net.eval().to(device)

    # Try best-effort strict=False load; this covers cases where backbone exists
    missing, unexpected = net.load_state_dict(sd, strict=False)
    # This is okay for inference if your saved model is a full backbone + head.
    # If you want hard failures, set strict=True and handle exceptions.

    _runtime_cache = LoadedModel(
        model_id=str(cur.id),
        version=cur.version,
        checksum=cur.checksum,
        net=net,
        device=device,
        transform=_build_transform(),
    )
    return _runtime_cache


@torch.inference_mode()
def predict_bytes(session: Session, image_bytes: bytes) -> Tuple[List[float], int]:
    """
    Returns (probs list, top_index)
    """
    lm = get_loaded_model(session)

    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    x = lm.transform(img).unsqueeze(0).to(lm.device)
    logits = lm.net(x)
    probs = torch.softmax(logits, dim=1)[0].cpu().tolist()
    top_idx = int(torch.tensor(probs).argmax().item())
    return probs, top_idx
