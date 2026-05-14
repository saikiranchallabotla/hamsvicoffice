"""
Temporary Works — Bill module.

Two-sheet workbook:
  Sheet 1 (Bill Summary) — one row per item, totals across events
  Sheet 2 (Bill Detail)  — per-event rows mirroring the Workslip layout

Session keys (tw_bill_*):
  tw_bill_entries
  tw_bill_events_list
  tw_bill_exec_map           - {entry_id: {event_id: qty_bill}}
  tw_bill_prev_exec          - cumulative qty from previous bills (carry-forward)
  tw_bill_work_name
  tw_bill_category
  tw_bill_selected_backend_id
  tw_bill_number
  tw_bill_source_workslip_id
"""
import io
import json
import logging
import re

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import redirect, render

from ..utils_excel import build_temp_day_rates, load_backend
from .tempworks_workslip_views import (
    _build_desc_map, _coerce_float, _norm_name, _rate_for_event_days, _to_roman_lower,
)

logger = logging.getLogger(__name__)


def _build_bill_view_rows(entries, exec_map, prev_exec, day_rates_by_item):
    rows = []
    sl = 1
    for entry in entries or []:
        if (entry or {}).get("mode") != "multi":
            continue
        item_name = entry.get("name") or ""
        entry_id = entry.get("id") or ""
        events = entry.get("events") or []
        valid_events = []
        for ev in events:
            ev_name = (ev.get("event_name") or "").strip()
            ev_days = int(_coerce_float(ev.get("days"), 0))
            ev_qty = _coerce_float(ev.get("qty"), 0.0)
            if ev_name and ev_days > 0 and ev_qty > 0:
                valid_events.append({
                    "event_id": ev.get("event_id") or "",
                    "event_name": ev_name,
                    "days": ev_days,
                    "qty_est": ev_qty,
                })
        if not valid_events:
            continue

        rows.append({
            "kind": "header",
            "sl": sl,
            "entry_id": entry_id,
            "item_name": item_name,
            "desc": item_name,
        })
        item_day_rates = day_rates_by_item.get(_norm_name(item_name)) or day_rates_by_item.get(item_name) or {}
        for i, ev in enumerate(valid_events, start=1):
            roman = _to_roman_lower(i)
            day_word = "day" if ev["days"] == 1 else "days"
            desc = f"{roman}. {ev['event_name']} for {ev['days']} {day_word}"
            rate = _rate_for_event_days(item_day_rates, ev["days"])
            bill_qty = _coerce_float((exec_map.get(entry_id) or {}).get(ev["event_id"]), 0.0)
            prev_qty = _coerce_float((prev_exec.get(entry_id) or {}).get(ev["event_id"]), 0.0)
            net_qty = round(bill_qty - prev_qty, 2)
            rows.append({
                "kind": "event",
                "entry_id": entry_id,
                "event_id": ev["event_id"],
                "roman": roman,
                "desc": desc,
                "event_name": ev["event_name"],
                "days": ev["days"],
                "qty_est": ev["qty_est"],
                "rate": rate,
                "amt_est": round(ev["qty_est"] * rate, 2),
                "qty_bill": bill_qty,
                "qty_prev": prev_qty,
                "qty_net": net_qty,
                "amt_net": round(net_qty * rate, 2),
            })
        sl += 1
    return rows


