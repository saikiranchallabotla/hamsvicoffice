# support/models.py
"""
Help center, FAQs, support tickets, and announcements.

Models:
- FAQCategory: Categories for organizing FAQs
- FAQItem: Individual FAQ entries
- HelpGuide: Detailed help articles/tutorials
- SupportTicket: User support requests
- TicketMessage: Messages within a ticket
- Announcement: System-wide announcements
"""

import uuid
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.utils.text import slugify


# ==============================================================================
# FAQ MODELS
# ==============================================================================

class FAQCategory(models.Model):
    """
    Categories for organizing FAQs.
    Examples: Getting Started, Billing, Estimates, Technical Issues
    """
    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    
    # Display
    icon = models.CharField(max_length=50, blank=True, help_text="Icon class or emoji")
    color = models.CharField(max_length=20, default='#3B82F6')
    display_order = models.PositiveIntegerField(default=0)
    
    # Status
    is_active = models.BooleanField(default=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'FAQ Category'
        verbose_name_plural = 'FAQ Categories'
        ordering = ['display_order', 'name']
    
    def __str__(self):
        return self.name
    
    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)
    
    def get_faq_count(self):
        return self.faqs.filter(is_published=True).count()


class FAQItem(models.Model):
    """
    Individual FAQ entries with question and answer.
    """
    category = models.ForeignKey(
        FAQCategory,
        on_delete=models.CASCADE,
        related_name='faqs'
    )
    
    # Content
    question = models.CharField(max_length=500)
    answer = models.TextField(help_text="Supports Markdown")
    
    # SEO & Search
    slug = models.SlugField(max_length=200, unique=True)
    keywords = models.CharField(
        max_length=500,
        blank=True,
        help_text="Comma-separated keywords for search"
    )
    
    # Display
    display_order = models.PositiveIntegerField(default=0)
    
    # Stats
    view_count = models.PositiveIntegerField(default=0)
    helpful_count = models.PositiveIntegerField(default=0)
    not_helpful_count = models.PositiveIntegerField(default=0)
    
    # Status
    is_published = models.BooleanField(default=True)
    is_featured = models.BooleanField(default=False, help_text="Show on help homepage")
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['category', 'display_order', '-created_at']
        indexes = [
            models.Index(fields=['category', 'is_published']),
            models.Index(fields=['is_featured', 'is_published']),
        ]
    
    def __str__(self):
        return self.question[:100]
    
    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.question[:180])
        super().save(*args, **kwargs)
    
    def record_view(self):
        from django.db.models import F
        type(self).objects.filter(pk=self.pk).update(view_count=F('view_count') + 1)

    def record_helpful(self, is_helpful=True):
        from django.db.models import F
        if is_helpful:
            type(self).objects.filter(pk=self.pk).update(helpful_count=F('helpful_count') + 1)
        else:
            type(self).objects.filter(pk=self.pk).update(not_helpful_count=F('not_helpful_count') + 1)
    @property
    def helpfulness_score(self):
        total = self.helpful_count + self.not_helpful_count
        if total > 0:
            return int((self.helpful_count / total) * 100)
        return 0


# ==============================================================================
# HELP GUIDES
# ==============================================================================

class HelpGuide(models.Model):
    """
    Detailed help articles and tutorials.
    Longer-form content than FAQs.
    """
    CONTENT_TYPE_CHOICES = (
        ('article', 'Article'),
        ('tutorial', 'Tutorial'),
        ('video', 'Video'),
        ('release_notes', 'Release Notes'),
    )
    
    # Basic info
    title = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, unique=True)
    excerpt = models.TextField(
        max_length=500,
        blank=True,
        help_text="Short summary for listings"
    )
    
    # Content
    content = models.TextField(help_text="Supports Markdown")
    content_type = models.CharField(
        max_length=20,
        choices=CONTENT_TYPE_CHOICES,
        default='article'
    )
    
    # Media
    featured_image = models.ImageField(
        upload_to='help/images/',
        blank=True,
        null=True
    )
    video_url = models.URLField(blank=True, help_text="YouTube or Vimeo URL")
    
    # Categorization
    category = models.ForeignKey(
        FAQCategory,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='guides'
    )
    related_module = models.CharField(
        max_length=50,
        blank=True,
        help_text="Module code this guide relates to"
    )
    tags = models.CharField(
        max_length=500,
        blank=True,
        help_text="Comma-separated tags"
    )
    
    # Stats
    view_count = models.PositiveIntegerField(default=0)
    
    # Status
    is_published = models.BooleanField(default=False)
    is_featured = models.BooleanField(default=False)
    
    # Admin
    author = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='help_guides'
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    published_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-published_at', '-created_at']
        indexes = [
            models.Index(fields=['is_published', 'content_type']),
            models.Index(fields=['related_module', 'is_published']),
        ]
    
    def __str__(self):
        return self.title
    
    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
        super().save(*args, **kwargs)
    
    def publish(self):
        self.is_published = True
        self.published_at = timezone.now()
        self.save()
    
    def record_view(self):
        from django.db.models import F
        type(self).objects.filter(pk=self.pk).update(view_count=F('view_count') + 1)
    
    def get_tags_list(self):
        if self.tags:
            return [t.strip() for t in self.tags.split(',')]
        return []


