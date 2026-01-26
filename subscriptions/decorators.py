# subscriptions/decorators.py
"""
View decorators for module access control and subscription checks.

Usage:
    @module_required('estimate')
    def generate_estimate(request):
        ...

    @subscription_required
    def premium_feature(request):
        ...

    @admin_required
    def admin_dashboard(request):
        ...
"""

from functools import wraps
from django.shortcuts import redirect
from django.http import JsonResponse
from django.contrib import messages
from django.urls import reverse


def module_required(module_code, record_usage=False, action=None):
    """
    Decorator to check if user has access to a specific module.
    
    Args:
        module_code: Module code to check (e.g., 'estimate', 'workslip')
        record_usage: Whether to record usage on successful access
        action: Action name for usage logging (default: view function name)
    
    Usage:
        @module_required('estimate')
        def my_view(request):
            ...
        
        @module_required('estimate', record_usage=True, action='generate')
        def generate_estimate(request):
            ...
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            from subscriptions.services import SubscriptionService
            
            if not request.user.is_authenticated:
                if _is_ajax(request):
                    return JsonResponse({
                        'ok': False,
                        'code': 'AUTH_REQUIRED',
                        'reason': 'Please log in to continue.',
                        'redirect': reverse('login')
                    }, status=401)
                messages.warning(request, 'Please log in to access this feature.')
                return redirect('login')
            
            # Check access
            result = SubscriptionService.check_access(request.user, module_code)
            
            if not result['ok']:
                # Handle different error codes
                code = result.get('code', 'ERROR')
                
                if _is_ajax(request):
                    return JsonResponse({
                        'ok': False,
                        'code': code,
                        'reason': result['reason'],
                        'data': result.get('data', {}),
                        'redirect': reverse('module_access', kwargs={'module_code': module_code})
                    }, status=403)
                
                # Show appropriate message
                if code == 'NO_SUBSCRIPTION':
                    data = result.get('data', {})
                    if data.get('trial_available'):
                        messages.info(
                            request,
                            f"Start your free {data.get('trial_days', 7)}-day trial to access this feature."
                        )
                    else:
                        messages.warning(request, 'Please subscribe to access this feature.')
                elif code == 'USAGE_LIMIT':
                    messages.warning(request, 'Monthly usage limit reached. Please upgrade your plan.')
                else:
                    messages.error(request, result['reason'])
                
                return redirect('module_access', module_code=module_code)
            
            # Record usage if requested
            if record_usage:
                usage_action = action or view_func.__name__
                SubscriptionService.record_usage(
                    user=request.user,
                    module_code=module_code,
                    action=usage_action,
                    request=request
                )
            
            # Store subscription info in request for use in view
            request.module_subscription = result['data']
            
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator


def subscription_required(view_func):
    """
    Decorator to ensure user has at least one active subscription.
    Less strict than @module_required - just checks for any subscription.
    
    Usage:
        @subscription_required
        def premium_dashboard(request):
            ...
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        from subscriptions.models import UserModuleSubscription
        
        if not request.user.is_authenticated:
            if _is_ajax(request):
                return JsonResponse({
                    'ok': False,
                    'code': 'AUTH_REQUIRED',
                    'reason': 'Please log in to continue.',
                }, status=401)
            return redirect('login')
        
        # Check for any active subscription
        has_subscription = UserModuleSubscription.objects.filter(
            user=request.user,
            status__in=['active', 'trial'],
            expires_at__gt=timezone.now()
        ).exists()
        
        if not has_subscription:
            if _is_ajax(request):
                return JsonResponse({
                    'ok': False,
                    'code': 'NO_SUBSCRIPTION',
                    'reason': 'An active subscription is required.',
                }, status=403)
            messages.warning(request, 'Please subscribe to access premium features.')
            return redirect('pricing')
        
        return view_func(request, *args, **kwargs)
    return wrapper


