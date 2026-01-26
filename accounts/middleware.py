# accounts/middleware.py
"""
Session tracking and user activity middleware.
SINGLE DEVICE LOGIN: Only one device can be logged in at a time.
"""

import logging
from django.utils import timezone
from django.conf import settings
from django.contrib.auth import logout
from django.contrib import messages
from django.shortcuts import redirect

logger = logging.getLogger(__name__)

# SINGLE DEVICE LOGIN: Set to 1 to allow only one device at a time
MAX_CONCURRENT_SESSIONS = getattr(settings, 'MAX_CONCURRENT_SESSIONS', 1)


class SessionTrackingMiddleware:
    """
    Track user sessions and update last activity.
    
    Features:
    - Creates/updates UserSession on login
    - Updates last_activity periodically
    - Tracks device info, IP, location
    - Handles session expiry
    - ENFORCES SINGLE DEVICE LOGIN (kicks out previous session on new login)
    - Validates session on each request (kicks out if session was invalidated)
    """
    
    # Update interval in seconds (don't update on every request)
    UPDATE_INTERVAL = 60  # 1 minute
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # Validate session first (check if kicked out by another login)
        kicked_out = self._check_if_kicked_out(request)
        if kicked_out:
            return kicked_out
        
        # Process request
        self._track_session(request)
        
        response = self.get_response(request)
        
        return response
    
    def _check_if_kicked_out(self, request):
        """
        Check if this session was invalidated by another login.
        If so, logout the user and redirect to login page with message.
        """
        if not request.user.is_authenticated:
            return None
        
        session_key = request.session.session_key
        if not session_key:
            return None
        
        try:
            from accounts.models import UserSession
            
            # Check if this session is still valid
            user_session = UserSession.objects.filter(
                user=request.user,
                session_key=session_key
            ).first()
            
            # If session doesn't exist or is marked inactive, kick them out
            if not user_session or not user_session.is_active:
                logger.info(f"User {request.user.username} kicked out - session invalidated by login on another device")
                
                # Logout the user
                logout(request)
                
                # Add message for login page
                messages.warning(
                    request, 
                    "You have been logged out because your account was accessed from another device. "
                    "Only one device can be logged in at a time."
                )
                
                # Redirect to login
                from django.urls import reverse
                return redirect(reverse('accounts:login'))
        
        except Exception as e:
            logger.error(f"Error checking session validity: {e}")
        
        return None
    
    def _track_session(self, request):
        """Track or update user session."""
        if not request.user.is_authenticated:
            return
        
        session_key = request.session.session_key
        if not session_key:
            request.session.create()
            session_key = request.session.session_key
        
        # Check if we need to update (throttle updates)
        last_update = request.session.get('_session_last_update')
        now = timezone.now()
        
        if last_update:
            from datetime import datetime
            try:
                last_update_dt = datetime.fromisoformat(last_update)
                if hasattr(last_update_dt, 'tzinfo') and last_update_dt.tzinfo is None:
                    from django.utils.timezone import make_aware
                    last_update_dt = make_aware(last_update_dt)
                
                delta = (now - last_update_dt).total_seconds()
                if delta < self.UPDATE_INTERVAL:
                    return
            except (ValueError, TypeError):
                pass
        
        # Update session
        try:
            from accounts.models import UserSession
            
            session, created = UserSession.objects.get_or_create(
                user=request.user,
                session_key=session_key,
                defaults={
                    'ip_address': self._get_client_ip(request),
                    'user_agent': request.META.get('HTTP_USER_AGENT', '')[:500],
                    'device_type': self._get_device_type(request),
                }
            )
            
            if created:
                # New session - enforce concurrent session limit
                self._enforce_session_limit(request.user, session_key)
            else:
                session.last_activity = now
                session.save(update_fields=['last_activity'])
            
            # Store update time
            request.session['_session_last_update'] = now.isoformat()
            
        except Exception as e:
            logger.error(f"Session tracking error: {e}")
    
    def _enforce_session_limit(self, user, current_session_key):
        """
        Enforce max concurrent sessions limit.
        Logout oldest sessions if limit exceeded (Netflix-style).
        """
        from accounts.models import UserSession
        
        active_sessions = UserSession.objects.filter(
            user=user,
            is_active=True
        ).order_by('-last_activity')
        
        session_count = active_sessions.count()
        
        if session_count > MAX_CONCURRENT_SESSIONS:
            # Get sessions to terminate (oldest ones, excluding current)
            sessions_to_kill = active_sessions.exclude(
                session_key=current_session_key
            ).order_by('last_activity')[:session_count - MAX_CONCURRENT_SESSIONS]
            
            for session in sessions_to_kill:
                session.is_active = False
                session.save(update_fields=['is_active'])
                
                # Also delete the Django session
                try:
                    from django.contrib.sessions.models import Session
                    Session.objects.filter(session_key=session.session_key).delete()
                except Exception as e:
                    logger.debug(f"Could not delete Django session: {e}")
            
            logger.info(
                f"User {user.username}: Terminated {len(sessions_to_kill)} old session(s) "
                f"due to concurrent session limit ({MAX_CONCURRENT_SESSIONS})"
            )
    
    def _get_client_ip(self, request):
        """Get client IP address."""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR', '')
        return ip[:45]  # Max length
    
    def _get_device_type(self, request):
        """Detect device type from user agent."""
        ua = request.META.get('HTTP_USER_AGENT', '').lower()
        
        if 'mobile' in ua or 'android' in ua or 'iphone' in ua:
            return 'Mobile'
        elif 'tablet' in ua or 'ipad' in ua:
            return 'Tablet'
        else:
            return 'Desktop'


class ConcurrentSessionCheckMiddleware:
    """
    Check if current session has been terminated due to concurrent login limit.
    If session is marked inactive, log user out and show message.
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        if request.user.is_authenticated:
            session_key = request.session.session_key
            
            if session_key:
                try:
                    from accounts.models import UserSession
                    
                    user_session = UserSession.objects.filter(
                        user=request.user,
                        session_key=session_key
                    ).first()
                    
                    # If session exists but is marked inactive, log out the user
                    if user_session and not user_session.is_active:
                        logout(request)
                        messages.warning(
                            request,
                            'You have been logged out because your account was accessed from another device. '
                            f'Only {MAX_CONCURRENT_SESSIONS} simultaneous session(s) allowed.'
                        )
                        return redirect('login')
                        
                except Exception as e:
                    logger.debug(f"Concurrent session check error: {e}")
        
        response = self.get_response(request)
        return response


class LastActivityMiddleware:
    """
    Simple middleware to update user's last activity timestamp.
    Lighter weight than full session tracking.
    """
    
    UPDATE_INTERVAL = 300  # 5 minutes
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        response = self.get_response(request)
        
        if request.user.is_authenticated:
            self._update_last_activity(request)
        
        return response
    
    def _update_last_activity(self, request):
        """Update user profile's last activity."""
        try:
            from accounts.models import UserProfile
            
            # Throttle updates
            cache_key = f'last_activity_{request.user.id}'
            
            # Use cache if available
            from django.core.cache import cache
            if cache.get(cache_key):
                return
            
            # Update profile
            UserProfile.objects.filter(user=request.user).update(
                last_activity_at=timezone.now()
            )
            
            # Set cache to prevent frequent updates
            cache.set(cache_key, True, self.UPDATE_INTERVAL)
            
        except Exception as e:
            logger.debug(f"Last activity update error: {e}")
