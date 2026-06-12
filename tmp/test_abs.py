import re

abs_row_re = re.compile(r"(?<![!\w])(\$?)([A-Za-z]{1,3})\$(\d+)(?![A-Za-z\d])")

src_min, end, off = 100, 110, -80

def shift(m):
    rn = int(m.group(3))
    if src_min <= rn <= end:
        return f"{m.group(1)}{m.group(2)}${rn+off}"
    return m.group(0)

tests = [
    "=$B$105+C103",
    "=B$105+C103",
    "=$B$200",
    "=LEAD!$J$131",
    "=$A$100+$Z$110+$B$111",
    "=SUM($A$100:$A$110)",
]
for t in tests:
    print(t, "->", abs_row_re.sub(shift, t))
