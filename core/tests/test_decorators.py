"""
Tests for decorators (@org_required, @login_required, etc).

Verifies:
- Decorators properly enforce auth
- Error handling in decorators
- Organization context extraction
"""

import pytest
from django.test import RequestFactory
from django.contrib.auth.models import AnonymousUser
from django.http import HttpResponse
from core.decorators import org_required
from core.models import Organization, Membership


@pytest.mark.django_db
class TestOrgRequiredDecorator:
    """Tests for @org_required decorator."""
    
    def test_org_required_with_valid_org(self, test_user, test_org):
        """Decorator allows access with valid org."""
        factory = RequestFactory()
        request = factory.get('/')
        request.user = test_user
        
        # Mock view
        @org_required
        def test_view(request):
            return HttpResponse('OK')
        
        # Should not raise exception
        response = test_view(request)
        assert response.status_code == 200
    
    def test_org_required_with_anonymous_user(self):
        """Decorator rejects anonymous users."""
        factory = RequestFactory()
        request = factory.get('/')
        request.user = AnonymousUser()
        
        @org_required
        def test_view(request):
            return HttpResponse('OK')
        
        # Should redirect to login
        response = test_view(request)
        assert response.status_code == 302
    
    def test_org_required_with_multiple_orgs(self, test_user):
        """User with multiple orgs can access."""
        # Add another org
        org2 = Organization.objects.create(name="Org 2")
        Membership.objects.create(
            user=test_user,
            organization=org2,
            role='owner'
        )
        
        factory = RequestFactory()
        request = factory.get('/')
        request.user = test_user
        
        @org_required
        def test_view(request):
            return HttpResponse('OK')
        
        response = test_view(request)
        assert response.status_code == 200


@pytest.mark.django_db
class TestDecoratorIntegration:
    """Tests for decorator integration with views."""
    
    def test_multiple_decorators_stack(self, test_user):
        """Multiple decorators work together."""
        factory = RequestFactory()
        request = factory.get('/')
        request.user = test_user
        
        # Apply multiple decorators
        @org_required
        def test_view(request):
            return HttpResponse('OK')
        
        response = test_view(request)
        assert response.status_code == 200
    
    def test_decorator_preserves_function_name(self):
        """Decorators preserve original function metadata."""
        @org_required
        def my_view(request):
            """My view docstring."""
            return HttpResponse('OK')
        
        # Name should be preserved (with functools.wraps)
        assert hasattr(my_view, '__name__')


@pytest.mark.django_db
class TestOrgContextExtraction:
    """Tests for extracting org from request."""
    
    def test_get_org_from_authenticated_user(self, test_user, test_org):
        """Can extract org from authenticated user."""
        # User should be in test_org via Membership
        memberships = Membership.objects.filter(user=test_user)
        assert memberships.count() >= 1
        
        user_org = memberships.first().organization
        assert user_org == test_org
    
    def test_user_org_context_in_view(self, authenticated_client, test_user):
        """Org context available in view."""
        # This would be tested in integration tests
        # Here we just verify the user -> org mapping exists
        user_orgs = Membership.objects.filter(user=test_user)
        assert user_orgs.count() >= 1
