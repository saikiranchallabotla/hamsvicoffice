# Auto-generated from core/views.py split
import json
import os
import re
import logging
from copy import copy

import inflect
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Font, Border, Side, PatternFill
from django.utils import timezone
from django.urls import reverse
from django.core.files.uploadedfile import InMemoryUploadedFile
from django.contrib.auth.decorators import login_required

from django.conf import settings
from django.http import HttpResponse, JsonResponse, HttpResponseNotAllowed
from django.shortcuts import render, redirect, get_object_or_404
from django.template.loader import render_to_string
from django.views.decorators.http import require_POST
from django.utils.crypto import get_random_string

import io
from io import BytesIO
from difflib import SequenceMatcher

from ..models import Project, SelfFormattedTemplate, Estimate, Organization, Membership, Upload, Job, OutputFile, LetterSettings
from ..decorators import org_required, role_required

logger = logging.getLogger(__name__)
from ..tasks import process_excel_upload, generate_bill_pdf, generate_workslip_pdf, generate_bill_document_task
from ..utils_excel import load_backend, copy_block_with_styles_and_formulas, build_temp_day_rates

p_engine = inflect.engine()
BILL_TEMPLATES_DIR = os.path.join(settings.BASE_DIR, "core", "templates", "core", "bill_templates")
_inflect_engine = inflect.engine()

from .utils import get_org_from_request
from .self_formatted_views import (_extract_labels_from_source_file,
    _build_placeholder_map, _fill_template_file,
    _replace_placeholders_in_docx_xml)

@login_required(login_url='login')
def self_formatted_form_page(request):
    """
    Shows:
      - Quick one-time generation form
      - Create reusable format form
      - List of saved formats (with lock status)
    Optimized: Limited query with only necessary fields for faster load.
    """
    # Only fetch the current user's formats (not other users')
    saved_formats = SelfFormattedTemplate.objects.filter(
        user=request.user
    ).only(
        'id', 'name', 'created_at', 'is_locked', 'template_file_size'
    ).order_by("-created_at")[:20]
    error_message = request.GET.get("error")  # optional error via redirect
    success_message = request.GET.get("success")  # optional success message

    return render(request, "core/self_formatted.html", {
        "saved_formats": saved_formats,
        "error_message": error_message,
        "success_message": success_message,
    })


@login_required(login_url='login')
def self_formatted_generate(request):
    """
    Quick one-time generation: user uploads source + template, optional
    custom placeholders text. Does not save anything in DB.
    Optimized: No database queries during file processing for speed.
    """
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    source_file = request.FILES.get("source_file")
    template_file = request.FILES.get("template_file")
    custom_text = request.POST.get("custom_placeholders", "")

    # On error, redirect with error message instead of querying DB
    if not source_file or not template_file:
        return redirect(f"{reverse('self_formatted_form_page')}?error=Please+upload+both+source+file+and+template+file")

    labels, lines = _extract_labels_from_source_file(source_file)
    
    # Check if no text was extracted (likely scanned PDF)
    if not lines:
        filename = source_file.name or ""
        if filename.lower().endswith('.pdf'):
            error_msg = "PDF+appears+to+be+scanned.+Use+Excel+or+Word+file+instead."
        else:
            error_msg = "No+text+could+be+extracted+from+the+source+file."
        return redirect(f"{reverse('self_formatted_form_page')}?error={error_msg}")
    
    placeholder_map = _build_placeholder_map(labels, lines, custom_text)

    return _fill_template_file(template_file, placeholder_map)


@login_required(login_url='login')
def self_formatted_preview(request):
    """AJAX endpoint: compute placeholder_map for a given source file + custom text and return JSON.
    Used by the UI to preview mappings before generation.
    Uses faster/lighter OCR settings for quicker preview response.
    """
    from django.http import JsonResponse
    import logging
    logger = logging.getLogger(__name__)

    if request.method != "POST":
        return JsonResponse({"error": "POST required"}, status=405)

    source_file = request.FILES.get("source_file")
    custom_text = request.POST.get("custom_placeholders", "")

    if not source_file:
        return JsonResponse({"error": "source_file required"}, status=400)

    try:
        logger.info(f"Preview: Processing {source_file.name}")
        labels, lines = _extract_labels_from_source_file(source_file)
        
        # Check if no text was extracted
        if not lines:
            filename = source_file.name or ""
            if filename.lower().endswith('.pdf'):
                return JsonResponse({
                    "error": "No text extracted. This appears to be a scanned PDF. Use Excel/Word file or install Tesseract OCR."
                }, status=400)
            return JsonResponse({"error": "No text could be extracted from the file."}, status=400)
        
        logger.info(f"Preview: Extracted {len(lines)} lines, building placeholders...")
        placeholder_map = _build_placeholder_map(labels, lines, custom_text)
        logger.info(f"Preview: Found {len(placeholder_map)} placeholders")
    except Exception as e:
        logger.error(f"Preview error: {e}")
        return JsonResponse({"error": str(e)}, status=500)

    return JsonResponse({"placeholders": placeholder_map})


