# datasets/models.py
"""
Admin-managed datasets (SSR data), versioning, import jobs, and audit logging.

Models:
- State: Indian states for SOR rates (Telangana, AP, etc.)
- SORRateBook: State-wise SOR rate books (Schedule of Rates)
- DatasetCategory: Categories for organizing datasets
- Dataset: Master data files (SSR books, rate lists, etc.)
- DatasetVersion: Version history with file storage
- DatasetImportJob: Track import progress for large files
- ModuleDatasetConfig: Link modules to multiple datasets/backends
- AuditLog: Track all admin actions on datasets
"""

import uuid
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.core.validators import FileExtensionValidator


# ==============================================================================
# INDIAN STATES
# ==============================================================================

class State(models.Model):
    """
    Indian states for SOR (Schedule of Rates) management.
    Each state can have different SOR rate books.
    """
    # State codes follow ISO 3166-2:IN
    code = models.CharField(
        max_length=10,
        unique=True,
        db_index=True,
        help_text="State code like 'TS', 'AP', 'KA', 'MH'"
    )
    name = models.CharField(max_length=100, unique=True)
    full_name = models.CharField(
        max_length=200,
        blank=True,
        help_text="Full official name (e.g., 'State of Telangana')"
    )
    
    # Display
    display_order = models.PositiveIntegerField(default=0)
    flag_icon = models.CharField(max_length=50, blank=True, help_text="Icon or emoji")
    
    # Status
    is_active = models.BooleanField(default=True)
    is_default = models.BooleanField(
        default=False,
        help_text="Default state for new users"
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['display_order', 'name']
        verbose_name = 'State'
        verbose_name_plural = 'States'
    
    def __str__(self):
        return f"{self.name} ({self.code})"
    
    def save(self, *args, **kwargs):
        # Ensure only one default state
        if self.is_default:
            State.objects.filter(is_default=True).exclude(pk=self.pk).update(is_default=False)
        super().save(*args, **kwargs)
    
    @classmethod
    def get_default(cls):
        """Get the default state (Telangana by default)"""
        default = cls.objects.filter(is_default=True, is_active=True).first()
        if not default:
            default = cls.objects.filter(is_active=True).first()
        return default
    
    @classmethod
    def get_active_states(cls):
        """Get all active states for dropdowns"""
        return cls.objects.filter(is_active=True).order_by('display_order', 'name')


# ==============================================================================
# SOR RATE BOOKS
# ==============================================================================

def sor_file_path(instance, filename):
    """Generate file path for SOR files"""
    return f"sor_rates/{instance.state.code}/{instance.work_type}/{filename}"


class SORRateBook(models.Model):
    """
    State-wise SOR (Schedule of Rates) rate books.
    Each state can have multiple rate books for different work types.
    
    Examples:
    - Telangana Electrical SOR 2024-25
    - Andhra Pradesh Civil SOR 2024-25
    - Telangana Buildings SOR 2023-24
    """
    WORK_TYPE_CHOICES = (
        ('electrical', 'Electrical'),
        ('civil', 'Civil'),
        ('buildings', 'Buildings'),
        ('roads', 'Roads'),
        ('irrigation', 'Irrigation'),
        ('plumbing', 'Plumbing'),
        ('mechanical', 'Mechanical'),
        ('other', 'Other'),
    )
    
    STATUS_CHOICES = (
        ('draft', 'Draft'),
        ('published', 'Published'),
        ('archived', 'Archived'),
    )
    
    # Identifiers
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(
        max_length=50,
        unique=True,
        db_index=True,
        help_text="Unique code like 'TS_ELEC_2024', 'AP_CIVIL_2024'"
    )
    
    # State link
    state = models.ForeignKey(
        State,
        on_delete=models.PROTECT,
        related_name='sor_rate_books'
    )
    
    # Basic info
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    work_type = models.CharField(
        max_length=20,
        choices=WORK_TYPE_CHOICES,
        db_index=True
    )
    
    # Financial year
    financial_year = models.CharField(
        max_length=20,
        help_text="Financial year like '2024-25', '2023-24'"
    )
    year = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Primary year (e.g., 2024)"
    )
    
    # Validity dates
    effective_from = models.DateField(
        null=True,
        blank=True,
        help_text="Date from which these rates are effective"
    )
    effective_until = models.DateField(
        null=True,
        blank=True,
        help_text="Date until which these rates are effective"
    )
    
    # The actual Excel file with rate data
    file = models.FileField(
        upload_to=sor_file_path,
        validators=[FileExtensionValidator(
            allowed_extensions=['xlsx', 'xls']
        )],
        help_text="Excel file with 'Master Datas' and 'Groups' sheets"
    )
    file_size = models.PositiveIntegerField(default=0, help_text="Size in bytes")
    
    # Stats
    total_items = models.PositiveIntegerField(default=0)
    total_groups = models.PositiveIntegerField(default=0)
    
    # Status
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='draft',
        db_index=True
    )
    is_active = models.BooleanField(default=True)
    is_default = models.BooleanField(
        default=False,
        help_text="Default rate book for this state and work type"
    )
    
    # Admin
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_sor_books'
    )
    updated_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='updated_sor_books'
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    published_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-year', 'state', 'work_type']
        verbose_name = 'SOR Rate Book'
        verbose_name_plural = 'SOR Rate Books'
        unique_together = ['state', 'work_type', 'financial_year']
        indexes = [
            models.Index(fields=['state', 'work_type', 'status']),
            models.Index(fields=['state', 'is_active', 'is_default']),
            models.Index(fields=['work_type', 'financial_year']),
        ]
    
    def __str__(self):
        return f"{self.state.code} {self.get_work_type_display()} SOR {self.financial_year}"
    
    def save(self, *args, **kwargs):
        # Calculate file size
        if self.file and hasattr(self.file, 'size'):
            self.file_size = self.file.size
        
        # Ensure only one default per state+work_type
        if self.is_default:
            SORRateBook.objects.filter(
                state=self.state,
                work_type=self.work_type,
                is_default=True
            ).exclude(pk=self.pk).update(is_default=False)
        
        super().save(*args, **kwargs)
    
    def publish(self, user=None):
        """Publish the rate book"""
        self.status = 'published'
        self.published_at = timezone.now()
        if user:
            self.updated_by = user
        self.save()
    
    def archive(self, user=None):
        """Archive the rate book"""
        self.status = 'archived'
        if user:
            self.updated_by = user
        self.save()
    
    def get_file_path(self):
        """Get absolute file path"""
        if self.file:
            return self.file.path
        return None
    
    def get_file_size_display(self):
        """Human-readable file size"""
        size = self.file_size
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} TB"
    
    @classmethod
    def get_for_state_and_type(cls, state_code, work_type):
        """Get the active default rate book for a state and work type"""
        return cls.objects.filter(
            state__code=state_code,
            work_type=work_type,
            is_active=True,
            status='published'
        ).order_by('-is_default', '-year').first()
    
    @classmethod
    def get_available_for_module(cls, module_code, state_code=None):
        """Get all rate books available for a module"""
        queryset = cls.objects.filter(
            is_active=True,
            status='published'
        )
        if state_code:
            queryset = queryset.filter(state__code=state_code)
        return queryset.order_by('state', 'work_type', '-year')


