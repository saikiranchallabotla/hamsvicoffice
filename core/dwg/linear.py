"""Linear (pipe / cable / duct) takeoff.

MEP drawings represent pipes as LINE / LWPOLYLINE / POLYLINE entities on
diameter-coded layers (e.g. one layer per pipe size, often distinguished
by color). We can't always reverse-engineer the layer-to-diameter map
automatically, so the parser collects per-segment records and the user
maps each layer to a diameter description in the review UI.

Records carry midpoint coords so each segment can be attributed to a
zone using the same nearest-label logic as the symbol takeoff.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Dict, Iterable, List, Optional


def _line_length(p1, p2) -> float:
    dx = float(p2[0]) - float(p1[0])
    dy = float(p2[1]) - float(p1[1])
    return (dx * dx + dy * dy) ** 0.5


def _line_midpoint(p1, p2):
    return ((float(p1[0]) + float(p2[0])) / 2.0,
            (float(p1[1]) + float(p2[1])) / 2.0)


def collect_linear(layout, owner_name: str = "Model") -> List[dict]:
    """Return [{layer, length, mx, my, layout}, ...] for one ezdxf layout.

    A polyline contributes ONE record (its full length, midpoint of bounding
    bbox of all segments). LINE contributes one record. Zero-length entities
    are skipped.
    """
    out: List[dict] = []

    for ln in layout.query("LINE"):
        try:
            start = ln.dxf.start
            end = ln.dxf.end
            length = _line_length(start, end)
            if length <= 0:
                continue
            mx, my = _line_midpoint(start, end)
            out.append({
                "layer": (ln.dxf.layer or "0").strip(),
                "length": length,
                "mx": float(mx),
                "my": float(my),
                "layout": owner_name,
            })
        except Exception:
            continue

    for pl in layout.query("LWPOLYLINE"):
        try:
            pts = [(float(x), float(y)) for x, y, *_ in pl.get_points("xy")]
            if len(pts) < 2:
                continue
            if bool(pl.closed):
                pts.append(pts[0])
            total = 0.0
            for i in range(len(pts) - 1):
                total += _line_length(pts[i], pts[i + 1])
            if total <= 0:
                continue
            xs = [p[0] for p in pts]
            ys = [p[1] for p in pts]
            mx = (min(xs) + max(xs)) / 2.0
            my = (min(ys) + max(ys)) / 2.0
            out.append({
                "layer": (pl.dxf.layer or "0").strip(),
                "length": total,
                "mx": mx,
                "my": my,
                "layout": owner_name,
            })
        except Exception:
            continue

    for pl in layout.query("POLYLINE"):
        try:
            pts = []
            for v in pl.vertices:
                try:
                    pts.append((float(v.dxf.location[0]), float(v.dxf.location[1])))
                except Exception:
                    pass
            if len(pts) < 2:
                continue
            if getattr(pl, "is_closed", False):
                pts.append(pts[0])
            total = 0.0
            for i in range(len(pts) - 1):
                total += _line_length(pts[i], pts[i + 1])
            if total <= 0:
                continue
            xs = [p[0] for p in pts]
            ys = [p[1] for p in pts]
            mx = (min(xs) + max(xs)) / 2.0
            my = (min(ys) + max(ys)) / 2.0
            out.append({
                "layer": (pl.dxf.layer or "0").strip(),
                "length": total,
                "mx": mx,
                "my": my,
                "layout": owner_name,
            })
        except Exception:
            continue

    return out


def length_by_layer(records: List[dict]) -> Dict[str, float]:
    """Sum length per layer across the supplied records."""
    out: Dict[str, float] = defaultdict(float)
    for r in records or []:
        out[r["layer"]] += float(r.get("length") or 0.0)
    return dict(out)


def _in_bbox(x: float, y: float, bbox) -> bool:
    if not bbox:
        return False
    try:
        minx, miny, maxx, maxy = bbox
    except Exception:
        return False
    return minx <= x <= maxx and miny <= y <= maxy


def _in_any_window(x: float, y: float, windows) -> bool:
    for w in windows or []:
        if w["minx"] <= x <= w["maxx"] and w["miny"] <= y <= w["maxy"]:
            return True
    return False


def run_linear_takeoff_per_layout(
    records: List[dict],
    layer_mapping: Dict[str, str],
    zone_meta: list,
    legend_bbox=None,
    unit_scale: float = 1.0,
    viewports: Optional[Dict[str, list]] = None,
) -> Dict[str, Dict[str, Dict[str, float]]]:
    """Return {sheet: {"Pipes||<desc>": {zone: total_length_in_user_units}}}.

    layer_mapping maps layer_name -> human description ('25mm Pipe'). Layers
    not in the map are ignored — that's the user's signal of "not a pipe".
    unit_scale converts drawing units to the user's reporting unit (e.g.
    0.001 for mm -> m).
    """
    from .zones import zones_from_meta, locate_zone

    zones = zones_from_meta(zone_meta)
    per_sheet: Dict[str, Dict[str, Dict[str, float]]] = defaultdict(
        lambda: defaultdict(lambda: defaultdict(float))
    )
    use_viewports = bool(viewports)

    for rec in records or []:
        layer = rec.get("layer")
        desc = layer_mapping.get(layer)
        if not desc:
            continue
        length = float(rec.get("length") or 0.0) * float(unit_scale or 1.0)
        if length <= 0:
            continue
        layout = rec.get("layout") or "Model"
        mx = rec.get("mx")
        my = rec.get("my")
        if mx is None or my is None:
            continue
        if _in_bbox(mx, my, legend_bbox) and layout == "Model":
            continue
        z = locate_zone(float(mx), float(my), zones)
        key = f"Pipes||{desc}"
        if not use_viewports:
            if layout != "Model":
                continue
            per_sheet["All"][key][z] += length
            continue
        if layout == "Model":
            assigned = False
            for layout_name, windows in viewports.items():
                if _in_any_window(float(mx), float(my), windows):
                    per_sheet[layout_name][key][z] += length
                    assigned = True
            if not assigned:
                per_sheet["Unassigned (no layout)"][key][z] += length

    return {
        sheet: {k: dict(zd) for k, zd in pivot.items()}
        for sheet, pivot in per_sheet.items()
    }
