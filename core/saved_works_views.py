# core/saved_works_views.py
"""
Views for the Saved Works feature.
Allows users to save their work-in-progress and resume later.
"""

import json
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST, require_GET
from django.http import JsonResponse
from django.contrib import messages
from django.db.models import Q
from django.utils import timezone
from django.urls import reverse

from .models import SavedWork, WorkFolder, Organization, Membership
from .decorators import org_required


# ==============================================================================
# SUBSCRIPTION ACCESS CONTROL FOR SAVED WORKS
# ==============================================================================

# Mapping from work_type to module_code for subscription checks
WORK_TYPE_TO_MODULE = {
    'new_estimate': 'new_estimate',
    'temporary_works': 'temp_works',
    'amc': 'amc',
    'workslip': 'workslip',
    'bill': 'bill',
}


def check_saved_work_access(user, saved_work):
    """
    Check if user has active subscription to access a saved work.
    
    Args:
        user: Django User object
        saved_work: SavedWork instance
        
    Returns:
        dict: {ok: bool, reason: str, module_code: str}
    """
    # Staff/superusers always have access
    if user.is_staff or user.is_superuser:
        return {'ok': True, 'reason': 'Admin access', 'module_code': None}
    
    work_type = saved_work.work_type
    module_code = WORK_TYPE_TO_MODULE.get(work_type)
    
    if not module_code:
        # Unknown work type - allow access (fallback)
        return {'ok': True, 'reason': 'No module restriction', 'module_code': None}
    
    try:
        from subscriptions.services import SubscriptionService
        result = SubscriptionService.check_access(user, module_code)
        return {
            'ok': result.get('ok', False),
            'reason': result.get('reason', 'Access denied'),
            'module_code': module_code,
            'data': result.get('data', {})
        }
    except Exception as e:
        # If subscription service fails, deny access for safety
        import logging
        logging.error(f"Subscription check failed for saved work: {e}")
        return {
            'ok': False, 
            'reason': 'Unable to verify subscription. Please try again.',
            'module_code': module_code
        }


def get_org_from_request(request):
    """Get organization from request, creating default if needed."""
    if hasattr(request, 'organization') and request.organization:
        return request.organization
    
    if request.user.is_authenticated:
        from django.utils.text import slugify
        
        membership = Membership.objects.filter(user=request.user).select_related('organization').first()
        
        if membership:
            request.organization = membership.organization
            return membership.organization
        
        org_name = f"{request.user.username}'s Organization"
        org_slug = slugify(org_name)[:255]
        
        base_slug = org_slug
        counter = 1
        while Organization.objects.filter(slug=org_slug).exists():
            org_slug = f"{base_slug}-{counter}"
            counter += 1
        
        org, created = Organization.objects.get_or_create(
            name=org_name,
            defaults={
                'slug': org_slug,
                'owner': request.user,
                'is_active': True
            }
        )
        
        Membership.objects.get_or_create(
            user=request.user,
            organization=org,
            defaults={'role': 'owner'}
        )
        
        request.organization = org
        return org
    
    from django.http import Http404
    raise Http404("Please login to continue.")


# ==============================================================================
# SAVED WORKS LIST & MANAGEMENT
# ==============================================================================

@login_required(login_url='login')
def saved_works_list(request):
    """List all saved works with folder structure."""
    org = get_org_from_request(request)
    user = request.user
    
    # Get filter parameters
    work_type_filter = request.GET.get('type', 'all')
    folder_id = request.GET.get('folder')
    search_query = request.GET.get('q', '').strip()
    status_filter = request.GET.get('status', 'all')
    
    # Get current folder if viewing inside a folder
    current_folder = None
    if folder_id and folder_id != 'unfiled':
        current_folder = get_object_or_404(WorkFolder, id=folder_id, organization=org, user=user)
    
    # Get folders to display (root folders or subfolders of current folder)
    if current_folder:
        folders = WorkFolder.objects.filter(organization=org, user=user, parent=current_folder)
    else:
        folders = WorkFolder.objects.filter(organization=org, user=user, parent__isnull=True)
    
    # Get saved works
    works = SavedWork.objects.filter(organization=org, user=user)
    
    # Fix orphan workslips/bills: link them to their parent estimate
    # This handles works created before parent-linking was implemented
    orphan_children = works.filter(
        parent__isnull=True,
        work_type__in=['workslip', 'bill'],
    )
    for oc in orphan_children:
        wd = oc.work_data or {}
        if oc.work_type == 'workslip':
            # For workslips, link to the source estimate
            src_id = wd.get('ws_source_estimate_id')
            if src_id:
                try:
                    parent_work = SavedWork.objects.get(id=int(src_id), organization=org, user=user)
                    # Walk up to root estimate
                    root = parent_work
                    while root and root.work_type not in ('new_estimate', 'temporary_works', 'amc') and root.parent:
                        root = root.parent
                    if root and root.work_type in ('new_estimate', 'temporary_works', 'amc'):
                        oc.parent = root
                        oc.save(update_fields=['parent'])
                except SavedWork.DoesNotExist:
                    pass
        elif oc.work_type == 'bill':
            # For bills, try to link to the source workslip first, then estimate
            bill_parent_id = wd.get('bill_parent_work_id') or wd.get('bill_source_work_id')
            if bill_parent_id:
                try:
                    bill_parent = SavedWork.objects.get(id=int(bill_parent_id), organization=org, user=user)
                    oc.parent = bill_parent
                    oc.save(update_fields=['parent'])
                except SavedWork.DoesNotExist:
                    # Fallback: try ws_source_estimate_id
                    src_id = wd.get('ws_source_estimate_id')
                    if src_id:
                        try:
                            root = SavedWork.objects.get(id=int(src_id), organization=org, user=user)
                            oc.parent = root
                            oc.save(update_fields=['parent'])
                        except SavedWork.DoesNotExist:
                            pass

    # Re-fetch works after fixing orphans
    works = SavedWork.objects.filter(organization=org, user=user)

    # Hide child works (workslips/bills with a parent) from the list.
    # They are accessible through the parent estimate's detail page.
    works = works.filter(parent__isnull=True)
    
    # Apply filters
    if work_type_filter != 'all':
        works = works.filter(work_type=work_type_filter)
    
    if folder_id:
        if folder_id == 'unfiled':
            works = works.filter(folder__isnull=True)
        else:
            works = works.filter(folder_id=folder_id)
    else:
        # At root, show only unfiled works
        works = works.filter(folder__isnull=True)
    
    if status_filter != 'all':
        works = works.filter(status=status_filter)
    
    if search_query:
        works = works.filter(Q(name__icontains=search_query) | Q(notes__icontains=search_query))
    
    # Build breadcrumb path for nested folders
    breadcrumb_path = []
    if current_folder:
        folder = current_folder
        while folder:
            breadcrumb_path.insert(0, folder)
            folder = folder.parent
    
    # Get all folders for the dropdown/tree
    all_folders = WorkFolder.objects.filter(organization=org, user=user)
    
    # Check module access for each work type
    # Mapping: work_type -> module_code
    work_type_to_module = {
        'new_estimate': 'new_estimate',
        'temporary_works': 'temp_works',
        'amc': 'amc',
        'workslip': 'workslip',
        'bill': 'bill',
    }

    module_access = {}
    try:
        from subscriptions.services import SubscriptionService
        for work_type, module_code in work_type_to_module.items():
            result = SubscriptionService.check_access(user, module_code)
            module_access[work_type] = result.get('ok', False)
        # Also check workslip access for the generate workslip button
        workslip_result = SubscriptionService.check_access(user, 'workslip')
        module_access['can_generate_workslip'] = workslip_result.get('ok', False)
        # Check bill access
        bill_result = SubscriptionService.check_access(user, 'bill')
        module_access['can_generate_bill'] = bill_result.get('ok', False)
    except Exception:
        # If subscription service fails, allow access (fallback)
        for work_type in work_type_to_module.keys():
            module_access[work_type] = True
        module_access['can_generate_workslip'] = True
        module_access['can_generate_bill'] = True

    # Evaluate queryset to list so we can attach workflow chain data
    works_list = list(works)

    # Build workflow chain data for ALL works in the current view.
    # Attach .wf_chain to each work object so the template can render
    # the full E/W/B navigation for every row.
    _chain_cache = {}  # Cache chains by root estimate id

    def _build_chain_for_estimate(est):
        """Build and cache the E/W/B chain for an estimate."""
        if est is None:
            return None
        if est.id in _chain_cache:
            return _chain_cache[est.id]
        ws_list = list(
            SavedWork.objects.filter(
                organization=org, user=user,
                work_type='workslip', parent=est,
            ).order_by('workslip_number')
        )
        ws_ids = [ws.id for ws in ws_list]
        bill_list = list(
            SavedWork.objects.filter(
                organization=org, user=user, work_type='bill',
            ).filter(
                Q(parent=est) | Q(parent_id__in=ws_ids)
            ).order_by('bill_number')
        )
        chain = {
            'estimate': est,
            'workslips': ws_list,
            'bills': bill_list,
        }
        _chain_cache[est.id] = chain
        return chain

    for work in works_list:
        # Build wf_chain for E/W/B navigation
        if work.work_type == 'new_estimate':
            work.wf_chain = _build_chain_for_estimate(work)
        elif work.work_type in ('workslip', 'bill'):
            root_est = None
            current = work.parent
            while current:
                if current.work_type == 'new_estimate':
                    root_est = current
                    break
                current = current.parent
            work.wf_chain = _build_chain_for_estimate(root_est)
        else:
            work.wf_chain = None

        # Also build workslip children data for dynamic W1, W2, W3... buttons
        if work.work_type in ('new_estimate', 'temporary_works', 'amc'):
            try:
                all_ws = work.get_all_workslips() if hasattr(work, 'get_all_workslips') else []
                work.workslip_children = all_ws
                work.next_ws_number = (max(ws.workslip_number for ws in all_ws) + 1) if all_ws else 1
                work.last_ws = all_ws[-1] if all_ws else None
                # Attach bill children from wf_chain
                work.bill_children = work.wf_chain.get('bills', []) if work.wf_chain else []
            except Exception:
                work.workslip_children = []
                work.next_ws_number = 1
                work.last_ws = None
                work.bill_children = []

        # Attach item_count for display
        wd = work.work_data or {}
        if work.work_type == 'new_estimate':
            work.item_count = len(wd.get('fetched_items', []))
        elif work.work_type == 'workslip':
            work.item_count = len(wd.get('ws_estimate_rows', []))
        elif work.work_type == 'bill':
            work.item_count = len(wd.get('bill_ws_rows', wd.get('ws_estimate_rows', [])))
        else:
            work.item_count = 0

        # Build sibling workslips for workslip cards
        if work.work_type == 'workslip':
            try:
                root = work.get_root_estimate() if hasattr(work, 'get_root_estimate') else None
                if root:
                    all_ws = root.get_all_workslips() if hasattr(root, 'get_all_workslips') else []
                    work.sibling_workslips = all_ws
                    work.root_estimate = root
                else:
                    work.sibling_workslips = []
                    work.root_estimate = None
            except Exception:
                work.sibling_workslips = []
                work.root_estimate = None
    
    context = {
        'works': works_list,
        'folders': folders,
        'all_folders': all_folders,
        'current_folder': current_folder,
        'breadcrumb_path': breadcrumb_path,
        'work_type_filter': work_type_filter,
        'status_filter': status_filter,
        'search_query': search_query,
        'work_type_choices': SavedWork.WORK_TYPE_CHOICES,
        'status_choices': SavedWork.STATUS_CHOICES,
        'module_access': module_access,
    }

    return render(request, 'core/saved_works/list.html', context)


