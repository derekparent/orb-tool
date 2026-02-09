"""
Manuals Search Service for Marine Engineering Hub

Handles PDF search, troubleshooting cards, and document authority.
Uses a separate database from the main ORB database.
"""

import json
import re
import sqlite3
import subprocess
import sys
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional
from html import escape

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

# Doc type boost multipliers for procedural queries
# Higher = better ranking (divides the BM25 score)
DOC_TYPE_BOOST = {
    "testing": 1.4,       # Best for procedural queries
    "disassembly": 1.3,   # Second best
    "service": 1.2,       # General service info
    "troubleshooting": 1.1,
    "systems": 1.0,
    "O&M": 0.9,           # Overview, less procedural
    "schematic": 0.8,     # Reference, rarely procedural
    "specifications": 0.8,
    "special-instructions": 1.0,
}

# Keywords that indicate procedural intent
PROCEDURAL_KEYWORDS = {
    "adjust", "adjustment", "adjusting", "set", "setting",
    "check", "checking", "test", "testing", "measure", "measuring",
    "replace", "replacing", "install", "installing", "remove", "removing",
    "procedure", "how to", "step", "clearance", "lash", "torque",
    "calibrate", "calibration", "timing", "alignment",
}

# Query expansion for acronyms, spelling variants, and synonyms.
ACRONYM_EXPANSIONS = {
    "tdc": ["top dead center", "top center", "top centre"],
    "ecm": ["engine control module", "engine control unit"],
    "ecu": ["engine control unit", "engine control module"],
    "o&m": ["operation and maintenance", "operations and maintenance"],
    "om": ["operation and maintenance", "operations and maintenance"],
    "jwac": ["jacket water aftercooler"],
    "scac": ["seawater charge air cooler", "sea water charge air cooler"],
    "heui": ["hydraulically actuated electronically controlled unit injector"],
    "meui": ["mechanically actuated electronically controlled unit injector"],
    "dpf": ["diesel particulate filter"],
    "scr": ["selective catalytic reduction"],
    "egr": ["exhaust gas recirculation"],
}

SPELLING_VARIANTS = {
    "labour": "labor",
    "centre": "center",
    "analyse": "analyze",
    "analysing": "analyzing",
    "cooland": "coolant",
}

SYNONYM_EXPANSIONS = {
    "turbo": ["turbocharger"],
    "turbocharger": ["turbo"],
    "schematic": ["wiring diagram", "electrical schematic"],
    "schematics": ["wiring diagram", "electrical schematics"],
    "wiring": ["wiring diagram", "schematic"],
    "aftercooler": ["scac", "jwac"],
}

PHRASE_SYNONYMS = {
    "top dead center": ["tdc", "top center", "top centre"],
    "top center": ["tdc", "top dead center", "top centre"],
    "top centre": ["tdc", "top dead center", "top center"],
    "valve lash": ["valve clearance", "valve adjustment"],
    "fuel system": ["fuel delivery", "fuel supply"],
    "fuel filter": ["fuel filtration"],
    "oil pressure": ["lube oil pressure"],
    "wiring diagram": ["schematic", "electrical schematic"],
}

# Stop words to strip from conversational queries before FTS5 search.
# FTS5 uses implicit AND, so "What is the valve lash procedure" requires
# ALL words including "What", "is", "the" — returning 0 results.
# Stripping these converts conversational input to keyword queries.
STOP_WORDS = frozenset({
    "a", "an", "the", "is", "are", "was", "were", "be", "been", "being",
    "what", "which", "who", "whom", "where", "when", "why", "how",
    "do", "does", "did", "have", "has", "had", "having",
    "can", "could", "would", "should", "shall", "will", "may", "might",
    "i", "me", "my", "we", "our", "you", "your", "it", "its",
    "this", "that", "these", "those",
    "of", "in", "on", "at", "to", "for", "with", "from", "by", "about",
    "if", "then", "so",
    "tell", "show", "find", "get", "give", "explain", "describe",
    "need", "want", "look", "help",
})