# ==============================================================================
# DATASET CATEGORIES
# ==============================================================================

class DatasetCategory(models.Model):
    """
    Categories for organizing datasets.
    Examples: SSR Books, Rate Lists, Material Rates, Labour Rates
    """
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    
    # Display
    icon = models.CharField(max_length=50, blank=True, help_text="Icon class or emoji")
    color = models.CharField(max_length=20, default='#6B7280')
    display_order = models.PositiveIntegerField(default=0)
    
    # Parent category for hierarchy
    parent = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='children'
    )
    
    # Status
    is_active = models.BooleanField(default=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Dataset Category'
        verbose_name_plural = 'Dataset Categories'
        ordering = ['display_order', 'name']
    
    def __str__(self):
        if self.parent:
            return f"{self.parent.name} > {self.name}"
        return self.name
    
    def get_full_path(self):
        """Get full category path"""
        if self.parent:
            return f"{self.parent.get_full_path()} > {self.name}"
        return self.name
    
    def get_dataset_count(self):
        """Get count of datasets in this category"""
        return self.datasets.filter(is_active=True).count()


# ==============================================================================
# DATASETS
# ==============================================================================

class Dataset(models.Model):
    """
    Master data files managed by admin.
    Examples: AP SSR 2023-24, Telangana SSR 2024, Material Rates Q1 2024
    """
    STATUS_CHOICES = (
        ('draft', 'Draft'),
        ('published', 'Published'),
        ('archived', 'Archived'),
    )
    
    # Identifiers
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(
        max_length=50,
        unique=True,
        db_index=True,
        help_text="Unique code like 'AP_SSR_2024', 'TS_MATERIALS_Q1'"
    )
    
    # Basic info
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    category = models.ForeignKey(
        DatasetCategory,
        on_delete=models.PROTECT,
        related_name='datasets'
    )
    
    # Metadata
    year = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Year this dataset applies to"
    )
    state = models.CharField(
        max_length=100,
        blank=True,
        help_text="State/region this dataset applies to"
    )
    effective_from = models.DateField(
        null=True,
        blank=True,
        help_text="Date from which this dataset is effective"
    )
    effective_until = models.DateField(
        null=True,
        blank=True,
        help_text="Date until which this dataset is effective"
    )
    
    # Current version
    current_version = models.ForeignKey(
        'DatasetVersion',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='current_for_dataset'
    )
    
    # Stats
    total_records = models.PositiveIntegerField(default=0)
    total_downloads = models.PositiveIntegerField(default=0)
    
    # Status
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='draft',
        db_index=True
    )
    is_active = models.BooleanField(default=True)
    is_premium = models.BooleanField(
        default=False,
        help_text="Requires paid subscription to access"
    )
    
    # Access control
    allowed_modules = models.JSONField(
        default=list,
        blank=True,
        help_text="List of module codes that can use this dataset"
    )
    
    # Admin
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_datasets'
    )
    updated_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='updated_datasets'
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    published_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['code']),
            models.Index(fields=['category', 'status']),
            models.Index(fields=['state', 'year']),
            models.Index(fields=['status', 'is_active']),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.code})"
    
    def publish(self, user=None):
        """Publish the dataset"""
        self.status = 'published'
        self.published_at = timezone.now()
        if user:
            self.updated_by = user
        self.save()
    
    def archive(self, user=None):
        """Archive the dataset"""
        self.status = 'archived'
        if user:
            self.updated_by = user
        self.save()
    
    def get_version_count(self):
        """Get number of versions"""
        return self.versions.count()
    
    def increment_downloads(self):
        """Increment download counter"""
        self.total_downloads += 1
        self.save(update_fields=['total_downloads'])


