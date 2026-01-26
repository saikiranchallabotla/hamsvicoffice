# subscriptions/middleware.py
"""
Subscription and module access middleware.
"""

import re
import logging
from django.shortcuts import redirect
from django.http import JsonResponse
from django.urls import reverse
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)


class ModuleAccessMiddleware:
    """
    Check module subscription access for protected routes.
    
    Configuration in settings.py:
    
    MODULE_PROTECTED_URLS = {
        'estimate': [r'^/estimate/', r'^/datas/'],
        'workslip': [r'^/workslip/'],
        'bill': [r'^/bill/'],
        'self_formatted': [r'^/self-formatted/'],
    }
    
    MODULE_EXEMPT_URLS = [
        r'^/accounts/',
        r'^/admin/',
        r'^/static/',
        r'^/media/',
        r'^/$',
    ]
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
        
        # Compile URL patterns for performance
        self.protected_urls = {}
        self.exempt_patterns = []
        
        # Load protected URLs from settings
        module_urls = getattr(settings, 'MODULE_PROTECTED_URLS', {})
        for module_code, patterns in module_urls.items():
            self.protected_urls[module_code] = [re.compile(p) for p in patterns]
        
        # Load exempt URLs
        exempt_urls = getattr(settings, 'MODULE_EXEMPT_URLS', [
            r'^/accounts/',
            r'^/admin/',
            r'^/static/',
            r'^/media/',
            r'^/$',
            r'^/api/auth/',
            r'^/pricing/',
            r'^/help/',
            r'^/support/',
        ])
        self.exempt_patterns = [re.compile(p) for p in exempt_urls]
    
    def __call__(self, request):
        # Check if URL is exempt first
        path = request.path
        if self._is_exempt(path):
            return self.get_response(request)
        
        # For unauthenticated users accessing protected URLs, redirect to login
        if not request.user.is_authenticated:
            module_code = self._get_required_module(path)
            if module_code:
                # Store intended URL for redirect after login
                request.session['subscription_redirect'] = path
                from django.shortcuts import redirect
                from django.urls import reverse
                login_url = reverse('login')
                return redirect(f'{login_url}?next={path}')
            return self.get_response(request)
        
        # Staff and superusers have full access - bypass subscription checks
        if request.user.is_staff or request.user.is_superuser:
            return self.get_response(request)
        
        # Check module access for authenticated users
        module_code = self._get_required_module(path)
        if module_code:
            access_result = self._check_access(request.user, module_code)
            
            if not access_result['has_access']:
                return self._handle_no_access(request, module_code, access_result)
            
            # Store access info in request for views
            request.module_access = access_result
        
        return self.get_response(request)
    
    def _is_exempt(self, path):
        """Check if path is exempt from module checks."""
        for pattern in self.exempt_patterns:
            if pattern.match(path):
                return True
        return False
    
    def _get_required_module(self, path):
        """Get the module code required for this path."""
        for module_code, patterns in self.protected_urls.items():
            for pattern in patterns:
                if pattern.match(path):
                    return module_code
        return None
    
    def _check_access(self, user, module_code):
        """Check if user has access to module."""
        try:
            from subscriptions.services import SubscriptionService
            result = SubscriptionService.check_access(user, module_code)
            # Normalize response - service uses 'ok', middleware expects 'has_access'
            return {
                'has_access': result.get('ok', False),
                'reason': result.get('reason', ''),
                'code': result.get('code', ''),
                'data': result.get('data', {}),
            }
        except Exception as e:
            logger.error(f"Access check error: {e}")
            return {
                'has_access': False,
                'reason': 'Access check failed',
            }
    
    def _handle_no_access(self, request, module_code, access_result):
        """Handle access denied."""
        code = access_result.get('code', '')
        
        # Check if AJAX request
        if self._is_ajax(request):
            return JsonResponse({
                'ok': False,
                'code': 'ACCESS_DENIED',
                'reason': access_result.get('reason', 'Access denied'),
                'module': module_code,
                'subscription_required': True,
                'access_url': reverse('module_access', kwargs={'module_code': module_code}),
            }, status=403)
        
        # For usage limit exceeded, just show message and redirect to dashboard
        # Don't redirect to module_access (that's for getting subscriptions, not upgrading)
        if code == 'USAGE_LIMIT':
            from django.contrib import messages
            messages.warning(request, f"Monthly usage limit reached for this module. Please upgrade your plan.")
            return redirect('dashboard')
        
        # Store attempted URL for redirect after subscription
        request.session['subscription_redirect'] = request.path
        
        # Redirect to module access page (shows trial + payment options)
        return redirect('module_access', module_code=module_code)
    
    def _is_ajax(self, request):
        """Check if request is AJAX."""
        return (
            request.headers.get('X-Requested-With') == 'XMLHttpRequest' or
            request.content_type == 'application/json' or
            'application/json' in request.headers.get('Accept', '')
        )


class SubscriptionCacheMiddleware:
    """
    Cache user's subscription status for performance.
    Invalidated on subscription changes.
    """
    
    CACHE_TTL = 300  # 5 minutes
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        if request.user.is_authenticated:
            self._load_subscription_cache(request)
        
        response = self.get_response(request)
        
        return response
    
    def _load_subscription_cache(self, request):
        """Load user's subscriptions into request."""
        try:
            from django.core.cache import cache
            
            cache_key = f'user_subs_{request.user.id}'
            cached = cache.get(cache_key)
            
            # Validate cached data is a proper dict with expected structure
            if cached is not None and isinstance(cached, dict) and 'modules' in cached:
                request.user_subscriptions = cached
                return
            
            # Fetch fresh from database
            from subscriptions.models import UserModuleSubscription
            
            subscriptions = UserModuleSubscription.objects.filter(
                user=request.user,
                status__in=['active', 'trial']
            ).select_related('module')
            
            # Build quick lookup
            sub_data = {
                'modules': {},
                'is_admin': request.user.is_staff,
                'fetched_at': timezone.now().isoformat(),
            }
            
            for sub in subscriptions:
                if sub.is_active():
                    sub_data['modules'][sub.module.code] = {
                        'status': sub.status,
                        'expires_at': sub.expires_at.isoformat() if sub.expires_at else None,
                        'is_trial': sub.is_trial,
                        'usage_count': sub.usage_count,
                        'usage_limit': sub.usage_limit,
                    }
            
            # Cache it
            cache.set(cache_key, sub_data, self.CACHE_TTL)
            request.user_subscriptions = sub_data
            
        except Exception as e:
            logger.error(f"Subscription cache error: {e}")
            request.user_subscriptions = {'modules': {}, 'is_admin': False}


