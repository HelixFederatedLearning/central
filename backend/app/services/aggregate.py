# # # app/services/aggregate.py
# # from __future__ import annotations
# # from typing import Dict, List, Tuple, Iterable, Optional
# # from datetime import datetime, timezone
# # from pathlib import Path

# # import torch
# # from sqlmodel import Session, select

# # from ..db.models import Round, Delta, Model, Setting
# # from ..core.settings import settings
# # from ..core.storage import sha256_file


# # # ------------------------------
# # # Low-level tensor helpers
# # # ------------------------------

# # def _ensure_float(d: Dict[str, torch.Tensor]) -> Dict[str, torch.Tensor]:
# #     out: Dict[str, torch.Tensor] = {}
# #     for k, v in d.items():
# #         t = v
# #         if not torch.is_floating_point(t):
# #             t = t.float()
# #         out[k] = t
# #     return out


# # def load_delta_blobs(path: str) -> Tuple[Dict[str, torch.Tensor], Optional[Dict[str, torch.Tensor]]]:
# #     """
# #     Return (bb, hd?) dicts from a saved .pt delta.
# #     We force weights_only=False for compatibility with PyTorch>=2.6.
# #     Expected delta structure written by hospital trainer:
# #         {'bb': {...}, 'hd': {...?}}
# #     """
# #     obj = torch.load(path, map_location="cpu", weights_only=False)
# #     bb = _ensure_float(obj.get("bb", {}))
# #     hd = obj.get("hd", None)
# #     if hd is not None:
# #         hd = _ensure_float(hd)
# #     return bb, hd


# # def _merge_keys(dicts: Iterable[Dict[str, torch.Tensor]]) -> List[str]:
# #     keys = set()
# #     for d in dicts:
# #         keys.update(d.keys())
# #     return sorted(keys)


# # def _weighted_mean_dict(dicts: List[Dict[str, torch.Tensor]], weights: List[float]) -> Dict[str, torch.Tensor]:
# #     assert len(dicts) == len(weights) and len(dicts) > 0
# #     keys = _merge_keys(dicts)
# #     totw = float(sum(weights)) if weights else 1.0
# #     if totw == 0.0:
# #         # fall back to simple mean
# #         weights = [1.0 for _ in dicts]
# #         totw = float(len(dicts))
# #     out: Dict[str, torch.Tensor] = {}
# #     for k in keys:
# #         acc: Optional[torch.Tensor] = None
# #         for d, w in zip(dicts, weights):
# #             if k not in d:
# #                 continue
# #             t = d[k].float()
# #             val = t * float(w)
# #             acc = val if acc is None else (acc + val)
# #         if acc is None:
# #             continue
# #         out[k] = acc / totw
# #     return out


# # def typed_aggregate(
# #     global_sd: Dict[str, torch.Tensor],
# #     hospital_bb: List[Dict[str, torch.Tensor]],
# #     hospital_hd: List[Dict[str, torch.Tensor]],
# #     patient_bb: List[Dict[str, torch.Tensor]],
# #     w_hosp: List[float],
# #     w_pat: List[float],
# # ) -> Dict[str, torch.Tensor]:
# #     """
# #     Typed aggregation:
# #       - Backbone (bb): average over hospitals and patients together (weighted by num_examples)
# #       - Head (hd): average over hospitals only (patients don't provide labels)

# #     Returns a *new* state dict built from global_sd then overwritten by the means.
# #     """
# #     new_sd: Dict[str, torch.Tensor] = {k: v.clone() for k, v in global_sd.items()}

# #     # Backbone: hospitals + patients (weights aligned)
# #     bb_updates: List[Dict[str, torch.Tensor]] = []
# #     bb_weights: List[float] = []
# #     if hospital_bb:
# #         bb_updates.extend(hospital_bb)
# #         bb_weights.extend(w_hosp)
# #     if patient_bb:
# #         bb_updates.extend(patient_bb)
# #         bb_weights.extend(w_pat)

# #     if bb_updates:
# #         bb_mean = _weighted_mean_dict(bb_updates, bb_weights)
# #         for k, v in bb_mean.items():
# #             new_sd[k] = v  # replace or add

