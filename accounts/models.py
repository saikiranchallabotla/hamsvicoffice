# accounts/models.py
"""
User accounts, OTP authentication, profiles, and session management.

Models:
- OTPToken: Store OTP codes for login/verification
- OTPRateLimit: Rate limiting for OTP requests
- UserProfile: Extended user profile with phone, verification, role
- UserSession: Track active sessions for logout-all-devices
"""

import secrets
import hashlib
from datetime import timedelta
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.core.validators import RegexValidator


# ==============================================================================
# VALIDATORS
# ==============================================================================

phone_validator = RegexValidator(
    regex=r'^\+?[1-9]\d{9,14}$',
    message="Phone number must be 10-15 digits with optional + prefix"
)

gstin_validator = RegexValidator(
    regex=r'^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$',
    message="Enter a valid 15-character GSTIN"
)


# ==============================================================================
# OTP MODELS
# ==============================================================================

class OTPToken(models.Model):
    """
    Store OTP codes for phone/email verification and login.
    OTPs expire after 5 minutes and are single-use.
    """
    OTP_TYPE_CHOICES = (
        ('login', 'Login'),
        ('verify_phone', 'Verify Phone'),
        ('verify_email', 'Verify Email'),
        ('reset_password', 'Reset Password'),
    )
    
    # User can be null for first-time login (before account exists)
    user = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name='otp_tokens',
        null=True, 
        blank=True
    )
    
    # Contact info (one of these must be set)
    phone = models.CharField(
        max_length=20, 
        blank=True, 
        null=True,
        validators=[phone_validator],
        db_index=True
    )
    email = models.EmailField(blank=True, null=True, db_index=True)
    
    # OTP details
    otp_code = models.CharField(max_length=6)  # 6-digit OTP
    otp_hash = models.CharField(max_length=64)  # SHA256 hash for security
    otp_type = models.CharField(max_length=20, choices=OTP_TYPE_CHOICES, default='login')
    
    # Security
    expires_at = models.DateTimeField(db_index=True)
    attempts = models.PositiveIntegerField(default=0)  # Wrong attempts count
    max_attempts = models.PositiveIntegerField(default=5)
    is_verified = models.BooleanField(default=False)
    
    # Metadata
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    verified_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['phone', 'otp_type', 'is_verified']),
            models.Index(fields=['email', 'otp_type', 'is_verified']),
            models.Index(fields=['expires_at']),
        ]
    
    def __str__(self):
        identifier = self.phone or self.email
        return f"OTP for {identifier} ({self.otp_type})"
    
    @classmethod
    def generate_otp(cls):
        """Generate a secure 6-digit OTP"""
        return ''.join([str(secrets.randbelow(10)) for _ in range(6)])
    
    @classmethod
    def hash_otp(cls, otp_code):
        """Hash OTP for secure storage"""
        return hashlib.sha256(otp_code.encode()).hexdigest()
    
    def is_expired(self):
        """Check if OTP has expired"""
        return timezone.now() > self.expires_at
    
    def is_locked(self):
        """Check if too many wrong attempts"""
        return self.attempts >= self.max_attempts
    
    def verify(self, otp_code):
        """
        Verify OTP code. Returns (success, error_message)
        """
        if self.is_verified:
            return False, "OTP already used"
        
        if self.is_expired():
            return False, "OTP expired"
        
        if self.is_locked():
            return False, "Too many wrong attempts. Request a new OTP."
        
        if self.otp_hash != self.hash_otp(otp_code):
            self.attempts += 1
            self.save(update_fields=['attempts'])
            remaining = self.max_attempts - self.attempts
            if remaining > 0:
                return False, f"Invalid OTP. {remaining} attempts remaining."
            return False, "Too many wrong attempts. Request a new OTP."
        
        # Success
        self.is_verified = True
        self.verified_at = timezone.now()
        self.save(update_fields=['is_verified', 'verified_at'])
        return True, None
    
    def save(self, *args, **kwargs):
        # Set expiry if not set (5 minutes from now)
        if not self.expires_at:
            self.expires_at = timezone.now() + timedelta(minutes=5)
        
        # Hash OTP if not already hashed
        if self.otp_code and len(self.otp_code) == 6 and not self.otp_hash:
            self.otp_hash = self.hash_otp(self.otp_code)
        
        super().save(*args, **kwargs)


