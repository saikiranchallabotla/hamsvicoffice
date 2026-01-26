# datasets/views.py
"""
Views for datasets app - State selection and SOR rate management.
"""

import json
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods, require_POST
from django.contrib import messages

from .models import State, SORRateBook, ModuleDatasetConfig, UserStatePreference


# ==============================================================================
# STATE SELECTION API
# ==============================================================================

@login_required
def get_available_states(request):
    """
    Get list of available states for a module and work type.
    
    Query params:
        - module_code: e.g., 'estimate', 'workslip'
        - work_type: e.g., 'electrical', 'civil'
    
    Returns JSON: {
        'states': [{'code': 'TS', 'name': 'Telangana', 'is_default': True}, ...],
        'user_preference': 'TS'  # User's currently selected state
    }
    """
    module_code = request.GET.get('module_code', '')
    work_type = request.GET.get('work_type', '')
    
    states = []
    
    try:
        # If module and work type provided, filter by ModuleDatasetConfig
        if module_code and work_type:
            available_states = ModuleDatasetConfig.get_available_states_for_module(
                module_code, work_type
            )
            if available_states.exists():
                states = [
                    {'code': s.code, 'name': s.name, 'is_default': s.is_default}
                    for s in available_states
                ]
        
        # If no states from config, try SORRateBook
        if not states and work_type:
            base_work_type = work_type.replace('temp_', '').replace('amc_', '')
            sor_states = State.objects.filter(
                sor_rate_books__work_type=base_work_type,
                sor_rate_books__is_active=True,
                sor_rate_books__status='published'
            ).distinct()
            
            if sor_states.exists():
                states = [
                    {'code': s.code, 'name': s.name, 'is_default': s.is_default}
                    for s in sor_states.order_by('display_order', 'name')
                ]
        
        # Fall back to all active states
        if not states:
            all_states = State.get_active_states()
            states = [
                {'code': s.code, 'name': s.name, 'is_default': s.is_default}
                for s in all_states
            ]
    except Exception:
        # Default to Telangana if anything fails
        states = [{'code': 'TS', 'name': 'Telangana', 'is_default': True}]
    
    # Get user's preference
    user_preference = None
    try:
        pref = UserStatePreference.objects.filter(user=request.user).first()
        if pref:
            if module_code:
                state = pref.get_state_for_module(module_code)
            else:
                state = pref.preferred_state
            user_preference = state.code if state else None
    except Exception:
        pass
    
    return JsonResponse({
        'states': states,
        'user_preference': user_preference,
        'default': next((s['code'] for s in states if s['is_default']), 
                       states[0]['code'] if states else 'TS')
    })


@login_required
@require_POST
def set_state_preference(request):
    """
    Set user's state preference.
    
    POST body (JSON):
        - state_code: 'TS', 'AP', etc.
        - module_code: (optional) Set preference for specific module
    
    Returns JSON: {'success': True, 'message': '...'}
    """
    try:
        data = json.loads(request.body)
        state_code = data.get('state_code')
        module_code = data.get('module_code')
        
        if not state_code:
            return JsonResponse({'success': False, 'error': 'state_code required'}, status=400)
        
        # Validate state exists
        state = State.objects.filter(code=state_code, is_active=True).first()
        if not state:
            return JsonResponse({'success': False, 'error': f'State {state_code} not found'}, status=404)
        
        # Get or create user preference
        pref = UserStatePreference.get_or_create_for_user(request.user)
        
        if module_code:
            # Set module-specific preference
            pref.set_state_for_module(module_code, state_code)
            message = f'Set {module_code} to use {state.name} SOR rates'
        else:
            # Set general preference
            pref.preferred_state = state
            pref.save(update_fields=['preferred_state', 'updated_at'])
            message = f'Set default state to {state.name}'
        
        return JsonResponse({'success': True, 'message': message})
    
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Invalid JSON'}, status=400)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required
def get_user_state_preference(request):
    """
    Get user's current state preferences.
    
    Returns JSON: {
        'preferred_state': {'code': 'TS', 'name': 'Telangana'},
        'module_states': {'estimate': 'TS', 'workslip': 'AP'}
    }
    """
    try:
        pref = UserStatePreference.objects.filter(user=request.user).first()
        
        if pref:
            preferred_state = None
            if pref.preferred_state:
                preferred_state = {
                    'code': pref.preferred_state.code,
                    'name': pref.preferred_state.name
                }
            
            return JsonResponse({
                'preferred_state': preferred_state,
                'module_states': pref.module_states or {}
            })
        else:
            # No preference set, return default
            default_state = State.get_default()
            return JsonResponse({
                'preferred_state': {
                    'code': default_state.code,
                    'name': default_state.name
                } if default_state else None,
                'module_states': {}
            })
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


# ==============================================================================
# SOR RATE BOOK VIEWS
# ==============================================================================

@login_required
def get_available_sor_books(request):
    """
    Get available SOR rate books for a state and work type.
    
    Query params:
        - state_code: 'TS', 'AP', etc.
        - work_type: 'electrical', 'civil', etc.
    
    Returns JSON: {
        'rate_books': [
            {'id': '...', 'name': '...', 'financial_year': '2024-25', 'is_default': True},
            ...
        ]
    }
    """
    state_code = request.GET.get('state_code')
    work_type = request.GET.get('work_type')
    
    queryset = SORRateBook.objects.filter(
        is_active=True,
        status='published'
    )
    
    if state_code:
        queryset = queryset.filter(state__code=state_code)
    
    if work_type:
        queryset = queryset.filter(work_type=work_type)
    
    rate_books = [
        {
            'id': str(rb.id),
            'code': rb.code,
            'name': rb.name,
            'state': rb.state.code,
            'state_name': rb.state.name,
            'work_type': rb.work_type,
            'financial_year': rb.financial_year,
            'is_default': rb.is_default,
            'total_items': rb.total_items
        }
        for rb in queryset.order_by('state', '-is_default', '-year')
    ]
    
    return JsonResponse({'rate_books': rate_books})


# ==============================================================================
# STATE SELECTION PAGE (for settings)
# ==============================================================================

@login_required
def state_selection_page(request):
    """
    Page for users to select their preferred state.
    """
    states = State.get_active_states()
    
    # Get current preference
    try:
        pref = UserStatePreference.objects.filter(user=request.user).first()
        current_state = pref.preferred_state if pref else State.get_default()
    except Exception:
        current_state = None
    
    if request.method == 'POST':
        state_code = request.POST.get('state_code')
        if state_code:
            state = State.objects.filter(code=state_code, is_active=True).first()
            if state:
                pref = UserStatePreference.get_or_create_for_user(request.user)
                pref.preferred_state = state
                pref.save()
                messages.success(request, f'State preference updated to {state.name}')
                return redirect('state_selection')
    
    return render(request, 'datasets/state_selection.html', {
        'states': states,
        'current_state': current_state
    })


# ==============================================================================
# CONTEXT PROCESSOR FOR GLOBAL STATE ACCESS
# ==============================================================================

def state_context(request):
    """
    Context processor to add state info to all templates.
    Add to settings.TEMPLATES['OPTIONS']['context_processors'].
    """
    context = {
        'available_states': [],
        'current_state': None,
    }
    
    if hasattr(request, 'user') and request.user.is_authenticated:
        try:
            states = State.get_active_states()
            context['available_states'] = states
            
            pref = UserStatePreference.objects.filter(user=request.user).first()
            if pref and pref.preferred_state:
                context['current_state'] = pref.preferred_state
            else:
                context['current_state'] = State.get_default()
        except Exception:
            pass
    
    return context