# ==============================================================================
# SUPPORT TICKETS
# ==============================================================================

class SupportTicket(models.Model):
    """
    User support requests with conversation thread.
    """
    STATUS_CHOICES = (
        ('open', 'Open'),
        ('in_progress', 'In Progress'),
        ('waiting_user', 'Waiting for User'),
        ('waiting_admin', 'Waiting for Admin'),
        ('resolved', 'Resolved'),
        ('closed', 'Closed'),
    )
    
    PRIORITY_CHOICES = (
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('urgent', 'Urgent'),
    )
    
    CATEGORY_CHOICES = (
        ('general', 'General Inquiry'),
        ('billing', 'Billing & Payments'),
        ('technical', 'Technical Issue'),
        ('bug', 'Bug Report'),
        ('feature', 'Feature Request'),
        ('account', 'Account Issue'),
        ('data', 'Data/SSR Issue'),
    )
    
    # Identifiers
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    ticket_number = models.CharField(
        max_length=20,
        unique=True,
        db_index=True
    )
    
    # User
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='support_tickets'
    )
    
    # Ticket details
    subject = models.CharField(max_length=255)
    description = models.TextField()
    category = models.CharField(
        max_length=20,
        choices=CATEGORY_CHOICES,
        default='general'
    )
    priority = models.CharField(
        max_length=10,
        choices=PRIORITY_CHOICES,
        default='medium'
    )
    
    # Status
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='open',
        db_index=True
    )
    
    # Assignment
    assigned_to = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_tickets'
    )
    
    # Attachments
    attachments = models.JSONField(
        default=list,
        blank=True,
        help_text="List of attachment file paths"
    )
    
    # Related entities
    related_module = models.CharField(max_length=50, blank=True)
    related_payment_id = models.CharField(max_length=100, blank=True)
    
    # Resolution
    resolution_notes = models.TextField(blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='resolved_tickets'
    )
    
    # Satisfaction
    satisfaction_rating = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="1-5 rating"
    )
    satisfaction_feedback = models.TextField(blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    first_response_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'status']),
            models.Index(fields=['status', 'priority']),
            models.Index(fields=['assigned_to', 'status']),
            models.Index(fields=['ticket_number']),
        ]
    
    def __str__(self):
        return f"{self.ticket_number}: {self.subject[:50]}"
    
    def save(self, *args, **kwargs):
        if not self.ticket_number:
            self.ticket_number = self.generate_ticket_number()
        super().save(*args, **kwargs)
    
    @classmethod
    def generate_ticket_number(cls):
        """Generate unique ticket number like TKT-202601-00001"""
        prefix = timezone.now().strftime('TKT-%Y%m')
        last_ticket = cls.objects.filter(
            ticket_number__startswith=prefix
        ).order_by('-ticket_number').first()
        
        if last_ticket:
            try:
                last_num = int(last_ticket.ticket_number.split('-')[-1])
                next_num = last_num + 1
            except ValueError:
                next_num = 1
        else:
            next_num = 1
        
        return f"{prefix}-{next_num:05d}"
    
    def assign(self, admin_user):
        """Assign ticket to admin"""
        self.assigned_to = admin_user
        self.status = 'in_progress'
        self.save()
    
    def resolve(self, admin_user, notes=''):
        """Mark ticket as resolved"""
        self.status = 'resolved'
        self.resolved_at = timezone.now()
        self.resolved_by = admin_user
        self.resolution_notes = notes
        self.save()
    
    def close(self):
        """Close the ticket"""
        self.status = 'closed'
        self.save()
    
    def reopen(self):
        """Reopen a closed ticket"""
        self.status = 'open'
        self.resolved_at = None
        self.save()
    
    def get_message_count(self):
        return self.messages.count()
    
    def get_response_time(self):
        """Get first response time in hours"""
        if self.first_response_at:
            delta = self.first_response_at - self.created_at
            return round(delta.total_seconds() / 3600, 1)
        return None


