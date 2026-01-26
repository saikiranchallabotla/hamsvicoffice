# accounts/managers.py
"""
Custom model managers for accounts app.
"""

from django.db import models
from django.utils import timezone


class ActiveSessionManager(models.Manager):
    """Manager for active user sessions"""
    
    def get_queryset(self):
        return super().get_queryset().filter(is_active=True)
    
    def for_user(self, user):
        """Get all active sessions for a user"""
        return self.get_queryset().filter(user=user)
    
    def cleanup_expired(self):
        """Remove expired sessions"""
        return self.get_queryset().filter(
            expires_at__lt=timezone.now()
        ).update(is_active=False)


class ValidOTPManager(models.Manager):
    """Manager for valid (non-expired, non-verified) OTPs"""
    
    def get_queryset(self):
        return super().get_queryset().filter(
            is_verified=False,
            expires_at__gt=timezone.now()
        )
    
    def for_phone(self, phone, otp_type='login'):
        """Get valid OTP for phone"""
        return self.get_queryset().filter(
            phone=phone,
            otp_type=otp_type
        ).order_by('-created_at').first()
    
    def for_email(self, email, otp_type='login'):
        """Get valid OTP for email"""
        return self.get_queryset().filter(
            email=email,
            otp_type=otp_type
        ).order_by('-created_at').first()
