#!/usr/bin/env python3
"""
Subsystem Tagging Schema for Manuals Search

Adds tags and document_tags tables to engine_search.db for multi-label
subsystem filtering. Keeps existing pages table unchanged.

Usage:
    python -m services.tagging_schema [--seed]
"""

import json
import sqlite3
from pathlib import Path

# Schema version for tracking migrations
SCHEMA_VERSION = "1.0"


def get_db_connection(db_path: Path) -> sqlite3.Connection:
    """Get database connection with row factory."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def create_documents_table(conn: sqlite3.Connection) -> int:
    """
    Create documents table from distinct filenames in pages table.
    Returns number of documents created.
    """
    cursor = conn.cursor()

    # Check if table exists
    cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type='table' AND name='documents'
    """)
    if cursor.fetchone():
        print("  documents table already exists, skipping...")
        cursor.execute("SELECT COUNT(*) FROM documents")
        return cursor.fetchone()[0]

    # Create documents table
    cursor.execute("""
        CREATE TABLE documents (
            doc_id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT UNIQUE NOT NULL,
            filepath TEXT NOT NULL,
            equipment TEXT NOT NULL,
            doc_type TEXT NOT NULL,
            page_count INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Populate from pages table (distinct documents)
    cursor.execute("""
        INSERT INTO documents (filename, filepath, equipment, doc_type, page_count)
        SELECT
            filename,
            filepath,
            equipment,
            doc_type,
            COUNT(*) as page_count
        FROM pages
        GROUP BY filename
        ORDER BY equipment, filename
    """)

    # Create indexes (prefixed to avoid collision with pages table indexes)
    cursor.execute("CREATE INDEX idx_documents_equipment ON documents(equipment)")
    cursor.execute("CREATE INDEX idx_documents_doc_type ON documents(doc_type)")
    cursor.execute("CREATE INDEX idx_documents_filename ON documents(filename)")

    conn.commit()

    cursor.execute("SELECT COUNT(*) FROM documents")
    count = cursor.fetchone()[0]
    print(f"  Created documents table with {count} documents")
    return count


def create_tags_table(conn: sqlite3.Connection) -> None:
    """Create tags table for tag definitions."""
    cursor = conn.cursor()

    # Check if table exists
    cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type='table' AND name='tags'
    """)
    if cursor.fetchone():
        print("  tags table already exists, skipping...")
        return

    cursor.execute("""
        CREATE TABLE tags (
            tag_id INTEGER PRIMARY KEY AUTOINCREMENT,
            tag_name TEXT UNIQUE NOT NULL,
            tag_category TEXT NOT NULL,
            parent_tag_id INTEGER,
            description TEXT,
            sort_order INTEGER DEFAULT 0,
            FOREIGN KEY (parent_tag_id) REFERENCES tags(tag_id)
        )
    """)

    cursor.execute("CREATE INDEX idx_tags_category ON tags(tag_category)")
    cursor.execute("CREATE INDEX idx_tags_parent ON tags(parent_tag_id)")

    conn.commit()
    print("  Created tags table")