@login_required(login_url='login')
@require_POST
def create_folder(request):
    """Create a new folder for organizing saved works."""
    org = get_org_from_request(request)
    user = request.user
    
    # Handle both form data and JSON
    if request.content_type and 'application/json' in request.content_type:
        import json
        data = json.loads(request.body.decode('utf-8'))
        name = data.get('name', '').strip()
        parent_id = data.get('parent_id')
        color = data.get('color', '#6366f1')
        description = data.get('description', '').strip()
    else:
        name = request.POST.get('name', '').strip()
        parent_id = request.POST.get('parent_id')
        color = request.POST.get('color', '#6366f1')
        description = request.POST.get('description', '').strip()
    
    if not name:
        return JsonResponse({'success': False, 'error': 'Folder name is required.'})
    
    parent = None
    if parent_id:
        parent = get_object_or_404(WorkFolder, id=parent_id, organization=org, user=user)
    
    # Check for duplicate name in same parent
    if WorkFolder.objects.filter(organization=org, user=user, name=name, parent=parent).exists():
        return JsonResponse({'success': False, 'error': 'A folder with this name already exists.'})
    
    folder = WorkFolder.objects.create(
        organization=org,
        user=user,
        name=name,
        parent=parent,
        color=color,
        description=description,
    )
    
    return JsonResponse({
        'success': True,
        'folder_id': folder.id,
        'folder_name': folder.name,
        'message': f'Folder "{name}" created successfully!'
    })


@login_required(login_url='login')
@require_POST
def rename_folder(request, folder_id):
    """Rename an existing folder."""
    org = get_org_from_request(request)
    user = request.user
    
    folder = get_object_or_404(WorkFolder, id=folder_id, organization=org, user=user)
    
    new_name = request.POST.get('name', '').strip()
    if not new_name:
        return JsonResponse({'success': False, 'error': 'Folder name is required.'})
    
    # Check for duplicate name in same parent
    if WorkFolder.objects.filter(
        organization=org, user=user, name=new_name, parent=folder.parent
    ).exclude(id=folder.id).exists():
        return JsonResponse({'success': False, 'error': 'A folder with this name already exists.'})
    
    folder.name = new_name
    folder.save()
    
    return JsonResponse({
        'success': True,
        'message': f'Folder renamed to "{new_name}"!'
    })


@login_required(login_url='login')
@require_POST
def delete_folder(request, folder_id):
    """Delete a folder and all its contents permanently."""
    from django.db import transaction
    
    org = get_org_from_request(request)
    user = request.user
    
    folder = get_object_or_404(WorkFolder, id=folder_id, organization=org, user=user)
    
    permanent = request.POST.get('permanent', 'false').lower() == 'true'
    
    folder_name = folder.name
    
    # Use transaction to ensure atomic deletion
    with transaction.atomic():
        if permanent:
            # Permanently delete all works and subfolders recursively
            def delete_folder_contents(f):
                # Delete all works in this folder
                f.saved_works.all().delete()
                # Recursively delete child folders
                for child in f.children.all():
                    delete_folder_contents(child)
                    child.delete()
            
            delete_folder_contents(folder)
        else:
            # Move saved works to parent folder or root
            folder.saved_works.update(folder=folder.parent)
            folder.children.update(parent=folder.parent)
        
        folder.delete()
    
    return JsonResponse({
        'success': True,
        'message': f'Folder "{folder_name}" deleted successfully!'
    })


# ==============================================================================
# SAVE WORK FUNCTIONALITY
# ==============================================================================

@login_required(login_url='login')
@require_POST
def save_work(request):
    """
    Save current work-in-progress.
    Called from any module (New Estimate, Workslip, Temporary Works, AMC).
    """
    org = get_org_from_request(request)
    user = request.user
    
    # Get work details from POST
    work_name = request.POST.get('work_name', '').strip()
    work_type = request.POST.get('work_type', '')
    folder_id = request.POST.get('folder_id')
    notes = request.POST.get('notes', '').strip()
    category = request.POST.get('category', 'electrical')
    work_id = request.POST.get('work_id')  # For updating existing saved work
    
    if not work_name:
        return JsonResponse({'success': False, 'error': 'Work name is required.'})
    
    if work_type not in dict(SavedWork.WORK_TYPE_CHOICES):
        return JsonResponse({'success': False, 'error': 'Invalid work type.'})
    
    # Get folder if specified
    folder = None
    if folder_id:
        folder = get_object_or_404(WorkFolder, id=folder_id, organization=org, user=user)
    
    # Collect work data from session based on work type
    work_data = collect_work_data(request, work_type)
    
    # Calculate progress based on work data
    progress_percent = calculate_progress(work_data, work_type)
    last_step = get_last_step(request, work_type)
    
    if work_id:
        # Check if existing saved work has a different work_type
        # If so, create a new record instead of overwriting (to preserve estimate when saving workslip)
        existing_work = get_object_or_404(SavedWork, id=work_id, organization=org, user=user)
        
        if existing_work.work_type != work_type:
            # Different work type - create a new record, don't overwrite
            # This prevents overwriting estimate data when saving from workslip
            
            # For workslips, set the workslip_number and parent
            workslip_number = 1
            parent = None
            if work_type == 'workslip':
                workslip_number = request.session.get('ws_target_workslip', 1) or 1
                # Link workslip to its source estimate
                source_est_id = request.session.get('ws_source_estimate_id')
                if source_est_id:
                    try:
                        parent = SavedWork.objects.get(id=source_est_id, organization=org, user=user)
                    except SavedWork.DoesNotExist:
                        pass
                if not parent:
                    parent = existing_work  # fallback: link to the work we came from

            # For bills, set bill_number and parent from session
            bill_number = 1
            if work_type == 'bill':
                bill_number = request.session.get('bill_target_number', 1) or 1
                parent_id = request.session.get('bill_parent_work_id')
                if parent_id:
                    try:
                        parent = SavedWork.objects.get(id=parent_id, organization=org, user=user)
                    except SavedWork.DoesNotExist:
                        pass

            # Auto-inherit parent's folder if no folder specified
            child_folder = folder
            if not child_folder and parent and parent.folder:
                child_folder = parent.folder

            saved_work = SavedWork.objects.create(
                organization=org,
                user=user,
                folder=child_folder,
                parent=parent,
                name=work_name,
                work_type=work_type,
                work_data=work_data,
                category=category,
                notes=notes,
                progress_percent=progress_percent,
                last_step=last_step,
                workslip_number=workslip_number,
                bill_number=bill_number,
            )
            message = f'Work "{work_name}" saved successfully!'
        else:
            # Same work type - update existing
            saved_work = existing_work
            saved_work.name = work_name
            saved_work.folder = folder
            saved_work.notes = notes
            saved_work.work_data = work_data
            saved_work.progress_percent = progress_percent
            saved_work.last_step = last_step

            # Update workslip_number if this is a workslip
            if work_type == 'workslip':
                saved_work.workslip_number = request.session.get('ws_target_workslip', 1) or 1

            # Update bill_number if this is a bill
            if work_type == 'bill':
                saved_work.bill_number = request.session.get('bill_target_number', 1) or 1

            saved_work.save()
            message = f'Work "{work_name}" updated successfully!'

            # ── Propagate estimate qty changes to child workslips ──
            if work_type == 'new_estimate':
                _propagate_estimate_to_children(saved_work, work_data)
    else:
        # Create new saved work

        # For workslips, set the workslip_number and parent
        workslip_number = 1
        parent = None
        if work_type == 'workslip':
            workslip_number = request.session.get('ws_target_workslip', 1) or 1
            # Link workslip to its source estimate
            source_est_id = request.session.get('ws_source_estimate_id')
            if source_est_id:
                try:
                    parent = SavedWork.objects.get(id=source_est_id, organization=org, user=user)
                except SavedWork.DoesNotExist:
                    pass

        # For bills, set bill_number and parent from session
        bill_number = 1
        if work_type == 'bill':
            bill_number = request.session.get('bill_target_number', 1) or 1
            parent_id = request.session.get('bill_parent_work_id')
            if parent_id:
                try:
                    parent = SavedWork.objects.get(id=parent_id, organization=org, user=user)
                except SavedWork.DoesNotExist:
                    pass

        # Auto-inherit parent's folder if no folder specified
        child_folder = folder
        if not child_folder and parent and parent.folder:
            child_folder = parent.folder

        saved_work = SavedWork.objects.create(
            organization=org,
            user=user,
            folder=child_folder,
            parent=parent,
            name=work_name,
            work_type=work_type,
            work_data=work_data,
            category=category,
            notes=notes,
            progress_percent=progress_percent,
            last_step=last_step,
            workslip_number=workslip_number,
            bill_number=bill_number,
        )
        message = f'Work "{work_name}" saved successfully!'
    
    # Store saved work ID in session for quick access
    request.session['current_saved_work_id'] = saved_work.id
    
    return JsonResponse({
        'success': True,
        'work_id': saved_work.id,
        'message': message
    })


# ==============================================================================
# PROPAGATE ESTIMATE CHANGES TO CHILD WORKSLIPS / BILLS
# ==============================================================================

