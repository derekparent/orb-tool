#!/usr/bin/env python3
"""
Auto-Tagger for Manuals Search

Scans document content for keywords and suggests/applies tags.
Uses keyword-assisted approach: automated suggestions + manual override.

Usage:
    python -m src.services.auto_tagger [--apply] [--threshold 3]
"""

import json
import sqlite3
from collections import defaultdict
from pathlib import Path
from typing import Optional


def get_db_connection(db_path: Path) -> sqlite3.Connection:
    """Get database connection with row factory."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def load_keywords(keywords_path: Path) -> dict:
    """Load and flatten keywords for matching."""
    with open(keywords_path) as f:
        data = json.load(f)

    # Flatten to tag_name -> keywords list
    keywords = {}
    for tag_name, tag_data in data.get("systems", {}).items():
        keywords[tag_name] = [k.lower() for k in tag_data.get("keywords", [])]
    for tag_name, tag_data in data.get("cross_cutting", {}).items():
        keywords[tag_name] = [k.lower() for k in tag_data.get("keywords", [])]

    return keywords


def get_document_content(conn: sqlite3.Connection, doc_id: int) -> str:
    """Get concatenated content for a document from pages table."""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT d.filename, GROUP_CONCAT(p.content, ' ') as full_content
        FROM documents d
        JOIN pages p ON d.filename = p.filename
        WHERE d.doc_id = ?
        GROUP BY d.doc_id
    """, (doc_id,))
    row = cursor.fetchone()
    return row["full_content"].lower() if row else ""


def score_document(content: str, keywords: dict) -> dict[str, int]:
    """
    Score document content against keyword dictionary.
    Returns dict of tag_name -> match_count.
    """
    scores = {}
    for tag_name, terms in keywords.items():
        matches = sum(1 for term in terms if term in content)
        if matches > 0:
            scores[tag_name] = matches
    return scores


def suggest_tags(
    scores: dict[str, int],
    threshold: int = 2,
    max_tags: int = 4
) -> list[tuple[str, int, float]]:
    """
    Suggest tags based on keyword scores.

    Args:
        scores: Dict of tag_name -> match_count
        threshold: Minimum matches to suggest
        max_tags: Maximum number of tags to suggest

    Returns:
        List of (tag_name, match_count, weight) tuples
    """
    # Filter by threshold and sort by score
    suggestions = [
        (tag, count)
        for tag, count in scores.items()
        if count >= threshold
    ]
    suggestions.sort(key=lambda x: x[1], reverse=True)

    # Calculate weights (1.0 for top tag, scaled down for others)
    result = []
    for i, (tag, count) in enumerate(suggestions[:max_tags]):
        # Primary tag gets 1.0, others get 0.8, 0.6, 0.4
        weight = max(0.4, 1.0 - (i * 0.2))
        result.append((tag, count, weight))

    return result


