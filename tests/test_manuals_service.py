"""Tests for manuals_service.py — search, ranking, page retrieval, query expansion.

Covers:
  - prepare_search_query (acronym, spelling, synonym, phrase expansion)
  - _tokenize_query, _contains_fts_syntax
  - _is_procedural_query
  - _calculate_ranking_boost
  - format_snippet
  - search_manuals (with mocked DB)
  - get_pages_content (exact match + fallback)
  - get_context_for_llm (wrapper)
  - get_tag_facets, get_document_tags
  - get_index_stats
  - load_keywords, load_manuals_database
  - Edge cases: empty DB, missing tables, special characters
"""

import sqlite3
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


# ─────────────────────────────────────────────────────────────────
# Unit Tests: _tokenize_query
# ─────────────────────────────────────────────────────────────────

class TestTokenizeQuery:
    """Test query tokenization."""

    def test_basic_words(self):
        from services.manuals_service import _tokenize_query

        assert _tokenize_query("valve lash") == ["valve", "lash"]

    def test_ampersand_replaced(self):
        from services.manuals_service import _tokenize_query

        tokens = _tokenize_query("O&M manual")
        assert "o" in tokens
        assert "and" in tokens
        assert "m" in tokens

    def test_model_numbers_preserved(self):
        from services.manuals_service import _tokenize_query

        tokens = _tokenize_query("C4.4 engine")
        assert "c4.4" in tokens

    def test_hyphenated_preserved(self):
        from services.manuals_service import _tokenize_query

        tokens = _tokenize_query("kenr5403-00")
        assert "kenr5403-00" in tokens

    def test_empty_string(self):
        from services.manuals_service import _tokenize_query

        assert _tokenize_query("") == []

    def test_uppercase_lowered(self):
        from services.manuals_service import _tokenize_query

        assert _tokenize_query("VALVE") == ["valve"]


# ─────────────────────────────────────────────────────────────────
# Unit Tests: _contains_fts_syntax
# ─────────────────────────────────────────────────────────────────

class TestContainsFtsSyntax:
    """Test FTS5 syntax detection."""

    def test_plain_query(self):
        from services.manuals_service import _contains_fts_syntax

        assert _contains_fts_syntax("valve lash") is False

    def test_quoted_phrase(self):
        from services.manuals_service import _contains_fts_syntax

        assert _contains_fts_syntax('"valve lash"') is True

    def test_wildcard(self):
        from services.manuals_service import _contains_fts_syntax

        assert _contains_fts_syntax("valve*") is True

    def test_boolean_and(self):
        from services.manuals_service import _contains_fts_syntax

        assert _contains_fts_syntax("valve AND lash") is True

    def test_boolean_or(self):
        from services.manuals_service import _contains_fts_syntax

        assert _contains_fts_syntax("valve OR lash") is True

    def test_boolean_not(self):
        from services.manuals_service import _contains_fts_syntax

        assert _contains_fts_syntax("valve NOT lash") is True

    def test_near_operator(self):
        from services.manuals_service import _contains_fts_syntax

        assert _contains_fts_syntax("valve NEAR lash") is True

    def test_parentheses(self):
        from services.manuals_service import _contains_fts_syntax

        assert _contains_fts_syntax("(valve lash)") is True

    def test_colon_prefix(self):
        from services.manuals_service import _contains_fts_syntax

        assert _contains_fts_syntax("content:valve") is True

    def test_lowercase_and_not_detected(self):
        from services.manuals_service import _contains_fts_syntax

        # Lowercase "and" is a natural word, NOT FTS5 syntax
        assert _contains_fts_syntax("operation and maintenance") is False

    def test_disassembly_and_assembly(self):
        from services.manuals_service import _contains_fts_syntax

        # Another common phrase with natural "and"
        assert _contains_fts_syntax("disassembly and assembly") is False

    def test_uppercase_and_detected(self):
        from services.manuals_service import _contains_fts_syntax

        # Uppercase AND is FTS5 boolean operator
        assert _contains_fts_syntax("valve AND lash") is True

    def test_uppercase_near_detected(self):
        from services.manuals_service import _contains_fts_syntax

        # Uppercase NEAR is FTS5 proximity operator
        assert _contains_fts_syntax("valve NEAR lash") is True

    def test_mixed_case_not_detected(self):
        from services.manuals_service import _contains_fts_syntax

        # Mixed case should NOT trigger detection (FTS5 requires uppercase)
        assert _contains_fts_syntax("valve And lash") is False


# ─────────────────────────────────────────────────────────────────
# Unit Tests: prepare_search_query (query expansion)
# ─────────────────────────────────────────────────────────────────

