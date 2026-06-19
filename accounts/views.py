# accounts/views.py
"""
OTP-based authentication views.

Flows:
1. Login: Enter phone → Request OTP → Verify OTP → Dashboard
2. Register: Enter details + phone → Request OTP → Verify → Dashboard
3. Logout: Clear session
"""

import json
import logging
from django.conf import settings
from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.contrib.auth import login, logout
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods, require_POST
from django.views.decorators.csrf import csrf_protect
from django.contrib import messages
from django.utils import timezone

from accounts.services import OTPService
from accounts.models import UserProfile, UserSession
from accounts.forms import (
    ProfileForm, ChangePhoneForm, ChangeEmailForm,
    DeleteAccountForm, NotificationPrefsForm
)
from django.core.validators import validate_email
from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils.http import url_has_allowed_host_and_scheme

logger = logging.getLogger(__name__)


def _client_ip(request):
    """Best-effort client IP. Honours X-Forwarded-For (first hop) when present.
    Used for per-IP OTP throttling — wrong-but-stable is fine, missing is not."""
    xff = request.META.get('HTTP_X_FORWARDED_FOR', '')
    if xff:
        return xff.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR', '') or ''


def _safe_next_url(request, raw_next):
    """Return raw_next iff it points to the same host; else fall back to dashboard.
    Prevents open-redirect via ?next=https://evil.example/."""
    if not raw_next:
        return '/dashboard/'
    if url_has_allowed_host_and_scheme(
        raw_next,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return raw_next
    return '/dashboard/'


# =============================================================================
# LOGIN VIEWS
# =============================================================================

@require_http_methods(["GET", "POST"])
def login_view(request):
    """
    Login page - enter phone/email to request OTP.
    """
    if request.user.is_authenticated:
        return redirect('dashboard')

    identifier = ''

    if request.method == 'POST':
        identifier = request.POST.get('identifier', '').strip()
        
        if not identifier:
            messages.error(request, 'Please enter your phone number or email.')
            return render(request, 'accounts/login.html')
        
        # Check if user exists. To prevent enumeration, mask the answer:
        # behave identically whether or not the identifier resolves to an
        # account. Real users get an OTP; unknown identifiers get no OTP
        # but the same redirect, so the verify step fails as "invalid code".
        user = _find_user(identifier)
        if not user:
            logger.info(f"login attempt for unknown identifier (masked={_mask_identifier(identifier)})")
            request.session['otp_identifier'] = identifier
            request.session['otp_purpose'] = 'login'
            request.session.save()
            messages.success(request, f'If an account exists, a code has been sent to {_mask_identifier(identifier)}.')
            return redirect('verify_otp')

        # Determine OTP channel and identifier based on settings
        otp_channel = getattr(settings, 'OTP_CHANNEL', 'email')

        if otp_channel == 'sms':
            # SMS mode: send OTP to user's registered phone number
            profile = getattr(user, 'account_profile', None)
            phone = profile.phone if profile else None

            if phone:
                otp_identifier = phone
            else:
                # Fallback: user has no phone yet, fall back to email
                otp_channel = 'email'
                otp_identifier = user.email
                messages.info(request, 'No phone number on file — sending OTP to your email instead.')
        else:
            # Email mode (default)
            otp_identifier = user.email

        if not otp_identifier:
            messages.error(request, 'No contact info on file. Please contact support.')
            return render(request, 'accounts/login.html', {'identifier': identifier})

        request.session['otp_identifier'] = otp_identifier
        request.session['otp_purpose'] = 'login'

        # Request OTP via the selected channel
        result = OTPService.request_otp(otp_identifier, otp_channel, ip_address=_client_ip(request))
        
        if result['ok']:
            # Get OTP for display in dev mode
            otp = result.get('data', {}).get('otp')
            dev_mode = result.get('data', {}).get('dev_mode', False)

            if dev_mode and otp:
                # Store OTP in session for display on verify page
                request.session['show_otp'] = otp
                messages.success(request, f'OTP sent! Use the code shown below.')
            else:
                messages.success(request, f'OTP sent to {_mask_identifier(identifier)}')
            # Ensure session is saved before redirect
            request.session.save()
            # Always redirect to verify_otp page
            return redirect('verify_otp')
        else:
            messages.error(request, result['reason'])
            return render(request, 'accounts/login.html', {'identifier': identifier})
    
    return render(request, 'accounts/login.html')


@require_http_methods(["GET", "POST"])
def verify_otp_view(request):
    """
    OTP verification page.
    """
    if request.user.is_authenticated:
        return redirect('dashboard')
    
    identifier = request.session.get('otp_identifier')
    purpose = request.session.get('otp_purpose', 'login')
    
    if not identifier:
        messages.warning(request, 'Please enter your phone/email first.')
        return redirect('login')
    
    # OTP popup display: in DEBUG only, surface via session (one-shot pop).
    # The previous `?_otp=` GET-param was removed because URLs leak through
    # Referer headers, browser history, and access logs.
    show_otp = request.session.pop('show_otp', None) if settings.DEBUG else None

    if request.method == 'POST':
        otp = request.POST.get('otp', '').strip()
        
        if not otp or len(otp) != 6:
            messages.error(request, 'Please enter a valid 6-digit OTP.')
            return render(request, 'accounts/verify_otp.html', {
                'identifier': _mask_identifier(identifier)
            })
        
        # Verify OTP
        result = OTPService.verify_otp(identifier, otp)
        
        if result['ok']:
            # Clear session data
            del request.session['otp_identifier']
            del request.session['otp_purpose']
            
            if purpose == 'login':
                return _handle_login_success(request, identifier)
            elif purpose == 'register':
                return _handle_register_success(request, identifier)
            else:
                messages.success(request, 'Phone verified successfully!')
                return redirect('dashboard')
        else:
            messages.error(request, result['reason'])
            return render(request, 'accounts/verify_otp.html', {
                'identifier': _mask_identifier(identifier),
                'attempts_remaining': result.get('data', {}).get('attempts_remaining'),
            })
    
    return render(request, 'accounts/verify_otp.html', {
        'identifier': _mask_identifier(identifier),
        'show_otp': show_otp,
    })


@require_POST
def resend_otp_view(request):
    """
    Resend OTP (AJAX endpoint).
    """
    identifier = request.session.get('otp_identifier')
    
    if not identifier:
        return JsonResponse({
            'ok': False,
            'reason': 'Session expired. Please start again.',
        }, status=400)
    
    channel = 'email' if '@' in identifier else 'sms'
    result = OTPService.request_otp(identifier, channel, ip_address=_client_ip(request))

    if result['ok']:
        response_data = {
            'ok': True,
            'reason': 'OTP sent successfully.',
            'cooldown': result['data'].get('cooldown', 60),
        }
        # In dev_mode (no SMS/Email configured), include OTP for testing
        dev_mode = result.get('data', {}).get('dev_mode', False)
        otp = result.get('data', {}).get('otp')
        if dev_mode and otp:
            response_data['otp'] = otp
            response_data['dev_mode'] = True
            response_data['reason'] = f"OTP sent. [DEV MODE] Your OTP is: {otp}"
        return JsonResponse(response_data)
    else:
        return JsonResponse({
            'ok': False,
            'reason': result['reason'],
            'cooldown': result.get('data', {}).get('retry_after', 0),
        }, status=429 if result.get('code') == 'COOLDOWN' else 400)


# =============================================================================
# REGISTER VIEWS
# =============================================================================

@require_http_methods(["GET", "POST"])
def register_view(request):
    """
    Registration page - enter details and phone to request OTP.
    """
    if request.user.is_authenticated:
        return redirect('dashboard')
    
    if request.method == 'POST':
        # Get form data
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        email = request.POST.get('email', '').strip().lower()
        # Strip everything except digits from phone (users enter digits only, e.g. 9876543210)
        phone = ''.join(c for c in request.POST.get('phone', '') if c.isdigit())
        company = request.POST.get('company', '').strip()
        
        # Validate
        errors = []
        if not first_name:
            errors.append('First name is required.')
        if not email:
            errors.append('Email address is required.')
        if email:
            try:
                validate_email(email)
            except DjangoValidationError:
                errors.append('Please enter a valid email address.')

        # NOTE: do NOT add "already registered" errors here — they enable
        # enumeration. If the email/phone is already in use we silently
        # short-circuit the OTP send below and let verify fail.
        email_already_taken = bool(email and User.objects.filter(email=email).exists())
        phone_already_taken = bool(phone and UserProfile.objects.filter(phone=phone).exists())
        
        if errors:
            for error in errors:
                messages.error(request, error)
            return render(request, 'accounts/register.html', {
                'first_name': first_name,
                'last_name': last_name,
                'email': email,
                'phone': phone,
                'company': company,
            })
        
        # Store in session for after OTP verification
        request.session['register_data'] = {
            'first_name': first_name,
            'last_name': last_name,
            'email': email,
            'phone': phone,
            'company': company,
        }
        request.session['otp_identifier'] = email
        request.session['otp_purpose'] = 'register'

        # Anti-enumeration: if only the phone is already in use (email is
        # fresh), skip the OTP send and show the same UX so the verify step
        # fails uniformly — no real account to recover here.
        if phone_already_taken and not email_already_taken:
            logger.info(f"register attempt with already-used phone (masked={_mask_identifier(email)})")
            request.session.save()
            messages.success(request, f'If this email is available, a code has been sent to {_mask_identifier(email)}.')
            return redirect('verify_otp')

        # If the email is already registered, still send a REAL OTP to that
        # inbox (same generic message — no enumeration leak to anyone who
        # doesn't control the inbox). Only the actual owner can complete
        # verification; _handle_register_success then logs them into their
        # existing account instead of creating a duplicate.
        if email_already_taken:
            logger.info(f"register attempt with already-registered email (masked={_mask_identifier(email)})")

        # Request OTP
        result = OTPService.request_otp(email, 'email', ip_address=_client_ip(request))
        
        if result['ok']:
            # Get OTP for display in dev mode
            otp = result.get('data', {}).get('otp')
            dev_mode = result.get('data', {}).get('dev_mode', False)

            if dev_mode and otp:
                # Store OTP in session for display on verify page (SPA-safe)
                request.session['show_otp'] = otp
                messages.success(request, f'OTP sent! Use the code shown below.')
            else:
                messages.success(request, f'OTP sent to {_mask_identifier(email)}')
            # Ensure session is saved before redirect
            request.session.save()
            return redirect('verify_otp')
        else:
            messages.error(request, result['reason'])
            return render(request, 'accounts/register.html', {
                'first_name': first_name,
                'last_name': last_name,
                'email': email,
                'phone': phone,
                'company': company,
            })
    
    return render(request, 'accounts/register.html')


# =============================================================================
# LOGOUT
# =============================================================================

@require_POST
def logout_view(request):
    """Logout current session. POST-only to prevent CSRF-driven log-out."""
    if request.user.is_authenticated:
        session_key = request.session.session_key
        if session_key:
            UserSession.objects.filter(session_key=session_key).update(is_active=False)
        logout(request)
        messages.success(request, 'You have been logged out.')
    return redirect('login')


@login_required
@require_POST
def logout_all_view(request):
    """
    Logout from all devices.
    """
    current_session = request.session.session_key
    count = UserSession.logout_all(request.user, except_session_key=current_session)
    
    messages.success(request, f'Logged out from {count} other device(s).')
    return redirect('settings')


# =============================================================================
# SESSION MANAGEMENT
# =============================================================================

@login_required
def active_sessions_view(request):
    """
    View and manage active sessions.
    """
    sessions = UserSession.objects.filter(
        user=request.user,
        is_active=True
    ).order_by('-last_activity')
    
    current_session = request.session.session_key
    
    return render(request, 'accounts/sessions.html', {
        'sessions': sessions,
        'current_session': current_session,
    })


@login_required
@require_POST
def revoke_session_view(request, session_id):
    """
    Revoke a specific session.
    """
    try:
        session = UserSession.objects.get(
            id=session_id,
            user=request.user,
            is_active=True
        )
        session.logout()
        messages.success(request, 'Session revoked successfully.')
    except UserSession.DoesNotExist:
        messages.error(request, 'Session not found.')
    
    return redirect('active_sessions')


# =============================================================================
# API ENDPOINTS
# =============================================================================

@require_POST
@csrf_protect
def api_request_otp(request):
    """
    API: Request OTP for login/register.
    
    POST /api/auth/request-otp/
    Body: {"identifier": "+919876543210", "purpose": "login"}
    """
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'ok': False, 'reason': 'Invalid JSON.'}, status=400)
    
    identifier = data.get('identifier', '').strip()
    purpose = data.get('purpose', 'login')

    if not identifier:
        return JsonResponse({'ok': False, 'reason': 'Identifier required.'}, status=400)

    # Anti-enumeration: NEVER tell the client whether the identifier exists
    # or not. If the state doesn't match the purpose (login on missing user,
    # register on existing user), pretend success but don't actually send.
    skip_send = False
    if purpose == 'login' and not _find_user(identifier):
        logger.info(f"api_request_otp login for unknown identifier (masked={_mask_identifier(identifier)})")
        skip_send = True
    elif purpose == 'register' and _find_user(identifier):
        logger.info(f"api_request_otp register for existing identifier (masked={_mask_identifier(identifier)})")
        skip_send = True

    if skip_send:
        request.session['otp_identifier'] = identifier
        request.session['otp_purpose'] = purpose
        return JsonResponse({
            'ok': True,
            'reason': 'OTP sent.',
            'data': {
                'masked': _mask_identifier(identifier),
                'expires_in': OTPService.OTP_TTL,
                'cooldown': OTPService.RESEND_COOLDOWN,
            }
        })

    # Request OTP
    channel = 'email' if '@' in identifier else 'sms'
    result = OTPService.request_otp(identifier, channel, ip_address=_client_ip(request))
    
    if result['ok']:
        # Store in session
        request.session['otp_identifier'] = identifier
        request.session['otp_purpose'] = purpose
        
        return JsonResponse({
            'ok': True,
            'reason': 'OTP sent.',
            'data': {
                'masked': _mask_identifier(identifier),
                'expires_in': result['data'].get('expires_in', 300),
                'cooldown': result['data'].get('cooldown', 60),
            }
        })
    
    status = 429 if result.get('code') in ('COOLDOWN', 'RATE_LIMITED', 'LOCKED_OUT') else 400
    return JsonResponse(result, status=status)


