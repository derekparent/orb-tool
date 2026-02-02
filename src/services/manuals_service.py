"""
Manuals Search Service for Marine Engineering Hub

Handles PDF search, troubleshooting cards, and document authority.
Uses a separate database from the main ORB database.
"""

import json
import sqlite3
import subprocess
import sys
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

# Database file (separate from main ORB database)
MANUALS_DB_FILE = "engine_search.db"

# Equipment and doc type options
EQUIPMENT_OPTIONS = ["All", "3516", "C18", "C32", "C4.4"]
DOC_TYPE_OPTIONS = [
    "All", "O&M", "troubleshooting", "schematic", "service",
    "testing", "disassembly", "specifications", "systems",
    "special-instructions"
]
SUBSYSTEM_CHOICES = ["fuel", "lube", "cooling", "controls", "starting", "alarms", "electrical", "exhaust"]

# System tags (from tagging schema)
SYSTEM_TAGS = [
    "Fuel System", "Air Intake System", "Cooling System", "Lubrication System",
    "Exhaust System", "Starting System", "Electrical/Controls",
    "Cylinder Block/Internals", "Cylinder Head/Valvetrain",
    "Safety/Alarms", "General/Maintenance"
]

# Authority levels with their search score multipliers
AUTHORITY_LEVELS = {
    "primary": 1.5,
    "secondary": 1.0,
    "mention": 0.7,
    "unset": 1.0,
}

AUTHORITY_LABELS = {
    "primary": "[PRIMARY]",
    "secondary": "[SECONDARY]",
    "mention": "[MENTION]",
    "unset": "",
}


def get_manuals_db_path() -> Path:
    """Get path to manuals database."""
    # Look in data/ directory
    data_dir = Path(__file__).parent.parent.parent / "data"
    return data_dir / MANUALS_DB_FILE


def load_manuals_database() -> Optional[sqlite3.Connection]:
    """
    Load the manuals SQLite database.

    Returns:
        SQLite connection with row_factory set, or None if not found
    """
    db_path = get_manuals_db_path()

    if not db_path.exists():
        return None

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def is_manuals_db_available() -> bool:
    """Check if manuals database exists."""
    return get_manuals_db_path().exists()


# =============================================================================
# Tag Functions
# =============================================================================

def get_tag_facets(equipment: Optional[str] = None) -> list[dict]:
    """
    Get tag counts for faceted search.

    Args:
        equipment: Optional equipment filter

    Returns:
        List of dicts with tag_name, tag_category, doc_count
    """
    conn = load_manuals_database()
    if not conn:
        return []

    try:
        cursor = conn.cursor()

        # Check if tags table exists
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='tags'
        """)
        if not cursor.fetchone():
            return []

        sql = """
            SELECT t.tag_name, t.tag_category, COUNT(DISTINCT d.doc_id) as doc_count
            FROM tags t
            JOIN document_tags dt ON t.tag_id = dt.tag_id
            JOIN documents d ON dt.doc_id = d.doc_id
            WHERE t.tag_category = 'system'
        """
        params = []

        if equipment:
            sql += " AND d.equipment = ?"
            params.append(equipment)

        sql += " GROUP BY t.tag_id ORDER BY doc_count DESC"

        cursor.execute(sql, params)
        return [
            {
                "tag_name": row["tag_name"],
                "tag_category": row["tag_category"],
                "doc_count": row["doc_count"]
            }
            for row in cursor.fetchall()
        ]

    except sqlite3.OperationalError:
        return []
    finally:
        conn.close()


def get_document_tags(filename: str) -> list[str]:
    """Get tags for a specific document by filename."""
    conn = load_manuals_database()
    if not conn:
        return []

    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT t.tag_name
            FROM tags t
            JOIN document_tags dt ON t.tag_id = dt.tag_id
            JOIN documents d ON dt.doc_id = d.doc_id
            WHERE d.filename = ?
            ORDER BY dt.tag_weight DESC
        """, (filename,))
        return [row["tag_name"] for row in cursor.fetchall()]
    except sqlite3.OperationalError:
        return []
    finally:
        conn.close()


# =============================================================================
# Search Functions
# =============================================================================