class TestPrepareSearchQuery:
    """Test query expansion with acronyms, synonyms, and spelling variants."""

    def test_empty_query_unchanged(self):
        from services.manuals_service import prepare_search_query

        assert prepare_search_query("") == ""
        assert prepare_search_query("   ") == "   "

    def test_fts_syntax_not_expanded(self):
        from services.manuals_service import prepare_search_query

        q = '"valve lash"'
        assert prepare_search_query(q) == q

    def test_acronym_expansion_tdc(self):
        from services.manuals_service import prepare_search_query

        result = prepare_search_query("tdc")
        assert "top dead center" in result.lower() or '"top dead center"' in result.lower()
        assert "OR" in result

    def test_acronym_expansion_ecm(self):
        from services.manuals_service import prepare_search_query

        result = prepare_search_query("ecm")
        assert "engine control module" in result.lower() or '"engine control module"' in result.lower()

    def test_spelling_variant_labour(self):
        from services.manuals_service import prepare_search_query

        result = prepare_search_query("labour")
        assert "labor" in result

    def test_spelling_variant_centre(self):
        from services.manuals_service import prepare_search_query

        result = prepare_search_query("centre")
        assert "center" in result

    def test_synonym_expansion_turbo(self):
        from services.manuals_service import prepare_search_query

        result = prepare_search_query("turbo")
        assert "turbocharger" in result

    def test_phrase_synonym_valve_lash(self):
        from services.manuals_service import prepare_search_query

        result = prepare_search_query("valve lash")
        assert "valve clearance" in result.lower() or '"valve clearance"' in result.lower()

    def test_multi_word_phrase_grouped(self):
        from services.manuals_service import prepare_search_query

        result = prepare_search_query("fuel filter")
        # Multi-word query adds a quoted phrase
        assert '"fuel filter"' in result

    def test_no_expansions_returns_original(self):
        from services.manuals_service import prepare_search_query

        # Single word with no expansions
        result = prepare_search_query("actuator")
        assert result == "actuator"

    def test_or_structure(self):
        from services.manuals_service import prepare_search_query

        result = prepare_search_query("tdc")
        # Should be: (tdc) OR (expansion1 OR expansion2 ...)
        assert result.startswith("(tdc) OR (")


# ─────────────────────────────────────────────────────────────────
# Unit Tests: _is_procedural_query
# ─────────────────────────────────────────────────────────────────

class TestIsProceduralQuery:
    """Test procedural intent detection."""

    def test_procedural_adjust(self):
        from services.manuals_service import _is_procedural_query

        assert _is_procedural_query("adjust valve lash") is True

    def test_procedural_replace(self):
        from services.manuals_service import _is_procedural_query

        assert _is_procedural_query("replace fuel filter") is True

    def test_procedural_torque(self):
        from services.manuals_service import _is_procedural_query

        assert _is_procedural_query("torque specifications") is True

    def test_procedural_how_to(self):
        from services.manuals_service import _is_procedural_query

        assert _is_procedural_query("how to check oil level") is True

    def test_not_procedural(self):
        from services.manuals_service import _is_procedural_query

        assert _is_procedural_query("engine overview") is False

    def test_not_procedural_specs(self):
        from services.manuals_service import _is_procedural_query

        # "specifications" is not in PROCEDURAL_KEYWORDS
        assert _is_procedural_query("engine specifications") is False


# ─────────────────────────────────────────────────────────────────
# Unit Tests: _calculate_ranking_boost
# ─────────────────────────────────────────────────────────────────

class TestCalculateRankingBoost:
    """Test combined ranking boost calculation."""

    def test_no_boost_basic(self):
        from services.manuals_service import _calculate_ranking_boost

        result = {"doc_type": "O&M", "tags": []}
        boost = _calculate_ranking_boost(result, "engine", False, set(), "engine overview")
        assert boost == 1.0

    def test_phrase_boost(self):
        from services.manuals_service import _calculate_ranking_boost

        result = {"doc_type": "O&M", "tags": []}
        # "valve lash" appears as phrase in content
        boost = _calculate_ranking_boost(
            result, "valve lash", False, set(),
            "Step 1: Adjust valve lash to specification."
        )
        assert boost == 1.5  # phrase match boost

    def test_phrase_no_match(self):
        from services.manuals_service import _calculate_ranking_boost

        result = {"doc_type": "O&M", "tags": []}
        # "valve lash" does NOT appear as phrase
        boost = _calculate_ranking_boost(
            result, "valve lash", False, set(),
            "The lash on a valve is important."
        )
        assert boost == 1.0

    def test_procedural_doc_type_boost(self):
        from services.manuals_service import _calculate_ranking_boost

        result = {"doc_type": "testing", "tags": []}
        boost = _calculate_ranking_boost(
            result, "adjust valve", True, set(), "some content"
        )
        # testing doc_type boost = 1.4
        assert boost == pytest.approx(1.4, rel=1e-2)

    def test_tag_aware_boost(self):
        from services.manuals_service import _calculate_ranking_boost

        matching_tags = {"Fuel System"}
        result = {"doc_type": "O&M", "tags": ["Fuel System"]}
        boost = _calculate_ranking_boost(
            result, "fuel", False, matching_tags, "some content"
        )
        # 1 matching tag = 1.0 + 0.2 = 1.2
        assert boost == pytest.approx(1.2, rel=1e-2)

    def test_tag_boost_capped(self):
        from services.manuals_service import _calculate_ranking_boost

        matching_tags = {"Fuel System", "Cooling System", "Lubrication System", "Exhaust System"}
        result = {"doc_type": "O&M", "tags": list(matching_tags)}
        boost = _calculate_ranking_boost(
            result, "systems", False, matching_tags, "some content"
        )
        # 4 tags * 0.2 = 0.8, capped at 0.6 → 1.6
        assert boost == pytest.approx(1.6, rel=1e-2)

    def test_combined_phrase_and_procedural(self):
        from services.manuals_service import _calculate_ranking_boost

        result = {"doc_type": "testing", "tags": []}
        boost = _calculate_ranking_boost(
            result, "valve lash", True, set(),
            "Adjust the valve lash to specification."
        )
        # phrase boost 1.5 * testing doc boost 1.4 = 2.1
        assert boost == pytest.approx(2.1, rel=1e-2)

    def test_single_word_query_no_phrase_boost(self):
        from services.manuals_service import _calculate_ranking_boost

        result = {"doc_type": "O&M", "tags": []}
        boost = _calculate_ranking_boost(
            result, "valve", False, set(), "valve cover removal"
        )
        # Single word query → no phrase boost possible
        assert boost == 1.0