# Known compound phrases in marine engineering manuals.
# When adjacent tokens form a known phrase, we quote them for FTS5 phrase matching.
# This prevents "oil filter replacement" from matching any page with just "oil".
KNOWN_PHRASES = frozenset({
    "oil filter", "fuel filter", "oil cooler", "oil pressure",
    "fuel pressure", "fuel rack", "fuel system", "fuel pump",
    "fuel delivery", "fuel supply", "fuel injector",
    "valve lash", "valve clearance", "valve adjustment", "valve bridge",
    "valve cover", "valve guide", "valve seat", "valve spring",
    "jacket water", "charge air", "water pump", "water temperature",
    "turbo charger", "air filter", "air intake",
    "cylinder head", "cylinder block", "cylinder liner",
    "crankshaft seal", "main bearing", "connecting rod",
    "lube oil", "oil pan",
    "starting motor", "starting system",
    "exhaust manifold", "exhaust temperature",
    "engine control", "control module",
    "top dead center",
})


def get_manuals_db_path() -> Path:
    """Get path to manuals database."""
    # Look in data/ directory
    data_dir = Path(__file__).parent.parent.parent / "data"
    return data_dir / MANUALS_DB_FILE


def get_keywords_path() -> Path:
    """Get path to keywords.json."""
    data_dir = Path(__file__).parent.parent.parent / "data"
    return data_dir / "keywords.json"


def load_keywords() -> dict:
    """Load keywords dictionary for tag-aware ranking."""
    keywords_path = get_keywords_path()
    if not keywords_path.exists():
        return {}
    try:
        with open(keywords_path) as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


# =============================================================================
# Ranking Boost Functions
# =============================================================================

def _tokenize_query(query: str) -> list[str]:
    """Tokenize query into lowercase words, keeping model identifiers."""
    normalized = query.lower().replace("&", " and ")
    return re.findall(r"[a-z0-9]+(?:[./-][a-z0-9]+)*", normalized)


def _contains_fts_syntax(query: str) -> bool:
    """Detect if query contains advanced FTS5 syntax that shouldn't be expanded."""
    if any(char in query for char in ('"', "*", "(", ")", ":")):
        return True
    return bool(re.search(r"\b(AND|OR|NOT|NEAR)\b", query))


def _quote_if_phrase(term: str) -> str:
    """Quote term if it contains whitespace."""
    term = term.strip()
    if " " in term:
        return f'"{term}"'
    return term


def prepare_search_query(query: str) -> str:
    """
    Expand query with acronyms, spelling variants, and synonyms for FTS5.

    Avoids altering queries that already use advanced FTS5 syntax.
    """
    if not query.strip() or _contains_fts_syntax(query):
        return query

    query_lower = query.lower()
    tokens = _tokenize_query(query_lower)
    expansions: set[str] = set()

    for token in tokens:
        if token in ACRONYM_EXPANSIONS:
            expansions.update(ACRONYM_EXPANSIONS[token])
        if token in SPELLING_VARIANTS:
            expansions.add(SPELLING_VARIANTS[token])
        if token in SYNONYM_EXPANSIONS:
            expansions.update(SYNONYM_EXPANSIONS[token])

    for phrase, synonyms in PHRASE_SYNONYMS.items():
        if phrase in query_lower:
            expansions.update(synonyms)

    if len(tokens) >= 2:
        phrase = " ".join(tokens)
        expansions.add(phrase)

    expansions = {_quote_if_phrase(term) for term in expansions if term}

    if not expansions:
        return query

    # Tradeoff: broader OR expansion improves recall but can add false positives.
    expansion_clause = " OR ".join(sorted(expansions))
    return f"({query}) OR ({expansion_clause})"


def _tokenize_smart_query(query: str) -> list[str]:
    """Strip punctuation and stop words, returning content keywords.

    Preserves model numbers like C4.4, C18, 3516.
    Used by smart query pipeline for natural language queries.
    """
    cleaned = query.strip().rstrip("?!.")
    tokens = re.findall(r"[A-Za-z0-9]+(?:[./-][A-Za-z0-9]+)*", cleaned)
    keywords = [t for t in tokens if t.lower() not in STOP_WORDS]
    return keywords if keywords else []