# #     # Head: hospitals only
# #     if hospital_hd:
# #         hd_mean = _weighted_mean_dict(hospital_hd, w_hosp)
# #         for k, v in hd_mean.items():
# #             new_sd[k] = v  # replace or add

# #     return new_sd


# # # ------------------------------
# # # Persistence helpers
# # # ------------------------------

# # def _load_current_global_state(session: Session) -> Dict[str, torch.Tensor]:
# #     """
# #     Load the current global model tensor dict.
# #     If there's no current model yet, return an empty dict (first round will be purely from deltas).
# #     """
# #     st = session.get(Setting, 1)
# #     if not st or not getattr(st, "current_model_id", None):
# #         return {}
# #     m = session.get(Model, st.current_model_id)
# #     if not m or not m.artifact_path:
# #         return {}
# #     p = Path(m.artifact_path)
# #     if not p.exists():
# #         return {}
# #     obj = torch.load(str(p), map_location="cpu", weights_only=False)
# #     # Accept either {'model': {...}} or a flat sd
# #     if isinstance(obj, dict) and "model" in obj and isinstance(obj["model"], dict):
# #         return {k: v.float() for k, v in obj["model"].items()}
# #     elif isinstance(obj, dict):
# #         # flat dict of tensors
# #         return {k: v.float() for k, v in obj.items()}
# #     return {}


# # def _write_new_global(state_dict: Dict[str, torch.Tensor], model_version: str) -> Path:
# #     tgt_dir = settings.STORE_ROOT / "models" / model_version
# #     tgt_dir.mkdir(parents=True, exist_ok=True)
# #     tgt = tgt_dir / "global.pth"
# #     torch.save({"model": state_dict}, tgt)
# #     return tgt


# # def _distinct_hospitals(deltas: List[Delta]) -> int:
# #     return len(set(d.client_id for d in deltas if (d.kind or "").lower() == "hospital"))


# # def _enough_to_aggregate(session: Session, r: Round, *, force: bool = False) -> tuple[bool, List[Delta], int, int]:
# #     """
# #     Returns (ok, deltas, min_total, min_hosp)
# #     """
# #     st = session.get(Setting, 1)
# #     min_total = (st.min_total if st and st.min_total is not None else 2)
# #     min_hosp = (st.min_hosp if st and st.min_hosp is not None else 1)

# #     deltas = list(session.exec(select(Delta).where(Delta.round_id == r.id)).all())
# #     if force:
# #         return (len(deltas) >= 1, deltas, min_total, min_hosp)

# #     if len(deltas) < min_total:
# #         return (False, deltas, min_total, min_hosp)
# #     if _distinct_hospitals(deltas) < min_hosp:
# #         return (False, deltas, min_total, min_hosp)
# #     return (True, deltas, min_total, min_hosp)


# # # ------------------------------
# # # Entry point from scheduler/route
# # # ------------------------------

# # def aggregate_round_if_ready(session: Session, round_id, *, force: bool = False) -> bool:
# #     """
# #     If round is 'open' and thresholds are met (or force=True), aggregate:
# #       1) collect deltas
# #       2) load current global
# #       3) perform typed aggregation
# #       4) persist new model
# #       5) update settings.current_model_id
# #       6) close round
# #     Returns True if aggregation happened (or the round was closed), False if skipped.
# #     """
# #     r = session.get(Round, round_id)
# #     if not r or r.status != "open":
# #         return False

# #     ok, deltas, min_total, min_hosp = _enough_to_aggregate(session, r, force=force)
# #     if not ok:
# #         # still open—skip silently
# #         return False

# #     # Split deltas by kind and load blobs; gather weights
# #     hosp_bb: List[Dict[str, torch.Tensor]] = []
# #     hosp_hd: List[Dict[str, torch.Tensor]] = []
# #     pat_bb:  List[Dict[str, torch.Tensor]] = []
# #     w_hosp:  List[float] = []
# #     w_pat:   List[float] = []