# ─────────────────────────────────────────────────────────────────
# Unit Tests: format_snippet
# ─────────────────────────────────────────────────────────────────

class TestFormatSnippet:
    """Test snippet extraction and highlighting."""

    def test_highlights_query_term(self):
        from services.manuals_service import format_snippet

        result = format_snippet("Adjust the valve lash to spec.", "valve", 200)
        assert "<mark>valve</mark>" in result

    def test_case_insensitive_highlight(self):
        from services.manuals_service import format_snippet

        result = format_snippet("VALVE LASH procedure", "valve", 200)
        assert "<mark>VALVE</mark>" in result

    def test_truncates_long_text(self):
        from services.manuals_service import format_snippet

        long_text = "x " * 500 + "valve target " + "y " * 500
        result = format_snippet(long_text, "valve", 200)
        assert len(result) < len(long_text)
        assert "..." in result

    def test_html_escaped(self):
        from services.manuals_service import format_snippet

        result = format_snippet("Check <value> & adjust valve", "valve", 200)
        assert "&lt;value&gt;" in result
        assert "&amp;" in result

    def test_boolean_operators_excluded_from_highlight(self):
        from services.manuals_service import format_snippet

        result = format_snippet("valve OR lash content", "valve OR lash", 200)
        # "OR" should NOT be highlighted
        assert "<mark>OR</mark>" not in result

    def test_empty_text(self):
        from services.manuals_service import format_snippet

        result = format_snippet("", "valve", 200)
        assert result == ""

    def test_no_match_returns_beginning(self):
        from services.manuals_service import format_snippet

        result = format_snippet("Some random text about engines", "nonexistent", 200)
        assert "Some random text" in result


# ─────────────────────────────────────────────────────────────────
# Unit Tests: search_manuals (with in-memory FTS5 DB)
# ─────────────────────────────────────────────────────────────────

_TEST_DB_SQL = """
    CREATE TABLE pages (
        id INTEGER PRIMARY KEY,
        filepath TEXT,
        filename TEXT,
        equipment TEXT,
        doc_type TEXT,
        page_num INTEGER,
        content TEXT
    );

    CREATE VIRTUAL TABLE pages_fts USING fts5(
        content,
        content='pages',
        content_rowid='id',
        tokenize='porter unicode61'
    );

    CREATE TABLE documents (
        doc_id INTEGER PRIMARY KEY,
        filename TEXT UNIQUE
    );

    CREATE TABLE tags (
        tag_id INTEGER PRIMARY KEY,
        tag_name TEXT,
        tag_category TEXT DEFAULT 'system'
    );

    CREATE TABLE document_tags (
        doc_id INTEGER,
        tag_id INTEGER,
        tag_weight REAL DEFAULT 1.0
    );

    INSERT INTO pages (id, filepath, filename, equipment, doc_type, page_num, content)
    VALUES
        (1, '/manuals/kenr5403.pdf', 'kenr5403-00_3516-testing', '3516', 'testing', 48,
         'Valve lash adjustment procedure. Set intake valve clearance to 0.38 mm.'),
        (2, '/manuals/kenr5403.pdf', 'kenr5403-00_3516-testing', '3516', 'testing', 49,
         'Exhaust valve lash clearance specification 0.76 mm.'),
        (3, '/manuals/senr9773.pdf', 'senr9773-00_3516-troubleshooting', '3516', 'troubleshooting', 112,
         'Fuel rack actuator troubleshooting steps.'),
        (4, '/manuals/c18-om.pdf', 'renr2400-00_C18-disassembly', 'C18', 'disassembly', 88,
         'Torque sequence for cylinder head bolts on C18 engine.');

    INSERT INTO pages_fts (rowid, content) VALUES
        (1, 'Valve lash adjustment procedure. Set intake valve clearance to 0.38 mm.'),
        (2, 'Exhaust valve lash clearance specification 0.76 mm.'),
        (3, 'Fuel rack actuator troubleshooting steps.'),
        (4, 'Torque sequence for cylinder head bolts on C18 engine.');

    INSERT INTO documents (doc_id, filename) VALUES
        (1, 'kenr5403-00_3516-testing'),
        (2, 'senr9773-00_3516-troubleshooting'),
        (3, 'renr2400-00_C18-disassembly');

    INSERT INTO tags (tag_id, tag_name, tag_category) VALUES
        (1, 'Cylinder Head/Valvetrain', 'system'),
        (2, 'Fuel System', 'system');

    INSERT INTO document_tags (doc_id, tag_id, tag_weight) VALUES
        (1, 1, 1.0),
        (2, 2, 1.0);
"""


