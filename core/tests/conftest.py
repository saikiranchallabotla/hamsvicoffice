"""
pytest configuration and fixtures for core app testing.

Provides:
- Test organizations and users
- Authenticated clients
- Test projects and data
"""

import pytest
from django.contrib.auth.models import User
from django.test import Client
from core.models import Organization, Membership, Project, Job, SelfFormattedTemplate


# ============================================================================
# ORGANIZATION & USER FIXTURES
# ============================================================================

@pytest.fixture
def test_org():
    """Create a test organization."""
    return Organization.objects.create(
        name="Test Organization",
        subscription_tier="pro"
    )


@pytest.fixture
def test_user(test_org):
    """Create a test user in test_org."""
    user = User.objects.create_user(
        username="testuser",
        email="test@example.com",
        password="testpass123"
    )
    Membership.objects.create(
        user=user,
        organization=test_org,
        role="owner"
    )
    return user


@pytest.fixture
def other_org():
    """Create a second test organization."""
    return Organization.objects.create(
        name="Other Organization",
        subscription_tier="pro"
    )


@pytest.fixture
def other_user(other_org):
    """Create a user in other_org."""
    user = User.objects.create_user(
        username="otheruser",
        email="other@example.com",
        password="otherpass123"
    )
    Membership.objects.create(
        user=user,
        organization=other_org,
        role="owner"
    )
    return user


# ============================================================================
# CLIENT FIXTURES
# ============================================================================

@pytest.fixture
def client():
    """Regular Django test client."""
    return Client()


@pytest.fixture
def authenticated_client(test_user):
    """Authenticated client for test_user."""
    client = Client()
    client.force_login(test_user)
    return client


@pytest.fixture
def other_authenticated_client(other_user):
    """Authenticated client for other_user."""
    client = Client()
    client.force_login(other_user)
    return client


# ============================================================================
# PROJECT FIXTURES
# ============================================================================

@pytest.fixture
def test_project(test_org, test_user):
    """Create a test project in test_org."""
    return Project.objects.create(
        organization=test_org,
        created_by=test_user,
        name="Test Project",
        category="electrical",
        data={}
    )


@pytest.fixture
def other_project(other_org, other_user):
    """Create a test project in other_org."""
    return Project.objects.create(
        organization=other_org,
        created_by=other_user,
        name="Other Project",
        category="electrical",
        data={}
    )


# ============================================================================
# JOB FIXTURES
# ============================================================================

@pytest.fixture
def test_job(test_org, test_user):
    """Create a test job."""
    return Job.objects.create(
        organization=test_org,
        user=test_user,
        job_type='generate_output_excel',
        status=Job.JobStatus.QUEUED,
        progress=0,
        current_step="Initializing..."
    )


@pytest.fixture
def completed_job(test_org, test_user):
    """Create a completed test job."""
    job = Job.objects.create(
        organization=test_org,
        user=test_user,
        job_type='generate_output_excel',
        status=Job.JobStatus.COMPLETED,
        progress=100,
        current_step="Complete"
    )
    job.result = {'output_file_id': 1}
    job.save()
    return job


@pytest.fixture
def failed_job(test_org, test_user):
    """Create a failed test job."""
    job = Job.objects.create(
        organization=test_org,
        user=test_user,
        job_type='generate_output_excel',
        status=Job.JobStatus.FAILED,
        progress=50,
        current_step="Building Output sheet"
    )
    job.error_message = "File not found"
    job.error_log = [{"timestamp": "2026-01-02T10:00:00", "error": "FileNotFoundError"}]
    job.save()
    return job


# ============================================================================
# TEMPLATE FIXTURES
# ============================================================================

@pytest.fixture
def test_template(test_org, test_user):
    """Create a test SelfFormattedTemplate."""
    return SelfFormattedTemplate.objects.create(
        organization=test_org,
        created_by=test_user,
        name="Test Template",
        description="A test template",
        custom_placeholders="Item Name|Quantity"
    )


@pytest.fixture
def other_template(other_org, other_user):
    """Create a template in other_org."""
    return SelfFormattedTemplate.objects.create(
        organization=other_org,
        created_by=other_user,
        name="Other Template",
        description="Template in other org",
        custom_placeholders="Item|Qty"
    )


# ============================================================================
# DATABASE MARKERS
# ============================================================================

pytest_plugins = ['django']


# Mark all tests as using database by default
def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "django_db: mark test as using database (auto-applied)"
    )


# Auto-apply django_db marker
@pytest.fixture
def django_db_blocker(django_db_blocker):
    """Allow all tests to access database."""
    return django_db_blocker
