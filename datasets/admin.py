# datasets/admin.py
"""
Admin configuration for datasets app.
Includes State management, SOR Rate Books, and Module Dataset Configurations.
"""

from django.contrib import admin
from django.utils import timezone
from django.utils.html import format_html
from datasets.models import (
    State, SORRateBook, DatasetCategory, Dataset, DatasetVersion,
    DatasetImportJob, ModuleDatasetConfig, UserStatePreference, AuditLog
)


# ==============================================================================
# STATE ADMIN
# ==============================================================================

@admin.register(State)
class StateAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'full_name', 'display_order', 'is_default', 'is_active', 'sor_count')
    list_filter = ('is_active', 'is_default')
    search_fields = ('name', 'code', 'full_name')
    list_editable = ('display_order', 'is_active', 'is_default')
    ordering = ('display_order', 'name')
    
    fieldsets = (
        ('Basic Info', {
            'fields': ('code', 'name', 'full_name')
        }),
        ('Display', {
            'fields': ('display_order', 'flag_icon')
        }),
        ('Status', {
            'fields': ('is_active', 'is_default')
        }),
    )
    
    def sor_count(self, obj):
        return obj.sor_rate_books.filter(is_active=True).count()
    sor_count.short_description = 'SOR Books'


# ==============================================================================
# SOR RATE BOOK ADMIN
# ==============================================================================

@admin.register(SORRateBook)
class SORRateBookAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'state', 'work_type', 'financial_year', 
                    'status_badge', 'is_default', 'file_size_display', 'total_items')
    list_filter = ('status', 'state', 'work_type', 'financial_year', 'is_active', 'is_default')
    search_fields = ('name', 'code', 'description')
    date_hierarchy = 'created_at'
    readonly_fields = ('id', 'file_size', 'total_items', 'total_groups', 
                       'created_at', 'updated_at', 'published_at')
    raw_id_fields = ('created_by', 'updated_by')
    list_editable = ('is_default',)
    
    fieldsets = (
        ('Basic Info', {
            'fields': ('id', 'code', 'name', 'description')
        }),
        ('State & Work Type', {
            'fields': ('state', 'work_type')
        }),
        ('Financial Year', {
            'fields': ('financial_year', 'year', 'effective_from', 'effective_until')
        }),
        ('File', {
            'fields': ('file', 'file_size')
        }),
        ('Statistics', {
            'fields': ('total_items', 'total_groups'),
            'classes': ('collapse',)
        }),
        ('Status', {
            'fields': ('status', 'is_active', 'is_default')
        }),
        ('Admin', {
            'fields': ('created_by', 'updated_by', 'created_at', 'updated_at', 'published_at'),
            'classes': ('collapse',)
        }),
    )
    
    def status_badge(self, obj):
        colors = {
            'draft': 'gray',
            'published': 'green',
            'archived': 'orange',
        }
        color = colors.get(obj.status, 'gray')
        return format_html(
            '<span style="background: {}; color: white; padding: 3px 8px; '
            'border-radius: 3px; font-size: 11px;">{}</span>',
            color, obj.status.upper()
        )
    status_badge.short_description = 'Status'
    
    def file_size_display(self, obj):
        return obj.get_file_size_display()
    file_size_display.short_description = 'Size'
    
    actions = ['publish_rate_books', 'archive_rate_books']
    
    @admin.action(description='Publish selected rate books')
    def publish_rate_books(self, request, queryset):
        for book in queryset:
            book.publish(request.user)
        self.message_user(request, f"Published {queryset.count()} rate books.")
    
    @admin.action(description='Archive selected rate books')
    def archive_rate_books(self, request, queryset):
        for book in queryset:
            book.archive(request.user)
        self.message_user(request, f"Archived {queryset.count()} rate books.")
    
    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)


# ==============================================================================
# MODULE DATASET CONFIG ADMIN
# ==============================================================================