@require_POST
@csrf_protect
def api_verify_otp(request):
    """
    API: Verify OTP and complete auth.

    POST /api/auth/verify-otp/
    Body: {"otp": "123456"}

    Identifier, purpose, and register_data come from the SERVER SESSION only.
    Client-supplied identifier/purpose/register_data are ignored — accepting
    them would let an attacker pair an OTP issued for phone X with a freshly
    forged account on email Y.
    """
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'ok': False, 'reason': 'Invalid JSON.'}, status=400)

    identifier = request.session.get('otp_identifier')
    purpose = request.session.get('otp_purpose', 'login')
    register_data = request.session.get('register_data', {}) if purpose == 'register' else {}
    otp = (data.get('otp') or '').strip()

    if not identifier:
        return JsonResponse({'ok': False, 'reason': 'Session expired. Start again.'}, status=400)

    if not otp or len(otp) != 6:
        return JsonResponse({'ok': False, 'reason': 'Valid 6-digit OTP required.'}, status=400)

    # Verify OTP
    result = OTPService.verify_otp(identifier, otp)

    if not result['ok']:
        return JsonResponse(result, status=400)

    # Handle based on purpose
    if purpose == 'register':
        # OTP proved control of this inbox. If an account already exists,
        # log into it instead of creating a duplicate (one email = one
        # account); existing account details are left untouched.
        existing_user = User.objects.filter(email=identifier).first()
        if existing_user:
            user = existing_user
        else:
            user = _create_user(identifier, register_data)
            if not user:
                return JsonResponse({
                    'ok': False,
                    'reason': 'Failed to create account.',
                }, status=500)
    else:
        user = _find_user(identifier)
        if not user:
            return JsonResponse({
                'ok': False,
                'reason': 'Account not found.',
            }, status=404)

    # Log user in
    login(request, user, backend='django.contrib.auth.backends.ModelBackend')

    # Clear session data
    request.session.pop('otp_identifier', None)
    request.session.pop('otp_purpose', None)
    request.session.pop('register_data', None)

    return JsonResponse({
        'ok': True,
        'reason': 'Authentication successful.',
        'data': {
            'user_id': user.id,
            'username': user.username,
            'email': user.email,
            'name': user.get_full_name(),
            'redirect': '/dashboard/',
        }
    })


