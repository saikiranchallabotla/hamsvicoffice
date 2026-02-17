import os
from copy import copy

from openpyxl import load_workbook
from openpyxl.formula.translate import Translator
from django.db.utils import OperationalError, ProgrammingError

from .models import BackendWorkbook


def normalize_text(text):
    """
    Normalize text by replacing special unicode characters with standard ASCII equivalents.
    Fixes encoding issues like em-dash (—) appearing as â€" in output.
    """
    if text is None:
        return None
    if not isinstance(text, str):
        return text
    # Replace various unicode dashes with standard hyphen
    text = text.replace('—', '-')  # em dash
    text = text.replace('–', '-')  # en dash
    text = text.replace('−', '-')  # minus sign
    text = text.replace('‐', '-')  # hyphen
    text = text.replace('‑', '-')  # non-breaking hyphen
    text = text.replace('‒', '-')  # figure dash
    # Replace other common problematic characters
    text = text.replace(''', "'")  # left single quote
    text = text.replace(''', "'")  # right single quote
    text = text.replace('"', '"')  # left double quote
    text = text.replace('"', '"')  # right double quote
    text = text.replace('…', '...')  # ellipsis
    text = text.replace('\u00a0', ' ')  # non-breaking space
    return text


# scan columns A..J
SCAN_COL_START = 1
SCAN_COL_END = 10


# ---------- Color detection helpers ----------
def cell_is_yellow(cell):
    fill = cell.fill
    if not fill or not fill.patternType or fill.patternType.lower() != "solid":
        return False

    rgb = getattr(fill.fgColor, "rgb", None)
    if rgb and str(rgb).upper().endswith("FFFF00"):
        return True

    if getattr(fill.fgColor, "type", None) == "theme":
        if getattr(fill.fgColor, "theme", None) in (4, 5, 6):
            return True

    if getattr(fill.fgColor, "indexed", None) == 6:
        return True

    return False


def cell_is_red_text(cell):
    font = cell.font
    if not font or not font.color:
        return False

    rgb = getattr(font.color, "rgb", None)
    if rgb and str(rgb).upper().endswith("FF0000"):
        return True

    if getattr(font.color, "type", None) == "theme":
        return True

    if getattr(font.color, "indexed", None) == 3:
        return True

    return False


def _is_yellow_and_red(cell):
    return cell_is_yellow(cell) and cell_is_red_text(cell)


# ---------- Detect items from "Master Datas" ----------
def detect_items(ws):
    """
    Detect item blocks:
    - A heading row is a row where ANY cell in A..J is yellow+red.
    - The block continues until the row before the next heading.
    """
    items = []
    max_row = ws.max_row
    r = 1

    while r <= max_row:
        heading_name = None
        for c in range(SCAN_COL_START, SCAN_COL_END + 1):
            cell = ws.cell(row=r, column=c)
            if _is_yellow_and_red(cell) and str(cell.value or "").strip():
                heading_name = str(cell.value).strip()
                break

        if heading_name:
            start_row = r

            # Find next heading
            end_row = max_row
            rr = r + 1
            while rr <= max_row:
                found_next = False
                for c in range(SCAN_COL_START, SCAN_COL_END + 1):
                    cell = ws.cell(row=rr, column=c)
                    if _is_yellow_and_red(cell) and str(cell.value or "").strip():
                        found_next = True
                        break
                if found_next:
                    end_row = rr - 1
                    break
                rr += 1

            items.append({
                "name": heading_name,
                "start_row": start_row,
                "end_row": end_row
            })

            r = end_row + 1
        else:
            r += 1

    return items


# ---------- Read groups from "Groups" ----------
def read_groups(ws_groups):
    """
    Column A = Item Name, Column B = Group, Column C = Prefix, Column D = Unit (optional)
    Return tuple: (groups_dict, units_dict)
      - groups_dict: { group_name: [item1, item2, ...] }
      - units_dict: { item_name: unit }
    """
    groups = {}
    units = {}
    max_row = ws_groups.max_row
    for r in range(2, max_row + 1):
        item = ws_groups.cell(row=r, column=1).value
        group = ws_groups.cell(row=r, column=2).value
        unit = ws_groups.cell(row=r, column=4).value  # Column D for unit
        if item and group:
            item = str(item).strip()
            group = str(group).strip()
            groups.setdefault(group, []).append(item)
            # Store unit if provided
            if unit:
                units[item] = str(unit).strip()
    return groups, units


