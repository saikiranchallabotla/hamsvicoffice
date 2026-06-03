"""Zone detection + assignment.

Zones in MEP floor plans are usually labeled (`zone-1`, `zone-2`, …) but
NOT enclosed by an explicit boundary polyline — the architectural walls
imply the region. So our primary strategy is **nearest-label assignment**:
each block insert is attributed to the closest zone label.

If a closed polyline *does* enclose a zone label (rare but possible), we
prefer point-in-polygon and only fall back to nearest-label when nothing
contains the point.
"""
import re
from dataclasses import dataclass
from typing import List, Tuple, Optional

# Matches "zone-1", "zone 2", "ZONE_A", "Zone-12B" etc.
# Tolerates an MTEXT control prefix (e.g. "\fArial|b0|i0;zone-1").
ZONE_RE = re.compile(r"\bzone\s*[-_]?\s*([a-z0-9]+)", re.IGNORECASE)


Point = Tuple[float, float]


@dataclass
class Zone:
    name: str
    polygon: List[Point]
    label_xy: Optional[Point] = None

    def to_meta(self) -> dict:
        return {
            "name": self.name,
            "polygon": [list(p) for p in self.polygon],
            "label_xy": list(self.label_xy) if self.label_xy else None,
        }


def _point_in_poly(x: float, y: float, poly: List[Point]) -> bool:
    n = len(poly)
    if n < 3:
        return False
    inside = False
    j = n - 1
    for i in range(n):
        xi, yi = poly[i]
        xj, yj = poly[j]
        if ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / ((yj - yi) or 1e-12) + xi):
            inside = not inside
        j = i
    return inside


def _bbox(poly: List[Point]) -> Tuple[float, float, float, float]:
    xs = [p[0] for p in poly]
    ys = [p[1] for p in poly]
    return min(xs), min(ys), max(xs), max(ys)


def _bbox_area(poly: List[Point]) -> float:
    minx, miny, maxx, maxy = _bbox(poly)
    return max(0.0, (maxx - minx) * (maxy - miny))


def _text_content(e) -> str:
    try:
        if e.dxftype() == "TEXT":
            return (e.dxf.text or "").strip()
        if e.dxftype() == "MTEXT":
            # plain_text strips MTEXT formatting codes.
            try:
                return (e.plain_text() or "").strip()
            except Exception:
                return (e.text or "").strip()
    except Exception:
        pass
    return ""


def detect_zones(msp) -> List[Zone]:
    """Detect zone labels and (if any) their enclosing polygons."""
    labels: List[Tuple[str, Point]] = []
    for e in msp.query("TEXT MTEXT"):
        txt = _text_content(e)
        if not txt:
            continue
        m = ZONE_RE.search(txt)
        if not m:
            continue
        name = f"Zone-{m.group(1).upper()}"
        try:
            ip = e.dxf.insert
            labels.append((name, (float(ip[0]), float(ip[1]))))
        except Exception:
            continue

    # De-duplicate labels: same name -> keep the first (others are usually
    # leader text or the area annotation right next to it).
    seen = set()
    deduped: List[Tuple[str, Point]] = []
    for name, xy in labels:
        if name in seen:
            continue
        seen.add(name)
        deduped.append((name, xy))
    labels = deduped

    polys: List[List[Point]] = []
    for pl in msp.query("LWPOLYLINE"):
        try:
            if not bool(pl.closed):
                continue
            pts = [(float(x), float(y)) for x, y, *_ in pl.get_points("xy")]
            if len(pts) >= 3:
                polys.append(pts)
        except Exception:
            continue
    for pl in msp.query("POLYLINE"):
        try:
            if not pl.is_closed:
                continue
            pts = [(float(v.dxf.location[0]), float(v.dxf.location[1])) for v in pl.vertices]
            if len(pts) >= 3:
                polys.append(pts)
        except Exception:
            continue

    zones: List[Zone] = []
    used_polys = set()
    for label_name, (lx, ly) in labels:
        best_idx = None
        best_area = float("inf")
        for i, poly in enumerate(polys):
            if i in used_polys:
                continue
            if _point_in_poly(lx, ly, poly):
                a = _bbox_area(poly)
                if a < best_area:
                    best_area = a
                    best_idx = i
        if best_idx is not None:
            used_polys.add(best_idx)
            zones.append(Zone(name=label_name, polygon=polys[best_idx], label_xy=(lx, ly)))
        else:
            zones.append(Zone(name=label_name, polygon=[], label_xy=(lx, ly)))
    return zones


def locate_zone(x: float, y: float, zones: List[Zone]) -> str:
    """Return the name of the zone for (x, y).

    Order of preference:
      1. Any polygon that geometrically contains (x, y).
      2. Nearest zone label (Euclidean) — the primary path when no polygon
         exists, which is the common case for our floor plans.
      3. 'Unassigned' if no labels exist at all.
    """
    for z in zones:
        if z.polygon and _point_in_poly(x, y, z.polygon):
            return z.name
    best = None
    best_d2 = float("inf")
    for z in zones:
        if not z.label_xy:
            continue
        dx = x - z.label_xy[0]
        dy = y - z.label_xy[1]
        d2 = dx * dx + dy * dy
        if d2 < best_d2:
            best_d2 = d2
            best = z.name
    return best or "Unassigned"


def zones_from_meta(meta: list) -> List[Zone]:
    """Rehydrate Zone objects from JSON. Preserves label_xy so nearest-label
    assignment continues to work after a round-trip through the database."""
    out: List[Zone] = []
    for z in meta or []:
        poly = [tuple(p) for p in z.get("polygon", []) or []]
        label_xy = z.get("label_xy")
        if label_xy:
            label_xy = (float(label_xy[0]), float(label_xy[1]))
        out.append(Zone(name=z["name"], polygon=poly, label_xy=label_xy))
    return out

