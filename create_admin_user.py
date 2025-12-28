#!/usr/bin/env python3
"""Create initial admin user for Oil Record Book Tool."""

import sys
from pathlib import Path

# Add src directory to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from app import create_app
from models import db, User, UserRole

def create_admin_user():
    """Create an initial admin user."""
    app = create_app('development')

    with app.app_context():
        # Check if admin user already exists
        admin = User.query.filter_by(username='admin').first()
        if admin:
            print("Admin user already exists")
            return

        # Create admin user
        admin = User(
            username='admin',
            email='admin@example.com',
            full_name='Chief Engineer',
            role=UserRole.CHIEF_ENGINEER
        )
        admin.set_password('admin123')  # Change this in production!

        db.session.add(admin)
        db.session.commit()

        print("✓ Admin user created")
        print("  Username: admin")
        print("  Password: admin123")
        print("  Role: Chief Engineer")
        print("\n⚠️  Remember to change the password after first login!")

if __name__ == "__main__":
    create_admin_user()