# ---------- Load workbook and sheets ----------
def load_backend(category, base_dir, backend_id=None, module_code=None, user=None):
    """
    Load backend Excel data.
    
    Returns: (items_list, groups_map, units_map, ws_data, filepath)

    Resolution priority:
    1. ModuleBackend by ID (if backend_id provided)
    2. User's preferred backend (if user provided)
    3. ModuleBackend default for module+category (if module_code provided)
    4. BackendWorkbook (legacy)
    5. Static file_map (core/data/*.xlsx)
    
    Args:
        category: Work type like 'electrical', 'civil', 'temp_electrical', etc.
        base_dir: Django BASE_DIR
        backend_id: Specific ModuleBackend ID to use (optional)
        module_code: Module code like 'estimate', 'workslip' (optional)
        user: User object (optional, for user preferences)
    """
    category_key = str(category).lower().strip()
    filepath = None
    
    # Map category to base category (remove temp_, amc_ prefixes for matching)
    base_category = category_key
    if category_key.startswith('temp_'):
        base_category = category_key.replace('temp_', '')
    elif category_key.startswith('amc_'):
        base_category = category_key.replace('amc_', '')
    
    # Helper to resolve backend file path (with DB fallback)
    def _resolve_backend_path(backend_obj):
        """Try disk path first, then restore from DB if needed."""
        if not backend_obj or not backend_obj.file:
            return None
        try:
            fpath = backend_obj.file.path
            if os.path.exists(fpath):
                return fpath
        except Exception:
            pass
        # Try restoring from DB via get_file_bytes()
        if hasattr(backend_obj, 'get_file_bytes'):
            try:
                data = backend_obj.get_file_bytes()
                if data and backend_obj.file:
                    return backend_obj.file.path
            except Exception:
                pass
        return None

    # 1. Try ModuleBackend by specific ID
    if backend_id:
        try:
            from subscriptions.models import ModuleBackend
            backend = ModuleBackend.objects.filter(pk=backend_id, is_active=True).first()
            filepath = _resolve_backend_path(backend)
        except (OperationalError, ProgrammingError, Exception):
            pass

    # 2. Try user's preferred backend
    if not filepath and user and user.is_authenticated and module_code:
        try:
            from accounts.models import UserBackendPreference
            backend = UserBackendPreference.get_user_backend(user, module_code, base_category)
            filepath = _resolve_backend_path(backend)
        except (OperationalError, ProgrammingError, Exception):
            pass

    # 3. Try ModuleBackend default for module + category
    module_backend_checked = False
    if not filepath and module_code:
        try:
            from subscriptions.models import ModuleBackend
            module_backend_checked = True
            backend = ModuleBackend.get_for_module(module_code, base_category)
            filepath = _resolve_backend_path(backend)
        except (OperationalError, ProgrammingError, Exception):
            pass
    
    # 4. Try BackendWorkbook (legacy) - only if module_code was NOT provided
    # When module_code is provided, we rely on ModuleBackend system only
    if not filepath and not module_code:
        try:
            backend = BackendWorkbook.objects.filter(
                category=category_key,
                is_active=True
            ).order_by('-is_default', '-uploaded_at').first()
            if backend and backend.file:
                filepath = backend.file.path
        except (OperationalError, ProgrammingError, Exception):
            pass
    
    # 5. Fall back to static file_map - only if module_code was NOT provided
    # When module_code is provided but no backend exists, we should NOT use static files
    # This allows showing "Coming Soon" for modules without configured backends
    if not filepath and not module_code:
        file_map = {
            "electrical":      os.path.join(base_dir, "core", "data", "electrical.xlsx"),
            "civil":           os.path.join(base_dir, "core", "data", "civil.xlsx"),
            "temp_electrical": os.path.join(base_dir, "core", "data", "temp_electrical.xlsx"),
            "temp_civil":      os.path.join(base_dir, "core", "data", "temp_civil.xlsx"),
            "amc_electrical":  os.path.join(base_dir, "core", "data", "amc_electrical.xlsx"),
            "amc_civil":       os.path.join(base_dir, "core", "data", "amc_civil.xlsx"),
        }
        filepath = file_map.get(category_key)

    if not filepath or not os.path.exists(filepath):
        raise FileNotFoundError(f"Excel file not found for category: {category_key}")

    # Keep formulas (needed for rates, etc.)
    wb = load_workbook(filepath, data_only=False)

    if "Master Datas" not in wb.sheetnames:
        raise ValueError("Sheet 'Master Datas' missing in backend Excel.")
    if "Groups" not in wb.sheetnames:
        raise ValueError("Sheet 'Groups' missing in backend Excel.")

    ws_data = wb["Master Datas"]
    ws_groups = wb["Groups"]

    items_list = detect_items(ws_data)
    groups_map, units_map = read_groups(ws_groups)

    return items_list, groups_map, units_map, ws_data, filepath