def _create_test_db(path: str = ":memory:") -> sqlite3.Connection:
    """Create a FTS5 database for testing search_manuals."""
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.executescript(_TEST_DB_SQL)
    return conn


@pytest.fixture
def test_db_path(tmp_path):
    """Create a temporary FTS5 database file and return its path.

    File-based DB is needed for search_manuals tests because the function
    calls load_manuals_database() multiple times internally (once for the
    main search, again inside get_document_tags for each result). An
    in-memory DB would be closed after the first connection.close().
    """
    db_path = tmp_path / "engine_search.db"
    conn = _create_test_db(str(db_path))
    conn.close()
    return db_path


class TestSearchManuals:
    """Test search_manuals with real FTS5 queries against file-based DB.

    Uses a temp file DB (not in-memory) because search_manuals calls
    load_manuals_database() multiple times internally, and each call
    opens a fresh connection. File-based DB survives across connections.
    """

    @patch("services.manuals_service.load_keywords")
    @patch("services.manuals_service.get_manuals_db_path")
    def test_basic_search(self, mock_path, mock_kw, test_db_path):
        from services.manuals_service import search_manuals

        mock_path.return_value = test_db_path
        mock_kw.return_value = {}

        results = search_manuals("valve lash")
        assert len(results) >= 1
        assert any("valve" in r["snippet"].lower() for r in results)

    @patch("services.manuals_service.load_keywords")
    @patch("services.manuals_service.get_manuals_db_path")
    def test_equipment_filter(self, mock_path, mock_kw, test_db_path):
        from services.manuals_service import search_manuals

        mock_path.return_value = test_db_path
        mock_kw.return_value = {}

        results = search_manuals("torque", equipment="C18")
        assert all(r["equipment"] == "C18" for r in results)
        assert len(results) >= 1

    @patch("services.manuals_service.load_keywords")
    @patch("services.manuals_service.get_manuals_db_path")
    def test_doc_type_filter(self, mock_path, mock_kw, test_db_path):
        from services.manuals_service import search_manuals

        mock_path.return_value = test_db_path
        mock_kw.return_value = {}

        results = search_manuals("fuel", doc_type="troubleshooting")
        assert all(r["doc_type"] == "troubleshooting" for r in results)

    @patch("services.manuals_service.load_keywords")
    @patch("services.manuals_service.get_manuals_db_path")
    def test_no_results(self, mock_path, mock_kw, test_db_path):
        from services.manuals_service import search_manuals

        mock_path.return_value = test_db_path
        mock_kw.return_value = {}

        results = search_manuals("xyznonexistent123")
        assert results == []

    @patch("services.manuals_service.load_manuals_database")
    def test_no_database(self, mock_db):
        from services.manuals_service import search_manuals

        mock_db.return_value = None
        results = search_manuals("valve lash")
        assert results == []

    @patch("services.manuals_service.load_keywords")
    @patch("services.manuals_service.get_manuals_db_path")
    def test_result_shape(self, mock_path, mock_kw, test_db_path):
        from services.manuals_service import search_manuals

        mock_path.return_value = test_db_path
        mock_kw.return_value = {}

        results = search_manuals("valve")
        assert len(results) >= 1
        r = results[0]
        assert "filepath" in r
        assert "filename" in r
        assert "equipment" in r
        assert "doc_type" in r
        assert "page_num" in r
        assert "snippet" in r
        assert "score" in r
        assert "authority" in r
        assert "tags" in r

    @patch("services.manuals_service.load_keywords")
    @patch("services.manuals_service.get_manuals_db_path")
    def test_limit_respected(self, mock_path, mock_kw, test_db_path):
        from services.manuals_service import search_manuals

        mock_path.return_value = test_db_path
        mock_kw.return_value = {}

        results = search_manuals("valve", limit=1)
        assert len(results) <= 1

    @patch("services.manuals_service.load_keywords")
    @patch("services.manuals_service.get_manuals_db_path")
    def test_boost_primary_flag(self, mock_path, mock_kw, test_db_path):
        from services.manuals_service import search_manuals

        mock_path.return_value = test_db_path
        mock_kw.return_value = {}

        results = search_manuals("valve", boost_primary=True)
        assert len(results) >= 1

    @patch("services.manuals_service.load_keywords")
    @patch("services.manuals_service.get_manuals_db_path")
    def test_systems_filter(self, mock_path, mock_kw, test_db_path):
        from services.manuals_service import search_manuals

        mock_path.return_value = test_db_path
        mock_kw.return_value = {}

        results = search_manuals("valve", systems=["Cylinder Head/Valvetrain"])
        assert len(results) >= 1
        for r in results:
            assert r["filename"] == "kenr5403-00_3516-testing"

    @patch("services.manuals_service.load_keywords")
    @patch("services.manuals_service.get_manuals_db_path")
    def test_special_characters_in_query(self, mock_path, mock_kw, test_db_path):
        from services.manuals_service import search_manuals

        mock_path.return_value = test_db_path
        mock_kw.return_value = {}

        results = search_manuals("O&M")
        assert isinstance(results, list)