def _detect_known_phrases(keywords: list[str]) -> list[str]:
    """Detect known compound phrases and quote them for FTS5.

    Scans adjacent keyword pairs (bigrams) against KNOWN_PHRASES.
    Matched pairs are quoted as FTS5 phrases; unmatched tokens pass through.

    Example:
        ["oil", "filter", "replacement"] → ['"oil filter"', "replacement"]
        ["3516", "valve", "lash"] → ["3516", '"valve lash"']
    """
    if len(keywords) < 2:
        return list(keywords)

    result: list[str] = []
    i = 0
    while i < len(keywords):
        if i + 1 < len(keywords):
            bigram = f"{keywords[i].lower()} {keywords[i + 1].lower()}"
            if bigram in KNOWN_PHRASES:
                result.append(f'"{keywords[i]} {keywords[i + 1]}"')
                i += 2
                continue
        result.append(keywords[i])
        i += 1
    return result


def prepare_smart_query(query: str) -> str:
    """Convert a conversational query into a precise FTS5 AND query.

    Pipeline:
      1. Strip punctuation and stop words
      2. Detect known compound phrases and quote them
      3. Return AND query (implicit AND via spaces)

    Used as first pass for search UI. If it returns too few results,
    the caller should fall back to prepare_broad_query().

    Examples:
        "How do I adjust valve lash?"
        → "adjust \"valve lash\""

        "valve lash"
        → "\"valve lash\""

        "3516 fuel rack"
        → "3516 \"fuel rack\""

        "turbocharger" → "turbocharger"

    Args:
        query: Natural language question from the user

    Returns:
        FTS5 query string using implicit AND with quoted phrases
    """
    keywords = _tokenize_smart_query(query)
    if not keywords:
        # No content keywords after stop-word removal → return original
        return query

    # Detect and quote known compound phrases
    phrased = _detect_known_phrases(keywords)

    # Join with spaces (implicit AND in FTS5)
    return " ".join(phrased)


def prepare_broad_query(query: str) -> str:
    """Convert a conversational query into a broad FTS5 OR query.

    Used as fallback when the precise AND query returns too few results.
    OR gives broad recall; BM25 ranks pages with more terms higher.

    Examples:
        "How do I adjust valve lash?"
        → "\"valve lash\" OR valve OR lash OR adjust"

    Args:
        query: Natural language question from the user

    Returns:
        FTS5 OR query with quoted phrases and individual words
    """
    keywords = _tokenize_smart_query(query)
    if not keywords:
        return query

    # Detect phrases for the OR list too
    phrased = _detect_known_phrases(keywords)

    # Build OR terms: include both quoted phrases and individual words
    or_terms: list[str] = list(phrased)
    for kw in keywords:
        if kw not in or_terms:
            or_terms.append(kw)

    return " OR ".join(or_terms)


def _is_procedural_query(query: str) -> bool:
    """Check if query indicates procedural intent."""
    query_words = set(_tokenize_query(query))
    return bool(query_words & PROCEDURAL_KEYWORDS)


def _phrase_appears_in_content(phrase: str, content: str) -> bool:
    """Check if multi-word phrase appears together in content."""
    return phrase.lower() in content.lower()


def _get_matching_tags_for_query(query: str, keywords_data: dict) -> set[str]:
    """
    Find which system tags are relevant based on query keywords.
    
    Returns set of tag names that have matching keywords.
    """
    if not keywords_data:
        return set()
    
    query_lower = query.lower()
    query_words = set(_tokenize_query(query_lower))
    matching_tags = set()
    
    systems = keywords_data.get("systems", {})
    for tag_name, tag_info in systems.items():
        tag_keywords = tag_info.get("keywords", [])
        # Check if any query word matches a keyword (partial match)
        for qword in query_words:
            for kw in tag_keywords:
                if qword in kw or kw in query_lower:
                    matching_tags.add(tag_name)
                    break
    
    return matching_tags


