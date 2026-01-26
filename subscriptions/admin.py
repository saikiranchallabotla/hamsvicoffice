# subscriptions/admin.py
"""
Admin configuration for subscriptions app.
"""

from django.contrib import admin
from django.utils.html import format_html
from subscriptions.models import (
    Module, ModuleBackend, ModulePricing, UserModuleSubscription,
    Payment, Invoice, Coupon, UsageLog
)


# ==============================================================================
# MODULE ADMIN
# ==============================================================================

class ModulePricingInline(admin.TabularInline):
    model = ModulePricing
    extra = 1
    fields = ('duration_months', 'base_price', 'sale_price', 'gst_percent', 
              'usage_limit', 'is_active', 'is_popular')


class ModuleBackendInline(admin.TabularInline):
    model = ModuleBackend
    extra = 0
    fields = ('name', 'category', 'file', 'is_default', 'is_active', 'display_order')
    readonly_fields = ()
    ordering = ('category', 'display_order', 'name')


@admin.register(Module)
class ModuleAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'is_active', 'is_free', 'trial_days', 
                    'free_tier_limit', 'backend_count', 'display_order')
    list_filter = ('is_active', 'is_free', 'is_addon')
    search_fields = ('name', 'code', 'description')
    list_editable = ('display_order', 'is_active')
    prepopulated_fields = {'code': ('name',)}
    inlines = [ModuleBackendInline, ModulePricingInline]
    
    fieldsets = (
        ('Basic Info', {
            'fields': ('code', 'name', 'description')
        }),
        ('Display', {
            'fields': ('icon', 'color', 'display_order', 'features')
        }),
        ('Settings', {
            'fields': ('is_active', 'is_free', 'is_addon', 'trial_days', 'free_tier_limit')
        }),
        ('Dependencies', {
            'fields': ('requires_modules',),
            'classes': ('collapse',)
        }),
    )
    
    def backend_count(self, obj):
        count = obj.backends.filter(is_active=True).count()
        if count > 0:
            return format_html('<span style="color: green;">{}</span>', count)
        return format_html('<span style="color: gray;">0</span>')
    backend_count.short_description = 'Backends'


# ==============================================================================
# MODULE BACKEND ADMIN (Standalone)
# ==============================================================================

@admin.register(ModuleBackend)
class ModuleBackendAdmin(admin.ModelAdmin):
    list_display = ('name', 'module', 'category', 'code', 'is_default', 'is_active', 
                    'display_order', 'file_link', 'updated_at')
    list_filter = ('module', 'category', 'is_active', 'is_default')
    search_fields = ('name', 'code', 'description', 'module__name')
    list_editable = ('is_default', 'is_active', 'display_order')
    ordering = ('module', 'category', 'display_order', 'name')
    
    fieldsets = (
        ('Module & Category', {
            'fields': ('module', 'category')
        }),
        ('Backend Details', {
            'fields': ('name', 'code', 'description')
        }),
        ('File', {
            'fields': ('file',),
            'description': 'Upload Excel file with "Master Datas" and "Groups" sheets'
        }),
        ('Display & Status', {
            'fields': ('display_order', 'is_active', 'is_default')
        }),
    )
    
    def file_link(self, obj):
        if obj.file:
            return format_html('<a href="{}" target="_blank">📄 View</a>', obj.file.url)
        return '-'
    file_link.short_description = 'File'


@admin.register(ModulePricing)
class ModulePricingAdmin(admin.ModelAdmin):
    list_display = ('module', 'duration_months', 'base_price', 'sale_price', 
                    'discount_display', 'is_active', 'is_popular')
    list_filter = ('module', 'is_active', 'is_popular', 'duration_months')
    list_editable = ('is_active', 'is_popular')
    
    def discount_display(self, obj):
        if obj.discount_percent > 0:
            return format_html(
                '<span style="color: green; font-weight: bold;">{:.0f}% OFF</span>',
                obj.discount_percent
            )
        return '-'
    discount_display.short_description = 'Discount'


# ==============================================================================
# SUBSCRIPTION ADMIN
# ==============================================================================