@admin.register(ModuleDatasetConfig)
class ModuleDatasetConfigAdmin(admin.ModelAdmin):
    list_display = ('module_code', 'work_type', 'state', 'display_name', 
                    'sor_rate_book', 'is_default', 'is_active', 'has_file')
    list_filter = ('module_code', 'work_type', 'state', 'is_active', 'is_default')
    search_fields = ('module_code', 'display_name', 'description')
    list_editable = ('is_default', 'is_active')
    raw_id_fields = ('sor_rate_book', 'created_by', 'updated_by')
    ordering = ('module_code', 'work_type', 'state__display_order')
    
    fieldsets = (
        ('Module & Work Type', {
            'fields': ('module_code', 'work_type', 'state')
        }),
        ('Display', {
            'fields': ('display_name', 'description', 'display_order')
        }),
        ('Data Source (choose one)', {
            'fields': ('sor_rate_book', 'custom_file', 'legacy_workbook_id'),
            'description': 'Priority: custom_file > sor_rate_book > legacy_workbook'
        }),
        ('Status', {
            'fields': ('is_active', 'is_default')
        }),
        ('Admin', {
            'fields': ('created_by', 'updated_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    readonly_fields = ('created_at', 'updated_at')
    
    def has_file(self, obj):
        path = obj.get_file_path()
        if path:
            return format_html('<span style="color: green;">✓</span>')
        return format_html('<span style="color: red;">✗</span>')
    has_file.short_description = 'File'
    
    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)


# ==============================================================================
# USER STATE PREFERENCE ADMIN
# ==============================================================================

@admin.register(UserStatePreference)
class UserStatePreferenceAdmin(admin.ModelAdmin):
    list_display = ('user', 'preferred_state', 'module_states_display', 'updated_at')
    list_filter = ('preferred_state',)
    search_fields = ('user__username', 'user__email')
    raw_id_fields = ('user', 'preferred_state')
    readonly_fields = ('created_at', 'updated_at')
    
    def module_states_display(self, obj):
        if obj.module_states:
            states = ', '.join([f"{k}:{v}" for k, v in obj.module_states.items()])
            return states[:50] + '...' if len(states) > 50 else states
        return '-'
    module_states_display.short_description = 'Module States'


# ==============================================================================
# CATEGORY ADMIN
# ==============================================================================

@admin.register(DatasetCategory)
class DatasetCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'parent', 'dataset_count', 'display_order', 'is_active')
    list_filter = ('is_active', 'parent')
    search_fields = ('name', 'description')
    list_editable = ('display_order', 'is_active')
    prepopulated_fields = {'slug': ('name',)}
    
    def dataset_count(self, obj):
        return obj.get_dataset_count()
    dataset_count.short_description = 'Datasets'


# ==============================================================================
# DATASET ADMIN
# ==============================================================================

class DatasetVersionInline(admin.TabularInline):
    model = DatasetVersion
    extra = 0
    fields = ('version', 'status', 'record_count', 'file_size_display', 'created_at')
    readonly_fields = ('version', 'status', 'record_count', 'file_size_display', 'created_at')
    can_delete = False
    max_num = 0  # Don't allow adding inline
    
    def file_size_display(self, obj):
        return obj.get_file_size_display()
    file_size_display.short_description = 'Size'


@admin.register(Dataset)
class DatasetAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'category', 'state', 'year', 'status_badge', 
                    'record_count', 'version_count', 'is_premium')
    list_filter = ('status', 'category', 'state', 'year', 'is_premium', 'is_active')
    search_fields = ('name', 'code', 'description')
    date_hierarchy = 'created_at'
    readonly_fields = ('id', 'total_records', 'total_downloads', 'created_at', 
                       'updated_at', 'published_at')
    raw_id_fields = ('created_by', 'updated_by', 'current_version')
    inlines = [DatasetVersionInline]
    
    fieldsets = (
        ('Basic Info', {
            'fields': ('id', 'code', 'name', 'description', 'category')
        }),
        ('Metadata', {
            'fields': ('state', 'year', 'effective_from', 'effective_until')
        }),
        ('Status', {
            'fields': ('status', 'is_active', 'is_premium', 'current_version')
        }),
        ('Access Control', {
            'fields': ('allowed_modules',),
            'classes': ('collapse',)
        }),
        ('Statistics', {
            'fields': ('total_records', 'total_downloads'),
            'classes': ('collapse',)
        }),
        ('Admin', {
            'fields': ('created_by', 'updated_by', 'created_at', 'updated_at', 'published_at'),
            'classes': ('collapse',)
        }),
    )
    
    def status_badge(self, obj):
        colors = {
            'draft': 'gray',
            'published': 'green',
            'archived': 'orange',
        }
        color = colors.get(obj.status, 'gray')
        return format_html(
            '<span style="background: {}; color: white; padding: 3px 8px; '
            'border-radius: 3px; font-size: 11px;">{}</span>',
            color, obj.status.upper()
        )
    status_badge.short_description = 'Status'
    
    def record_count(self, obj):
        return f"{obj.total_records:,}"
    record_count.short_description = 'Records'
    
    def version_count(self, obj):
        return obj.get_version_count()
    version_count.short_description = 'Versions'
    
    actions = ['publish_datasets', 'archive_datasets']
    
    @admin.action(description='Publish selected datasets')
    def publish_datasets(self, request, queryset):
        for dataset in queryset:
            dataset.publish(request.user)
        self.message_user(request, f"Published {queryset.count()} datasets.")
    
    @admin.action(description='Archive selected datasets')
    def archive_datasets(self, request, queryset):
        for dataset in queryset:
            dataset.archive(request.user)
        self.message_user(request, f"Archived {queryset.count()} datasets.")
    
    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)


