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

from .utils import _get_letter_settings

def home(request):
    """Home page - shows login/register for guests, modules for authenticated users"""
    if not request.user.is_authenticated:
        # Show landing page with login/register options
        return render(request, "core/landing.html")
    try:
        return render(request, "core/home.html")
    except Exception:
        return HttpResponse("Home page temporarily unavailable.")


@login_required(login_url='login')
def letter_settings(request):
    """
    Letter Settings page - allows users to save their organization/officer details
    for use in forwarding letters and other documents.
    """
    # Get or create letter settings for the user
    settings_obj, created = LetterSettings.objects.get_or_create(user=request.user)
    
    if request.method == 'POST':
        # Update settings from form data
        settings_obj.government_name = request.POST.get('government_name', '').strip()
        settings_obj.department_name = request.POST.get('department_name', '').strip()
        settings_obj.officer_name = request.POST.get('officer_name', '').strip()
        settings_obj.officer_qualification = request.POST.get('officer_qualification', '').strip()
        settings_obj.officer_designation = request.POST.get('officer_designation', '').strip()
        settings_obj.sub_division = request.POST.get('sub_division', '').strip()
        settings_obj.office_address = request.POST.get('office_address', '').strip()
        settings_obj.recipient_designation = request.POST.get('recipient_designation', '').strip()
        settings_obj.recipient_division = request.POST.get('recipient_division', '').strip()
        settings_obj.recipient_address = request.POST.get('recipient_address', '').strip()
        settings_obj.office_code = request.POST.get('office_code', '').strip()
        settings_obj.superior_designation = request.POST.get('superior_designation', '').strip()
        settings_obj.copy_to_designation = request.POST.get('copy_to_designation', '').strip()
        settings_obj.copy_to_section = request.POST.get('copy_to_section', '').strip()
        settings_obj.save()
        
        from django.contrib import messages
        messages.success(request, 'Letter settings saved successfully!')
        return redirect('letter_settings')
    
    return render(request, 'core/letter_settings.html', {
        'settings': settings_obj
    })


@login_required(login_url='login')
def workslip_home(request):
    """
    Landing page for Workslip module:
    - Step 1: Select work type (New Estimate / AMC / Temporary Works)
    - Step 2: Select work mode (Original / Repair)
    - Step 3: Select category (Electrical / Civil)
    Then redirect to workslip main page with parameters
    """
    return render(request, "core/workslip_home.html")


