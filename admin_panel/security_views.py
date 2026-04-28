"""
Admin Panel security gate views.

These views handle the second-factor password gate for the admin panel:
- unlock: prompt for the admin-panel password and unlock the session.
- lock: clear the unlock flag immediately.
- setup: first-time password configuration (superadmin only).
- security_settings: rotate the password (superadmin only).

Auth assumptions:
- The user is already authenticated (OTP login).
- The user is an admin/superadmin (enforced by per-view checks).

Session keys (also used in admin_panel/decorators.py):
- 'admin_panel_unlocked_at': ISO timestamp of last successful unlock/activity.
- 'admin_panel_failed_attempts': count of recent failed unlock attempts.
- 'admin_panel_locked_until': ISO timestamp until which unlock is rate-limited.
"""

from datetime import timedelta
from functools import wraps

from django.contrib import messages
from django.http import Http404, HttpResponseRedirect
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_http_methods, require_POST

from admin_panel.models import AdminPanelSecurity


# --------------------------------------------------------------------------- #
# Tunables
# --------------------------------------------------------------------------- #

UNLOCK_INACTIVITY_MINUTES = 30
MAX_FAILED_ATTEMPTS = 5
LOCKOUT_MINUTES = 15
MIN_PASSWORD_LENGTH = 8


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #

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


def _admin_only(view_func):
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if not _is_admin(request.user):
            raise Http404
        return view_func(request, *args, **kwargs)
    return _wrapped


def _superadmin_only(view_func):
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if not _is_superadmin(request.user):
            raise Http404
        return view_func(request, *args, **kwargs)
    return _wrapped


def is_unlocked(request):
    """True if this session has a valid (non-expired) admin-panel unlock."""
    last = request.session.get('admin_panel_unlocked_at')
    if not last:
        return False
    try:
        last_dt = timezone.datetime.fromisoformat(last)
    except (TypeError, ValueError):
        return False
    if timezone.is_naive(last_dt):
        last_dt = timezone.make_aware(last_dt, timezone.get_current_timezone())
    if timezone.now() - last_dt > timedelta(minutes=UNLOCK_INACTIVITY_MINUTES):
        return False
    return True


def mark_unlocked(request):
    request.session['admin_panel_unlocked_at'] = timezone.now().isoformat()
    request.session.pop('admin_panel_failed_attempts', None)
    request.session.pop('admin_panel_locked_until', None)
    request.session.modified = True


def clear_unlock(request):
    for key in (
        'admin_panel_unlocked_at',
        'admin_panel_failed_attempts',
        'admin_panel_locked_until',
    ):
        request.session.pop(key, None)
    request.session.modified = True


def touch_unlock(request):
    """Bump the inactivity timer on each authorised admin request."""
    if request.session.get('admin_panel_unlocked_at'):
        request.session['admin_panel_unlocked_at'] = timezone.now().isoformat()
        request.session.modified = True


def _is_rate_limited(request):
    locked_until = request.session.get('admin_panel_locked_until')
    if not locked_until:
        return False, 0
    try:
        until_dt = timezone.datetime.fromisoformat(locked_until)
    except (TypeError, ValueError):
        return False, 0
    if timezone.is_naive(until_dt):
        until_dt = timezone.make_aware(until_dt, timezone.get_current_timezone())
    remaining = (until_dt - timezone.now()).total_seconds()
    if remaining <= 0:
        request.session.pop('admin_panel_locked_until', None)
        request.session.pop('admin_panel_failed_attempts', None)
        request.session.modified = True
        return False, 0
    return True, int(remaining)


def _record_failure(request):
    attempts = int(request.session.get('admin_panel_failed_attempts', 0)) + 1
    request.session['admin_panel_failed_attempts'] = attempts
    if attempts >= MAX_FAILED_ATTEMPTS:
        request.session['admin_panel_locked_until'] = (
            timezone.now() + timedelta(minutes=LOCKOUT_MINUTES)
        ).isoformat()
        request.session['admin_panel_failed_attempts'] = 0
    request.session.modified = True
    return attempts


# --------------------------------------------------------------------------- #
# Views
# --------------------------------------------------------------------------- #