class OTPRateLimit(models.Model):
    """
    Rate limiting for OTP requests.
    Prevents spam/abuse by limiting requests per phone/email/IP.
    """
    IDENTIFIER_TYPE_CHOICES = (
        ('phone', 'Phone'),
        ('email', 'Email'),
        ('ip', 'IP Address'),
    )
    
    identifier = models.CharField(max_length=255, db_index=True)  # phone/email/IP
    identifier_type = models.CharField(max_length=10, choices=IDENTIFIER_TYPE_CHOICES)
    
    # Counters
    request_count = models.PositiveIntegerField(default=0)  # Requests in current window
    failed_attempts = models.PositiveIntegerField(default=0)  # Failed verifications
    
    # Lockout
    locked_until = models.DateTimeField(null=True, blank=True)
    lockout_count = models.PositiveIntegerField(default=0)  # How many times locked out
    
    # Timestamps
    window_start = models.DateTimeField(auto_now_add=True)
    last_request_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['identifier', 'identifier_type']
        indexes = [
            models.Index(fields=['identifier', 'identifier_type']),
            models.Index(fields=['locked_until']),
        ]
    
    def __str__(self):
        return f"RateLimit: {self.identifier_type}={self.identifier}"
    
    # Rate limit settings
    MAX_REQUESTS_PER_HOUR = 10
    MAX_FAILED_ATTEMPTS = 5
    LOCKOUT_DURATION_MINUTES = 30
    RESEND_COOLDOWN_SECONDS = 60
    
    def is_locked(self):
        """Check if currently locked out"""
        if self.locked_until and timezone.now() < self.locked_until:
            return True
        return False
    
    def seconds_until_next_request(self):
        """Get seconds until next OTP request allowed (resend cooldown)"""
        if not self.last_request_at:
            return 0
        
        elapsed = (timezone.now() - self.last_request_at).total_seconds()
        remaining = self.RESEND_COOLDOWN_SECONDS - elapsed
        return max(0, int(remaining))
    
    def can_request_otp(self):
        """
        Check if OTP request is allowed.
        Returns (allowed, error_message, cooldown_seconds)
        """
        # Check lockout
        if self.is_locked():
            remaining = (self.locked_until - timezone.now()).total_seconds()
            return False, f"Too many attempts. Try again in {int(remaining // 60)} minutes.", 0
        
        # Check cooldown
        cooldown = self.seconds_until_next_request()
        if cooldown > 0:
            return False, f"Please wait {cooldown} seconds before requesting another OTP.", cooldown
        
        # Check hourly limit
        if self._is_window_expired():
            self._reset_window()
        
        if self.request_count >= self.MAX_REQUESTS_PER_HOUR:
            return False, "Too many OTP requests. Try again in an hour.", 0
        
        return True, None, 0
    
    def record_request(self):
        """Record an OTP request"""
        if self._is_window_expired():
            self._reset_window()
        
        self.request_count += 1
        self.last_request_at = timezone.now()
        self.save(update_fields=['request_count', 'last_request_at'])
    
    def record_failed_attempt(self):
        """Record a failed verification attempt"""
        self.failed_attempts += 1
        
        if self.failed_attempts >= self.MAX_FAILED_ATTEMPTS:
            self.locked_until = timezone.now() + timedelta(minutes=self.LOCKOUT_DURATION_MINUTES)
            self.lockout_count += 1
            self.failed_attempts = 0  # Reset for next lockout period
        
        self.save(update_fields=['failed_attempts', 'locked_until', 'lockout_count'])
    
    def reset_on_success(self):
        """Reset counters on successful verification"""
        self.failed_attempts = 0
        self.locked_until = None
        self.save(update_fields=['failed_attempts', 'locked_until'])
    
    def _is_window_expired(self):
        """Check if the rate limit window (1 hour) has expired"""
        return (timezone.now() - self.window_start).total_seconds() > 3600
    
    def _reset_window(self):
        """Reset the rate limit window"""
        self.window_start = timezone.now()
        self.request_count = 0


