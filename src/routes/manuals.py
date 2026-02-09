"""
Manuals Blueprint - PDF Search and Troubleshooting Cards

Routes for searching CAT engine documentation integrated into ORB tool.
"""

import re
import sqlite3
from pathlib import Path

from flask import Blueprint, render_template, request, jsonify, current_app
from flask_login import login_required

from app import limiter
from security import SecurityConfig
from services.manuals_service import (
    search_manuals,
    search_cards,
    get_card,
    list_cards,
    get_index_stats,
    get_tag_facets,
    load_manuals_database,
    log_search,
    open_pdf_to_page,
    is_manuals_db_available,
    prepare_smart_query,
    prepare_broad_query,
    EQUIPMENT_OPTIONS,
    DOC_TYPE_OPTIONS,
    SUBSYSTEM_CHOICES,
    SYSTEM_TAGS,
)

manuals_bp = Blueprint("manuals", __name__, url_prefix="/manuals")

# Pagination constant
PER_PAGE = 20


@manuals_bp.route("/")
@limiter.limit(SecurityConfig.RATE_LIMIT_PER_MINUTE)
@login_required
def search():
    """Main search page for manuals."""
    # Check if database is available
    if not is_manuals_db_available():
        return render_template(
            "manuals/search.html",
            db_available=False,
            query="",
            equipment="All",
            doc_type="All",
            systems=[],
            boost=False,
            results=[],
            card_results=[],
            error="Manuals database not found. Place engine_search.db in data/ folder.",
            equipment_options=EQUIPMENT_OPTIONS,
            doc_type_options=DOC_TYPE_OPTIONS,
            tag_facets=[],
        )

    query = request.args.get("q", "").strip()
    equipment = request.args.get("equipment", "All")
    doc_type = request.args.get("doc_type", "All")
    systems = request.args.getlist("system")  # Multiple checkbox values
    boost = request.args.get("boost", "0") == "1"

    # Pagination
    try:
        page = max(1, int(request.args.get("page", "1")))
    except ValueError:
        page = 1

    offset = (page - 1) * PER_PAGE

    # Convert "All" to None for search functions
    equipment_filter = None if equipment == "All" else equipment
    doc_type_filter = None if doc_type == "All" else doc_type
    systems_filter = systems if systems else None

    # Get tag facets for filter UI
    tag_facets = get_tag_facets(equipment=equipment_filter)

    results = []
    card_results = []
    error = None

    if query:
        try:
            # Two-pass search strategy with pagination:
            # Pass 1: Smart query with stop-word removal and phrase detection (AND)
            smart_query = prepare_smart_query(query)
            results = search_manuals(
                smart_query,
                equipment=equipment_filter,
                doc_type=doc_type_filter,
                systems=systems_filter,
                limit=PER_PAGE,
                boost_primary=boost,
                offset=offset
            )

            # Pass 2: If < 3 results on page 1, fallback to broad OR query
            if len(results) < 3 and page == 1:
                broad_query = prepare_broad_query(query)
                if broad_query != smart_query:
                    results = search_manuals(
                        broad_query,
                        equipment=equipment_filter,
                        doc_type=doc_type_filter,
                        systems=systems_filter,
                        limit=PER_PAGE,
                        boost_primary=boost,
                        offset=offset
                    )

            # Search cards using broad query for better recall (not paginated)
            card_query = prepare_broad_query(query)
            card_results = search_cards(card_query, equipment=equipment_filter, limit=20)

            # Determine if there are more results
            has_more = len(results) == PER_PAGE

            # Log the search
            total_results = len(results) + len(card_results)
            log_search(
                query,
                total_results,
                equipment_filter=equipment_filter,
                doc_type_filter=doc_type_filter,
                boost_primary=boost
            )

        except sqlite3.Error as e:
            current_app.logger_instance.error(f"Search database error: {e}")
            error = "Search database error"
        except (TypeError, ValueError) as e:
            current_app.logger_instance.warning(f"Search query processing error: {e}")
            error = "Invalid search query"
        except Exception as e:  # Safety net for unexpected errors
            current_app.logger_instance.exception(f"Unexpected search error: {e}")
            error = "An unexpected error occurred"

    # Calculate has_more flag
    has_more = len(results) == PER_PAGE if query else False

    return render_template(
        "manuals/search.html",
        db_available=True,
        query=query,
        equipment=equipment,
        doc_type=doc_type,
        systems=systems,
        boost=boost,
        results=results,
        card_results=card_results,
        error=error,
        equipment_options=EQUIPMENT_OPTIONS,
        doc_type_options=DOC_TYPE_OPTIONS,
        tag_facets=tag_facets,
        page=page,
        per_page=PER_PAGE,
        has_more=has_more,
    )


