"""Top-level DXF reader. Walks model + paper space, extracts the full INSERT
list (with layer + xy + nesting info), and detects legend rows + zones.

The full insert list is cached in the DwgTakeoff row so subsequent re-runs
(after the user tweaks the mapping) don't need to re-open the DXF.
"""
from __future__ import annotations

from typing import Dict, List, Optional

try:
    import ezdxf  # type: ignore
    from ezdxf.math import Matrix44  # type: ignore
except ImportError:  # pragma: no cover
    ezdxf = None
    Matrix44 = None

from .legend import extract_legend
from .linear import collect_linear, length_by_layer
from .zones import detect_zones


class DxfParseError(Exception):
    pass


def _walk_inserts(layout, owner_name: str = "MODEL") -> List[dict]:
    """Yield every block insertion in `layout`, recursing into nested blocks.

    Each record: {block, x, y, layer, layout, nested}
    - `block` is the block reference name (skips anonymous *U-style names)
    - `nested=True` when the INSERT is inside another block (via virtual_entities)
    """
    rows: List[dict] = []
    for ins in layout.query("INSERT"):
        try:
            name = ins.dxf.name
            ip = ins.dxf.insert
            layer = (ins.dxf.layer or "0").strip()
        except Exception:
            continue
        if name and not name.startswith("*"):
            rows.append({
                "block": name,
                "x": float(ip[0]),
                "y": float(ip[1]),
                "layer": layer,
                "layout": owner_name,
                "nested": False,
            })
        # Recurse: expand the block's virtual entities to surface nested INSERTs.
        try:
            for v in ins.virtual_entities():
                if v.dxftype() != "INSERT":
                    continue
                vname = v.dxf.name
                if not vname or vname.startswith("*"):
                    continue
                try:
                    vp = v.dxf.insert
                    vlayer = (v.dxf.layer or layer).strip()
                except Exception:
                    continue
                rows.append({
                    "block": vname,
                    "x": float(vp[0]),
                    "y": float(vp[1]),
                    "layer": vlayer,
                    "layout": owner_name,
                    "nested": True,
                })
        except Exception:
            continue
    return rows


def _collect_viewports(doc) -> Dict[str, List[dict]]:
    """For each paper-space layout, return its viewport windows in model coords.

    AutoCAD MEP plans typically draw everything in model space and use paper
    layouts to publish per-floor views. Each VIEWPORT entity exposes:
      - view_center_point (model coord at viewport center)
      - view_height       (model-space height shown in the viewport)
      - width / height    (viewport size on the paper layout)
    We derive the model-space rectangle so the takeoff can attribute model
    inserts to the floor (layout) that displays them.

    Returns: { layout_name: [ {minx, miny, maxx, maxy}, ... ] }
    Layout #1 in each paper space is the layout's own paper viewport — we
    skip it (id == 1) so only real "windowed" viewports are returned.
    """
    out: Dict[str, List[dict]] = {}
    try:
        for layout_name in doc.layout_names_in_taborder():
            if layout_name == "Model":
                continue
            try:
                lyt = doc.layouts.get(layout_name)
            except Exception:
                continue
            windows: List[dict] = []
            try:
                for vp in lyt.query("VIEWPORT"):
                    try:
                        # vp.dxf.id == 1 is the paper-space "main" viewport (the
                        # layout boundary itself), not a windowed view.
                        if int(getattr(vp.dxf, "id", 0)) == 1:
                            continue
                        cx, cy = float(vp.dxf.view_center_point[0]), float(vp.dxf.view_center_point[1])
                        vh = float(vp.dxf.view_height)
                        # paper-space size of the viewport rectangle
                        pw = float(vp.dxf.width)
                        ph = float(vp.dxf.height) or 1.0
                        aspect = pw / ph if ph else 1.0
                        vw = vh * aspect
                        windows.append({
                            "minx": cx - vw / 2.0,
                            "miny": cy - vh / 2.0,
                            "maxx": cx + vw / 2.0,
                            "maxy": cy + vh / 2.0,
                        })
                    except Exception:
                        continue
            except Exception:
                pass
            if windows:
                out[layout_name] = windows
    except Exception:
        pass
    return out


def parse_dxf(dxf_path: str) -> dict:
    """Return everything we can extract from a DXF in one pass.

    {
      'legend_map':   {block_name: {desc, declared_qty, qty_detected, included, layers}},
      'legend_bbox':  (minx, miny, maxx, maxy) | None,
      'zone_meta':    [{name, polygon}, ...],
      'inserts':      [{block, x, y, layer, layout, nested}, ...],  # cached for re-runs
      'layouts':      ['Model', 'Layout1', ...],
      'warnings':     [str, ...],
    }
    """
    if ezdxf is None:
        raise DxfParseError("ezdxf not installed (add 'ezdxf>=1.3.0' to requirements).")

    warnings: List[str] = []

    try:
        doc = ezdxf.readfile(dxf_path)
    except IOError as e:
        raise DxfParseError(f"Cannot open DXF: {e}") from e
    except ezdxf.DXFStructureError as e:
        # Try the recover module for partially corrupt files.
        try:
            from ezdxf import recover  # type: ignore
            doc, audit = recover.readfile(dxf_path)
            if audit.errors:
                warnings.append(f"DXF had {len(audit.errors)} structural errors; auto-recovered.")
        except Exception:
            raise DxfParseError(f"Invalid/corrupt DXF: {e}") from e

    msp = doc.modelspace()

    # Walk all layouts (model + paper).
    inserts: List[dict] = []
    linear_records: List[dict] = []
    layout_names: List[str] = ["Model"]
    inserts.extend(_walk_inserts(msp, owner_name="Model"))
    try:
        linear_records.extend(collect_linear(msp, owner_name="Model"))
    except Exception as e:
        warnings.append(f"Linear scan (Model) failed: {e}")
    try:
        for layout_name in doc.layout_names_in_taborder():
            if layout_name == "Model":
                continue
            try:
                lyt = doc.layouts.get(layout_name)
            except Exception:
                continue
            layout_names.append(layout_name)
            try:
                inserts.extend(_walk_inserts(lyt, owner_name=layout_name))
            except Exception as e:
                warnings.append(f"Could not scan layout {layout_name!r}: {e}")
            try:
                linear_records.extend(collect_linear(lyt, owner_name=layout_name))
            except Exception as e:
                warnings.append(f"Linear scan ({layout_name!r}) failed: {e}")
    except Exception:
        pass

    # Legend (uses doc, scans all layouts internally).
    try:
        legend_map, legend_bbox = extract_legend(doc)
    except Exception as e:
        legend_map, legend_bbox = {}, None
        warnings.append(f"Legend detection failed: {e}")

    # Zones (model space only — they describe physical floor regions).
    try:
        zones = detect_zones(msp)
        zone_meta = [z.to_meta() for z in zones]
    except Exception as e:
        zone_meta = []
        warnings.append(f"Zone detection failed: {e}")

    # Backfill per-block layer counts on the legend map.
    from collections import defaultdict
    layer_counts: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for r in inserts:
        layer_counts[r["block"]][r["layer"]] += 1
    for block, info in legend_map.items():
        info["layers"] = dict(layer_counts.get(block, {}))

    return {
        "legend_map": legend_map,
        "legend_bbox": list(legend_bbox) if legend_bbox else None,
        "zone_meta": zone_meta,
        "inserts": inserts,
        "linear_records": linear_records,
        "linear_by_layer": length_by_layer(linear_records),
        "layouts": layout_names,
        "viewports": _collect_viewports(doc),
        "warnings": warnings,
    }
