# subscriptions/access_control.py
"""
Module Access Control Utilities.

Centralized entitlement checks for module-based access control.

Usage:
    from subscriptions.access_control import can_access_module, require_module_access
    
    # Direct check
    allowed, reason = can_access_module(user, 'estimate')
    
    # Decorator
    @require_module_access('estimate')
    def my_view(request):
        ...

# ---------------------------------------------------------------------------
# MIDDLEWARE NOTE:
# For automatic URL-based access control, use ModuleAccessMiddleware from
# subscriptions.middleware. Configure MODULE_PROTECTED_URLS in settings.py
# to map URL patterns to module slugs. The middleware uses can_access_module()
# internally for consistent access decisions.
# ---------------------------------------------------------------------------
"""

from functools import wraps
from typing import Tuple
from django.http import JsonResponse, HttpResponseForbidden
from django.shortcuts import redirect
from django.contrib import messages
from django.urls import reverse
from django.utils import timezone


def can_access_module(user, module_slug: str) -> Tuple[bool, str]:
    """
    Check if user can access a specific module.
    
    Args:
        user: Django User instance
        module_slug: Module code/slug (e.g., 'estimate', 'workslip', 'bill')
    
    Returns:
        Tuple of (allowed: bool, reason: str)
        
    Rules (in order):
        1. Unauthenticated users -> denied
        2. SuperAdmin (is_superuser) -> always allowed
        3. Staff/Admin (is_staff) -> always allowed  
        4. Manual override (if exists) -> check override status
        5. Active paid subscription -> allowed
        6. Active trial subscription -> allowed
        7. Expired subscription -> denied with upgrade prompt
        8. No subscription -> denied with subscribe prompt
    """
    
    # Rule 1: Must be authenticated
    if not user or not user.is_authenticated:
        return False, "Authentication required"
    
    # Rule 2: SuperAdmin bypass
    if user.is_superuser:
        return True, "SuperAdmin access"
    
    # Rule 3: Staff/Admin bypass
    if user.is_staff:
        return True, "Admin access"
    
    # Rule 4: Manual override check
    # TODO: Implement ModuleAccessOverride model if needed for manual grants/revokes
    # Example model structure:
    #   class ModuleAccessOverride(models.Model):
    #       user = models.ForeignKey(User, on_delete=models.CASCADE)
    #       module = models.ForeignKey(Module, on_delete=models.CASCADE)
    #       access_type = models.CharField(choices=[('grant', 'Grant'), ('revoke', 'Revoke')])
    #       reason = models.TextField()
    #       granted_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    #       valid_until = models.DateTimeField(null=True, blank=True)
    #       created_at = models.DateTimeField(auto_now_add=True)
    #
    # override = ModuleAccessOverride.objects.filter(
    #     user=user,
    #     module__code=module_slug,
    #     valid_until__gte=timezone.now()  # or null for permanent
    # ).order_by('-created_at').first()
    # 
    # if override:
    #     if override.access_type == 'grant':
    #         return True, f"Manual grant: {override.reason}"
    #     elif override.access_type == 'revoke':
    #         return False, f"Access revoked: {override.reason}"
    
    # Rule 5 & 6: Check subscription
    try:
        from subscriptions.models import UserModuleSubscription
        
        subscription = UserModuleSubscription.objects.filter(
            user=user,
            module__code=module_slug,
        ).select_related('module').order_by('-expires_at').first()
        
        if not subscription:
            return False, "No subscription for this module"
        
        # Check status
        if subscription.status == 'cancelled':
            return False, "Subscription cancelled"
        
        if subscription.status == 'suspended':
            return False, "Subscription suspended - please contact support"
        
        # Check expiry
        if subscription.expires_at and subscription.expires_at < timezone.now():
            if subscription.is_trial:
                return False, "Trial expired - please subscribe to continue"
            else:
                return False, "Subscription expired - please renew"
        
        # Active subscription
        if subscription.status == 'active':
            if subscription.is_trial:
                days_left = (subscription.expires_at - timezone.now()).days if subscription.expires_at else 0
                return True, f"Trial access ({days_left} days remaining)"
            else:
                return True, "Paid subscription"
        
        # Pending subscription (payment processing)
        if subscription.status == 'pending':
            return False, "Subscription pending - payment processing"
        
        return False, "Invalid subscription status"
        
    except Exception as e:
        # Log error but don't expose details
        import logging
        logging.error(f"Access check error for {user.id}/{module_slug}: {e}")
        return False, "Access check failed - please try again"