# #     for d in deltas:
# #         try:
# #             bb, hd = load_delta_blobs(d.path)
# #         except Exception as e:
# #             # skip corrupt/unreadable deltas but keep aggregating the rest
# #             print(f"[aggregate] skip delta {d.id}: {e}")
# #             continue

# #         w = float(d.num_examples or 1)
# #         kind = (d.kind or "").lower()

# #         if kind == "hospital":
# #             if bb: hosp_bb.append(bb); w_hosp.append(w)
# #             if hd: hosp_hd.append(hd)  # head is unweighted separately; uses w_hosp
# #         else:
# #             # include patient (or any other) only in backbone
# #             if bb: pat_bb.append(bb); w_pat.append(w)

# #     # If nothing to aggregate (all skipped or empty), close the round without update
# #     if not hosp_bb and not pat_bb and not hosp_hd:
# #         r.status = "closed"
# #         r.closed_at = datetime.now(timezone.utc)
# #         session.add(r); session.commit()
# #         return True

# #     # Load current global state dict
# #     global_sd = _load_current_global_state(session)

# #     # Run typed aggregation
# #     new_sd = typed_aggregate(global_sd, hosp_bb, hosp_hd, pat_bb, w_hosp, w_pat)

# #     # Persist new model
# #     m = Model(version=f"round-{r.id}", created_at=datetime.now(timezone.utc))
# #     session.add(m); session.commit(); session.refresh(m)

# #     tgt_path = _write_new_global(new_sd, m.id)
# #     m.artifact_path = str(Path(tgt_path).resolve())
# #     session.add(m); session.commit(); session.refresh(m)

# #     # Set as current model
# #     st = session.get(Setting, 1)
# #     if not st:
# #         st = Setting(id=1)
# #     st.current_model_id = m.id
# #     session.add(st); session.commit()

# #     # Close round
# #     r.status = "closed"
# #     r.closed_at = datetime.now(timezone.utc)
# #     session.add(r); session.commit()

# #     # Optional checksum/log
# #     _ = sha256_file(tgt_path)
# #     print(f"[aggregate] round={r.id} -> model={m.id} at {tgt_path} "
# #           f"(min_total={min_total}, min_hosp={min_hosp}, deltas={len(deltas)})")

# #     return True

# from __future__ import annotations

# import os
# from datetime import datetime, timezone
# from typing import Dict, List, Tuple, Iterable

# import torch
# from sqlmodel import Session, select

# from ..db.models import Model, Round, Delta, Setting
# from ..core.storage import sha256_file


# # -----------------------
# # Tensor helpers
# # -----------------------

# def _ensure_float(d: Dict[str, torch.Tensor]) -> Dict[str, torch.Tensor]:
#     out: Dict[str, torch.Tensor] = {}
#     for k, v in d.items():
#         t = v
#         if not torch.is_floating_point(t):
#             t = t.float()
#         out[k] = t
#     return out


# def load_delta_blobs(path: str) -> Tuple[Dict[str, torch.Tensor], Dict[str, torch.Tensor] | None]:
#     """
#     Return (bb, hd?) dicts from a saved .pt delta.
#     We force weights_only=False for compatibility with PyTorch >= 2.6.
#     Structure is expected like: {'bb': {...}, 'hd': {...?}}
#     """
#     obj = torch.load(path, map_location="cpu", weights_only=False)
#     bb = _ensure_float(obj.get("bb", {}))
#     hd = obj.get("hd", None)
#     if hd is not None:
#         hd = _ensure_float(hd)
#     return bb, hd


# def _merge_keys(dicts: Iterable[Dict[str, torch.Tensor]]) -> List[str]:
#     keys = set()
#     for d in dicts:
#         keys.update(d.keys())
#     return sorted(keys)


# def _weighted_mean_dict(dicts: List[Dict[str, torch.Tensor]], weights: List[float]) -> Dict[str, torch.Tensor]:
#     assert len(dicts) == len(weights) and len(dicts) > 0
#     keys = _merge_keys(dicts)
#     totw = float(sum(weights)) if weights else 1.0
#     if totw == 0:
#         # fallback to simple mean
#         weights = [1.0 for _ in dicts]
#         totw = float(len(dicts))

