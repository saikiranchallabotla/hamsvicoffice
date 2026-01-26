# accounts/admin.py
"""
Admin configuration for accounts app.
"""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User

from accounts.models import OTPToken, OTPRateLimit, UserProfile, UserSession


# ==============================================================================
# INLINE ADMINS
# ==============================================================================

class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False
    verbose_name_plural = 'Profile'
    fk_name = 'user'
    
    fieldsets = (
        ('Contact', {
            'fields': ('phone', 'phone_verified', 'email_verified')
        }),
        ('Organization', {
            'fields': ('company_name', 'department', 'designation')
        }),
        ('Address', {
            'fields': ('address_line1', 'address_line2', 'city', 'state', 'pincode', 'country'),
            'classes': ('collapse',)
        }),
        ('Billing', {
            'fields': ('gstin',),
            'classes': ('collapse',)
        }),
        ('Role & Status', {
            'fields': ('role', 'profile_completed', 'is_active', 'subscription_tier')
        }),
        ('Preferences', {
            'fields': ('notification_prefs',),
            'classes': ('collapse',)
        }),
    )


# ==============================================================================
# EXTEND USER ADMIN
# ==============================================================================

class CustomUserAdmin(BaseUserAdmin):
    inlines = (UserProfileInline,)
    list_display = ('username', 'email', 'first_name', 'last_name', 'get_role', 'is_staff', 'is_active')
    list_filter = BaseUserAdmin.list_filter + ('account_profile__role',)
    
    def get_role(self, obj):
        if hasattr(obj, 'account_profile'):
            return obj.account_profile.role
        return '-'
    get_role.short_description = 'Role'
    get_role.admin_order_field = 'account_profile__role'


# Re-register User with custom admin
admin.site.unregister(User)
admin.site.register(User, CustomUserAdmin)


# ==============================================================================
# OTP TOKEN ADMIN
# ==============================================================================

@admin.register(OTPToken)
class OTPTokenAdmin(admin.ModelAdmin):
    list_display = ('get_identifier', 'otp_type', 'is_verified', 'attempts', 'expires_at', 'created_at')
    list_filter = ('otp_type', 'is_verified')
    search_fields = ('phone', 'email', 'user__username')
    readonly_fields = ('otp_hash', 'created_at', 'verified_at')
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Identifier', {
            'fields': ('user', 'phone', 'email')
        }),
        ('OTP Details', {
            'fields': ('otp_type', 'otp_code', 'otp_hash', 'expires_at')
        }),
        ('Status', {
            'fields': ('is_verified', 'attempts', 'max_attempts')
        }),
        ('Metadata', {
            'fields': ('ip_address', 'user_agent', 'created_at', 'verified_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_identifier(self, obj):
        return obj.phone or obj.email
    get_identifier.short_description = 'Phone/Email'


# ==============================================================================
# OTP RATE LIMIT ADMIN
# ==============================================================================

@admin.register(OTPRateLimit)
class OTPRateLimitAdmin(admin.ModelAdmin):
    list_display = ('identifier', 'identifier_type', 'request_count', 'failed_attempts', 
                    'is_locked_display', 'last_request_at')
    list_filter = ('identifier_type',)
    search_fields = ('identifier',)
    readonly_fields = ('window_start', 'last_request_at')
    
    def is_locked_display(self, obj):
        return obj.is_locked()
    is_locked_display.boolean = True
    is_locked_display.short_description = 'Locked'
    
    actions = ['unlock_selected']
    
    @admin.action(description='Unlock selected rate limits')
    def unlock_selected(self, request, queryset):
        queryset.update(locked_until=None, failed_attempts=0)
        self.message_user(request, f"Unlocked {queryset.count()} rate limits.")


# ==============================================================================
# USER PROFILE ADMIN (standalone)
# ==============================================================================

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'phone', 'company_name', 'role', 'profile_completed', 
                    'phone_verified', 'email_verified')
    list_filter = ('role', 'profile_completed', 'phone_verified', 'email_verified', 'subscription_tier')
    search_fields = ('user__username', 'user__email', 'phone', 'company_name')
    readonly_fields = ('created_at', 'updated_at', 'last_login_at')
    
    fieldsets = (
        ('User', {
            'fields': ('user',)
        }),
        ('Contact', {
            'fields': ('phone', 'phone_verified', 'email_verified')
        }),
        ('Organization', {
            'fields': ('company_name', 'department', 'designation')
        }),
        ('Address', {
            'fields': ('address_line1', 'address_line2', 'city', 'state', 'pincode', 'country'),
            'classes': ('collapse',)
        }),
        ('Billing', {
            'fields': ('gstin',),
            'classes': ('collapse',)
        }),
        ('Role & Status', {
            'fields': ('role', 'profile_completed', 'is_active', 'subscription_tier')
        }),
        ('Privacy', {
            'fields': ('data_export_requested_at', 'deletion_requested_at'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at', 'last_login_at'),
            'classes': ('collapse',)
        }),
    )


# ==============================================================================
# USER SESSION ADMIN
# ==============================================================================

@admin.register(UserSession)
class UserSessionAdmin(admin.ModelAdmin):
    list_display = ('user', 'device_name', 'ip_address', 'is_active', 'is_current', 
                    'last_activity', 'created_at')
    list_filter = ('is_active', 'is_current', 'device_type')
    search_fields = ('user__username', 'ip_address', 'device_name')
    readonly_fields = ('session_key', 'created_at', 'last_activity')
    date_hierarchy = 'created_at'
    
    actions = ['logout_selected', 'cleanup_expired']
    
    @admin.action(description='Logout selected sessions')
    def logout_selected(self, request, queryset):
        count = queryset.update(is_active=False)
        self.message_user(request, f"Logged out {count} sessions.")
    
    @admin.action(description='Cleanup expired sessions')
    def cleanup_expired(self, request, queryset):
        count = UserSession.cleanup_expired()
        self.message_user(request, f"Cleaned up {count} expired sessions.")
