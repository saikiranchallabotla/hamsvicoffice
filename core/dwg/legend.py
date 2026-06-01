"""Detect legend tables in an ezdxf modelspace and pair block-refs with their
human-readable description text.

Heuristic — legends typically look like a column of INSERTs with TEXT/MTEXT to
the right. We:

1. Build a list of INSERTs (excluding zone polylines).
2. For each unique block_name, find the smallest cluster of insertions that sit
   side-by-side with TEXT/MTEXT (the legend uses each block once). The total
   set of insertions for that block in the drawing is the takeoff count.
3. Pair each legend INSERT with the nearest TEXT/MTEXT within a small
   horizontal band to the right.

Returns: { block_name: {"desc": str, "qty_detected": int, "included": True} }
"""
from collections import defaultdict
from typing import Dict, List, Tuple

LEGEND_TEXT_MAX_DX = 8000.0  # drawing units; tolerant
LEGEND_TEXT_MAX_DY = 200.0   # vertical tolerance for "same row"


def _text_of(e) -> str:
    try:
        if e.dxftype() == "TEXT":
            return (e.dxf.text or "").strip()
        if e.dxftype() == "MTEXT":
            return (e.plain_text() or e.text or "").strip()
    except Exception:
        pass
    return ""


def _insertion_xy(e) -> Tuple[float, float]:
    ip = e.dxf.insert
    return float(ip[0]), float(ip[1])


def _is_drawing_label(txt: str) -> bool:
    if not txt:
        return False
    low = txt.lower().strip()
    if low.startswith("zone"):
        return False
    if low.startswith("legend") or low.startswith("symbol") or low == "detail" or low == "qty":
        return False
    return True


def extract_legend(msp) -> Dict[str, dict]:
    inserts_by_name: Dict[str, List] = defaultdict(list)
    for ins in msp.query("INSERT"):
        try:
            name = ins.dxf.name
            if name.startswith("*"):
                continue  # anonymous / dynamic block ref
            inserts_by_name[name].append(ins)
        except Exception:
            continue

    # collect all text entities once
    texts = []
    for t in msp.query("TEXT MTEXT"):
        txt = _text_of(t)
        if not _is_drawing_label(txt):
            continue
        try:
            ip = t.dxf.insert
            texts.append((float(ip[0]), float(ip[1]), txt))
        except Exception:
            continue

    legend: Dict[str, dict] = {}
    for name, inserts in inserts_by_name.items():
        if not inserts:
            continue
        # candidate legend instance: the one with a text label very close to its right
        best_desc = ""
        best_d = float("inf")
        for ins in inserts:
            ix, iy = _insertion_xy(ins)
            for tx, ty, txt in texts:
                dy = abs(ty - iy)
                dx = tx - ix
                if dy <= LEGEND_TEXT_MAX_DY and 0 < dx <= LEGEND_TEXT_MAX_DX:
                    d = dx + dy * 5
                    if d < best_d:
                        best_d = d
                        best_desc = txt
        if not best_desc:
            continue  # no description -> probably not a legend symbol
        legend[name] = {
            "desc": best_desc,
            "qty_detected": len(inserts),
            "included": True,
        }
    return legend
