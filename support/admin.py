# support/admin.py
"""
Admin configuration for support app.
"""

from django.contrib import admin
from django.utils.html import format_html
from django.utils import timezone
from support.models import (
    FAQCategory, FAQItem, HelpGuide,
    SupportTicket, TicketMessage,
    Announcement, UserDismissedAnnouncement
)


# ==============================================================================
# FAQ ADMIN
# ==============================================================================

@admin.register(FAQCategory)
class FAQCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'faq_count', 'display_order', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('name', 'description')
    list_editable = ('display_order', 'is_active')
    prepopulated_fields = {'slug': ('name',)}
    
    def faq_count(self, obj):
        return obj.get_faq_count()
    faq_count.short_description = 'FAQs'


@admin.register(FAQItem)
class FAQItemAdmin(admin.ModelAdmin):
    list_display = ('question_short', 'category', 'view_count', 'helpfulness', 
                    'is_published', 'is_featured', 'display_order')
    list_filter = ('category', 'is_published', 'is_featured')
    search_fields = ('question', 'answer', 'keywords')
    list_editable = ('display_order', 'is_published', 'is_featured')
    prepopulated_fields = {'slug': ('question',)}
    
    fieldsets = (
        ('Content', {
            'fields': ('category', 'question', 'answer', 'slug')
        }),
        ('SEO', {
            'fields': ('keywords',),
            'classes': ('collapse',)
        }),
        ('Display', {
            'fields': ('display_order', 'is_published', 'is_featured')
        }),
        ('Stats', {
            'fields': ('view_count', 'helpful_count', 'not_helpful_count'),
            'classes': ('collapse',)
        }),
    )
    
    def question_short(self, obj):
        return obj.question[:80] + '...' if len(obj.question) > 80 else obj.question
    question_short.short_description = 'Question'
    
    def helpfulness(self, obj):
        score = obj.helpfulness_score
        if score >= 70:
            color = 'green'
        elif score >= 40:
            color = 'orange'
        else:
            color = 'red'
        return format_html(
            '<span style="color: {};">{:.0f}%</span>',
            color, score
        )
    helpfulness.short_description = 'Helpful'


# ==============================================================================
# HELP GUIDE ADMIN
# ==============================================================================

