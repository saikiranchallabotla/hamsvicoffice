from django.contrib import admin
from .models import (
    Organization, Membership, Upload, Job, OutputFile,
    Project, Estimate, SelfFormattedTemplate, BackendWorkbook, UserProfile,
    SavedWork, WorkFolder
)


# ==============================================================================
# MULTI-TENANCY ADMIN
# ==============================================================================

@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "plan", "owner", "is_active", "created_at")
    list_filter = ("plan", "is_active", "created_at")
    search_fields = ("name", "slug", "owner__username")
    readonly_fields = ("created_at", "updated_at")
    ordering = ("-created_at",)


@admin.register(Membership)
class MembershipAdmin(admin.ModelAdmin):
    list_display = ("user", "organization", "role", "joined_at")
    list_filter = ("role", "organization", "joined_at")
    search_fields = ("user__username", "organization__name")
    readonly_fields = ("joined_at",)
    ordering = ("-joined_at",)


# ==============================================================================
# UPLOAD & JOB PROCESSING ADMIN
# ==============================================================================

@admin.register(Upload)
class UploadAdmin(admin.ModelAdmin):
    list_display = ("filename", "organization", "user", "status", "file_size", "created_at")
    list_filter = ("status", "created_at", "organization")
    search_fields = ("filename", "organization__name", "user__username")
    readonly_fields = ("created_at", "updated_at", "file_size")
    ordering = ("-created_at",)


@admin.register(Job)
class JobAdmin(admin.ModelAdmin):
    list_display = ("job_type", "organization", "user", "status", "progress", "created_at", "completed_at")
    list_filter = ("job_type", "status", "created_at", "organization")
    search_fields = ("organization__name", "user__username", "celery_task_id")
    readonly_fields = ("celery_task_id", "created_at", "started_at", "completed_at")
    fieldsets = (
        ('Job Info', {
            'fields': ('organization', 'user', 'upload', 'job_type', 'status', 'celery_task_id')
        }),
        ('Progress', {
            'fields': ('progress', 'current_step')
        }),
        ('Results', {
            'fields': ('result', 'error_message', 'error_log')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'started_at', 'completed_at'),
            'classes': ('collapse',)
        }),
    )
    ordering = ("-created_at",)


@admin.register(OutputFile)
class OutputFileAdmin(admin.ModelAdmin):
    list_display = ("filename", "organization", "job", "file_type", "file_size", "download_count", "created_at")
    list_filter = ("file_type", "created_at", "organization")
    search_fields = ("filename", "organization__name", "job__id")
    readonly_fields = ("created_at", "last_downloaded")
    ordering = ("-created_at",)


# ==============================================================================
# PROJECT & ESTIMATE ADMIN
# ==============================================================================

@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ("name", "organization", "category", "created_at")
    list_filter = ("category", "organization", "created_at")
    search_fields = ("name", "organization__name")
    readonly_fields = ("created_at", "updated_at")
    ordering = ("-created_at",)


@admin.register(Estimate)
class EstimateAdmin(admin.ModelAdmin):
    list_display = ("work_name", "organization", "user", "category", "status", "total_amount", "created_at")
    list_filter = ("status", "category", "organization", "created_at")
    search_fields = ("work_name", "organization__name", "user__username")
    readonly_fields = ("created_at", "updated_at")
    fieldsets = (
        ('Estimate Info', {
            'fields': ('organization', 'user', 'project', 'job', 'work_name', 'category', 'status')
        }),
        ('Data', {
            'fields': ('estimate_data', 'total_amount', 'rate_snapshot')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    ordering = ("-created_at",)


@admin.register(SelfFormattedTemplate)
class SelfFormattedTemplateAdmin(admin.ModelAdmin):
    list_display = ("name", "organization", "is_shared", "created_at", "updated_at")
    list_filter = ("is_shared", "organization", "created_at")
    search_fields = ("name", "organization__name")
    readonly_fields = ("created_at", "updated_at")
    ordering = ("-created_at",)


@admin.register(BackendWorkbook)
class BackendWorkbookAdmin(admin.ModelAdmin):
    list_display = ("category", "state", "name", "financial_year", "is_default", "is_active", "uploaded_at")
    list_filter = ("category", "state", "is_active", "is_default")
    list_editable = ("is_default", "is_active")
    search_fields = ("name", "category")
    ordering = ("-uploaded_at",)
    raw_id_fields = ("state", "uploaded_by")
    
    fieldsets = (
        ('Category & State', {
            'fields': ('category', 'state')
        }),
        ('Details', {
            'fields': ('name', 'financial_year', 'file')
        }),
        ('Status', {
            'fields': ('is_active', 'is_default')
        }),
        ('Statistics', {
            'fields': ('item_count', 'group_count'),
            'classes': ('collapse',)
        }),
        ('Admin', {
            'fields': ('uploaded_by', 'uploaded_at'),
            'classes': ('collapse',)
        }),
    )
    readonly_fields = ('uploaded_at', 'item_count', 'group_count')
    
    def save_model(self, request, obj, form, change):
        if not change and not obj.uploaded_by:
            obj.uploaded_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "company_name", "subscription_tier", "estimates_created", "estimates_limit")
    list_filter = ("subscription_tier", "created_at")
    search_fields = ("user__username", "company_name")
    readonly_fields = ("created_at", "updated_at")
    ordering = ("-created_at",)


# ==============================================================================
# SAVED WORKS ADMIN
# ==============================================================================

@admin.register(WorkFolder)
class WorkFolderAdmin(admin.ModelAdmin):
    list_display = ("name", "organization", "user", "parent", "color", "created_at")
    list_filter = ("organization", "created_at")
    search_fields = ("name", "organization__name", "user__username")
    readonly_fields = ("created_at", "updated_at")
    ordering = ("name",)


@admin.register(SavedWork)
class SavedWorkAdmin(admin.ModelAdmin):
    list_display = ("name", "work_type", "organization", "user", "folder", "status", "progress_percent", "updated_at")
    list_filter = ("work_type", "status", "organization", "created_at")
    search_fields = ("name", "organization__name", "user__username")
    readonly_fields = ("created_at", "updated_at")
    fieldsets = (
        ('Work Info', {
            'fields': ('organization', 'user', 'folder', 'name', 'work_type', 'category', 'status')
        }),
        ('Progress', {
            'fields': ('progress_percent', 'last_step', 'notes')
        }),
        ('Data', {
            'fields': ('work_data',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    ordering = ("-updated_at",)