def _propagate_estimate_to_children(estimate_work, estimate_data):
    """
    When an estimate is re-saved, update qty_est in every child workslip's
    ws_estimate_rows so the workslip always reflects the latest estimate
    quantities, rates, and items.
    
    Also recalculates ws_estimate_grand_total for each child.
    """
    import logging
    logger = logging.getLogger(__name__)

    qty_map = estimate_data.get('qty_map', {})
    item_rates = estimate_data.get('item_rates', {})
    item_units = estimate_data.get('item_units', {})
    grand_total = estimate_data.get('grand_total', '')
    work_name = estimate_data.get('work_name', '')

    # Parse grand_total to float for children
    try:
        grand_total_float = float(grand_total) if grand_total else 0.0
    except (ValueError, TypeError):
        grand_total_float = 0.0

    # Find all descendant workslips — direct children of this estimate
    # AND chained workslips (Workslip-2 → parent=Workslip-1, etc.)
    # We walk the tree breadth-first so every workslip in the chain gets
    # its ws_estimate_rows updated.
    queue = list(SavedWork.objects.filter(parent=estimate_work, work_type='workslip'))
    visited = set()

    updated_count = 0
    while queue:
        child = queue.pop(0)
        if child.id in visited:
            continue
        visited.add(child.id)

        child_data = child.work_data or {}
        ws_rows = child_data.get('ws_estimate_rows', [])
        if not ws_rows:
            # Still enqueue grandchildren even if this child has no rows
            grandchildren = list(SavedWork.objects.filter(parent=child, work_type='workslip'))
            queue.extend(grandchildren)
            continue

        changed = False
        for row in ws_rows:
            item_name = row.get('item_name', '')
            if not item_name:
                continue

            # Update qty_est from estimate's qty_map
            new_qty = qty_map.get(item_name, 0)
            try:
                new_qty = float(new_qty) if new_qty else 0.0
            except (ValueError, TypeError):
                new_qty = 0.0

            old_qty = row.get('qty_est', 0)
            try:
                old_qty = float(old_qty) if old_qty else 0.0
            except (ValueError, TypeError):
                old_qty = 0.0

            if new_qty != old_qty:
                row['qty_est'] = new_qty
                changed = True

            # Update rate if available from estimate
            if item_name in item_rates:
                new_rate = float(item_rates[item_name] or 0)
                old_rate = float(row.get('rate', 0) or 0)
                if new_rate != old_rate:
                    row['rate'] = new_rate
                    changed = True

            # Update unit if available from estimate
            if item_name in item_units:
                new_unit = str(item_units[item_name])
                if new_unit != row.get('unit', ''):
                    row['unit'] = new_unit
                    changed = True

        if changed:
            child_data['ws_estimate_rows'] = ws_rows
            # Update grand total
            child_data['ws_estimate_grand_total'] = grand_total_float
            # Update work name if the estimate's work name changed
            if work_name:
                child_data['ws_work_name'] = work_name
            # Update metadata
            ws_meta = child_data.get('ws_metadata', {})
            if ws_meta:
                ws_meta['estimate_amount'] = str(grand_total_float) if grand_total_float else ''
                if work_name:
                    ws_meta['work_name'] = work_name
                ws_meta['grand_total'] = grand_total_float
                child_data['ws_metadata'] = ws_meta

            child.work_data = child_data
            child.save()
            updated_count += 1
            logger.info(f"[PROPAGATE] Updated child workslip '{child.name}' (ID={child.id}) with new estimate quantities")

        # Enqueue any grandchildren (next workslips in the chain)
        grandchildren = list(SavedWork.objects.filter(parent=child, work_type='workslip'))
        queue.extend(grandchildren)

    if updated_count:
        logger.info(f"[PROPAGATE] Propagated estimate changes to {updated_count} child workslip(s)")


def collect_work_data(request, work_type):
    """Collect all relevant session data for a given work type.
    
    For new_estimate: prefer direct POST data (qty_map_json, etc.) over session
    so we don't depend on a prior save_qty_map request having flushed to DB.
    """
    import json as _json
    work_data = {}
    
    if work_type == 'new_estimate':
        # ---- qty_map: prefer direct POST JSON over session ----
        qty_map = request.session.get('qty_map', {})
        qty_map_json = request.POST.get('qty_map_json', '')
        if qty_map_json:
            try:
                parsed = _json.loads(qty_map_json)
                if isinstance(parsed, dict):
                    qty_map = parsed
                    # Also update session so subsequent reads are consistent
                    request.session['qty_map'] = qty_map
            except (ValueError, TypeError):
                pass

        # ---- unit_map: prefer direct POST JSON over session ----
        unit_map = request.session.get('unit_map', {})
        unit_map_json = request.POST.get('unit_map_json', '')
        if unit_map_json:
            try:
                parsed = _json.loads(unit_map_json)
                if isinstance(parsed, dict):
                    unit_map = parsed
                    request.session['unit_map'] = unit_map
            except (ValueError, TypeError):
                pass

        # ---- scalar fields: prefer POST *_value suffix over session ----
        def _post_or_session(post_key, session_key, default=''):
            val = request.POST.get(post_key, '')
            if val:
                request.session[session_key] = val
                return val
            return request.session.get(session_key, default)

        work_data = {
            'fetched_items': request.session.get('fetched_items', []),
            'current_project_name': request.session.get('current_project_name'),
            'work_type': _post_or_session('work_type_value', 'work_type', 'original'),
            'qty_map': qty_map,
            'unit_map': unit_map,
            'work_name': _post_or_session('work_name_value', 'work_name', ''),
            'grand_total': _post_or_session('grand_total_value', 'grand_total', ''),
            'excess_tp_percent': _post_or_session('excess_tp_percent_value', 'excess_tp_percent', ''),
            'ls_special_name': _post_or_session('ls_special_name_value', 'ls_special_name', ''),
            'ls_special_amount': _post_or_session('ls_special_amount_value', 'ls_special_amount', ''),
            'deduct_old_material': _post_or_session('deduct_old_material_value', 'deduct_old_material', ''),
            'last_group': request.POST.get('group', ''),
            'selected_backend_id': request.session.get('selected_backend_id'),
            'item_rates': request.session.get('item_rates', {}),
            'item_units': request.session.get('item_units', {}),
        }
        request.session.modified = True
    
    elif work_type == 'workslip':
        work_data = {
            'ws_estimate_rows': request.session.get('ws_estimate_rows', []),
            'ws_exec_map': request.session.get('ws_exec_map', {}),
            'ws_tp_percent': request.session.get('ws_tp_percent', 0.0),
            'ws_tp_type': request.session.get('ws_tp_type', 'Excess'),
            'ws_supp_items': request.session.get('ws_supp_items', []),
            'ws_estimate_grand_total': request.session.get('ws_estimate_grand_total', 0.0),
            'ws_work_name': request.session.get('ws_work_name', ''),
            'ws_deduct_old_material': request.session.get('ws_deduct_old_material', 0.0),
            'ws_lc_percent': request.session.get('ws_lc_percent', 0.0),
            'ws_qc_percent': request.session.get('ws_qc_percent', 0.0),
            'ws_nac_percent': request.session.get('ws_nac_percent', 0.0),
            'ws_current_phase': request.session.get('ws_current_phase', 1),
            'ws_target_workslip': request.session.get('ws_target_workslip', 1),
            'ws_previous_phases': request.session.get('ws_previous_phases', []),
            'ws_previous_ae_data': request.session.get('ws_previous_ae_data', []),
            'ws_previous_supp_items': request.session.get('ws_previous_supp_items', []),
            'ws_metadata': request.session.get('ws_metadata', {}),
            'selected_backend_id': request.session.get('ws_selected_backend_id'),
            'ws_source_estimate_id': request.session.get('ws_source_estimate_id'),
        }
    
    elif work_type == 'temporary_works':
        work_data = {
            'temp_items': request.session.get('temp_items', []),
            'temp_selected_entries': request.session.get('temp_selected_entries', {}),
            'temp_category': request.session.get('temp_category', 'electrical'),
        }
    
    elif work_type == 'amc':
        work_data = {
            'amc_fetched_items': request.session.get('amc_fetched_items', []),
            'amc_qty_map': request.session.get('amc_qty_map', {}),
            'amc_category': request.session.get('amc_category', 'electrical'),
        }

    elif work_type == 'bill':
        work_data = {
            'bill_source_work_id': request.session.get('bill_source_work_id'),
            'bill_source_work_type': request.session.get('bill_source_work_type', ''),
            'bill_source_work_name': request.session.get('bill_source_work_name', ''),
            'bill_from_workslip': request.session.get('bill_from_workslip', False),
            'bill_ws_rows': request.session.get('bill_ws_rows', []),
            'bill_ws_exec_map': request.session.get('bill_ws_exec_map', {}),
            'bill_ws_tp_percent': request.session.get('bill_ws_tp_percent', 0),
            'bill_ws_tp_type': request.session.get('bill_ws_tp_type', 'Excess'),
            'bill_target_number': request.session.get('bill_target_number', 1),
            'bill_type': request.session.get('bill_type', ''),
            'source_workslip_id': request.session.get('bill_source_work_id'),
            'bill_ws_metadata': request.session.get('bill_ws_metadata', {}),
            'bill_parent_work_id': request.session.get('bill_parent_work_id'),
            'ws_source_estimate_id': request.session.get('ws_source_estimate_id'),
        }

    return work_data


def calculate_progress(work_data, work_type):
    """Calculate progress percentage based on work data completeness."""
    if work_type == 'new_estimate':
        items = work_data.get('fetched_items', [])
        if not items:
            return 0
        qty_map = work_data.get('qty_map', {})
        if qty_map:
            return min(80, 20 + len(items) * 5)
        return min(50, len(items) * 5)
    
    elif work_type == 'workslip':
        rows = work_data.get('ws_estimate_rows', [])
        if not rows:
            return 0
        exec_map = work_data.get('ws_exec_map', {})
        if exec_map:
            return min(90, 30 + len(rows) * 3)
        return min(50, len(rows) * 3)
    
    elif work_type == 'temporary_works':
        items = work_data.get('temp_items', [])
        if not items:
            return 0
        return min(80, len(items) * 10)
    
    elif work_type == 'bill':
        # Bill progress is determined by existence of bill data
        if work_data.get('bill_ws_rows'):
            return 50
        return 10

    elif work_type == 'amc':
        items = work_data.get('amc_fetched_items', [])
        if not items:
            return 0
        qty_map = work_data.get('amc_qty_map', {})
        if qty_map:
            return min(80, 20 + len(items) * 5)
        return min(50, len(items) * 5)
    
    return 0


def get_last_step(request, work_type):
    """Get description of last step user was on."""
    if work_type == 'new_estimate':
        items = request.session.get('fetched_items', [])
        if items:
            return f"Selected {len(items)} items"
        return "Category selection"
    
    elif work_type == 'workslip':
        rows = request.session.get('ws_estimate_rows', [])
        if rows:
            return f"Uploaded estimate with {len(rows)} items"
        return "Initial upload"
    
    elif work_type == 'temporary_works':
        items = request.session.get('temp_items', [])
        if items:
            return f"Added {len(items)} temporary items"
        return "Category selection"
    
    elif work_type == 'amc':
        items = request.session.get('amc_fetched_items', [])
        if items:
            return f"Selected {len(items)} AMC items"
        return "Category selection"

    elif work_type == 'bill':
        bill_num = request.session.get('bill_target_number', 1)
        return f"Bill-{bill_num} generation"

    return "Started"


# ==============================================================================
# RESUME WORK FUNCTIONALITY
# ==============================================================================

@login_required(login_url='login')
def resume_saved_work(request, work_id):
    """Resume a saved work - restores session state and redirects to appropriate module."""
    org = get_org_from_request(request)
    user = request.user
    
    saved_work = get_object_or_404(SavedWork, id=work_id, organization=org, user=user)
    
    # Check subscription access BEFORE allowing resume
    access_result = check_saved_work_access(user, saved_work)
    if not access_result['ok']:
        module_code = access_result.get('module_code')
        messages.warning(
            request, 
            f'You need an active subscription to access this saved work. {access_result["reason"]}'
        )
        # Redirect to module subscription page if module_code exists
        if module_code:
            return redirect('module_access', module_code=module_code)
        return redirect('saved_works_list')
    
    # Restore session state based on work type
    restore_work_data(request, saved_work)
    
    # Store current saved work ID in session
    request.session['current_saved_work_id'] = saved_work.id
    request.session['current_saved_work_name'] = saved_work.name
    
    # Update last accessed
    saved_work.save()  # Updates updated_at timestamp
    
    # Redirect to appropriate module
    redirect_url = get_module_url(saved_work)
    
    messages.success(request, f'Resumed work: "{saved_work.name}"')
    
    return redirect(redirect_url)