def require_module_access(module_slug: str, ajax_response: bool = None):
    """
    Decorator to require module access for a view.
    
    Args:
        module_slug: Module code to check access for
        ajax_response: If True, return JSON. If False, redirect. 
                       If None, auto-detect from request headers.
    
    Usage:
        @require_module_access('estimate')
        def estimate_view(request):
            ...
        
        @require_module_access('workslip', ajax_response=True)
        def workslip_api(request):
            ...
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            allowed, reason = can_access_module(request.user, module_slug)
            
            if allowed:
                # Attach access info to request for use in view
                request.module_access = {
                    'module': module_slug,
                    'allowed': True,
                    'reason': reason,
                }
                return view_func(request, *args, **kwargs)
            
            # Access denied - determine response type
            is_ajax = ajax_response
            if is_ajax is None:
                is_ajax = _is_ajax_request(request)
            
            if is_ajax:
                return JsonResponse({
                    'ok': False,
                    'code': 'ACCESS_DENIED',
                    'module': module_slug,
                    'reason': reason,
                    'subscription_required': True,
                    'module_access_url': f'/subscriptions/access/{module_slug}/',
                }, status=403)
            else:
                messages.warning(request, f"Access denied: {reason}")
                
                # Store intended destination for post-subscription redirect
                request.session['subscription_redirect'] = request.get_full_path()
                
                # Redirect to module access page
                module_access_url = reverse('module_access', kwargs={'module_code': module_slug})
                return redirect(module_access_url)
        
        return wrapper
    return decorator


def _is_ajax_request(request) -> bool:
    """Detect if request is AJAX/API call."""
    return (
        request.headers.get('X-Requested-With') == 'XMLHttpRequest' or
        request.content_type == 'application/json' or
        'application/json' in request.headers.get('Accept', '')
    )


# ---------------------------------------------------------------------------
# Convenience functions for common checks
# ---------------------------------------------------------------------------

def get_user_modules(user) -> list:
    """
    Get list of module slugs user has access to.
    
    Returns:
        List of module codes the user can access
    """
    if not user or not user.is_authenticated:
        return []
    
    # Admin/SuperAdmin have all modules
    if user.is_superuser or user.is_staff:
        try:
            from subscriptions.models import Module
            return list(Module.objects.filter(is_active=True).values_list('code', flat=True))
        except Exception:
            return []
    
    # Regular users - check subscriptions
    try:
        from subscriptions.models import UserModuleSubscription
        
        active_subs = UserModuleSubscription.objects.filter(
            user=user,
            status='active',
        ).filter(
            # Not expired
            expires_at__gte=timezone.now()
        ).select_related('module').values_list('module__code', flat=True)
        
        return list(active_subs)
        
    except Exception:
        return []


def has_any_subscription(user) -> bool:
    """Check if user has any active subscription."""
    return len(get_user_modules(user)) > 0


def get_subscription_status(user, module_slug: str) -> dict:
    """
    Get detailed subscription status for a module.
    
    Returns:
        Dict with subscription details or None
    """
    try:
        from subscriptions.models import UserModuleSubscription
        
        subscription = UserModuleSubscription.objects.filter(
            user=user,
            module__code=module_slug,
        ).select_related('module').first()
        
        if not subscription:
            return {
                'exists': False,
                'status': None,
                'is_trial': False,
                'expires_at': None,
                'days_remaining': None,
                'can_access': False,
            }
        
        days_remaining = None
        if subscription.expires_at:
            delta = subscription.expires_at - timezone.now()
            days_remaining = max(0, delta.days)
        
        allowed, _ = can_access_module(user, module_slug)
        
        return {
            'exists': True,
            'status': subscription.status,
            'is_trial': subscription.is_trial,
            'expires_at': subscription.expires_at,
            'days_remaining': days_remaining,
            'can_access': allowed,
            'usage_count': subscription.usage_count,
            'usage_limit': subscription.usage_limit,
        }
        
    except Exception:
        return {
            'exists': False,
            'status': 'error',
            'can_access': False,
        }
