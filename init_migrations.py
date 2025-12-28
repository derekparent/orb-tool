#!/usr/bin/env python3
"""Initialize Flask-Migrate for the Oil Record Book Tool."""

import os
import sys
from pathlib import Path

# Add src directory to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from flask_migrate import init, migrate, upgrade
from app import create_app

def main():
    """Initialize migration repository and create initial migration."""
    # Set Flask app environment
    os.environ['FLASK_APP'] = 'src/app.py'

    # Create app with development config
    app = create_app('development')

    with app.app_context():
        print("Initializing migration repository...")
        try:
            init()
            print("✓ Migration repository initialized")
        except Exception as e:
            if "already exists" in str(e).lower():
                print("Migration repository already exists")
            else:
                print(f"Error initializing migrations: {e}")
                return 1

        print("Creating complete migration with all models...")
        try:
            migrate(message="Complete initial migration - all ORB models")
            print("✓ Migration created with all models")
        except Exception as e:
            print(f"Error creating migration: {e}")
            return 1

        print("\nApplying migration to database...")
        try:
            upgrade()
            print("✓ Migration applied successfully")
        except Exception as e:
            print(f"Error applying migration: {e}")
            print("This might be normal if tables already exist")

        print("\nMigration setup complete!")
        print("Next steps:")
        print("1. Review the generated migration in migrations/versions/")
        print("2. Test rollback with: flask db downgrade")
        print("3. Test upgrade with: flask db upgrade")

    return 0

if __name__ == "__main__":
    sys.exit(main())