def restore_work_data(request, saved_work):
    """Restore session state from saved work data."""
    import logging
    logger = logging.getLogger(__name__)
    
    work_data = saved_work.work_data
    work_type = saved_work.work_type
    
    logger.info(f"[RESTORE DEBUG] Restoring work_type={work_type}, work_data keys={work_data.keys() if work_data else 'None'}")
    
    if work_type == 'new_estimate':
        request.session['fetched_items'] = work_data.get('fetched_items', [])
        request.session['current_project_name'] = work_data.get('current_project_name')
        request.session['work_type'] = work_data.get('work_type', 'original')
        request.session['qty_map'] = work_data.get('qty_map', {})
        request.session['unit_map'] = work_data.get('unit_map', {})
        request.session['work_name'] = work_data.get('work_name', '')
        request.session['grand_total'] = work_data.get('grand_total', '')
        request.session['excess_tp_percent'] = work_data.get('excess_tp_percent', '')
        request.session['ls_special_name'] = work_data.get('ls_special_name', '')
        request.session['ls_special_amount'] = work_data.get('ls_special_amount', '')
        request.session['deduct_old_material'] = work_data.get('deduct_old_material', '')
        # Restore backend_id so modules use the correct backend
        if work_data.get('selected_backend_id'):
            request.session['selected_backend_id'] = work_data['selected_backend_id']
        # Restore saved item rates & units so workslip generation uses exact values
        if work_data.get('item_rates'):
            request.session['item_rates'] = work_data['item_rates']
        if work_data.get('item_units'):
            request.session['item_units'] = work_data['item_units']
        # Force session save
        request.session.modified = True
    
    elif work_type == 'workslip':
        ws_estimate_rows = work_data.get('ws_estimate_rows', [])
        logger.info(f"[RESTORE DEBUG] ws_estimate_rows count={len(ws_estimate_rows)}")
        if ws_estimate_rows:
            logger.info(f"[RESTORE DEBUG] First row: {ws_estimate_rows[0]}")
        
        request.session['ws_estimate_rows'] = ws_estimate_rows
        request.session['ws_exec_map'] = work_data.get('ws_exec_map', {})
        request.session['ws_tp_percent'] = work_data.get('ws_tp_percent', 0.0)
        request.session['ws_tp_type'] = work_data.get('ws_tp_type', 'Excess')
        request.session['ws_supp_items'] = work_data.get('ws_supp_items', [])
        request.session['ws_estimate_grand_total'] = work_data.get('ws_estimate_grand_total', 0.0)
        request.session['ws_work_name'] = work_data.get('ws_work_name', '')
        request.session['ws_deduct_old_material'] = work_data.get('ws_deduct_old_material', 0.0)
        request.session['ws_current_phase'] = work_data.get('ws_current_phase', 1)
        request.session['ws_target_workslip'] = work_data.get('ws_target_workslip', 1)
        request.session['ws_previous_phases'] = work_data.get('ws_previous_phases', [])
        request.session['ws_previous_ae_data'] = work_data.get('ws_previous_ae_data', [])
        request.session['ws_previous_supp_items'] = work_data.get('ws_previous_supp_items', [])
        request.session['ws_metadata'] = work_data.get('ws_metadata', {})
        
        # Restore backend_id so the workslip module uses the correct backend
        if work_data.get('selected_backend_id'):
            request.session['ws_selected_backend_id'] = work_data['selected_backend_id']
        request.session['ws_source_estimate_id'] = work_data.get('ws_source_estimate_id')
        request.session['ws_lc_percent'] = work_data.get('ws_lc_percent', 0.0)
        request.session['ws_qc_percent'] = work_data.get('ws_qc_percent', 0.0)
        request.session['ws_nac_percent'] = work_data.get('ws_nac_percent', 0.0)
        
        # Force session save
        request.session.modified = True
        logger.info(f"[RESTORE DEBUG] Session saved. ws_estimate_rows in session: {len(request.session.get('ws_estimate_rows', []))}")
    
    elif work_type == 'temporary_works':
        request.session['temp_items'] = work_data.get('temp_items', [])
        request.session['temp_selected_entries'] = work_data.get('temp_selected_entries', {})
        request.session['temp_category'] = work_data.get('temp_category', 'electrical')
    
    elif work_type == 'amc':
        request.session['amc_fetched_items'] = work_data.get('amc_fetched_items', [])
        request.session['amc_qty_map'] = work_data.get('amc_qty_map', {})
        request.session['amc_category'] = work_data.get('amc_category', 'electrical')

    elif work_type == 'bill':
        # Restore bill session data for the existing bill engine
        request.session['bill_source_work_id'] = work_data.get('bill_source_work_id')
        request.session['bill_source_work_type'] = work_data.get('bill_source_work_type', '')
        request.session['bill_source_work_name'] = work_data.get('bill_source_work_name', '')
        request.session['bill_from_workslip'] = work_data.get('bill_from_workslip', False)
        request.session['bill_ws_rows'] = work_data.get('bill_ws_rows', [])
        request.session['bill_ws_exec_map'] = work_data.get('bill_ws_exec_map', {})
        request.session['bill_ws_tp_percent'] = work_data.get('bill_ws_tp_percent', 0)
        request.session['bill_ws_tp_type'] = work_data.get('bill_ws_tp_type', 'Excess')
        request.session['bill_target_number'] = work_data.get('bill_target_number', 1)
        request.session['bill_type'] = work_data.get('bill_type', '')
        request.session['bill_ws_metadata'] = work_data.get('bill_ws_metadata', {})
        request.session.modified = True


def get_module_url(saved_work):
    """Get the URL to redirect to for resuming work."""
    from django.urls import reverse
    
    work_type = saved_work.work_type
    category = saved_work.category or 'electrical'
    work_data = saved_work.work_data or {}
    
    if work_type == 'new_estimate':
        # If we have a last group saved, redirect to that group's items page
        last_group = work_data.get('last_group', '')
        if last_group:
            return reverse('datas_items', kwargs={'category': category, 'group': last_group})
        return reverse('datas_groups', kwargs={'category': category})
    
    elif work_type == 'workslip':
        return reverse('workslip_main') + '?preserve=1'
    
    elif work_type == 'temporary_works':
        return reverse('temp_groups', kwargs={'category': category})
    
    elif work_type == 'amc':
        return reverse('amc_groups', kwargs={'category': category})

    elif work_type == 'bill':
        return reverse('bill') + '?from_saved=1'

    return reverse('dashboard')


# ==============================================================================
# SAVED WORK DETAILS & ACTIONS
# ==============================================================================

@login_required(login_url='login')
@require_POST
def update_saved_work(request, work_id):
    """Update saved work metadata (name, folder, notes)."""
    org = get_org_from_request(request)
    user = request.user
    
    saved_work = get_object_or_404(SavedWork, id=work_id, organization=org, user=user)
    
    work_name = request.POST.get('name', '').strip()
    folder_id = request.POST.get('folder_id')
    notes = request.POST.get('notes', '').strip()
    status = request.POST.get('status')
    
    if work_name:
        saved_work.name = work_name
    
    if folder_id:
        if folder_id == 'none':
            saved_work.folder = None
        else:
            saved_work.folder = get_object_or_404(WorkFolder, id=folder_id, organization=org, user=user)
    
    saved_work.notes = notes
    
    if status in dict(SavedWork.STATUS_CHOICES):
        saved_work.status = status
    
    saved_work.save()
    
    return JsonResponse({
        'success': True,
        'message': f'Work "{saved_work.name}" updated successfully!'
    })


@login_required(login_url='login')
@require_POST
def delete_saved_work(request, work_id):
    """Delete a saved work."""
    org = get_org_from_request(request)
    user = request.user
    
    saved_work = get_object_or_404(SavedWork, id=work_id, organization=org, user=user)
    work_name = saved_work.name
    saved_work.delete()
    
    return JsonResponse({
        'success': True,
        'message': f'Work "{work_name}" deleted successfully!'
    })


@login_required(login_url='login')
@require_POST
def move_to_folder(request, work_id):
    """Move a saved work to a different folder."""
    org = get_org_from_request(request)
    user = request.user
    
    saved_work = get_object_or_404(SavedWork, id=work_id, organization=org, user=user)
    folder_id = request.POST.get('folder_id')
    
    if folder_id == 'none' or not folder_id:
        saved_work.folder = None
    else:
        saved_work.folder = get_object_or_404(WorkFolder, id=folder_id, organization=org, user=user)
    
    saved_work.save()
    
    return JsonResponse({
        'success': True,
        'message': f'Work moved successfully!'
    })


@login_required(login_url='login')
@require_POST
def duplicate_saved_work(request, work_id):
    """Duplicate a saved work."""
    org = get_org_from_request(request)
    user = request.user
    
    saved_work = get_object_or_404(SavedWork, id=work_id, organization=org, user=user)
    
    new_work = SavedWork.objects.create(
        organization=org,
        user=user,
        folder=saved_work.folder,
        name=f"{saved_work.name} (Copy)",
        work_type=saved_work.work_type,
        work_data=saved_work.work_data.copy() if saved_work.work_data else {},
        category=saved_work.category,
        notes=saved_work.notes,
        progress_percent=saved_work.progress_percent,
        last_step=saved_work.last_step,
    )
    
    return JsonResponse({
        'success': True,
        'work_id': new_work.id,
        'message': f'Work duplicated as "{new_work.name}"!'
    })


# ==============================================================================
# SAVE MODAL DATA (for frontend save work modal)
# ==============================================================================

@login_required(login_url='login')
def get_save_work_modal_data(request):
    """Get data needed for save work modal (folders list, current work info)."""
    org = get_org_from_request(request)
    user = request.user
    
    folders = WorkFolder.objects.filter(organization=org, user=user).values('id', 'name', 'color')
    
    current_work_id = request.session.get('current_saved_work_id')
    current_work = None
    if current_work_id:
        try:
            work = SavedWork.objects.get(id=current_work_id, organization=org, user=user)
            current_work = {
                'id': work.id,
                'name': work.name,
                'folder_id': work.folder_id,
                'notes': work.notes,
            }
        except SavedWork.DoesNotExist:
            pass
    
    return JsonResponse({
        'folders': list(folders),
        'current_work': current_work,
    })


# ==============================================================================
# WORKFLOW CHAIN: ESTIMATE â†’ WORKSLIP â†’ BILL
# ==============================================================================

