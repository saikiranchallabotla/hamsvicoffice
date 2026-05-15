# Direct test of _remap_formula with the exact user example
# Run: python tmp/test_remap.py

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import just the two functions we care about - no Django needed
import re
from openpyxl.utils import get_column_letter, column_index_from_string

# ---- paste the two functions directly ----

_CELL_REF_RE = re.compile(r'(?<![!\w\$])(\$?)([A-Za-z]{1,3})(\$?)(\d+)(?![A-Za-z\d])')

def _remap_formula(formula, src_r, src_c, dst_r, dst_c,
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
            # Looser check: shift if row >= src_min_row (not strict upper bound)
            new_row = row_num + row_delta if row_num >= src_min_row else row_num
        else:
            new_row = row_num + row_delta
        new_col = max(1, min(new_col, 16384)); new_row = max(1, min(new_row, 1048576))
        return f'{col_dollar}{get_column_letter(new_col)}{row_dollar}{new_row}'
    return _CELL_REF_RE.sub(_sub, formula)

# -----------------------------------------------
# USER'S EXACT EXAMPLE
# Block: rows 120-135, cols 1-10
# Cell J132 has formula =$J$131
# User fetches this item 1st → dst_start_row = 3 (after header+blank)
# -----------------------------------------------
SRC_MIN = 120
SRC_MAX = 135
DST_START = 3     # cursor starts at 3

row_offset = DST_START - SRC_MIN  # = -117

print("=== User's example: block rows 120-135 → output row 3 ===")
print(f"row_offset = {row_offset}")
print()

cases = [
    # (src_row, src_col, formula, description)
    (132, 10, '=$J$131',    'both absolute, intra-block'),
    (132, 10, '=J131',      'both relative, intra-block'),
    (132, 10, '=J$131',     'abs-row only, intra-block'),
    (132, 10, '=$J131',     'abs-col only, intra-block'),
    (132, 10, '=$J$131+=$J$119', 'intra-block + outside-block absolute'),
    (132, 10, '=$J$131+J119',    'intra-block abs + outside-block relative'),
    (132, 10, "=SUM(J$120:J$135)", 'abs-row range, full block extent'),
    (132, 10, "=LEAD!$J$131",      'cross-sheet ref (must NOT change)'),
    (132, 10, "='Master Datas'!$J$131", 'self-sheet-qualified (strips + shifts)'),
    (132, 10, '=SUM(E132*I132/G132)',   'typical intra-block relative formula'),
]

all_passed = True
for src_r, src_c, formula, desc in cases:
    dst_r = src_r + row_offset
    dst_c = src_c

    # Strip self-sheet qualifier (as the function does)
    self_re = re.compile(r"(?:\[\d+\])?'?Master Datas'?!")
    f_stripped = self_re.sub('', formula)

    result = _remap_formula(
        f_stripped,
        src_r=src_r, src_c=src_c,
        dst_r=dst_r, dst_c=dst_c,
        src_min_row=SRC_MIN, src_max_row=SRC_MAX,
        col_start=1, col_end=10,
    )
    print(f"  {desc}")
    print(f"    Input:  {formula}")
    print(f"    Output: {result}")
    print()

# Specific assertion for the user's exact case
f = _remap_formula('=$J$131', src_r=132, src_c=10,
                    dst_r=132+row_offset, dst_c=10,
                    src_min_row=120, src_max_row=135,
                    col_start=1, col_end=10)
expected = '=$J$14'  # 131 + (-117) = 14
assert f == expected, f"FAIL: got {f!r}, expected {expected!r}"
print(f"ASSERTION PASSED: =$J$131 correctly remapped to {expected}")
print()

# Test that relative refs within the block also shift correctly
f2 = _remap_formula('=J131', src_r=132, src_c=10,
                     dst_r=132+row_offset, dst_c=10,
                     src_min_row=120, src_max_row=135,
                     col_start=1, col_end=10)
expected2 = '=J14'
assert f2 == expected2, f"FAIL: got {f2!r}, expected {expected2!r}"
print(f"ASSERTION PASSED: =J131 (relative) correctly remapped to {expected2}")

# Test cross-sheet ref stays unchanged
f3 = _remap_formula('=LEAD!$J$131', src_r=132, src_c=10,
                     dst_r=132+row_offset, dst_c=10,
                     src_min_row=120, src_max_row=135,
                     col_start=1, col_end=10)
assert f3 == '=LEAD!$J$131', f"FAIL cross-sheet: got {f3!r}"
print(f"ASSERTION PASSED: =LEAD!$J$131 cross-sheet ref unchanged")

# More cross-sheet cases
f4 = _remap_formula("='Master Datas'!$J$131", src_r=132, src_c=10,
                     dst_r=132+row_offset, dst_c=10,
                     src_min_row=120, src_max_row=135,
                     col_start=1, col_end=10)
# After stripping self-sheet: =$J$131 → =$J$14
self_re = re.compile(r"(?:\[\d+\])?'?Master Datas'?!")
f4_stripped = self_re.sub('', "='Master Datas'!$J$131")
f4_result = _remap_formula(f4_stripped, src_r=132, src_c=10,
                            dst_r=132+row_offset, dst_c=10,
                            src_min_row=120, src_max_row=135,
                            col_start=1, col_end=10)
assert f4_result == '=$J$14', f"FAIL self-sheet stripped: got {f4_result!r}"
print(f"ASSERTION PASSED: ='Master Datas'!$J$131 after strip → =$J$14")

# Relative ref outside block stays shifted (normal Excel behaviour for relative)
f5 = _remap_formula('=J119', src_r=132, src_c=10,
                     dst_r=132+row_offset, dst_c=10,
                     src_min_row=120, src_max_row=135,
                     col_start=1, col_end=10)
expected5 = f'=J{119 - 117}'  # = J2
assert f5 == expected5, f"FAIL relative-outside: got {f5!r}"
print(f"ASSERTION PASSED: =J119 (relative outside block) shifts to {expected5}")

# Absolute ref OUTSIDE block (BEFORE src_min_row=120) does NOT shift
f6 = _remap_formula('=$J$119', src_r=132, src_c=10,
                     dst_r=132+row_offset, dst_c=10,
                     src_min_row=120, src_max_row=135,
                     col_start=1, col_end=10)
assert f6 == '=$J$119', f"FAIL abs-outside: got {f6!r}"
print(f"ASSERTION PASSED: =$J$119 (absolute BEFORE block start 120) unchanged")

# -------------------------------------------------------
# USER'S EXACT CASE (latest complaint)
# Item 10 block: detect_items gives src_max_row=163 (last rate row)
# but block logically extends to row 165.
# Formula =$J$165*G163, fetched first → dst_start=3, row_offset=-144
# OLD code: $J$165 not shifted (165 > 163 = src_max_row) → BUG
# NEW code: $J$165 shifted (165 >= 147 = src_min_row) → FIXED
# -------------------------------------------------------
print()
print("=== User's exact failing case ===")
src_min_user, src_max_user = 147, 163   # detect_items cutoff at rate row
formula_row_user = 163
row_offset_user = 3 - 147  # = -144

result_user = _remap_formula(
    '=$J$165*G163',
    src_r=formula_row_user, src_c=10,
    dst_r=formula_row_user + row_offset_user, dst_c=10,
    src_min_row=src_min_user, src_max_row=src_max_user,
    col_start=1, col_end=10,
)
expected_user = '=$J$21*G19'   # 165-144=21,  163-144=19
assert result_user == expected_user, f"FAIL user case: got {result_user!r}"
print(f"ASSERTION PASSED: =$J$165*G163 → {result_user}")

# Header ref ($A$1, row 1 < src_min_row=147) → stays fixed
result_header = _remap_formula('=$A$1', src_r=163, src_c=1,
                                dst_r=163+row_offset_user, dst_c=1,
                                src_min_row=src_min_user, src_max_row=src_max_user,
                                col_start=1, col_end=10)
assert result_header == '=$A$1', f"FAIL header: got {result_header!r}"
print(f"ASSERTION PASSED: =$A$1 (header, row < block start) preserved")
