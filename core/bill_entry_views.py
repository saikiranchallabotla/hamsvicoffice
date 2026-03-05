# core/bill_entry_views.py
"""
Bill Entry Views - Allow sequential bill creation without file uploads.
Work with SavedWork model to maintain workflow chain: Estimate → Workslip → Bill
"""

import json
from decimal import Decimal
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST, require_GET
from django.http import JsonResponse
from django.contrib import messages
from django.utils import timezone
from django.urls import reverse
from django.db.models import Q

from .models import SavedWork, Organization
from .saved_works_views import get_org_from_request, check_saved_work_access


@login_required(login_url='login')
def bill_entry(request, work_id):
    """
    Display bill entry form for creating a bill from a workslip or estimate.
    Allows sequential quantity entry without file uploads.
    
    Args:
        work_id: ID of the parent work (Estimate or Workslip)
    
    Flow:
        1. User selects a workslip/estimate
        2. System loads the items and previous bill data (if Bill 2+)
        3. User enters quantities and deductions
        4. User saves bill (goes to bill_entry_save)
    """
    org = get_org_from_request(request)
    user = request.user
    
    # Get the parent work (source workslip or estimate)
    try:
        source_work = get_object_or_404(SavedWork, id=work_id, organization=org, user=user)
    except:
        messages.error(request, 'Workslip or Estimate not found.')
        return redirect('saved_works_list')
    
    # Validate source work type
    if source_work.work_type not in ['workslip', 'new_estimate']:
        messages.error(request, 'Only workslips and estimates can generate bills.')
        return redirect('saved_work_detail', work_id=work_id)
    
    work_data = source_work.work_data or {}
    
    # Get items from source work
    if source_work.work_type == 'workslip':
        ws_rows = work_data.get('ws_estimate_rows', [])
        ws_exec = work_data.get('ws_exec_map', {})
        bill_number = source_work.workslip_number or 1
        item_type = 'workslip'
    else:
        # From estimate
        ws_rows = work_data.get('fetched_items', [])
        ws_exec = work_data.get('qty_map', {})
        bill_number = 1
        item_type = 'estimate'
    
    if not ws_rows:
        messages.error(request, f'{source_work.work_type.title()} has no items.')
        return redirect('saved_work_detail', work_id=work_id)
    
    # Build bill items from workslip quantities (including supplemental items)
    bill_items = []
    for idx, row in enumerate(ws_rows):
        key = row.get('key') or row.get('item_name') or f'item_{idx}'
        qty_exec = ws_exec.get(key, 0)
        try:
            qty_exec = float(qty_exec) if qty_exec else 0.0
        except (ValueError, TypeError):
            qty_exec = 0.0
        
        # Include ALL items from workslip, including supplemental items
        rate = float(row.get('rate', 0) or 0)
        item_name = row.get('display_name') or row.get('item_name') or row.get('desc') or 'Item'
        unit = row.get('unit') or 'Nos'
        
        bill_items.append({
            'key': key,
            'item_name': item_name,
            'unit': unit,
            'qty_exec': qty_exec,
            'rate': rate,
            'is_supplemental': 'Supplemental' in (row.get('label', '') or ''),
        })
    
    # Get previous bill (if Bill 2+)
    prev_bill = None
    prev_bill_items = []
    
    if bill_number > 1:
        # Find the previous bill for this source
        if source_work.work_type == 'workslip':
            # Bill N links to Workslip N
            prev_bill = SavedWork.objects.filter(
                organization=org,
                user=user,
                work_type='bill',
                bill_number=bill_number - 1,
                parent=source_work
            ).first()
        else:
            # From estimate
            prev_bill = SavedWork.objects.filter(
                organization=org,
                user=user,
                work_type='bill',
                bill_number=bill_number - 1,
                parent=source_work
            ).first()
        
        if prev_bill:
            prev_data = prev_bill.work_data or {}
            prev_rows = prev_data.get('bill_ws_rows', prev_data.get('ws_estimate_rows', []))
            prev_exec = prev_data.get('bill_ws_exec_map', prev_data.get('ws_exec_map', {}))
            
            # Build previous bill items
            for idx, row in enumerate(prev_rows):
                key = row.get('key', f'item_{idx}')
                qty = prev_exec.get(key, 0)
                try:
                    qty = float(qty) if qty else 0.0
                except (ValueError, TypeError):
                    qty = 0.0
                
                if qty <= 0:
                    continue
                
                prev_bill_items.append({
                    'key': key,
                    'item_name': row.get('display_name') or row.get('item_name') or row.get('desc', ''),
                    'qty': qty,
                })
    
    # Build workflow chain for breadcrumb
    workflow_chain = []
    root_estimate = source_work
    
    if source_work.work_type == 'workslip':
        root_estimate = source_work.parent or source_work
    
    if root_estimate and root_estimate.work_type == 'new_estimate':
        workflow_chain.append({
            'id': root_estimate.id,
            'type': 'estimate',
            'label': root_estimate.name,
            'short_label': 'Estimate',
            'icon': 'bi-file-earmark-spreadsheet',
        })
    
    workflow_chain.append({
        'id': source_work.id,
        'type': 'workslip',
        'label': f'Workslip-{source_work.workslip_number}' if source_work.work_type == 'workslip' else 'Workslip',
        'short_label': f'W{source_work.workslip_number}' if source_work.work_type == 'workslip' else 'W1',
        'icon': 'bi-file-earmark-text',
    })
    
    workflow_chain.append({
        'id': None,
        'type': 'bill',
        'label': f'Bill-{bill_number}',
        'short_label': f'B{bill_number}',
        'icon': 'bi-receipt',
    })
    
    # Bill type label
    bill_type_label = ''
    if bill_number == 1:
        bill_type_label = 'First & Part Bill'
    elif bill_number == 2:
        bill_type_label = 'Second & Final Bill' if prev_bill and prev_bill.bill_type == 'first_part' else 'Second & Part Bill'
    else:
        bill_type_label = f'{bill_number}th & Part Bill'
    
    # Load existing bill data if this bill was previously saved
    existing_bill = None
    if source_work.work_type == 'workslip':
        existing_bill = SavedWork.objects.filter(
            organization=org,
            user=user,
            work_type='bill',
            bill_number=bill_number,
            parent=source_work
        ).first()
    
    # If bill exists, load saved data
    mb_no = ''
    mb_from_page = ''
    mb_to_page = ''
    doi = ''
    doc = ''
    domr = ''
    dobr = ''
    
    if existing_bill:
        bill_work_data = existing_bill.work_data or {}
        mb_no = bill_work_data.get('mb_no', '')
        mb_from_page = bill_work_data.get('mb_from_page', '')
        mb_to_page = bill_work_data.get('mb_to_page', '')
        doi = bill_work_data.get('doi', '')
        doc = bill_work_data.get('doc', '')
        domr = bill_work_data.get('domr', '')
        dobr = bill_work_data.get('dobr', '')
        
        # Load saved quantities and deductions
        bill_exec = bill_work_data.get('bill_ws_exec_map', {})
        bill_deduct = bill_work_data.get('bill_deduct_map', {})
        
        # Update bill_items with saved quantities
        for item in bill_items:
            key = item['key']
            if key in bill_exec:
                item['qty_exec'] = bill_exec[key]

    context = {
        'work_id': work_id,
        'source_work': source_work,
        'bill_number': bill_number,
        'bill_type': 'first_part' if bill_number == 1 else 'nth_part',
        'bill_type_label': bill_type_label,
        'work_name': source_work.name,
        'created_date': timezone.now().strftime('%d %b %Y'),
        'bill_items': bill_items,
        'bill_items_json': json.dumps(bill_items),
        'prev_bill': prev_bill,
        'prev_bill_items': prev_bill_items,
        'prev_bill_items_json': json.dumps(prev_bill_items),
        'workflow_chain': workflow_chain,
        'source_workslip': source_work if source_work.work_type == 'workslip' else None,
        'item_count': len(bill_items),
        'mb_no': mb_no,
        'mb_from_page': mb_from_page,
        'mb_to_page': mb_to_page,
        'doi': doi,
        'doc': doc,
        'domr': domr,
        'dobr': dobr,
    }
    
    return render(request, 'core/bill_entry_new.html', context)