def load_item_rates_from_backend(category, item_names, backend_id=None, user=None, module_code=None):
    """
    Load item rates and descriptions from the backend Excel file for given item names.
    Uses the user's selected backend (ModuleBackend) if available, falling back to default.
    Returns a dict: {item_name: {'rate': value, 'unit': 'Nos/Mtrs/Pts', 'group': 'group_name', 'desc': 'description'}}
    """
    from django.conf import settings
    from openpyxl import load_workbook
    import os
    import logging
    logger = logging.getLogger(__name__)
    
    logger.info(f"[LOAD_RATES DEBUG] Loading rates for category={category}, items={item_names}, backend_id={backend_id}")
    
    try:
        from core.utils_excel import load_backend
        
        # Use load_backend which handles backend_id, user preferences, and fallbacks
        items_list, groups_map, _units_map, ws_data, filepath = load_backend(
            category, settings.BASE_DIR,
            backend_id=backend_id,
            module_code=module_code or 'new_estimate',
            user=user
        )
        
        logger.info(f"[LOAD_RATES DEBUG] Backend filepath: {filepath}, found {len(items_list)} items")
        
        if not filepath or not os.path.exists(filepath):
            logger.warning(f"[LOAD_RATES DEBUG] Backend file not found at {filepath}!")
            return {name: {'rate': 0, 'unit': 'Nos', 'group': '', 'desc': name} for name in item_names}
        
        # Open workbook with data_only=True to get calculated formula values
        wb_data = load_workbook(filepath, data_only=True)
        ws_data_only = wb_data["Master Datas"]
        # Build item to group mapping
        item_to_group = {}
        for grp_name, item_list_in_grp in groups_map.items():
            for nm in item_list_in_grp:
                item_to_group[nm] = grp_name
        
        # Get rates and descriptions for requested items
        result = {}
        for info in items_list:
            name = info["name"]
            if name not in item_names:
                continue
            
            start_row = info["start_row"]
            end_row = info["end_row"]
            rate = 0
            
            # Find rate from bottom up (last value in column J)
            # Try data_only workbook first (has calculated values), then formula workbook
            for r in range(end_row, start_row - 1, -1):
                val = ws_data_only.cell(row=r, column=10).value  # column J (data_only)
                if val not in (None, ""):
                    try:
                        rate = float(val)
                    except (ValueError, TypeError):
                        rate = 0
                    break
            
            # If rate is still 0, try the formula workbook (ws_data)
            # Some Excel files may only have literal values, not formula results
            if rate == 0 and ws_data is not None:
                for r in range(end_row, start_row - 1, -1):
                    val = ws_data.cell(row=r, column=10).value
                    if val not in (None, ""):
                        try:
                            rate = float(val)
                        except (ValueError, TypeError):
                            rate = 0
                        break
            
            # Get description from row start_row + 2, column D (4)
            desc = name  # default to item name
            if ws_data is not None:
                desc_cell = ws_data.cell(row=start_row + 2, column=4).value
                if desc_cell and str(desc_cell).strip():
                    desc = str(desc_cell).strip()
            
            # Determine unit from units_map (Column D of Groups sheet) — authoritative source
            unit = _units_map.get(name, "")
            if not unit:
                # Fallback: infer from group name
                grp_name = item_to_group.get(name, "")
                if grp_name in ("Piping", "Wiring & Cables", "Wiring and cables"):
                    unit = "Mtrs"
                elif grp_name == "Points":
                    unit = "Pts"
                else:
                    unit = "Nos"
            else:
                grp_name = item_to_group.get(name, "")
            
            result[name] = {'rate': rate, 'unit': unit, 'group': grp_name, 'desc': desc}
            logger.info(f"[LOAD_RATES DEBUG] Found rate for '{name}': rate={rate}, unit={unit}, desc={desc[:50] if desc else 'None'}")
        
        wb_data.close()
        
        # Fill in any missing items with defaults
        for name in item_names:
            if name not in result:
                logger.warning(f"[LOAD_RATES DEBUG] Item '{name}' NOT FOUND in backend!")
                result[name] = {'rate': 0, 'unit': 'Nos', 'group': '', 'desc': name}
        
        return result
        
    except Exception as e:
        logger.error(f"[LOAD_RATES DEBUG] Error loading item rates: {e}")
        import traceback
        traceback.print_exc()
        return {name: {'rate': 0, 'unit': 'Nos', 'group': '', 'desc': name} for name in item_names}


@login_required(login_url='login')
def generate_workslip_from_saved(request, work_id):
    """
    Generate a workslip from a saved estimate.
    Loads the estimate data into workslip session and redirects to workslip page.
    """
    import logging
    logger = logging.getLogger(__name__)
    
    org = get_org_from_request(request)
    user = request.user
    
    saved_work = get_object_or_404(SavedWork, id=work_id, organization=org, user=user)
    
    # Verify this is an estimate, temporary_works, or amc
    if saved_work.work_type not in ['new_estimate', 'temporary_works', 'amc']:
        messages.error(request, 'Only estimates, temporary works, or AMC can be used to generate workslips.')
        return redirect('saved_works_list')
    
    # Load estimate data into workslip session
    work_data = saved_work.work_data or {}
    
    # Get item names and quantities from saved data
    # fetched_items can be either a list of names (strings) or a list of dicts
    fetched_items = work_data.get('fetched_items', [])
    qty_map = work_data.get('qty_map', {})
    category = saved_work.category or 'electrical'
    
    # Get saved backend_id from estimate work_data for correct rate lookup
    saved_backend_id = work_data.get('selected_backend_id')
    
    logger.info(f"[GEN_WORKSLIP DEBUG] fetched_items={fetched_items}")
    logger.info(f"[GEN_WORKSLIP DEBUG] qty_map={qty_map}")
    logger.info(f"[GEN_WORKSLIP DEBUG] category={category}, backend_id={saved_backend_id}")
    
    # Determine module_code for backend loading
    if saved_work.work_type == 'amc':
        ws_module_code = 'amc'
    elif saved_work.work_type == 'temporary_works':
        ws_module_code = 'temp_works'
    else:
        ws_module_code = 'new_estimate'
    
    # Saved rates / units from the estimate session (exact values the user saw)
    saved_item_rates = work_data.get('item_rates', {})
    saved_item_units = work_data.get('item_units', {})
    
    logger.info(f"[GEN_WORKSLIP DEBUG] saved_item_rates keys={list(saved_item_rates.keys())[:10]}")
    
    # Check if fetched_items is a list of strings (item names) or dicts
    if fetched_items and isinstance(fetched_items[0], str):
        item_names = fetched_items
        
        # Only re-fetch from backend for items that don't have saved rates
        items_needing_backend = [n for n in item_names if n not in saved_item_rates or saved_item_rates.get(n, 0) == 0]
        
        item_info_map = {}
        if items_needing_backend:
            logger.info(f"[GEN_WORKSLIP DEBUG] Re-fetching rates from backend for {len(items_needing_backend)} items: {items_needing_backend[:5]}")
            item_info_map = load_item_rates_from_backend(
                category, items_needing_backend,
                backend_id=saved_backend_id,
                user=request.user,
                module_code=ws_module_code
            )
        
        # Convert to workslip format - match the format from estimate upload
        ws_estimate_rows = []
        for idx, item_name in enumerate(item_names):
            qty = qty_map.get(item_name, 0)
            try:
                qty = float(qty) if qty else 0.0
            except (ValueError, TypeError):
                qty = 0.0
            
            # Priority: 1) saved rates from estimate, 2) backend re-fetch
            if item_name in saved_item_rates and saved_item_rates[item_name]:
                rate = float(saved_item_rates[item_name])
                unit = str(saved_item_units.get(item_name, 'Nos'))
                desc = item_name  # Use name as desc; backend lookup below fills desc if needed
            else:
                info = item_info_map.get(item_name, {'rate': 0, 'unit': 'Nos', 'desc': item_name})
                rate = float(info.get('rate', 0) or 0)
                unit = str(info.get('unit', 'Nos'))
                desc = str(info.get('desc', item_name) or item_name)
            
            logger.info(f"[GEN_WORKSLIP DEBUG] Item '{item_name}': qty={qty}, rate={rate} (source={'saved' if item_name in saved_item_rates and saved_item_rates.get(item_name) else 'backend'})")
            
            ws_estimate_rows.append({
                'key': f"saved_{idx}",
                'item_name': str(item_name),
                'display_name': str(item_name),
                'desc': desc,
                'unit': unit,
                'qty_est': qty,
                'rate': rate,
            })
    else:
        # It's already a list of dicts with full item info
        ws_estimate_rows = []
        for idx, item in enumerate(fetched_items):
            if isinstance(item, dict):
                item_id = item.get('id') or item.get('name') or str(idx)
                qty = qty_map.get(str(item_id), item.get('qty', 0))
                try:
                    qty = float(qty) if qty else 0.0
                except (ValueError, TypeError):
                    qty = 0.0
                rate = float(item.get('rate', 0)) if item.get('rate') else 0.0
                
                ws_estimate_rows.append({
                    'key': f"saved_{idx}",
                    'item_name': str(item.get('name', item.get('description', ''))),
                    'display_name': str(item.get('name', item.get('description', ''))),
                    'desc': str(item.get('description', item.get('name', ''))),
                    'unit': str(item.get('unit', 'Nos')),
                    'qty_est': qty,
                    'rate': rate,
                })
    
    # Convert grand_total to float (it might be stored as string)
    grand_total = work_data.get('grand_total', 0)
    logger.info(f"[GEN_WORKSLIP DEBUG] Raw grand_total from work_data: '{grand_total}' (type: {type(grand_total).__name__})")
    try:
        grand_total = float(grand_total) if grand_total else 0.0
    except (ValueError, TypeError):
        grand_total = 0.0
    logger.info(f"[GEN_WORKSLIP DEBUG] Parsed grand_total: {grand_total}")
    
    # Get the work_name from the saved estimate data (entered in estimate preview)
    # This is the "Name of the Work" for Excel, NOT the project/file name (saved_work.name)
    estimate_work_name = work_data.get('work_name', '') or ''
    
    # Set workslip session data - ensure all values are JSON serializable
    request.session['ws_estimate_rows'] = ws_estimate_rows
    request.session['ws_exec_map'] = {}  # Start fresh execution quantities
    request.session['ws_tp_percent'] = 0.0  # TP will be entered via UI for Workslip-1
    request.session['ws_tp_type'] = 'Excess'
    request.session['ws_supp_items'] = []
    request.session['ws_estimate_grand_total'] = grand_total
    request.session['ws_work_name'] = str(estimate_work_name)
    request.session['ws_source_estimate_id'] = int(saved_work.id)
    request.session['ws_current_phase'] = 1
    request.session['ws_target_workslip'] = 1
    request.session['ws_previous_phases'] = []
    request.session['ws_previous_supp_items'] = []
    
    # For Workslip-1: Set initial metadata from estimate
    # work_name and grand_total come from estimate, TP will be entered via UI
    request.session['ws_metadata'] = {
        'work_name': str(estimate_work_name),
        'estimate_amount': str(grand_total) if grand_total else '',
        'admin_sanction': '',  # To be entered via UI or left blank
        'tech_sanction': '',   # To be entered via UI or left blank
        'agreement': '',       # To be entered via UI or left blank
        'agency_name': '',     # To be entered via UI or left blank
        'tp_percent': 0.0,
        'tp_type': 'Excess',
        'grand_total': grand_total,
    }
    
    # Set the backend_id in session so the workslip module uses the correct backend
    if saved_backend_id:
        request.session['ws_selected_backend_id'] = saved_backend_id
    
    # Set work type/mode/category for workslip module
    if saved_work.work_type == 'amc':
        request.session['ws_work_type'] = 'amc'
    elif saved_work.work_type == 'temporary_works':
        request.session['ws_work_type'] = 'tempworks'
    else:
        request.session['ws_work_type'] = 'new_estimate'
    request.session['ws_category'] = category
    
    # ── Pre-create the SavedWork record for Workslip-1 so
    #    quickSaveWorkslip() finds it and auto-updates without asking
    #    for a name. ──
    new_ws_name = f"{saved_work.name} - W1"

    new_ws = SavedWork.objects.create(
        organization=org,
        user=user,
        folder=saved_work.folder,
        parent=saved_work,
        name=new_ws_name,
        work_type='workslip',
        work_data={},  # will be filled on first quickSave
        category=category,
        notes='',
        progress_percent=0,
        last_step='workslip',
        workslip_number=1,
    )

    request.session['current_saved_work_id'] = new_ws.id
    request.session['current_saved_work_name'] = new_ws_name
    request.session.modified = True
    
    messages.success(request, f'Loaded estimate "{saved_work.name}" for workslip generation.')
    return redirect(reverse('workslip_main') + '?preserve=1')


