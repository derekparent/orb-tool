#!/usr/bin/env python3
"""Database backup script for Oil Record Book Tool."""

import os
import sys
import shutil
from datetime import datetime
from pathlib import Path

def main():
    """Create database backup with timestamp."""
    # Project root directory
    project_root = Path(__file__).parent.parent
    db_file = project_root / "data" / "orb.db"
    backup_dir = project_root / "data" / "backups"

    # Check if database exists
    if not db_file.exists():
        print(f"Error: Database file not found: {db_file}")
        return 1

    # Create backups directory if it doesn't exist
    backup_dir.mkdir(exist_ok=True)

    # Generate backup filename with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = backup_dir / f"orb.db.backup-{timestamp}"

    try:
        # Copy database file
        shutil.copy2(db_file, backup_file)

        # Get file sizes for verification
        original_size = db_file.stat().st_size
        backup_size = backup_file.stat().st_size

        if original_size != backup_size:
            print(f"Warning: Size mismatch! Original: {original_size}, Backup: {backup_size}")
            return 1

        print(f"✓ Database backed up successfully")
        print(f"  Original: {db_file}")
        print(f"  Backup:   {backup_file}")
        print(f"  Size:     {original_size:,} bytes")

        # Cleanup old backups (keep last 10)
        cleanup_old_backups(backup_dir)

        return 0

    except Exception as e:
        print(f"Error creating backup: {e}")
        return 1

def cleanup_old_backups(backup_dir, keep_count=10):
    """Remove old backup files, keeping only the most recent ones."""
    try:
        backup_files = list(backup_dir.glob("orb.db.backup-*"))
        backup_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)

        if len(backup_files) <= keep_count:
            print(f"  Keeping all {len(backup_files)} backup files")
            return

        files_to_remove = backup_files[keep_count:]

        for old_backup in files_to_remove:
            old_backup.unlink()
            print(f"  Removed old backup: {old_backup.name}")

        print(f"  Kept {keep_count} most recent backups, removed {len(files_to_remove)} old ones")

    except Exception as e:
        print(f"Warning: Failed to cleanup old backups: {e}")

if __name__ == "__main__":
    sys.exit(main())