@login_required(login_url='login')
@require_POST
def bill_entry_save(request, work_id):
    """
    Save bill data (quantities and deductions) and create SavedWork for bill.
    
    POST data:
        - action: 'save_bill_data'
        - bill_exec_map: JSON map of {item_key: quantity}
        - bill_deduct_map: JSON map of {item_key: deduct_quantity}
        - bill_rate_map: JSON map of {item_key: rate}
        - mb_no, mb_from_page, mb_to_page: Measurement book details
        - doi, doc, domr, dobr: Dates
    """
    org = get_org_from_request(request)
    user = request.user
    
    try:
        source_work = get_object_or_404(SavedWork, id=work_id, organization=org, user=user)
    except:
        return JsonResponse({'success': False, 'error': 'Work not found'}, status=404)
    
    if source_work.work_type not in ['workslip', 'new_estimate']:
        return JsonResponse({'success': False, 'error': 'Invalid source work type'}, status=400)
    
    # Parse submitted data
    try:
        bill_exec_map = json.loads(request.POST.get('bill_exec_map', '{}'))
        bill_deduct_map = json.loads(request.POST.get('bill_deduct_map', '{}'))
        bill_rate_map = json.loads(request.POST.get('bill_rate_map', '{}'))
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Invalid JSON data'}, status=400)
    
    # Validate that at least one quantity is entered
    has_qty = any(float(q or 0) > 0 for q in bill_exec_map.values())
    if not has_qty:
        return JsonResponse({
            'success': False, 
            'error': 'Please enter at least one quantity'
        }, status=400)
    
    # Get source work data
    work_data = source_work.work_data or {}
    
    # Determine bill number
    if source_work.work_type == 'workslip':
        bill_number = source_work.workslip_number or 1
    else:
        bill_number = 1
    
    # Build bill data to save
    bill_data = {
        'bill_number': bill_number,
        'bill_type': 'first_part' if bill_number == 1 else 'nth_part',
        'bill_exec_map': bill_exec_map,
        'bill_deduct_map': bill_deduct_map,
        'bill_rate_map': bill_rate_map,
        'mb_no': request.POST.get('mb_no', ''),
        'mb_from_page': request.POST.get('mb_from_page', ''),
        'mb_to_page': request.POST.get('mb_to_page', ''),
        'doi': request.POST.get('doi', ''),
        'doc': request.POST.get('doc', ''),
        'domr': request.POST.get('domr', ''),
        'dobr': request.POST.get('dobr', ''),
        # Copy source work data for bill generation
        'bill_ws_rows': work_data.get('ws_estimate_rows', work_data.get('fetched_items', [])),
        'bill_ws_exec_map': bill_exec_map,
        'bill_ws_tp_percent': work_data.get('ws_tp_percent', 0),
        'bill_ws_tp_type': work_data.get('ws_tp_type', 'Excess'),
        'bill_ws_metadata': work_data.get('ws_metadata', {}),
        'source_workslip_id': source_work.id if source_work.work_type == 'workslip' else None,
    }
    
    # Create SavedWork for bill
    bill_name = f"Bill-{bill_number} from {source_work.name}"
    
    saved_bill = SavedWork.objects.create(
        organization=org,
        user=user,
        parent=source_work,
        name=bill_name,
        work_type='bill',
        work_data=bill_data,
        category=source_work.category,
        bill_number=bill_number,
        bill_type='first_part' if bill_number == 1 else 'nth_part',
        status='in_progress',
    )
    
    messages.success(request, f'Bill-{bill_number} created successfully!')
    
    return JsonResponse({
        'success': True,
        'work_id': saved_bill.id,
        'redirect_url': reverse('saved_work_detail', kwargs={'work_id': saved_bill.id}),
        'message': f'Bill-{bill_number} saved!'
    })


