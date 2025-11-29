# # app/services/aggregate.py
# from __future__ import annotations

# import os
# from datetime import datetime, timezone
# from typing import Dict, List, Tuple, Iterable

# import torch
# from sqlmodel import Session, select

# from ..db.models import Model, Round, Delta, Setting
# from ..core.storage import sha256_file
# from ..routers.events import (
#     emit_round_aggregated,
#     emit_current_model_updated,
# )

# # -----------------------
# # Helpers
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
#     - Backbone (bb): average hospitals + patients (weighted by num_examples)
#     - Head (hd): average hospitals only
#     """
#     new_sd = {k: v.clone() for k, v in global_sd.items()}

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
#         pass


# def aggregate_round_if_ready(session: Session, round_id: str, force: bool = False) -> Dict:
#     """
#     Steps:
#       1) Gather deltas assigned to the round.
#       2) Aggregate -> produce new state dict.
#       3) SAVE FILE FIRST (global.pth) + compute checksum.
#       4) Insert Model row with artifact_path & checksum set.
#       5) Close + mark round as aggregated, update Setting.current_model_id.
#       6) Delete used deltas (files + rows).
#       7) Emit SSE events for Dashboard (round_aggregated + current_model_updated).
#     """
#     try:
#         r = session.get(Round, round_id)
#         if not r:
#             raise ValueError(f"Round not found: {round_id}")

#         deltas: List[Delta] = list(session.exec(select(Delta).where(Delta.round_id == round_id)))
#         if not deltas and not force:
#             return {"ok": False, "reason": "no_deltas", "round_id": round_id}

#         st = session.get(Setting, 1)
#         if not st or not st.current_model_id:
#             raise ValueError("No current model set in settings")
#         cur_model = session.get(Model, st.current_model_id)
#         if not cur_model or not cur_model.artifact_path:
#             raise ValueError("Current model artifact missing")

#         # Load current global checkpoint
#         g_obj = torch.load(cur_model.artifact_path, map_location="cpu", weights_only=False)
#         global_sd: Dict[str, torch.Tensor] = g_obj.get("model", g_obj)

#         # Partition updates
#         hosp_bb: List[Dict[str, torch.Tensor]] = []
#         hosp_hd: List[Dict[str, torch.Tensor]] = []
#         w_hosp: List[float] = []

#         pat_bb: List[Dict[str, torch.Tensor]] = []
#         w_pat: List[float] = []

#         used_delta_ids: List[str] = []

#         for d in deltas:
#             d_path = getattr(d, "artifact_path", None) or getattr(d, "path", None)
#             if not d_path or not os.path.exists(d_path):
#                 continue
#             try:
#                 bb, hd = load_delta_blobs(d_path)
#             except Exception:
#                 continue

#             n = float(getattr(d, "num_examples", 1.0) or 1.0)
#             if getattr(d, "kind", "") == "hospital":
#                 hosp_bb.append(bb); w_hosp.append(n)
#                 if hd: hosp_hd.append(hd)
#             else:
#                 pat_bb.append(bb); w_pat.append(n)
#             used_delta_ids.append(d.id)

#         if not used_delta_ids and not force:
#             return {"ok": False, "reason": "no_readable_deltas", "round_id": round_id}

#         # Aggregate
#         new_sd = typed_aggregate(
#             global_sd=global_sd,
#             hospital_bb=hosp_bb,
#             hospital_hd=hosp_hd,
#             patient_bb=pat_bb,
#             w_hosp=w_hosp,
#             w_pat=w_pat,
#         )

#         # SAVE FIRST
#         base_dir = os.path.dirname(cur_model.artifact_path) or "."
#         stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
#         new_dir = os.path.join(base_dir, f"model_{stamp}")
#         os.makedirs(new_dir, exist_ok=True)
#         out_path = os.path.join(new_dir, "global.pth")
#         torch.save({"model": new_sd}, out_path)
#         chksum = sha256_file(out_path)

#         # Insert model row
#         new_model = Model(
#             version=f"agg-{stamp}",
#             artifact_path=out_path,
#             checksum=chksum,
#             is_current=False,
#         )
#         session.add(new_model)
#         session.commit()
#         session.refresh(new_model)

#         # Close / mark round as aggregated, update settings
#         r.status = "aggregated"
#         r.closed_at = datetime.now(timezone.utc)
#         if hasattr(r, "model_id"):
#             r.model_id = new_model.id
#         elif hasattr(r, "modelId"):
#             r.modelId = new_model.id

#         st.current_model_id = new_model.id

#         if hasattr(r, "aggregate_summary"):
#             r.aggregate_summary = {
#                 "used_hospital": len(hosp_bb),
#                 "used_patient": len(pat_bb),
#                 "sum_w_hosp": float(sum(w_hosp)) if w_hosp else 0.0,
#                 "sum_w_pat": float(sum(w_pat)) if w_pat else 0.0,
#                 "delta_count": len(used_delta_ids),
#                 "artifact_checksum": chksum,
#             }