@admin.register(HelpGuide)
class HelpGuideAdmin(admin.ModelAdmin):
    list_display = ('title', 'content_type', 'category', 'view_count', 
                    'is_published', 'is_featured', 'published_at')
    list_filter = ('content_type', 'category', 'is_published', 'is_featured')
    search_fields = ('title', 'excerpt', 'content', 'tags')
    list_editable = ('is_published', 'is_featured')
    prepopulated_fields = {'slug': ('title',)}
    raw_id_fields = ('author',)
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Basic Info', {
            'fields': ('title', 'slug', 'excerpt', 'content_type')
        }),
        ('Content', {
            'fields': ('content', 'featured_image', 'video_url')
        }),
        ('Categorization', {
            'fields': ('category', 'related_module', 'tags')
        }),
        ('Status', {
            'fields': ('is_published', 'is_featured', 'author')
        }),
        ('Stats', {
            'fields': ('view_count', 'published_at'),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['publish_guides']
    
    @admin.action(description='Publish selected guides')
    def publish_guides(self, request, queryset):
        for guide in queryset:
            guide.publish()
        self.message_user(request, f"Published {queryset.count()} guides.")
    
    def save_model(self, request, obj, form, change):
        if not change:
            obj.author = request.user
        super().save_model(request, obj, form, change)


# ==============================================================================
# SUPPORT TICKET ADMIN
# ==============================================================================

class TicketMessageInline(admin.TabularInline):
    model = TicketMessage
    extra = 1
    fields = ('sender', 'message', 'is_admin_reply', 'is_internal', 'created_at')
    readonly_fields = ('created_at',)
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('sender')


@admin.register(SupportTicket)
class SupportTicketAdmin(admin.ModelAdmin):
    list_display = ('ticket_number', 'subject_short', 'user', 'category', 
                    'priority_badge', 'status_badge', 'assigned_to', 
                    'message_count', 'created_at')
    list_filter = ('status', 'priority', 'category', 'assigned_to', 'created_at')
    search_fields = ('ticket_number', 'subject', 'description', 
                     'user__username', 'user__email')
    date_hierarchy = 'created_at'
    readonly_fields = ('id', 'ticket_number', 'created_at', 'updated_at', 
                       'first_response_at', 'resolved_at')
    raw_id_fields = ('user', 'assigned_to', 'resolved_by')
    inlines = [TicketMessageInline]
    
    fieldsets = (
        ('Ticket Info', {
            'fields': ('id', 'ticket_number', 'user', 'subject', 'description')
        }),
        ('Classification', {
            'fields': ('category', 'priority', 'status')
        }),
        ('Assignment', {
            'fields': ('assigned_to',)
        }),
        ('Related', {
            'fields': ('related_module', 'related_payment_id', 'attachments'),
            'classes': ('collapse',)
        }),
        ('Resolution', {
            'fields': ('resolution_notes', 'resolved_by', 'resolved_at'),
            'classes': ('collapse',)
        }),
        ('Satisfaction', {
            'fields': ('satisfaction_rating', 'satisfaction_feedback'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at', 'first_response_at'),
            'classes': ('collapse',)
        }),
    )
    
    def subject_short(self, obj):
        return obj.subject[:50] + '...' if len(obj.subject) > 50 else obj.subject
    subject_short.short_description = 'Subject'
    
    def priority_badge(self, obj):
        colors = {
            'low': 'gray',
            'medium': 'blue',
            'high': 'orange',
            'urgent': 'red',
        }
        color = colors.get(obj.priority, 'gray')
        return format_html(
            '<span style="background: {}; color: white; padding: 3px 8px; '
            'border-radius: 3px; font-size: 11px;">{}</span>',
            color, obj.priority.upper()
        )
    priority_badge.short_description = 'Priority'
    
    def status_badge(self, obj):
        colors = {
            'open': 'green',
            'in_progress': 'blue',
            'waiting_user': 'orange',
            'waiting_admin': 'purple',
            'resolved': 'teal',
            'closed': 'gray',
        }
        color = colors.get(obj.status, 'gray')
        return format_html(
            '<span style="background: {}; color: white; padding: 3px 8px; '
            'border-radius: 3px; font-size: 11px;">{}</span>',
            color, obj.get_status_display()
        )
    status_badge.short_description = 'Status'
    
    def message_count(self, obj):
        return obj.get_message_count()
    message_count.short_description = 'Messages'
    
    actions = ['assign_to_me', 'mark_resolved', 'close_tickets']
    
    @admin.action(description='Assign to me')
    def assign_to_me(self, request, queryset):
        for ticket in queryset:
            ticket.assign(request.user)
        self.message_user(request, f"Assigned {queryset.count()} tickets to you.")
    
    @admin.action(description='Mark as resolved')
    def mark_resolved(self, request, queryset):
        for ticket in queryset:
            ticket.resolve(request.user)
        self.message_user(request, f"Resolved {queryset.count()} tickets.")
    
    @admin.action(description='Close tickets')
    def close_tickets(self, request, queryset):
        for ticket in queryset:
            ticket.close()
        self.message_user(request, f"Closed {queryset.count()} tickets.")


@admin.register(TicketMessage)
class TicketMessageAdmin(admin.ModelAdmin):
    list_display = ('ticket', 'sender', 'is_admin_reply', 'is_internal', 
                    'message_short', 'created_at')
    list_filter = ('is_admin_reply', 'is_internal', 'created_at')
    search_fields = ('ticket__ticket_number', 'message', 'sender__username')
    date_hierarchy = 'created_at'
    raw_id_fields = ('ticket', 'sender')
    
    def message_short(self, obj):
        return obj.message[:100] + '...' if len(obj.message) > 100 else obj.message
    message_short.short_description = 'Message'


# ==============================================================================
# ANNOUNCEMENT ADMIN
# ==============================================================================

@admin.register(Announcement)
class AnnouncementAdmin(admin.ModelAdmin):
    list_display = ('title', 'type_badge', 'target_audience', 'is_banner',
                    'is_visible_now', 'view_count', 'dismiss_count', 
                    'starts_at', 'ends_at')
    list_filter = ('announcement_type', 'target_audience', 'is_active', 
                   'is_banner', 'is_dismissible')
    search_fields = ('title', 'message')
    list_editable = ('is_banner',)
    date_hierarchy = 'starts_at'
    raw_id_fields = ('created_by',)
    
    fieldsets = (
        ('Content', {
            'fields': ('title', 'message', 'announcement_type')
        }),
        ('Targeting', {
            'fields': ('target_audience', 'target_modules')
        }),
        ('Display', {
            'fields': ('is_banner', 'is_dismissible', 'link_url', 'link_text')
        }),
        ('Schedule', {
            'fields': ('is_active', 'starts_at', 'ends_at')
        }),
        ('Stats', {
            'fields': ('view_count', 'dismiss_count', 'created_by'),
            'classes': ('collapse',)
        }),
    )
    
    def type_badge(self, obj):
        colors = {
            'info': 'blue',
            'success': 'green',
            'warning': 'orange',
            'danger': 'red',
            'maintenance': 'purple',
            'feature': 'teal',
        }
        color = colors.get(obj.announcement_type, 'gray')
        return format_html(
            '<span style="background: {}; color: white; padding: 3px 8px; '
            'border-radius: 3px; font-size: 11px;">{}</span>',
            color, obj.announcement_type.upper()
        )
    type_badge.short_description = 'Type'
    
    def is_visible_now(self, obj):
        return obj.is_visible()
    is_visible_now.boolean = True
    is_visible_now.short_description = 'Visible'
    
    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(UserDismissedAnnouncement)
class UserDismissedAnnouncementAdmin(admin.ModelAdmin):
    list_display = ('user', 'announcement', 'dismissed_at')
    list_filter = ('dismissed_at',)
    search_fields = ('user__username', 'announcement__title')
    raw_id_fields = ('user', 'announcement')