def get_available_backends_for_module(module_code, category):
    """
    Get list of available backends for a module and category.
    
    Returns list of dicts: [{'id': 1, 'name': 'Telangana SOR', 'is_default': True}, ...]
    """
    category_key = str(category).lower().strip()
    
    try:
        from subscriptions.models import ModuleBackend
        
        backends = ModuleBackend.objects.filter(
            module__code=module_code,
            category=category_key,
            is_active=True
        ).order_by('display_order', 'name')
        
        return [
            {'id': b.pk, 'name': b.name, 'is_default': b.is_default}
            for b in backends
        ]
    except (OperationalError, ProgrammingError, Exception):
        return []



# ---------- Extract full cell objects for a block ----------
def extract_item_block(ws_data, item_info):
    rows = []
    for r in range(item_info["start_row"], item_info["end_row"] + 1):
        row_cells = [ws_data.cell(row=r, column=c) for c in range(SCAN_COL_START, SCAN_COL_END + 1)]
        rows.append(row_cells)
    return rows


# ---------- Copy with styles, merges, widths, heights & formula translation ----------
from openpyxl.utils import get_column_letter
from openpyxl.formula.translate import Translator
from copy import copy

from copy import copy
from openpyxl.utils import get_column_letter
from openpyxl.cell.cell import MergedCell

from copy import copy
from openpyxl.utils import get_column_letter
from openpyxl.formula.translate import Translator
from openpyxl.cell.cell import MergedCell