# ==============================================================================
# USER PROFILE (Extended)
# ==============================================================================

class UserProfile(models.Model):
    """
    Extended user profile for SaaS features.
    Stores phone, verification status, role, preferences.
    """
    ROLE_CHOICES = (
        ('superadmin', 'Super Admin'),
        ('admin', 'Admin'),
        ('user', 'User'),
    )
    
    SUBSCRIPTION_CHOICES = (
        ('free', 'Free'),
        ('starter', 'Starter'),
        ('professional', 'Professional'),
        ('enterprise', 'Enterprise'),
    )
    
    user = models.OneToOneField(
        User, 
        on_delete=models.CASCADE, 
        related_name='account_profile'  # Changed to avoid conflict with core.UserProfile
    )
    
    # Contact info
    phone = models.CharField(
        max_length=20, 
        unique=True, 
        null=True, 
        blank=True,
        validators=[phone_validator]
    )
    phone_verified = models.BooleanField(default=False)
    email_verified = models.BooleanField(default=False)
    
    # Organization info
    company_name = models.CharField(max_length=255, blank=True)
    department = models.CharField(max_length=255, blank=True)
    designation = models.CharField(max_length=255, blank=True)
    
    # Address
    address_line1 = models.CharField(max_length=255, blank=True)
    address_line2 = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=100, blank=True)
    state = models.CharField(max_length=100, blank=True)
    pincode = models.CharField(max_length=10, blank=True)
    country = models.CharField(max_length=100, default='India')
    
    # Billing info
    gstin = models.CharField(
        max_length=15, 
        blank=True,
        validators=[gstin_validator],
        help_text="15-character GST Identification Number"
    )
    
    # Role & status
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='user')
    profile_completed = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    
    # Legacy subscription (will be replaced by subscriptions app)
    subscription_tier = models.CharField(
        max_length=20, 
        choices=SUBSCRIPTION_CHOICES, 
        default='free'
    )
    
    # Preferences
    notification_prefs = models.JSONField(default=dict, blank=True)
    # Default: {"email_updates": True, "sms_updates": False, "marketing": False}
    
    # Privacy & data
    data_export_requested_at = models.DateTimeField(null=True, blank=True)
    deletion_requested_at = models.DateTimeField(null=True, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_login_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        verbose_name = 'User Profile'
        verbose_name_plural = 'User Profiles'
        indexes = [
            models.Index(fields=['phone']),
            models.Index(fields=['role']),
            models.Index(fields=['profile_completed']),
        ]
    
    def __str__(self):
        return f"{self.user.get_full_name() or self.user.username} ({self.role})"
    
    def get_full_address(self):
        """Return formatted full address"""
        parts = [
            self.address_line1,
            self.address_line2,
            self.city,
            self.state,
            self.pincode,
            self.country
        ]
        return ', '.join([p for p in parts if p])
    
    def is_superadmin(self):
        return self.role == 'superadmin'
    
    def is_admin(self):
        return self.role in ('superadmin', 'admin')
    
    def is_profile_complete(self):
        """Check if minimum required profile fields are filled"""
        return all([
            self.user.first_name,
            self.company_name or self.department,
            self.phone or self.user.email
        ])
    
    def get_default_notification_prefs(self):
        return {
            'email_updates': True,
            'sms_updates': False,
            'marketing': False,
            'ticket_updates': True,
            'subscription_reminders': True,
        }
    
    def save(self, *args, **kwargs):
        # Set default notification prefs if empty
        if not self.notification_prefs:
            self.notification_prefs = self.get_default_notification_prefs()
        
        # Update profile_completed status
        self.profile_completed = self.is_profile_complete()
        
        super().save(*args, **kwargs)


# ==============================================================================
# SESSION MANAGEMENT
# ==============================================================================

class UserSession(models.Model):
    """
    Track active user sessions for security and logout-all-devices feature.
    """
    user = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name='active_sessions'
    )
    
    # Session info
    session_key = models.CharField(max_length=40, unique=True, db_index=True)
    
    # Device info
    device_type = models.CharField(max_length=50, blank=True)  # mobile/desktop/tablet
    device_name = models.CharField(max_length=255, blank=True)  # "Chrome on Windows"
    browser = models.CharField(max_length=100, blank=True)
    os = models.CharField(max_length=100, blank=True)
    
    # Network info
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    location = models.CharField(max_length=255, blank=True)  # "Mumbai, India"
    user_agent = models.TextField(blank=True)
    
    # Status
    is_active = models.BooleanField(default=True)
    is_current = models.BooleanField(default=False)  # Mark current session
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    last_activity = models.DateTimeField(auto_now=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-last_activity']
        indexes = [
            models.Index(fields=['user', 'is_active']),
            models.Index(fields=['session_key']),
            models.Index(fields=['expires_at']),
        ]
    
    def __str__(self):
        return f"{self.user.username} - {self.device_name or 'Unknown Device'}"
    
    def is_expired(self):
        """Check if session has expired"""
        if self.expires_at:
            return timezone.now() > self.expires_at
        return False
    
    def logout(self):
        """Mark session as logged out"""
        self.is_active = False
        self.save(update_fields=['is_active'])
    
    @classmethod
    def logout_all(cls, user, except_session_key=None):
        """
        Logout all sessions for a user.
        Optionally keep current session active.
        """
        sessions = cls.objects.filter(user=user, is_active=True)
        if except_session_key:
            sessions = sessions.exclude(session_key=except_session_key)
        
        count = sessions.update(is_active=False)
        return count
    
    @classmethod
    def cleanup_expired(cls):
        """Remove expired sessions (run periodically)"""
        return cls.objects.filter(
            expires_at__lt=timezone.now()
        ).delete()[0]


# ==============================================================================
# USER BACKEND PREFERENCE (Multi-State SOR Support)
# ==============================================================================

class UserBackendPreference(models.Model):
    """
    Track which backend (SOR rates) a user prefers for each module and category.
    This allows users to select their state's rates (Telangana, AP, Karnataka, etc.)
    
    Example:
    - User A prefers Telangana Electrical for New Estimate module
    - User B prefers AP Civil for Workslip module
    """
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='backend_preferences'
    )
    
    # Link to the preferred backend
    backend = models.ForeignKey(
        'subscriptions.ModuleBackend',
        on_delete=models.CASCADE,
        related_name='user_preferences'
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        # One preference per user per module+category combination
        unique_together = ['user', 'backend']
        ordering = ['-updated_at']
        verbose_name = 'User Backend Preference'
        verbose_name_plural = 'User Backend Preferences'
    
    def __str__(self):
        return f"{self.user.username} → {self.backend.name}"
    
    @classmethod
    def get_user_backend(cls, user, module_code, category):
        """
        Get the user's preferred backend for a module and category.
        Falls back to default backend if no preference set.
        
        Args:
            user: User instance
            module_code: e.g., 'new_estimate', 'workslip'
            category: 'electrical' or 'civil'
        
        Returns:
            ModuleBackend instance or None
        """
        from subscriptions.models import ModuleBackend
        
        # First, check user's preference
        pref = cls.objects.filter(
            user=user,
            backend__module__code=module_code,
            backend__category=category,
            backend__is_active=True
        ).select_related('backend').first()
        
        if pref:
            return pref.backend
        
        # Fall back to default backend
        return ModuleBackend.get_for_module(module_code, category)
    
    @classmethod
    def set_user_backend(cls, user, backend):
        """
        Set user's preferred backend.
        Replaces any existing preference for the same module+category.
        """
        # Remove existing preference for same module+category
        cls.objects.filter(
            user=user,
            backend__module=backend.module,
            backend__category=backend.category
        ).delete()
        
        # Create new preference
        return cls.objects.create(user=user, backend=backend)
    
    @classmethod
    def get_user_preferences(cls, user):
        """
        Get all backend preferences for a user.
        Returns dict: {(module_code, category): backend, ...}
        """
        prefs = cls.objects.filter(user=user).select_related(
            'backend', 'backend__module'
        )
        return {
            (p.backend.module.code, p.backend.category): p.backend
            for p in prefs
        }

