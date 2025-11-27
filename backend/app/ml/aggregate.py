from typing import Dict, List
import torch

def _avg_float_or_first(dicts: List[Dict[str, torch.Tensor]], fallback: Dict[str, torch.Tensor]):
    if not dicts: return fallback
    keys = dicts[0].keys()
    out = {}
    for k in keys:
        ts = [d[k] for d in dicts]
        out[k] = torch.stack(ts, 0).mean(0) if ts[0].is_floating_point() else ts[0]
    return out

def split_bb_hd(sd: Dict[str, torch.Tensor]):
    bb, hd = {}, {}
    for k, v in sd.items():
        if "classifier" in k or ".fc." in k or ".head." in k: hd[k] = v
        else: bb[k] = v
    return bb, hd

def merge_bb_hd(base: Dict[str, torch.Tensor], bb: Dict[str, torch.Tensor], hd: Dict[str, torch.Tensor]):
    out = {**base}
    out.update(bb); out.update(hd)
    return out

def typed_fedavg(global_sd, hospital_deltas: List[Dict], patient_deltas: List[Dict]):
    cur_bb, cur_hd = split_bb_hd(global_sd)
    bb_updates = []
    hd_updates = []
    for d in hospital_deltas:
        bb, hd = split_bb_hd(d)
        bb_updates.append(bb); hd_updates.append(hd)
    for d in patient_deltas:
        bb, _ = split_bb_hd(d)
        bb_updates.append(bb)
    new_bb = _avg_float_or_first(bb_updates, cur_bb)
    new_hd = _avg_float_or_first(hd_updates, cur_hd)
    return merge_bb_hd(global_sd, new_bb, new_hd)
