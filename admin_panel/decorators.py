from functools import wraps
from django.http import Http404


def admin_required(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            raise Http404

        if request.user.is_superuser:
            return view_func(request, *args, **kwargs)

        profile = getattr(request.user, 'account_profile', None)
        if profile and profile.role in ('admin', 'superadmin'):
            return view_func(request, *args, **kwargs)

        raise Http404

    return _wrapped_view


def superadmin_required(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            raise Http404

        if request.user.is_superuser:
            return view_func(request, *args, **kwargs)

        profile = getattr(request.user, 'account_profile', None)
        if profile and profile.role == 'superadmin':
            return view_func(request, *args, **kwargs)

        raise Http404

    return _wrapped_view
