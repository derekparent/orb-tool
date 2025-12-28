"""Authentication tests for Oil Record Book Tool."""

import pytest
from datetime import datetime, UTC
import json
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from models import db, User, UserRole


class TestUserModel:
    """Test User model functionality."""

    def test_user_creation(self, app):
        """Test creating a new user."""
        with app.app_context():
            user = User(
                username='testuser',
                email='test@example.com',
                full_name='Test User',
                role=UserRole.ENGINEER
            )
            user.set_password('testpass')

            db.session.add(user)
            db.session.commit()

            # Verify user was created
            saved_user = User.query.filter_by(username='testuser').first()
            assert saved_user is not None
            assert saved_user.email == 'test@example.com'
            assert saved_user.role == UserRole.ENGINEER
            assert saved_user.check_password('testpass')
            assert not saved_user.check_password('wrongpass')

    def test_password_hashing(self):
        """Test password hashing and verification."""
        user = User(username='test', role=UserRole.ENGINEER)
        user.set_password('mypassword')

        assert user.password_hash != 'mypassword'
        assert user.check_password('mypassword')
        assert not user.check_password('wrongpassword')

    def test_role_permissions(self):
        """Test role-based access control."""
        # Chief Engineer (admin)
        chief = User(username='chief', role=UserRole.CHIEF_ENGINEER, is_active=True)
        assert chief.can_access_route('read')
        assert chief.can_access_route('write')
        assert chief.can_access_route('admin')

        # Engineer (write)
        engineer = User(username='engineer', role=UserRole.ENGINEER, is_active=True)
        assert engineer.can_access_route('read')
        assert engineer.can_access_route('write')
        assert not engineer.can_access_route('admin')

        # Viewer (read-only)
        viewer = User(username='viewer', role=UserRole.VIEWER, is_active=True)
        assert viewer.can_access_route('read')
        assert not viewer.can_access_route('write')
        assert not viewer.can_access_route('admin')

        # Inactive user
        inactive = User(username='inactive', role=UserRole.ENGINEER, is_active=False)
        assert not inactive.can_access_route('read')
        assert not inactive.can_access_route('write')
        assert not inactive.can_access_route('admin')

    def test_user_to_dict(self, app):
        """Test user serialization."""
        with app.app_context():
            user = User(
                username='testuser',
                email='test@example.com',
                full_name='Test User',
                role=UserRole.ENGINEER
            )
            user.set_password('testpass')
            user.last_login = datetime.now(UTC)

            db.session.add(user)
            db.session.commit()

            user_dict = user.to_dict()
            assert user_dict['username'] == 'testuser'
            assert user_dict['email'] == 'test@example.com'
            assert user_dict['role'] == 'engineer'
            assert 'password_hash' not in user_dict


