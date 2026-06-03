"""Legend table detection in AutoCAD drawings.

Strategy (in order of preference):

1. **ACAD_TABLE entities** — modern AutoCAD legends are often real tables.
   When present we extract rows directly: each row maps a block reference
   to a description and (if present) a declared QTY.

2. **Cluster heuristic** — fall back to spatial pairing: for each distinct
   block name, find its compact cluster of insertions (where insertions are
   stacked vertically at roughly equal x), and pair each with the nearest
   TEXT/MTEXT entity. Text is searched in all four cardinal directions,
   preferring the same row (small dy) and the right side, then below, then
   left, then above.

3. **Group assignment** — real MEP drawings have several legend tables on
   one sheet (LEGEND, LEGEND:BLOCK-D fire-alarm, LEGEND:BLOCK-D pipes …).
   Every legend-row insert is assigned to the nearest LEGEND header text,
   so blocks belonging to the same logical table end up in the same group.

Returns:
    legend_map: { block_name: {
        "desc":          str,    # human-readable label
        "declared_qty":  int|None,
        "qty_detected":  int,    # raw count of all INSERTs anywhere
        "included":      True,
        "group":         str,    # name of the parent legend table
        "layers":        {layer_name: count, ...},   # populated by takeoff
    } }
    legend_bbox: (minx, miny, maxx, maxy) | None
        Combined bounding box of all legend-row insertions, used by the
        takeoff step to *exclude* the legend's own symbols from counts.
"""
from collections import defaultdict
import re
from typing import Dict, List, Optional, Tuple

# Same-row tolerance: text on the same horizontal band as the symbol.
SAME_ROW_DY = 250.0
# Search radius for text near a symbol (drawing units; tolerant).
TEXT_SEARCH_RADIUS = 12000.0
# Max insertions of a block that still counts as a legend cluster.
LEGEND_CLUSTER_MAX = 4
# An instance only counts toward the legend bbox if its paired label is
# this close (in score units). Placements out in the drawing rarely have
# labels this near, so they're correctly excluded.
LEGEND_LABEL_MAX_SCORE = 1500.0
# Padding around the detected legend bbox (so we exclude a generous margin).
BBOX_PADDING = 100.0

# Header text that introduces a legend table.
LEGEND_HEADER_RE = re.compile(r"\blegend\b", re.IGNORECASE)
# A legend block is attached to the closest header within this radius.
# Beyond this it falls into the "Default" group.
HEADER_ATTACH_MAX = 8000.0


def _text_of(e) -> str:
    try:
        if e.dxftype() == "TEXT":
            return (e.dxf.text or "").strip()
        if e.dxftype() == "MTEXT":
            return (e.plain_text() or "").strip()
        if e.dxftype() == "ATTRIB":
            return (e.dxf.text or "").strip()
    except Exception:
        pass
    return ""


def _ip(e) -> Optional[Tuple[float, float]]:
    try:
        ip = e.dxf.insert
        return float(ip[0]), float(ip[1])
    except Exception:
        return None


def _is_label(txt: str) -> bool:
    if not txt or len(txt) > 120:
        return False
    low = txt.lower().strip()
    junk_prefixes = ("zone", "scale", "drawn", "checked", "drawing no", "rev",
                     "date", "sheet", "title", "north", "key plan")
    if any(low.startswith(p) for p in junk_prefixes):
        return False
    if low in ("symbol", "detail", "qty", "description", "legend", "block", "no", "no.", "s.no"):
        return False
    return True


def _parse_int(s: str) -> Optional[int]:
    """Extract integer from a QTY cell ('06', '239', '—', '06 NOS' etc.)."""
    if not s:
        return None
    cleaned = "".join(c for c in s if c.isdigit())
    if not cleaned:
        return None
    try:
        return int(cleaned)
    except ValueError:
        return None


