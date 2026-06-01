"""Quantity takeoff: walk all INSERTs in modelspace, classify by zone,
return pivot {description: {zone_name: count}}."""
from __future__ import annotations

from collections import defaultdict
from typing import Dict

try:
    import ezdxf  # type: ignore
except ImportError:
    ezdxf = None

from .zones import zones_from_meta, locate_zone


def run_takeoff(dxf_path: str, legend_map: dict, zone_meta: list) -> Dict[str, Dict[str, int]]:
    """Return nested dict: desc -> zone_name -> count."""
    if ezdxf is None:
        raise RuntimeError("ezdxf not installed")
    doc = ezdxf.readfile(dxf_path)
    msp = doc.modelspace()
    zones = zones_from_meta(zone_meta)

    summary: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for ins in msp.query("INSERT"):
        try:
            name = ins.dxf.name
        except Exception:
            continue
        info = legend_map.get(name)
        if not info or not info.get("included", True):
            continue
        desc = (info.get("desc") or name).strip() or name
        try:
            ip = ins.dxf.insert
            x, y = float(ip[0]), float(ip[1])
        except Exception:
            continue
        z = locate_zone(x, y, zones)
        summary[desc][z] += 1
    # cast nested defaultdicts to plain dicts for JSON serialization
    return {desc: dict(zd) for desc, zd in summary.items()}


def zone_names(zone_meta: list) -> list:
    names = [z["name"] for z in (zone_meta or [])]
    seen = set()
    out = []
    for n in names:
        if n not in seen:
            seen.add(n)
            out.append(n)
    return out