@login_required(login_url='login')
def start_bill_creation(request, work_id):
    """
    Start bill creation workflow for a workslip.
    Redirects to bill_entry view.
    """
    org = get_org_from_request(request)
    user = request.user
    
    try:
        source_work = get_object_or_404(SavedWork, id=work_id, organization=org, user=user)
    except:
        messages.error(request, 'Workslip not found.')
        return redirect('saved_works_list')
    
    if source_work.work_type != 'workslip':
        messages.error(request, 'Only workslips can generate bills.')
        return redirect('saved_work_detail', work_id=work_id)
    
    return redirect('bill_entry', work_id=work_id)


# ==============================================================================
# WORKSLIP ENTRY VIEWS - Sequential Workslip Creation
# ==============================================================================

@login_required(login_url='login')
def workslip_entry(request, work_id):
    """
    Display workslip entry form for creating a workslip from an estimate.
    Allows sequential quantity entry without file uploads.
    
    Args:
        work_id: ID of the source estimate
    
    Flow:
        1. User selects an estimate
        2. System loads the estimate items
        3. User enters quantities and T.P. percentage
        4. User saves workslip (goes to workslip_entry_save)
    """
    org = get_org_from_request(request)
    user = request.user
    
    # Get the source estimate
    try:
        source_estimate = get_object_or_404(SavedWork, id=work_id, organization=org, user=user)
    except:
        messages.error(request, 'Estimate not found.')
        return redirect('saved_works_list')
    
    # Validate source estimate type
    if source_estimate.work_type != 'new_estimate':
        messages.error(request, 'Only estimates can generate workslips.')
        return redirect('saved_work_detail', work_id=work_id)
    
    work_data = source_estimate.work_data or {}
    
    # Get items from estimate
    estimate_items = work_data.get('fetched_items', [])
    
    if not estimate_items:
        messages.error(request, 'Estimate has no items.')
        return redirect('saved_work_detail', work_id=work_id)
    
    # Determine workslip number
    # Find the highest workslip number for this estimate
    existing_workslips = SavedWork.objects.filter(
        organization=org,
        user=user,
        work_type='workslip',
        parent=source_estimate
    ).order_by('-workslip_number')
    
    if existing_workslips.exists():
        workslip_number = existing_workslips.first().workslip_number + 1
    else:
        workslip_number = 1
    
    # Build workslip items from estimate
    workslip_items = []
    for idx, item in enumerate(estimate_items):
        key = item.get('key') or item.get('item_name') or f'item_{idx}'
        item_name = item.get('display_name') or item.get('item_name') or item.get('desc') or 'Item'
        unit = item.get('unit') or 'Nos'
        rate = float(item.get('rate', 0) or 0)
        
        workslip_items.append({
            'key': key,
            'item_name': item_name,
            'unit': unit,
            'rate': rate,
        })
    
    # Get previous workslip (if Workslip 2+)
    prev_workslip = None
    prev_workslip_items = []
    
    if workslip_number > 1:
        prev_workslip = SavedWork.objects.filter(
            organization=org,
            user=user,
            work_type='workslip',
            parent=source_estimate,
            workslip_number=workslip_number - 1
        ).first()
        
        if prev_workslip:
            prev_data = prev_workslip.work_data or {}
            prev_rows = prev_data.get('ws_estimate_rows', [])
            prev_exec = prev_data.get('ws_exec_map', {})
            
            # Build previous workslip items
            for idx, row in enumerate(prev_rows):
                key = row.get('key', f'item_{idx}')
                qty = prev_exec.get(key, 0)
                try:
                    qty = float(qty) if qty else 0.0
                except (ValueError, TypeError):
                    qty = 0.0
                
                prev_workslip_items.append({
                    'key': key,
                    'item_name': row.get('display_name') or row.get('item_name') or row.get('desc', ''),
                    'qty': qty,
                })
    
    # Build workflow chain
    workflow_chain = [
        {
            'id': source_estimate.id,
            'type': 'estimate',
            'label': source_estimate.name,
            'short_label': 'Estimate',
            'icon': 'bi-file-earmark-spreadsheet',
        },
        {
            'id': None,
            'type': 'workslip',
            'label': f'Workslip-{workslip_number}',
            'short_label': f'W{workslip_number}',
            'icon': 'bi-file-earmark-text',
        }
    ]
    
    context = {
        'work_id': work_id,
        'source_estimate': source_estimate,
        'workslip_number': workslip_number,
        'work_name': source_estimate.name,
        'created_date': timezone.now().strftime('%d %b %Y'),
        'workslip_items': workslip_items,
        'workslip_items_json': json.dumps(workslip_items),
        'prev_workslip': prev_workslip,
        'prev_workslip_items': prev_workslip_items,
        'prev_workslip_items_json': json.dumps(prev_workslip_items),
        'workflow_chain': workflow_chain,
        'item_count': len(workslip_items),
        'tp_percent': 0,
        'tp_type': 'Excess',
    }
    
    return render(request, 'core/workslip_entry.html', context)


