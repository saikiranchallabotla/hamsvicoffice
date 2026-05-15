# Prove the root cause with the user's exact numbers
import re
from openpyxl.utils import get_column_letter, column_index_from_string

_CELL_REF_RE = re.compile(r'(?<![!\w\$])(\$?)([A-Za-z]{1,3})(\$?)(\d+)(?![A-Za-z\d])')

def _remap_formula_current(formula, src_r, src_c, dst_r, dst_c,
                            src_min_row, src_max_row, col_start, col_end):
    if not isinstance(formula, str) or not formula.startswith('='):
        return formula
    row_delta = dst_r - src_r
    col_delta = dst_c - src_c
    if row_delta == 0 and col_delta == 0:
        return formula
    def _sub(m):
        col_dollar = m.group(1); col_str = m.group(2)
        row_dollar = m.group(3); row_str = m.group(4)
        col_num = column_index_from_string(col_str); row_num = int(row_str)
        if col_dollar:
            new_col = col_num + col_delta if col_start <= col_num <= col_end else col_num
        else:
            new_col = col_num + col_delta
        if row_dollar:
            new_row = row_num + row_delta if src_min_row <= row_num <= src_max_row else row_num
        else:
            new_row = row_num + row_delta
        new_col = max(1, min(new_col, 16384)); new_row = max(1, min(new_row, 1048576))
        return f'{col_dollar}{get_column_letter(new_col)}{row_dollar}{new_row}'
    return _CELL_REF_RE.sub(_sub, formula)

# ===========================================================================
# User's exact case:
#   Item 10 in backend. Formula = =$J$165*G163.
#   User fetches it first → output cursor = 3.
#   G163 → G19  (delta = -144)  → src_min_row = 147
#   $J$165 → $J$165  (NOT shifted) → means 165 > src_max_row in current code
# ===========================================================================

# What src_max_row values cause the bug?
# G163 delta = 19-163 = -144 = row_offset = dst_start_row - src_min_row
# dst_start_row = 3,  src_min_row = 147
src_min_row = 147
dst_start_row = 3
row_offset = dst_start_row - src_min_row  # = -144
formula_row = 163  # the cell containing the formula
dst_row = formula_row + row_offset  # = 19

print("=== Root cause analysis ===")
print(f"src_min_row = {src_min_row}")
print(f"row_offset  = {row_offset}")
print(f"formula at row {formula_row} moves to row {dst_row}")
print()

for src_max_row in [163, 164, 165, 175]:
    result = _remap_formula_current(
        '=$J$165*G163',
        src_r=formula_row, src_c=10,
        dst_r=dst_row, dst_c=10,
        src_min_row=src_min_row, src_max_row=src_max_row,
        col_start=1, col_end=10
    )
    abs_shifted = '$J$165' not in result
    print(f"  src_max_row={src_max_row}: {result}   abs_shifted={abs_shifted}")

print()
print("CONCLUSION:")
print("  When src_max_row < 165 (e.g. 163 or 164), $J$165 is treated as")
print("  'outside block' and is NOT shifted. G163 (relative) shifts anyway.")
print("  This matches exactly what the user is seeing.")
print()
print("  The block boundary detected by detect_items ends BEFORE row 165,")
print("  probably because the next item heading is at row 164 or 165,")
print("  OR a subrow within item 10's block has yellow+red formatting.")
print()
print("FIX: for absolute row refs, check row_num >= src_min_row")
print("  (shift if in-or-after current block start, not in strict [min,max] range)")
print("  This means: refs to rows BEFORE this block are NOT shifted (preserved)")
print("  while refs to rows AT OR AFTER src_min_row ARE shifted (treated as intra-block)")