def _calculate_ranking_boost(
    result: dict,
    query: str,
    is_procedural: bool,
    matching_tags: set[str],
    content: str,
) -> float:
    """
    Calculate combined ranking boost multiplier.
    
    Higher multiplier = better ranking (divides BM25 score).
    
    Args:
        result: Search result dict
        query: Original search query
        is_procedural: Whether query has procedural intent
        matching_tags: Set of tag names that match query keywords
        content: Page content for phrase matching
    
    Returns:
        Combined boost multiplier (>= 1.0)
    """
    boost = 1.0
    
    # 1. Phrase boost: multi-word query appears as phrase in content
    # Filter out FTS5 boolean operators before phrase matching
    query_words = [w for w in query.lower().split() if w.upper() not in ("AND", "OR", "NOT")]
    if len(query_words) >= 2:
        phrase = " ".join(query_words).strip('"')
        if _phrase_appears_in_content(phrase, content):
            boost *= 1.5  # 50% boost for phrase match
    
    # 2. Doc type boost: for procedural queries, boost testing/disassembly docs
    if is_procedural:
        doc_type = result.get("doc_type", "")
        doc_boost = DOC_TYPE_BOOST.get(doc_type, 1.0)
        boost *= doc_boost
    
    # 3. Tag-aware boost: if query matches tag keywords, boost docs with that tag
    if matching_tags:
        result_tags = set(result.get("tags", []))
        matching_result_tags = matching_tags & result_tags
        if matching_result_tags:
            # 20% boost per matching tag, capped at 60%
            tag_boost = 1.0 + min(0.2 * len(matching_result_tags), 0.6)
            boost *= tag_boost
    
    return boost


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
    """Format text snippet for display, showing context around match with highlighted terms."""
    # Normalize whitespace
    text = " ".join(text.split())

    query_lower = query.lower().strip('"')
    text_lower = text.lower()

    # Get query words, excluding boolean operators
    query_words = [w for w in query_lower.split() if w.upper() not in ("AND", "OR", "NOT")]
    
    # Find best position (earliest match)
    best_pos = len(text)
    for word in query_words:
        pos = text_lower.find(word.rstrip("*"))
        if pos != -1 and pos < best_pos:
            best_pos = pos

    if best_pos == len(text):
        best_pos = 0

    # Extract snippet with context
    start = max(0, best_pos - 50)
    end = min(len(text), start + max_length)

    if start > 0:
        start = text.find(" ", start) + 1

    snippet = text[start:end]

    if start > 0:
        snippet = "..." + snippet
    if end < len(text):
        snippet = snippet.rsplit(" ", 1)[0] + "..."

    # Highlight query terms using placeholders, then escape HTML
    # Use null byte markers that won't appear in text and won't be affected by HTML escaping
    MARK_START = "\x00MS\x00"
    MARK_END = "\x00ME\x00"
    
    for word in query_words:
        word_clean = word.rstrip("*")
        if word_clean:
            # Case-insensitive replacement while preserving original case
            pattern = re.compile(re.escape(word_clean), re.IGNORECASE)
            snippet = pattern.sub(lambda m: f"{MARK_START}{m.group()}{MARK_END}", snippet)
    
    # Now escape HTML (this won't affect our null-byte markers)
    snippet = escape(snippet)
    
    # Replace markers with actual <mark> tags
    snippet = snippet.replace(MARK_START, "<mark>").replace(MARK_END, "</mark>")

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
        fts_query = prepare_search_query(query)

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
            params = [fts_query] + params + systems + [fetch_limit]
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
            params = [fts_query] + params + [fetch_limit]

        cursor.execute(sql, params)
        rows = cursor.fetchall()

        # Initialize authority table if needed
        _init_authority_table(conn)

        # Pre-compute ranking boost parameters
        is_procedural = _is_procedural_query(query)
        keywords_data = load_keywords()
        matching_tags = _get_matching_tags_for_query(query, keywords_data)

        results = []
        for row in rows:
            base_score = abs(row["score"])
            filepath = row["filepath"]
            content = row["content"]

            authority_level = _get_authority_for_filepath(conn, filepath)
            authority_label = AUTHORITY_LABELS.get(authority_level, "")

            # Start with base score
            adjusted_score = base_score

            # Get tags for this document (needed for tag-aware boost)
            doc_tags = get_document_tags(row["filename"])

            # Build result dict first (needed for boost calculation)
            result = {
                "base_score": base_score,
                "filepath": filepath,
                "filename": row["filename"],
                "equipment": row["equipment"],
                "doc_type": row["doc_type"],
                "page_num": row["page_num"],
                "snippet": format_snippet(content, query),
                "authority": authority_level,
                "authority_label": authority_label,
                "tags": doc_tags,
            }

            # Apply authority boost if enabled
            if boost_primary:
                authority_multiplier = AUTHORITY_LEVELS.get(authority_level, 1.0)
                adjusted_score = adjusted_score / authority_multiplier

            # Apply ranking boosts (phrase, doc_type, tag-aware)
            ranking_boost = _calculate_ranking_boost(
                result, query, is_procedural, matching_tags, content
            )
            adjusted_score = adjusted_score / ranking_boost

            result["score"] = adjusted_score
            results.append(result)

        # Always sort by adjusted score (lower = better in BM25)
        results.sort(key=lambda x: x["score"])

        return results[:limit]

    except sqlite3.OperationalError:
        return []
    finally:
        conn.close()


