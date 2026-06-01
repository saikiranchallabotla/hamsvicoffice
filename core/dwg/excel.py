"""Excel writer: produces a Bill-of-Quantities pivot in legend-table style."""
from io import BytesIO

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter


HEADER_FILL = PatternFill("solid", fgColor="1F4E78")
HEADER_FONT = Font(bold=True, color="FFFFFF")
TOTAL_FILL = PatternFill("solid", fgColor="E7E6E6")
BORDER = Border(*[Side(style="thin", color="888888")] * 4)
CENTER = Alignment(horizontal="center", vertical="center", wrap_text=True)
LEFT = Alignment(horizontal="left", vertical="center", wrap_text=True)


def build_takeoff_workbook(name: str, summary: dict, zone_names: list) -> bytes:
    """summary: {description: {zone_name: count}}"""
    wb = Workbook()
    ws = wb.active
    ws.title = (name or "Takeoff")[:31]

    zones = list(zone_names) if zone_names else []
    # Always include Unassigned if any row has it
    if any("Unassigned" in zd for zd in summary.values()) and "Unassigned" not in zones:
        zones.append("Unassigned")

    header = ["#", "Description"] + zones + ["Total"]
    ws.append(header)
    for col_idx, _ in enumerate(header, start=1):
        cell = ws.cell(row=1, column=col_idx)
        cell.fill = HEADER_FILL
        cell.font = HEADER_FONT
        cell.alignment = CENTER
        cell.border = BORDER

    grand_total = 0
    zone_totals = {z: 0 for z in zones}
    for i, (desc, zd) in enumerate(sorted(summary.items(), key=lambda kv: kv[0].lower()), start=1):
        row = [i, desc]
        row_total = 0
        for z in zones:
            v = int(zd.get(z, 0))
            row.append(v)
            row_total += v
            zone_totals[z] += v
        row.append(row_total)
        grand_total += row_total
        ws.append(row)
        r = ws.max_row
        ws.cell(row=r, column=1).alignment = CENTER
        ws.cell(row=r, column=2).alignment = LEFT
        for c in range(3, len(header) + 1):
            ws.cell(row=r, column=c).alignment = CENTER
        for c in range(1, len(header) + 1):
            ws.cell(row=r, column=c).border = BORDER

    # Totals row
    totals = ["", "TOTAL"] + [zone_totals[z] for z in zones] + [grand_total]
    ws.append(totals)
    r = ws.max_row
    for c in range(1, len(header) + 1):
        cell = ws.cell(row=r, column=c)
        cell.font = Font(bold=True)
        cell.fill = TOTAL_FILL
        cell.alignment = CENTER if c != 2 else LEFT
        cell.border = BORDER

    # Column widths
    ws.column_dimensions["A"].width = 6
    ws.column_dimensions["B"].width = 42
    for idx in range(3, len(header) + 1):
        ws.column_dimensions[get_column_letter(idx)].width = 14
    ws.freeze_panes = "C2"

    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()
