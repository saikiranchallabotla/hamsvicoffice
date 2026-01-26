"""
Tests for multi-tenancy isolation.

Verifies:
- User A cannot access User B's data
- Org-scoped queries work correctly
- No data leakage between organizations
"""

import pytest
from django.contrib.auth.models import User
from core.models import (
    Organization, Membership, Project, Job, 
    SelfFormattedTemplate
)


@pytest.mark.django_db
class TestProjectIsolation:
    """Tests for project isolation between organizations."""
    
    def test_project_belongs_to_org(self, test_project, test_org):
        """Project should belong to organization."""
        assert test_project.organization == test_org
    
    def test_user_can_list_own_projects(self, test_user, test_project):
        """User can see projects in their org."""
        user_orgs = Membership.objects.filter(
            user=test_user
        ).values_list('organization', flat=True)
        
        projects = Project.objects.filter(organization__in=user_orgs)
        assert test_project in projects
    
    def test_user_cannot_see_other_org_projects(
        self, 
        test_user, 
        other_project
    ):
        """User cannot see projects from other org."""
        user_orgs = Membership.objects.filter(
            user=test_user
        ).values_list('organization', flat=True)
        
        projects = Project.objects.filter(organization__in=user_orgs)
        assert other_project not in projects
    
    def test_project_query_filtering(self, test_user, test_project, other_project):
        """Project queries properly filtered by org."""
        # Simulate what the view does
        user_orgs = [m.organization for m in Membership.objects.filter(user=test_user)]
        visible_projects = Project.objects.filter(organization__in=user_orgs)
        
        assert test_project in visible_projects
        assert other_project not in visible_projects


@pytest.mark.django_db
class TestJobIsolation:
    """Tests for job isolation between organizations."""
    
    def test_job_belongs_to_org(self, test_job, test_org):
        """Job should belong to organization."""
        assert test_job.organization == test_org
    
    def test_user_can_see_own_jobs(self, test_user, test_job):
        """User can see jobs in their org."""
        user_orgs = Membership.objects.filter(
            user=test_user
        ).values_list('organization', flat=True)
        
        jobs = Job.objects.filter(organization__in=user_orgs)
        assert test_job in jobs
    
    def test_user_cannot_see_other_org_jobs(
        self, 
        test_user, 
        other_user,
        test_org,
        other_org
    ):
        """User cannot see jobs from other org."""
        # Create job in other org
        other_job = Job.objects.create(
            organization=other_org,
            user=other_user,
            job_type='generate_output_excel',
            status=Job.JobStatus.COMPLETED
        )
        
        # Query from user's perspective
        user_orgs = Membership.objects.filter(
            user=test_user
        ).values_list('organization', flat=True)
        
        visible_jobs = Job.objects.filter(organization__in=user_orgs)
        assert other_job not in visible_jobs
    
    def test_multiple_orgs_have_separate_job_queues(
        self,
        test_user,
        other_user,
        test_org,
        other_org
    ):
        """Different orgs have separate job lists."""
        # Create jobs in each org
        job1 = Job.objects.create(
            organization=test_org,
            user=test_user,
            job_type='test',
            status=Job.JobStatus.QUEUED
        )
        
        job2 = Job.objects.create(
            organization=other_org,
            user=other_user,
            job_type='test',
            status=Job.JobStatus.QUEUED
        )
        
        # Verify isolation
        org1_jobs = Job.objects.filter(organization=test_org)
        org2_jobs = Job.objects.filter(organization=other_org)
        
        assert job1 in org1_jobs
        assert job1 not in org2_jobs
        assert job2 in org2_jobs
        assert job2 not in org1_jobs


@pytest.mark.django_db
class TestTemplateIsolation:
    """Tests for template isolation between organizations."""
    
    def test_template_belongs_to_org(self, test_template, test_org):
        """Template should belong to organization."""
        assert test_template.organization == test_org
    
    def test_user_can_see_own_templates(self, test_user, test_template):
        """User can see templates in their org."""
        user_orgs = Membership.objects.filter(
            user=test_user
        ).values_list('organization', flat=True)
        
        templates = SelfFormattedTemplate.objects.filter(organization__in=user_orgs)
        assert test_template in templates
    
    def test_user_cannot_see_other_org_templates(
        self, 
        test_user, 
        other_template
    ):
        """User cannot see templates from other org."""
        user_orgs = Membership.objects.filter(
            user=test_user
        ).values_list('organization', flat=True)
        
        templates = SelfFormattedTemplate.objects.filter(organization__in=user_orgs)
        assert other_template not in templates


@pytest.mark.django_db
class TestMembershipIsolation:
    """Tests for organization membership isolation."""
    
    def test_user_belongs_to_org(self, test_user, test_org):
        """User should have membership in org."""
        membership = Membership.objects.get(user=test_user)
        assert membership.organization == test_org
    
    def test_user_not_member_of_other_org(self, test_user, other_org):
        """User should not be member of other org."""
        memberships = Membership.objects.filter(user=test_user)
        orgs = [m.organization for m in memberships]
        
        assert other_org not in orgs
    
    def test_cannot_access_after_membership_removed(
        self, 
        test_user, 
        test_org
    ):
        """User cannot access org after membership removed."""
        # Remove membership
        Membership.objects.filter(user=test_user, organization=test_org).delete()
        
        # Verify not in org
        memberships = Membership.objects.filter(user=test_user)
        assert memberships.count() == 0


@pytest.mark.django_db
class TestCrossOrgDataLeakage:
    """Tests to prevent data leakage between organizations."""
    
    def test_no_data_leakage_in_project_list(
        self,
        test_user,
        other_user,
        test_project,
        other_project
    ):
        """Project list should not leak other org data."""
        # Get test_user's visible projects
        user_orgs = Membership.objects.filter(
            user=test_user
        ).values_list('organization', flat=True)
        
        user_projects = Project.objects.filter(organization__in=user_orgs)
        
        # Should see own, not other
        assert test_project in user_projects
        assert other_project not in user_projects
    
    def test_no_data_leakage_in_job_status(
        self,
        test_user,
        other_user,
        test_org,
        other_org
    ):
        """Job status API should not leak other org data."""
        # Create jobs
        job1 = Job.objects.create(
            organization=test_org,
            user=test_user,
            job_type='test',
            status=Job.JobStatus.COMPLETED,
            progress=100
        )
        
        job2 = Job.objects.create(
            organization=other_org,
            user=other_user,
            job_type='test',
            status=Job.JobStatus.COMPLETED,
            progress=100
        )
        
        # test_user should only see job1
        user_orgs = [m.organization for m in Membership.objects.filter(user=test_user)]
        visible_jobs = Job.objects.filter(organization__in=user_orgs)
        
        assert job1 in visible_jobs
        assert job2 not in visible_jobs
    
    def test_org_scope_in_all_queries(
        self,
        test_user,
        test_project,
        other_project
    ):
        """All queries should be scoped by org."""
        # This tests the principle that all queries should filter by org
        user_orgs = Membership.objects.filter(
            user=test_user
        ).values_list('organization_id', flat=True)
        
        # All major model queries should filter by org
        projects = Project.objects.filter(organization_id__in=user_orgs)
        jobs = Job.objects.filter(organization_id__in=user_orgs)
        templates = SelfFormattedTemplate.objects.filter(organization_id__in=user_orgs)
        
        # Verify filtering works
        assert test_project in projects
        assert other_project not in projects
