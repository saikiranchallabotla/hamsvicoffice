"""Top-level DXF parser. Loads file via ezdxf, extracts legend + zones,
returns a dict ready to save into DwgTakeoff."""
from __future__ import annotations

from typing import Optional

try:
    import ezdxf  # type: ignore
except ImportError:  # pragma: no cover
    ezdxf = None  # parser will raise a friendly error on use

from .legend import extract_legend
from .zones import detect_zones


class DxfParseError(Exception):
    pass


def parse_dxf(dxf_path: str) -> dict:
    """Read a DXF and return {'legend_map': {...}, 'zone_meta': [...]}"""
    if ezdxf is None:
        raise DxfParseError(
            "ezdxf is not installed. Add 'ezdxf>=1.3' to requirements.txt."
        )
    try:
        doc = ezdxf.readfile(dxf_path)
    except IOError as e:
        raise DxfParseError(f"Cannot open DXF: {e}") from e
    except ezdxf.DXFStructureError as e:
        raise DxfParseError(f"Invalid/corrupt DXF: {e}") from e

    msp = doc.modelspace()
    legend = extract_legend(msp)
    zones = detect_zones(msp)
    return {
        "legend_map": legend,
        "zone_meta": [z.to_meta() for z in zones],
    }
