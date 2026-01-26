from django.db import models
from django.contrib.auth.models import User
import json
from .managers import OrgScopedManager, ProjectManager, JobManager, EstimateManager


# ==============================================================================
# MULTI-TENANCY & ORGANIZATION MODELS
# ==============================================================================

class Organization(models.Model):
    """Tenant organization - all users and their data belong to an org"""
    PLAN_CHOICES = (
        ("free", "Free"),
        ("starter", "Starter"),
        ("professional", "Professional"),
        ("enterprise", "Enterprise"),
    )
    
    name = models.CharField(max_length=255, unique=True)
    slug = models.SlugField(max_length=255, unique=True)  # For URL-safe naming
    plan = models.CharField(max_length=20, choices=PLAN_CHOICES, default="free")
    
    # Owner/creator
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='owned_organizations')
    
    # Settings
    is_active = models.BooleanField(default=True)
    metadata = models.JSONField(default=dict, blank=True)  # Custom org settings
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['owner', '-created_at']),
            models.Index(fields=['slug']),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.plan})"


class Membership(models.Model):
    """User's membership and role in an organization"""
    ROLE_CHOICES = (
        ("owner", "Owner"),
        ("admin", "Admin"),
        ("member", "Member"),
        ("viewer", "Viewer"),
    )
    
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='memberships')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='memberships')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default="member")
    
    # Track when user was added
    joined_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['organization', 'user']
        ordering = ['-joined_at']
        indexes = [
            models.Index(fields=['organization', 'user']),
        ]
    
    def __str__(self):
        return f"{self.user.username} - {self.organization.name} ({self.role})"


# ==============================================================================
# FILE UPLOAD & JOB PROCESSING MODELS
# ==============================================================================

class Upload(models.Model):
    """Track uploaded Excel files"""
    STATUS_CHOICES = (
        ("pending", "Pending"),
        ("processing", "Processing"),
        ("completed", "Completed"),
        ("failed", "Failed"),
    )
    
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='uploads')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='uploads')
    
    file = models.FileField(upload_to="uploads/%Y/%m/%d/")
    filename = models.CharField(max_length=255)
    file_size = models.BigIntegerField()  # in bytes
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    objects = OrgScopedManager()
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['organization', '-created_at']),
            models.Index(fields=['user', '-created_at']),
        ]
    
    def __str__(self):
        return f"{self.filename} - {self.organization.name}"


class Job(models.Model):
    """Track background job processing (Excel parsing, generation, etc.)"""
    STATUS_CHOICES = (
        ("queued", "Queued"),
        ("running", "Running"),
        ("completed", "Completed"),
        ("failed", "Failed"),
        ("cancelled", "Cancelled"),
    )
    
    JOB_TYPE_CHOICES = (
        ("parse_estimate", "Parse Estimate"),
        ("generate_bill", "Generate Bill"),
        ("generate_workslip", "Generate Workslip"),
        ("export_data", "Export Data"),
        ("generate_output_excel", "Generate Output Excel"),
        ("generate_estimate_excel", "Generate Estimate Excel"),
    )
    
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='jobs')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='jobs')
    upload = models.ForeignKey(Upload, on_delete=models.SET_NULL, null=True, blank=True, related_name='jobs')
    
    job_type = models.CharField(max_length=50, choices=JOB_TYPE_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="queued")
    
    # Celery task tracking
    celery_task_id = models.CharField(max_length=255, blank=True, null=True, db_index=True)
    
    # Progress tracking
    progress = models.IntegerField(default=0)  # 0-100
    current_step = models.CharField(max_length=255, blank=True)  # "Parsing rows..." etc.
    
    # Results
    result = models.JSONField(default=dict, blank=True)  # Job output data
    error_message = models.TextField(blank=True)
    error_log = models.JSONField(default=list, blank=True)  # List of errors/warnings
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    objects = JobManager()
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['organization', '-created_at']),
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['status']),
            models.Index(fields=['celery_task_id']),
        ]
    
    def __str__(self):
        return f"{self.job_type} - {self.status} ({self.organization.name})"
    
    def is_complete(self):
        return self.status in ['completed', 'failed', 'cancelled']