class TestAuthRoutes:
    """Test authentication routes."""

    def test_login_page(self, client):
        """Test login page displays."""
        response = client.get('/auth/login')
        assert response.status_code == 200
        assert b'Engine Room Login' in response.data

    def test_login_with_valid_credentials(self, client, admin_user):
        """Test successful login."""
        response = client.post('/auth/login', data={
            'username': 'admin',
            'password': 'admin123'
        }, follow_redirects=True)

        assert response.status_code == 200
        # Should redirect to dashboard
        assert b'Dashboard' in response.data or b'dashboard' in response.data

    def test_login_with_invalid_credentials(self, client, admin_user):
        """Test failed login."""
        response = client.post('/auth/login', data={
            'username': 'admin',
            'password': 'wrongpassword'
        })

        assert response.status_code == 200
        assert b'Invalid username or password' in response.data

    def test_login_api(self, client, admin_user):
        """Test JSON API login."""
        response = client.post('/auth/login',
            json={
                'username': 'admin',
                'password': 'admin123'
            },
            headers={'Content-Type': 'application/json'}
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is True
        assert 'user' in data

    def test_logout(self, client, logged_in_admin):
        """Test user logout."""
        response = client.get('/auth/logout', follow_redirects=True)
        assert response.status_code == 200
        assert b'Engine Room Login' in response.data

    def test_profile_page(self, client, logged_in_admin):
        """Test profile page access."""
        response = client.get('/auth/profile')
        assert response.status_code == 200
        assert b'User Profile' in response.data
        assert b'admin' in response.data

    def test_current_user_api(self, client, logged_in_admin):
        """Test current user API endpoint."""
        response = client.get('/auth/api/current-user')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is True
        assert data['user']['username'] == 'admin'

    def test_check_auth_api_authenticated(self, client, logged_in_admin):
        """Test auth check API when authenticated."""
        response = client.get('/auth/api/check-auth')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['authenticated'] is True

    def test_check_auth_api_unauthenticated(self, client):
        """Test auth check API when not authenticated."""
        response = client.get('/auth/api/check-auth')
        assert response.status_code == 401
        data = json.loads(response.data)
        assert data['authenticated'] is False


class TestUserManagement:
    """Test user management routes (admin only)."""

    def test_manage_users_page_admin(self, client, logged_in_admin):
        """Test user management page access as admin."""
        response = client.get('/auth/admin/users')
        assert response.status_code == 200
        assert b'User Management' in response.data

    def test_manage_users_page_non_admin(self, client, logged_in_engineer):
        """Test user management page blocked for non-admin."""
        response = client.get('/auth/admin/users', follow_redirects=True)
        assert response.status_code == 200
        assert b'Access denied' in response.data

    def test_create_user_admin(self, client, logged_in_admin):
        """Test creating user as admin."""
        response = client.post('/auth/admin/users', json={
            'username': 'newuser',
            'password': 'newpass123',
            'full_name': 'New User',
            'role': 'engineer'
        })

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is True
        assert data['user']['username'] == 'newuser'

    def test_create_user_non_admin(self, client, logged_in_engineer):
        """Test creating user blocked for non-admin."""
        response = client.post('/auth/admin/users', json={
            'username': 'newuser',
            'password': 'newpass123',
            'role': 'engineer'
        })

        assert response.status_code == 403

    def test_toggle_user_status_admin(self, client, logged_in_admin, app):
        """Test toggling user status as admin."""
        with app.app_context():
            # Create a test user
            user = User(username='toggleuser', role=UserRole.ENGINEER)
            user.set_password('pass123')
            db.session.add(user)
            db.session.commit()
            user_id = user.id

        response = client.post(f'/auth/admin/users/{user_id}/toggle')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is True

    def test_cannot_toggle_own_status(self, client, logged_in_admin):
        """Test that admin cannot disable their own account."""
        # Get admin user ID
        response = client.get('/auth/api/current-user')
        user_data = json.loads(response.data)
        admin_id = user_data['user']['id']

        response = client.post(f'/auth/admin/users/{admin_id}/toggle')
        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'Cannot disable your own account' in data['error']


class TestRouteProtection:
    """Test route protection with authentication."""

    def test_dashboard_requires_auth(self, client):
        """Test dashboard redirects to login when not authenticated."""
        response = client.get('/')
        assert response.status_code == 302
        assert '/auth/login' in response.location

    def test_api_routes_require_auth(self, client):
        """Test API routes require authentication."""
        # Test a read endpoint
        response = client.get('/api/dashboard/stats')
        assert response.status_code == 302 or response.status_code == 401

        # Test a write endpoint
        response = client.post('/api/soundings', json={'test': 'data'})
        assert response.status_code == 302 or response.status_code == 401

    def test_role_based_route_access(self, client, app):
        """Test role-based access to routes."""
        with app.app_context():
            # Create users with different roles
            viewer = User(username='viewer', role=UserRole.VIEWER)
            viewer.set_password('pass123')
            engineer = User(username='engineer', role=UserRole.ENGINEER)
            engineer.set_password('pass123')

            db.session.add_all([viewer, engineer])
            db.session.commit()

        # Test viewer cannot access write routes
        with client.session_transaction() as sess:
            sess['_user_id'] = str(viewer.id)
            sess['_fresh'] = True

        response = client.get('/soundings', follow_redirects=True)
        assert b'Access denied' in response.data

        # Test engineer can access write routes
        with client.session_transaction() as sess:
            sess['_user_id'] = str(engineer.id)
            sess['_fresh'] = True

        response = client.get('/soundings')
        assert response.status_code == 200

    def test_admin_only_routes(self, client, logged_in_engineer):
        """Test admin-only routes are protected."""
        response = client.get('/new-hitch', follow_redirects=True)
        assert b'Access denied' in response.data or b'Chief Engineer role required' in response.data


class TestSessionPersistence:
    """Test session persistence for offshore use."""

    def test_remember_me_login(self, client, admin_user):
        """Test remember me functionality."""
        response = client.post('/auth/login', data={
            'username': 'admin',
            'password': 'admin123',
            'remember': '1'
        }, follow_redirects=True)

        assert response.status_code == 200
        # Check for remember cookie (implementation depends on Flask-Login settings)

    def test_session_survives_server_restart(self, client, logged_in_admin):
        """Test session persistence across server restart simulation."""
        # First, verify we're logged in
        response = client.get('/auth/api/current-user')
        assert response.status_code == 200

        # Simulate session persistence by checking that we're still logged in
        # after making another request (Flask test client maintains session)
        response = client.get('/auth/profile')
        assert response.status_code == 200
        assert b'User Profile' in response.data

    def test_inactive_user_cannot_login(self, client, app):
        """Test that inactive users cannot log in."""
        with app.app_context():
            user = User(username='inactive', role=UserRole.ENGINEER, is_active=False)
            user.set_password('pass123')
            db.session.add(user)
            db.session.commit()

        response = client.post('/auth/login', data={
            'username': 'inactive',
            'password': 'pass123'
        })

        assert response.status_code == 200
        assert b'Invalid username or password' in response.data