# ==============================================================================
# DATASET VERSIONS
# ==============================================================================

def dataset_file_path(instance, filename):
    """Generate file path for dataset files"""
    return f"datasets/{instance.dataset.code}/{instance.version}/{filename}"


class DatasetVersion(models.Model):
    """
    Version history for datasets.
    Each version can have a different file with changelog.
    """
    STATUS_CHOICES = (
        ('uploading', 'Uploading'),
        ('processing', 'Processing'),
        ('ready', 'Ready'),
        ('failed', 'Failed'),
    )
    
    # Identifiers
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    dataset = models.ForeignKey(
        Dataset,
        on_delete=models.CASCADE,
        related_name='versions'
    )
    
    # Version info
    version = models.CharField(
        max_length=20,
        help_text="Version string like 'v1.0', 'v2.1'"
    )
    changelog = models.TextField(
        blank=True,
        help_text="What changed in this version"
    )
    
    # File
    file = models.FileField(
        upload_to=dataset_file_path,
        validators=[FileExtensionValidator(
            allowed_extensions=['xlsx', 'xls', 'csv', 'json']
        )]
    )
    file_size = models.PositiveIntegerField(default=0, help_text="Size in bytes")
    file_hash = models.CharField(max_length=64, blank=True, help_text="SHA256 hash")
    
    # Processing info
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='uploading'
    )
    record_count = models.PositiveIntegerField(default=0)
    error_message = models.TextField(blank=True)
    
    # Parsed data (stored in JSON for quick access)
    parsed_data = models.JSONField(
        default=dict,
        blank=True,
        help_text="Parsed and indexed data from file"
    )
    column_mapping = models.JSONField(
        default=dict,
        blank=True,
        help_text="Column name mappings"
    )
    
    # Admin
    uploaded_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='uploaded_versions'
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        unique_together = ['dataset', 'version']
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['dataset', 'status']),
            models.Index(fields=['version']),
        ]
    
    def __str__(self):
        return f"{self.dataset.name} - {self.version}"
    
    def save(self, *args, **kwargs):
        # Calculate file size
        if self.file and hasattr(self.file, 'size'):
            self.file_size = self.file.size
        super().save(*args, **kwargs)
    
    def mark_ready(self, record_count=0):
        """Mark version as ready"""
        self.status = 'ready'
        self.record_count = record_count
        self.processed_at = timezone.now()
        self.save()
        
        # Update parent dataset
        self.dataset.current_version = self
        self.dataset.total_records = record_count
        self.dataset.save(update_fields=['current_version', 'total_records'])
    
    def mark_failed(self, error_message):
        """Mark version as failed"""
        self.status = 'failed'
        self.error_message = error_message
        self.processed_at = timezone.now()
        self.save()
    
    def get_file_size_display(self):
        """Human-readable file size"""
        size = self.file_size
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} TB"