#     out: Dict[str, torch.Tensor] = {}
#     for k in keys:
#         acc = None
#         for d, w in zip(dicts, weights):
#             if k not in d:
#                 continue
#             t = d[k].float()
#             val = t * float(w)
#             acc = val if acc is None else (acc + val)
#         if acc is None:
#             continue
#         out[k] = acc / totw
#     return out


# def typed_aggregate(
#     global_sd: Dict[str, torch.Tensor],
#     hospital_bb: List[Dict[str, torch.Tensor]],
#     hospital_hd: List[Dict[str, torch.Tensor]],
#     patient_bb: List[Dict[str, torch.Tensor]],
#     w_hosp: List[float],
#     w_pat: List[float],
# ) -> Dict[str, torch.Tensor]:
#     """
#     Typed aggregation:
#       - Backbone (bb): average over hospitals and patients together (weighted by num_examples)
#       - Head (hd): average over hospitals only (patients don't provide labels)
#     Updates are applied to a clone of global_sd; keys not present in global are added.
#     """
#     new_sd = {k: v.clone() for k, v in global_sd.items()}

#     # Backbone: hospitals + patients
#     bb_updates: List[Dict[str, torch.Tensor]] = []
#     bb_weights: List[float] = []
#     if hospital_bb:
#         bb_updates.extend(hospital_bb)
#         bb_weights.extend(w_hosp)
#     if patient_bb:
#         bb_updates.extend(patient_bb)
#         bb_weights.extend(w_pat)

#     if bb_updates:
#         bb_mean = _weighted_mean_dict(bb_updates, bb_weights)
#         for k, v in bb_mean.items():
#             new_sd[k] = v

#     # Head: only hospitals
#     if hospital_hd:
#         hd_mean = _weighted_mean_dict(hospital_hd, w_hosp)
#         for k, v in hd_mean.items():
#             new_sd[k] = v

#     return new_sd


# # -----------------------
# # Aggregation + pruning
# # -----------------------

# def _safe_unlink(path: str):
#     try:
#         if path and os.path.exists(path):
#             os.unlink(path)
#     except Exception:
#         # don't crash on file deletion issues
#         pass


# def aggregate_round_if_ready(session: Session, round_id: str, force: bool = False) -> Dict:
#     """
#     Steps:
#       1) Load deltas for the round.
#       2) Aggregate using typed_aggregate.
#       3) Save a new global model artifact.
#       4) Insert new Model row WITH checksum & artifact_path set.
#       5) Update DB: close round, set new current model.
#       6) **Prune** the used deltas (DB rows + files).

#     Returns a small summary dict for logs/UI.
#     """
#     r = session.get(Round, round_id)
#     if not r:
#         raise ValueError(f"Round not found: {round_id}")

#     deltas: List[Delta] = list(session.exec(select(Delta).where(Delta.round_id == round_id)))

#     if not deltas and not force:
#         return {"ok": False, "reason": "no_deltas", "round_id": round_id}

#     # Fetch current global model
#     st = session.get(Setting, 1)
#     if not st or not st.current_model_id:
#         raise ValueError("No current model set in settings")
#     cur_model = session.get(Model, st.current_model_id)
#     if not cur_model or not cur_model.artifact_path:
#         raise ValueError("Current model artifact missing")

#     # Load global state dict (supports {'model': state_dict} or raw state_dict)
#     g_obj = torch.load(cur_model.artifact_path, map_location="cpu", weights_only=False)
#     global_sd: Dict[str, torch.Tensor] = g_obj.get("model", g_obj)

#     # Partition deltas + weights
#     hosp_bb: List[Dict[str, torch.Tensor]] = []
#     hosp_hd: List[Dict[str, torch.Tensor]] = []
#     w_hosp: List[float] = []

#     pat_bb: List[Dict[str, torch.Tensor]] = []
#     w_pat: List[float] = []

#     used_delta_ids: List[str] = []

#     for d in deltas:
#         d_path = getattr(d, "artifact_path", None) or getattr(d, "path", None)
#         if not d_path or not os.path.exists(d_path):
#             continue

