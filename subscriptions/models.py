# subscriptions/models.py
"""
Module-wise subscriptions, pricing, payments, and invoicing.

Models:
- Module: Available modules (Estimate, Workslip, Bill, etc.)
- ModulePricing: Pricing tiers for each module
- UserModuleSubscription: User's active module subscriptions
- Payment: Payment transactions
- Invoice: Generated invoices
- Coupon: Discount coupons
- UsageLog: Track module usage for analytics
"""

import uuid
from decimal import Decimal
from datetime import timedelta
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator


# ==============================================================================
# MODULE DEFINITIONS
# ==============================================================================

class Module(models.Model):
    """
    Available modules/features that users can subscribe to.
    Examples: Estimate, Workslip, Bill, Self-Formatted, Temp Works
    """
    # Identifiers
    code = models.CharField(
        max_length=50, 
        unique=True, 
        db_index=True,
        help_text="Unique code like 'estimate', 'workslip', 'bill'"
    )
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    
    # URL for this module
    url_name = models.CharField(
        max_length=100,
        blank=True,
        help_text="Django URL name for this module (e.g., 'datas', 'tempworks_home')"
    )
    
    # Display
    icon = models.CharField(max_length=50, blank=True, help_text="Icon class or emoji")
    color = models.CharField(max_length=20, default='#3B82F6', help_text="Hex color code")
    display_order = models.PositiveIntegerField(default=0)
    
    # Features included in this module
    features = models.JSONField(
        default=list,
        blank=True,
        help_text="List of feature strings for display"
    )
    # Example: ["Generate estimates", "PDF export", "Share via link"]
    
    # Dependencies
    requires_modules = models.ManyToManyField(
        'self',
        symmetrical=False,
        blank=True,
        related_name='required_by',
        help_text="Other modules required to use this module"
    )
    
    # Status
    is_active = models.BooleanField(default=True)
    is_free = models.BooleanField(default=False, help_text="Free for all users")
    is_addon = models.BooleanField(default=False, help_text="Add-on module (not standalone)")
    
    # Trial
    trial_days = models.PositiveIntegerField(
        default=1,
        help_text="Free trial period in days (1 day per user)"
    )
    
    # Limits for free tier
    free_tier_limit = models.PositiveIntegerField(
        default=5,
        help_text="Number of free uses per month (0 = unlimited)"
    )
    
    # Backend Excel sheet for modules that use custom data (like AMC)
    backend_sheet_name = models.CharField(
        max_length=100,
        blank=True,
        help_text="Custom name for backend sheet (e.g., 'amc_electrical', 'amc_civil')"
    )
    backend_sheet_file = models.FileField(
        upload_to='module_backends/',
        blank=True,
        null=True,
        help_text="Custom backend Excel file for this module"
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['display_order', 'name']
    
    def __str__(self):
        return self.name
    
    def get_active_pricing(self):
        """Get all active pricing options for this module"""
        return self.pricing_options.filter(is_active=True).order_by('duration_months')
    
    def get_backends(self, category=None):
        """Get all active backends for this module, optionally filtered by category"""
        qs = self.backends.filter(is_active=True)
        if category:
            qs = qs.filter(category=category)
        return qs.order_by('display_order', 'name')


class ModuleBackend(models.Model):
    """
    Backend data files (SOR rates) for each module.
    Allows multiple backends per module - one for each state/region.
    
    Examples:
    - Estimate module: Telangana Electrical, Telangana Civil, AP Electrical, AP Civil
    - Workslip module: Telangana Electrical, Telangana Civil
    - AMC module: AMC Electrical, AMC Civil
    """
    CATEGORY_CHOICES = (
        ('electrical', 'Electrical'),
        ('civil', 'Civil'),
    )
    
    # Link to module
    module = models.ForeignKey(
        Module,
        on_delete=models.CASCADE,
        related_name='backends'
    )
    
    # Category (electrical or civil)
    category = models.CharField(
        max_length=20,
        choices=CATEGORY_CHOICES,
        db_index=True
    )
    
    # Name - you can name it anything (Telangana SOR, AP SOR 2024, etc.)
    name = models.CharField(
        max_length=255,
        help_text="Name for this backend (e.g., 'Telangana SOR 2024-25', 'AP Electrical Rates')"
    )
    
    # Short code for internal reference
    code = models.CharField(
        max_length=50,
        blank=True,
        help_text="Short code (e.g., 'TS_2024', 'AP_2024')"
    )
    
    # Description
    description = models.TextField(
        blank=True,
        help_text="Optional description or notes"
    )
    
    # The actual Excel file
    file = models.FileField(
        upload_to='module_backends/',
        help_text="Excel file with 'Master Datas' and 'Groups' sheets"
    )

    # Binary backup of file content in database (survives ephemeral filesystem redeployments)
    file_data = models.BinaryField(
        null=True,
        blank=True,
        editable=False,
        help_text="Binary copy of the backend file stored in DB for persistence"
    )
    file_name = models.CharField(
        max_length=255,
        blank=True,
        default='',
        help_text="Original filename for restoration"
    )
    
    # Display order (lower = appears first)
    display_order = models.PositiveIntegerField(
        default=0,
        help_text="Order in dropdown (lower appears first)"
    )
    
    # Status
    is_active = models.BooleanField(default=True)
    is_default = models.BooleanField(
        default=False,
        help_text="Use as default when user hasn't selected a specific backend"
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['module', 'category', 'display_order', 'name']
        verbose_name = 'Module Backend'
        verbose_name_plural = 'Module Backends'
        indexes = [
            models.Index(fields=['module', 'category', 'is_active']),
            models.Index(fields=['module', 'is_default']),
        ]
    
    def __str__(self):
        return f"{self.module.name} - {self.name} ({self.get_category_display()})"
    
    def save(self, *args, **kwargs):
        # Ensure only one default per module + category
        if self.is_default:
            ModuleBackend.objects.filter(
                module=self.module,
                category=self.category,
                is_default=True
            ).exclude(pk=self.pk).update(is_default=False)
        super().save(*args, **kwargs)
    
    def get_file_bytes(self):
        """
        Get the backend file content, preferring DB storage over disk.
        Restores disk file from DB if missing (for local/ephemeral storage).
        """
        import os
        # 1. If DB has file_data, use it (authoritative)
        if self.file_data:
            # Also restore disk file if missing
            if self.file:
                try:
                    file_path = self.file.path
                    if not os.path.exists(file_path):
                        os.makedirs(os.path.dirname(file_path), exist_ok=True)
                        with open(file_path, 'wb') as f:
                            f.write(bytes(self.file_data))
                except Exception:
                    pass
            return bytes(self.file_data)

        # 2. Fallback: read from disk file and backfill DB
        if self.file:
            try:
                file_path = self.file.path
                if os.path.exists(file_path):
                    with open(file_path, 'rb') as f:
                        data = f.read()
                    # Backfill DB storage
                    ModuleBackend.objects.filter(pk=self.pk).update(
                        file_data=data,
                        file_name=os.path.basename(file_path)
                    )
                    return data
            except Exception:
                pass

        return None

    @classmethod
    def get_for_module(cls, module_code, category, backend_id=None):
        """
        Get a specific backend or the default for a module and category.
        
        Args:
            module_code: Module code like 'estimate', 'workslip'
            category: 'electrical' or 'civil'
            backend_id: Specific backend ID (optional)
        
        Returns:
            ModuleBackend instance or None
        """
        base_qs = cls.objects.filter(
            module__code=module_code,
            category=category,
            is_active=True
        )
        
        if backend_id:
            return base_qs.filter(pk=backend_id).first()
        
        # Return default or first available
        return base_qs.filter(is_default=True).first() or base_qs.first()
    
    @classmethod
    def get_choices_for_module(cls, module_code, category):
        """
        Get list of backends for dropdown selection.
        
        Returns:
            List of tuples: [(id, name), ...]
        """
        backends = cls.objects.filter(
            module__code=module_code,
            category=category,
            is_active=True
        ).order_by('display_order', 'name')
        
        return [(b.pk, b.name) for b in backends]


class ModulePricing(models.Model):
    """
    Pricing tiers for each module.
    Supports monthly, quarterly, yearly pricing with discounts.
    """
    DURATION_CHOICES = (
        (1, '1 Month'),
        (3, '3 Months'),
        (6, '6 Months'),
        (12, '1 Year'),
        (24, '2 Years'),
    )
    
    module = models.ForeignKey(
        Module,
        on_delete=models.CASCADE,
        related_name='pricing_options'
    )
    
    # Duration
    duration_months = models.PositiveIntegerField(
        choices=DURATION_CHOICES,
        default=1
    )
    
    # Pricing (in INR)
    base_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))],
        help_text="Original price before discount"
    )
    sale_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))],
        help_text="Actual selling price"
    )
    
    # Tax
    gst_percent = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('18.00'),
        help_text="GST percentage"
    )
    
    # Limits for this tier
    usage_limit = models.PositiveIntegerField(
        default=0,
        help_text="Max uses per month (0 = unlimited)"
    )
    
    # Status
    is_active = models.BooleanField(default=True)
    is_popular = models.BooleanField(default=False, help_text="Show 'Popular' badge")
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['module', 'duration_months']
        ordering = ['module', 'duration_months']
    
    def __str__(self):
        return f"{self.module.name} - {self.get_duration_months_display()}"
    
    @property
    def discount_percent(self):
        """Calculate discount percentage"""
        if self.base_price > 0:
            discount = ((self.base_price - self.sale_price) / self.base_price) * 100
            return round(discount, 0)
        return 0
    
    @property
    def discount_amount(self):
        """Calculate discount amount"""
        return self.base_price - self.sale_price
    
    @property
    def monthly_price(self):
        """Calculate effective monthly price"""
        if self.duration_months > 0:
            return self.sale_price / self.duration_months
        return self.sale_price
    
    @property
    def gst_amount(self):
        """Calculate GST amount"""
        return (self.sale_price * self.gst_percent) / 100
    
    @property
    def total_price(self):
        """Total price including GST"""
        return self.sale_price + self.gst_amount