# ==============================================================================
# IMPORT JOBS
# ==============================================================================

class DatasetImportJob(models.Model):
    """
    Track import progress for large dataset files.
    Useful for async processing with Celery.
    """
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('running', 'Running'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
    )
    
    # Identifiers
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    dataset_version = models.ForeignKey(
        DatasetVersion,
        on_delete=models.CASCADE,
        related_name='import_jobs'
    )
    
    # Status
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending',
        db_index=True
    )
    
    # Progress
    total_rows = models.PositiveIntegerField(default=0)
    processed_rows = models.PositiveIntegerField(default=0)
    failed_rows = models.PositiveIntegerField(default=0)
    
    # Errors
    error_log = models.JSONField(
        default=list,
        blank=True,
        help_text="List of row-level errors"
    )
    error_message = models.TextField(blank=True)
    
    # Celery task info
    task_id = models.CharField(max_length=255, blank=True)
    
    # Admin
    started_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='started_imports'
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'created_at']),
        ]
    
    def __str__(self):
        return f"Import {self.dataset_version} ({self.status})"
    
    @property
    def progress_percent(self):
        """Get progress percentage"""
        if self.total_rows > 0:
            return int((self.processed_rows / self.total_rows) * 100)
        return 0
    
    def start(self):
        """Mark job as started"""
        self.status = 'running'
        self.started_at = timezone.now()
        self.save()
    
    def complete(self):
        """Mark job as completed"""
        self.status = 'completed'
        self.completed_at = timezone.now()
        self.save()
        
        # Update version
        self.dataset_version.mark_ready(self.processed_rows)
    
    def fail(self, error_message):
        """Mark job as failed"""
        self.status = 'failed'
        self.error_message = error_message
        self.completed_at = timezone.now()
        self.save()
        
        # Update version
        self.dataset_version.mark_failed(error_message)
    
    def add_row_error(self, row_number, error):
        """Add a row-level error"""
        self.error_log.append({
            'row': row_number,
            'error': str(error),
            'timestamp': timezone.now().isoformat()
        })
        self.failed_rows += 1
        self.save(update_fields=['error_log', 'failed_rows'])
    
    def update_progress(self, processed):
        """Update progress"""
        self.processed_rows = processed
        self.save(update_fields=['processed_rows'])


# ==============================================================================
# AUDIT LOG
# ==============================================================================