#         try:
#             bb, hd = load_delta_blobs(d_path)
#         except Exception:
#             # unreadable / corrupted delta — skip
#             continue

#         n = float(getattr(d, "num_examples", 1.0) or 1.0)

#         if getattr(d, "kind", "") == "hospital":
#             hosp_bb.append(bb)
#             w_hosp.append(n)
#             if hd:
#                 hosp_hd.append(hd)
#         else:
#             pat_bb.append(bb)
#             w_pat.append(n)

#         used_delta_ids.append(d.id)

#     if not used_delta_ids and not force:
#         return {"ok": False, "reason": "no_readable_deltas", "round_id": round_id}

#     # Aggregate and save first (so we have checksum)
#     new_sd = typed_aggregate(
#         global_sd=global_sd,
#         hospital_bb=hosp_bb,
#         hospital_hd=hosp_hd,
#         patient_bb=pat_bb,
#         w_hosp=w_hosp,
#         w_pat=w_pat,
#     )

#     base_dir = os.path.dirname(cur_model.artifact_path) or "."
#     stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
#     new_dir = os.path.join(base_dir, f"model_{stamp}")
#     os.makedirs(new_dir, exist_ok=True)
#     out_path = os.path.join(new_dir, "global.pth")

#     torch.save({"model": new_sd}, out_path)
#     chksum = sha256_file(out_path)

#     # Now insert new Model row with path + checksum
#     new_model = Model(
#         version=f"agg-{stamp}",
#         artifact_path=out_path,
#         checksum=chksum,
#         is_current=False
#     )
#     session.add(new_model)
#     session.commit()
#     session.refresh(new_model)

#     # Close round + switch current model
#     r.status = "closed"
#     r.closed_at = datetime.now(timezone.utc)
#     if hasattr(r, "model_id"):
#         r.model_id = new_model.id
#     elif hasattr(r, "modelId"):
#         r.modelId = new_model.id

#     st.current_model_id = new_model.id

#     if hasattr(r, "aggregate_summary"):
#         r.aggregate_summary = {
#             "used_hospital": len(hosp_bb),
#             "used_patient": len(pat_bb),
#             "sum_w_hosp": float(sum(w_hosp)) if w_hosp else 0.0,
#             "sum_w_pat": float(sum(w_pat)) if w_pat else 0.0,
#             "delta_count": len(used_delta_ids),
#             "artifact_checksum": chksum,
#         }

#     session.add(new_model)
#     session.add(r)
#     session.add(st)
#     session.commit()

#     # Prune used deltas (files + rows)
#     if used_delta_ids:
#         try:
#             used_rows: List[Delta] = list(
#                 session.exec(
#                     select(Delta).where(
#                         Delta.round_id == round_id,
#                         Delta.id.in_(used_delta_ids)
#                     )
#                 )
#             )
#             for d in used_rows:
#                 d_path = getattr(d, "artifact_path", None) or getattr(d, "path", None)
#                 _safe_unlink(d_path)
#             for d in used_rows:
#                 session.delete(d)
#             session.commit()
#             print(f"[aggregate] pruned {len(used_rows)} deltas for round={round_id}")
#         except Exception as e:
#             session.rollback()
#             print(f"[aggregate] prune failed for round={round_id}: {e}")

#     return {
#         "ok": True,
#         "round_id": r.id,
#         "new_model_id": new_model.id,
#         "used_deltas": len(used_delta_ids),
#         "weights": {
#             "hospital_total": float(sum(w_hosp)) if w_hosp else 0.0,
#             "patient_total": float(sum(w_pat)) if w_pat else 0.0,
#         },
#         "artifact_path": out_path,
#         "checksum": chksum,
#     }
# app/services/aggregate.py
from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Dict, List, Tuple, Iterable

import torch
from sqlmodel import Session, select

from ..db.models import Model, Round, Delta, Setting
from ..core.storage import sha256_file


# -----------------------
# Helpers
# -----------------------

