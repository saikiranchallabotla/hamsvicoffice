"""DWG/DXF takeoff views: upload, mapping review, Excel generation/download."""
from __future__ import annotations

import os

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.files.base import ContentFile
from django.http import HttpResponse, JsonResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_POST

from core.models import DwgTakeoff
from core.dwg.excel import build_takeoff_workbook, build_takeoff_workbook_multi
from core.dwg.takeoff import run_takeoff, run_takeoff_per_layout, zone_names
from core.dwg.linear import run_linear_takeoff_per_layout
from core.tasks import parse_dwg_takeoff


ALLOWED_EXT = {".dwg", ".dxf"}
MAX_BYTES = 100 * 1024 * 1024  # 100 MB


def _user_org(request):
    return getattr(request, "organization", None) or getattr(request.user, "organization", None)


def _scoped(request):
    org = _user_org(request)
    qs = DwgTakeoff.objects.filter(user=request.user)
    if org is not None:
        qs = qs.filter(organization=org)
    return qs


@login_required
def upload_view(request):
    if request.method == "POST":
        f = request.FILES.get("file")
        if not f:
            messages.error(request, "Please choose a .dwg or .dxf file.")
            return redirect("dwg_upload")
        ext = os.path.splitext(f.name)[1].lower()
        if ext not in ALLOWED_EXT:
            messages.error(request, "Only .dwg and .dxf files are supported.")
            return redirect("dwg_upload")
        if f.size > MAX_BYTES:
            messages.error(request, "File exceeds 100 MB limit.")
            return redirect("dwg_upload")

        org = _user_org(request)
        if org is None:
            messages.error(request, "Your account is not attached to an organization.")
            return redirect("dashboard")

        t = DwgTakeoff.objects.create(
            organization=org,
            user=request.user,
            name=os.path.splitext(f.name)[0][:255],
            source_file=f,
            source_format="dwg" if ext == ".dwg" else "dxf",
            status="pending",
        )
        # Trigger async parsing (runs eagerly in dev when CELERY_TASK_ALWAYS_EAGER).
        parse_dwg_takeoff.delay(t.id)
        return redirect("dwg_review", pk=t.id)

    recent = _scoped(request).order_by("-created_at")[:20]
    return render(request, "core/dwg/upload.html", {"recent": recent})


@login_required
def review_view(request, pk: int):
    t = get_object_or_404(_scoped(request), pk=pk)

    if request.method == "POST":
        if t.status not in ("needs_review", "ready"):
            messages.error(request, "Takeoff is not ready for review yet.")
            return redirect("dwg_review", pk=pk)

        legend_map = dict(t.legend_map or {})
        layer_filter: dict = {}
        for block_name, info in list(legend_map.items()):
            desc_field = f"desc__{block_name}"
            include_field = f"include__{block_name}"
            new_desc = request.POST.get(desc_field, info.get("desc", "")).strip()
            legend_map[block_name] = {
                **info,
                "desc": new_desc or block_name,
                "included": include_field in request.POST,
            }
            # Per-block layer checkboxes: name="layer__<block>" multiple values.
            allowed_layers = request.POST.getlist(f"layer__{block_name}")
            block_layers = list((info.get("layers") or {}).keys())
            # Only persist a filter if user actually narrowed it (otherwise keep
            # the block on all layers it appears on).
            if block_layers and 0 < len(allowed_layers) < len(block_layers):
                layer_filter[block_name] = allowed_layers
        t.legend_map = legend_map
        t.layer_filter = layer_filter
        # Pipe (linear) mapping: `pipe_layer__<layer>` -> description; empty
        # means "not a pipe" and is skipped during takeoff.
        linear_mapping: dict = {}
        for layer in list((t.linear_by_layer or {}).keys()):
            val = (request.POST.get(f"pipe_layer__{layer}") or "").strip()
            if val:
                linear_mapping[layer] = val
        t.linear_mapping = linear_mapping
        try:
            t.unit_scale = float(request.POST.get("unit_scale") or 1.0)
        except (TypeError, ValueError):
            t.unit_scale = 1.0
        include_paper = request.POST.get("include_paper_space") == "on"
        split_by_layout = request.POST.get("split_by_layout") == "on"
        t.status = "generating"
        t.save(update_fields=["legend_map", "layer_filter", "linear_mapping",
                              "unit_scale", "status", "updated_at"])

        try:
            inserts = _load_inserts(t)
            viewports = (t.viewports or {}) if split_by_layout else None
            per_sheet = run_takeoff_per_layout(
                inserts,
                legend_map,
                t.zone_meta or [],
                legend_bbox=t.legend_bbox,
                layer_filter=layer_filter,
                include_paper_space=include_paper,
                viewports=viewports,
            )
            # Merge linear (pipe) takeoff into the same per-sheet pivot so
            # pipes show up as a "Pipes" category under each floor.
            if linear_mapping:
                linear_records = _load_linear(t)
                per_sheet_pipes = run_linear_takeoff_per_layout(
                    linear_records,
                    linear_mapping,
                    t.zone_meta or [],
                    legend_bbox=t.legend_bbox,
                    unit_scale=float(t.unit_scale or 1.0),
                    viewports=viewports,
                )
                for sheet_name, pivot in per_sheet_pipes.items():
                    target = per_sheet.setdefault(sheet_name, {})
                    for key, zd in pivot.items():
                        bucket = target.setdefault(key, {})
                        for z, n in zd.items():
                            bucket[z] = float(bucket.get(z, 0)) + float(n)
            zones = zone_names(t.zone_meta or [])
            if split_by_layout and viewports:
                xlsx_bytes = build_takeoff_workbook_multi(t.name, per_sheet, zones)
                summary: dict = {}
                for pivot in per_sheet.values():
                    for key, zd in pivot.items():
                        bucket = summary.setdefault(key, {})
                        for z, n in zd.items():
                            bucket[z] = float(bucket.get(z, 0)) + float(n)
            else:
                summary = per_sheet.get("All", {})
                xlsx_bytes = build_takeoff_workbook(t.name, summary, zones)
            t.result_file.save(
                f"{t.name}_takeoff.xlsx",
                ContentFile(xlsx_bytes),
                save=False,
            )
            t.summary = summary
            t.status = "ready"
            t.error = ""
            t.save()
            return redirect("dwg_result", pk=pk)
        except Exception as e:
            t.status = "failed"
            t.error = f"Takeoff failed: {e}"
            t.save(update_fields=["status", "error", "updated_at"])
            messages.error(request, t.error)
            return redirect("dwg_review", pk=pk)

    return render(request, "core/dwg/review.html", {"t": t})