@login_required(login_url='login')
def generate_next_workslip_from_saved(request, work_id):
    """
    Generate the next workslip from a saved workslip.
    For example, if work_id is Workslip-1, this generates Workslip-2.
    Loads previous workslip data as phase data and redirects to workslip page.
    """
    import logging
    logger = logging.getLogger(__name__)
    
    org = get_org_from_request(request)
    user = request.user
    
    saved_work = get_object_or_404(SavedWork, id=work_id, organization=org, user=user)
    
    # Verify this is a workslip
    if saved_work.work_type != 'workslip':
        messages.error(request, 'Only saved workslips can generate next workslips.')
        return redirect('saved_works_list')
    
    # Load workslip data
    work_data = saved_work.work_data or {}
    
    # Get the current workslip number and calculate next
    current_workslip_number = saved_work.workslip_number or 1
    next_workslip_number = current_workslip_number + 1
    
    logger.info(f"[NEXT_WORKSLIP] Generating Workslip-{next_workslip_number} from saved Workslip-{current_workslip_number} (ID: {work_id})")
    
    # Get estimate rows (base items) from saved workslip
    ws_estimate_rows = work_data.get('ws_estimate_rows', [])
    
    # Get previous phases from saved data (might already have phases from earlier workslips)
    existing_previous_phases = work_data.get('ws_previous_phases', [])
    
    # Get the execution map from this workslip - this becomes a new phase
    current_exec_map = work_data.get('ws_exec_map', {})
    
    # Get supplemental items from this workslip
    current_supp_items = work_data.get('ws_supp_items', [])
    
    # Get previous supplemental items
    existing_prev_supp_items = work_data.get('ws_previous_supp_items', [])
    
    # Build the new phase from current workslip's execution data
    new_phase_map = {}
    for key, qty in current_exec_map.items():
        if qty and str(qty).strip():
            try:
                new_phase_map[key] = float(qty)
            except (ValueError, TypeError):
                pass
    
    # Combine all previous phases plus the current workslip as a new phase
    all_previous_phases = list(existing_previous_phases) + [new_phase_map]
    
    # Build supplemental items from current workslip to add to previous supp items
    new_supp_items = []
    if current_supp_items and ws_estimate_rows:
        # Load rates from backend for supplemental items
        category = saved_work.category or 'electrical'
        saved_backend_id = work_data.get('selected_backend_id')
        supp_rates = load_item_rates_from_backend(
            category, current_supp_items,
            backend_id=saved_backend_id,
            user=request.user,
            module_code='new_estimate'
        )
        
        for supp_name in current_supp_items:
            supp_key = f"supp:{supp_name}"
            supp_qty = current_exec_map.get(supp_key, 0)
            try:
                supp_qty = float(supp_qty) if supp_qty else 0.0
            except:
                supp_qty = 0.0
            if supp_qty > 0:
                # Get rate from backend lookup
                supp_info = supp_rates.get(supp_name, {})
                supp_rate = float(supp_info.get('rate', 0) or 0)
                supp_unit = str(supp_info.get('unit', 'Nos') or 'Nos')
                supp_desc = str(supp_info.get('desc', supp_name) or supp_name)
                
                new_supp_items.append({
                    "name": supp_name,
                    "qty": supp_qty,
                    "phase": current_workslip_number,
                    "supp_section": current_workslip_number,
                    "desc": supp_desc,
                    "unit": supp_unit,
                    "rate": supp_rate,
                    "amount": supp_qty * supp_rate,
                })
    
    # Combine previous supplemental items
    all_previous_supp_items = list(existing_prev_supp_items) + new_supp_items
    
    # Set workslip session data for the next workslip
    request.session['ws_estimate_rows'] = ws_estimate_rows
    request.session['ws_exec_map'] = {}  # Start fresh execution quantities
    request.session['ws_previous_phases'] = all_previous_phases
    request.session['ws_previous_supp_items'] = all_previous_supp_items
    request.session['ws_current_phase'] = next_workslip_number
    request.session['ws_target_workslip'] = next_workslip_number
    request.session['ws_tp_percent'] = work_data.get('ws_tp_percent', 0.0)
    request.session['ws_tp_type'] = work_data.get('ws_tp_type', 'Excess')
    request.session['ws_supp_items'] = []  # Start fresh supplemental items for new workslip
    request.session['ws_estimate_grand_total'] = work_data.get('ws_estimate_grand_total', 0)
    request.session['ws_work_name'] = work_data.get('ws_work_name', '')
    request.session['ws_deduct_old_material'] = work_data.get('ws_deduct_old_material', 0)
    request.session['ws_lc_percent'] = work_data.get('ws_lc_percent', 0)
    request.session['ws_qc_percent'] = work_data.get('ws_qc_percent', 0)
    request.session['ws_nac_percent'] = work_data.get('ws_nac_percent', 0)
    
    # Carry over metadata from previous workslip (Name of work, Agency, Sanctions, Agreement, etc.)
    prev_metadata = work_data.get('ws_metadata', {})
    # Ensure all metadata fields are preserved
    metadata = {
        'work_name': prev_metadata.get('work_name', '') or work_data.get('ws_work_name', ''),
        'estimate_amount': prev_metadata.get('estimate_amount', ''),
        'admin_sanction': prev_metadata.get('admin_sanction', ''),
        'tech_sanction': prev_metadata.get('tech_sanction', ''),
        'agreement': prev_metadata.get('agreement', ''),
        'agency_name': prev_metadata.get('agency_name', ''),
        'tp_percent': work_data.get('ws_tp_percent', 0.0),
        'tp_type': work_data.get('ws_tp_type', 'Excess'),
        'grand_total': work_data.get('ws_estimate_grand_total', 0),
        'deduct_old_material': work_data.get('ws_deduct_old_material', 0),
        'lc_percent': work_data.get('ws_lc_percent', 0),
        'qc_percent': work_data.get('ws_qc_percent', 0),
        'nac_percent': work_data.get('ws_nac_percent', 0),
    }
    request.session['ws_metadata'] = metadata
    
    # Set the backend_id in session so the workslip module uses the correct backend
    saved_backend_id_session = work_data.get('selected_backend_id')
    if saved_backend_id_session:
        request.session['ws_selected_backend_id'] = saved_backend_id_session
    
    # Set parent work info for saving
    # Carry forward the source estimate ID so new workslip links to root estimate
    source_est_id = work_data.get('ws_source_estimate_id')
    if source_est_id:
        request.session['ws_source_estimate_id'] = source_est_id
    elif saved_work.parent_id:
        request.session['ws_source_estimate_id'] = saved_work.parent_id
    request.session['ws_parent_work_id'] = saved_work.id

    # ── Pre-create the SavedWork record for the new workslip so
    #    quickSaveWorkslip() finds it and auto-updates without asking
    #    for a name.  Derive name from parent workslip / root estimate. ─
    # Walk up to root estimate for the base name
    base_name = saved_work.name
    root = saved_work.parent
    while root:
        if root.work_type == 'new_estimate':
            base_name = root.name
            break
        root = root.parent

    new_ws_name = f"{base_name} - W{next_workslip_number}"

    new_ws = SavedWork.objects.create(
        organization=org,
        user=user,
        folder=saved_work.folder,
        parent=saved_work,
        name=new_ws_name,
        work_type='workslip',
        work_data={},  # will be filled on first quickSave
        category=saved_work.category or 'electrical',
        notes='',
        progress_percent=0,
        last_step='workslip',
        workslip_number=next_workslip_number,
    )

    request.session['current_saved_work_id'] = new_ws.id
    request.session['current_saved_work_name'] = new_ws_name
    request.session.modified = True
    
    messages.success(request, f'Ready to generate Workslip-{next_workslip_number} from "{saved_work.name}".')
    return redirect(reverse('workslip_main') + '?preserve=1')