def _collect_inserts(layouts) -> Dict[str, List]:
    """All INSERTs by block name across the provided layouts."""
    by_name: Dict[str, List] = defaultdict(list)
    for layout in layouts:
        for ins in layout.query("INSERT"):
            try:
                name = ins.dxf.name
                if not name or name.startswith("*"):
                    continue
                by_name[name].append(ins)
            except Exception:
                continue
    return by_name


def _collect_texts(layouts) -> List[Tuple[float, float, str]]:
    out = []
    for layout in layouts:
        for t in layout.query("TEXT MTEXT"):
            txt = _text_of(t)
            if not _is_label(txt):
                continue
            ip = _ip(t)
            if ip is None:
                continue
            out.append((ip[0], ip[1], txt))
    return out


def _collect_headers(layouts) -> List[Tuple[float, float, str]]:
    """LEGEND header texts ('LEGEND', 'LEGEND:BLOCK-D', 'LEGEND BLOCK D')."""
    out = []
    for layout in layouts:
        for t in layout.query("TEXT MTEXT"):
            try:
                if t.dxftype() == "TEXT":
                    txt = (t.dxf.text or "").strip()
                else:
                    try:
                        txt = (t.plain_text() or "").strip()
                    except Exception:
                        txt = ""
            except Exception:
                continue
            if not txt or not LEGEND_HEADER_RE.search(txt):
                continue
            ip = _ip(t)
            if ip is None:
                continue
            out.append((ip[0], ip[1], txt.strip(":").strip()))
    return out


def _nearest_header(x: float, y: float,
                    headers: List[Tuple[float, float, str]]) -> str:
    """Return the name of the closest LEGEND header (within HEADER_ATTACH_MAX)
    or 'Default' when no header is plausibly nearby."""
    if not headers:
        return "Default"
    best_name = "Default"
    best_d2 = HEADER_ATTACH_MAX ** 2
    for hx, hy, hname in headers:
        dx = x - hx
        dy = y - hy
        d2 = dx * dx + dy * dy
        if d2 < best_d2:
            best_d2 = d2
            best_name = hname
    return best_name


def _best_text(ix: float, iy: float, texts: List[Tuple[float, float, str]]) -> str:
    return _best_text_scored(ix, iy, texts)[0]


def _best_text_scored(ix: float, iy: float, texts: List[Tuple[float, float, str]]) -> Tuple[str, float]:
    """Pair symbol at (ix, iy) with the most likely description text.

    Scoring: prefer same row (small |dy|), then right side over below/left/above.
    Returns (best_text, best_score). Closer wins; ties broken by direction penalty.
    """
    best_txt = ""
    best_score = float("inf")
    for tx, ty, txt in texts:
        dx = tx - ix
        dy = ty - iy
        dist = (dx * dx + dy * dy) ** 0.5
        if dist > TEXT_SEARCH_RADIUS:
            continue
        if abs(dy) <= SAME_ROW_DY and dx > 0:
            penalty = 0
        elif abs(dy) <= SAME_ROW_DY and dx < 0:
            penalty = 0.8 * abs(dx)
        elif dy < 0:
            penalty = 0.4 * abs(dy)
        else:
            penalty = 0.6 * abs(dy)
        score = dist + penalty
        if score < best_score:
            best_score = score
            best_txt = txt
    return best_txt, best_score