# ==============================================================================
# USER SUBSCRIPTIONS
# ==============================================================================

class UserModuleSubscription(models.Model):
    """
    Track user's active subscriptions to modules.
    Each user can have multiple module subscriptions.
    """
    STATUS_CHOICES = (
        ('trial', 'Trial'),
        ('active', 'Active'),
        ('expired', 'Expired'),
        ('cancelled', 'Cancelled'),
        ('suspended', 'Suspended'),
    )
    
    # Identifiers
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='module_subscriptions'
    )
    module = models.ForeignKey(
        Module,
        on_delete=models.PROTECT,
        related_name='subscriptions'
    )
    pricing = models.ForeignKey(
        ModulePricing,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        help_text="Null for trial/free subscriptions"
    )
    
    # Status
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='trial',
        db_index=True
    )
    
    # Dates
    started_at = models.DateTimeField(default=timezone.now)
    expires_at = models.DateTimeField(db_index=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    
    # Usage tracking
    usage_count = models.PositiveIntegerField(default=0)
    usage_limit = models.PositiveIntegerField(
        default=0,
        help_text="0 = unlimited"
    )
    usage_reset_at = models.DateTimeField(null=True, blank=True)
    
    # Payment reference
    payment = models.ForeignKey(
        'Payment',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='subscriptions'
    )
    
    # Auto-renewal
    auto_renew = models.BooleanField(default=False)
    renewal_reminder_sent = models.BooleanField(default=False)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'module', 'status']),
            models.Index(fields=['expires_at']),
            models.Index(fields=['status', 'expires_at']),
        ]
    
    def __str__(self):
        return f"{self.user.username} - {self.module.name} ({self.status})"
    
    def is_active(self):
        """Check if subscription is currently active"""
        if self.status not in ('active', 'trial'):
            return False
        return timezone.now() < self.expires_at
    
    def is_trial(self):
        return self.status == 'trial'
    
    def days_remaining(self):
        """Get days until expiration"""
        if self.expires_at:
            delta = self.expires_at - timezone.now()
            return max(0, delta.days)
        return 0
    
    def can_use(self):
        """Check if user can use this module (active + within usage limit)"""
        if not self.is_active():
            return False, "Subscription expired"
        
        if self.usage_limit > 0 and self.usage_count >= self.usage_limit:
            return False, "Monthly usage limit reached"
        
        return True, None
    
    def record_usage(self):
        """Record a usage of this module"""
        self.usage_count += 1
        self.save(update_fields=['usage_count', 'updated_at'])
    
    def reset_usage(self):
        """Reset monthly usage counter"""
        self.usage_count = 0
        self.usage_reset_at = timezone.now()
        self.save(update_fields=['usage_count', 'usage_reset_at'])
    
    def cancel(self):
        """Cancel subscription (still active until expires_at)"""
        self.status = 'cancelled'
        self.cancelled_at = timezone.now()
        self.auto_renew = False
        self.save(update_fields=['status', 'cancelled_at', 'auto_renew'])
    
    def expire(self):
        """Mark subscription as expired"""
        self.status = 'expired'
        self.save(update_fields=['status'])
    
    @classmethod
    def get_active_subscription(cls, user, module_code):
        """Get user's active subscription for a module"""
        return cls.objects.filter(
            user=user,
            module__code=module_code,
            status__in=['active', 'trial'],
            expires_at__gt=timezone.now()
        ).first()
    
    @classmethod
    def has_access(cls, user, module_code):
        """Check if user has access to a module"""
        # Check if module is free
        try:
            module = Module.objects.get(code=module_code)
            if module.is_free:
                return True
        except Module.DoesNotExist:
            return False
        
        # Check for active subscription
        return cls.get_active_subscription(user, module_code) is not None