@login_required(login_url='login')
def generate_bill_from_saved(request, work_id):
    """
    Generate a bill from a saved workslip or estimate.
    Saved Works acts as navigation layer only - passes data to existing bill engine.
    Redirects to bill page with appropriate data loaded.
    """
    import logging
    logger = logging.getLogger(__name__)

    org = get_org_from_request(request)
    user = request.user

    try:
        saved_work = get_object_or_404(SavedWork, id=work_id, organization=org, user=user)
    except Exception:
        messages.error(request, 'Saved work not found or you do not have access.')
        return redirect('saved_works_list')

    # Verify this is a workslip or estimate
    if saved_work.work_type not in ['workslip', 'new_estimate']:
        messages.error(request, 'Only workslips or estimates can be used to generate bills.')
        return redirect('saved_works_list')

    work_data = saved_work.work_data or {}

    # Validate: Estimate must have data
    if saved_work.work_type == 'new_estimate':
        fetched_items = work_data.get('fetched_items', [])
        if not fetched_items:
            messages.error(request, 'Estimate has no items. Cannot generate bill from empty estimate.')
            return redirect('saved_work_detail', work_id=work_id)

    # Validate: Workslip must have estimate rows
    if saved_work.work_type == 'workslip':
        ws_rows = work_data.get('ws_estimate_rows', [])
        if not ws_rows:
            messages.error(request, 'WorkSlip has no data. Cannot generate bill from empty workslip.')
            return redirect('saved_work_detail', work_id=work_id)

    # Store source info in session for bill page
    request.session['bill_source_work_id'] = saved_work.id
    request.session['bill_source_work_type'] = saved_work.work_type
    request.session['bill_source_work_name'] = saved_work.name

    if saved_work.work_type == 'workslip':
        # B(N) from W(N): bill_number matches the source workslip_number
        bill_number = saved_work.workslip_number or 1
        request.session['bill_target_number'] = bill_number
        request.session['bill_sequence_number'] = bill_number
        # Store parent workslip ID so save_work can link the bill to this workslip
        request.session['bill_parent_work_id'] = saved_work.id

        # Load workslip data for bill generation
        request.session['bill_from_workslip'] = True
        request.session['bill_ws_rows'] = work_data.get('ws_estimate_rows', [])
        request.session['bill_ws_exec_map'] = work_data.get('ws_exec_map', {})
        request.session['bill_ws_tp_percent'] = work_data.get('ws_tp_percent', 0)
        request.session['bill_ws_tp_type'] = work_data.get('ws_tp_type', 'Excess')
        # Pass metadata for bill header (name of work, estimate amount, sanctions, agency)
        ws_metadata = work_data.get('ws_metadata', {})
        request.session['bill_ws_metadata'] = {
            'name_of_work': ws_metadata.get('work_name', '') or work_data.get('ws_work_name', ''),
            'estimate_amount': ws_metadata.get('estimate_amount', '') or str(work_data.get('ws_estimate_grand_total', '')),
            'admin_sanction': ws_metadata.get('admin_sanction', ''),
            'tech_sanction': ws_metadata.get('tech_sanction', ''),
            'agreement': ws_metadata.get('agreement', ''),
            'agency': ws_metadata.get('agency_name', ''),
        }
        # Pass supplemental items if any
        request.session['bill_ws_supp_items'] = work_data.get('ws_supp_items', [])

        logger.info(f"[GEN_BILL] Generating Bill-{bill_number} from WorkSlip-{saved_work.workslip_number} '{saved_work.name}' (ID: {work_id})")
        messages.success(request, f'Ready to generate Bill-{bill_number} from WorkSlip-{saved_work.workslip_number} "{saved_work.name}".')
    else:
        # Bill from estimate (fallback)
        request.session['bill_target_number'] = 1
        request.session['bill_sequence_number'] = 1
        request.session['bill_parent_work_id'] = saved_work.id

        request.session['bill_from_workslip'] = False
        request.session['bill_estimate_items'] = work_data.get('fetched_items', [])
        request.session['bill_qty_map'] = work_data.get('qty_map', {})

        logger.info(f"[GEN_BILL] Generating Bill-1 from estimate '{saved_work.name}' (ID: {work_id})")
        messages.success(request, f'Ready to generate bill from "{saved_work.name}".')

    # ── Pre-create the SavedWork record for the bill so save button
    #    auto-updates without asking for a name. ──
    # Walk up to root estimate for the base name
    base_name = saved_work.name
    root = saved_work.parent
    while root:
        if root.work_type == 'new_estimate':
            base_name = root.name
            break
        root = root.parent
    if saved_work.work_type == 'new_estimate':
        base_name = saved_work.name

    bill_number = request.session.get('bill_target_number', 1)
    new_bill_name = f"{base_name} - B{bill_number}"

    new_bill = SavedWork.objects.create(
        organization=org,
        user=user,
        folder=saved_work.folder,
        parent=saved_work,
        name=new_bill_name,
        work_type='bill',
        work_data={},  # will be filled on first save
        category=saved_work.category or 'electrical',
        notes='',
        progress_percent=0,
        last_step='bill',
        bill_number=bill_number,
    )

    request.session['current_saved_work_id'] = new_bill.id
    request.session['current_saved_work_name'] = new_bill_name
    request.session.modified = True
    return redirect(reverse('bill') + '?from_saved=1')


@login_required(login_url='login')
def saved_work_detail(request, work_id):
    """
    View detailed information about a saved work including workflow chain.
    Provides E, W1-W3, B1-B3 button context for the Saved Works navigation layer.
    """
    org = get_org_from_request(request)
    user = request.user

    saved_work = get_object_or_404(SavedWork, id=work_id, organization=org, user=user)

    # Find the root estimate for this workflow chain
    root_estimate = None
    if saved_work.work_type == 'new_estimate':
        root_estimate = saved_work
    else:
        # Walk up parent chain to find root estimate
        current = saved_work.parent
        while current:
            if current.work_type == 'new_estimate':
                root_estimate = current
                break
            current = current.parent

        # Fallback for orphan workslips/bills (parent not set):
        # Try to find the estimate by ws_source_estimate_id stored in work_data
        if not root_estimate:
            work_data = saved_work.work_data or {}
            source_est_id = work_data.get('ws_source_estimate_id') or work_data.get('bill_source_work_id')
            if source_est_id:
                try:
                    candidate = SavedWork.objects.get(id=source_est_id, organization=org, user=user)
                    if candidate.work_type == 'new_estimate':
                        root_estimate = candidate
                        # Fix the parent relationship while we're at it
                        saved_work.parent = root_estimate
                        saved_work.save(update_fields=['parent'])
                    else:
                        # Maybe the source is a workslip; walk up from there
                        cur = candidate.parent
                        while cur:
                            if cur.work_type == 'new_estimate':
                                root_estimate = cur
                                break
                            cur = cur.parent
                except SavedWork.DoesNotExist:
                    pass

        # Last fallback: find estimate with same name in same org
        if not root_estimate:
            root_estimate = SavedWork.objects.filter(
                organization=org, user=user,
                work_type='new_estimate',
                name=saved_work.name,
            ).first()

    # Build workflow navigation: E, W1-W3, B1-B3 buttons
    workslips = []
    bills = []
    if root_estimate:
        workslips = list(
            SavedWork.objects.filter(
                organization=org, user=user,
                work_type='workslip',
                parent=root_estimate,
            ).order_by('workslip_number')
        )

        # Also find orphan workslips (parent not set) that reference this estimate
        # via ws_source_estimate_id in their work_data — fix their parent and include them
        existing_ws_ids = {ws.id for ws in workslips}
        orphan_workslips = SavedWork.objects.filter(
            organization=org, user=user,
            work_type='workslip',
            parent__isnull=True,
        )
        for ow in orphan_workslips:
            wd = ow.work_data or {}
            src_id = wd.get('ws_source_estimate_id')
            if src_id and int(src_id) == root_estimate.id and ow.id not in existing_ws_ids:
                # Fix the parent relationship
                ow.parent = root_estimate
                ow.save(update_fields=['parent'])
                workslips.append(ow)
                existing_ws_ids.add(ow.id)
        # Re-sort workslips by workslip_number after adding orphans
        workslips.sort(key=lambda w: w.workslip_number or 0)

        # Bills: children of root_estimate or children of any of its workslips
        workslip_ids = [ws.id for ws in workslips]
        bills = list(
            SavedWork.objects.filter(
                Q(parent=root_estimate, work_type='bill') |
                Q(parent_id__in=workslip_ids, work_type='bill')
            ).filter(organization=org, user=user).order_by('bill_number')
        )

        # Also find orphan bills that reference this estimate or its workslips
        existing_bill_ids = {b.id for b in bills}
        orphan_bills = SavedWork.objects.filter(
            organization=org, user=user,
            work_type='bill',
            parent__isnull=True,
        )
        for ob in orphan_bills:
            bd = ob.work_data or {}
            src_id = bd.get('bill_source_work_id')
            if src_id:
                src_id = int(src_id)
                if (src_id == root_estimate.id or src_id in existing_ws_ids) and ob.id not in existing_bill_ids:
                    ob.parent = root_estimate
                    ob.save(update_fields=['parent'])
                    bills.append(ob)
                    existing_bill_ids.add(ob.id)
        bills.sort(key=lambda b: b.bill_number or 0)

    # Get workflow chain (parents)
    parent_chain = []
    current = saved_work.parent
    while current:
        parent_chain.insert(0, current)
        current = current.parent

    children = saved_work.children.all()

    # Check subscription access for this work
    access_result = check_saved_work_access(user, saved_work)

    # Module access checks
    module_access = {}
    try:
        from subscriptions.services import SubscriptionService
        for wt, mc in WORK_TYPE_TO_MODULE.items():
            result = SubscriptionService.check_access(user, mc)
            module_access[wt] = result.get('ok', False)
    except Exception:
        for wt in WORK_TYPE_TO_MODULE:
            module_access[wt] = True

    # ===========================================================
    # BILL PREVIEW: Build preview rows for workslip/bill types
    # Shows data as it would appear in the generated Excel bill
    # ===========================================================
    bill_preview_rows = []
    bill_preview_number = 0
    bill_preview_total = 0.0
    previous_bill_rows = []  # For Bill 2+ to show deductions

    if saved_work.work_type == 'workslip':
        work_data = saved_work.work_data or {}
        ws_rows = work_data.get('ws_estimate_rows', [])
        ws_exec = work_data.get('ws_exec_map', {}) or {}
        bill_preview_number = saved_work.workslip_number or 1

        for idx, row in enumerate(ws_rows):
            key = row.get('key', f'saved_{idx}')
            exec_qty = ws_exec.get(key, 0)
            try:
                exec_qty = float(exec_qty) if exec_qty else 0.0
            except (ValueError, TypeError):
                exec_qty = 0.0
            if exec_qty <= 0:
                continue
            rate = float(row.get('rate', 0) or 0)
            amount = exec_qty * rate
            bill_preview_total += amount
            bill_preview_rows.append({
                'sl': len(bill_preview_rows) + 1,
                'name': row.get('desc') or row.get('display_name') or row.get('item_name', ''),
                'desc': row.get('desc', ''),
                'unit': row.get('unit', 'Nos'),
                'qty': exec_qty,
                'rate': rate,
                'amount': amount,
                'key': key,
            })

        # For Bill 2+, find the previous bill's data for deductions
        if bill_preview_number > 1:
            prev_bill = SavedWork.objects.filter(
                organization=org, user=user, work_type='bill',
                bill_number=bill_preview_number - 1,
                parent=root_estimate,
            ).first()
            if not prev_bill:
                # Check if the previous bill is a child of a workslip
                for ws in workslips:
                    prev_bill = SavedWork.objects.filter(
                        organization=org, user=user, work_type='bill',
                        bill_number=bill_preview_number - 1,
                        parent=ws,
                    ).first()
                    if prev_bill:
                        break

            if prev_bill:
                prev_data = prev_bill.work_data or {}
                prev_ws_rows = prev_data.get('ws_estimate_rows', [])
                prev_exec = prev_data.get('ws_exec_map', prev_data.get('bill_ws_exec_map', {})) or {}
                for pidx, prow in enumerate(prev_ws_rows):
                    pkey = prow.get('key', f'saved_{pidx}')
                    pqty = prev_exec.get(pkey, 0)
                    try:
                        pqty = float(pqty) if pqty else 0.0
                    except (ValueError, TypeError):
                        pqty = 0.0
                    previous_bill_rows.append({
                        'key': pkey,
                        'name': prow.get('display_name') or prow.get('item_name', ''),
                        'qty': pqty,
                    })

    elif saved_work.work_type == 'bill':
        work_data = saved_work.work_data or {}
        ws_rows = work_data.get('bill_ws_rows', work_data.get('ws_estimate_rows', []))
        ws_exec = work_data.get('bill_ws_exec_map', work_data.get('ws_exec_map', {})) or {}
        bill_preview_number = saved_work.bill_number or 1

        for idx, row in enumerate(ws_rows):
            key = row.get('key', f'saved_{idx}')
            exec_qty = ws_exec.get(key, 0)
            try:
                exec_qty = float(exec_qty) if exec_qty else 0.0
            except (ValueError, TypeError):
                exec_qty = 0.0
            if exec_qty <= 0:
                continue
            rate = float(row.get('rate', 0) or 0)
            amount = exec_qty * rate
            bill_preview_total += amount
            bill_preview_rows.append({
                'sl': len(bill_preview_rows) + 1,
                'name': row.get('desc') or row.get('display_name') or row.get('item_name', ''),
                'desc': row.get('desc', ''),
                'unit': row.get('unit', 'Nos'),
                'qty': exec_qty,
                'rate': rate,
                'amount': amount,
                'key': key,
            })

    # Determine last workslip for the W button prompt
    last_workslip = workslips[-1] if workslips else None

    context = {
        'work': saved_work,
        'root_estimate': root_estimate,
        'workslips': workslips,
        'bills': bills,
        'last_workslip': last_workslip,
        'parent_chain': parent_chain,
        'children': children,
        'can_generate_workslip': saved_work.can_generate_workslip(),
        'can_generate_bill': saved_work.can_generate_bill(),
        'has_subscription_access': access_result['ok'],
        'subscription_reason': access_result.get('reason', ''),
        'module_code': access_result.get('module_code'),
        'module_access': module_access,
        'bill_preview_rows': bill_preview_rows,
        'bill_preview_number': bill_preview_number,
        'bill_preview_total': bill_preview_total,
        'previous_bill_rows': json.dumps(previous_bill_rows),
    }

    return render(request, 'core/saved_works/detail.html', context)


