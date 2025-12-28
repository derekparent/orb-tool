#!/usr/bin/env python3
"""Simple migration management for Oil Record Book Tool."""

import os
import sys
from pathlib import Path

# Add src directory to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate, upgrade, downgrade, migrate
from config import Config

def create_simple_app():
    """Create minimal Flask app for migrations."""
    app = Flask(__name__)
    app.config.from_object(Config)

    # Import models to register them
    from models import db
    db.init_app(app)

    # Initialize migration
    migrate_obj = Migrate(app, db)

    return app

def main():
    """Run migration commands."""
    if len(sys.argv) < 2:
        print("Usage: python simple_migration.py [command]")
        print("Commands: upgrade, downgrade, create")
        return 1

    command = sys.argv[1]
    app = create_simple_app()

    with app.app_context():
        try:
            if command == "upgrade":
                print("Upgrading database...")
                upgrade()
                print("✓ Database upgraded")

            elif command == "downgrade":
                print("Downgrading database...")
                downgrade()
                print("✓ Database downgraded")

            elif command == "create":
                message = sys.argv[2] if len(sys.argv) > 2 else "Auto migration"
                print(f"Creating migration: {message}")
                migrate(message=message)
                print("✓ Migration created")

            else:
                print(f"Unknown command: {command}")
                return 1

        except Exception as e:
            print(f"Error: {e}")
            return 1

    return 0

if __name__ == "__main__":
    sys.exit(main())