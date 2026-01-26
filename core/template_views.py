# core/template_views.py
"""
Views for managing user document templates (Covering Letter, Movement Slip).
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, FileResponse
from django.views.decorators.http import require_POST, require_GET
import os

from core.models import UserDocumentTemplate


@login_required
def template_list_view(request):
    """List all user's document templates."""
    templates = UserDocumentTemplate.objects.filter(user=request.user)
    
    # Check which template types the user has
    covering_letter = templates.filter(template_type='covering_letter', is_active=True).first()
    movement_slip = templates.filter(template_type='movement_slip', is_active=True).first()
    
    context = {
        'templates': templates,
        'covering_letter': covering_letter,
        'movement_slip': movement_slip,
    }
    return render(request, 'core/template_list.html', context)


@login_required
def template_upload_view(request):
    """Upload a new document template."""
    if request.method == 'POST':
        template_type = request.POST.get('template_type')
        name = request.POST.get('name', '').strip()
        file = request.FILES.get('file')
        redirect_to = request.POST.get('next', '') or request.GET.get('next', '')
        
        # Determine redirect destination
        def get_redirect():
            if redirect_to == 'bill':
                return redirect('bill')
            return redirect('template_list')
        
        # Validation
        if not template_type or template_type not in ['covering_letter', 'movement_slip']:
            messages.error(request, 'Invalid template type.')
            return get_redirect()
        
        if not file:
            messages.error(request, 'Please select a file to upload.')
            return get_redirect()
        
        # Check file extension
        ext = os.path.splitext(file.name)[1].lower()
        if ext not in ['.docx', '.doc']:
            messages.error(request, 'Please upload a Word document (.docx or .doc).')
            return get_redirect()
        
        if not name:
            name = f"My {template_type.replace('_', ' ').title()}"
        
        # Create or update the template
        # Deactivate existing templates of this type
        UserDocumentTemplate.objects.filter(
            user=request.user,
            template_type=template_type
        ).update(is_active=False)
        
        # Create new template
        template = UserDocumentTemplate.objects.create(
            user=request.user,
            template_type=template_type,
            name=name,
            file=file,
            is_active=True
        )
        
        type_display = template.get_template_type_display()
        messages.success(request, f'{type_display} template uploaded!')
        return get_redirect()
    
    # GET request - show upload form
    template_type = request.GET.get('type', 'covering_letter')
    context = {
        'template_type': template_type,
        'template_types': UserDocumentTemplate.TEMPLATE_TYPE_CHOICES,
    }
    return render(request, 'core/template_upload.html', context)


@login_required
@require_POST
def template_delete_view(request, template_id):
    """Delete a document template."""
    template = get_object_or_404(UserDocumentTemplate, id=template_id, user=request.user)
    type_display = template.get_template_type_display()
    template.delete()
    messages.success(request, f'{type_display} template removed.')
    
    # Redirect back to bill page if coming from there
    next_page = request.GET.get('next', '') or request.POST.get('next', '')
    if next_page == 'bill':
        return redirect('bill')
    return redirect('template_list')


@login_required
@require_POST
def template_activate_view(request, template_id):
    """Set a template as the active one for its type."""
    template = get_object_or_404(UserDocumentTemplate, id=template_id, user=request.user)
    template.is_active = True
    template.save()  # save() method handles deactivating others
    messages.success(request, f'{template.name} is now the active template.')
    return redirect('template_list')


@login_required
@require_GET
def template_download_view(request, template_id):
    """Download a template file."""
    template = get_object_or_404(UserDocumentTemplate, id=template_id, user=request.user)
    return FileResponse(template.file.open('rb'), as_attachment=True, filename=os.path.basename(template.file.name))


def get_user_template(user, template_type):
    """
    Helper function to get a user's active template for a given type.
    Returns None if no template is uploaded.
    """
    return UserDocumentTemplate.objects.filter(
        user=user,
        template_type=template_type,
        is_active=True
    ).first()