#         session.add(r)
#         session.add(st)
#         session.commit()

#         # Emit SSE events *after* commit so dashboard sees stable state
#         agg_ts = r.closed_at.isoformat() if r.closed_at else datetime.now(timezone.utc).isoformat()

#         emit_round_aggregated(
#             round_id=r.id,
#             aggregated_at=agg_ts,
#             new_model_id=new_model.id,
#             new_version=new_model.version,
#         )

#         emit_current_model_updated(
#             model_id=new_model.id,
#             version=new_model.version,
#             at=agg_ts,
#         )

#         # PRUNE used deltas (files + rows)
#         if used_delta_ids:
#             used_rows: List[Delta] = list(session.exec(select(Delta).where(Delta.id.in_(used_delta_ids))))
#             for d in used_rows:
#                 d_path = getattr(d, "artifact_path", None) or getattr(d, "path", None)
#                 _safe_unlink(d_path)
#             for d in used_rows:
#                 session.delete(d)
#             session.commit()

#         return {
#             "ok": True,
#             "round_id": r.id,
#             "new_model_id": new_model.id,
#             "used_deltas": len(used_delta_ids),
#             "weights": {
#                 "hospital_total": float(sum(w_hosp)) if w_hosp else 0.0,
#                 "patient_total": float(sum(w_pat)) if w_pat else 0.0,
#             },
#             "artifact_path": out_path,
#             "checksum": chksum,
#         }

#     except Exception:
#         session.rollback()
#         raise
# app/services/aggregate.py
from __future__ import annotations

import os
import asyncio
from datetime import datetime, timezone
from typing import Dict, List, Tuple, Iterable

import torch
from sqlmodel import Session, select

from ..db.models import Model, Round, Delta, Setting
from ..core.storage import sha256_file
from ..core.events import publish as sse_publish
from ..services.rounds import get_or_open_current_round   # ⬅️ NEW: open next round after agg


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
      5) Close + mark round as aggregated, update Setting.current_model_id.
      6) Delete used deltas (files + rows).
      7) Emit SSE events for Dashboard (round_aggregated + current_model_updated).
      8) Immediately open a NEW round for the next cycle and emit 'round_opened'.
    """
    try:
        r = session.get(Round, round_id)
        if not r:
            raise ValueError(f"Round not found: {round_id}")

        deltas: List[Delta] = list(
            session.exec(select(Delta).where(Delta.round_id == round_id))
        )
        if not deltas and not force:
            return {"ok": False, "reason": "no_deltas", "round_id": round_id}

        st = session.get(Setting, 1)
        if not st or not st.current_model_id:
            raise ValueError("No current model set in settings")
        cur_model = session.get(Model, st.current_model_id)
        if not cur_model or not cur_model.artifact_path:
            raise ValueError("Current model artifact missing")

        # Load current global checkpoint
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
                hosp_bb.append(bb)
                w_hosp.append(n)
                if hd:
                    hosp_hd.append(hd)
            else:
                pat_bb.append(bb)
                w_pat.append(n)
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

        # Insert model row
        new_model = Model(
            version=f"agg-{stamp}",
            artifact_path=out_path,
            checksum=chksum,
            is_current=False,
        )
        session.add(new_model)
        session.commit()
        session.refresh(new_model)

        # Close / mark round as aggregated, update settings
        r.status = "aggregated"
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

        # Emit SSE events *after* commit so dashboard sees stable state
        agg_ts = (
            r.closed_at.isoformat()
            if r.closed_at
            else datetime.now(timezone.utc).isoformat()
        )

        payload_agg = {
            "type": "round_aggregated",
            "round_id": r.id,
            "aggregated_at": agg_ts,
            "new_model_id": new_model.id,
            "new_version": new_model.version,
        }
        payload_model = {
            "type": "current_model_updated",
            "model_id": new_model.id,
            "version": new_model.version,
            "at": agg_ts,
        }

        try:
            loop = asyncio.get_running_loop()
            loop.create_task(sse_publish(payload_agg))
            loop.create_task(sse_publish(payload_model))
        except RuntimeError:
            # not in async loop; aggregation still succeeded
            pass

        # PRUNE used deltas (files + rows)
        if used_delta_ids:
            used_rows: List[Delta] = list(
                session.exec(select(Delta).where(Delta.id.in_(used_delta_ids)))
            )
            for d in used_rows:
                d_path = getattr(d, "artifact_path", None) or getattr(d, "path", None)
                _safe_unlink(d_path)
            for d in used_rows:
                session.delete(d)
            session.commit()

        # 🔁 Immediately open NEXT round for new cycle, and emit round_opened SSE
        #    (get_or_open_current_round already does the SSE publish internally)
        next_round = get_or_open_current_round(session)

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
            "next_round_id": next_round.id,   # ⬅️ for debugging / logs
        }

    except Exception:
        session.rollback()
        raise