def _load_inserts(t: DwgTakeoff) -> list:
    """Load the cached inserts JSON; fall back to re-parsing the DXF."""
    import json
    if t.inserts_cache:
        try:
            with t.inserts_cache.open("rb") as fh:
                return json.loads(fh.read().decode("utf-8"))
        except Exception:
            pass
    # Fallback: re-open the DXF.
    if not t.dxf_file:
        raise RuntimeError("Cached inserts missing and no DXF available; please re-upload.")
    from core.dwg.parser import parse_dxf
    local_path = t.dxf_file.path if hasattr(t.dxf_file, "path") else None
    if not local_path or not os.path.exists(local_path):
        import tempfile
        with t.dxf_file.open("rb") as fh:
            data = fh.read()
        tmp = tempfile.NamedTemporaryFile(suffix=".dxf", delete=False)
        tmp.write(data)
        tmp.close()
        local_path = tmp.name
    result = parse_dxf(local_path)
    return result.get("inserts", [])


def _load_linear(t: DwgTakeoff) -> list:
    """Load the cached linear records JSON; empty list if none."""
    import json
    if t.linear_cache:
        try:
            with t.linear_cache.open("rb") as fh:
                return json.loads(fh.read().decode("utf-8"))
        except Exception:
            pass
    return []


@login_required
def result_view(request, pk: int):
    t = get_object_or_404(_scoped(request), pk=pk)
    if t.status != "ready":
        return redirect("dwg_review", pk=pk)
    from core.dwg.takeoff import split_key
    rows = []
    for key, counts in (t.summary or {}).items():
        group, desc = split_key(key)
        total = sum(float(v) for v in (counts or {}).values())
        rows.append({
            "group": group,
            "desc": desc,
            "total": int(total) if total == int(total) else round(total, 3),
        })
    rows.sort(key=lambda r: (r["group"].lower(), r["desc"].lower()))
    return render(request, "core/dwg/result.html", {
        "t": t,
        "zones": zone_names(t.zone_meta or []),
        "rows": rows,
    })


@login_required
def download_view(request, pk: int):
    t = get_object_or_404(_scoped(request), pk=pk)
    if not t.result_file:
        raise Http404("Result file not generated yet.")
    with t.result_file.open("rb") as fh:
        data = fh.read()
    resp = HttpResponse(
        data,
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    fname = os.path.basename(t.result_file.name) or f"{t.name}.xlsx"
    resp["Content-Disposition"] = f'attachment; filename="{fname}"'
    return resp


@login_required
@require_GET
def status_view(request, pk: int):
    t = get_object_or_404(_scoped(request), pk=pk)
    return JsonResponse({
        "status": t.status,
        "error": t.error,
        "progress": t.progress,
        "step": t.current_step,
        "blocks": len(t.legend_map or {}),
        "zones": len(t.zone_meta or []),
        "warnings": t.warnings or [],
    })


@login_required
@require_POST
def delete_view(request, pk: int):
    t = get_object_or_404(_scoped(request), pk=pk)
    t.delete()
    messages.success(request, "Takeoff deleted.")
    return redirect("dwg_upload")
