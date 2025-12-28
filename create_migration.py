#!/usr/bin/env python3
"""Create migration for all Oil Record Book models."""

import os
import sys
from pathlib import Path

# Add src directory to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from flask_migrate import migrate, upgrade, downgrade
from app import create_app

def main():
    """Create and apply migration for all models."""
    # Set Flask app environment
    os.environ['FLASK_APP'] = 'src/app.py'

    # Create app with development config
    app = create_app('development')

    with app.app_context():
        print("Creating migration for all Oil Record Book models...")
        try:
            migrate(message="Complete ORB models - all tables")
            print("✓ Migration created successfully")
        except Exception as e:
            print(f"Error creating migration: {e}")
            return 1

        print("\nApplying migration to database...")
        try:
            upgrade()
            print("✓ Migration applied successfully")
        except Exception as e:
            print(f"Warning: {e}")
            print("This might be normal if some tables already exist")

        print("\nMigration setup complete!")

    return 0

if __name__ == "__main__":
    sys.exit(main())