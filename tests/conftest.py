"""Test fixtures for Oil Record Book Tool."""

import pytest
import sys
import tempfile
import os
from pathlib import Path

# Add src directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from app import create_app
from models import db, User, UserRole


@pytest.fixture
def app():
    """Create Flask app for testing."""
    # Create temporary database file
    db_fd, db_path = tempfile.mkstemp()

    # Test configuration
    test_config = {
        'TESTING': True,
        'SQLALCHEMY_DATABASE_URI': f'sqlite:///{db_path}',
        'SQLALCHEMY_TRACK_MODIFICATIONS': False,
        'SECRET_KEY': 'test-secret-key',
        'WTF_CSRF_ENABLED': False,
        'LOGIN_DISABLED': False,
        'CORS_ORIGINS': ['http://localhost:3000'],
        'SOUNDING_TABLES_PATH': str(Path(__file__).parent.parent / "data" / "sounding_tables.json")
    }

    app = create_app('testing')

    # Override config with test values
    app.config.update(test_config)

    with app.app_context():
        # Create all tables
        db.create_all()
        yield app

        # Cleanup
        db.session.remove()
        db.drop_all()

    os.close(db_fd)
    os.unlink(db_path)


@pytest.fixture
def client(app):
    """Create test client."""
    return app.test_client()


@pytest.fixture
def runner(app):
    """Create test CLI runner."""
    return app.test_cli_runner()


@pytest.fixture
def admin_user(app):
    """Create admin user for testing."""
    with app.app_context():
        user = User(
            username='admin',
            email='admin@test.com',
            full_name='Test Admin',
            role=UserRole.CHIEF_ENGINEER
        )
        user.set_password('admin123')

        db.session.add(user)
        db.session.commit()

        return user


@pytest.fixture
def engineer_user(app):
    """Create engineer user for testing."""
    with app.app_context():
        user = User(
            username='engineer',
            email='engineer@test.com',
            full_name='Test Engineer',
            role=UserRole.ENGINEER
        )
        user.set_password('engineer123')

        db.session.add(user)
        db.session.commit()

        return user


@pytest.fixture
def viewer_user(app):
    """Create viewer user for testing."""
    with app.app_context():
        user = User(
            username='viewer',
            email='viewer@test.com',
            full_name='Test Viewer',
            role=UserRole.VIEWER
        )
        user.set_password('viewer123')

        db.session.add(user)
        db.session.commit()

        return user


@pytest.fixture
def logged_in_admin(client, admin_user):
    """Log in admin user."""
    with client.session_transaction() as sess:
        sess['_user_id'] = str(admin_user.id)
        sess['_fresh'] = True
    return admin_user


@pytest.fixture
def logged_in_engineer(client, engineer_user):
    """Log in engineer user."""
    with client.session_transaction() as sess:
        sess['_user_id'] = str(engineer_user.id)
        sess['_fresh'] = True
    return engineer_user


@pytest.fixture
def logged_in_viewer(client, viewer_user):
    """Log in viewer user."""
    with client.session_transaction() as sess:
        sess['_user_id'] = str(viewer_user.id)
        sess['_fresh'] = True
    return viewer_user