# ==============================================================================
# VERSION ADMIN
# ==============================================================================

@admin.register(DatasetVersion)
class DatasetVersionAdmin(admin.ModelAdmin):
    list_display = ('dataset', 'version', 'status_badge', 'record_count', 
                    'file_size_display', 'uploaded_by', 'created_at')
    list_filter = ('status', 'dataset__category', 'created_at')
    search_fields = ('dataset__name', 'dataset__code', 'version')
    date_hierarchy = 'created_at'
    readonly_fields = ('id', 'file_size', 'file_hash', 'record_count', 
                       'created_at', 'processed_at')
    raw_id_fields = ('dataset', 'uploaded_by')
    
    fieldsets = (
        ('Version Info', {
            'fields': ('id', 'dataset', 'version', 'changelog')
        }),
        ('File', {
            'fields': ('file', 'file_size', 'file_hash')
        }),
        ('Processing', {
            'fields': ('status', 'record_count', 'error_message')
        }),
        ('Data', {
            'fields': ('column_mapping',),
            'classes': ('collapse',)
        }),
        ('Admin', {
            'fields': ('uploaded_by', 'created_at', 'processed_at'),
            'classes': ('collapse',)
        }),
    )
    
    def status_badge(self, obj):
        colors = {
            'uploading': 'blue',
            'processing': 'orange',
            'ready': 'green',
            'failed': 'red',
        }
        color = colors.get(obj.status, 'gray')
        return format_html(
            '<span style="background: {}; color: white; padding: 3px 8px; '
            'border-radius: 3px; font-size: 11px;">{}</span>',
            color, obj.status.upper()
        )
    status_badge.short_description = 'Status'
    
    def file_size_display(self, obj):
        return obj.get_file_size_display()
    file_size_display.short_description = 'Size'
    
    def save_model(self, request, obj, form, change):
        if not change:
            obj.uploaded_by = request.user
        super().save_model(request, obj, form, change)


# ==============================================================================
# IMPORT JOB ADMIN
# ==============================================================================

@admin.register(DatasetImportJob)
class DatasetImportJobAdmin(admin.ModelAdmin):
    list_display = ('dataset_version', 'status_badge', 'progress_display', 
                    'started_by', 'duration', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('dataset_version__dataset__name', 'task_id')
    date_hierarchy = 'created_at'
    readonly_fields = ('id', 'total_rows', 'processed_rows', 'failed_rows',
                       'task_id', 'created_at', 'started_at', 'completed_at')
    raw_id_fields = ('dataset_version', 'started_by')
    
    def status_badge(self, obj):
        colors = {
            'pending': 'gray',
            'running': 'blue',
            'completed': 'green',
            'failed': 'red',
            'cancelled': 'orange',
        }
        color = colors.get(obj.status, 'gray')
        return format_html(
            '<span style="background: {}; color: white; padding: 3px 8px; '
            'border-radius: 3px; font-size: 11px;">{}</span>',
            color, obj.status.upper()
        )
    status_badge.short_description = 'Status'
    
    def progress_display(self, obj):
        return format_html(
            '<progress value="{}" max="100" style="width: 100px;"></progress> {}%',
            obj.progress_percent, obj.progress_percent
        )
    progress_display.short_description = 'Progress'
    
    def duration(self, obj):
        if obj.started_at and obj.completed_at:
            delta = obj.completed_at - obj.started_at
            return f"{delta.seconds}s"
        elif obj.started_at:
            delta = timezone.now() - obj.started_at
            return f"{delta.seconds}s (running)"
        return '-'
    duration.short_description = 'Duration'


# ==============================================================================
# AUDIT LOG ADMIN
# ==============================================================================

@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ('created_at', 'user_email', 'action_badge', 'model_name', 
                    'object_repr', 'ip_address')
    list_filter = ('action', 'model_name', 'created_at')
    search_fields = ('user_email', 'object_repr', 'object_id', 'ip_address')
    date_hierarchy = 'created_at'
    readonly_fields = ('user', 'user_email', 'action', 'model_name', 'object_id',
                       'object_repr', 'changes', 'metadata', 'ip_address', 
                       'user_agent', 'created_at')
    
    def action_badge(self, obj):
        colors = {
            'create': 'green',
            'update': 'blue',
            'delete': 'red',
            'publish': 'purple',
            'archive': 'orange',
            'upload': 'teal',
            'download': 'gray',
            'import': 'indigo',
            'export': 'cyan',
            'access': 'gray',
        }
        color = colors.get(obj.action, 'gray')
        return format_html(
            '<span style="background: {}; color: white; padding: 3px 8px; '
            'border-radius: 3px; font-size: 11px;">{}</span>',
            color, obj.action.upper()
        )
    action_badge.short_description = 'Action'
    
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False
    
    def has_delete_permission(self, request, obj=None):
        return False