@login_required(login_url="login")
def temp_bill(request):
    entries = request.session.get("tw_bill_entries") or []
    exec_map = request.session.get("tw_bill_exec_map") or {}
    prev_exec = request.session.get("tw_bill_prev_exec") or {}
    work_name = request.session.get("tw_bill_work_name") or ""
    category = request.session.get("tw_bill_category") or "electrical"
    backend_id = request.session.get("tw_bill_selected_backend_id")
    bill_number = request.session.get("tw_bill_number") or 1

    if not entries:
        return redirect("dashboard")

    items_list = []
    filepath = None
    try:
        items_list, _gm, _um, _ws_src, filepath = load_backend(
            f"temp_{category}", settings.BASE_DIR,
            backend_id=backend_id, module_code="temp_works",
        )
        day_rates = build_temp_day_rates(filepath, items_list) or {}
    except Exception:
        logger.exception("[TEMP_BILL] load_backend failed (category=%s)", category)
        day_rates = {}

    day_rates_by_item = {}
    for k, v in (day_rates or {}).items():
        day_rates_by_item[k] = v
        day_rates_by_item[_norm_name(k)] = v

    desc_by_item = _build_desc_map(items_list, filepath)

    if request.method == "POST":
        action = request.POST.get("action") or ""
        exec_map_str = request.POST.get("exec_map", "")
        new_exec_map = exec_map
        if exec_map_str:
            try:
                parsed = json.loads(exec_map_str)
                if isinstance(parsed, dict):
                    new_exec_map = {}
                    for ent_id, evs in parsed.items():
                        if not isinstance(evs, dict):
                            continue
                        new_exec_map[str(ent_id)] = {
                            str(ev_id): _coerce_float(q, 0.0)
                            for ev_id, q in evs.items()
                        }
            except Exception:
                logger.exception("[TEMP_BILL] bad exec_map payload")

        wn_form = (request.POST.get("ws_work_name") or "").strip()
        if wn_form:
            work_name = wn_form
            request.session["tw_bill_work_name"] = work_name

        request.session["tw_bill_exec_map"] = new_exec_map
        request.session.modified = True
        exec_map = new_exec_map

        if action == "download_bill":
            return _download_bill_excel(
                entries=entries, exec_map=exec_map, prev_exec=prev_exec,
                day_rates_by_item=day_rates_by_item, desc_by_item=desc_by_item,
                work_name=work_name, bill_number=bill_number,
            )

    view_rows = _build_bill_view_rows(entries, exec_map, prev_exec, day_rates_by_item)
    total_net = sum(r["amt_net"] for r in view_rows if r["kind"] == "event")

    return render(request, "core/temp_bill.html", {
        "view_rows": view_rows,
        "work_name": work_name,
        "category": category,
        "bill_number": bill_number,
        "total_net": round(total_net, 2),
        "has_previous": any(r.get("qty_prev") for r in view_rows if r["kind"] == "event"),
    })


def _aggregate_per_item(entries, exec_map, prev_exec, day_rates_by_item):
    """Return a list of per-item totals for the Bill Summary sheet."""
    summary = []
    for entry in entries or []:
        if (entry or {}).get("mode") != "multi":
            continue
        item_name = entry.get("name") or ""
        entry_id = entry.get("id") or ""
        events = entry.get("events") or []
        item_day_rates = day_rates_by_item.get(_norm_name(item_name)) or day_rates_by_item.get(item_name) or {}

        qty_est_total = 0.0
        qty_bill_total = 0.0
        qty_prev_total = 0.0
        amt_net_total = 0.0
        # Simple rate for summary: weighted by event days. We use per-event rate
        # to compute amount; report a notional "rate" = total_amt/total_qty when usable.
        for ev in events:
            ev_name = (ev.get("event_name") or "").strip()
            ev_days = int(_coerce_float(ev.get("days"), 0))
            ev_qty_est = _coerce_float(ev.get("qty"), 0.0)
            if not (ev_name and ev_days > 0 and ev_qty_est > 0):
                continue
            ev_id = ev.get("event_id") or ""
            rate = _rate_for_event_days(item_day_rates, ev_days)
            qty_bill = _coerce_float((exec_map.get(entry_id) or {}).get(ev_id), 0.0)
            qty_prev = _coerce_float((prev_exec.get(entry_id) or {}).get(ev_id), 0.0)
            qty_net = qty_bill - qty_prev

            qty_est_total += ev_qty_est
            qty_bill_total += qty_bill
            qty_prev_total += qty_prev
            amt_net_total += qty_net * rate

        if qty_est_total <= 0 and qty_bill_total <= 0:
            continue
        summary.append({
            "item_name": item_name,
            "qty_est": round(qty_est_total, 2),
            "qty_prev": round(qty_prev_total, 2),
            "qty_bill": round(qty_bill_total, 2),
            "qty_net": round(qty_bill_total - qty_prev_total, 2),
            "amt_net": round(amt_net_total, 2),
        })
    return summary