@org_required
def self_formatted_save_format(request):
    """
    Save a reusable format (name + description + template file + custom placeholders).
    Automatically creates a database backup of the template for maximum persistence.
    Optimized: Redirect with error instead of querying DB.
    """
    if request.method != "POST":
        return redirect("self_formatted_form_page")

    format_name = request.POST.get("format_name", "").strip()
    format_description = request.POST.get("format_description", "").strip()
    template_file = request.FILES.get("format_template_file")
    raw_custom = request.POST.get("format_custom_placeholders", "").strip()

    if not format_name or not template_file:
        return redirect(f"{reverse('self_formatted_form_page')}?error=Format+name+and+template+file+are+required")

    # Read the template file content for backup before save
    template_file.seek(0)
    template_content = template_file.read()
    template_file.seek(0)  # Reset for FileField save

    fmt = SelfFormattedTemplate(
        name=format_name,
        description=format_description,
        template_file=template_file,
        custom_placeholders=raw_custom,
        user=request.user,
        organization=request.organization,
        is_locked=True,  # New formats are locked by default
        template_file_backup=template_content,
        template_file_name=template_file.name,
        template_file_size=len(template_content),
    )
    fmt.save()

    return redirect("self_formatted_form_page")


@org_required
def self_formatted_use_format(request, pk):
    """
    Use a saved format:
      GET  -> show page asking only for source_file upload.
      POST -> generate document using saved template + placeholders.
    """
    fmt = get_object_or_404(SelfFormattedTemplate, pk=pk, user=request.user)

    if request.method == "GET":
        return render(request, "core/self_formatted_use.html", {
            "format": fmt,
        })

    if request.method == "POST":
        source_file = request.FILES.get("source_file")
        if not source_file:
            return HttpResponse("Please upload a source file.", status=400)

        labels, lines = _extract_labels_from_source_file(source_file)
        placeholder_source = fmt.custom_placeholders or ""
        placeholder_map = _build_placeholder_map(labels, lines, placeholder_source)

        # Use the new get_template_content method which falls back to backup
        data = fmt.get_template_content()
        
        if not data:
            # Template file was not found in file storage OR database backup
            return redirect(
                f"{reverse('self_formatted_form_page')}?error="
                "Template file not found. The template may have been corrupted. "
                "Please re-create this format."
            )

        mem = io.BytesIO(data)
        uploaded = InMemoryUploadedFile(
            mem,
            field_name="template_file",
            name=os.path.basename(fmt.template_file.name),
            content_type="application/octet-stream",
            size=len(data),
            charset=None,
        )
        return _fill_template_file(uploaded, placeholder_map)

    return HttpResponseNotAllowed(["GET", "POST"])


@org_required
def self_formatted_delete_format(request, pk):
    """
    Delete a saved format (and its underlying template file).
    Respects is_locked flag - locked templates require explicit unlock first.
    """
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    fmt = get_object_or_404(SelfFormattedTemplate, pk=pk, user=request.user)
    
    # Check if format is locked
    if fmt.is_locked:
        # Check for unlock confirmation in request
        confirm_delete = request.POST.get('confirm_delete', '').lower()
        if confirm_delete != 'yes':
            return redirect(
                f"{reverse('self_formatted_form_page')}?error="
                "Format is locked. Click the lock icon to unlock before deleting."
            )

    template = fmt.template_file
    storage = template.storage if template else None
    name = template.name if template else None

    fmt.delete()

    if storage and name and storage.exists(name):
        storage.delete(name)

    return redirect("self_formatted_form_page")