# =============================================================================
# LLM Context Functions
# =============================================================================

def get_context_for_llm(
    query: str,
    equipment: Optional[str] = None,
    limit: int = 10,
) -> list[dict]:
    """
    Retrieve search results for LLM context via search_manuals().

    Single search path: both the search UI and LLM use the same
    ranking (authority boost, phrase boost, tag-aware boost).
    Returns summaries (snippets) for triage, not full page content.

    Args:
        query: User's question
        equipment: Optional equipment filter
        limit: Max results to return

    Returns:
        List of dicts with: filename, page_num, equipment, doc_type,
        snippet, authority, score
    """
    results = search_manuals(
        query, equipment=equipment, boost_primary=True, limit=limit
    )
    return [
        {
            "filename": r["filename"],
            "page_num": r["page_num"],
            "equipment": r["equipment"],
            "doc_type": r["doc_type"],
            "snippet": r["snippet"],
            "authority": r["authority"],
            "score": r["score"],
        }
        for r in results
    ]


def get_pages_content(
    filename: str,
    page_nums: list[int],
) -> list[dict]:
    """
    Fetch full page content by filename and page numbers.

    Used for deep-dive phase: after the LLM triages search results
    and the user picks specific pages to examine.

    Args:
        filename: Document filename (e.g. 'kenr5403-00_3516-testing-&-adjusting')
        page_nums: List of page numbers to fetch

    Returns:
        List of dicts with: content, filename, page_num, equipment, doc_type
    """
    if not page_nums:
        return []

    conn = load_manuals_database()
    if not conn:
        return []

    try:
        cursor = conn.cursor()
        placeholders = ",".join("?" * len(page_nums))

        # Exact match first
        cursor.execute(
            f"""
            SELECT filepath, filename, equipment, doc_type, page_num, content
            FROM pages
            WHERE filename = ? AND page_num IN ({placeholders})
            ORDER BY page_num
            """,
            [filename] + list(page_nums),
        )
        rows = cursor.fetchall()

        # Fallback: LLM abbreviates filenames (drops .pdf, middle segments).
        # Match on doc ID prefix (e.g. "kenr5403-11-00") which is unique.
        if not rows:
            doc_id = re.match(r"^[a-z]+\d+", filename)
            if doc_id:
                cursor.execute(
                    f"""
                    SELECT filepath, filename, equipment, doc_type, page_num, content
                    FROM pages
                    WHERE filename LIKE ? AND page_num IN ({placeholders})
                    ORDER BY page_num
                    """,
                    [f"{doc_id.group(0)}%"] + list(page_nums),
                )
                rows = cursor.fetchall()

        return [
            {
                "content": row["content"].strip(),
                "filename": row["filename"],
                "page_num": row["page_num"],
                "equipment": row["equipment"],
                "doc_type": row["doc_type"],
            }
            for row in rows
        ]
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
        fts_query = prepare_search_query(query)

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
        """, [fts_query] + params + [limit])

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