@login_required(login_url='login')
@require_POST
def workslip_entry_save(request, work_id):
    """
    Save workslip data (quantities and T.P.) and create SavedWork for workslip.
    
    POST data:
        - action: 'save_workslip_data'
        - ws_exec_map: JSON map of {item_key: quantity}
        - ws_rate_map: JSON map of {item_key: rate}
        - ws_tp_percent: T.P. percentage
        - ws_tp_type: T.P. type (Excess/Deduct)
        - mb_no, mb_from_page, mb_to_page: Measurement book (optional)
    """
    org = get_org_from_request(request)
    user = request.user
    
    try:
        source_estimate = get_object_or_404(SavedWork, id=work_id, organization=org, user=user)
    except:
        return JsonResponse({'success': False, 'error': 'Estimate not found'}, status=404)
    
    if source_estimate.work_type != 'new_estimate':
        return JsonResponse({'success': False, 'error': 'Invalid source estimate'}, status=400)
    
    # Parse submitted data
    try:
        ws_exec_map = json.loads(request.POST.get('ws_exec_map', '{}'))
        ws_rate_map = json.loads(request.POST.get('ws_rate_map', '{}'))
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Invalid JSON data'}, status=400)
    
    # Validate that at least one quantity is entered
    has_qty = any(float(q or 0) > 0 for q in ws_exec_map.values())
    if not has_qty:
        return JsonResponse({
            'success': False, 
            'error': 'Please enter at least one quantity'
        }, status=400)
    
    # Get T.P. data
    ws_tp_percent = float(request.POST.get('ws_tp_percent', 0) or 0)
    ws_tp_type = request.POST.get('ws_tp_type', 'Excess').strip()
    
    # Get source estimate data
    estimate_data = source_estimate.work_data or {}
    estimate_items = estimate_data.get('fetched_items', [])
    
    # Determine workslip number
    existing_workslips = SavedWork.objects.filter(
        organization=org,
        user=user,
        work_type='workslip',
        parent=source_estimate
    ).order_by('-workslip_number')
    
    workslip_number = existing_workslips.first().workslip_number + 1 if existing_workslips.exists() else 1
    
    # Build workslip data to save
    # Store estimate items with key preservation
    ws_rows = []
    for item in estimate_items:
        key = item.get('key', f'item_{len(ws_rows)}')
        ws_rows.append({
            'key': key,
            'item_name': item.get('item_name', ''),
            'display_name': item.get('display_name', ''),
            'desc': item.get('desc', ''),
            'unit': item.get('unit', 'Nos'),
            'qty_est': float(item.get('qty_est', 0) or 0),
            'rate': float(item.get('rate', 0) or 0),
        })
    
    workslip_data = {
        'workslip_number': workslip_number,
        'ws_estimate_rows': ws_rows,
        'ws_exec_map': ws_exec_map,
        'ws_rate_map': ws_rate_map,
        'ws_tp_percent': ws_tp_percent,
        'ws_tp_type': ws_tp_type,
        'ws_metadata': {
            'work_name': source_estimate.name,
            'estimate_amount': str(estimate_data.get('total_amount', '')),
            'admin_sanction': estimate_data.get('admin_sanction', ''),
            'tech_sanction': estimate_data.get('tech_sanction', ''),
            'agreement': estimate_data.get('agreement', ''),
            'agency_name': estimate_data.get('agency_name', ''),
        },
        'mb_no': request.POST.get('mb_no', ''),
        'mb_from_page': request.POST.get('mb_from_page', ''),
        'mb_to_page': request.POST.get('mb_to_page', ''),
        # Store parent estimate reference
        'ws_source_estimate_id': source_estimate.id,
    }
    
    # Create SavedWork for workslip
    workslip_name = f"Workslip-{workslip_number} from {source_estimate.name}"
    
    saved_workslip = SavedWork.objects.create(
        organization=org,
        user=user,
        parent=source_estimate,
        name=workslip_name,
        work_type='workslip',
        work_data=workslip_data,
        category=source_estimate.category,
        workslip_number=workslip_number,
        status='in_progress',
    )
    
    messages.success(request, f'Workslip-{workslip_number} created successfully!')
    
    return JsonResponse({
        'success': True,
        'work_id': saved_workslip.id,
        'redirect_url': reverse('saved_work_detail', kwargs={'work_id': saved_workslip.id}),
        'message': f'Workslip-{workslip_number} saved!'
    })


@login_required(login_url='login')
def start_workslip_creation(request, work_id):
    """
    Start workslip creation workflow for an estimate.
    Redirects to workslip_entry view.
    """
    org = get_org_from_request(request)
    user = request.user
    
    try:
        source_estimate = get_object_or_404(SavedWork, id=work_id, organization=org, user=user)
    except:
        messages.error(request, 'Estimate not found.')
        return redirect('saved_works_list')
    
    if source_estimate.work_type != 'new_estimate':
        messages.error(request, 'Only estimates can generate workslips.')
        return redirect('saved_work_detail', work_id=work_id)
    
    return redirect('workslip_entry', work_id=work_id)
