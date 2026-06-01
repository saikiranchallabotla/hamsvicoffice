"""DWG -> DXF conversion via ODA File Converter (Open Design Alliance, free)."""
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
        return "ODAFileConverter.exe"
    return "/usr/bin/ODAFileConverter"


def dwg_to_dxf(dwg_path: str, out_dir: str | None = None, timeout: int = 180) -> str:
    """Convert a DWG file to DXF. Returns absolute path to the produced DXF.

    Requires the ODA File Converter binary to be installed on the system.
    https://www.opendesign.com/guestfiles/oda_file_converter
    """
    dwg_path = os.path.abspath(dwg_path)
    if not os.path.exists(dwg_path):
        raise ConversionError(f"Input DWG not found: {dwg_path}")

    src_dir = tempfile.mkdtemp(prefix="oda_in_")
    dst_dir = out_dir or tempfile.mkdtemp(prefix="oda_out_")
    os.makedirs(dst_dir, exist_ok=True)
    staged = os.path.join(src_dir, os.path.basename(dwg_path))
    shutil.copy2(dwg_path, staged)

    oda = _oda_path()
    # Args: <in_dir> <out_dir> <out_ver> <out_format> <recurse> <audit> [filter]
    # out_ver "ACAD2018" works for ezdxf 1.x. out_format "DXF". recurse 0, audit 1.
    cmd = [oda, src_dir, dst_dir, "ACAD2018", "DXF", "0", "1", "*.DWG"]

    try:
        result = subprocess.run(
            cmd,
            timeout=timeout,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError as e:
        raise ConversionError(
            f"ODA File Converter not found at {oda}. "
            "Install it from https://www.opendesign.com/guestfiles/oda_file_converter "
            "or set ODA_CONVERTER_PATH."
        ) from e
    except subprocess.TimeoutExpired as e:
        raise ConversionError(f"DWG conversion timed out after {timeout}s") from e

    base = os.path.splitext(os.path.basename(dwg_path))[0]
    produced = os.path.join(dst_dir, base + ".dxf")
    if not os.path.exists(produced):
        # Some ODA builds keep the original extension case
        for f in os.listdir(dst_dir):
            if f.lower().endswith(".dxf") and Path(f).stem.lower() == base.lower():
                produced = os.path.join(dst_dir, f)
                break
    if not os.path.exists(produced):
        raise ConversionError(
            f"ODA did not produce a DXF. stdout={result.stdout[:500]} stderr={result.stderr[:500]}"
        )

    shutil.rmtree(src_dir, ignore_errors=True)
    return produced