def format_snippet(text: str, query: str, max_length: int = 200) -> str:
    """Format text snippet for display, showing context around match."""
    text = " ".join(text.split())

    query_lower = query.lower().strip('"')
    text_lower = text.lower()

    query_words = query_lower.split()
    best_pos = len(text)
    for word in query_words:
        if word.upper() in ("AND", "OR", "NOT"):
            continue
        pos = text_lower.find(word.rstrip("*"))
        if pos != -1 and pos < best_pos:
            best_pos = pos

    if best_pos == len(text):
        best_pos = 0

    start = max(0, best_pos - 50)
    end = min(len(text), start + max_length)

    if start > 0:
        start = text.find(" ", start) + 1

    snippet = text[start:end]

    if start > 0:
        snippet = "..." + snippet
    if end < len(text):
        snippet = snippet.rsplit(" ", 1)[0] + "..."

    return snippet


def search_manuals(
    query: str,
    equipment: Optional[str] = None,
    doc_type: Optional[str] = None,
    systems: Optional[list[str]] = None,
    limit: int = 50,
    boost_primary: bool = False,
) -> list[dict]:
    """
    Execute search query against the FTS5 index.

    Args:
        query: Search query string (supports FTS5 syntax)
        equipment: Filter by equipment (3516, C18, C32, C4.4)
        doc_type: Filter by document type
        systems: Filter by subsystem tags (e.g., ["Fuel System", "Cooling System"])
        limit: Max results to return
        boost_primary: If True, apply authority-based score multipliers

    Returns:
        List of result dicts with doc info and snippets
    """
    conn = load_manuals_database()
    if not conn:
        return []

    try:
        cursor = conn.cursor()

        where_parts = []
        params = []

        if equipment:
            where_parts.append("p.equipment = ?")
            params.append(equipment)
        if doc_type:
            where_parts.append("p.doc_type = ?")
            params.append(doc_type)

        where_clause = " AND ".join(where_parts) if where_parts else "1=1"

        fetch_limit = limit * 3 if boost_primary else limit

        # Build base query
        if systems:
            # Join with tags to filter by system
            placeholders = ",".join("?" * len(systems))
            sql = f"""
                SELECT DISTINCT
                    p.filepath,
                    p.filename,
                    p.equipment,
                    p.doc_type,
                    p.page_num,
                    p.content,
                    bm25(pages_fts) as score
                FROM pages_fts
                JOIN pages p ON pages_fts.rowid = p.id
                JOIN documents d ON p.filename = d.filename
                JOIN document_tags dt ON d.doc_id = dt.doc_id
                JOIN tags t ON dt.tag_id = t.tag_id
                WHERE pages_fts MATCH ?
                AND {where_clause}
                AND t.tag_name IN ({placeholders})
                ORDER BY bm25(pages_fts)
                LIMIT ?
            """
            params = [query] + params + systems + [fetch_limit]
        else:
            sql = f"""
                SELECT
                    p.filepath,
                    p.filename,
                    p.equipment,
                    p.doc_type,
                    p.page_num,
                    p.content,
                    bm25(pages_fts) as score
                FROM pages_fts
                JOIN pages p ON pages_fts.rowid = p.id
                WHERE pages_fts MATCH ?
                AND {where_clause}
                ORDER BY bm25(pages_fts)
                LIMIT ?
            """
            params = [query] + params + [fetch_limit]

        cursor.execute(sql, params)
        rows = cursor.fetchall()

        # Initialize authority table if needed
        _init_authority_table(conn)

        results = []
        for row in rows:
            base_score = abs(row["score"])
            filepath = row["filepath"]

            authority_level = _get_authority_for_filepath(conn, filepath)
            authority_label = AUTHORITY_LABELS.get(authority_level, "")

            if boost_primary:
                multiplier = AUTHORITY_LEVELS.get(authority_level, 1.0)
                adjusted_score = base_score / multiplier
            else:
                adjusted_score = base_score

            # Get tags for this document
            doc_tags = get_document_tags(row["filename"])

            results.append({
                "score": adjusted_score,
                "base_score": base_score,
                "filepath": filepath,
                "filename": row["filename"],
                "equipment": row["equipment"],
                "doc_type": row["doc_type"],
                "page_num": row["page_num"],
                "snippet": format_snippet(row["content"], query),
                "authority": authority_level,
                "authority_label": authority_label,
                "tags": doc_tags,
            })

        if boost_primary:
            results.sort(key=lambda x: x["score"])

        return results[:limit]

    except sqlite3.OperationalError:
        return []
    finally:
        conn.close()