@require_POST
def api_logout(request):
    """
    API: Logout current session.
    """
    if request.user.is_authenticated:
        session_key = request.session.session_key
        if session_key:
            UserSession.objects.filter(session_key=session_key).update(is_active=False)
        logout(request)
    
    return JsonResponse({'ok': True, 'reason': 'Logged out.'})


def api_check_session(request):
    """
    API: Check if current session is still valid.
    Called by client-side polling to detect if user was kicked out
    from another device login.
    
    GET /api/auth/check-session/
    Response: {"valid": true} or {"valid": false, "reason": "..."}
    """
    # If not authenticated, session is invalid
    if not request.user.is_authenticated:
        return JsonResponse({
            'valid': False,
            'reason': 'not_authenticated',
            'message': 'Session expired. Please login again.'
        })
    
    session_key = request.session.session_key
    if not session_key:
        return JsonResponse({
            'valid': False,
            'reason': 'no_session',
            'message': 'Session not found. Please login again.'
        })
    
    # Check if session is still active in UserSession
    try:
        user_session = UserSession.objects.filter(
            user=request.user,
            session_key=session_key
        ).first()
        
        if not user_session:
            return JsonResponse({
                'valid': False,
                'reason': 'session_not_found',
                'message': 'Your session was not found. Please login again.'
            })
        
        if not user_session.is_active:
            return JsonResponse({
                'valid': False,
                'reason': 'kicked_out',
                'message': 'You have been logged out because your account was accessed from another device.'
            })
        
        # Session is valid
        return JsonResponse({
            'valid': True
        })
    
    except Exception as e:
        logger.exception(f"api_check_session error: {e}")
        # Fail closed: an unknown error should not keep a possibly-revoked
        # session alive. Force the client to re-validate by re-logging in.
        return JsonResponse({
            'valid': False,
            'reason': 'check_failed',
            'message': 'Session check failed. Please login again.',
        }, status=503)


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def _find_user(identifier: str):
    """Find user by phone or email."""
    identifier = identifier.strip()

    # Check by email
    if '@' in identifier:
        return User.objects.filter(email=identifier.lower()).first()

    # Check by phone — strip everything except digits, use last 10
    digits = ''.join(c for c in identifier if c.isdigit())
    if len(digits) > 10:
        digits = digits[-10:]  # strip country code prefix (e.g. 91XXXXXXXXXX → XXXXXXXXXX)

    if not digits:
        return None

    profile = UserProfile.objects.filter(phone=digits).select_related('user').first()
    return profile.user if profile else None


