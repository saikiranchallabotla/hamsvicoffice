# core/managers.py
"""
Custom QuerySet managers for organization scoping.
All models inherit from OrgScopedQuerySet to enforce data isolation.
"""

from django.db import models
from django.db.models import Q


class OrgScopedQuerySet(models.QuerySet):
    """Base QuerySet that filters by organization"""
    
    def for_org(self, organization):
        """Filter queryset for a specific organization"""
        return self.filter(organization=organization)
    
    def for_user(self, user):
        """Filter queryset for a specific user"""
        return self.filter(user=user)
    
    def for_org_and_user(self, organization, user):
        """Filter by both org and user - most common pattern"""
        return self.filter(organization=organization, user=user)


class OrgScopedManager(models.Manager):
    """Manager that returns OrgScopedQuerySet by default"""
    
    def get_queryset(self):
        return OrgScopedQuerySet(self.model, using=self._db)
    
    def for_org(self, organization):
        """Shortcut: Model.objects.for_org(org)"""
        return self.get_queryset().for_org(organization)
    
    def for_user(self, user):
        """Shortcut: Model.objects.for_user(user)"""
        return self.get_queryset().for_user(user)
    
    def for_org_and_user(self, organization, user):
        """Shortcut: Model.objects.for_org_and_user(org, user)"""
        return self.get_queryset().for_org_and_user(organization, user)


class ProjectQuerySet(OrgScopedQuerySet):
    """Project-specific queryset with utility methods"""
    
    def by_category(self, category):
        return self.filter(category=category)
    
    def recent(self, limit=10):
        return self[:limit]


class ProjectManager(OrgScopedManager):
    def get_queryset(self):
        return ProjectQuerySet(self.model, using=self._db)


class JobQuerySet(OrgScopedQuerySet):
    """Job-specific queryset with status filtering"""
    
    def active(self):
        """Get active (non-completed) jobs"""
        return self.filter(status__in=['queued', 'running'])
    
    def completed(self):
        """Get completed jobs"""
        return self.filter(status__in=['completed', 'failed', 'cancelled'])
    
    def successful(self):
        """Get successfully completed jobs"""
        return self.filter(status='completed')
    
    def failed(self):
        """Get failed jobs"""
        return self.filter(status='failed')
    
    def by_type(self, job_type):
        return self.filter(job_type=job_type)
    
    def recent(self, limit=10):
        return self.order_by('-created_at')[:limit]


class JobManager(OrgScopedManager):
    def get_queryset(self):
        return JobQuerySet(self.model, using=self._db)


class EstimateQuerySet(OrgScopedQuerySet):
    """Estimate-specific queryset"""
    
    def drafts(self):
        return self.filter(status='draft')
    
    def finalized(self):
        return self.filter(status='finalized')
    
    def archived(self):
        return self.filter(status='archived')
    
    def by_category(self, category):
        return self.filter(category=category)


class EstimateManager(OrgScopedManager):
    def get_queryset(self):
        return EstimateQuerySet(self.model, using=self._db)
