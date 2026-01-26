# accounts/signals.py
"""
Signal handlers for automatic profile creation and session tracking.
"""

import logging
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import User
from django.contrib.auth.signals import user_logged_in, user_logged_out

from accounts.models import UserProfile, UserSession

logger = logging.getLogger(__name__)


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    """
    Create UserProfile when new User is created.
    """
    if not created:
        return
    
    try:
        # Check if profile already exists (avoid duplicates)
        if not hasattr(instance, 'account_profile'):
            UserProfile.objects.get_or_create(user=instance)
            logger.info(f"Created UserProfile for user {instance.username}")
    except Exception as e:
        logger.error(f"Error creating UserProfile for user {instance.username}: {e}")


@receiver(user_logged_in)
def track_user_login(sender, request, user, **kwargs):
    """
    Track user login - update profile and create session record.
    ENFORCES SINGLE DEVICE LOGIN: Logs out all other sessions when user logs in.
    """
    from django.utils import timezone
    from django.contrib.sessions.models import Session
    
    try:
        # Update last login on profile
        if hasattr(user, 'account_profile'):
            user.account_profile.last_login_at = timezone.now()
            user.account_profile.save(update_fields=['last_login_at'])
        
        # Create session record if session exists
        if hasattr(request, 'session') and request.session.session_key:
            # Parse user agent for device info
            user_agent = request.META.get('HTTP_USER_AGENT', '')
            device_info = _parse_user_agent(user_agent)
            
            # Get IP address
            ip = _get_client_ip(request)
            
            # ============================================================
            # SINGLE DEVICE LOGIN ENFORCEMENT
            # Log out ALL other active sessions for this user
            # ============================================================
            current_session_key = request.session.session_key
            
            # Get all other active sessions for this user
            other_sessions = UserSession.objects.filter(
                user=user,
                is_active=True
            ).exclude(session_key=current_session_key)
            
            # Delete the actual Django sessions (this kicks them out)
            for user_session in other_sessions:
                try:
                    Session.objects.filter(session_key=user_session.session_key).delete()
                    logger.info(f"Kicked out session {user_session.session_key[:8]}... for user {user.username}")
                except Exception as e:
                    logger.warning(f"Could not delete session: {e}")
            
            # Mark all other UserSession records as inactive
            other_sessions.update(is_active=False, is_current=False)
            
            logger.info(f"Single-device enforcement: Logged out {other_sessions.count()} other sessions for {user.username}")
            # ============================================================
            
            # Create or update current session record
            UserSession.objects.update_or_create(
                session_key=request.session.session_key,
                defaults={
                    'user': user,
                    'ip_address': ip,
                    'user_agent': user_agent,
                    'device_type': device_info.get('device_type', ''),
                    'device_name': device_info.get('device_name', ''),
                    'browser': device_info.get('browser', ''),
                    'os': device_info.get('os', ''),
                    'is_active': True,
                    'is_current': True,
                }
            )
            
            logger.info(f"Session tracked for user {user.username} from {ip}")
    
    except Exception as e:
        logger.error(f"Error tracking login for {user.username}: {e}")


@receiver(user_logged_out)
def track_user_logout(sender, request, user, **kwargs):
    """
    Mark session as inactive on logout.
    """
    if not user:
        return
    
    try:
        if hasattr(request, 'session') and request.session.session_key:
            UserSession.objects.filter(
                session_key=request.session.session_key
            ).update(is_active=False)
            
            logger.info(f"Session ended for user {user.username}")
    
    except Exception as e:
        logger.error(f"Error tracking logout for {user.username}: {e}")


def _get_client_ip(request):
    """Extract client IP from request headers"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0].strip()
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


def _parse_user_agent(user_agent):
    """
    Parse user agent string to extract device info.
    Returns dict with device_type, device_name, browser, os
    """
    ua = user_agent.lower()
    
    # Detect device type
    if 'mobile' in ua or 'android' in ua and 'mobile' in ua:
        device_type = 'mobile'
    elif 'tablet' in ua or 'ipad' in ua:
        device_type = 'tablet'
    else:
        device_type = 'desktop'
    
    # Detect browser
    browser = 'Unknown'
    if 'chrome' in ua and 'edg' not in ua:
        browser = 'Chrome'
    elif 'firefox' in ua:
        browser = 'Firefox'
    elif 'safari' in ua and 'chrome' not in ua:
        browser = 'Safari'
    elif 'edg' in ua:
        browser = 'Edge'
    elif 'opera' in ua or 'opr' in ua:
        browser = 'Opera'
    
    # Detect OS
    os_name = 'Unknown'
    if 'windows' in ua:
        os_name = 'Windows'
    elif 'mac os' in ua or 'macintosh' in ua:
        os_name = 'macOS'
    elif 'linux' in ua and 'android' not in ua:
        os_name = 'Linux'
    elif 'android' in ua:
        os_name = 'Android'
    elif 'iphone' in ua or 'ipad' in ua:
        os_name = 'iOS'
    
    device_name = f"{browser} on {os_name}"
    
    return {
        'device_type': device_type,
        'device_name': device_name,
        'browser': browser,
        'os': os_name,
    }