# =============================================================================
# Cards Functions
# =============================================================================

def _init_cards_table(conn: sqlite3.Connection) -> None:
    """Initialize cards table if it doesn't exist."""
    cursor = conn.cursor()

    cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type='table' AND name='cards'
    """)
    if cursor.fetchone():
        return

    cursor.execute("""
        CREATE TABLE cards (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            equipment TEXT NOT NULL,
            subsystem TEXT,
            steps TEXT NOT NULL,
            sources TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """)

    cursor.execute("""
        CREATE VIRTUAL TABLE cards_fts USING fts5(
            title,
            steps,
            content='cards',
            content_rowid='rowid',
            tokenize='porter unicode61'
        )
    """)

    cursor.execute("""
        CREATE TRIGGER cards_ai AFTER INSERT ON cards BEGIN
            INSERT INTO cards_fts(rowid, title, steps)
            VALUES (new.rowid, new.title, new.steps);
        END
    """)

    cursor.execute("""
        CREATE TRIGGER cards_ad AFTER DELETE ON cards BEGIN
            INSERT INTO cards_fts(cards_fts, rowid, title, steps)
            VALUES ('delete', old.rowid, old.title, old.steps);
        END
    """)

    cursor.execute("""
        CREATE TRIGGER cards_au AFTER UPDATE ON cards BEGIN
            INSERT INTO cards_fts(cards_fts, rowid, title, steps)
            VALUES ('delete', old.rowid, old.title, old.steps);
            INSERT INTO cards_fts(rowid, title, steps)
            VALUES (new.rowid, new.title, new.steps);
        END
    """)

    cursor.execute("CREATE INDEX idx_cards_equipment ON cards(equipment)")
    cursor.execute("CREATE INDEX idx_cards_subsystem ON cards(subsystem)")

    conn.commit()


def _row_to_card(row: sqlite3.Row) -> dict:
    """Convert a database row to a card dict."""
    return {
        "id": row["id"],
        "title": row["title"],
        "equipment": row["equipment"],
        "subsystem": row["subsystem"],
        "steps": row["steps"],
        "sources": json.loads(row["sources"]) if row["sources"] else [],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def search_cards(
    query: str,
    equipment: Optional[str] = None,
    limit: int = 20,
) -> list[dict]:
    """Search troubleshooting cards using FTS5."""
    conn = load_manuals_database()
    if not conn:
        return []

    try:
        _init_cards_table(conn)
        cursor = conn.cursor()

        where_parts = []
        params = []

        if equipment:
            where_parts.append("c.equipment = ?")
            params.append(equipment)

        where_clause = " AND ".join(where_parts) if where_parts else "1=1"

        cursor.execute(f"""
            SELECT
                c.*,
                bm25(cards_fts) as score
            FROM cards_fts
            JOIN cards c ON cards_fts.rowid = c.rowid
            WHERE cards_fts MATCH ?
            AND {where_clause}
            ORDER BY bm25(cards_fts)
            LIMIT ?
        """, [query] + params + [limit])

        results = []
        for row in cursor.fetchall():
            card = _row_to_card(row)
            card["score"] = abs(row["score"])
            results.append(card)

        return results

    except sqlite3.OperationalError:
        return []
    finally:
        conn.close()


def get_card(card_id: str) -> Optional[dict]:
    """Get a card by ID."""
    conn = load_manuals_database()
    if not conn:
        return None

    try:
        _init_cards_table(conn)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM cards WHERE id LIKE ?", (f"{card_id}%",))
        row = cursor.fetchone()
        return _row_to_card(row) if row else None
    finally:
        conn.close()


def list_cards(
    equipment: Optional[str] = None,
    subsystem: Optional[str] = None,
) -> list[dict]:
    """List all cards, optionally filtered."""
    conn = load_manuals_database()
    if not conn:
        return []

    try:
        _init_cards_table(conn)
        cursor = conn.cursor()

        where_parts = []
        params = []

        if equipment:
            where_parts.append("equipment = ?")
            params.append(equipment)
        if subsystem:
            where_parts.append("subsystem = ?")
            params.append(subsystem)

        where_clause = " AND ".join(where_parts) if where_parts else "1=1"

        cursor.execute(f"""
            SELECT * FROM cards
            WHERE {where_clause}
            ORDER BY updated_at DESC
        """, params)

        return [_row_to_card(row) for row in cursor.fetchall()]
    finally:
        conn.close()


# =============================================================================
# Authority Functions
# =============================================================================

def _init_authority_table(conn: sqlite3.Connection) -> None:
    """Initialize doc_authority table if it doesn't exist."""
    cursor = conn.cursor()

    cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type='table' AND name='doc_authority'
    """)
    if cursor.fetchone():
        return

    cursor.execute("""
        CREATE TABLE doc_authority (
            filepath TEXT PRIMARY KEY,
            authority_level TEXT NOT NULL DEFAULT 'unset',
            notes TEXT,
            updated_at TEXT NOT NULL
        )
    """)

    cursor.execute("CREATE INDEX idx_authority_level ON doc_authority(authority_level)")
    conn.commit()


def _get_authority_for_filepath(conn: sqlite3.Connection, filepath: str) -> str:
    """Get authority level for a filepath."""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT authority_level FROM doc_authority WHERE filepath = ?
    """, (filepath,))
    row = cursor.fetchone()
    return row["authority_level"] if row else "unset"