# ==============================================================================
# PAYMENTS
# ==============================================================================

class Payment(models.Model):
    """
    Payment transactions for subscriptions.
    Supports Razorpay, Stripe, and manual payments.
    """
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('refunded', 'Refunded'),
        ('partially_refunded', 'Partially Refunded'),
    )
    
    GATEWAY_CHOICES = (
        ('razorpay', 'Razorpay'),
        ('stripe', 'Stripe'),
        ('manual', 'Manual/Bank Transfer'),
        ('free', 'Free/Coupon'),
    )
    
    # Identifiers
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order_id = models.CharField(
        max_length=100,
        unique=True,
        db_index=True,
        help_text="Internal order ID"
    )
    
    user = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='payments'
    )
    
    # What they're paying for
    modules = models.ManyToManyField(
        Module,
        related_name='payments',
        help_text="Modules included in this payment"
    )
    pricing_snapshot = models.JSONField(
        default=dict,
        help_text="Snapshot of pricing at time of payment"
    )
    
    # Amounts (in INR)
    subtotal = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    discount_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00')
    )
    gst_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00')
    )
    total_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    
    # Coupon
    coupon = models.ForeignKey(
        'Coupon',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='payments'
    )
    
    # Payment gateway
    gateway = models.CharField(
        max_length=20,
        choices=GATEWAY_CHOICES,
        default='razorpay'
    )
    gateway_order_id = models.CharField(
        max_length=255,
        blank=True,
        help_text="Order ID from payment gateway"
    )
    gateway_payment_id = models.CharField(
        max_length=255,
        blank=True,
        help_text="Payment ID from gateway (after success)"
    )
    gateway_signature = models.CharField(
        max_length=255,
        blank=True,
        help_text="Signature for verification"
    )
    gateway_response = models.JSONField(
        default=dict,
        blank=True,
        help_text="Full response from gateway"
    )
    
    # Status
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending',
        db_index=True
    )
    
    # Refund info
    refund_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00')
    )
    refund_reason = models.TextField(blank=True)
    refunded_at = models.DateTimeField(null=True, blank=True)
    
    # Billing info snapshot
    billing_name = models.CharField(max_length=255, blank=True)
    billing_email = models.EmailField(blank=True)
    billing_phone = models.CharField(max_length=20, blank=True)
    billing_address = models.TextField(blank=True)
    billing_gstin = models.CharField(max_length=15, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'status']),
            models.Index(fields=['order_id']),
            models.Index(fields=['gateway_order_id']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        return f"Payment {self.order_id} - ₹{self.total_amount} ({self.status})"
    
    def mark_completed(self, gateway_payment_id=None, gateway_response=None):
        """Mark payment as completed"""
        self.status = 'completed'
        self.completed_at = timezone.now()
        if gateway_payment_id:
            self.gateway_payment_id = gateway_payment_id
        if gateway_response:
            self.gateway_response = gateway_response
        self.save()
    
    def mark_failed(self, gateway_response=None):
        """Mark payment as failed"""
        self.status = 'failed'
        if gateway_response:
            self.gateway_response = gateway_response
        self.save()
    
    def process_refund(self, amount, reason=''):
        """Process a refund"""
        self.refund_amount = amount
        self.refund_reason = reason
        self.refunded_at = timezone.now()
        
        if amount >= self.total_amount:
            self.status = 'refunded'
        else:
            self.status = 'partially_refunded'
        
        self.save()
    
    @classmethod
    def generate_order_id(cls):
        """Generate unique order ID"""
        import random
        import string
        timestamp = timezone.now().strftime('%Y%m%d%H%M%S')
        random_str = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
        return f"ORD-{timestamp}-{random_str}"


# ==============================================================================
# INVOICES
# ==============================================================================

class Invoice(models.Model):
    """
    Tax invoices generated for completed payments.
    """
    # Identifiers
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    invoice_number = models.CharField(
        max_length=50,
        unique=True,
        db_index=True
    )
    
    payment = models.OneToOneField(
        Payment,
        on_delete=models.PROTECT,
        related_name='invoice'
    )
    user = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='invoices'
    )
    
    # Invoice details
    invoice_date = models.DateField(default=timezone.now)
    due_date = models.DateField(null=True, blank=True)
    
    # Amounts
    subtotal = models.DecimalField(max_digits=10, decimal_places=2)
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    taxable_amount = models.DecimalField(max_digits=10, decimal_places=2)
    cgst_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    sgst_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    igst_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    
    # Line items
    line_items = models.JSONField(default=list)
    # Format: [{"module": "Estimate", "duration": "1 Year", "price": 999, "gst": 180}, ...]
    
    # Billing info
    billing_name = models.CharField(max_length=255)
    billing_address = models.TextField()
    billing_gstin = models.CharField(max_length=15, blank=True)
    billing_state = models.CharField(max_length=100, blank=True)
    
    # Seller info
    seller_name = models.CharField(max_length=255, default='Your Company Name')
    seller_address = models.TextField(default='Your Company Address')
    seller_gstin = models.CharField(max_length=15, blank=True)
    
    # PDF
    pdf_file = models.FileField(
        upload_to='invoices/%Y/%m/',
        blank=True,
        null=True
    )
    
    # Status
    is_paid = models.BooleanField(default=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-invoice_date', '-invoice_number']
        indexes = [
            models.Index(fields=['user', 'invoice_date']),
            models.Index(fields=['invoice_number']),
        ]
    
    def __str__(self):
        return f"Invoice {self.invoice_number}"
    
    @classmethod
    def generate_invoice_number(cls):
        """Generate sequential invoice number"""
        year = timezone.now().strftime('%Y%m')
        last_invoice = cls.objects.filter(
            invoice_number__startswith=f'INV-{year}'
        ).order_by('-invoice_number').first()
        
        if last_invoice:
            try:
                last_num = int(last_invoice.invoice_number.split('-')[-1])
                next_num = last_num + 1
            except ValueError:
                next_num = 1
        else:
            next_num = 1
        
        return f"INV-{year}-{next_num:05d}"


# ==============================================================================
# COUPONS
# ==============================================================================

class Coupon(models.Model):
    """
    Discount coupons for subscriptions.
    """
    DISCOUNT_TYPE_CHOICES = (
        ('percent', 'Percentage'),
        ('fixed', 'Fixed Amount'),
    )
    
    # Identifiers
    code = models.CharField(
        max_length=50,
        unique=True,
        db_index=True,
        help_text="Coupon code (uppercase)"
    )
    description = models.CharField(max_length=255, blank=True)
    
    # Discount
    discount_type = models.CharField(
        max_length=10,
        choices=DISCOUNT_TYPE_CHOICES,
        default='percent'
    )
    discount_value = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))]
    )
    max_discount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Max discount amount (for percentage coupons)"
    )
    
    # Applicability
    applicable_modules = models.ManyToManyField(
        Module,
        blank=True,
        help_text="Leave empty for all modules"
    )
    min_purchase = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Minimum purchase amount"
    )
    
    # Usage limits
    max_uses = models.PositiveIntegerField(
        default=0,
        help_text="0 = unlimited"
    )
    max_uses_per_user = models.PositiveIntegerField(
        default=1,
        help_text="Max uses per user"
    )
    current_uses = models.PositiveIntegerField(default=0)
    
    # Validity
    valid_from = models.DateTimeField(default=timezone.now)
    valid_until = models.DateTimeField(null=True, blank=True)
    
    # Restrictions
    first_purchase_only = models.BooleanField(default=False)
    specific_users = models.ManyToManyField(
        User,
        blank=True,
        help_text="Leave empty for all users"
    )
    
    # Status
    is_active = models.BooleanField(default=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        if self.discount_type == 'percent':
            return f"{self.code} ({self.discount_value}% off)"
        return f"{self.code} (₹{self.discount_value} off)"
    
    def save(self, *args, **kwargs):
        self.code = self.code.upper()
        super().save(*args, **kwargs)
    
    def is_valid(self):
        """Check if coupon is currently valid"""
        if not self.is_active:
            return False, "Coupon is inactive"
        
        now = timezone.now()
        if now < self.valid_from:
            return False, "Coupon not yet valid"
        
        if self.valid_until and now > self.valid_until:
            return False, "Coupon has expired"
        
        if self.max_uses > 0 and self.current_uses >= self.max_uses:
            return False, "Coupon usage limit reached"
        
        return True, None
    
    def can_use(self, user, amount):
        """Check if user can use this coupon"""
        is_valid, error = self.is_valid()
        if not is_valid:
            return False, error
        
        # Check min purchase
        if amount < self.min_purchase:
            return False, f"Minimum purchase of ₹{self.min_purchase} required"
        
        # Check user restriction
        if self.specific_users.exists():
            if not self.specific_users.filter(id=user.id).exists():
                return False, "Coupon not valid for this account"
        
        # Check first purchase only
        if self.first_purchase_only:
            if Payment.objects.filter(user=user, status='completed').exists():
                return False, "Coupon valid for first purchase only"
        
        # Check per-user limit
        user_uses = Payment.objects.filter(
            user=user,
            coupon=self,
            status='completed'
        ).count()
        if user_uses >= self.max_uses_per_user:
            return False, "You have already used this coupon"
        
        return True, None
    
    def calculate_discount(self, amount):
        """Calculate discount amount"""
        if self.discount_type == 'percent':
            discount = (amount * self.discount_value) / 100
            if self.max_discount:
                discount = min(discount, self.max_discount)
        else:
            discount = self.discount_value
        
        return min(discount, amount)  # Can't exceed purchase amount
    
    def record_use(self):
        """Record coupon usage"""
        self.current_uses += 1
        self.save(update_fields=['current_uses'])


# ==============================================================================
# USAGE TRACKING
# ==============================================================================

class UsageLog(models.Model):
    """
    Track module usage for analytics and billing.
    """
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='usage_logs'
    )
    module = models.ForeignKey(
        Module,
        on_delete=models.CASCADE,
        related_name='usage_logs'
    )
    subscription = models.ForeignKey(
        UserModuleSubscription,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='usage_logs'
    )
    
    # Action details
    action = models.CharField(
        max_length=100,
        help_text="What action was performed (generate_estimate, download_pdf, etc.)"
    )
    resource_id = models.CharField(
        max_length=100,
        blank=True,
        help_text="ID of the resource created/modified"
    )
    metadata = models.JSONField(default=dict, blank=True)
    
    # Request info
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    
    # Timestamp
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'module', 'created_at']),
            models.Index(fields=['module', 'action', 'created_at']),
        ]
    
    def __str__(self):
        return f"{self.user.username} - {self.module.code}:{self.action}"
    
    @classmethod
    def log(cls, user, module_code, action, resource_id='', metadata=None, request=None):
        """Convenience method to create usage log"""
        try:
            module = Module.objects.get(code=module_code)
        except Module.DoesNotExist:
            return None
        
        ip_address = None
        user_agent = ''
        if request:
            ip_address = request.META.get('HTTP_X_FORWARDED_FOR', 
                         request.META.get('REMOTE_ADDR'))
            if ip_address:
                ip_address = ip_address.split(',')[0].strip()
            user_agent = request.META.get('HTTP_USER_AGENT', '')
        
        subscription = UserModuleSubscription.get_active_subscription(user, module_code)
        
        return cls.objects.create(
            user=user,
            module=module,
            subscription=subscription,
            action=action,
            resource_id=str(resource_id),
            metadata=metadata or {},
            ip_address=ip_address,
            user_agent=user_agent
        )