def copy_block_with_styles_and_formulas(
    ws_src,
    ws_dst,
    src_min_row,
    src_max_row,
    col_start,
    col_end,
    dst_start_row,
    dst_start_col=1
):
    """
    Copies a rectangular block including:
      - values / formulas (✅ translated to new position)
      - styles
      - row heights / col widths
      - merged ranges (replicated with offset)

    Safely handles merged cells (does not write into MergedCell).
    """

    row_offset = dst_start_row - src_min_row
    col_offset = dst_start_col - col_start

    # 1) Column widths
    for c in range(col_start, col_end + 1):
        letter = get_column_letter(c)
        dst_letter = get_column_letter(c + col_offset)
        src_dim = ws_src.column_dimensions.get(letter)
        if src_dim and src_dim.width:
            ws_dst.column_dimensions[dst_letter].width = src_dim.width

    # 2) Row heights
    for r in range(src_min_row, src_max_row + 1):
        src_dim = ws_src.row_dimensions.get(r)
        if src_dim and src_dim.height:
            ws_dst.row_dimensions[r + row_offset].height = src_dim.height

    # 3) Prepare merged ranges mapping inside the block.
    merged_map = []  # list of (min_row, min_col, max_row, max_col)
    for merged in ws_src.merged_cells.ranges:
        min_col, min_row, max_col, max_row = merged.bounds
        if (
            min_row >= src_min_row and max_row <= src_max_row and
            min_col >= col_start and max_col <= col_end
        ):
            merged_map.append((min_row, min_col, max_row, max_col))

    def find_merged_top(r, c):
        for (mr1, mc1, mr2, mc2) in merged_map:
            if mr1 <= r <= mr2 and mc1 <= c <= mc2:
                return mr1, mc1
        return None

    # 4) Copy cell values + styles (✅ translate formulas)
    for r in range(src_min_row, src_max_row + 1):
        for c in range(col_start, col_end + 1):
            # If this cell is inside a merged range, use the top-left src cell as source
            top = find_merged_top(r, c)
            if top:
                src_r, src_c = top
                # For non-top-left cells in merged regions, skip value/style copy
                # (they'll be part of the merge later)
                if (r, c) != top:
                    continue
            else:
                src_r, src_c = r, c

            src_cell = ws_src.cell(row=src_r, column=src_c)
            dst_cell = ws_dst.cell(row=r + row_offset, column=c + col_offset)
            
            # Skip if source is a MergedCell (shouldn't happen with our logic, but safety check)
            if isinstance(src_cell, MergedCell):
                continue

            v = src_cell.value

            # If formula, translate it to new position (origin is actual src coordinate)
            if isinstance(v, str) and v.startswith("="):
                try:
                    v = Translator(v, origin=src_cell.coordinate).translate_formula(
                        row_delta=row_offset + (src_r - r),
                        col_delta=col_offset + (src_c - c)
                    )
                except Exception:
                    pass
            elif isinstance(v, str):
                # Normalize text to fix encoding issues (em-dash -> hyphen, etc.)
                v = normalize_text(v)

            dst_cell.value = v

            # Always copy styles - don't rely on has_style which can be unreliable
            # Copy each style attribute individually for maximum compatibility
            try:
                if src_cell.font:
                    dst_cell.font = copy(src_cell.font)
            except Exception:
                pass
            
            try:
                if src_cell.fill:
                    dst_cell.fill = copy(src_cell.fill)
            except Exception:
                pass
            
            try:
                if src_cell.border:
                    dst_cell.border = copy(src_cell.border)
            except Exception:
                pass
            
            try:
                if src_cell.alignment:
                    dst_cell.alignment = copy(src_cell.alignment)
            except Exception:
                pass
            
            try:
                if src_cell.number_format:
                    dst_cell.number_format = src_cell.number_format
            except Exception:
                pass
            
            try:
                if src_cell.protection:
                    dst_cell.protection = copy(src_cell.protection)
            except Exception:
                pass

    # 5) Now replicate merged cells inside the block (after copying values/styles)
    for (min_row, min_col, max_row, max_col) in merged_map:
        ws_dst.merge_cells(
            start_row=min_row + row_offset,
            end_row=max_row + row_offset,
            start_column=min_col + col_offset,
            end_column=max_col + col_offset,
        )



def get_item_description_and_rate(ws_data, item_info):
    """
    Extracts:
      - Description from 2 rows below header in col D
      - Rate as last non-empty cell in column J (inside block only)
    """
    desc = ws_data.cell(item_info["start_row"] + 2, 4).value
    desc = str(desc).strip() if desc else ""

    rate = ""
    # iterate from end_row down to start_row (inclusive)
    for r in range(item_info["end_row"], item_info["start_row"] - 1, -1):
        val = ws_data.cell(r, 10).value
        if val not in (None, ""):
            rate = val
            break

    return desc, rate
# core/utils_excel.py

import json

import re

def _norm_item_name(s: str) -> str:
    """Normalize item names so dict keys match UI values."""
    s = "" if s is None else str(s)
    s = s.replace("\n", " ").replace("\r", " ")
    s = re.sub(r"\s+", " ", s).strip()
    return s

import re

def _parse_number_maybe(v):
    """
    Converts values like:
      1016
      1,016
      ₹ 1,016.00
      "1016.00"
    into float.
    If v is a formula string like "=G148*I148", returns None.
    """
    if v is None or v == "":
        return None

    # numeric already
    if isinstance(v, (int, float)):
        return float(v)

    s = str(v).strip()

    # formula -> cannot evaluate here (use data_only=True sheet to get cached result)
    if s.startswith("="):
        return None

    # remove currency / commas / non-numeric except dot and minus
    s = s.replace(",", "")
    s = re.sub(r"[^0-9.\-]", "", s)

    if s in ("", "-", ".", "-."):
        return None

    try:
        return float(s)
    except Exception:
        return None

import re
import ast
import operator as op