@org_required
def self_formatted_edit_format(request, pk):
    """Edit an existing SelfFormattedTemplate.
    GET: show edit form
    POST: apply updates (name, description, optional new template file, custom placeholders)
    """
    fmt = get_object_or_404(SelfFormattedTemplate, pk=pk, user=request.user)

    if request.method == "GET":
        preview_text = None
        template_url = None
        try:
            if fmt.template_file and fmt.template_file.name:
                template_url = fmt.template_file.url
                # attempt lightweight preview depending on extension
                name = fmt.template_file.name.lower()
                with fmt.template_file.open('rb') as f:
                    data = f.read()

                if name.endswith('.txt') or name.endswith('.csv'):
                    preview_text = data.decode('utf-8', errors='replace')[:4000]
                elif name.endswith('.docx'):
                    try:
                        from docx import Document
                        mem = io.BytesIO(data)
                        doc = Document(mem)
                        paras = [p.text for p in doc.paragraphs if p.text]
                        preview_text = '\n'.join(paras)[:4000]
                    except Exception:
                        preview_text = None
                elif name.endswith('.pdf'):
                    try:
                        from PyPDF2 import PdfReader
                        mem = io.BytesIO(data)
                        reader = PdfReader(mem)
                        text_parts = []
                        if reader.pages:
                            text_parts.append(reader.pages[0].extract_text() or '')
                        preview_text = '\n'.join(text_parts)[:4000]
                    except Exception:
                        preview_text = None
                elif name.endswith('.xlsx') or name.endswith('.xlsm'):
                    try:
                        from openpyxl import load_workbook
                        mem = io.BytesIO(data)
                        wb = load_workbook(mem, read_only=True, data_only=True)
                        sheet = wb.active
                        rows = []
                        for r in sheet.iter_rows(min_row=1, max_row=8, max_col=6, values_only=True):
                            rows.append('\t'.join([str(c) if c is not None else '' for c in r]))
                        preview_text = '\n'.join(rows)
                    except Exception:
                        preview_text = None
        except Exception:
            preview_text = None

        return render(request, "core/self_formatted_edit.html", {
            "format": fmt,
            "preview_text": preview_text,
            "template_url": template_url,
        })

    # POST
    name = request.POST.get("format_name", "").strip()
    description = request.POST.get("format_description", "").strip()
    raw_custom = request.POST.get("format_custom_placeholders", "").strip()
    new_template = request.FILES.get("format_template_file")

    if not name:
        return render(request, "core/self_formatted_edit.html", {
            "format": fmt,
            "error_message": "Name is required.",
        }, status=400)

    # Replace template file if new file provided
    old_name = None
    storage = None
    if new_template:
        if fmt.template_file and fmt.template_file.name:
            old_name = fmt.template_file.name
            storage = fmt.template_file.storage
        fmt.template_file = new_template
        # Update backup with new template content
        new_template.seek(0)
        fmt.template_file_backup = new_template.read()
        fmt.template_file_name = new_template.name
        fmt.template_file_size = len(fmt.template_file_backup)
        new_template.seek(0)

    fmt.name = name
    fmt.description = description
    fmt.custom_placeholders = raw_custom
    fmt.save()

    # delete old template file from storage after saving new one
    try:
        if old_name and storage and storage.exists(old_name):
            storage.delete(old_name)
    except Exception:
        pass

    return redirect("self_formatted_form_page")


@org_required
@require_POST
def self_formatted_toggle_lock(request, pk):
    """
    Toggle the lock status of a saved format.
    Locked formats require extra confirmation to delete.
    Returns JSON response for AJAX calls.
    """
    fmt = get_object_or_404(SelfFormattedTemplate, pk=pk, user=request.user)
    fmt.is_locked = not fmt.is_locked
    fmt.save(update_fields=['is_locked'])
    
    return JsonResponse({
        'success': True,
        'is_locked': fmt.is_locked,
        'message': f"Format {'locked' if fmt.is_locked else 'unlocked'} successfully"
    })


@org_required
@require_POST
def self_formatted_restore_backup(request, pk):
    """
    Restore a format's template file from database backup.
    Used when file storage fails but backup exists.
    """
    fmt = get_object_or_404(SelfFormattedTemplate, pk=pk, user=request.user)
    
    if not fmt.template_file_backup:
        return JsonResponse({
            'success': False,
            'message': 'No backup available for this format'
        }, status=400)
    
    success = fmt.restore_from_backup()
    
    if success:
        return JsonResponse({
            'success': True,
            'message': 'Template restored from backup successfully'
        })
    else:
        return JsonResponse({
            'success': False,
            'message': 'Failed to restore template from backup'
        }, status=500)


# ==========================
#  TEMPORARY WORKS MODULE
#  (completely separate from New Estimate)
# ==========================


