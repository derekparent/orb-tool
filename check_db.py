#!/usr/bin/env python3
"""Check database tables."""

import sqlite3
import sys
from pathlib import Path

def main():
    """Check what tables exist in the database."""
    db_path = Path(__file__).parent / "data" / "orb.db"

    if not db_path.exists():
        print(f"Database file not found: {db_path}")
        return 1

    try:
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()

        # Get all table names
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()

        print("Existing tables in database:")
        for table in tables:
            table_name = table[0]
            print(f"  - {table_name}")

            # Get table schema
            cursor.execute(f"PRAGMA table_info({table_name});")
            columns = cursor.fetchall()
            print(f"    Columns: {len(columns)}")
            for col in columns[:3]:  # Show first 3 columns
                print(f"      {col[1]} ({col[2]})")
            if len(columns) > 3:
                print(f"      ... and {len(columns) - 3} more")
            print()

        conn.close()

    except Exception as e:
        print(f"Error checking database: {e}")
        return 1

    return 0

if __name__ == "__main__":
    sys.exit(main())