# ---- safe eval for very simple excel formulas like: =G148*I148 or =J10*2 ----
_ALLOWED_OPS = {
    ast.Add: op.add,
    ast.Sub: op.sub,
    ast.Mult: op.mul,
    ast.Div: op.truediv,
    ast.USub: op.neg,
    ast.UAdd: op.pos,
}

_CELL_REF_RE = re.compile(r"\$?([A-Z]{1,3})\$?(\d+)", re.IGNORECASE)

def _to_number(v):
    try:
        if v is None or v == "":
            return 0.0
        return float(v)
    except Exception:
        return 0.0

def _safe_eval_expr(expr: str) -> float:
    """
    Evaluate expression containing only numbers and + - * / ().
    """
    def _eval(node):
        if isinstance(node, ast.Num):  # py<3.8
            return float(node.n)
        if isinstance(node, ast.Constant):  # py>=3.8
            if isinstance(node.value, (int, float)):
                return float(node.value)
            return 0.0
        if isinstance(node, ast.BinOp) and type(node.op) in _ALLOWED_OPS:
            return _ALLOWED_OPS[type(node.op)](_eval(node.left), _eval(node.right))
        if isinstance(node, ast.UnaryOp) and type(node.op) in _ALLOWED_OPS:
            return _ALLOWED_OPS[type(node.op)](_eval(node.operand))
        raise ValueError("Unsafe/unsupported expression")
    tree = ast.parse(expr, mode="eval")
    return float(_eval(tree.body))

def _eval_excel_formula_cell(ws, formula: str, current_row: int) -> float:
    """
    Supports formulas like:
      =G148*I148
      =$G$148*$I$148
      =G148*2
      =G148+I148
    We replace cell refs with their numeric values from the SAME SHEET.
    """
    if not isinstance(formula, str):
        return 0.0

    f = formula.strip()
    if not f.startswith("="):
        return _to_number(f)

    f = f[1:]  # remove '='

    def repl(m):
        col = m.group(1).upper()
        row = int(m.group(2))
        v = ws[f"{col}{row}"].value

        # if referenced cell is itself a formula, we try ONE level of evaluation
        if isinstance(v, str) and v.strip().startswith("="):
            return str(_eval_excel_formula_cell(ws, v, row))
        return str(_to_number(v))

    expr = _CELL_REF_RE.sub(repl, f)

    # remove any leftover illegal characters
    # (keep digits, dot, operators, parentheses, spaces)
    expr = re.sub(r"[^0-9\.\+\-\*\/\(\)\s]", "", expr)

    try:
        return _safe_eval_expr(expr)
    except Exception:
        return 0.0

import re
import math
from openpyxl import load_workbook
from openpyxl.utils.cell import coordinate_from_string, column_index_from_string


def _safe_float(x):
    try:
        if x is None or x == "":
            return None
        if isinstance(x, (int, float)):
            return float(x)
        s = str(x).replace(",", "").strip()
        if s == "":
            return None
        return float(s)
    except Exception:
        return None


_cell_ref_re = re.compile(r"\b(\$?[A-Z]{1,3}\$?\d+)\b")


def _get_cell_value(ws_vals, ws_formulas, addr, _depth=0):
    """
    Return numeric value for a cell reference like 'J148'.
    Uses cached values first; if missing and formula exists, tries to evaluate recursively.
    """
    if _depth > 25:
        return 0.0  # prevent infinite loops

    col_letter, row = coordinate_from_string(addr.replace("$", ""))
    col = column_index_from_string(col_letter)
    r = int(row)

    v = ws_vals.cell(row=r, column=col).value
    num = _safe_float(v)
    if num is not None:
        return num

    # if cached missing, try formula evaluation
    f = ws_formulas.cell(row=r, column=col).value
    if isinstance(f, str) and f.startswith("="):
        return _eval_excel_formula(f, ws_vals, ws_formulas, _depth=_depth + 1)

    return 0.0


def _round_excel(x, ndigits):
    # Excel ROUND halves away from zero? Python round is bankers.
    # We'll implement "away from zero" to be closer.
    try:
        nd = int(ndigits)
    except Exception:
        nd = 0
    factor = 10 ** nd
    if factor == 0:
        return x
    if x >= 0:
        return math.floor(x * factor + 0.5) / factor
    return math.ceil(x * factor - 0.5) / factor