class UsageTrackingMiddleware:
    """
    Track module usage for metered billing.
    Only tracks for specific URL patterns.
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
        
        # URLs that count as "usage" - typically form submissions
        self.tracked_patterns = getattr(settings, 'USAGE_TRACKED_URLS', [
            (r'^/estimate/$', 'estimate', 'POST'),
            (r'^/workslip/$', 'workslip', 'POST'),
            (r'^/bill/$', 'bill', 'POST'),
        ])
        
        self.compiled_patterns = [
            (re.compile(p), m, method) 
            for p, m, method in self.tracked_patterns
        ]
    
    def __call__(self, request):
        response = self.get_response(request)
        
        # Only track successful POST requests
        if (request.user.is_authenticated and 
            response.status_code in (200, 201, 302) and
            request.method in ('POST', 'PUT')):
            
            self._track_usage(request, response)
        
        return response
    
    def _track_usage(self, request, response):
        """Track usage if URL matches."""
        path = request.path
        
        for pattern, module_code, method in self.compiled_patterns:
            if pattern.match(path) and request.method == method:
                try:
                    from subscriptions.services import SubscriptionService
                    SubscriptionService.record_usage(
                        user=request.user,
                        module_code=module_code,
                        action=f'{method} {path}',
                        metadata={
                            'path': path,
                            'status': response.status_code,
                        }
                    )
                except Exception as e:
                    logger.error(f"Usage tracking error: {e}")
                break


class TrialExpiryMiddleware:
    """
    Show trial expiry warnings to users.
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        response = self.get_response(request)
        
        if request.user.is_authenticated and hasattr(response, 'context_data'):
            self._add_trial_warnings(request, response)
        
        return response
    
    def _add_trial_warnings(self, request, response):
        """Add trial expiry warnings to context."""
        try:
            from subscriptions.models import UserModuleSubscription
            from django.utils import timezone
            from datetime import timedelta
            
            # Check for trials expiring within 3 days
            warning_threshold = timezone.now() + timedelta(days=3)
            
            expiring_trials = UserModuleSubscription.objects.filter(
                user=request.user,
                status='active',
                is_trial=True,
                expires_at__lte=warning_threshold,
                expires_at__gt=timezone.now(),
            ).select_related('module')
            
            if expiring_trials.exists():
                warnings = []
                for trial in expiring_trials:
                    days_left = (trial.expires_at - timezone.now()).days
                    warnings.append({
                        'module': trial.module.name,
                        'days_left': days_left,
                        'expires_at': trial.expires_at,
                    })
                
                if hasattr(response, 'context_data'):
                    response.context_data['trial_warnings'] = warnings
                    
        except Exception as e:
            logger.debug(f"Trial warning error: {e}")