# ==============================================================================
# BILL GENERATION FROM SAVED WORKS (B1, B2, B3 FLOW)
# ==============================================================================

@login_required(login_url='login')
def generate_next_bill_from_saved(request, work_id):
    """
    Generate the next bill from a saved bill.
    For example, if work_id is Bill-1, this generates Bill-2.
    Saved Works acts as navigation layer only — passes IDs to existing bill engine.
    """
    import logging
    logger = logging.getLogger(__name__)

    org = get_org_from_request(request)
    user = request.user

    saved_work = get_object_or_404(SavedWork, id=work_id, organization=org, user=user)

    # Validate: must be a bill
    if saved_work.work_type != 'bill':
        return JsonResponse({
            'success': False,
            'error': 'Only saved bills can generate next bills.'
        }, status=400)

    if saved_work.status != 'completed':
        return JsonResponse({
            'success': False,
            'error': 'Bill must be completed before generating the next bill.'
        }, status=400)

    current_bill_number = saved_work.bill_number or 1
    next_bill_number = current_bill_number + 1

    logger.info(
        f"[NEXT_BILL] Generating Bill-{next_bill_number} from saved Bill-{current_bill_number} (ID: {work_id})"
    )

    work_data = saved_work.work_data or {}

    # Find the source workslip for this bill chain — walk up parent to find the workslip
    source_workslip_id = work_data.get('source_workslip_id')
    if not source_workslip_id and saved_work.parent:
        # If this bill's parent is a workslip, use that
        if saved_work.parent.work_type == 'workslip':
            source_workslip_id = saved_work.parent.id
        elif saved_work.parent.work_type in ('new_estimate', 'temporary_works', 'amc'):
            # Bill parented to an estimate — try to find the newest completed workslip
            newest_ws = SavedWork.objects.filter(
                organization=org, user=user,
                work_type='workslip',
                parent=saved_work.parent,
                status='completed',
            ).order_by('-workslip_number').first()
            if newest_ws:
                source_workslip_id = newest_ws.id

    # Pass minimal info to bill session — let existing bill engine handle calculations
    request.session['bill_source_work_id'] = saved_work.id
    request.session['bill_source_work_type'] = 'bill'
    request.session['bill_source_work_name'] = saved_work.name
    request.session['bill_from_workslip'] = True
    request.session['bill_previous_bill_id'] = saved_work.id
    request.session['bill_previous_bill_number'] = current_bill_number
    request.session['bill_target_number'] = next_bill_number
    request.session['bill_sequence_number'] = next_bill_number

    # CRITICAL: Set bill_parent_work_id so save_work() can link the bill to its parent
    # Use source workslip if available, otherwise fall back to current bill's parent
    if source_workslip_id:
        request.session['bill_parent_work_id'] = int(source_workslip_id)
    elif saved_work.parent_id:
        request.session['bill_parent_work_id'] = saved_work.parent_id
    
    # Also carry the source estimate ID for orphan recovery
    ws_source_est = work_data.get('ws_source_estimate_id')
    if ws_source_est:
        request.session['ws_source_estimate_id'] = ws_source_est

    # Carry over bill data for the existing engine to use
    if 'bill_ws_rows' in work_data:
        request.session['bill_ws_rows'] = work_data['bill_ws_rows']
    if 'bill_ws_exec_map' in work_data:
        request.session['bill_ws_exec_map'] = work_data['bill_ws_exec_map']
    if 'bill_ws_tp_percent' in work_data:
        request.session['bill_ws_tp_percent'] = work_data['bill_ws_tp_percent']
    if 'bill_ws_tp_type' in work_data:
        request.session['bill_ws_tp_type'] = work_data['bill_ws_tp_type']
    # Carry over metadata for bill header
    if 'bill_ws_metadata' in work_data:
        request.session['bill_ws_metadata'] = work_data['bill_ws_metadata']

    request.session.modified = True

    messages.success(request, f'Ready to generate Bill-{next_bill_number} from "{saved_work.name}".')
    return redirect(reverse('bill') + '?from_saved=1')


@login_required(login_url='login')
@require_POST
def saved_work_action(request, work_id):
    """
    Handle AJAX actions from the Saved Works detail page.
    This is the navigation layer that routes to existing module APIs.
    Actions: update_workslip, start_next_workslip, update_bill, start_next_bill
    """
    org = get_org_from_request(request)
    user = request.user

    saved_work = get_object_or_404(SavedWork, id=work_id, organization=org, user=user)

    action = request.POST.get('action', '')

    if action == 'update_estimate':
        # Resume existing estimate — same as resume_saved_work
        return JsonResponse({
            'success': True,
            'redirect_url': reverse('resume_saved_work', kwargs={'work_id': work_id}),
            'action': 'update_estimate',
        })

    elif action == 'update_workslip':
        # Resume existing workslip
        return JsonResponse({
            'success': True,
            'redirect_url': reverse('resume_saved_work', kwargs={'work_id': work_id}),
            'action': 'update_workslip',
        })

    elif action == 'start_next_workslip':
        # Validate: workslip must be completed
        if saved_work.work_type != 'workslip':
            return JsonResponse({
                'success': False,
                'error': 'Only completed workslips can generate next workslips.'
            }, status=400)
        return JsonResponse({
            'success': True,
            'redirect_url': reverse('generate_next_workslip_from_saved', kwargs={'work_id': work_id}),
            'action': 'start_next_workslip',
        })

    elif action == 'update_bill':
        # Resume existing bill
        return JsonResponse({
            'success': True,
            'redirect_url': reverse('resume_saved_work', kwargs={'work_id': work_id}),
            'action': 'update_bill',
        })

    elif action == 'start_next_bill':
        # Generate next bill from existing bill
        if saved_work.work_type != 'bill':
            return JsonResponse({
                'success': False,
                'error': 'Only completed bills can generate next bills.'
            }, status=400)
        return JsonResponse({
            'success': True,
            'redirect_url': reverse('generate_next_bill_from_saved', kwargs={'work_id': work_id}),
            'action': 'start_next_bill',
        })

    elif action == 'generate_first_bill':
        # Generate Bill-1 from a workslip
        if saved_work.work_type != 'workslip':
            return JsonResponse({
                'success': False,
                'error': 'Only workslips can generate bills.'
            }, status=400)
        return JsonResponse({
            'success': True,
            'redirect_url': reverse('generate_bill_from_saved', kwargs={'work_id': work_id}),
            'action': 'generate_first_bill',
        })

    return JsonResponse({
        'success': False,
        'error': f'Unknown action: {action}'
    }, status=400)


@login_required(login_url='login')
@require_POST
def save_with_parent(request):
    """
    Save current work with a parent reference (for workflow chain).
    Called when saving a workslip generated from an estimate, or bill from workslip.
    """
    org = get_org_from_request(request)
    user = request.user
    
    work_name = request.POST.get('work_name', '').strip()
    work_type = request.POST.get('work_type', '')
    parent_id = request.POST.get('parent_id')
    folder_id = request.POST.get('folder_id')
    notes = request.POST.get('notes', '').strip()
    category = request.POST.get('category', 'electrical')
    
    if not work_name:
        return JsonResponse({'success': False, 'error': 'Work name is required.'})
    
    if work_type not in dict(SavedWork.WORK_TYPE_CHOICES):
        return JsonResponse({'success': False, 'error': 'Invalid work type.'})
    
    # Get parent if specified
    parent = None
    if parent_id:
        parent = get_object_or_404(SavedWork, id=parent_id, organization=org, user=user)
    
    # Get folder if specified
    folder = None
    if folder_id:
        folder = get_object_or_404(WorkFolder, id=folder_id, organization=org, user=user)
    
    # Collect work data
    work_data = collect_work_data(request, work_type)
    progress_percent = calculate_progress(work_data, work_type)
    last_step = get_last_step(request, work_type)
    
    # Auto-inherit parent's folder if no folder specified
    if not folder and parent and parent.folder:
        folder = parent.folder

    # Determine workslip_number / bill_number from session
    workslip_number = 1
    bill_number = 1
    if work_type == 'workslip':
        workslip_number = request.session.get('ws_target_workslip', 1) or 1
    elif work_type == 'bill':
        bill_number = request.session.get('bill_target_number', 1) or 1

    # Create saved work with parent reference
    saved_work = SavedWork.objects.create(
        organization=org,
        user=user,
        folder=folder,
        parent=parent,
        name=work_name,
        work_type=work_type,
        work_data=work_data,
        category=category,
        notes=notes,
        progress_percent=progress_percent,
        last_step=last_step,
        workslip_number=workslip_number,
        bill_number=bill_number,
    )
    
    # Store saved work ID in session
    request.session['current_saved_work_id'] = saved_work.id
    
    return JsonResponse({
        'success': True,
        'work_id': saved_work.id,
        'message': f'Work "{work_name}" saved successfully!'
    })