class AuditLog(models.Model):
    """
    Track all admin actions on datasets for accountability.
    """
    ACTION_CHOICES = (
        ('create', 'Create'),
        ('update', 'Update'),
        ('delete', 'Delete'),
        ('publish', 'Publish'),
        ('archive', 'Archive'),
        ('upload', 'Upload Version'),
        ('download', 'Download'),
        ('import', 'Import Data'),
        ('export', 'Export Data'),
        ('access', 'Access'),
    )
    
    # Who
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='dataset_audit_logs'
    )
    user_email = models.EmailField(blank=True, help_text="Snapshot of user email")
    
    # What
    action = models.CharField(max_length=20, choices=ACTION_CHOICES, db_index=True)
    model_name = models.CharField(
        max_length=100,
        help_text="Model that was acted upon"
    )
    object_id = models.CharField(
        max_length=100,
        db_index=True,
        help_text="ID of the object"
    )
    object_repr = models.CharField(
        max_length=255,
        help_text="String representation of object"
    )
    
    # Details
    changes = models.JSONField(
        default=dict,
        blank=True,
        help_text="Before/after values for updates"
    )
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Additional context"
    )
    
    # Request info
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    
    # Timestamp
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Audit Log'
        verbose_name_plural = 'Audit Logs'
        indexes = [
            models.Index(fields=['user', 'action', 'created_at']),
            models.Index(fields=['model_name', 'object_id']),
            models.Index(fields=['action', 'created_at']),
        ]
    
    def __str__(self):
        return f"{self.user_email or 'System'} {self.action} {self.model_name}"
    
    @classmethod
    def log(cls, user, action, obj, changes=None, metadata=None, request=None):
        """
        Convenience method to create audit log entry.
        
        Usage:
            AuditLog.log(request.user, 'update', dataset, 
                         changes={'name': {'old': 'A', 'new': 'B'}})
        """
        ip_address = None
        user_agent = ''
        
        if request:
            ip_address = request.META.get('HTTP_X_FORWARDED_FOR',
                         request.META.get('REMOTE_ADDR'))
            if ip_address:
                ip_address = ip_address.split(',')[0].strip()
            user_agent = request.META.get('HTTP_USER_AGENT', '')
        
        # Support non-model objects (like string identifiers)
        if hasattr(obj, 'pk') and hasattr(obj, '__class__'):
            model_name = obj.__class__.__name__
            object_id = str(obj.pk)
            object_repr = str(obj)[:255]
        else:
            model_name = str(obj)
            object_id = str(obj)
            object_repr = str(obj)[:255]

        return cls.objects.create(
            user=user,
            user_email=user.email if user else '',
            action=action,
            model_name=model_name,
            object_id=object_id,
            object_repr=object_repr,
            changes=changes or {},
            metadata=metadata or {},
            ip_address=ip_address,
            user_agent=user_agent
        )
    
    @classmethod
    def get_history(cls, obj):
        """Get audit history for an object"""
        return cls.objects.filter(
            model_name=obj.__class__.__name__,
            object_id=str(obj.pk)
        ).order_by('-created_at')


# ==============================================================================
# MODULE DATASET CONFIGURATION
# ==============================================================================

class ModuleDatasetConfig(models.Model):
    """
    Links modules to their available SOR rate books and datasets.
    Allows admins to configure which backends are available for each module.
    
    This enables:
    - Multiple rate books per module (Telangana, AP, etc.)
    - Different rate books for different work types within a module
    - Flexible configuration without code changes
    
    Example configurations:
    - Estimate module + Electrical + TS = TS_ELEC_2024
    - Estimate module + Electrical + AP = AP_ELEC_2024
    - AMC module + Electrical + TS = TS_AMC_ELEC_2024
    """
    # Identifiers
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Module link (from subscriptions app)
    module_code = models.CharField(
        max_length=50,
        db_index=True,
        help_text="Module code like 'estimate', 'workslip', 'amc'"
    )
    
    # Work type category
    WORK_TYPE_CHOICES = (
        ('electrical', 'Electrical'),
        ('civil', 'Civil'),
        ('temp_electrical', 'Temp Electrical'),
        ('temp_civil', 'Temp Civil'),
        ('amc_electrical', 'AMC Electrical'),
        ('amc_civil', 'AMC Civil'),
        ('buildings', 'Buildings'),
        ('roads', 'Roads'),
        ('other', 'Other'),
    )
    work_type = models.CharField(
        max_length=30,
        choices=WORK_TYPE_CHOICES,
        db_index=True
    )
    
    # State link
    state = models.ForeignKey(
        State,
        on_delete=models.CASCADE,
        related_name='module_configs'
    )
    
    # Link to SOR Rate Book (new system)
    sor_rate_book = models.ForeignKey(
        SORRateBook,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='module_configs',
        help_text="SOR rate book to use for this configuration"
    )
    
    # Legacy: Link to old BackendWorkbook (for backward compatibility)
    legacy_workbook_id = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="ID of legacy BackendWorkbook (for migration)"
    )
    
    # Direct file upload (for quick setup without SORRateBook)
    custom_file = models.FileField(
        upload_to='module_backends/',
        blank=True,
        null=True,
        validators=[FileExtensionValidator(allowed_extensions=['xlsx', 'xls'])],
        help_text="Custom Excel file (overrides sor_rate_book)"
    )
    
    # Display
    display_name = models.CharField(
        max_length=255,
        blank=True,
        help_text="User-friendly name shown in dropdowns"
    )
    description = models.TextField(blank=True)
    
    # Ordering
    display_order = models.PositiveIntegerField(default=0)
    
    # Status
    is_active = models.BooleanField(default=True)
    is_default = models.BooleanField(
        default=False,
        help_text="Default config for this module + work_type combination"
    )
    
    # Admin
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_module_configs'
    )
    updated_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='updated_module_configs'
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['module_code', 'work_type', 'state__name', 'display_order']
        verbose_name = 'Module Dataset Config'
        verbose_name_plural = 'Module Dataset Configs'
        unique_together = ['module_code', 'work_type', 'state']
        indexes = [
            models.Index(fields=['module_code', 'work_type', 'is_active']),
            models.Index(fields=['state', 'is_active']),
            models.Index(fields=['module_code', 'is_default']),
        ]
    
    def __str__(self):
        return f"{self.module_code} / {self.work_type} / {self.state.code}"
    
    def save(self, *args, **kwargs):
        # Auto-generate display name if not provided
        if not self.display_name:
            self.display_name = f"{self.state.name} {self.get_work_type_display()}"
        
        # Ensure only one default per module + work_type
        if self.is_default:
            ModuleDatasetConfig.objects.filter(
                module_code=self.module_code,
                work_type=self.work_type,
                is_default=True
            ).exclude(pk=self.pk).update(is_default=False)
        
        super().save(*args, **kwargs)
    
    def get_file_path(self):
        """Get the file path to use for this configuration"""
        # Priority: custom_file > sor_rate_book > legacy_workbook
        if self.custom_file:
            return self.custom_file.path
        
        if self.sor_rate_book and self.sor_rate_book.file:
            return self.sor_rate_book.file.path
        
        # Try legacy workbook
        if self.legacy_workbook_id:
            try:
                from core.models import BackendWorkbook
                wb = BackendWorkbook.objects.get(pk=self.legacy_workbook_id)
                return wb.file.path
            except Exception:
                pass
        
        return None
    
    @classmethod
    def get_for_module(cls, module_code, work_type, state_code=None):
        """
        Get the appropriate config for a module and work type.
        Falls back to default if state-specific not found.
        """
        base_qs = cls.objects.filter(
            module_code=module_code,
            work_type=work_type,
            is_active=True
        )
        
        if state_code:
            # Try state-specific first
            config = base_qs.filter(state__code=state_code).first()
            if config:
                return config
        
        # Fall back to default
        return base_qs.filter(is_default=True).first()
    
    @classmethod
    def get_available_states_for_module(cls, module_code, work_type):
        """Get list of states available for a module and work type"""
        return State.objects.filter(
            module_configs__module_code=module_code,
            module_configs__work_type=work_type,
            module_configs__is_active=True
        ).distinct().order_by('display_order', 'name')
    
    @classmethod
    def get_all_for_module(cls, module_code, work_type=None):
        """Get all configs for a module, optionally filtered by work type"""
        qs = cls.objects.filter(module_code=module_code, is_active=True)
        if work_type:
            qs = qs.filter(work_type=work_type)
        return qs.select_related('state', 'sor_rate_book').order_by(
            'work_type', 'state__display_order', 'display_order'
        )