# ─────────────────────────────────────────────────────────────────
# Unit Tests: get_pages_content (with in-memory DB)
# ─────────────────────────────────────────────────────────────────

class TestGetPagesContentInMemory:
    """Test get_pages_content with real SQLite queries."""

    @patch("services.manuals_service.load_manuals_database")
    def test_exact_match(self, mock_db):
        from services.manuals_service import get_pages_content

        mock_db.return_value = _create_test_db()
        results = get_pages_content("kenr5403-00_3516-testing", [48])
        assert len(results) == 1
        assert results[0]["page_num"] == 48
        assert "valve" in results[0]["content"].lower()

    @patch("services.manuals_service.load_manuals_database")
    def test_multiple_pages(self, mock_db):
        from services.manuals_service import get_pages_content

        mock_db.return_value = _create_test_db()
        results = get_pages_content("kenr5403-00_3516-testing", [48, 49])
        assert len(results) == 2
        assert results[0]["page_num"] == 48
        assert results[1]["page_num"] == 49

    @patch("services.manuals_service.load_manuals_database")
    def test_missing_page(self, mock_db):
        from services.manuals_service import get_pages_content

        mock_db.return_value = _create_test_db()
        results = get_pages_content("kenr5403-00_3516-testing", [999])
        assert results == []

    @patch("services.manuals_service.load_manuals_database")
    def test_invalid_filename(self, mock_db):
        from services.manuals_service import get_pages_content

        mock_db.return_value = _create_test_db()
        results = get_pages_content("nonexistent_doc", [1])
        assert results == []

    @patch("services.manuals_service.load_manuals_database")
    def test_fallback_prefix_match(self, mock_db):
        from services.manuals_service import get_pages_content

        mock_db.return_value = _create_test_db()
        # LLM abbreviates filename — fallback matches on doc ID prefix
        results = get_pages_content("kenr5403", [48])
        assert len(results) == 1
        assert results[0]["filename"] == "kenr5403-00_3516-testing"

    @patch("services.manuals_service.load_manuals_database")
    def test_content_stripped(self, mock_db):
        from services.manuals_service import get_pages_content

        conn = _create_test_db()
        # Insert a row with leading/trailing whitespace
        conn.execute(
            "INSERT INTO pages (id, filepath, filename, equipment, doc_type, page_num, content) "
            "VALUES (100, '/test.pdf', 'test-doc', '3516', 'testing', 1, '   padded content   ')"
        )
        mock_db.return_value = conn

        results = get_pages_content("test-doc", [1])
        assert results[0]["content"] == "padded content"

    def test_empty_page_list(self):
        from services.manuals_service import get_pages_content

        results = get_pages_content("any-doc", [])
        assert results == []

    @patch("services.manuals_service.load_manuals_database")
    def test_no_database(self, mock_db):
        from services.manuals_service import get_pages_content

        mock_db.return_value = None
        results = get_pages_content("doc", [1])
        assert results == []


# ─────────────────────────────────────────────────────────────────
# Unit Tests: get_context_for_llm
# ─────────────────────────────────────────────────────────────────

class TestGetContextForLLMService:
    """Test get_context_for_llm wrapper function."""

    @patch("services.manuals_service.search_manuals")
    def test_delegates_to_search_manuals(self, mock_search):
        from services.manuals_service import get_context_for_llm

        mock_search.return_value = [
            {
                "filepath": "/path/doc.pdf",
                "filename": "doc.pdf",
                "equipment": "3516",
                "doc_type": "testing",
                "page_num": 48,
                "snippet": "valve lash",
                "authority": "primary",
                "authority_label": "[PRIMARY]",
                "tags": [],
                "score": 2.0,
                "base_score": 3.0,
            }
        ]
        results = get_context_for_llm("valve lash", equipment="3516", limit=5)

        mock_search.assert_called_once_with(
            "valve lash", equipment="3516", boost_primary=True, limit=5
        )
        assert len(results) == 1
        # Only expected keys in output
        assert set(results[0].keys()) == {
            "filename", "page_num", "equipment", "doc_type",
            "snippet", "authority", "score"
        }

    @patch("services.manuals_service.search_manuals")
    def test_empty_results(self, mock_search):
        from services.manuals_service import get_context_for_llm

        mock_search.return_value = []
        results = get_context_for_llm("nonexistent")
        assert results == []


