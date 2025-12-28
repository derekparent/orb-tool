#!/usr/bin/env python3
"""Database restore script for Oil Record Book Tool."""

import os
import sys
import shutil
from pathlib import Path

def main():
    """Restore database from backup."""
    if len(sys.argv) < 2:
        print("Usage: python restore_database.py <backup_file>")
        print("\nAvailable backups:")
        list_backups()
        return 1

    # Project root directory
    project_root = Path(__file__).parent.parent
    db_file = project_root / "data" / "orb.db"
    backup_dir = project_root / "data" / "backups"

    # Parse backup file argument
    backup_arg = sys.argv[1]

    # If just a filename, assume it's in the backup directory
    if "/" not in backup_arg:
        backup_file = backup_dir / backup_arg
    else:
        backup_file = Path(backup_arg)

    # Check if backup exists
    if not backup_file.exists():
        print(f"Error: Backup file not found: {backup_file}")
        print("\nAvailable backups:")
        list_backups()
        return 1

    try:
        # Create backup of current database before restore
        if db_file.exists():
            current_backup = backup_dir / f"orb.db.pre-restore-{int(datetime.now().timestamp())}"
            shutil.copy2(db_file, current_backup)
            print(f"✓ Current database backed up to: {current_backup.name}")

        # Restore from backup
        shutil.copy2(backup_file, db_file)

        # Verify restore
        original_size = backup_file.stat().st_size
        restored_size = db_file.stat().st_size

        if original_size != restored_size:
            print(f"Warning: Size mismatch! Backup: {original_size}, Restored: {restored_size}")
            return 1

        print(f"✓ Database restored successfully")
        print(f"  From:     {backup_file}")
        print(f"  To:       {db_file}")
        print(f"  Size:     {restored_size:,} bytes")

        return 0

    except Exception as e:
        print(f"Error restoring database: {e}")
        return 1

def list_backups():
    """List available backup files."""
    project_root = Path(__file__).parent.parent
    backup_dir = project_root / "data" / "backups"

    if not backup_dir.exists():
        print("  No backups directory found")
        return

    backup_files = list(backup_dir.glob("orb.db.backup-*"))
    backup_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)

    if not backup_files:
        print("  No backup files found")
        return

    print("  Most recent backups:")
    for backup in backup_files[:10]:  # Show last 10
        mtime = backup.stat().st_mtime
        size = backup.stat().st_size
        from datetime import datetime
        date_str = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M:%S")
        print(f"    {backup.name} ({size:,} bytes, {date_str})")

if __name__ == "__main__":
    from datetime import datetime
    sys.exit(main())