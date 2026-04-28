from functools import wraps

from django.http import Http404
from django.shortcuts import redirect
from django.urls import reverse


def _is_admin(user):
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    profile = getattr(user, 'account_profile', None)
    return bool(profile and profile.role in ('admin', 'superadmin'))


def _is_superadmin(user):
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    profile = getattr(user, 'account_profile', None)
    return bool(profile and profile.role == 'superadmin')


def _gate(request):
    """
    Redirect to the appropriate gate page if the admin panel is not unlocked.
    Returns a redirect response, or None if the request may proceed.
    """
    # Local imports to avoid circular import at module load.
    from admin_panel.models import AdminPanelSecurity
    from admin_panel.security_views import is_unlocked, touch_unlock

    AdminPanelSecurity.bootstrap_from_env_if_needed()

    if not AdminPanelSecurity.is_configured():
        # Only a superadmin can perform first-time setup. Other admins
        # are blocked until a superadmin sets the password.
        if _is_superadmin(request.user):
            return redirect(reverse('admin_panel_setup'))
        raise Http404

    if not is_unlocked(request):
        return redirect(f"{reverse('admin_panel_unlock')}?next={request.path}")

    touch_unlock(request)
    return None


def admin_required(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not _is_admin(request.user):
            raise Http404
        gate_redirect = _gate(request)
        if gate_redirect is not None:
            return gate_redirect
        return view_func(request, *args, **kwargs)

    return _wrapped_view


def superadmin_required(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not _is_superadmin(request.user):
            raise Http404
        gate_redirect = _gate(request)
        if gate_redirect is not None:
            return gate_redirect
        return view_func(request, *args, **kwargs)

    return _wrapped_view