@admin.register(UserModuleSubscription)
class UserModuleSubscriptionAdmin(admin.ModelAdmin):
    list_display = ('user', 'module', 'status', 'started_at', 'expires_at', 
                    'days_remaining_display', 'usage_display', 'auto_renew')
    list_filter = ('status', 'module', 'auto_renew')
    search_fields = ('user__username', 'user__email', 'module__name')
    date_hierarchy = 'started_at'
    readonly_fields = ('id', 'created_at', 'updated_at')
    raw_id_fields = ('user', 'payment')
    
    fieldsets = (
        ('Subscription', {
            'fields': ('id', 'user', 'module', 'pricing', 'status')
        }),
        ('Dates', {
            'fields': ('started_at', 'expires_at', 'cancelled_at')
        }),
        ('Usage', {
            'fields': ('usage_count', 'usage_limit', 'usage_reset_at')
        }),
        ('Payment & Renewal', {
            'fields': ('payment', 'auto_renew', 'renewal_reminder_sent')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def days_remaining_display(self, obj):
        days = obj.days_remaining()
        if days <= 0:
            return format_html('<span style="color: red;">Expired</span>')
        elif days <= 7:
            return format_html('<span style="color: orange;">{} days</span>', days)
        return f"{days} days"
    days_remaining_display.short_description = 'Remaining'
    
    def usage_display(self, obj):
        if obj.usage_limit > 0:
            return f"{obj.usage_count}/{obj.usage_limit}"
        return f"{obj.usage_count}/∞"
    usage_display.short_description = 'Usage'
    
    actions = ['expire_subscriptions', 'reset_usage']
    
    @admin.action(description='Mark selected as expired')
    def expire_subscriptions(self, request, queryset):
        count = queryset.update(status='expired')
        self.message_user(request, f"Expired {count} subscriptions.")
    
    @admin.action(description='Reset usage counters')
    def reset_usage(self, request, queryset):
        from django.utils import timezone
        count = queryset.update(usage_count=0, usage_reset_at=timezone.now())
        self.message_user(request, f"Reset usage for {count} subscriptions.")


# ==============================================================================
# PAYMENT ADMIN
# ==============================================================================

@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ('order_id', 'user', 'total_display', 'gateway', 'status', 
                    'created_at', 'completed_at')
    list_filter = ('status', 'gateway', 'created_at')
    search_fields = ('order_id', 'user__username', 'user__email', 
                     'gateway_order_id', 'gateway_payment_id')
    date_hierarchy = 'created_at'
    readonly_fields = ('id', 'order_id', 'created_at', 'updated_at', 'completed_at')
    raw_id_fields = ('user', 'coupon')
    filter_horizontal = ('modules',)
    
    fieldsets = (
        ('Order', {
            'fields': ('id', 'order_id', 'user', 'modules')
        }),
        ('Amounts', {
            'fields': ('subtotal', 'discount_amount', 'gst_amount', 'total_amount', 'coupon')
        }),
        ('Payment Gateway', {
            'fields': ('gateway', 'gateway_order_id', 'gateway_payment_id', 
                       'gateway_signature', 'gateway_response')
        }),
        ('Status', {
            'fields': ('status', 'created_at', 'completed_at')
        }),
        ('Refund', {
            'fields': ('refund_amount', 'refund_reason', 'refunded_at'),
            'classes': ('collapse',)
        }),
        ('Billing Info', {
            'fields': ('billing_name', 'billing_email', 'billing_phone', 
                       'billing_address', 'billing_gstin'),
            'classes': ('collapse',)
        }),
    )
    
    def total_display(self, obj):
        return f"₹{obj.total_amount:,.2f}"
    total_display.short_description = 'Total'
    total_display.admin_order_field = 'total_amount'


# ==============================================================================
# INVOICE ADMIN
# ==============================================================================

@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ('invoice_number', 'user', 'total_display', 'invoice_date', 
                    'is_paid', 'pdf_link')
    list_filter = ('is_paid', 'invoice_date')
    search_fields = ('invoice_number', 'user__username', 'billing_name', 'billing_gstin')
    date_hierarchy = 'invoice_date'
    readonly_fields = ('id', 'invoice_number', 'created_at')
    raw_id_fields = ('user', 'payment')
    
    def total_display(self, obj):
        return f"₹{obj.total_amount:,.2f}"
    total_display.short_description = 'Total'
    
    def pdf_link(self, obj):
        if obj.pdf_file:
            return format_html('<a href="{}" target="_blank">Download PDF</a>', obj.pdf_file.url)
        return '-'
    pdf_link.short_description = 'PDF'


# ==============================================================================
# COUPON ADMIN
# ==============================================================================

@admin.register(Coupon)
class CouponAdmin(admin.ModelAdmin):
    list_display = ('code', 'discount_display', 'usage_display', 'valid_from', 
                    'valid_until', 'is_active')
    list_filter = ('is_active', 'discount_type', 'first_purchase_only')
    search_fields = ('code', 'description')
    list_editable = ('is_active',)
    filter_horizontal = ('applicable_modules', 'specific_users')
    readonly_fields = ('current_uses', 'created_at', 'updated_at')
    
    fieldsets = (
        ('Coupon Code', {
            'fields': ('code', 'description')
        }),
        ('Discount', {
            'fields': ('discount_type', 'discount_value', 'max_discount')
        }),
        ('Applicability', {
            'fields': ('applicable_modules', 'min_purchase')
        }),
        ('Usage Limits', {
            'fields': ('max_uses', 'max_uses_per_user', 'current_uses')
        }),
        ('Validity', {
            'fields': ('valid_from', 'valid_until', 'is_active')
        }),
        ('Restrictions', {
            'fields': ('first_purchase_only', 'specific_users'),
            'classes': ('collapse',)
        }),
    )
    
    def discount_display(self, obj):
        if obj.discount_type == 'percent':
            return f"{obj.discount_value}%"
        return f"₹{obj.discount_value}"
    discount_display.short_description = 'Discount'
    
    def usage_display(self, obj):
        if obj.max_uses > 0:
            return f"{obj.current_uses}/{obj.max_uses}"
        return f"{obj.current_uses}/∞"
    usage_display.short_description = 'Usage'


# ==============================================================================
# USAGE LOG ADMIN
# ==============================================================================

@admin.register(UsageLog)
class UsageLogAdmin(admin.ModelAdmin):
    list_display = ('user', 'module', 'action', 'resource_id', 'created_at')
    list_filter = ('module', 'action', 'created_at')
    search_fields = ('user__username', 'action', 'resource_id')
    date_hierarchy = 'created_at'
    readonly_fields = ('created_at',)
    raw_id_fields = ('user', 'subscription')
    
    def has_add_permission(self, request):
        return False  # Logs should only be created programmatically
    
    def has_change_permission(self, request, obj=None):
        return False  # Logs should be immutable