# =============================================================================
# Stats Functions
# =============================================================================

def get_index_stats() -> dict:
    """Get statistics about the index."""
    conn = load_manuals_database()
    if not conn:
        return {
            "available": False,
            "total_pages": 0,
            "total_files": 0,
            "total_cards": 0,
        }

    try:
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) FROM pages")
        total_pages = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(DISTINCT filepath) FROM pages")
        total_files = cursor.fetchone()[0]

        total_cards = 0
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='cards'
        """)
        if cursor.fetchone():
            cursor.execute("SELECT COUNT(*) FROM cards")
            total_cards = cursor.fetchone()[0]

        return {
            "available": True,
            "total_pages": total_pages,
            "total_files": total_files,
            "total_cards": total_cards,
        }
    finally:
        conn.close()


# =============================================================================
# Search Logging
# =============================================================================

def _init_search_log_table(conn: sqlite3.Connection) -> None:
    """Initialize search_log table."""
    cursor = conn.cursor()

    cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type='table' AND name='search_log'
    """)
    if cursor.fetchone():
        return

    cursor.execute("""
        CREATE TABLE search_log (
            id INTEGER PRIMARY KEY,
            timestamp TEXT DEFAULT (datetime('now')),
            query TEXT,
            equipment_filter TEXT,
            doc_type_filter TEXT,
            boost_primary INTEGER,
            result_count INTEGER,
            source TEXT
        )
    """)

    cursor.execute("CREATE INDEX idx_search_log_timestamp ON search_log(timestamp)")
    cursor.execute("CREATE INDEX idx_search_log_query ON search_log(query)")
    conn.commit()


def log_search(
    query: str,
    result_count: int,
    equipment_filter: Optional[str] = None,
    doc_type_filter: Optional[str] = None,
    boost_primary: bool = False,
) -> None:
    """Log a search query for analytics."""
    conn = load_manuals_database()
    if not conn:
        return

    try:
        _init_search_log_table(conn)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO search_log
            (query, equipment_filter, doc_type_filter, boost_primary, result_count, source)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (query, equipment_filter, doc_type_filter, 1 if boost_primary else 0, result_count, "web"))
        conn.commit()
    finally:
        conn.close()


# =============================================================================
# PDF Viewer (macOS only)
# =============================================================================

def open_pdf_to_page(filepath: str, page_num: int) -> bool:
    """
    Open PDF at specific page using Preview (macOS).

    Returns True if successful.
    """
    if sys.platform != "darwin":
        return False

    try:
        script = f'''
        tell application "Preview"
            activate
            open POSIX file "{filepath}"
            delay 0.5
            tell application "System Events"
                keystroke "g" using {{option down, command down}}
                delay 0.2
                keystroke "{page_num}"
                delay 0.1
                keystroke return
            end tell
        end tell
        '''
        subprocess.run(["osascript", "-e", script], check=True, capture_output=True)
        return True
    except Exception:
        # Fallback: just open the file
        try:
            subprocess.run(["open", filepath], check=True)
            return True
        except Exception:
            return False
