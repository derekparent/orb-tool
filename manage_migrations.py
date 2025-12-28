#!/usr/bin/env python3
"""Manage migrations for Oil Record Book Tool."""

import os
import sys
from pathlib import Path

# Add src directory to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from flask_migrate import migrate, upgrade, downgrade, current, stamp
from app import create_app

def main():
    """Manage database migrations."""
    if len(sys.argv) < 2:
        print("Usage: python manage_migrations.py [command]")
        print("Commands: upgrade, migrate, downgrade, current, stamp, status")
        return 1

    command = sys.argv[1]

    # Set Flask app environment
    os.environ['FLASK_APP'] = 'src/app.py'

    # Create app with development config
    app = create_app('development')

    with app.app_context():
        try:
            if command == "upgrade":
                print("Upgrading database to latest migration...")
                upgrade()
                print("✓ Database upgraded successfully")

            elif command == "migrate":
                message = sys.argv[2] if len(sys.argv) > 2 else "Auto migration"
                print(f"Creating new migration: {message}")
                migrate(message=message)
                print("✓ Migration created successfully")

            elif command == "downgrade":
                print("Downgrading database by one migration...")
                downgrade()
                print("✓ Database downgraded successfully")

            elif command == "current":
                print("Current database revision:")
                current()

            elif command == "stamp":
                revision = sys.argv[2] if len(sys.argv) > 2 else "head"
                print(f"Stamping database as revision: {revision}")
                stamp(revision=revision)
                print("✓ Database stamped successfully")

            elif command == "status":
                print("Migration status:")
                current()

            else:
                print(f"Unknown command: {command}")
                return 1

        except Exception as e:
            print(f"Error: {e}")
            return 1

    return 0

if __name__ == "__main__":
    sys.exit(main())