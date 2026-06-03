"""Quantity takeoff: classify cached INSERT records by zone.

Consumes the pre-walked insert list produced by `parser.parse_dxf` so
re-runs (after the user tweaks mapping, layers, or zones) don't need
to re-open the DXF.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Dict, Iterable, List, Optional, Tuple

from .zones import zones_from_meta, locate_zone


def _in_bbox(x: float, y: float, bbox: Optional[Iterable[float]]) -> bool:
    if not bbox:
        return False
    try:
        minx, miny, maxx, maxy = bbox
    except Exception:
        return False
    return minx <= x <= maxx and miny <= y <= maxy


def _in_any_window(x: float, y: float, windows: List[dict]) -> bool:
    for w in windows or []:
        if w["minx"] <= x <= w["maxx"] and w["miny"] <= y <= w["maxy"]:
            return True
    return False


def run_takeoff(
    inserts: List[dict],
    legend_map: dict,
    zone_meta: list,
    legend_bbox: Optional[Iterable[float]] = None,
    layer_filter: Optional[Dict[str, List[str]]] = None,
    include_paper_space: bool = False,
) -> Dict[str, Dict[str, int]]:
    """Single-pivot takeoff. Returns desc -> zone -> count, collapsing group.

    For multi-legend output use `run_takeoff_per_layout` directly.
    """
    out = run_takeoff_per_layout(
        inserts, legend_map, zone_meta,
        legend_bbox=legend_bbox,
        layer_filter=layer_filter,
        include_paper_space=include_paper_space,
        viewports=None,
    )
    flat: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for key, zd in out.get("All", {}).items():
        _, desc = split_key(key)
        for z, n in zd.items():
            flat[desc][z] += int(n)
    return {d: dict(zd) for d, zd in flat.items()}


def run_takeoff_per_layout(
    inserts: List[dict],
    legend_map: dict,
    zone_meta: list,
    legend_bbox: Optional[Iterable[float]] = None,
    layer_filter: Optional[Dict[str, List[str]]] = None,
    include_paper_space: bool = False,
    viewports: Optional[Dict[str, List[dict]]] = None,
) -> Dict[str, Dict[str, Dict[str, int]]]:
    """Return {sheet_name: {"<group>||<desc>": {zone_name: count}}}.

    Compound keys carry the legend group so descriptions that collide across
    legend tables (e.g. FLOW SWITCH in both fire-alarm and fire-fighting)
    stay separate. The excel writer splits them back into group + desc.

    When `viewports` is provided each layout gets its own sheet (inserts in
    no viewport land in 'Unassigned (no layout)'). Otherwise everything
    rolls up under 'All'.
    """
    zones = zones_from_meta(zone_meta)
    per_sheet: Dict[str, Dict[str, Dict[str, int]]] = defaultdict(
        lambda: defaultdict(lambda: defaultdict(int))
    )

    use_viewports = bool(viewports)

    for rec in inserts or []:
        name = rec.get("block")
        if not name:
            continue
        info = legend_map.get(name)
        if not info or not info.get("included", True):
            continue

        layout = rec.get("layout") or "Model"
        x = rec.get("x")
        y = rec.get("y")
        if x is None or y is None:
            continue
        if _in_bbox(x, y, legend_bbox) and layout == "Model":
            continue

        if layer_filter:
            allowed = layer_filter.get(name)
            if allowed is not None and rec.get("layer") not in allowed:
                continue

        desc = (info.get("desc") or name).strip() or name
        group = (info.get("group") or "Default").strip() or "Default"
        key = f"{group}||{desc}"
        z = locate_zone(float(x), float(y), zones)

        if not use_viewports:
            if not include_paper_space and layout != "Model":
                continue
            per_sheet["All"][key][z] += 1
            continue

        if layout == "Model":
            assigned = False
            for layout_name, windows in viewports.items():
                if _in_any_window(float(x), float(y), windows):
                    per_sheet[layout_name][key][z] += 1
                    assigned = True
            if not assigned:
                per_sheet["Unassigned (no layout)"][key][z] += 1
        else:
            if include_paper_space:
                per_sheet[layout][key][z] += 1

    return {
        sheet: {k: dict(zd) for k, zd in pivot.items()}
        for sheet, pivot in per_sheet.items()
    }


def split_key(k: str) -> Tuple[str, str]:
    """Inverse of the f'{group}||{desc}' encoding used above."""
    if "||" in k:
        g, d = k.split("||", 1)
        return g, d
    return "Default", k


def zone_names(zone_meta: list) -> list:
    names = [z["name"] for z in (zone_meta or [])]
    seen = set()
    out = []
    for n in names:
        if n not in seen:
            seen.add(n)
            out.append(n)
    return out