class OutputFile(models.Model):
    """Generated output files (Excel, PDF, etc.) from jobs"""
    FILE_TYPE_CHOICES = (
        ("excel", "Excel"),
        ("pdf", "PDF"),
        ("docx", "Word"),
        ("json", "JSON"),
    )
    
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='output_files')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='output_files')
    job = models.ForeignKey(Job, on_delete=models.CASCADE, related_name='output_files')
    
    file = models.FileField(upload_to="outputs/%Y/%m/%d/")
    filename = models.CharField(max_length=255)
    file_type = models.CharField(max_length=20, choices=FILE_TYPE_CHOICES)
    file_size = models.BigIntegerField()  # in bytes
    
    # Access tracking
    download_count = models.IntegerField(default=0)
    last_downloaded = models.DateTimeField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['organization', '-created_at']),
            models.Index(fields=['job']),
        ]
    
    def __str__(self):
        return f"{self.filename} ({self.organization.name})"


# ==============================================================================
# USER PROFILE (EXISTING - kept for reference)
# ==============================================================================

class UserProfile(models.Model):
    """Extended user profile for commercial features"""
    SUBSCRIPTION_CHOICES = (
        ("free", "Free"),
        ("pro", "Pro"),
        ("enterprise", "Enterprise"),
    )
    
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    company_name = models.CharField(max_length=255, blank=True)
    subscription_tier = models.CharField(max_length=20, choices=SUBSCRIPTION_CHOICES, default="free")
    estimates_limit = models.IntegerField(default=10)  # Free tier limit
    estimates_created = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def can_create_estimate(self):
        """Check if user can create more estimates based on tier"""
        if self.subscription_tier == "free":
            return self.estimates_created < self.estimates_limit
        return True
    
    def __str__(self):
        return f"{self.user.get_full_name() or self.user.username} - {self.subscription_tier}"


# ==============================================================================
# PROJECT & ESTIMATE MODELS (EXISTING - updated for org scoping)
# ==============================================================================

class Project(models.Model):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='projects')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='projects', null=True, blank=True)
    
    name = models.CharField(max_length=255)
    category = models.CharField(max_length=50, null=True, blank=True)
    items_json = models.TextField(default="[]")  # list stored safely
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    objects = ProjectManager()

    class Meta:
        unique_together = [['organization', 'name']]  # Project names unique per org
        ordering = ['-updated_at']
        indexes = [
            models.Index(fields=['organization', '-created_at']),
        ]

    def set_items(self, items_list):
        self.items_json = json.dumps(items_list)

    def get_items(self):
        try:
            return json.loads(self.items_json)
        except Exception:
            return []

    def __str__(self):
        return f"{self.name} ({self.organization.name})"


class Estimate(models.Model):
    """Stores completed estimates/workslips with full data persistence"""
    STATUS_CHOICES = (
        ("draft", "Draft"),
        ("finalized", "Finalized"),
        ("archived", "Archived"),
    )
    
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='estimates')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='estimates')
    project = models.ForeignKey(Project, on_delete=models.SET_NULL, null=True, blank=True, related_name='estimates')
    job = models.ForeignKey(Job, on_delete=models.SET_NULL, null=True, blank=True, related_name='estimates')
    
    work_name = models.CharField(max_length=255)
    category = models.CharField(max_length=50, default="electrical")
    
    # Store complete workslip data as JSON
    estimate_data = models.JSONField(default=dict)  # Full estimate state
    total_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="draft")
    
    # Snapshot rates/catalogs at time of generation to prevent later changes affecting old estimates
    rate_snapshot = models.JSONField(default=dict, blank=True)  # Rates used at generation time
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    objects = EstimateManager()
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['organization', '-created_at']),
            models.Index(fields=['user', '-created_at']),
        ]
    
    def __str__(self):
        return f"{self.work_name} - {self.organization.name}"


class SelfFormattedTemplate(models.Model):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='templates', null=True, blank=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='templates', null=True, blank=True)
    
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    template_file = models.FileField(upload_to="self_formatted/%Y/%m/")

    # matches your views: dict of placeholders
    custom_placeholders = models.JSONField(default=dict, blank=True)
    
    is_shared = models.BooleanField(default=False)  # Can be shared across org

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        org = self.organization.name if self.organization else "Shared"
        return f"{self.name} ({org})"


