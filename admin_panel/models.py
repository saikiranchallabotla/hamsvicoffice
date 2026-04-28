"""
Admin Panel models.

AdminPanelSecurity: singleton row holding the hashed admin-panel password
that gates access to /admin-panel/* even after a user has logged in via OTP.
Only superadmins can set or rotate it.
"""

from django.db import models
from django.contrib.auth.models import User
from django.contrib.auth.hashers import make_password, check_password
from django.utils import timezone


class AdminPanelSecurity(models.Model):
    """
    Singleton model holding the hashed admin-panel password.

    There is at most one row (pk=1). The password is stored as a Django
    password hash (PBKDF2 by default) and verified with `check_password`.
    """

    SINGLETON_ID = 1

    password_hash = models.CharField(max_length=255)
    updated_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='admin_panel_security_updates',
    )
    updated_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Admin Panel Security'
        verbose_name_plural = 'Admin Panel Security'

    def __str__(self):
        return f"AdminPanelSecurity (updated {self.updated_at:%Y-%m-%d %H:%M})"

    @classmethod
    def get(cls):
        """Return the singleton row, or None if password has never been set."""
        return cls.objects.filter(pk=cls.SINGLETON_ID).first()

    @classmethod
    def is_configured(cls):
        return cls.objects.filter(pk=cls.SINGLETON_ID).exists()

    @classmethod
    def set_password(cls, raw_password, updated_by=None):
        """Create/update the singleton row with a freshly hashed password."""
        obj, _ = cls.objects.get_or_create(
            pk=cls.SINGLETON_ID,
            defaults={'password_hash': make_password(raw_password)},
        )
        obj.password_hash = make_password(raw_password)
        obj.updated_by = updated_by
        obj.save(update_fields=['password_hash', 'updated_by', 'updated_at'])
        return obj

    def verify(self, raw_password):
        if not raw_password or not self.password_hash:
            return False
        return check_password(raw_password, self.password_hash)

    @classmethod
    def bootstrap_from_env_if_needed(cls):
        """
        On first use, seed the password from settings.ADMIN_PANEL_PASSWORD
        (or fall back to ADMIN_PASSWORD) so a fresh deploy is not locked out.
        Returns the singleton if seeded or already present, else None.
        """
        existing = cls.get()
        if existing:
            return existing

        from django.conf import settings
        seed = (
            getattr(settings, 'ADMIN_PANEL_PASSWORD', None)
            or getattr(settings, 'ADMIN_PASSWORD', None)
        )
        if not seed:
            import os
            seed = os.environ.get('ADMIN_PANEL_PASSWORD') or os.environ.get('ADMIN_PASSWORD')
        if not seed:
            return None
        return cls.set_password(seed, updated_by=None)