def _create_user(identifier: str, data: dict):
    """
    Create new user from registration data.
    Uses database transaction to prevent race conditions.
    """
    from django.db import transaction, IntegrityError
    import logging

    # identifier may be email (new flow) or phone (legacy)
    if '@' in identifier:
        email = identifier
        # Normalize: strip everything except digits
        phone = ''.join(c for c in data.get('phone', '') if c.isdigit())
    else:
        phone = ''.join(c for c in identifier if c.isdigit())
        email = data.get('email', '')

    first_name = data.get('first_name', '')
    last_name = data.get('last_name', '')
    company = data.get('company', '')
    
    try:
        with transaction.atomic():
            # Double-check email is not already registered (race condition prevention)
            if email:
                existing_user = User.objects.filter(email=email).select_for_update().first()
                if existing_user:
                    logging.warning(f"Email {email} already registered (race condition caught)")
                    return existing_user

            # Double-check phone is not already registered
            if phone:
                existing_profile = UserProfile.objects.filter(phone=phone).select_for_update().first()
                if existing_profile:
                    logging.warning(f"Phone {phone} already registered (race condition caught)")
                    return existing_profile.user
            
            # Generate username from email local part or phone
            if email:
                base = email.split('@')[0][:12]
            else:
                base = phone[-10:] if phone else 'user'
            username = f"user_{base}"
            counter = 1
            while User.objects.filter(username=username).exists():
                username = f"user_{base}_{counter}"
                counter += 1
            
            # Create user
            user = User.objects.create(
                username=username,
                email=email,
                first_name=first_name,
                last_name=last_name,
            )
            user.set_unusable_password()  # No password for OTP-only auth
            user.save()
            
            # Create or update profile with phone (signal may have already created it)
            profile, created = UserProfile.objects.get_or_create(
                user=user,
                defaults={
                    'phone': phone,
                    'phone_verified': True,
                    'company_name': company
                }
            )
            if not created:
                # Profile was created by signal, update it with phone info
                profile.phone = phone
                profile.phone_verified = True
                profile.company_name = company
                profile.save()
            
            logging.info(f"Created new user: {username} with phone: {phone}")
            return user
            
    except IntegrityError as e:
        # Handle database constraint violations (duplicate email/phone)
        logging.error(f"IntegrityError creating user: {e}")
        if email:
            existing = User.objects.filter(email=email).first()
            if existing:
                return existing
        if phone:
            profile = UserProfile.objects.filter(phone=phone).select_related('user').first()
            if profile:
                return profile.user
        return None
    except Exception as e:
        logging.error(f"Failed to create user: {e}")
        return None