# ==============================================================================
# USER STATE PREFERENCE
# ==============================================================================

class UserStatePreference(models.Model):
    """
    Stores user's preferred state for SOR rates.
    Each user can select their default state for estimates and other modules.
    """
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='state_preference'
    )
    
    # Preferred state
    preferred_state = models.ForeignKey(
        State,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='user_preferences'
    )
    
    # Per-module state overrides (JSON: {"estimate": "AP", "workslip": "TS"})
    module_states = models.JSONField(
        default=dict,
        blank=True,
        help_text="Per-module state preferences"
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'User State Preference'
        verbose_name_plural = 'User State Preferences'
    
    def __str__(self):
        state_name = self.preferred_state.name if self.preferred_state else "Default"
        return f"{self.user.username} - {state_name}"
    
    def get_state_for_module(self, module_code):
        """Get the user's preferred state for a specific module"""
        # Check module-specific override first
        module_state_code = self.module_states.get(module_code)
        if module_state_code:
            state = State.objects.filter(code=module_state_code, is_active=True).first()
            if state:
                return state
        
        # Fall back to general preference
        if self.preferred_state and self.preferred_state.is_active:
            return self.preferred_state
        
        # Fall back to system default
        return State.get_default()
    
    def set_state_for_module(self, module_code, state_code):
        """Set state preference for a specific module"""
        self.module_states[module_code] = state_code
        self.save(update_fields=['module_states', 'updated_at'])
    
    @classmethod
    def get_or_create_for_user(cls, user):
        """Get or create state preference for a user"""
        pref, created = cls.objects.get_or_create(
            user=user,
            defaults={'preferred_state': State.get_default()}
        )
        return pref