# ─────────────────────────────────────────────────────────────────
# Unit Tests: get_tag_facets
# ─────────────────────────────────────────────────────────────────

class TestGetTagFacets:
    """Test tag facet retrieval."""

    @patch("services.manuals_service.load_manuals_database")
    def test_returns_facets(self, mock_db):
        from services.manuals_service import get_tag_facets

        mock_db.return_value = _create_test_db()
        facets = get_tag_facets()
        assert isinstance(facets, list)
        assert len(facets) >= 1
        assert "tag_name" in facets[0]
        assert "doc_count" in facets[0]

    @patch("services.manuals_service.load_manuals_database")
    def test_equipment_filter(self, mock_db):
        from services.manuals_service import get_tag_facets

        mock_db.return_value = _create_test_db()
        facets = get_tag_facets(equipment="3516")
        # All results should be from 3516 docs
        assert isinstance(facets, list)

    @patch("services.manuals_service.load_manuals_database")
    def test_no_database(self, mock_db):
        from services.manuals_service import get_tag_facets

        mock_db.return_value = None
        assert get_tag_facets() == []


# ─────────────────────────────────────────────────────────────────
# Unit Tests: get_document_tags
# ─────────────────────────────────────────────────────────────────

class TestGetDocumentTags:
    """Test document tag retrieval."""

    @patch("services.manuals_service.load_manuals_database")
    def test_returns_tags(self, mock_db):
        from services.manuals_service import get_document_tags

        mock_db.return_value = _create_test_db()
        tags = get_document_tags("kenr5403-00_3516-testing")
        assert "Cylinder Head/Valvetrain" in tags

    @patch("services.manuals_service.load_manuals_database")
    def test_no_tags(self, mock_db):
        from services.manuals_service import get_document_tags

        mock_db.return_value = _create_test_db()
        tags = get_document_tags("nonexistent_doc")
        assert tags == []

    @patch("services.manuals_service.load_manuals_database")
    def test_no_database(self, mock_db):
        from services.manuals_service import get_document_tags

        mock_db.return_value = None
        assert get_document_tags("any") == []


# ─────────────────────────────────────────────────────────────────
# Unit Tests: get_index_stats
# ─────────────────────────────────────────────────────────────────

class TestGetIndexStats:
    """Test index statistics."""

    @patch("services.manuals_service.load_manuals_database")
    def test_returns_stats(self, mock_db):
        from services.manuals_service import get_index_stats

        mock_db.return_value = _create_test_db()
        stats = get_index_stats()
        assert stats["available"] is True
        assert stats["total_pages"] == 4
        assert stats["total_files"] >= 1

    @patch("services.manuals_service.load_manuals_database")
    def test_no_database(self, mock_db):
        from services.manuals_service import get_index_stats

        mock_db.return_value = None
        stats = get_index_stats()
        assert stats["available"] is False
        assert stats["total_pages"] == 0


# ─────────────────────────────────────────────────────────────────
# Unit Tests: load_keywords
# ─────────────────────────────────────────────────────────────────

class TestLoadKeywords:
    """Test keywords.json loading."""

    @patch("services.manuals_service.get_keywords_path")
    def test_missing_file(self, mock_path):
        from services.manuals_service import load_keywords

        mock_path.return_value = Path("/nonexistent/keywords.json")
        assert load_keywords() == {}

    @patch("services.manuals_service.get_keywords_path")
    def test_invalid_json(self, mock_path, tmp_path):
        from services.manuals_service import load_keywords

        bad_file = tmp_path / "keywords.json"
        bad_file.write_text("not json!")
        mock_path.return_value = bad_file
        assert load_keywords() == {}

    @patch("services.manuals_service.get_keywords_path")
    def test_valid_json(self, mock_path, tmp_path):
        from services.manuals_service import load_keywords

        good_file = tmp_path / "keywords.json"
        good_file.write_text('{"systems": {"Fuel System": {"keywords": ["fuel", "injection"]}}}')
        mock_path.return_value = good_file
        result = load_keywords()
        assert "systems" in result
        assert "Fuel System" in result["systems"]


# ─────────────────────────────────────────────────────────────────
# Unit Tests: _get_matching_tags_for_query
# ─────────────────────────────────────────────────────────────────