class TicketMessage(models.Model):
    """
    Messages within a support ticket thread.
    """
    ticket = models.ForeignKey(
        SupportTicket,
        on_delete=models.CASCADE,
        related_name='messages'
    )
    
    # Sender
    sender = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='ticket_messages'
    )
    is_admin_reply = models.BooleanField(default=False)
    
    # Content
    message = models.TextField()
    
    # Attachments
    attachments = models.JSONField(
        default=list,
        blank=True,
        help_text="List of attachment file paths"
    )
    
    # Status
    is_internal = models.BooleanField(
        default=False,
        help_text="Internal note (not visible to user)"
    )
    is_read = models.BooleanField(default=False)
    
    # Timestamp
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['created_at']
        indexes = [
            models.Index(fields=['ticket', 'created_at']),
        ]
    
    def __str__(self):
        sender_name = self.sender.get_full_name() if self.sender else 'System'
        return f"Message from {sender_name} on {self.ticket.ticket_number}"
    
    def save(self, *args, **kwargs):
        is_new = self._state.adding
        super().save(*args, **kwargs)
        
        # Update first response time
        if is_new and self.is_admin_reply and not self.ticket.first_response_at:
            self.ticket.first_response_at = self.created_at
            self.ticket.save(update_fields=['first_response_at'])


# ==============================================================================
# ANNOUNCEMENTS
# ==============================================================================

class Announcement(models.Model):
    """
    System-wide announcements shown to users.
    """
    TYPE_CHOICES = (
        ('info', 'Information'),
        ('success', 'Success'),
        ('warning', 'Warning'),
        ('danger', 'Critical'),
        ('maintenance', 'Maintenance'),
        ('feature', 'New Feature'),
    )
    
    TARGET_CHOICES = (
        ('all', 'All Users'),
        ('free', 'Free Users Only'),
        ('paid', 'Paid Users Only'),
        ('admin', 'Admins Only'),
    )
    
    # Content
    title = models.CharField(max_length=255)
    message = models.TextField(help_text="Supports Markdown")
    
    # Type & styling
    announcement_type = models.CharField(
        max_length=20,
        choices=TYPE_CHOICES,
        default='info'
    )
    
    # Targeting
    target_audience = models.CharField(
        max_length=20,
        choices=TARGET_CHOICES,
        default='all'
    )
    target_modules = models.JSONField(
        default=list,
        blank=True,
        help_text="Show only for specific modules (empty = all)"
    )
    
    # Display
    is_dismissible = models.BooleanField(default=True)
    is_banner = models.BooleanField(
        default=False,
        help_text="Show as top banner (vs modal/toast)"
    )
    link_url = models.URLField(blank=True, help_text="Learn more link")
    link_text = models.CharField(max_length=100, blank=True, default='Learn More')
    
    # Scheduling
    is_active = models.BooleanField(default=True)
    starts_at = models.DateTimeField(default=timezone.now)
    ends_at = models.DateTimeField(null=True, blank=True)
    
    # Stats
    view_count = models.PositiveIntegerField(default=0)
    dismiss_count = models.PositiveIntegerField(default=0)
    
    # Admin
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_announcements'
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-starts_at']
        indexes = [
            models.Index(fields=['is_active', 'starts_at', 'ends_at']),
            models.Index(fields=['target_audience', 'is_active']),
        ]
    
    def __str__(self):
        return f"[{self.announcement_type.upper()}] {self.title}"
    
    def is_visible(self):
        """Check if announcement should be shown now"""
        if not self.is_active:
            return False
        
        now = timezone.now()
        if now < self.starts_at:
            return False
        
        if self.ends_at and now > self.ends_at:
            return False
        
        return True
    
    def record_view(self):
        from django.db.models import F
        type(self).objects.filter(pk=self.pk).update(view_count=F('view_count') + 1)

    def record_dismiss(self):
        from django.db.models import F
        type(self).objects.filter(pk=self.pk).update(dismiss_count=F('dismiss_count') + 1)

    @classmethod
    def get_active(cls, user=None, module_code=None):
        """Get active announcements for a user/module"""
        now = timezone.now()
        qs = cls.objects.filter(
            is_active=True,
            starts_at__lte=now
        ).filter(
            models.Q(ends_at__isnull=True) | models.Q(ends_at__gte=now)
        )
        
        # Filter by target audience
        if user:
            if user.is_staff:
                pass  # Staff sees all
            elif hasattr(user, 'module_subscriptions') and \
                 user.module_subscriptions.filter(status='active').exists():
                qs = qs.exclude(target_audience='free')
            else:
                qs = qs.exclude(target_audience='paid')
                qs = qs.exclude(target_audience='admin')
        
        # Filter by module
        if module_code:
            qs = qs.filter(
                models.Q(target_modules=[]) | 
                models.Q(target_modules__contains=[module_code])
            )
        
        return qs


# ==============================================================================
# USER DISMISSED ANNOUNCEMENTS
# ==============================================================================

class UserDismissedAnnouncement(models.Model):
    """
    Track which announcements a user has dismissed.
    """
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='dismissed_announcements'
    )
    announcement = models.ForeignKey(
        Announcement,
        on_delete=models.CASCADE,
        related_name='dismissed_by_users'
    )
    dismissed_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['user', 'announcement']
    
    def __str__(self):
        return f"{self.user.username} dismissed {self.announcement.title}"