def _ensure_float(d: Dict[str, torch.Tensor]) -> Dict[str, torch.Tensor]:
    out: Dict[str, torch.Tensor] = {}
    for k, v in d.items():
        t = v
        if not torch.is_floating_point(t):
            t = t.float()
        out[k] = t
    return out


def load_delta_blobs(path: str) -> Tuple[Dict[str, torch.Tensor], Dict[str, torch.Tensor] | None]:
    """
    Return (bb, hd?) dicts from a saved .pt delta.
    We force weights_only=False for compatibility with PyTorch >= 2.6.
    Structure is expected like: {'bb': {...}, 'hd': {...?}}
    """
    obj = torch.load(path, map_location="cpu", weights_only=False)
    bb = _ensure_float(obj.get("bb", {}))
    hd = obj.get("hd", None)
    if hd is not None:
        hd = _ensure_float(hd)
    return bb, hd


def _merge_keys(dicts: Iterable[Dict[str, torch.Tensor]]) -> List[str]:
    keys = set()
    for d in dicts:
        keys.update(d.keys())
    return sorted(keys)


def _weighted_mean_dict(dicts: List[Dict[str, torch.Tensor]], weights: List[float]) -> Dict[str, torch.Tensor]:
    assert len(dicts) == len(weights) and len(dicts) > 0
    keys = _merge_keys(dicts)
    totw = float(sum(weights)) if weights else 1.0
    if totw == 0:
        weights = [1.0 for _ in dicts]
        totw = float(len(dicts))

    out: Dict[str, torch.Tensor] = {}
    for k in keys:
        acc = None
        for d, w in zip(dicts, weights):
            if k not in d:
                continue
            t = d[k].float()
            val = t * float(w)
            acc = val if acc is None else (acc + val)
        if acc is None:
            continue
        out[k] = acc / totw
    return out


def typed_aggregate(
    global_sd: Dict[str, torch.Tensor],
    hospital_bb: List[Dict[str, torch.Tensor]],
    hospital_hd: List[Dict[str, torch.Tensor]],
    patient_bb: List[Dict[str, torch.Tensor]],
    w_hosp: List[float],
    w_pat: List[float],
) -> Dict[str, torch.Tensor]:
    """
    - Backbone (bb): average hospitals + patients (weighted by num_examples)
    - Head (hd): average hospitals only
    """
    new_sd = {k: v.clone() for k, v in global_sd.items()}

    bb_updates: List[Dict[str, torch.Tensor]] = []
    bb_weights: List[float] = []
    if hospital_bb:
        bb_updates.extend(hospital_bb)
        bb_weights.extend(w_hosp)
    if patient_bb:
        bb_updates.extend(patient_bb)
        bb_weights.extend(w_pat)

    if bb_updates:
        bb_mean = _weighted_mean_dict(bb_updates, bb_weights)
        for k, v in bb_mean.items():
            new_sd[k] = v

    if hospital_hd:
        hd_mean = _weighted_mean_dict(hospital_hd, w_hosp)
        for k, v in hd_mean.items():
            new_sd[k] = v

    return new_sd


# -----------------------
# Aggregation + pruning
# -----------------------

def _safe_unlink(path: str):
    try:
        if path and os.path.exists(path):
            os.unlink(path)
    except Exception:
        pass


