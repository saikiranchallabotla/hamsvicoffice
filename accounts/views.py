# accounts/views.py
"""
OTP-based authentication views.

Flows:
1. Login: Enter phone → Request OTP → Verify OTP → Dashboard
2. Register: Enter details + phone → Request OTP → Verify → Dashboard
3. Logout: Clear session
"""

import json
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
    
    if request.method == 'POST':
        identifier = request.POST.get('identifier', '').strip()
        
        if not identifier:
            messages.error(request, 'Please enter your phone number or email.')
            return render(request, 'accounts/login.html')
        
        # Check if user exists
        user = _find_user(identifier)
        if not user:
            messages.error(request, 'No account found with this phone/email. Please register.')
            return render(request, 'accounts/login.html', {'identifier': identifier})
        
        # Store identifier in session for OTP verification
        request.session['otp_identifier'] = identifier
        request.session['otp_purpose'] = 'login'
        
        # Request OTP
        channel = 'email' if '@' in identifier else 'sms'
        result = OTPService.request_otp(identifier, channel)
        
        if result['ok']:
            # Store OTP in session for popup display
            otp = result.get('data', {}).get('otp')
            if otp:
                request.session['show_otp'] = otp
            messages.success(request, f'OTP sent to {_mask_identifier(identifier)}')
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
    
    # Get OTP for popup display (if set)
    show_otp = request.session.pop('show_otp', None)
    
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
    result = OTPService.request_otp(identifier, channel)
    
    if result['ok']:
        response_data = {
            'ok': True,
            'reason': 'OTP sent successfully.',
            'cooldown': result['data'].get('cooldown', 60),
        }
        # In DEBUG mode, include OTP for testing
        if settings.DEBUG and result.get('data', {}).get('otp'):
            response_data['otp'] = result['data']['otp']
            response_data['reason'] = f"OTP sent. [DEV MODE] Your OTP is: {result['data']['otp']}"
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
        phone = request.POST.get('phone', '').strip()
        company = request.POST.get('company', '').strip()
        
        # Validate
        errors = []
        if not first_name:
            errors.append('First name is required.')
        if not phone:
            errors.append('Phone number is required.')
        if email and User.objects.filter(email=email).exists():
            errors.append('Email already registered.')
        if phone and UserProfile.objects.filter(phone=phone).exists():
            errors.append('Phone number already registered.')
        
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
        request.session['otp_identifier'] = phone
        request.session['otp_purpose'] = 'register'
        
        # Request OTP
        result = OTPService.request_otp(phone, 'sms')
        
        if result['ok']:
            # Store OTP in session for popup display (testing mode)
            otp = result.get('data', {}).get('otp')
            if otp:
                request.session['show_otp'] = otp
            messages.success(request, f'OTP sent to {_mask_identifier(phone)}')
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

