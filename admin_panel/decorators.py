# admin_panel/decorators.py
"""
Admin panel access decorators.
"""

from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages
from django.http import HttpResponseForbidden


def admin_required(view_func):
    """
    Decorator to require admin or superadmin role.
    """
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            messages.warning(request, 'Please login to access admin panel.')
            return redirect('login')
        
        # Check for superuser
        if request.user.is_superuser:
            return view_func(request, *args, **kwargs)
        
        # Check for admin role in profile
        profile = getattr(request.user, 'account_profile', None)
        if profile and profile.role in ('admin', 'superadmin'):
            return view_func(request, *args, **kwargs)
        
        messages.error(request, 'You do not have permission to access the admin panel.')
        return redirect('dashboard')
    
    return _wrapped_view


def superadmin_required(view_func):
    """
    Decorator to require superadmin role only.
    """
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            messages.warning(request, 'Please login to access admin panel.')
            return redirect('login')
        
        # Check for superuser
        if request.user.is_superuser:
            return view_func(request, *args, **kwargs)
        
        # Check for superadmin role in profile
        profile = getattr(request.user, 'account_profile', None)
        if profile and profile.role == 'superadmin':
            return view_func(request, *args, **kwargs)
        
        messages.error(request, 'This action requires superadmin privileges.')
        return redirect('admin_dashboard')
    
    return _wrapped_view