def get_existing_tags(conn: sqlite3.Connection, doc_id: int) -> list[str]:
    """Get existing tags for a document."""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT t.tag_name
        FROM document_tags dt
        JOIN tags t ON dt.tag_id = t.tag_id
        WHERE dt.doc_id = ?
    """, (doc_id,))
    return [row["tag_name"] for row in cursor.fetchall()]


def apply_tags(
    conn: sqlite3.Connection,
    doc_id: int,
    tags: list[tuple[str, float]]
) -> int:
    """
    Apply tags to a document.

    Args:
        conn: Database connection
        doc_id: Document ID
        tags: List of (tag_name, weight) tuples

    Returns:
        Number of tags applied
    """
    cursor = conn.cursor()
    applied = 0

    for tag_name, weight in tags:
        # Get tag_id
        cursor.execute("SELECT tag_id FROM tags WHERE tag_name = ?", (tag_name,))
        row = cursor.fetchone()
        if not row:
            continue

        tag_id = row["tag_id"]

        # Insert or update
        cursor.execute("""
            INSERT OR REPLACE INTO document_tags (doc_id, tag_id, tag_weight)
            VALUES (?, ?, ?)
        """, (doc_id, tag_id, weight))
        applied += 1

    conn.commit()
    return applied


def run_auto_tagger(
    db_path: Path,
    keywords_path: Path,
    threshold: int = 2,
    apply: bool = False,
    verbose: bool = True
) -> dict:
    """
    Run auto-tagger on all documents.

    Args:
        db_path: Path to database
        keywords_path: Path to keywords.json
        threshold: Minimum keyword matches to suggest tag
        apply: If True, apply suggested tags to database
        verbose: Print progress

    Returns:
        Dict with stats and suggestions
    """
    conn = get_db_connection(db_path)
    keywords = load_keywords(keywords_path)

    cursor = conn.cursor()
    cursor.execute("""
        SELECT doc_id, filename, equipment, doc_type, page_count
        FROM documents
        ORDER BY equipment, filename
    """)
    documents = cursor.fetchall()

    results = {
        "documents": len(documents),
        "tagged": 0,
        "skipped": 0,
        "suggestions": [],
        "by_equipment": defaultdict(int),
        "by_tag": defaultdict(int)
    }

    if verbose:
        print("=" * 70)
        print("Auto-Tagger: Keyword-Assisted Document Tagging")
        print("=" * 70)
        print(f"Documents: {len(documents)}")
        print(f"Threshold: {threshold} keyword matches")
        print(f"Mode: {'APPLY' if apply else 'DRY RUN'}")
        print("=" * 70)

    for doc in documents:
        doc_id = doc["doc_id"]
        filename = doc["filename"]
        equipment = doc["equipment"]

        # Check existing tags
        existing = get_existing_tags(conn, doc_id)
        if existing and not apply:
            results["skipped"] += 1
            continue

        # Get content and score
        content = get_document_content(conn, doc_id)
        if not content:
            if verbose:
                print(f"  SKIP: {filename} (no content)")
            results["skipped"] += 1
            continue

        scores = score_document(content, keywords)
        suggestions = suggest_tags(scores, threshold=threshold)

        if not suggestions:
            if verbose:
                print(f"  SKIP: {filename} (no matches above threshold)")
            results["skipped"] += 1
            continue

        # Record suggestion
        doc_result = {
            "doc_id": doc_id,
            "filename": filename,
            "equipment": equipment,
            "existing_tags": existing,
            "suggested_tags": [(t, c, w) for t, c, w in suggestions]
        }
        results["suggestions"].append(doc_result)

        if verbose:
            tag_str = ", ".join([f"{t}({c})" for t, c, _ in suggestions])
            print(f"  {equipment}/{filename[:40]:<40} -> {tag_str}")

        # Apply if requested
        if apply:
            tags_to_apply = [(t, w) for t, _, w in suggestions]
            applied = apply_tags(conn, doc_id, tags_to_apply)
            results["tagged"] += 1
            results["by_equipment"][equipment] += 1
            for tag_name, _, _ in suggestions:
                results["by_tag"][tag_name] += 1

    conn.close()

    if verbose:
        print("\n" + "=" * 70)
        print("SUMMARY")
        print("=" * 70)
        print(f"Documents processed: {results['documents']}")
        print(f"Documents tagged: {results['tagged']}")
        print(f"Documents skipped: {results['skipped']}")

        if results["by_tag"]:
            print("\nTags applied:")
            for tag, count in sorted(results["by_tag"].items(), key=lambda x: -x[1]):
                print(f"  {tag}: {count}")

    return results


def main():
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Auto-tag documents using keyword matching"
    )
    parser.add_argument("--db", type=Path, default=Path("data/engine_search.db"),
                       help="Path to database")
    parser.add_argument("--keywords", type=Path, default=Path("data/keywords.json"),
                       help="Path to keywords.json")
    parser.add_argument("--threshold", type=int, default=2,
                       help="Minimum keyword matches to suggest tag (default: 2)")
    parser.add_argument("--apply", action="store_true",
                       help="Apply tags to database (default: dry run)")
    parser.add_argument("--quiet", action="store_true",
                       help="Suppress verbose output")

    args = parser.parse_args()

    # Resolve paths relative to project root
    base_dir = Path(__file__).parent.parent.parent
    db_path = base_dir / args.db
    keywords_path = base_dir / args.keywords

    run_auto_tagger(
        db_path,
        keywords_path,
        threshold=args.threshold,
        apply=args.apply,
        verbose=not args.quiet
    )


if __name__ == "__main__":
    main()