class TestGetMatchingTagsForQuery:
    """Test keyword-to-tag matching."""

    def test_matches_fuel(self):
        from services.manuals_service import _get_matching_tags_for_query

        keywords_data = {
            "systems": {
                "Fuel System": {"keywords": ["fuel", "injection", "rack"]},
                "Cooling System": {"keywords": ["coolant", "water", "radiator"]},
            }
        }
        result = _get_matching_tags_for_query("fuel filter replacement", keywords_data)
        assert "Fuel System" in result
        assert "Cooling System" not in result

    def test_empty_keywords(self):
        from services.manuals_service import _get_matching_tags_for_query

        assert _get_matching_tags_for_query("fuel", {}) == set()

    def test_no_match(self):
        from services.manuals_service import _get_matching_tags_for_query

        keywords_data = {
            "systems": {
                "Fuel System": {"keywords": ["fuel"]},
            }
        }
        result = _get_matching_tags_for_query("valve lash", keywords_data)
        assert result == set()


# ─────────────────────────────────────────────────────────────────
# Unit Tests: load_manuals_database
# ─────────────────────────────────────────────────────────────────

class TestLoadManualsDatabase:
    """Test database loading."""

    @patch("services.manuals_service.get_manuals_db_path")
    def test_missing_db_returns_none(self, mock_path):
        from services.manuals_service import load_manuals_database

        mock_path.return_value = Path("/nonexistent/engine_search.db")
        assert load_manuals_database() is None

    @patch("services.manuals_service.get_manuals_db_path")
    def test_existing_db_returns_connection(self, mock_path, tmp_path):
        from services.manuals_service import load_manuals_database

        db_file = tmp_path / "engine_search.db"
        # Create an actual SQLite file
        conn = sqlite3.connect(str(db_file))
        conn.execute("CREATE TABLE test (id INTEGER)")
        conn.close()

        mock_path.return_value = db_file
        result = load_manuals_database()
        assert result is not None
        assert isinstance(result, sqlite3.Connection)
        result.close()


# ─────────────────────────────────────────────────────────────────
# Unit Tests: _quote_if_phrase
# ─────────────────────────────────────────────────────────────────

class TestQuoteIfPhrase:
    """Test phrase quoting utility."""

    def test_single_word(self):
        from services.manuals_service import _quote_if_phrase

        assert _quote_if_phrase("valve") == "valve"

    def test_multi_word_quoted(self):
        from services.manuals_service import _quote_if_phrase

        assert _quote_if_phrase("top dead center") == '"top dead center"'

    def test_strips_whitespace(self):
        from services.manuals_service import _quote_if_phrase

        assert _quote_if_phrase("  valve  ") == "valve"


# ─────────────────────────────────────────────────────────────────
# Unit Tests: _tokenize_smart_query
# ─────────────────────────────────────────────────────────────────

class TestTokenizeSmartQuery:
    """Test smart query tokenization with stop-word removal."""

    def test_basic_words(self):
        from services.manuals_service import _tokenize_smart_query

        assert _tokenize_smart_query("valve lash") == ["valve", "lash"]

    def test_stop_words_removed(self):
        from services.manuals_service import _tokenize_smart_query

        result = _tokenize_smart_query("How do I adjust valve lash?")
        assert "how" not in [t.lower() for t in result]
        assert "do" not in [t.lower() for t in result]
        assert "i" not in [t.lower() for t in result]
        assert "adjust" in [t.lower() for t in result]
        assert "valve" in [t.lower() for t in result]
        assert "lash" in [t.lower() for t in result]

    def test_model_numbers_preserved(self):
        from services.manuals_service import _tokenize_smart_query

        tokens = _tokenize_smart_query("What is the 3516 fuel rack?")
        assert "3516" in tokens
        assert "fuel" in [t.lower() for t in tokens]
        assert "rack" in [t.lower() for t in tokens]

    def test_strips_punctuation(self):
        from services.manuals_service import _tokenize_smart_query

        tokens = _tokenize_smart_query("valve lash?")
        # Should not have trailing punctuation
        assert all("?" not in t for t in tokens)

    def test_empty_query(self):
        from services.manuals_service import _tokenize_smart_query

        assert _tokenize_smart_query("") == []

    def test_only_stop_words(self):
        from services.manuals_service import _tokenize_smart_query

        # Query with only stop words returns empty
        assert _tokenize_smart_query("how do I") == []

    def test_c4_dot_4_preserved(self):
        from services.manuals_service import _tokenize_smart_query

        tokens = _tokenize_smart_query("C4.4 engine")
        assert "C4.4" in tokens or "c4.4" in [t.lower() for t in tokens]


# ─────────────────────────────────────────────────────────────────
# Unit Tests: _detect_known_phrases
# ─────────────────────────────────────────────────────────────────

