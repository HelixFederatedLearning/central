#!/usr/bin/env python
import argparse
from pathlib import Path
from datetime import datetime
import sys

import torch
import timm

# Allow "app.*" imports when running from scripts/
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.db.session import engine, init_db  # <-- init_db added
from app.db.models import Model, Setting
from sqlmodel import Session


def find_current_artifact_from_db() -> tuple[Path, str]:
    """Return (artifact_path, model_id) for the current model from DB."""
    # Ensure DB schema exists
    init_db()

    with Session(engine) as s:
        st = s.get(Setting, 1)
        if not st:
            # create default settings row if missing
            st = Setting(id=1)
            s.add(st)
            s.commit()
            s.refresh(st)

        if not st.current_model_id:
            raise SystemExit(
                "No current model set in DB (Setting.id=1 missing current_model_id). "
                "Either set it via the API or run with --ckpt <path>."
            )
        m = s.get(Model, st.current_model_id)
        if not m or not m.artifact_path:
            raise SystemExit("Current model row missing or artifact_path not set.")
        p = Path(m.artifact_path).resolve()
        if not p.is_file():
            raise SystemExit(f"Artifact path does not exist: {p}")
        return p, str(m.id)


def guess_num_classes(state_dict: dict, default: int = 5) -> int:
    """
    Try to infer num_classes from typical classifier heads.
    """
    sd = state_dict.get("model", state_dict)
    for k in ("classifier.bias", "fc.bias", "head.bias", "classifer.bias"):
        b = sd.get(k)
        if isinstance(b, torch.Tensor) and b.dim() == 1:
            return int(b.numel())
    return default


def load_into_timm(state_dict: dict, num_classes: int):
    """
    Build a timm EfficientNet-B3 and load weights with strict=False.
    """
    model = timm.create_model("tf_efficientnet_b3_ns", pretrained=False, num_classes=num_classes)
    sd = state_dict.get("model", state_dict)
    missing, unexpected = model.load_state_dict(sd, strict=False)
    if missing:
        print(f"[export_onnx] Warning: {len(missing)} missing keys.")
    if unexpected:
        print(f"[export_onnx] Warning: {len(unexpected)} unexpected keys.")
    model.eval()
    return model


def main():
    ap = argparse.ArgumentParser(description="Export current central model to ONNX.")
    ap.add_argument("--ckpt", type=str, default=None,
                    help="Path to a .pth checkpoint (if omitted, use DB current model).")
    ap.add_argument("--out", type=str, default=None,
                    help="Output ONNX path (default: alongside artifact as model.onnx).")
    ap.add_argument("--opset", type=int, default=13, help="ONNX opset version.")
    ap.add_argument("--img-size", type=int, default=300, help="Input size (EffNet-B3 = 300).")
    args = ap.parse_args()

    if args.ckpt:
        ckpt_path = Path(args.ckpt).resolve()
        model_id = "manual"
    else:
        ckpt_path, model_id = find_current_artifact_from_db()

    if not ckpt_path.is_file():
        raise SystemExit(f"Checkpoint not found: {ckpt_path}")

    print(f"[export_onnx] Loading checkpoint: {ckpt_path}")
    # weights_only=False to allow legacy pickled tensors
    state = torch.load(str(ckpt_path), map_location="cpu", weights_only=False)

    num_classes = guess_num_classes(state, default=5)
    print(f"[export_onnx] Inferred num_classes={num_classes}")

    model = load_into_timm(state, num_classes=num_classes)

    if args.out:
        onnx_path = Path(args.out).resolve()
        onnx_path.parent.mkdir(parents=True, exist_ok=True)
    else:
        onnx_path = ckpt_path.parent / "model.onnx"

    dummy = torch.randn(1, 3, args.img_size, args.img_size, dtype=torch.float32)
    print(f"[export_onnx] Exporting to: {onnx_path}")
    torch.onnx.export(
        model,
        dummy,
        str(onnx_path),
        input_names=["input"],
        output_names=["logits"],
        opset_version=args.opset,
        dynamic_axes={"input": {0: "batch"}, "logits": {0: "batch"}},
    )
    size = onnx_path.stat().st_size if onnx_path.exists() else 0
    print(f"[export_onnx] Done. {onnx_path} ({size/1024:.1f} KB)  {datetime.now()}")


if __name__ == "__main__":
    main()