def _handle_login_success(request, identifier):
    """Handle successful login - check for existing sessions first."""
    user = _find_user(identifier)
    if not user:
        messages.error(request, 'Account not found.')
        return redirect('login')
    
    # Check for active sessions on other devices
    active_sessions = UserSession.objects.filter(
        user=user,
        is_active=True
    ).order_by('-last_activity')
    
    if active_sessions.exists():
        # Store pending login info in session for confirmation
        request.session['pending_login_identifier'] = identifier
        request.session['pending_login_user_id'] = user.id

        # Anti-recon: we have NOT yet established that the visitor is the
        # account owner (only that they passed an OTP). Don't surface device
        # specifics (IP, full UA, exact timestamp) — show only a count and
        # coarse device-type so they can recognise their own sessions.
        device_types = []
        for s in active_sessions[:5]:
            device_types.append(s.device_type or 'Unknown')
        request.session['pending_login_sessions'] = {
            'count': active_sessions.count(),
            'device_types': device_types,
        }
        request.session.save()  # Ensure session is saved before redirect

        return redirect('confirm_device_login')
    
    # No existing sessions - proceed directly
    return _complete_login(request, user, identifier)


def _complete_login(request, user, identifier):
    """Complete the login process after device confirmation."""
    login(request, user, backend='django.contrib.auth.backends.ModelBackend')
    
    # Ensure profile exists and update it
    profile, created = UserProfile.objects.get_or_create(user=user)
    if created:
        if '@' not in identifier:
            phone = ''.join(c for c in identifier if c.isdigit() or c == '+')
            profile.phone = phone
            profile.phone_verified = True
        else:
            profile.email_verified = True
    else:
        profile.last_login_at = timezone.now()
        if '@' not in identifier:
            profile.phone_verified = True
        else:
            profile.email_verified = True
    profile.save()
    
    messages.success(request, f'Welcome back, {user.first_name or user.username}!')
    
    next_url = _safe_next_url(request, request.session.pop('next', None) or request.GET.get('next'))
    return redirect(next_url)


@require_http_methods(["GET", "POST"])
def confirm_device_login_view(request):
    """
    Hotstar-style device conflict page.
    Shows active sessions and asks user to confirm logging out other devices.
    """
    pending_user_id = request.session.get('pending_login_user_id')
    pending_identifier = request.session.get('pending_login_identifier')
    session_info = request.session.get('pending_login_sessions', {})

    if not pending_user_id or not pending_identifier:
        return redirect('login')
    
    if request.method == 'POST':
        action = request.POST.get('form_action', '')
        
        try:
            user = User.objects.get(id=pending_user_id)
        except User.DoesNotExist:
            messages.error(request, 'Account not found.')
            return redirect('login')
        
        if action == 'logout_all_and_login':
            # Logout all existing sessions
            UserSession.logout_all(user)
            
            # Clean up session data
            request.session.pop('pending_login_identifier', None)
            request.session.pop('pending_login_user_id', None)
            request.session.pop('pending_login_sessions', None)
            
            # Complete login
            return _complete_login(request, user, pending_identifier)
        
        elif action == 'cancel':
            # Clean up and go back to login
            request.session.pop('pending_login_identifier', None)
            request.session.pop('pending_login_user_id', None)
            request.session.pop('pending_login_sessions', None)
            messages.info(request, 'Login cancelled.')
            return redirect('login')
    
    context = {
        'active_sessions': session_info.get('device_types', []) if isinstance(session_info, dict) else [],
        'session_count': session_info.get('count', 0) if isinstance(session_info, dict) else 0,
    }
    return render(request, 'accounts/confirm_device_login.html', context)


def _handle_register_success(request, identifier):
    """Handle successful registration."""
    register_data = request.session.pop('register_data', {})

    # The OTP proved control of this inbox. If an account already exists
    # for it, don't create a duplicate — log into the existing account
    # (one email = one account) and leave its saved details untouched.
    existing_user = User.objects.filter(email=identifier).first()
    if existing_user:
        login(request, existing_user, backend='django.contrib.auth.backends.ModelBackend')
        messages.info(request, 'An account with this email already exists. You have been logged in.')
        return redirect('dashboard')

    user = _create_user(identifier, register_data)
    if not user:
        messages.error(request, 'Failed to create account. Please try again.')
        return redirect('register')

    login(request, user, backend='django.contrib.auth.backends.ModelBackend')
    messages.success(request, f'Welcome, {user.first_name}! Your account has been created.')

    return redirect('dashboard')


def _mask_identifier(identifier: str) -> str:
    """Mask phone/email for display."""
    identifier = identifier.strip()
    
    if '@' in identifier:
        # Email: show first 2 chars and domain
        parts = identifier.split('@')
        if len(parts[0]) > 2:
            return f"{parts[0][:2]}***@{parts[1]}"
        return f"***@{parts[1]}"
    else:
        # Phone: show last 4 digits
        digits = ''.join(c for c in identifier if c.isdigit())
        if len(digits) >= 4:
            return f"****{digits[-4:]}"
        return "****"


# =============================================================================
# PROFILE VIEWS
# =============================================================================