@manuals_bp.route("/card/<card_id>")
@limiter.limit(SecurityConfig.RATE_LIMIT_PER_MINUTE)
@login_required
def card_detail(card_id: str):
    """Show troubleshooting card detail."""
    card = get_card(card_id)

    if not card:
        return render_template("manuals/card.html", card=None, error="Card not found")

    return render_template("manuals/card.html", card=card, error=None)


@manuals_bp.route("/cards")
@limiter.limit(SecurityConfig.RATE_LIMIT_PER_MINUTE)
@login_required
def cards_list():
    """List all troubleshooting cards."""
    equipment = request.args.get("equipment")
    subsystem = request.args.get("subsystem")

    # Convert empty strings to None
    equipment = equipment if equipment else None
    subsystem = subsystem if subsystem else None

    cards = list_cards(equipment=equipment, subsystem=subsystem)

    return render_template(
        "manuals/cards.html",
        cards=cards,
        equipment=equipment or "All",
        subsystem=subsystem or "All",
        equipment_options=EQUIPMENT_OPTIONS,
        subsystem_options=["All"] + SUBSYSTEM_CHOICES,
    )


@manuals_bp.route("/stats")
@limiter.limit(SecurityConfig.RATE_LIMIT_PER_MINUTE)
@login_required
def stats():
    """Show index statistics."""
    stats = get_index_stats()
    return render_template("manuals/stats.html", stats=stats)


@manuals_bp.route("/open")
@limiter.limit(SecurityConfig.RATE_LIMIT_PER_MINUTE)
@login_required
def open_pdf():
    """
    Open PDF at specific page (macOS only).

    Query params:
        file: File path
        page: Page number
    """
    filepath = request.args.get("file", "")
    page = request.args.get("page", "1")

    try:
        page_num = int(page)
    except ValueError:
        page_num = 1

    if filepath:
        success = open_pdf_to_page(filepath, page_num)
        if success:
            return jsonify({
                "status": "ok",
                "message": f"Opened {Path(filepath).name} at page {page_num}"
            })
        else:
            return jsonify({
                "status": "error",
                "message": "Failed to open PDF (macOS Preview required)"
            }), 500

    return jsonify({"status": "error", "message": "No file specified"}), 400


@manuals_bp.route("/open-by-name")
@limiter.limit(SecurityConfig.RATE_LIMIT_PER_MINUTE)
@login_required
def open_pdf_by_name():
    """Open PDF by filename (resolved from DB) at specific page.

    Chat citations only have filename + page, not the full filepath.
    This endpoint looks up the filepath from the pages table and
    delegates to open_pdf_to_page().

    Query params:
        filename: Document filename (e.g. 'kenr5403-00_3516-testing-&-adjusting')
        page: Page number (default 1)
    """
    filename = request.args.get("filename", "").strip()
    page = request.args.get("page", "1")

    if not filename:
        return jsonify({"status": "error", "message": "No filename specified"}), 400

    try:
        page_num = int(page)
    except ValueError:
        page_num = 1

    # Resolve filepath from DB
    conn = load_manuals_database()
    if not conn:
        return jsonify({
            "status": "error",
            "message": "Manuals database not available"
        }), 500

    try:
        # Exact match first
        row = conn.execute(
            "SELECT filepath FROM pages WHERE filename = ? LIMIT 1",
            (filename,),
        ).fetchone()

        # Fallback: LLM abbreviates filenames (drops .pdf, middle segments).
        # Match on doc ID prefix (e.g. "kenr5403-11-00") which is unique.
        if not row:
            doc_id = re.match(r"^[a-z]+\d+", filename)
            if doc_id:
                row = conn.execute(
                    "SELECT filepath FROM pages WHERE filename LIKE ? LIMIT 1",
                    (f"{doc_id.group(0)}%",),
                ).fetchone()
    finally:
        conn.close()

    if not row:
        return jsonify({
            "status": "error",
            "message": f"Document '{filename}' not found in database"
        }), 404

    filepath = row["filepath"] if isinstance(row, dict) else row[0]
    success = open_pdf_to_page(filepath, page_num)

    if success:
        return jsonify({
            "status": "ok",
            "message": f"Opened {filename} at page {page_num}"
        })
    else:
        return jsonify({
            "status": "error",
            "message": "Failed to open PDF (macOS Preview required)"
        }), 500


# Template filter for getting filename from path
@manuals_bp.app_template_filter("basename")
def basename_filter(path: str) -> str:
    """Get filename from path."""
    return Path(path).name if path else ""
