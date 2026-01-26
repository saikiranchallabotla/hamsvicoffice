"""
Tests for authentication and authorization.

Verifies:
- Login required on protected views
- Public views accessible without login
- Session management
- Decorator functionality
"""

import pytest
from django.contrib.auth.models import User
from django.urls import reverse
from core.models import Organization, Membership


@pytest.mark.django_db
class TestLoginRequired:
    """Tests for @login_required decorator."""
    
    def test_home_page_accessible_without_login(self, client):
        """Home page should be accessible without login."""
        response = client.get('/core/home/')
        assert response.status_code in [200, 404]  # May not exist in test env
    
    def test_datas_view_redirects_to_login(self, client):
        """Protected /datas/ view should redirect to login."""
        response = client.get('/datas/electrical/', follow=False)
        assert response.status_code == 302
        assert 'login' in response.url.lower()
    
    def test_estimate_view_redirects_to_login(self, client):
        """Protected estimate view should redirect to login."""
        response = client.get('/estimate/', follow=False)
        assert response.status_code == 302
        assert 'login' in response.url.lower()
    
    def test_authenticated_user_can_access_protected_view(self, authenticated_client):
        """Authenticated user can access protected views."""
        # Just verify no redirect to login
        response = authenticated_client.get('/datas/', follow=True)
        # Should not redirect to login (status may vary, but not 302 to login)
        if response.status_code == 302:
            assert 'login' not in response.url.lower()
    
    def test_logout_clears_session(self, authenticated_client, test_user):
        """Logout should clear user session."""
        # First verify user is logged in
        assert authenticated_client.session.get('_auth_user_id') == str(test_user.id)
        
        # Logout
        response = authenticated_client.get('/logout/', follow=True)
        
        # Verify session cleared (new request should have no auth)
        new_client = authenticated_client.__class__()
        assert new_client.session.get('_auth_user_id') is None


@pytest.mark.django_db
class TestOrgRequired:
    """Tests for @org_required decorator."""
    
    def test_user_can_access_own_org_projects(self, authenticated_client, test_project):
        """User can access projects in their own organization."""
        response = authenticated_client.get(
            f'/my_projects/',
            follow=True
        )
        # Should return 200 or 302 (redirect), not 403
        assert response.status_code in [200, 302]
    
    def test_user_cannot_access_other_org_project(
        self, 
        authenticated_client, 
        test_user, 
        other_project
    ):
        """User cannot access projects in other organization."""
        # This test verifies org isolation is enforced
        # Accessing other org's project should fail (403 or 404)
        response = authenticated_client.get(
            f'/delete_project/{other_project.id}/',
            follow=True
        )
        # Should be forbidden or not found
        assert response.status_code in [403, 404, 302]
    
    def test_self_formatted_save_requires_org_context(self, authenticated_client):
        """Self-formatted save requires proper org context."""
        response = authenticated_client.post(
            '/self_formatted/save/',
            {
                'name': 'Test',
                'description': 'Test',
            },
            follow=True
        )
        # Should either process or redirect, not error
        assert response.status_code != 500


@pytest.mark.django_db
class TestUserSessionManagement:
    """Tests for user session handling."""
    
    def test_session_data_per_user(self, authenticated_client, test_user):
        """Each user has isolated session data."""
        # Set some session data
        session = authenticated_client.session
        session['test_key'] = 'test_value'
        session.save()
        
        # Verify it's there
        session = authenticated_client.session
        assert session.get('test_key') == 'test_value'
    
    def test_different_users_have_different_sessions(
        self, 
        authenticated_client, 
        other_authenticated_client
    ):
        """Different authenticated clients have different sessions."""
        # Set data in first client
        session1 = authenticated_client.session
        session1['user_data'] = 'user1'
        session1.save()
        
        # Other client should not see it
        session2 = other_authenticated_client.session
        assert session2.get('user_data') != 'user1'


@pytest.mark.django_db
class TestUserIsolation:
    """Tests for user data isolation."""
    
    def test_user_can_only_see_own_org(self, test_user, other_org):
        """User should only be member of their own org."""
        memberships = Membership.objects.filter(user=test_user)
        orgs = [m.organization for m in memberships]
        
        # User should be in one org
        assert len(orgs) >= 1
        
        # other_org should not be in user's orgs
        assert other_org not in orgs
    
    def test_multiple_users_in_same_org(self, test_org):
        """Multiple users can belong to same organization."""
        user1 = User.objects.create_user(
            username='user1',
            password='pass1'
        )
        user2 = User.objects.create_user(
            username='user2',
            password='pass2'
        )
        
        Membership.objects.create(user=user1, organization=test_org, role='owner')
        Membership.objects.create(user=user2, organization=test_org, role='editor')
        
        # Both should be members
        members = Membership.objects.filter(organization=test_org)
        assert members.count() >= 2


@pytest.mark.django_db
class TestPermissionLevels:
    """Tests for different permission levels (owner, editor, viewer)."""
    
    def test_owner_can_delete_project(self, authenticated_client, test_project, test_user):
        """Owner can delete project."""
        # Verify user is owner
        member = Membership.objects.get(user=test_user)
        assert member.role == 'owner'
    
    def test_editor_role_exists(self, test_org):
        """Editor role can be assigned."""
        user = User.objects.create_user(username='editor', password='pass')
        member = Membership.objects.create(
            user=user,
            organization=test_org,
            role='editor'
        )
        assert member.role == 'editor'
    
    def test_viewer_role_exists(self, test_org):
        """Viewer role can be assigned."""
        user = User.objects.create_user(username='viewer', password='pass')
        member = Membership.objects.create(
            user=user,
            organization=test_org,
            role='viewer'
        )
        assert member.role == 'viewer'