@login_required
def profile_view(request):
    """View user profile - redirects to settings."""
    return redirect('settings')


@login_required
def settings_view(request):
    """Combined settings page with profile, security, and preferences."""
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    
    return render(request, 'accounts/settings.html', {
        'profile': profile,
        'user': request.user,
    })


@login_required
@require_http_methods(["GET", "POST"])
def profile_edit_view(request):
    """Edit user profile."""
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    
    if request.method == 'POST':
        form = ProfileForm(request.POST, instance=profile, user=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Profile updated successfully.')
            return redirect('settings')
    else:
        form = ProfileForm(instance=profile, user=request.user)
    
    return render(request, 'accounts/profile_edit.html', {
        'form': form,
        'profile': profile,
    })


@login_required
@require_http_methods(["GET", "POST"])
def change_phone_view(request):
    """
    Request phone number change.
    Two-step flow:
      1. Verify OTP sent to CURRENT phone (or email fallback) — proves the
         requester holds the existing recovery channel, not just the session.
      2. Verify OTP sent to NEW phone — proves they hold the new device.
    Without step 1, an attacker who briefly hijacks a session can permanently
    rebind the account to their own phone.
    """
    profile = getattr(request.user, 'account_profile', None)
    current_phone = profile.phone if profile else None

    if request.method == 'POST':
        form = ChangePhoneForm(request.POST)
        if form.is_valid():
            new_phone = form.cleaned_data['new_phone']

            # Pick current recovery channel: current phone if set, else email.
            if current_phone:
                current_identifier = current_phone
                current_channel = 'sms'
            elif request.user.email:
                current_identifier = request.user.email
                current_channel = 'email'
            else:
                messages.error(request, 'No recovery channel on file. Contact support.')
                return redirect('settings')

            request.session['pending_phone_change'] = new_phone
            request.session['change_phone_step'] = 'verify_current'
            request.session['otp_identifier'] = current_identifier
            request.session['otp_purpose'] = 'change_phone_current'

            result = OTPService.request_otp(current_identifier, current_channel, ip_address=_client_ip(request))

            if result['ok']:
                dev_otp = result.get('data', {}).get('otp')
                if dev_otp:
                    request.session['dev_otp'] = dev_otp
                messages.success(request, f'Verification code sent to your current {current_channel}: {_mask_identifier(current_identifier)}')
                return redirect('verify_phone_change')
            else:
                messages.error(request, result['reason'])
    else:
        form = ChangePhoneForm()

    return render(request, 'accounts/change_phone.html', {
        'form': form,
        'current_phone': _mask_identifier(current_phone) if current_phone else None,
    })


@login_required
@require_http_methods(["GET", "POST"])
def verify_phone_change_view(request):
    """Verify OTP for phone change (handles both steps of the two-step flow)."""
    new_phone = request.session.get('pending_phone_change')
    step = request.session.get('change_phone_step', 'verify_current')

    if not new_phone:
        messages.warning(request, 'Please enter a new phone number first.')
        return redirect('change_phone')

    if request.method == 'POST':
        otp = request.POST.get('otp', '').strip()

        if not otp or len(otp) != 6:
            messages.error(request, 'Please enter a valid 6-digit OTP.')
        elif step == 'verify_current':
            # Verify against current recovery channel.
            current_identifier = request.session.get('otp_identifier', '')
            result = OTPService.verify_otp(current_identifier, otp)

            if result['ok']:
                # Step 1 cleared — now send OTP to the NEW phone.
                request.session['change_phone_step'] = 'verify_new'
                request.session['otp_identifier'] = new_phone
                request.session['otp_purpose'] = 'change_phone_new'

                send = OTPService.request_otp(new_phone, 'sms', ip_address=_client_ip(request))
                if send['ok']:
                    dev_otp = send.get('data', {}).get('otp')
                    if dev_otp:
                        request.session['dev_otp'] = dev_otp
                    messages.success(request, f'Verified. New code sent to {_mask_identifier(new_phone)}')
                    return redirect('verify_phone_change')
                messages.error(request, send['reason'])
            else:
                messages.error(request, result['reason'])
        else:
            # step == 'verify_new'
            result = OTPService.verify_otp(new_phone, otp)

            if result['ok']:
                profile, _ = UserProfile.objects.get_or_create(user=request.user)
                profile.phone = new_phone
                profile.phone_verified = True
                profile.save()

                request.session.pop('pending_phone_change', None)
                request.session.pop('change_phone_step', None)
                request.session.pop('otp_identifier', None)
                request.session.pop('otp_purpose', None)

                messages.success(request, 'Phone number updated successfully!')
                return redirect('settings')
            else:
                messages.error(request, result['reason'])

    dev_otp = request.session.pop('dev_otp', None)
    display_identifier = (
        _mask_identifier(request.session.get('otp_identifier', '')) if step == 'verify_current'
        else _mask_identifier(new_phone)
    )

    return render(request, 'accounts/verify_change.html', {
        'identifier': display_identifier,
        'change_type': 'phone',
        'dev_otp': dev_otp,
        'step': step,
    })


@login_required
@require_http_methods(["GET", "POST"])
def change_email_view(request):
    """
    Request email change. Two-step flow analogous to change_phone_view —
    OTP to current email first (fallback: current phone), then OTP to new
    email. Prevents session hijack from permanently rebinding the account.
    """
    current_email = request.user.email
    profile = getattr(request.user, 'account_profile', None)
    current_phone = profile.phone if profile else None

    if request.method == 'POST':
        form = ChangeEmailForm(request.POST)
        if form.is_valid():
            new_email = form.cleaned_data['new_email']

            if current_email:
                current_identifier = current_email
                current_channel = 'email'
            elif current_phone:
                current_identifier = current_phone
                current_channel = 'sms'
            else:
                messages.error(request, 'No recovery channel on file. Contact support.')
                return redirect('settings')

            request.session['pending_email_change'] = new_email
            request.session['change_email_step'] = 'verify_current'
            request.session['otp_identifier'] = current_identifier
            request.session['otp_purpose'] = 'change_email_current'

            result = OTPService.request_otp(current_identifier, current_channel, ip_address=_client_ip(request))

            if result['ok']:
                dev_otp = result.get('data', {}).get('otp')
                if dev_otp:
                    request.session['dev_otp'] = dev_otp
                messages.success(request, f'Verification code sent to your current {current_channel}: {_mask_identifier(current_identifier)}')
                return redirect('verify_email_change')
            else:
                messages.error(request, result['reason'])
    else:
        form = ChangeEmailForm()

    return render(request, 'accounts/change_email.html', {
        'form': form,
        'current_email': _mask_identifier(current_email) if current_email else None,
    })


@login_required
@require_http_methods(["GET", "POST"])
def verify_email_change_view(request):
    """Verify OTP for email change (handles both steps of the two-step flow)."""
    new_email = request.session.get('pending_email_change')
    step = request.session.get('change_email_step', 'verify_current')

    if not new_email:
        messages.warning(request, 'Please enter a new email first.')
        return redirect('change_email')

    if request.method == 'POST':
        otp = request.POST.get('otp', '').strip()

        if not otp or len(otp) != 6:
            messages.error(request, 'Please enter a valid 6-digit OTP.')
        elif step == 'verify_current':
            current_identifier = request.session.get('otp_identifier', '')
            result = OTPService.verify_otp(current_identifier, otp)

            if result['ok']:
                request.session['change_email_step'] = 'verify_new'
                request.session['otp_identifier'] = new_email
                request.session['otp_purpose'] = 'change_email_new'

                send = OTPService.request_otp(new_email, 'email', ip_address=_client_ip(request))
                if send['ok']:
                    dev_otp = send.get('data', {}).get('otp')
                    if dev_otp:
                        request.session['dev_otp'] = dev_otp
                    messages.success(request, f'Verified. New code sent to {_mask_identifier(new_email)}')
                    return redirect('verify_email_change')
                messages.error(request, send['reason'])
            else:
                messages.error(request, result['reason'])
        else:
            # step == 'verify_new'
            result = OTPService.verify_otp(new_email, otp)

            if result['ok']:
                request.user.email = new_email
                request.user.save()

                profile = getattr(request.user, 'account_profile', None)
                if profile:
                    profile.email_verified = True
                    profile.save()

                request.session.pop('pending_email_change', None)
                request.session.pop('change_email_step', None)
                request.session.pop('otp_identifier', None)
                request.session.pop('otp_purpose', None)

                messages.success(request, 'Email address updated successfully!')
                return redirect('settings')
            else:
                messages.error(request, result['reason'])

    dev_otp = request.session.pop('dev_otp', None)
    display_identifier = (
        _mask_identifier(request.session.get('otp_identifier', '')) if step == 'verify_current'
        else _mask_identifier(new_email)
    )

    return render(request, 'accounts/verify_change.html', {
        'identifier': display_identifier,
        'change_type': 'email',
        'dev_otp': dev_otp,
        'step': step,
    })


@login_required
@require_http_methods(["GET", "POST"])
def notification_prefs_view(request):
    """Manage notification preferences."""
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    
    if request.method == 'POST':
        form = NotificationPrefsForm(request.POST)
        if form.is_valid():
            # Store preferences in profile.notification_prefs JSON field
            prefs = profile.notification_prefs or {}
            prefs['email_subscription_expiry'] = form.cleaned_data['email_subscription_expiry']
            prefs['email_payment_receipts'] = form.cleaned_data['email_payment_receipts']
            prefs['email_product_updates'] = form.cleaned_data['email_product_updates']
            prefs['email_tips_tutorials'] = form.cleaned_data['email_tips_tutorials']
            profile.notification_prefs = prefs
            profile.save()
            messages.success(request, 'Notification preferences updated.')
            return redirect('profile')
    else:
        # Load existing preferences
        prefs = profile.notification_prefs or {}
        form = NotificationPrefsForm(initial={
            'email_subscription_expiry': prefs.get('email_subscription_expiry', True),
            'email_payment_receipts': prefs.get('email_payment_receipts', True),
            'email_product_updates': prefs.get('email_product_updates', True),
            'email_tips_tutorials': prefs.get('email_tips_tutorials', False),
            'sms_otp': True,
        })
    
    return render(request, 'accounts/notification_prefs.html', {
        'form': form,
    })


@login_required
def export_data_view(request):
    """Export user data (GDPR compliance)."""
    import json
    from django.http import HttpResponse
    
    user = request.user
    profile, _ = UserProfile.objects.get_or_create(user=user)
    
    # Collect user data
    data = {
        'account': {
            'username': user.username,
            'email': user.email,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'date_joined': user.date_joined.isoformat(),
            'last_login': user.last_login.isoformat() if user.last_login else None,
        },
        'profile': {
            'phone': profile.phone,
            'phone_verified': profile.phone_verified,
            'email_verified': profile.email_verified,
            'company_name': profile.company_name,
            'designation': profile.designation,
            'address_line1': profile.address_line1,
            'address_line2': profile.address_line2,
            'city': profile.city,
            'state': profile.state,
            'pincode': profile.pincode,
            'country': profile.country,
            'gstin': profile.gstin,
            'role': profile.role,
        },
        'sessions': list(UserSession.objects.filter(user=user, is_active=True).values(
            'device_type', 'browser', 'os', 'ip_address', 'location', 'last_activity'
        )),
        'exported_at': timezone.now().isoformat(),
    }
    
    # Return as JSON file download
    response = HttpResponse(
        json.dumps(data, indent=2, default=str),
        content_type='application/json'
    )
    response['Content-Disposition'] = 'attachment; filename="My_Data.json"'
    return response


@login_required
@require_http_methods(["GET", "POST"])
def delete_account_view(request):
    """Request account deletion."""
    if request.method == 'POST':
        form = DeleteAccountForm(request.POST)
        if form.is_valid():
            reason = form.cleaned_data.get('reason', '')
            
            # Log the deletion request
            import logging
            logger = logging.getLogger(__name__)
            logger.info(f"Account deletion requested: user={request.user.id}, reason={reason}")
            
            # Get user info before deletion
            user = request.user
            username = user.username
            
            # Logout and delete
            logout(request)
            
            # Soft delete: deactivate instead of hard delete
            user.is_active = False
            user.save()
            
            # Mark profile as deletion_requested
            profile = getattr(user, 'account_profile', None)
            if profile:
                profile.deletion_requested_at = timezone.now()
                prefs = profile.notification_prefs or {}
                prefs['deletion_reason'] = reason
                profile.notification_prefs = prefs
                profile.save()
            
            messages.success(request, 
                'Your account has been scheduled for deletion. '
                'It will be permanently removed within 30 days. '
                'Contact support if you change your mind.'
            )
            return redirect('login')
    else:
        form = DeleteAccountForm()
    
    return render(request, 'accounts/delete_account.html', {
        'form': form,
    })


# ==============================================================================
# BACKEND PREFERENCE VIEWS (Multi-State SOR Support)
# ==============================================================================

@login_required
def backend_preferences_view(request):
    """
    Show and update user's preferred backends for each module.
    Users can select their preferred SOR rates (Telangana, AP, etc.)
    """
    from subscriptions.models import Module, ModuleBackend
    from accounts.models import UserBackendPreference
    
    # Get modules that have backends
    modules_with_backends = Module.objects.filter(
        code__in=['new_estimate', 'estimate', 'workslip', 'bill', 'temp_works']
    ).order_by('display_order', 'name')
    
    # Get user's current preferences
    user_prefs = UserBackendPreference.get_user_preferences(request.user)
    
    # Build list of modules with backend options
    module_backends = []
    for module in modules_with_backends:
        electrical_backends = ModuleBackend.objects.filter(
            module=module, category='electrical', is_active=True
        ).order_by('display_order', 'name')
        
        civil_backends = ModuleBackend.objects.filter(
            module=module, category='civil', is_active=True
        ).order_by('display_order', 'name')
        
        if electrical_backends.exists() or civil_backends.exists():
            # Get user's current selection
            current_electrical = user_prefs.get((module.code, 'electrical'))
            current_civil = user_prefs.get((module.code, 'civil'))
            
            module_backends.append({
                'module': module,
                'electrical_backends': electrical_backends,
                'civil_backends': civil_backends,
                'current_electrical': current_electrical.pk if current_electrical else None,
                'current_civil': current_civil.pk if current_civil else None,
            })
    
    return render(request, 'accounts/backend_preferences.html', {
        'module_backends': module_backends,
    })


@login_required
@require_http_methods(["POST"])
def set_backend_preference_view(request):
    """
    AJAX endpoint to set a user's backend preference.
    """
    from subscriptions.models import ModuleBackend
    from accounts.models import UserBackendPreference
    
    backend_id = request.POST.get('backend_id')
    
    if not backend_id:
        return JsonResponse({'ok': False, 'error': 'Backend ID required'}, status=400)
    
    try:
        backend = ModuleBackend.objects.get(pk=backend_id, is_active=True)
    except ModuleBackend.DoesNotExist:
        return JsonResponse({'ok': False, 'error': 'Backend not found'}, status=404)
    
    # Set the preference
    UserBackendPreference.set_user_backend(request.user, backend)
    
    return JsonResponse({
        'ok': True,
        'message': f'Preference updated to {backend.name}',
        'backend': {
            'id': backend.pk,
            'name': backend.name,
            'category': backend.category,
            'module': backend.module.name,
        }
    })


@login_required
@require_http_methods(["POST"])
def clear_backend_preference_view(request):
    """
    Clear a user's backend preference for a specific module+category.
    This resets to the default backend.
    """
    from subscriptions.models import Module
    from accounts.models import UserBackendPreference
    
    module_code = request.POST.get('module_code')
    category = request.POST.get('category')
    
    if not module_code or not category:
        return JsonResponse({'ok': False, 'error': 'Module and category required'}, status=400)
    
    # Delete the preference
    deleted_count = UserBackendPreference.objects.filter(
        user=request.user,
        backend__module__code=module_code,
        backend__category=category
    ).delete()[0]
    
    return JsonResponse({
        'ok': True,
        'cleared': deleted_count > 0,
        'message': 'Preference cleared, now using default'
    })