@_admin_only
@require_http_methods(["GET", "POST"])
def unlock(request):
    """Prompt for admin-panel password and unlock the session on success."""
    AdminPanelSecurity.bootstrap_from_env_if_needed()

    if not AdminPanelSecurity.is_configured():
        # No password set yet — only a superadmin can configure it.
        if _is_superadmin(request.user):
            return redirect('admin_panel_setup')
        messages.error(
            request,
            "Admin panel password has not been configured. "
            "Please contact a Super Admin.",
        )
        return redirect('dashboard')

    if is_unlocked(request):
        return redirect(request.GET.get('next') or 'admin_dashboard')

    locked, remaining = _is_rate_limited(request)
    context = {
        'next_url': request.GET.get('next', ''),
        'locked': locked,
        'lockout_seconds': remaining,
        'lockout_minutes': max(1, (remaining + 59) // 60) if locked else 0,
        'max_attempts': MAX_FAILED_ATTEMPTS,
    }

    if request.method == 'POST':
        if locked:
            return render(request, 'admin_panel/security/unlock.html', context)

        password = request.POST.get('password', '')
        sec = AdminPanelSecurity.get()
        if sec and sec.verify(password):
            mark_unlocked(request)
            next_url = request.POST.get('next') or request.GET.get('next')
            return redirect(next_url or 'admin_dashboard')

        attempts = _record_failure(request)
        remaining_attempts = max(0, MAX_FAILED_ATTEMPTS - attempts)
        if remaining_attempts:
            messages.error(
                request,
                f"Incorrect password. {remaining_attempts} attempts remaining.",
            )
        else:
            messages.error(
                request,
                f"Too many wrong attempts. Locked for {LOCKOUT_MINUTES} minutes.",
            )
        # Re-evaluate rate limit so the template shows the lock immediately.
        locked, remaining = _is_rate_limited(request)
        context.update({
            'locked': locked,
            'lockout_seconds': remaining,
            'lockout_minutes': max(1, (remaining + 59) // 60) if locked else 0,
        })

    return render(request, 'admin_panel/security/unlock.html', context)


@_admin_only
@require_POST
def lock(request):
    """Manually lock the admin panel for this session."""
    clear_unlock(request)
    messages.info(request, "Admin panel locked.")
    return redirect('dashboard')


@_superadmin_only
@require_http_methods(["GET", "POST"])
def setup(request):
    """First-time setup: configure the admin-panel password (superadmin only)."""
    AdminPanelSecurity.bootstrap_from_env_if_needed()
    if AdminPanelSecurity.is_configured():
        return redirect('admin_panel_security_settings')

    error = None
    if request.method == 'POST':
        new_pw = request.POST.get('new_password', '')
        confirm = request.POST.get('confirm_password', '')
        if len(new_pw) < MIN_PASSWORD_LENGTH:
            error = f"Password must be at least {MIN_PASSWORD_LENGTH} characters."
        elif new_pw != confirm:
            error = "Passwords do not match."
        else:
            AdminPanelSecurity.set_password(new_pw, updated_by=request.user)
            mark_unlocked(request)
            messages.success(request, "Admin panel password configured.")
            return redirect('admin_dashboard')

    return render(request, 'admin_panel/security/setup.html', {
        'error': error,
        'min_length': MIN_PASSWORD_LENGTH,
    })


@_superadmin_only
@require_http_methods(["GET", "POST"])
def security_settings(request):
    """Rotate the admin-panel password (superadmin only).

    Reached only via the unlocked admin panel — so the user must already
    have proven the current password to get here. We still re-verify it on
    submit as a defense-in-depth check.
    """
    AdminPanelSecurity.bootstrap_from_env_if_needed()
    sec = AdminPanelSecurity.get()
    if not sec:
        return redirect('admin_panel_setup')

    if not is_unlocked(request):
        return redirect(f"{reverse('admin_panel_unlock')}?next={request.path}")

    error = None
    if request.method == 'POST':
        current_pw = request.POST.get('current_password', '')
        new_pw = request.POST.get('new_password', '')
        confirm = request.POST.get('confirm_password', '')
        if not sec.verify(current_pw):
            error = "Current password is incorrect."
        elif len(new_pw) < MIN_PASSWORD_LENGTH:
            error = f"New password must be at least {MIN_PASSWORD_LENGTH} characters."
        elif new_pw == current_pw:
            error = "New password must be different from the current password."
        elif new_pw != confirm:
            error = "New passwords do not match."
        else:
            AdminPanelSecurity.set_password(new_pw, updated_by=request.user)
            mark_unlocked(request)
            messages.success(request, "Admin panel password updated.")
            return redirect('admin_panel_security_settings')

    return render(request, 'admin_panel/security/settings.html', {
        'error': error,
        'security': sec,
        'min_length': MIN_PASSWORD_LENGTH,
        'inactivity_minutes': UNLOCK_INACTIVITY_MINUTES,
    })