def _download_bill_excel(entries, exec_map, prev_exec, day_rates_by_item, desc_by_item, work_name, bill_number):
    wb = Workbook()
    thin = Side(border_style="thin", color="000000")
    border_all = Border(left=thin, right=thin, top=thin, bottom=thin)
    header_fill = PatternFill("solid", fgColor="FFC8C8C8")

    # ---------- Sheet 1: Bill Summary ----------
    ws_sum = wb.active
    ws_sum.title = "Bill Summary"
    sum_headers = ["Sl.No", "Item Description", "Qty (Est)", "Prev Bill Qty", "Bill Qty", "Net Qty", "Amount"]
    ws_sum.merge_cells(start_row=1, start_column=1, end_row=1, end_column=len(sum_headers))
    t1 = ws_sum.cell(row=1, column=1, value=f"TEMP WORKS — BILL {bill_number} — SUMMARY")
    t1.font = Font(bold=True, size=14)
    t1.alignment = Alignment(horizontal="center", vertical="center")
    ws_sum.merge_cells(start_row=2, start_column=1, end_row=2, end_column=len(sum_headers))
    wn1 = ws_sum.cell(row=2, column=1, value=f"Name of the work : {work_name}" if work_name else "Name of the work :")
    wn1.font = Font(bold=True)
    wn1.alignment = Alignment(horizontal="left", vertical="center")

    for i, h in enumerate(sum_headers, start=1):
        c = ws_sum.cell(row=4, column=i, value=h)
        c.font = Font(bold=True)
        c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        c.fill = header_fill
        c.border = border_all
    widths_sum = [6, 50, 12, 14, 12, 12, 16]
    for i, w in enumerate(widths_sum, start=1):
        ws_sum.column_dimensions[get_column_letter(i)].width = w

    summary = _aggregate_per_item(entries, exec_map, prev_exec, day_rates_by_item)
    sum_row = 5
    grand_amt = 0.0
    for sl, it in enumerate(summary, start=1):
        item_name = it["item_name"]
        item_desc = (desc_by_item or {}).get(item_name) or (desc_by_item or {}).get(_norm_name(item_name)) or item_name
        ws_sum.cell(row=sum_row, column=1, value=sl).alignment = Alignment(horizontal="center", vertical="center")
        ws_sum.cell(row=sum_row, column=2, value=item_desc).alignment = Alignment(horizontal="justify", vertical="top", wrap_text=True)
        ws_sum.cell(row=sum_row, column=3, value=it["qty_est"]).alignment = Alignment(horizontal="right")
        ws_sum.cell(row=sum_row, column=4, value=it["qty_prev"]).alignment = Alignment(horizontal="right")
        ws_sum.cell(row=sum_row, column=5, value=it["qty_bill"]).alignment = Alignment(horizontal="right")
        ws_sum.cell(row=sum_row, column=6, value=it["qty_net"]).alignment = Alignment(horizontal="right")
        ws_sum.cell(row=sum_row, column=7, value=it["amt_net"]).alignment = Alignment(horizontal="right")
        for c_idx in range(1, len(sum_headers) + 1):
            ws_sum.cell(row=sum_row, column=c_idx).border = border_all
        grand_amt += it["amt_net"]
        sum_row += 1
    # Total row
    tot_cell = ws_sum.cell(row=sum_row, column=6, value="Total")
    tot_cell.font = Font(bold=True)
    tot_cell.alignment = Alignment(horizontal="right", vertical="center")
    ws_sum.cell(row=sum_row, column=7, value=round(grand_amt, 2)).font = Font(bold=True)
    for c_idx in range(1, len(sum_headers) + 1):
        ws_sum.cell(row=sum_row, column=c_idx).border = border_all

    # ---------- Sheet 2: Bill Detail ----------
    ws_det = wb.create_sheet("Bill Detail")
    det_headers = [
        "Sl.No", "Description of Item / Event",
        "Qty (Est)", "Rate", "Amt (Est)",
        "Prev Bill Qty", "Bill Qty", "Net Qty", "Net Amount",
        "Remarks",
    ]
    ws_det.merge_cells(start_row=1, start_column=1, end_row=1, end_column=len(det_headers))
    t2 = ws_det.cell(row=1, column=1, value=f"TEMP WORKS — BILL {bill_number} — DETAIL")
    t2.font = Font(bold=True, size=14)
    t2.alignment = Alignment(horizontal="center", vertical="center")
    ws_det.merge_cells(start_row=2, start_column=1, end_row=2, end_column=len(det_headers))
    wn2 = ws_det.cell(row=2, column=1, value=f"Name of the work : {work_name}" if work_name else "Name of the work :")
    wn2.font = Font(bold=True)
    wn2.alignment = Alignment(horizontal="left", vertical="center")

    for i, h in enumerate(det_headers, start=1):
        c = ws_det.cell(row=4, column=i, value=h)
        c.font = Font(bold=True)
        c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        c.fill = header_fill
        c.border = border_all
    widths_det = [6, 56, 10, 12, 14, 13, 12, 12, 14, 24]
    for i, w in enumerate(widths_det, start=1):
        ws_det.column_dimensions[get_column_letter(i)].width = w

    out_row = 5
    sl_counter = 1
    grand_det_amt = 0.0
    for entry in entries or []:
        if (entry or {}).get("mode") != "multi":
            continue
        item_name = entry.get("name") or ""
        entry_id = entry.get("id") or ""
        events = entry.get("events") or []
        valid_events = []
        for ev in events:
            ev_name = (ev.get("event_name") or "").strip()
            try:
                ev_days = int(ev.get("days") or 0)
            except (TypeError, ValueError):
                ev_days = 0
            try:
                ev_qty = float(ev.get("qty") or 0)
            except (TypeError, ValueError):
                ev_qty = 0.0
            if ev_name and ev_days > 0 and ev_qty > 0:
                valid_events.append({
                    "event_id": ev.get("event_id") or "",
                    "event_name": ev_name,
                    "days": ev_days,
                    "qty_est": ev_qty,
                })
        if not valid_events:
            continue

        header_desc = (desc_by_item or {}).get(item_name) or (desc_by_item or {}).get(_norm_name(item_name)) or item_name
        ws_det.cell(row=out_row, column=1, value=sl_counter).alignment = Alignment(horizontal="center", vertical="center")
        ws_det.cell(row=out_row, column=2, value=header_desc).alignment = Alignment(horizontal="justify", vertical="top", wrap_text=True)
        for c_idx in range(1, len(det_headers) + 1):
            ws_det.cell(row=out_row, column=c_idx).border = border_all
        out_row += 1

        item_day_rates = day_rates_by_item.get(_norm_name(item_name)) or day_rates_by_item.get(item_name) or {}
        ae_counter = 0

        for i, ev in enumerate(valid_events, start=1):
            roman = _to_roman_lower(i)
            day_word = "day" if ev["days"] == 1 else "days"
            desc = f"{roman}. {ev['event_name']} for {ev['days']} {day_word}"
            rate = _rate_for_event_days(item_day_rates, ev["days"])
            qty_est = float(ev["qty_est"])
            qty_bill = _coerce_float((exec_map.get(entry_id) or {}).get(ev["event_id"]), 0.0)
            qty_prev = _coerce_float((prev_exec.get(entry_id) or {}).get(ev["event_id"]), 0.0)
            qty_net = round(qty_bill - qty_prev, 2)
            amt_net = round(qty_net * rate, 2)
            excess = round(max(0.0, qty_bill - qty_est), 2)

            ws_det.cell(row=out_row, column=1, value="")
            ws_det.cell(row=out_row, column=2, value=desc).alignment = Alignment(horizontal="left", vertical="top", wrap_text=True)
            ws_det.cell(row=out_row, column=3, value=round(qty_est, 2))
            ws_det.cell(row=out_row, column=4, value=round(rate, 2))
            ws_det.cell(row=out_row, column=5, value=f"=C{out_row}*D{out_row}")
            ws_det.cell(row=out_row, column=6, value=round(qty_prev, 2))
            ws_det.cell(row=out_row, column=7, value=round(qty_bill, 2))
            ws_det.cell(row=out_row, column=8, value=qty_net)
            ws_det.cell(row=out_row, column=9, value=amt_net)
            remark = ""
            if excess > 0:
                remark = "Excess as per estimated"
            elif qty_bill == 0:
                remark = "Deleted"
            elif 0 < qty_bill < qty_est:
                remark = "Less as per estimated"
            ws_det.cell(row=out_row, column=10, value=remark)
            for c_idx in range(1, len(det_headers) + 1):
                ws_det.cell(row=out_row, column=c_idx).border = border_all
            grand_det_amt += amt_net
            out_row += 1

            # AE row (per event) when qty_bill > qty_est
            if excess > 0:
                ae_counter += 1
                ae_desc = f"AE{ae_counter}"
                ws_det.cell(row=out_row, column=1, value="")
                ws_det.cell(row=out_row, column=2, value=ae_desc).alignment = Alignment(horizontal="left", vertical="top", wrap_text=True)
                ws_det.cell(row=out_row, column=3, value="")
                ws_det.cell(row=out_row, column=4, value=round(rate, 2))
                ws_det.cell(row=out_row, column=5, value="")
                ws_det.cell(row=out_row, column=6, value="")
                ws_det.cell(row=out_row, column=7, value=excess)
                ws_det.cell(row=out_row, column=8, value="")
                ws_det.cell(row=out_row, column=9, value=round(excess * rate, 2))
                ws_det.cell(row=out_row, column=10, value="Excess as per estimated")
                for c_idx in range(1, len(det_headers) + 1):
                    ws_det.cell(row=out_row, column=c_idx).border = border_all
                out_row += 1

        sl_counter += 1

    # Total row on detail sheet
    tot2 = ws_det.cell(row=out_row, column=8, value="Total")
    tot2.font = Font(bold=True)
    tot2.alignment = Alignment(horizontal="right", vertical="center")
    ws_det.cell(row=out_row, column=9, value=round(grand_det_amt, 2)).font = Font(bold=True)
    for c_idx in range(1, len(det_headers) + 1):
        ws_det.cell(row=out_row, column=c_idx).border = border_all

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    safe_name = re.sub(r"[^A-Za-z0-9_-]+", "_", work_name).strip("_") or "TempWorks"
    filename = f"{safe_name}_Bill_{bill_number}.xlsx"
    resp = HttpResponse(
        buf.getvalue(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    resp["Content-Disposition"] = f'attachment; filename="{filename}"'
    return resp
