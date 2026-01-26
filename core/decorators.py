# core/decorators.py
"""
Decorators for organization-scoped views and permissions.
Enforces that users can only access their own organization's data.
"""

from functools import wraps
from django.shortcuts import redirect
from django.http import HttpResponseForbidden, JsonResponse
from django.contrib.auth.decorators import login_required
from core.models import Organization, Membership


def org_required(view_func):
    """
    Decorator that ensures user has an active organization membership.
    Attaches request.organization for use in the view.
    """
    @login_required
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        # Try to get org from middleware (already attached)
        if hasattr(request, 'organization') and request.organization:
            return view_func(request, *args, **kwargs)
        
        # Fallback: get from user's membership
        membership = Membership.objects.filter(
            user=request.user,
            organization__is_active=True
        ).select_related('organization').first()
        
        if not membership:
            # User has no active organization - create one automatically
            from core.models import Organization
            
            # Create default organization for user
            org_slug = request.user.username.lower().replace(' ', '-')
            org_name = f"{request.user.first_name or request.user.username}'s Organization"
            
            organization = Organization.objects.create(
                name=org_name,
                slug=org_slug,
                plan='free',
                owner=request.user,
            )
            
            membership = Membership.objects.create(
                user=request.user,
                organization=organization,
                role='owner',
            )
        
        request.organization = membership.organization
        return view_func(request, *args, **kwargs)
    
    return wrapper


def org_scoped(view_func):
    """
    Decorator that enforces organization scoping for object access.
    
    Checks that URL parameter 'org_slug' matches request.organization.slug
    Prevents cross-organization access.
    
    Usage in URL: path('projects/<org_slug>/', view_func, name='projects')
    """
    @org_required
    @wraps(view_func)
    def wrapper(request, org_slug=None, *args, **kwargs):
        if not org_slug:
            # No org_slug provided, use request.organization
            return view_func(request, *args, **kwargs)
        
        # Verify org_slug matches user's organization
        if request.organization.slug != org_slug:
            return HttpResponseForbidden(
                "You don't have permission to access this organization."
            )
        
        return view_func(request, org_slug=org_slug, *args, **kwargs)
    
    return wrapper


def role_required(*roles):
    """
    Decorator that enforces minimum role requirement.
    
    Args:
        *roles: Tuple of allowed roles (e.g., 'admin', 'owner')
    
    Usage:
        @role_required('owner', 'admin')
        def manage_team(request):
            ...
    """
    def decorator(view_func):
        @org_required
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            # Get user's role in their organization
            membership = Membership.objects.filter(
                user=request.user,
                organization=request.organization,
            ).first()
            
            if not membership:
                return HttpResponseForbidden(
                    "You are not a member of this organization."
                )
            
            # Check if user's role is in allowed roles
            if membership.role not in roles:
                return HttpResponseForbidden(
                    f"This action requires one of these roles: {', '.join(roles)}"
                )
            
            request.membership = membership
            return view_func(request, *args, **kwargs)
        
        return wrapper
    
    return decorator


def api_org_scoped(view_func):
    """
    Decorator for API views that returns JSON error responses.
    Similar to org_scoped but returns JSON 403 instead of HTML.
    """
    @org_required
    @wraps(view_func)
    def wrapper(request, org_slug=None, *args, **kwargs):
        if org_slug and request.organization.slug != org_slug:
            return JsonResponse(
                {'error': 'You do not have access to this organization.'},
                status=403
            )
        
        return view_func(request, org_slug=org_slug, *args, **kwargs)
    
    return wrapper


def handle_org_access_error(view_func):
    """
    Wrapper that catches org access errors and returns proper responses.
    Useful for views that fetch objects and need to verify org access.
    
    Usage:
        @handle_org_access_error
        def project_detail(request, project_id):
            project = Project.objects.for_org(request.organization).get(id=project_id)
            # If project not in org, DoesNotExist is caught and returns 404
    """
    @org_required
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        try:
            return view_func(request, *args, **kwargs)
        except Exception as e:
            from django.http import Http404
            from django.core.exceptions import ObjectDoesNotExist
            
            if isinstance(e, ObjectDoesNotExist):
                raise Http404("Object not found or you don't have permission to access it.")
            raise
    
    return wrapper