class BackendWorkbook(models.Model):
    """
    Stores the backend Excel for each category (electrical / civil),
    uploaded via Django admin. Now supports multi-state SOR rates.
    
    DEPRECATED: Use datasets.SORRateBook for new state-based rate books.
    This model is kept for backward compatibility.
    """
    CATEGORY_CHOICES = (
        ("electrical", "Electrical"),
        ("civil", "Civil"),
        ("temp_electrical", "Temp Electrical"),
        ("temp_civil", "Temp Civil"),
        ("amc_electrical", "AMC Electrical"),
        ("amc_civil", "AMC Civil"),
    )
    
    category = models.CharField(max_length=30, choices=CATEGORY_CHOICES)
    file = models.FileField(upload_to="backend_excels/")
    uploaded_at = models.DateTimeField(auto_now_add=True)
    
    # New: State support for multi-state SOR rates
    state = models.ForeignKey(
        'datasets.State',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='legacy_workbooks',
        help_text="State this rate book applies to (leave blank for default/Telangana)"
    )
    
    # Metadata
    name = models.CharField(
        max_length=255,
        blank=True,
        help_text="Descriptive name like 'TS Electrical SOR 2024-25'"
    )
    financial_year = models.CharField(
        max_length=20,
        blank=True,
        help_text="Financial year like '2024-25'"
    )
    is_active = models.BooleanField(default=True)
    is_default = models.BooleanField(
        default=False,
        help_text="Use as default for this category when no state specified"
    )
    
    # Stats
    item_count = models.PositiveIntegerField(default=0)
    group_count = models.PositiveIntegerField(default=0)
    
    uploaded_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='uploaded_workbooks'
    )

    class Meta:
        ordering = ["-uploaded_at"]
        verbose_name = "Backend Workbook"
        verbose_name_plural = "Backend Workbooks"
        indexes = [
            models.Index(fields=['category', 'state', 'is_active']),
            models.Index(fields=['category', 'is_default']),
        ]

    def __str__(self):
        state_name = self.state.code if self.state else "Default"
        return f"{self.category} ({state_name}) - {self.uploaded_at:%Y-%m-%d %H:%M}"
    
    def save(self, *args, **kwargs):
        # Ensure only one default per category
        if self.is_default:
            BackendWorkbook.objects.filter(
                category=self.category,
                is_default=True
            ).exclude(pk=self.pk).update(is_default=False)
        super().save(*args, **kwargs)
    
    @classmethod
    def get_for_category_and_state(cls, category, state_code=None):
        """
        Get the appropriate workbook for a category and optional state.
        Falls back to default if state-specific not found.
        """
        if state_code:
            # Try to find state-specific workbook
            wb = cls.objects.filter(
                category=category,
                state__code=state_code,
                is_active=True
            ).order_by('-uploaded_at').first()
            if wb:
                return wb
        
        # Fall back to default (no state or is_default=True)
        return cls.objects.filter(
            category=category,
            is_active=True
        ).filter(
            models.Q(state__isnull=True) | models.Q(is_default=True)
        ).order_by('-is_default', '-uploaded_at').first()


class UserDocumentTemplate(models.Model):
    """
    User-specific document templates for Covering Letter and Movement Slip.
    Each user can upload their own templates with their officer names.
    """
    TEMPLATE_TYPE_CHOICES = (
        ("covering_letter", "Covering Letter"),
        ("movement_slip", "Movement Slip"),
    )
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='document_templates')
    template_type = models.CharField(max_length=20, choices=TEMPLATE_TYPE_CHOICES)
    name = models.CharField(max_length=255, help_text="A friendly name for this template")
    file = models.FileField(upload_to="user_templates/")
    is_active = models.BooleanField(default=True, help_text="Use this template for document generation")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ["-updated_at"]
        # Each user can have only one active template per type
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'template_type'],
                condition=models.Q(is_active=True),
                name='unique_active_template_per_user_type'
            )
        ]
        indexes = [
            models.Index(fields=['user', 'template_type', 'is_active']),
        ]
    
    def __str__(self):
        return f"{self.user.email} - {self.get_template_type_display()} - {self.name}"
    
    def save(self, *args, **kwargs):
        # If setting this as active, deactivate other templates of same type for this user
        if self.is_active:
            UserDocumentTemplate.objects.filter(
                user=self.user,
                template_type=self.template_type,
                is_active=True
            ).exclude(pk=self.pk).update(is_active=False)
        super().save(*args, **kwargs)


# ==============================================================================
# SAVED WORKS - Save and Resume Work Feature
# ==============================================================================

class WorkFolder(models.Model):
    """
    Folders for organizing saved works.
    Users can create hierarchical folders to organize their saved works.
    """
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='work_folders')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='work_folders')
    
    name = models.CharField(max_length=255)
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='children')
    description = models.TextField(blank=True)
    color = models.CharField(max_length=20, default='#6366f1')  # For folder icon color
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['name']
        unique_together = [['organization', 'user', 'name', 'parent']]
        indexes = [
            models.Index(fields=['organization', 'user']),
            models.Index(fields=['parent']),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.user.username})"
    
    def get_path(self):
        """Get full folder path like 'Parent/Child/Current'"""
        if self.parent:
            return f"{self.parent.get_path()}/{self.name}"
        return self.name
    
    def get_children_count(self):
        """Get number of child folders"""
        return self.children.count()
    
    def get_works_count(self):
        """Get number of saved works in this folder"""
        return self.saved_works.count()