def aggregate_round_if_ready(session: Session, round_id: str, force: bool = False) -> Dict:
    """
    Steps:
      1) Gather deltas assigned to the round.
      2) Aggregate -> produce new state dict.
      3) SAVE FILE FIRST (global.pth) + compute checksum.
      4) Insert Model row with artifact_path & checksum set.
      5) Close round + update Setting.current_model_id.
      6) Delete used deltas (files + rows).

    On any exception, rolls back the session and re-raises.
    """
    try:
        r = session.get(Round, round_id)
        if not r:
            raise ValueError(f"Round not found: {round_id}")

        deltas: List[Delta] = list(session.exec(select(Delta).where(Delta.round_id == round_id)))
        if not deltas and not force:
            return {"ok": False, "reason": "no_deltas", "round_id": round_id}

        st = session.get(Setting, 1)
        if not st or not st.current_model_id:
            raise ValueError("No current model set in settings")
        cur_model = session.get(Model, st.current_model_id)
        if not cur_model or not cur_model.artifact_path:
            raise ValueError("Current model artifact missing")

        # Load current global
        g_obj = torch.load(cur_model.artifact_path, map_location="cpu", weights_only=False)
        global_sd: Dict[str, torch.Tensor] = g_obj.get("model", g_obj)

        # Partition updates
        hosp_bb: List[Dict[str, torch.Tensor]] = []
        hosp_hd: List[Dict[str, torch.Tensor]] = []
        w_hosp: List[float] = []

        pat_bb: List[Dict[str, torch.Tensor]] = []
        w_pat: List[float] = []

        used_delta_ids: List[str] = []

        for d in deltas:
            d_path = getattr(d, "artifact_path", None) or getattr(d, "path", None)
            if not d_path or not os.path.exists(d_path):
                continue
            try:
                bb, hd = load_delta_blobs(d_path)
            except Exception:
                continue

            n = float(getattr(d, "num_examples", 1.0) or 1.0)
            if getattr(d, "kind", "") == "hospital":
                hosp_bb.append(bb); w_hosp.append(n)
                if hd: hosp_hd.append(hd)
            else:
                pat_bb.append(bb); w_pat.append(n)
            used_delta_ids.append(d.id)

        if not used_delta_ids and not force:
            return {"ok": False, "reason": "no_readable_deltas", "round_id": round_id}

        # Aggregate
        new_sd = typed_aggregate(
            global_sd=global_sd,
            hospital_bb=hosp_bb,
            hospital_hd=hosp_hd,
            patient_bb=pat_bb,
            w_hosp=w_hosp,
            w_pat=w_pat,
        )

        # SAVE FIRST
        base_dir = os.path.dirname(cur_model.artifact_path) or "."
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        new_dir = os.path.join(base_dir, f"model_{stamp}")
        os.makedirs(new_dir, exist_ok=True)
        out_path = os.path.join(new_dir, "global.pth")
        torch.save({"model": new_sd}, out_path)
        chksum = sha256_file(out_path)

        # Insert model with non-null fields
        new_model = Model(
            version=f"agg-{stamp}",
            artifact_path=out_path,
            checksum=chksum,
            is_current=False,
        )
        session.add(new_model)
        session.commit()
        session.refresh(new_model)

        # Close round + update settings
        r.status = "closed"
        r.closed_at = datetime.now(timezone.utc)
        if hasattr(r, "model_id"):
            r.model_id = new_model.id
        elif hasattr(r, "modelId"):
            r.modelId = new_model.id

        st.current_model_id = new_model.id

        if hasattr(r, "aggregate_summary"):
            r.aggregate_summary = {
                "used_hospital": len(hosp_bb),
                "used_patient": len(pat_bb),
                "sum_w_hosp": float(sum(w_hosp)) if w_hosp else 0.0,
                "sum_w_pat": float(sum(w_pat)) if w_pat else 0.0,
                "delta_count": len(used_delta_ids),
                "artifact_checksum": chksum,
            }

        session.add(r)
        session.add(st)
        session.commit()

        # PRUNE used deltas (files + rows)
        if used_delta_ids:
            used_rows: List[Delta] = list(session.exec(select(Delta).where(Delta.id.in_(used_delta_ids))))
            for d in used_rows:
                d_path = getattr(d, "artifact_path", None) or getattr(d, "path", None)
                _safe_unlink(d_path)
            for d in used_rows:
                session.delete(d)
            session.commit()

        return {
            "ok": True,
            "round_id": r.id,
            "new_model_id": new_model.id,
            "used_deltas": len(used_delta_ids),
            "weights": {
                "hospital_total": float(sum(w_hosp)) if w_hosp else 0.0,
                "patient_total": float(sum(w_pat)) if w_pat else 0.0,
            },
            "artifact_path": out_path,
            "checksum": chksum,
        }

    except Exception as e:
        session.rollback()   # <<< IMPORTANT so subsequent ticks don’t die
        raise
