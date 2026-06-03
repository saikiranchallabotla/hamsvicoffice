"""DWG -> DXF conversion.

Two backends supported:
  1. LibreDWG `dwg2dxf` — preferred on Linux servers. Apt-installable
     (`apt install libredwg-tools`), CLI-only, no GUI deps.
  2. ODA File Converter — fallback for files LibreDWG can't read (typically
     AutoCAD R2024+). Requires the proprietary binary + Qt.

Selection: if `ODA_CONVERTER_PATH` is set explicitly, try ODA first; otherwise
prefer LibreDWG. If the chosen backend fails, fall back to the other.
"""
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from django.conf import settings


class ConversionError(Exception):
    pass


def _oda_path() -> str:
    explicit = getattr(settings, "ODA_CONVERTER_PATH", "") or os.getenv("ODA_CONVERTER_PATH", "")
    if explicit:
        return explicit
    if sys.platform.startswith("win"):
        for p in (
            r"C:\Program Files\ODA\ODAFileConverter\ODAFileConverter.exe",
            r"C:\Program Files (x86)\ODA\ODAFileConverter\ODAFileConverter.exe",
        ):
            if os.path.exists(p):
                return p
        return ""
    return ""


def _libredwg_path() -> str:
    explicit = getattr(settings, "LIBREDWG_PATH", "") or os.getenv("LIBREDWG_PATH", "")
    if explicit:
        return explicit
    found = shutil.which("dwg2dxf")
    return found or ""


def _convert_libredwg(dwg_path: str, dst_dir: str, timeout: int) -> str:
    """Run `dwg2dxf -y -o <out.dxf> <in.dwg>`. Returns absolute DXF path."""
    binary = _libredwg_path()
    if not binary:
        raise ConversionError("LibreDWG `dwg2dxf` not found on PATH.")
    base = os.path.splitext(os.path.basename(dwg_path))[0]
    out_path = os.path.join(dst_dir, base + ".dxf")
    cmd = [binary, "-y", "-o", out_path, dwg_path]
    try:
        result = subprocess.run(cmd, timeout=timeout, capture_output=True, text=True)
    except FileNotFoundError as e:
        raise ConversionError(f"LibreDWG not found: {e}") from e
    except subprocess.TimeoutExpired as e:
        raise ConversionError(f"LibreDWG conversion timed out after {timeout}s") from e
    if not os.path.exists(out_path) or os.path.getsize(out_path) == 0:
        raise ConversionError(
            f"LibreDWG produced no DXF. rc={result.returncode} "
            f"stderr={(result.stderr or '')[:500]}"
        )
    return out_path


def _convert_oda(dwg_path: str, dst_dir: str, timeout: int) -> str:
    """Run ODA File Converter. Returns absolute DXF path."""
    binary = _oda_path()
    if not binary:
        raise ConversionError("ODA File Converter path not configured.")
    src_dir = tempfile.mkdtemp(prefix="oda_in_")
    staged = os.path.join(src_dir, os.path.basename(dwg_path))
    shutil.copy2(dwg_path, staged)
    cmd = [binary, src_dir, dst_dir, "ACAD2018", "DXF", "0", "1", "*.DWG"]
    try:
        result = subprocess.run(cmd, timeout=timeout, capture_output=True, text=True)
    except FileNotFoundError as e:
        raise ConversionError(f"ODA binary not executable: {e}") from e
    except subprocess.TimeoutExpired as e:
        raise ConversionError(f"ODA conversion timed out after {timeout}s") from e
    finally:
        shutil.rmtree(src_dir, ignore_errors=True)
    base = os.path.splitext(os.path.basename(dwg_path))[0]
    produced = os.path.join(dst_dir, base + ".dxf")
    if not os.path.exists(produced):
        for f in os.listdir(dst_dir):
            if f.lower().endswith(".dxf") and Path(f).stem.lower() == base.lower():
                produced = os.path.join(dst_dir, f)
                break
    if not os.path.exists(produced):
        raise ConversionError(
            f"ODA did not produce a DXF. stdout={(result.stdout or '')[:500]} "
            f"stderr={(result.stderr or '')[:500]}"
        )
    return produced


def dwg_to_dxf(dwg_path: str, out_dir: str | None = None, timeout: int = 180) -> str:
    """Convert a DWG file to DXF and return the absolute DXF path.

    Tries LibreDWG first (or ODA if explicitly configured). On failure, falls
    back to the other backend so a single bad-version file doesn't kill the
    whole pipeline when both are installed.
    """
    dwg_path = os.path.abspath(dwg_path)
    if not os.path.exists(dwg_path):
        raise ConversionError(f"Input DWG not found: {dwg_path}")
    dst_dir = out_dir or tempfile.mkdtemp(prefix="dwg_out_")
    os.makedirs(dst_dir, exist_ok=True)

    oda_configured = bool(_oda_path())
    libredwg_available = bool(_libredwg_path())

    if not oda_configured and not libredwg_available:
        raise ConversionError(
            "No DWG converter available. Install LibreDWG (`apt install libredwg-tools`) "
            "or set ODA_CONVERTER_PATH to the ODA File Converter binary."
        )

    order = []
    if oda_configured:
        order.append(("ODA", _convert_oda))
        if libredwg_available:
            order.append(("LibreDWG", _convert_libredwg))
    else:
        order.append(("LibreDWG", _convert_libredwg))

    errors = []
    for name, fn in order:
        try:
            return fn(dwg_path, dst_dir, timeout)
        except ConversionError as e:
            errors.append(f"{name}: {e}")
    raise ConversionError("All converters failed. " + " | ".join(errors))