class SavedWork(models.Model):
    """
    Saved work-in-progress for various modules.
    Allows users to save their work and resume from where they left off.
    
    Workflow Chain: Estimate → Workslip → Bill
    - An Estimate can generate a Workslip (parent = Estimate)
    - A Workslip can generate a Bill (parent = Workslip)
    """
    WORK_TYPE_CHOICES = (
        ("new_estimate", "New Estimate"),
        ("workslip", "Workslip"),
        ("bill", "Bill"),
        ("temporary_works", "Temporary Works"),
        ("amc", "AMC Module"),
    )
    
    STATUS_CHOICES = (
        ("in_progress", "In Progress"),
        ("completed", "Completed"),
        ("archived", "Archived"),
    )
    
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='saved_works')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='saved_works')
    folder = models.ForeignKey(WorkFolder, on_delete=models.SET_NULL, null=True, blank=True, related_name='saved_works')
    
    # Parent-child relationship for workflow chain (Estimate → Workslip → Bill)
    parent = models.ForeignKey(
        'self', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='children',
        help_text="Parent work this was generated from (e.g., Workslip from Estimate)"
    )
    
    # Work identification
    name = models.CharField(max_length=255, help_text="Custom name for this saved work")
    work_type = models.CharField(max_length=30, choices=WORK_TYPE_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="in_progress")
    
    # Work data - stores all session state as JSON
    work_data = models.JSONField(default=dict)
    
    # Additional metadata
    category = models.CharField(max_length=50, default="electrical")  # electrical/civil
    notes = models.TextField(blank=True, help_text="Optional notes about this work")
    
    # Workslip tracking - which workslip number this is (1, 2, 3, etc.)
    workslip_number = models.IntegerField(default=1, help_text="Workslip number for multi-workslip generation")
    
    # Progress tracking
    progress_percent = models.IntegerField(default=0)  # 0-100
    last_step = models.CharField(max_length=255, blank=True)  # Last step user was on
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-updated_at']
        indexes = [
            models.Index(fields=['organization', 'user', '-updated_at']),
            models.Index(fields=['work_type']),
            models.Index(fields=['folder']),
            models.Index(fields=['status']),
            models.Index(fields=['parent']),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.get_work_type_display()}) - {self.user.username}"
    
    def get_work_type_icon(self):
        """Return Bootstrap icon class for work type"""
        icons = {
            "new_estimate": "bi-file-earmark-spreadsheet",
            "workslip": "bi-file-earmark-text",
            "bill": "bi-receipt",
            "temporary_works": "bi-tools",
            "amc": "bi-calendar-check",
        }
        return icons.get(self.work_type, "bi-file-earmark")
    
    def get_work_type_color(self):
        """Return color class for work type"""
        colors = {
            "new_estimate": "primary",
            "workslip": "success",
            "bill": "danger",
            "temporary_works": "warning",
            "amc": "info",
        }
        return colors.get(self.work_type, "secondary")
    
    def get_resume_url(self):
        """Get URL to resume this work"""
        from django.urls import reverse
        return reverse('resume_saved_work', kwargs={'work_id': self.id})
    
    def can_generate_workslip(self):
        """Check if this work can generate a workslip (only Estimates can)"""
        return self.work_type == 'new_estimate'
    
    def can_generate_next_workslip(self):
        """Check if this work can generate the next workslip (only completed Workslips can)"""
        return self.work_type == 'workslip' and self.status == 'completed'
    
    def get_next_workslip_number(self):
        """Get the next workslip number to generate"""
        return self.workslip_number + 1 if self.work_type == 'workslip' else 1
    
    def can_generate_bill(self):
        """Check if this work can generate a bill (Estimates and Workslips can)"""
        return self.work_type in ['new_estimate', 'workslip']
    
    def get_children_by_type(self, work_type):
        """Get all child works of a specific type"""
        return self.children.filter(work_type=work_type)
    
    def get_workflow_chain(self):
        """Get the full workflow chain (parent → self → children)"""
        chain = []
        # Get all parents
        current = self.parent
        parents = []
        while current:
            parents.append(current)
            current = current.parent
        chain = list(reversed(parents))
        chain.append(self)
        # Add direct children
        chain.extend(list(self.children.all()))
        return chain
