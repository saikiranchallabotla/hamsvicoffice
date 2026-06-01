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
from core.dwg.excel import build_takeoff_workbook
from core.dwg.takeoff import run_takeoff, zone_names
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
        for block_name, info in list(legend_map.items()):
            desc_field = f"desc__{block_name}"
            include_field = f"include__{block_name}"
            new_desc = request.POST.get(desc_field, info.get("desc", "")).strip()
            legend_map[block_name] = {
                **info,
                "desc": new_desc or block_name,
                "included": include_field in request.POST,
            }
        t.legend_map = legend_map
        t.status = "generating"
        t.save(update_fields=["legend_map", "status", "updated_at"])

        # Run takeoff synchronously (counting is fast once parsing is done).
        try:
            if not t.dxf_file:
                raise RuntimeError("DXF file missing; re-upload required.")
            local_path = t.dxf_file.path if hasattr(t.dxf_file, "path") else None
            if not local_path or not os.path.exists(local_path):
                # Storage may be remote — stage to a temp file.
                import tempfile
                with t.dxf_file.open("rb") as fh:
                    data = fh.read()
                tmp = tempfile.NamedTemporaryFile(suffix=".dxf", delete=False)
                tmp.write(data)
                tmp.close()
                local_path = tmp.name

            summary = run_takeoff(local_path, legend_map, t.zone_meta or [])
            xlsx_bytes = build_takeoff_workbook(t.name, summary, zone_names(t.zone_meta or []))
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


@login_required
def result_view(request, pk: int):
    t = get_object_or_404(_scoped(request), pk=pk)
    if t.status != "ready":
        return redirect("dwg_review", pk=pk)
    rows = sorted(
        (
            {"desc": desc, "total": sum(int(v) for v in (counts or {}).values())}
            for desc, counts in (t.summary or {}).items()
        ),
        key=lambda r: r["desc"].lower(),
    )
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
        "blocks": len(t.legend_map or {}),
        "zones": len(t.zone_meta or []),
    })


@login_required
@require_POST
def delete_view(request, pk: int):
    t = get_object_or_404(_scoped(request), pk=pk)
    t.delete()
    messages.success(request, "Takeoff deleted.")
    return redirect("dwg_upload")
