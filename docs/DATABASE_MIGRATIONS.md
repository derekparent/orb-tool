# Database Migration Guide

## Overview

This project uses Flask-Migrate (Alembic) for database schema evolution. Flask-Migrate is the standard migration tool for Flask applications and provides safe, versioned schema changes.

## Why Migrations?

Previously, the app used `db.create_all()` which is unsuitable for production because:

- **No version control**: Can't track schema changes over time
- **Data loss risk**: Recreating tables loses existing data
- **No rollback**: Can't undo changes if something goes wrong
- **Team sync issues**: Different developers may have different schemas

Flask-Migrate solves these problems by:

- **Versioned changes**: Each migration is a timestamped file
- **Data preservation**: Migrations modify existing tables without data loss
- **Rollback capability**: Can undo migrations if needed
- **Production safety**: Changes can be tested and reviewed before deployment

## Migration Commands

Use the `simple_migration.py` script for all migration operations:

```bash
# Apply all pending migrations
python simple_migration.py upgrade

# Rollback the last migration
python simple_migration.py downgrade

# Create a new migration (after modifying models)
python simple_migration.py create "Add new column to users table"
```

## Production Workflow

### Before Making Schema Changes

1. **Create a branch**: `git checkout -b feature/add-new-field`
2. **Modify models**: Edit `src/models.py` with your changes
3. **Generate migration**: `python simple_migration.py create "Add new field description"`
4. **Review migration**: Check the generated file in `migrations/versions/`
5. **Test migration**: Run `upgrade` and `downgrade` to verify it works
6. **Commit changes**: Include both model changes and migration file

### Production Deployment

1. **Backup database**:
   ```bash
   cp data/orb.db data/orb.db.backup-$(date +%Y%m%d_%H%M%S)
   ```

2. **Stop application** (avoid concurrent access during migration)

3. **Review migration files**:
   ```bash
   # Check what migrations will be applied
   ls migrations/versions/
   ```

4. **Test on copy first** (recommended for critical changes):
   ```bash
   cp data/orb.db data/orb.db.test
   # Edit simple_migration.py to point to test DB
   python simple_migration.py upgrade
   # Verify app works with test DB
   ```

5. **Apply to production**:
   ```bash
   python simple_migration.py upgrade
   ```

6. **Verify application starts**:
   ```bash
   source venv/bin/activate
   python src/app.py
   ```

7. **Test critical functions** (create fuel ticket, view dashboard, etc.)

## Recovery Procedures

### Migration Fails

If a migration fails during upgrade:

1. **Don't panic** - data is usually still intact
2. **Restore backup**: `cp data/orb.db.backup-* data/orb.db`
3. **Check migration file** for syntax errors
4. **Fix and retry** or **rollback** problematic migration

### Rollback Procedure

```bash
# Check current migration status
python simple_migration.py current

# Rollback one migration
python simple_migration.py downgrade

# Continue rollback if needed
python simple_migration.py downgrade
```

### Manual Database Repair

In extreme cases, you might need to manually fix the database:

```bash
# Open SQLite console
sqlite3 data/orb.db

# Check tables
.tables

# Check schema
.schema table_name

# Manual SQL fixes if needed
ALTER TABLE ...
```

## Migration File Structure

Migration files are stored in `migrations/versions/` with this format:

```
2e194345a0a0_initial_migration_from_existing_models.py
```

Each file contains:

```python
def upgrade():
    # SQL commands to apply changes
    op.create_table('new_table', ...)
    op.add_column('existing_table', ...)

def downgrade():
    # SQL commands to undo changes
    op.drop_table('new_table')
    op.drop_column('existing_table', ...)
```

## Common Migration Scenarios

### Adding a New Column

1. **Edit model**:
   ```python
   # In src/models.py
   class WeeklySounding(db.Model):
       # ... existing fields ...
       new_field = db.Column(db.String(100), nullable=True)
   ```

2. **Generate migration**:
   ```bash
   python simple_migration.py create "Add new_field to WeeklySounding"
   ```

3. **Review and apply**:
   ```bash
   # Check the generated migration file
   python simple_migration.py upgrade
   ```

### Renaming a Column

This is more complex and requires careful handling:

1. **Create migration manually** or use data migration
2. **Copy data** from old column to new column
3. **Drop old column** (SQLite limitation: may require table recreation)

### Adding Foreign Keys

When adding relationships:

1. **Add model relationship**
2. **Generate migration**
3. **Verify foreign key constraints** are correctly created

## Best Practices

### Do's

- **Always backup** before production migrations
- **Test migrations** on copy of production data
- **Review generated migrations** before applying
- **Use descriptive migration messages**
- **Commit migrations** with related model changes
- **Run migrations in order** - never skip or reorder

### Don'ts

- **Don't edit existing migrations** once they're deployed
- **Don't delete migration files** from deployed systems
- **Don't run migrations directly with Alembic** - use our script
- **Don't ignore migration errors** - fix them properly
- **Don't make multiple unrelated changes** in one migration

## Troubleshooting

### "Target database is not up to date"

```bash
# This means you need to upgrade first
python simple_migration.py upgrade
```

### "No changes in schema detected"

The models haven't changed since the last migration, or:
- You forgot to save model file changes
- The changes don't affect database schema (e.g., method changes)

### Migration hangs or fails

- **Check database file permissions**
- **Ensure no other processes** are using the database
- **Verify SQLite version** compatibility
- **Check available disk space**

### Flask-Migrate import errors

```bash
# Reinstall migration tools
pip install flask-migrate --upgrade
```

## Monitoring and Maintenance

### Regular Checks

- **Monthly**: Review migration history for any anomalies
- **Before major releases**: Test complete migration rollback/upgrade cycle
- **After deployments**: Verify migration completed successfully

### Performance Considerations

- **Large table migrations** may take time - plan maintenance windows
- **Index creation** can be slow on large datasets
- **Data migrations** (updating existing records) need special care

## Files Created by This Setup

- `migrations/` - Migration repository
- `migrations/env.py` - Migration environment configuration
- `migrations/versions/*.py` - Individual migration files
- `simple_migration.py` - Our custom migration management script
- `data/orb.db.backup-*` - Automatic backups

This migration system replaces the previous `db.create_all()` approach and provides a professional, production-ready database management solution.