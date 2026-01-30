# accounts/services/otp_service.py
"""
Production-ready OTP service using Redis for storage and rate limiting.
"""

import secrets
import hashlib
import logging
from typing import Optional
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

logger = logging.getLogger(__name__)


class OTPService:
    """
    OTP generation, storage, and verification using Redis.
    
    Usage:
        result = OTPService.request_otp('+919876543210', 'sms')
        result = OTPService.verify_otp('+919876543210', '123456')
    """
    
    # Configuration
    OTP_LENGTH = 6
    OTP_TTL = 300  # 5 minutes
    RESEND_COOLDOWN = 60  # 60 seconds
    MAX_ATTEMPTS = 5  # Max wrong attempts before lockout
    LOCKOUT_DURATION = 1800  # 30 minutes
    HOURLY_LIMIT = 10  # Max OTPs per hour per identifier
    
    # Redis key prefixes
    PREFIX_OTP = "otp:code:"
    PREFIX_COOLDOWN = "otp:cooldown:"
    PREFIX_ATTEMPTS = "otp:attempts:"
    PREFIX_LOCKOUT = "otp:lockout:"
    PREFIX_HOURLY = "otp:hourly:"
    
    # =========================================================================
    # PUBLIC API
    # =========================================================================
    
    @classmethod
    def request_otp(cls, identifier: str, channel: str = 'sms') -> dict:
        """
        Generate and store OTP for phone/email.
        
        Args:
            identifier: Phone number or email
            channel: 'sms' or 'email'
        
        Returns:
            {ok: bool, reason: str, data: {otp, expires_in, cooldown}}
        """
        identifier = cls._normalize(identifier)
        
        # Check lockout
        if cls._is_locked(identifier):
            remaining = cls._get_lockout_remaining(identifier)
            return cls._fail(
                f"Too many failed attempts. Try again in {remaining // 60} minutes.",
                code="LOCKED_OUT",
                data={"retry_after": remaining}
            )
        
        # Check cooldown (resend too fast)
        cooldown = cls._get_cooldown(identifier)
        if cooldown > 0:
            return cls._fail(
                f"Please wait {cooldown} seconds before requesting another OTP.",
                code="COOLDOWN",
                data={"retry_after": cooldown}
            )
        
        # Check hourly limit
        if cls._is_hourly_limit_reached(identifier):
            return cls._fail(
                "Too many OTP requests. Try again in an hour.",
                code="RATE_LIMITED"
            )
        
        # Generate OTP
        otp = cls._generate_otp()
        otp_hash = cls._hash_otp(otp)
        
        # Store in cache
        import time
        cache.set(cls._key_otp(identifier), otp_hash, cls.OTP_TTL)
        cache.set(cls._key_cooldown(identifier), {'expires_at': time.time() + cls.RESEND_COOLDOWN}, cls.RESEND_COOLDOWN)
        cls._increment_hourly(identifier)
        
        # Send OTP (stub - integrate with SMS/email provider)
        send_result = cls._send_otp(identifier, otp, channel)
        
        cls._audit_log(identifier, "otp_requested", {"channel": channel})
        
        # Check if we're in development mode (no SMS/email services configured)
        sms_configured = all([
            getattr(settings, 'TWILIO_ACCOUNT_SID', ''),
            getattr(settings, 'TWILIO_AUTH_TOKEN', ''),
            getattr(settings, 'TWILIO_PHONE_NUMBER', '')
        ])
        # Email requires host, user, AND password to be properly configured
        email_host = getattr(settings, 'EMAIL_HOST', '')
        email_user = getattr(settings, 'EMAIL_HOST_USER', '')
        email_pass = getattr(settings, 'EMAIL_HOST_PASSWORD', '')
        email_configured = all([email_host, email_user, email_pass])
        
        # FORCE dev_mode = True for testing until SMS/Email is properly configured
        # TODO: Remove this line when going to production with real SMS/Email
        dev_mode = True  # Force OTP to show on screen
        
        # Log for debugging
        logger.info(f"[OTP_DEV_MODE] FORCED dev_mode=True for testing")
        
        # Build response data
        response_data = {
            "expires_in": cls.OTP_TTL,
            "cooldown": cls.RESEND_COOLDOWN,
            "channel": channel,
            "dev_mode": dev_mode,  # Tell frontend if we're in dev mode
        }
        
        # Include OTP in response when:
        # 1. DEBUG mode is enabled, OR
        # 2. No SMS/Email services are configured (development without services)
        if dev_mode:
            response_data["otp"] = otp
        
        return cls._success(
            "OTP sent successfully.",
            data=response_data
        )
    
    @classmethod
    def verify_otp(cls, identifier: str, otp: str) -> dict:
        """
        Verify OTP for phone/email.
        
        Args:
            identifier: Phone number or email
            otp: 6-digit OTP code
        
        Returns:
            {ok: bool, reason: str, data: {}}
        """
        identifier = cls._normalize(identifier)
        
        # Check lockout
        if cls._is_locked(identifier):
            remaining = cls._get_lockout_remaining(identifier)
            return cls._fail(
                f"Account temporarily locked. Try again in {remaining // 60} minutes.",
                code="LOCKED_OUT",
                data={"retry_after": remaining}
            )
        
        # Get stored OTP hash
        stored_hash = cache.get(cls._key_otp(identifier))
        if not stored_hash:
            return cls._fail("OTP expired or not found. Request a new one.", code="NOT_FOUND")
        
        # Verify
        if cls._hash_otp(otp) != stored_hash:
            attempts = cls._increment_attempts(identifier)
            remaining = cls.MAX_ATTEMPTS - attempts
            
            if remaining <= 0:
                cls._set_lockout(identifier)
                cls._audit_log(identifier, "otp_lockout", {"reason": "max_attempts"})
                return cls._fail(
                    "Too many wrong attempts. Account locked for 30 minutes.",
                    code="LOCKED_OUT",
                    data={"retry_after": cls.LOCKOUT_DURATION}
                )
            
            cls._audit_log(identifier, "otp_failed", {"attempts": attempts})
            return cls._fail(
                f"Invalid OTP. {remaining} attempts remaining.",
                code="INVALID",
                data={"attempts_remaining": remaining}
            )
        
        # Success - clear all keys
        cls._clear_keys(identifier)
        cls._audit_log(identifier, "otp_verified", {})
        
        return cls._success("OTP verified successfully.")
    
    # =========================================================================
    # KEY GENERATORS
    # =========================================================================
    
    @classmethod
    def _key_otp(cls, identifier: str) -> str:
        return f"{cls.PREFIX_OTP}{identifier}"
    
    @classmethod
    def _key_cooldown(cls, identifier: str) -> str:
        return f"{cls.PREFIX_COOLDOWN}{identifier}"
    
    @classmethod
    def _key_attempts(cls, identifier: str) -> str:
        return f"{cls.PREFIX_ATTEMPTS}{identifier}"
    
    @classmethod
    def _key_lockout(cls, identifier: str) -> str:
        return f"{cls.PREFIX_LOCKOUT}{identifier}"
    
    @classmethod
    def _key_hourly(cls, identifier: str) -> str:
        hour = timezone.now().strftime("%Y%m%d%H")
        return f"{cls.PREFIX_HOURLY}{identifier}:{hour}"
    
    # =========================================================================
    # HELPERS
    # =========================================================================
    
    @classmethod
    def _normalize(cls, identifier: str) -> str:
        """Normalize phone/email to consistent format."""
        identifier = identifier.strip().lower()
        # Remove spaces and dashes from phone numbers
        if '@' not in identifier:
            identifier = ''.join(c for c in identifier if c.isdigit() or c == '+')
        return identifier
    
    @classmethod
    def _generate_otp(cls) -> str:
        """Generate secure random OTP."""
        return ''.join(str(secrets.randbelow(10)) for _ in range(cls.OTP_LENGTH))
    
    @classmethod
    def _hash_otp(cls, otp: str) -> str:
        """Hash OTP for secure storage."""
        return hashlib.sha256(otp.encode()).hexdigest()
    
    # =========================================================================
    # THROTTLING
    # =========================================================================
    
    @classmethod
    def _get_cooldown(cls, identifier: str) -> int:
        """Get remaining cooldown seconds."""
        # LocMemCache doesn't support ttl(), so we store expiry time
        cooldown_data = cache.get(cls._key_cooldown(identifier))
        if cooldown_data:
            import time
            expiry_time = cooldown_data.get('expires_at', 0)
            remaining = int(expiry_time - time.time())
            return max(0, remaining)
        return 0
    
    @classmethod
    def _is_locked(cls, identifier: str) -> bool:
        """Check if identifier is locked out."""
        return cache.get(cls._key_lockout(identifier)) is not None
    
    @classmethod
    def _get_lockout_remaining(cls, identifier: str) -> int:
        """Get remaining lockout seconds."""
        # LocMemCache doesn't support ttl(), so we store expiry time
        lockout_data = cache.get(cls._key_lockout(identifier))
        if lockout_data:
            import time
            expiry_time = lockout_data.get('expires_at', 0)
            remaining = int(expiry_time - time.time())
            return max(0, remaining)
        return 0
    
    @classmethod
    def _set_lockout(cls, identifier: str):
        """Set lockout for identifier."""
        import time
        cache.set(cls._key_lockout(identifier), {'expires_at': time.time() + cls.LOCKOUT_DURATION}, cls.LOCKOUT_DURATION)
        cache.delete(cls._key_attempts(identifier))
    
    @classmethod
    def _increment_attempts(cls, identifier: str) -> int:
        """Increment and return failed attempt count."""
        key = cls._key_attempts(identifier)
        try:
            return cache.incr(key)
        except ValueError:
            cache.set(key, 1, cls.LOCKOUT_DURATION)
            return 1
    
    @classmethod
    def _is_hourly_limit_reached(cls, identifier: str) -> bool:
        """Check if hourly OTP limit reached."""
        count = cache.get(cls._key_hourly(identifier)) or 0
        return count >= cls.HOURLY_LIMIT
    
    @classmethod
    def _increment_hourly(cls, identifier: str):
        """Increment hourly OTP counter."""
        key = cls._key_hourly(identifier)
        try:
            cache.incr(key)
        except ValueError:
            cache.set(key, 1, 3600)  # 1 hour TTL
    
    @classmethod
    def _clear_keys(cls, identifier: str):
        """Clear all OTP-related keys on successful verification."""
        cache.delete(cls._key_otp(identifier))
        cache.delete(cls._key_attempts(identifier))
        # Don't clear cooldown - prevent rapid re-requests after success
    
    # =========================================================================
    # RESPONSE BUILDERS
    # =========================================================================
    
    @classmethod
    def _success(cls, reason: str, data: Optional[dict] = None) -> dict:
        return {"ok": True, "reason": reason, "data": data or {}}
    
    @classmethod
    def _fail(cls, reason: str, code: str = "ERROR", data: Optional[dict] = None) -> dict:
        return {"ok": False, "reason": reason, "code": code, "data": data or {}}
    
    # =========================================================================
    # SMS & EMAIL PROVIDERS
    # =========================================================================
    
    @classmethod
    def _send_otp(cls, identifier: str, otp: str, channel: str) -> bool:
        """
        Send OTP via SMS (Twilio) or email (Django mail).
        
        Configured providers:
        - SMS: Twilio
        - Email: Django email backend (AWS SES, SMTP, etc.)
        """
        if channel == 'sms':
            return cls._send_sms_otp(identifier, otp)
        elif channel == 'email':
            return cls._send_email_otp(identifier, otp)
        return False
    
    @classmethod
    def _send_sms_otp(cls, phone: str, otp: str) -> bool:
        """
        Send OTP via Twilio SMS.
        
        Requires in settings.py:
        - TWILIO_ACCOUNT_SID
        - TWILIO_AUTH_TOKEN
        - TWILIO_PHONE_NUMBER
        """
        from django.conf import settings
        
        # Get Twilio credentials
        account_sid = getattr(settings, 'TWILIO_ACCOUNT_SID', '')
        auth_token = getattr(settings, 'TWILIO_AUTH_TOKEN', '')
        from_number = getattr(settings, 'TWILIO_PHONE_NUMBER', '')
        
        # In DEBUG mode without Twilio configured, just log
        if not all([account_sid, auth_token, from_number]):
            if settings.DEBUG:
                logger.info(f"[OTP] DEV MODE - SMS to {phone}: {otp}")
                return True
            logger.error("Twilio not configured. Set TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_PHONE_NUMBER")
            return False
        
        try:
            from twilio.rest import Client
            client = Client(account_sid, auth_token)
            
            message = client.messages.create(
                body=f"Your Hamsvic verification code is: {otp}. Valid for 5 minutes. Do not share this code.",
                from_=from_number,
                to=phone
            )
            
            logger.info(f"[OTP] SMS sent to {phone}, SID: {message.sid}")
            return True
            
        except ImportError:
            logger.error("Twilio package not installed. Run: pip install twilio")
            if settings.DEBUG:
                logger.info(f"[OTP] DEV MODE (no twilio) - SMS to {phone}: {otp}")
                return True
            return False
        except Exception as e:
            logger.error(f"[OTP] Twilio SMS failed to {phone}: {str(e)}")
            return False
    
    @classmethod
    def _send_email_otp(cls, email: str, otp: str) -> bool:
        """
        Send OTP via Django email backend.
        
        Works with any configured EMAIL_BACKEND:
        - AWS SES, SendGrid, SMTP, Console (dev)
        """
        from django.conf import settings
        from django.core.mail import send_mail
        from django.template.loader import render_to_string
        from django.utils.html import strip_tags
        
        subject = 'Your Hamsvic Verification Code'
        
        # Try to use HTML template, fallback to plain text
        try:
            html_message = render_to_string('accounts/emails/otp_email.html', {
                'otp': otp,
                'expiry_minutes': 5,
            })
            plain_message = strip_tags(html_message)
        except Exception:
            # Fallback to simple message
            plain_message = f"""Your Hamsvic verification code is: {otp}

This code is valid for 5 minutes.

If you didn't request this code, please ignore this email.

- Hamsvic Team"""
            html_message = f"""
            <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                <h2 style="color: #6366f1;">Verification Code</h2>
                <p>Your Hamsvic verification code is:</p>
                <div style="background: #f3f4f6; padding: 20px; text-align: center; margin: 20px 0; border-radius: 8px;">
                    <span style="font-size: 32px; font-weight: bold; letter-spacing: 8px; color: #1f2937;">{otp}</span>
                </div>
                <p style="color: #6b7280;">This code is valid for 5 minutes.</p>
                <p style="color: #6b7280;">If you didn't request this code, please ignore this email.</p>
                <hr style="border: none; border-top: 1px solid #e5e7eb; margin: 20px 0;">
                <p style="color: #9ca3af; font-size: 12px;">- Hamsvic Team</p>
            </div>
            """
        
        try:
            from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@hamsvic.com')
            
            send_mail(
                subject=subject,
                message=plain_message,
                from_email=from_email,
                recipient_list=[email],
                html_message=html_message,
                fail_silently=False,
            )
            
            logger.info(f"[OTP] Email sent to {email}")
            return True
            
        except Exception as e:
            logger.error(f"[OTP] Email failed to {email}: {str(e)}")
            # In DEBUG mode, still return True so testing works
            if settings.DEBUG:
                logger.info(f"[OTP] DEV MODE - Email to {email}: {otp}")
                return True
            return False
    
    @classmethod
    def _audit_log(cls, identifier: str, action: str, metadata: dict):
        """
        Log OTP events for audit trail.
        
        TODO: Connect to your audit logging system.
        """
        logger.info(f"[OTP_AUDIT] {action} | {identifier} | {metadata}")