def _extract_acad_tables(layouts) -> Dict[str, dict]:
    """Try to extract symbol/description rows from ACAD_TABLE entities.

    Returns partial legend_map keyed by block_name. Each row's symbol cell
    must reference a known block via its BLOCK content. The table's own
    insertion point is used as the group anchor.
    """
    out: Dict[str, dict] = {}
    for layout in layouts:
        for tbl in layout.query("ACAD_TABLE"):
            try:
                n_rows = tbl.dxf.n_rows
                n_cols = tbl.dxf.n_cols
            except Exception:
                continue
            try:
                tx, ty = float(tbl.dxf.insert[0]), float(tbl.dxf.insert[1])
            except Exception:
                tx, ty = 0.0, 0.0
            try:
                rows = []
                for r in range(n_rows):
                    row = []
                    for c in range(n_cols):
                        try:
                            cell = tbl.get_cell(r, c)
                            row.append(cell)
                        except Exception:
                            row.append(None)
                    rows.append(row)
            except Exception:
                continue
            for r in range(n_rows):
                block_name = None
                desc_text = ""
                qty = None
                for c in range(n_cols):
                    cell = rows[r][c]
                    if cell is None:
                        continue
                    bn = getattr(cell, "block_name", None) or getattr(cell, "block_record_name", None)
                    if bn:
                        block_name = bn
                    text = getattr(cell, "text", "") or ""
                    if text:
                        if not desc_text and _is_label(text):
                            desc_text = text
                        q = _parse_int(text)
                        if q is not None and qty is None:
                            qty = q
                if block_name and (desc_text or qty is not None):
                    out[block_name] = {
                        "desc": desc_text or block_name,
                        "declared_qty": qty,
                        "anchor": (tx, ty),
                    }
    return out


def _legend_cluster(inserts: List) -> List:
    """Return the subset of `inserts` that look like the legend row for this block."""
    if len(inserts) <= LEGEND_CLUSTER_MAX:
        return list(inserts)
    sorted_by_y = sorted(inserts, key=lambda i: -(_ip(i) or (0, 0))[1])
    return sorted_by_y[:LEGEND_CLUSTER_MAX]


def extract_legend(doc) -> Tuple[Dict[str, dict], Optional[Tuple[float, float, float, float]]]:
    layouts = [doc.modelspace()]
    try:
        for layout_name in doc.layout_names_in_taborder():
            if layout_name == "Model":
                continue
            try:
                layouts.append(doc.layouts.get(layout_name))
            except Exception:
                continue
    except Exception:
        pass

    inserts_by_name = _collect_inserts(layouts)
    texts = _collect_texts(layouts)
    headers = _collect_headers(layouts)

    legend_map: Dict[str, dict] = {}

    # 1) ACAD_TABLE pass.
    table_hits = _extract_acad_tables(layouts)
    for name, info in table_hits.items():
        if name in inserts_by_name:
            ax, ay = info.get("anchor", (0.0, 0.0))
            legend_map[name] = {
                "desc": info["desc"],
                "declared_qty": info.get("declared_qty"),
                "qty_detected": len(inserts_by_name[name]),
                "included": True,
                "group": _nearest_header(ax, ay, headers),
                "layers": {},
            }

    # 2) Cluster heuristic for everything not yet in the legend.
    legend_xys: List[Tuple[float, float]] = []

    def _record_bbox(cluster):
        for ins in cluster:
            ip = _ip(ins)
            if ip is None:
                continue
            _, score = _best_text_scored(ip[0], ip[1], texts)
            if score <= LEGEND_LABEL_MAX_SCORE:
                legend_xys.append(ip)

    for name, inserts in inserts_by_name.items():
        if name in legend_map:
            _record_bbox(_legend_cluster(inserts))
            continue

        cluster = _legend_cluster(inserts)
        if not cluster:
            continue

        best_desc = ""
        best_score = float("inf")
        best_xy: Optional[Tuple[float, float]] = None
        for ins in cluster:
            ip = _ip(ins)
            if ip is None:
                continue
            cand, score = _best_text_scored(ip[0], ip[1], texts)
            if cand and score < best_score:
                best_desc = cand
                best_score = score
                best_xy = ip
        if not best_desc:
            continue
        _record_bbox(cluster)
        group = _nearest_header(best_xy[0], best_xy[1], headers) if best_xy else "Default"
        legend_map[name] = {
            "desc": best_desc,
            "declared_qty": None,
            "qty_detected": len(inserts),
            "included": True,
            "group": group,
            "layers": {},
        }

    bbox = None
    if legend_xys:
        xs = [p[0] for p in legend_xys]
        ys = [p[1] for p in legend_xys]
        bbox = (min(xs) - BBOX_PADDING, min(ys) - BBOX_PADDING,
                max(xs) + BBOX_PADDING, max(ys) + BBOX_PADDING)

    return legend_map, bbox