@login_required
def logout_view(request):
    """
    Logout current session.
    """
    # Mark session as inactive
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
    
    # For login, check user exists
    if purpose == 'login':
        user = _find_user(identifier)
        if not user:
            return JsonResponse({
                'ok': False,
                'code': 'NOT_FOUND',
                'reason': 'No account found. Please register.',
            }, status=404)
    
    # For register, check user doesn't exist
    if purpose == 'register':
        if _find_user(identifier):
            return JsonResponse({
                'ok': False,
                'code': 'EXISTS',
                'reason': 'Account already exists. Please login.',
            }, status=409)
    
    # Request OTP
    channel = 'email' if '@' in identifier else 'sms'
    result = OTPService.request_otp(identifier, channel)
    
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
    Body: {"identifier": "+919876543210", "otp": "123456", "register_data": {...}}
    """
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'ok': False, 'reason': 'Invalid JSON.'}, status=400)
    
    identifier = data.get('identifier') or request.session.get('otp_identifier')
    otp = data.get('otp', '').strip()
    purpose = data.get('purpose') or request.session.get('otp_purpose', 'login')
    register_data = data.get('register_data', {})
    
    if not identifier:
        return JsonResponse({'ok': False, 'reason': 'Identifier required.'}, status=400)
    
    if not otp or len(otp) != 6:
        return JsonResponse({'ok': False, 'reason': 'Valid 6-digit OTP required.'}, status=400)
    
    # Verify OTP
    result = OTPService.verify_otp(identifier, otp)
    
    if not result['ok']:
        return JsonResponse(result, status=400)
    
    # Handle based on purpose
    if purpose == 'register':
        # Create user
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
        logger.error(f"Error checking session validity: {e}")
        return JsonResponse({
            'valid': True  # Assume valid on error to avoid false kicks
        })


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def _find_user(identifier: str):
    """Find user by phone or email."""
    identifier = identifier.strip().lower()
    
    # Check by email
    if '@' in identifier:
        return User.objects.filter(email=identifier).first()
    
    # Check by phone
    phone = ''.join(c for c in identifier if c.isdigit() or c == '+')
    profile = UserProfile.objects.filter(phone=phone).select_related('user').first()
    return profile.user if profile else None


def _create_user(identifier: str, data: dict):
    """
    Create new user from registration data.
    Uses database transaction to prevent race conditions.
    """
    from django.db import transaction, IntegrityError
    import logging
    
    phone = ''.join(c for c in identifier if c.isdigit() or c == '+')
    email = data.get('email', '')
    first_name = data.get('first_name', '')
    last_name = data.get('last_name', '')
    company = data.get('company', '')
    
    try:
        with transaction.atomic():
            # Double-check phone is not already registered (race condition prevention)
            existing_profile = UserProfile.objects.filter(phone=phone).select_for_update().first()
            if existing_profile:
                logging.warning(f"Phone {phone} already registered (race condition caught)")
                return existing_profile.user
            
            # Double-check email is not already registered
            if email:
                existing_user = User.objects.filter(email=email).first()
                if existing_user:
                    logging.warning(f"Email {email} already registered (race condition caught)")
                    # If email exists but phone doesn't, could be a conflict
                    # For now, return None to show error to user
                    return None
            
            # Generate username from phone
            username = f"user_{phone[-10:]}"
            counter = 1
            while User.objects.filter(username=username).exists():
                username = f"user_{phone[-10:]}_{counter}"
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
            
            # Create profile with phone
            profile = UserProfile.objects.create(
                user=user,
                phone=phone,
                phone_verified=True,
                company_name=company
            )
            
            logging.info(f"Created new user: {username} with phone: {phone}")
            return user
            
    except IntegrityError as e:
        # Handle database constraint violations (duplicate phone/email)
        logging.error(f"IntegrityError creating user: {e}")
        # Try to find and return existing user by phone
        profile = UserProfile.objects.filter(phone=phone).select_related('user').first()
        if profile:
            return profile.user
        return None
    except Exception as e:
        logging.error(f"Failed to create user: {e}")
        return None


def _handle_login_success(request, identifier):
    """Handle successful login."""
    user = _find_user(identifier)
    if not user:
        messages.error(request, 'Account not found.')
        return redirect('login')
    
    login(request, user, backend='django.contrib.auth.backends.ModelBackend')
    
    # Ensure profile exists and update it
    profile, created = UserProfile.objects.get_or_create(user=user)
    if created:
        # Profile was missing (legacy user or edge case) - populate from identifier
        if '@' not in identifier:
            phone = ''.join(c for c in identifier if c.isdigit() or c == '+')
            profile.phone = phone
            profile.phone_verified = True
        else:
            profile.email_verified = True
    else:
        # Update verification status
        profile.last_login_at = timezone.now()
        if '@' not in identifier:
            profile.phone_verified = True
        else:
            profile.email_verified = True
    profile.save()
    
    messages.success(request, f'Welcome back, {user.first_name or user.username}!')
    
    # Redirect to next or dashboard
    next_url = request.session.pop('next', None) or request.GET.get('next', '/dashboard/')
    return redirect(next_url)


def _handle_register_success(request, identifier):
    """Handle successful registration."""
    register_data = request.session.pop('register_data', {})
    
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
    Step 1: Enter new phone → Request OTP to new phone
    Step 2: Verify OTP → Update phone
    """
    profile = getattr(request.user, 'account_profile', None)
    current_phone = profile.phone if profile else None
    
    if request.method == 'POST':
        form = ChangePhoneForm(request.POST)
        if form.is_valid():
            new_phone = form.cleaned_data['new_phone']
            
            # Store in session for verification
            request.session['pending_phone_change'] = new_phone
            request.session['otp_identifier'] = new_phone
            request.session['otp_purpose'] = 'change_phone'
            
            # Send OTP to new phone
            result = OTPService.request_otp(new_phone, 'sms')
            
            if result['ok']:
                # Store dev OTP in session for display
                dev_otp = result.get('data', {}).get('otp')
                if dev_otp:
                    request.session['dev_otp'] = dev_otp
                messages.success(request, f'OTP sent to {_mask_identifier(new_phone)}')
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
    """Verify OTP for phone change."""
    new_phone = request.session.get('pending_phone_change')
    
    if not new_phone:
        messages.warning(request, 'Please enter a new phone number first.')
        return redirect('change_phone')
    
    if request.method == 'POST':
        otp = request.POST.get('otp', '').strip()
        
        if not otp or len(otp) != 6:
            messages.error(request, 'Please enter a valid 6-digit OTP.')
        else:
            result = OTPService.verify_otp(new_phone, otp)
            
            if result['ok']:
                # Update phone
                profile, _ = UserProfile.objects.get_or_create(user=request.user)
                profile.phone = new_phone
                profile.phone_verified = True
                profile.save()
                
                # Clear session
                del request.session['pending_phone_change']
                request.session.pop('otp_identifier', None)
                request.session.pop('otp_purpose', None)
                
                messages.success(request, 'Phone number updated successfully!')
                return redirect('settings')
            else:
                messages.error(request, result['reason'])
    
    # Get and clear dev OTP for display
    dev_otp = request.session.pop('dev_otp', None)
    
    return render(request, 'accounts/verify_change.html', {
        'identifier': _mask_identifier(new_phone),
        'change_type': 'phone',
        'dev_otp': dev_otp,
    })