class TestDetectKnownPhrases:
    """Test known phrase detection."""

    def test_valve_lash_detected(self):
        from services.manuals_service import _detect_known_phrases

        result = _detect_known_phrases(["valve", "lash"])
        assert '"valve lash"' in result

    def test_oil_filter_detected(self):
        from services.manuals_service import _detect_known_phrases

        result = _detect_known_phrases(["oil", "filter", "replacement"])
        assert '"oil filter"' in result
        assert "replacement" in result

    def test_fuel_rack_detected(self):
        from services.manuals_service import _detect_known_phrases

        result = _detect_known_phrases(["3516", "fuel", "rack"])
        assert "3516" in result
        assert '"fuel rack"' in result

    def test_no_phrase_match(self):
        from services.manuals_service import _detect_known_phrases

        result = _detect_known_phrases(["turbocharger", "maintenance"])
        assert "turbocharger" in result
        assert "maintenance" in result
        # No quoted phrases
        assert not any('"' in r for r in result)

    def test_single_keyword(self):
        from services.manuals_service import _detect_known_phrases

        result = _detect_known_phrases(["valve"])
        assert result == ["valve"]

    def test_empty_list(self):
        from services.manuals_service import _detect_known_phrases

        assert _detect_known_phrases([]) == []


# ─────────────────────────────────────────────────────────────────
# Unit Tests: prepare_smart_query
# ─────────────────────────────────────────────────────────────────

class TestPrepareSmartQuery:
    """Test smart query pipeline with stop-word removal and phrase detection."""

    def test_stop_words_removed(self):
        from services.manuals_service import prepare_smart_query

        result = prepare_smart_query("How do I adjust valve lash?")
        # "how", "do", "i" should be stripped
        assert "how" not in result.lower()
        assert "do" not in result.lower() or '"valve lash"' in result.lower()  # 'do' might be in 'procedure'
        assert result.count("adjust") >= 1
        assert '"valve lash"' in result

    def test_valve_lash_phrase(self):
        from services.manuals_service import prepare_smart_query

        result = prepare_smart_query("valve lash")
        assert result == '"valve lash"'

    def test_3516_fuel_rack(self):
        from services.manuals_service import prepare_smart_query

        result = prepare_smart_query("3516 fuel rack")
        assert "3516" in result
        assert '"fuel rack"' in result

    def test_single_keyword(self):
        from services.manuals_service import prepare_smart_query

        result = prepare_smart_query("turbocharger")
        assert result == "turbocharger"

    def test_empty_query(self):
        from services.manuals_service import prepare_smart_query

        assert prepare_smart_query("") == ""

    def test_only_stop_words_returns_original(self):
        from services.manuals_service import prepare_smart_query

        # No content keywords → return original
        result = prepare_smart_query("how do I")
        assert result == "how do I"

    def test_oil_filter_replacement(self):
        from services.manuals_service import prepare_smart_query

        result = prepare_smart_query("oil filter replacement")
        assert '"oil filter"' in result
        assert "replacement" in result


# ─────────────────────────────────────────────────────────────────
# Unit Tests: prepare_broad_query
# ─────────────────────────────────────────────────────────────────

class TestPrepareBroadQuery:
    """Test broad OR query generation."""

    def test_or_joining(self):
        from services.manuals_service import prepare_broad_query

        result = prepare_broad_query("valve lash adjustment")
        assert "OR" in result

    def test_phrases_included(self):
        from services.manuals_service import prepare_broad_query

        result = prepare_broad_query("oil filter replacement")
        # Should have both the phrase and individual words
        assert '"oil filter"' in result
        assert "OR" in result

    def test_individual_words_included(self):
        from services.manuals_service import prepare_broad_query

        result = prepare_broad_query("valve lash")
        # Should have both the phrase and individual words
        assert '"valve lash"' in result
        assert "valve" in result
        assert "lash" in result
        assert "OR" in result

    def test_single_keyword(self):
        from services.manuals_service import prepare_broad_query

        result = prepare_broad_query("turbocharger")
        assert result == "turbocharger"

    def test_empty_query(self):
        from services.manuals_service import prepare_broad_query

        assert prepare_broad_query("") == ""

    def test_stop_words_removed(self):
        from services.manuals_service import prepare_broad_query

        result = prepare_broad_query("How do I adjust valve lash?")
        # Stop words should be removed
        assert "how" not in result.lower().split(" or ")
        assert "adjust" in result.lower()
        assert '"valve lash"' in result


# ─────────────────────────────────────────────────────────────────
# Unit Tests: is_manuals_db_available
# ─────────────────────────────────────────────────────────────────

class TestIsManualsDbAvailable:
    """Test DB availability check."""

    @patch("services.manuals_service.get_manuals_db_path")
    def test_exists(self, mock_path, tmp_path):
        from services.manuals_service import is_manuals_db_available

        db_file = tmp_path / "engine_search.db"
        db_file.touch()
        mock_path.return_value = db_file
        assert is_manuals_db_available() is True

    @patch("services.manuals_service.get_manuals_db_path")
    def test_missing(self, mock_path):
        from services.manuals_service import is_manuals_db_available

        mock_path.return_value = Path("/nonexistent/db.sqlite")
        assert is_manuals_db_available() is False
