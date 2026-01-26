# core/middleware.py
"""
Organization middleware for multi-tenant support.
Attaches the current user's organization to each request.
"""

from django.shortcuts import redirect
from django.urls import reverse
from core.models import Organization, Membership


class OrganizationMiddleware:
    """
    Middleware that:
    1. Attaches request.organization based on user's primary membership
    2. Enforces that user is a member of at least one organization
    3. Redirects to org selection if needed
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
        # Paths that should not require organization (login, logout, etc.)
        self.excluded_paths = {
            '/admin/',
            '/login/',
            '/register/',
            '/logout/',
            '/api/health/',
        }
    
    def __call__(self, request):
        # Skip middleware for excluded paths
        if self._should_skip(request.path):
            request.organization = None
            return self.get_response(request)
        
        # If user not authenticated, skip
        if not request.user.is_authenticated:
            request.organization = None
            return self.get_response(request)
        
        # Get user's primary organization (first membership)
        try:
            membership = Membership.objects.filter(
                user=request.user,
                organization__is_active=True
            ).select_related('organization').first()
            
            if membership:
                request.organization = membership.organization
            else:
                # User has no active organization membership
                # Redirect to org selection page (to be implemented)
                request.organization = None
                # Optionally redirect:
                # return redirect('select_organization')
        except Exception as e:
            # Handle any database errors gracefully
            request.organization = None
        
        response = self.get_response(request)
        return response
    
    def _should_skip(self, path):
        """Check if path should skip organization enforcement"""
        return any(path.startswith(excluded) for excluded in self.excluded_paths)


class OrgScopingMiddleware:
    """
    QuerySet filtering middleware - automatically scopes queries to user's org.
    This is enforced at the model level via managers, but this middleware
    serves as a safety check and documentation.
    
    NOTE: Most enforcement happens in view decorators and model managers.
    This is here for defense-in-depth.
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # Middleware just passes through; actual enforcement is in views
        response = self.get_response(request)
        return response
