"""Zone polygon detection + point-in-polygon assignment.

Strategy:
1. Find TEXT/MTEXT entities whose content matches `zone[-_\\s]?\\d+` or `zone[-_\\s]?[a-z]`.
2. Find candidate boundary polylines: closed LWPOLYLINE on a layer matching ZONE*
   or BOUNDARY*, OR any closed LWPOLYLINE that contains a zone label inside it.
3. Each polygon stores the inner label as its name.

Shapely-free fallback (ray casting) so the module works even if shapely isn't installed.
"""
import re
from dataclasses import dataclass, field
from typing import List, Tuple, Optional

ZONE_RE = re.compile(r"zone\s*[-_]?\s*([a-z0-9]+)", re.IGNORECASE)


Point = Tuple[float, float]


@dataclass
class Zone:
    name: str
    polygon: List[Point]  # list of (x, y)
    label_xy: Optional[Point] = None

    def to_meta(self) -> dict:
        return {"name": self.name, "polygon": [list(p) for p in self.polygon]}


def _point_in_poly(x: float, y: float, poly: List[Point]) -> bool:
    """Ray-casting point in polygon."""
    n = len(poly)
    inside = False
    if n < 3:
        return False
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


def detect_zones(msp) -> List[Zone]:
    """Detect zone polygons from an ezdxf modelspace."""
    labels: List[Tuple[str, Point]] = []
    for e in msp.query("TEXT MTEXT"):
        try:
            txt = (e.dxf.text if e.dxftype() == "TEXT" else e.text) or ""
        except Exception:
            continue
        m = ZONE_RE.search(str(txt))
        if not m:
            continue
        name = f"Zone-{m.group(1).upper()}"
        try:
            if e.dxftype() == "TEXT":
                ip = e.dxf.insert
            else:
                ip = e.dxf.insert
            labels.append((name, (float(ip[0]), float(ip[1]))))
        except Exception:
            continue

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
            # No enclosing polygon -> create a synthetic small box around label so
            # at least the zone is recorded; assignment will fall back to nearest-label.
            zones.append(Zone(name=label_name, polygon=[], label_xy=(lx, ly)))
    return zones


def locate_zone(x: float, y: float, zones: List[Zone]) -> str:
    """Return the name of the zone containing (x,y), or 'Unassigned'.

    Falls back to nearest zone label when no polygon contains the point.
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
    out = []
    for z in meta or []:
        poly = [tuple(p) for p in z.get("polygon", [])]
        out.append(Zone(name=z["name"], polygon=poly))
    return out