def admin_required(view_func):
    """
    Decorator to ensure user is admin or superadmin.
    
    Usage:
        @admin_required
        def admin_dashboard(request):
            ...
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            if _is_ajax(request):
                return JsonResponse({
                    'ok': False,
                    'code': 'AUTH_REQUIRED',
                    'reason': 'Please log in to continue.',
                }, status=401)
            return redirect('login')
        
        # Check admin status
        is_admin = False
        
        # Django staff/superuser
        if request.user.is_staff or request.user.is_superuser:
            is_admin = True
        
        # Custom profile role
        if hasattr(request.user, 'account_profile'):
            if request.user.account_profile.role in ('admin', 'superadmin'):
                is_admin = True
        
        if not is_admin:
            if _is_ajax(request):
                return JsonResponse({
                    'ok': False,
                    'code': 'FORBIDDEN',
                    'reason': 'Admin access required.',
                }, status=403)
            messages.error(request, 'You do not have permission to access this page.')
            return redirect('dashboard')
        
        return view_func(request, *args, **kwargs)
    return wrapper


def superadmin_required(view_func):
    """
    Decorator to ensure user is superadmin only.
    
    Usage:
        @superadmin_required
        def system_settings(request):
            ...
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')
        
        is_superadmin = request.user.is_superuser
        
        if hasattr(request.user, 'account_profile'):
            if request.user.account_profile.role == 'superadmin':
                is_superadmin = True
        
        if not is_superadmin:
            if _is_ajax(request):
                return JsonResponse({
                    'ok': False,
                    'code': 'FORBIDDEN',
                    'reason': 'Superadmin access required.',
                }, status=403)
            messages.error(request, 'Superadmin access required.')
            return redirect('dashboard')
        
        return view_func(request, *args, **kwargs)
    return wrapper


def trial_or_paid(module_code):
    """
    Decorator that allows both trial and paid users.
    Shows trial banner for trial users.
    
    Usage:
        @trial_or_paid('estimate')
        def estimate_view(request):
            # request.is_trial will be True/False
            ...
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            from subscriptions.services import SubscriptionService
            
            if not request.user.is_authenticated:
                return redirect('login')
            
            result = SubscriptionService.check_access(request.user, module_code)
            
            if not result['ok']:
                return redirect('module_access', module_code=module_code)
            
            # Set trial flag for template use
            request.is_trial = result['data'].get('is_trial', False)
            request.days_remaining = result['data'].get('days_remaining', 0)
            request.module_subscription = result['data']
            
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator


def usage_limit_check(module_code, limit_per_request=1):
    """
    Decorator to check and enforce usage limits before action.
    
    Args:
        module_code: Module to check
        limit_per_request: How many "uses" this action counts as
    
    Usage:
        @usage_limit_check('estimate', limit_per_request=1)
        def generate_estimate(request):
            ...
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            from subscriptions.services import SubscriptionService
            
            if not request.user.is_authenticated:
                return redirect('login')
            
            result = SubscriptionService.check_access(request.user, module_code)
            
            if not result['ok']:
                if _is_ajax(request):
                    return JsonResponse(result, status=403)
                messages.error(request, result['reason'])
                return redirect('module_access', module_code=module_code)
            
            data = result['data']
            usage_limit = data.get('usage_limit', 0)
            usage_count = data.get('usage_count', 0)
            
            # Check if this request would exceed limit
            if usage_limit > 0 and (usage_count + limit_per_request) > usage_limit:
                error_msg = f"This action would exceed your monthly limit ({usage_count}/{usage_limit})."
                if _is_ajax(request):
                    return JsonResponse({
                        'ok': False,
                        'code': 'USAGE_LIMIT',
                        'reason': error_msg,
                        'data': {
                            'usage_count': usage_count,
                            'usage_limit': usage_limit,
                        }
                    }, status=403)
                messages.warning(request, error_msg)
                return redirect('upgrade', module=module_code)
            
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator


def ajax_login_required(view_func):
    """
    Decorator for AJAX views that returns JSON on auth failure.
    
    Usage:
        @ajax_login_required
        def api_endpoint(request):
            ...
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse({
                'ok': False,
                'code': 'AUTH_REQUIRED',
                'reason': 'Authentication required.',
                'redirect': reverse('login')
            }, status=401)
        return view_func(request, *args, **kwargs)
    return wrapper


def ajax_module_required(module_code):
    """
    AJAX-only version of module_required.
    Always returns JSON responses.
    
    Usage:
        @ajax_module_required('estimate')
        def api_generate_estimate(request):
            ...
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            from subscriptions.services import SubscriptionService
            
            if not request.user.is_authenticated:
                return JsonResponse({
                    'ok': False,
                    'code': 'AUTH_REQUIRED',
                    'reason': 'Please log in to continue.',
                }, status=401)
            
            result = SubscriptionService.check_access(request.user, module_code)
            
            if not result['ok']:
                return JsonResponse({
                    'ok': False,
                    'code': result.get('code', 'ACCESS_DENIED'),
                    'reason': result['reason'],
                    'data': result.get('data', {}),
                }, status=403)
            
            request.module_subscription = result['data']
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator


# =========================================================================
# HELPERS
# =========================================================================

def _is_ajax(request):
    """Check if request is AJAX/API call."""
    # Check header
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return True
    # Check Accept header for JSON
    if 'application/json' in request.headers.get('Accept', ''):
        return True
    # Check content type
    if request.content_type == 'application/json':
        return True
    return False


# Import timezone for subscription_required
from django.utils import timezone