def create_document_tags_table(conn: sqlite3.Connection) -> None:
    """Create junction table for document-tag relationships."""
    cursor = conn.cursor()

    # Check if table exists
    cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type='table' AND name='document_tags'
    """)
    if cursor.fetchone():
        print("  document_tags table already exists, skipping...")
        return

    cursor.execute("""
        CREATE TABLE document_tags (
            doc_id INTEGER NOT NULL,
            tag_id INTEGER NOT NULL,
            tag_weight REAL DEFAULT 1.0,
            added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (doc_id, tag_id),
            FOREIGN KEY (doc_id) REFERENCES documents(doc_id) ON DELETE CASCADE,
            FOREIGN KEY (tag_id) REFERENCES tags(tag_id) ON DELETE CASCADE
        )
    """)

    cursor.execute("CREATE INDEX idx_doc_tags_tag ON document_tags(tag_id)")
    cursor.execute("CREATE INDEX idx_doc_tags_doc ON document_tags(doc_id)")

    conn.commit()
    print("  Created document_tags table")


def seed_tags(conn: sqlite3.Connection, keywords_path: Path) -> int:
    """
    Seed tags table from keywords.json.
    Returns number of tags created.
    """
    cursor = conn.cursor()

    # Check if already seeded
    cursor.execute("SELECT COUNT(*) FROM tags")
    if cursor.fetchone()[0] > 0:
        print("  Tags already seeded, skipping...")
        cursor.execute("SELECT COUNT(*) FROM tags")
        return cursor.fetchone()[0]

    # Load keywords
    with open(keywords_path) as f:
        keywords = json.load(f)

    tag_count = 0
    sort_order = 0

    # Insert system tags
    for tag_name, tag_data in keywords["systems"].items():
        cursor.execute("""
            INSERT INTO tags (tag_name, tag_category, description, sort_order)
            VALUES (?, ?, ?, ?)
        """, (
            tag_name,
            tag_data["category"],
            f"Keywords: {', '.join(tag_data['keywords'][:5])}...",
            sort_order
        ))
        tag_count += 1
        sort_order += 1

    # Insert cross-cutting tags
    for tag_name, tag_data in keywords["cross_cutting"].items():
        cursor.execute("""
            INSERT INTO tags (tag_name, tag_category, description, sort_order)
            VALUES (?, ?, ?, ?)
        """, (
            tag_name,
            tag_data["category"],
            f"Keywords: {', '.join(tag_data['keywords'][:5])}...",
            sort_order
        ))
        tag_count += 1
        sort_order += 1

    conn.commit()
    print(f"  Seeded {tag_count} tags")
    return tag_count


def create_schema_version_table(conn: sqlite3.Connection) -> None:
    """Track schema version for future migrations."""
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS schema_version (
            version TEXT PRIMARY KEY,
            applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        INSERT OR IGNORE INTO schema_version (version) VALUES (?)
    """, (SCHEMA_VERSION,))

    conn.commit()


def run_migration(db_path: Path, keywords_path: Path, seed: bool = True) -> dict:
    """
    Run the full tagging schema migration.

    Args:
        db_path: Path to engine_search.db
        keywords_path: Path to keywords.json
        seed: Whether to seed tags from keywords.json

    Returns:
        Dict with migration stats
    """
    print("=" * 60)
    print("Subsystem Tagging Schema Migration")
    print("=" * 60)

    if not db_path.exists():
        raise FileNotFoundError(f"Database not found: {db_path}")

    conn = get_db_connection(db_path)

    try:
        print("\n1. Creating schema version table...")
        create_schema_version_table(conn)

        print("\n2. Creating documents table...")
        doc_count = create_documents_table(conn)

        print("\n3. Creating tags table...")
        create_tags_table(conn)

        print("\n4. Creating document_tags table...")
        create_document_tags_table(conn)

        tag_count = 0
        if seed and keywords_path.exists():
            print("\n5. Seeding tags from keywords.json...")
            tag_count = seed_tags(conn, keywords_path)

        print("\n" + "=" * 60)
        print("MIGRATION COMPLETE")
        print("=" * 60)
        print(f"\nDocuments: {doc_count}")
        print(f"Tags: {tag_count}")
        print(f"Schema version: {SCHEMA_VERSION}")

        return {
            "documents": doc_count,
            "tags": tag_count,
            "schema_version": SCHEMA_VERSION
        }

    finally:
        conn.close()


def main():
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Apply tagging schema to engine_search.db")
    parser.add_argument("--db", type=Path, default=Path("data/engine_search.db"),
                       help="Path to database")
    parser.add_argument("--keywords", type=Path, default=Path("data/keywords.json"),
                       help="Path to keywords.json")
    parser.add_argument("--no-seed", action="store_true",
                       help="Skip seeding tags")

    args = parser.parse_args()

    # Resolve paths relative to project root
    base_dir = Path(__file__).parent.parent.parent
    db_path = base_dir / args.db
    keywords_path = base_dir / args.keywords

    run_migration(db_path, keywords_path, seed=not args.no_seed)


if __name__ == "__main__":
    main()