@login_required
@require_http_methods(["GET", "POST"])
def change_email_view(request):
    """
    Request email change.
    Step 1: Enter new email → Request OTP to new email
    Step 2: Verify OTP → Update email
    """
    current_email = request.user.email
    
    if request.method == 'POST':
        form = ChangeEmailForm(request.POST)
        if form.is_valid():
            new_email = form.cleaned_data['new_email']
            
            # Store in session for verification
            request.session['pending_email_change'] = new_email
            request.session['otp_identifier'] = new_email
            request.session['otp_purpose'] = 'change_email'
            
            # Send OTP to new email
            result = OTPService.request_otp(new_email, 'email')
            
            if result['ok']:
                # Store dev OTP in session for display
                dev_otp = result.get('data', {}).get('otp')
                if dev_otp:
                    request.session['dev_otp'] = dev_otp
                messages.success(request, f'OTP sent to {_mask_identifier(new_email)}')
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
    """Verify OTP for email change."""
    new_email = request.session.get('pending_email_change')
    
    if not new_email:
        messages.warning(request, 'Please enter a new email first.')
        return redirect('change_email')
    
    if request.method == 'POST':
        otp = request.POST.get('otp', '').strip()
        
        if not otp or len(otp) != 6:
            messages.error(request, 'Please enter a valid 6-digit OTP.')
        else:
            result = OTPService.verify_otp(new_email, otp)
            
            if result['ok']:
                # Update email
                request.user.email = new_email
                request.user.save()
                
                # Update profile verification
                profile = getattr(request.user, 'account_profile', None)
                if profile:
                    profile.email_verified = True
                    profile.save()
                
                # Clear session
                del request.session['pending_email_change']
                request.session.pop('otp_identifier', None)
                request.session.pop('otp_purpose', None)
                
                messages.success(request, 'Email address updated successfully!')
                return redirect('settings')
            else:
                messages.error(request, result['reason'])
    
    # Get and clear dev OTP for display
    dev_otp = request.session.pop('dev_otp', None)
    
    return render(request, 'accounts/verify_change.html', {
        'identifier': _mask_identifier(new_email),
        'change_type': 'email',
        'dev_otp': dev_otp,
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
    response['Content-Disposition'] = f'attachment; filename="my_data_{user.username}.json"'
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