def _eval_excel_formula(formula, ws_vals, ws_formulas, _depth=0):
    """
    Minimal evaluator for formulas like:
      =ROUND(G148*I148,0)
      =G148*I148
      =(G148+I148)/2
    Supports: + - * / ( ) and ROUND(x,n)
    """
    if _depth > 25:
        return 0.0

    expr = formula.strip()
    if expr.startswith("="):
        expr = expr[1:].strip()

    # Normalize Excel function names
    # Handle ROUND(...)
    # We'll convert ROUND(a,b) -> ROUND(a,b) and process ourselves.
    expr_up = expr.upper()

    # Replace cell refs with numeric values
    def repl(m):
        addr = m.group(1)
        val = _get_cell_value(ws_vals, ws_formulas, addr, _depth=_depth + 1)
        return str(val)

    expr2 = _cell_ref_re.sub(repl, expr_up)

    # Handle ROUND(...) manually
    # We will repeatedly evaluate innermost ROUND.
    round_re = re.compile(r"ROUND\(([^()]+?),([^()]+?)\)")
    while True:
        m = round_re.search(expr2)
        if not m:
            break
        a = m.group(1).strip()
        b = m.group(2).strip()
        try:
            aval = _safe_eval_arith(a)
            bval = _safe_eval_arith(b)
            rep = str(_round_excel(aval, bval))
        except Exception:
            rep = "0.0"
        expr2 = expr2[:m.start()] + rep + expr2[m.end():]

    # Now evaluate remaining arithmetic safely
    try:
        return float(_safe_eval_arith(expr2))
    except Exception:
        return 0.0


def _safe_eval_arith(s):
    """
    Safe arithmetic evaluator for numbers and + - * / parentheses only.
    Uses AST parsing instead of eval() for security.
    """
    s = s.strip()
    if s == "":
        return 0.0

    # Reject anything unexpected - only allow digits, decimals, operators, parentheses, spaces
    if re.search(r"[^0-9\.\+\-\*\/\(\)\s]", s):
        raise ValueError("Unsafe expression")

    # Use AST-based safe evaluation instead of eval()
    try:
        return _safe_eval_expr(s)
    except Exception:
        raise ValueError("Invalid arithmetic expression")


def build_temp_day_rates(filepath, items_list):
    """
    Backend TEMP structure (your final clarification):
      - Day numbers are in Column C
      - Rates are in Column J
      - Column J often has formulas like ROUND()
    We load:
      - ws_vals (data_only=True) for cached values
      - ws_formulas (data_only=False) for the formula text
    """
    wb_vals = load_workbook(filepath, data_only=True)
    wb_for = load_workbook(filepath, data_only=False)

    if "Master Datas" not in wb_vals.sheetnames or "Master Datas" not in wb_for.sheetnames:
        return {}

    ws_vals = wb_vals["Master Datas"]
    ws_for = wb_for["Master Datas"]

    day_rates = {}

    for it in items_list:
        name = (it.get("name") or "").strip()
        sr = int(it.get("start_row") or 0)
        er = int(it.get("end_row") or 0)
        if not name or sr <= 0 or er <= 0:
            continue

        per_item = {}

        for r in range(sr, er + 1):
            day_cell = ws_vals.cell(row=r, column=3).value  # Column C
            if day_cell in (None, ""):
                continue

            try:
                day_no = int(float(day_cell))
            except Exception:
                continue

            if day_no <= 0:
                continue

            # Try cached numeric
            rate_cached = _safe_float(ws_vals.cell(row=r, column=10).value)  # J
            if rate_cached is not None and rate_cached > 0:
                per_item[str(day_no)] = rate_cached
                continue

            # Fallback: evaluate formula from ws_for J
            f = ws_for.cell(row=r, column=10).value
            if isinstance(f, str) and f.startswith("="):
                rate_calc = _eval_excel_formula(f, ws_vals, ws_for)
                if rate_calc and rate_calc > 0:
                    per_item[str(day_no)] = float(rate_calc)

        if per_item:
            day_rates[_norm_item_name(name)] = per_item

    return day_rates
