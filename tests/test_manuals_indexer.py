"""Tests for src/services/manuals_indexer.py.

Covers:
  - derive_equipment() — known mappings, unknown fallback
  - derive_doc_type() — all prefix/content rules
  - compute_file_hash() — deterministic, truncated to 16 chars
  - extract_pdf_text() — normal PDF, empty PDF, corrupt PDF
  - create_database() — table/FTS5/trigger/index creation, replaces existing
  - scan_pdfs() — discovers PDFs in equipment folders, skips missing folders
  - build_index() — inserts pages, updates stats, calls progress callback
  - run_indexer() — end-to-end pipeline with metadata output
"""

import json
import sqlite3
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock, mock_open

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from services.manuals_indexer import (
    derive_equipment,
    derive_doc_type,
    compute_file_hash,
    extract_pdf_text,
    create_database,
    scan_pdfs,
    build_index,
    run_indexer,
    EQUIPMENT_FOLDERS,
)


# ─────────────────────────────────────────────────────────────────
# derive_equipment
# ─────────────────────────────────────────────────────────────────

class TestDeriveEquipment:

    def test_main_engine(self):
        assert derive_equipment("Main_Engine_3516") == "3516"

    def test_genset(self):
        assert derive_equipment("GenSet_C18") == "C18"

    def test_thruster(self):
        assert derive_equipment("Thruster_C32") == "C32"

    def test_emergency(self):
        assert derive_equipment("Emergency_C4.4") == "C4.4"

    def test_unknown_returns_folder_name(self):
        assert derive_equipment("Unknown_Equipment") == "Unknown_Equipment"


# ─────────────────────────────────────────────────────────────────
# derive_doc_type
# ─────────────────────────────────────────────────────────────────

class TestDeriveDocType:

    def test_schematic_in_name(self):
        assert derive_doc_type("c18_pub_schematics.pdf") == "schematic"
        assert derive_doc_type("SCHEMATIC_wiring.pdf") == "schematic"

    def test_troubleshooting(self):
        assert derive_doc_type("3516_troubleshooting_guide.pdf") == "troubleshooting"

    def test_sebu_prefix(self):
        assert derive_doc_type("sebu8145-00_3516-om.pdf") == "O&M"

    def test_kenr_service(self):
        assert derive_doc_type("kenr5403-00_3516-general.pdf") == "service"

    def test_kenr_disassembly(self):
        assert derive_doc_type("kenr1234_disassembly.pdf") == "disassembly"

    def test_kenr_assembly(self):
        assert derive_doc_type("kenr1234_assembly_guide.pdf") == "disassembly"

    def test_kenr_testing(self):
        assert derive_doc_type("kenr1234_testing-adjusting.pdf") == "testing"

    def test_kenr_adjusting(self):
        assert derive_doc_type("kenr1234_adjusting.pdf") == "testing"

    def test_kenr_specification(self):
        assert derive_doc_type("kenr1234_specification.pdf") == "specifications"

    def test_kenr_systems_operations(self):
        assert derive_doc_type("kenr1234_systems-operations.pdf") == "systems"

    def test_kenr_special_instructions(self):
        assert derive_doc_type("kenr1234_special-instructions.pdf") == "special-instructions"

    def test_renr_prefix(self):
        assert derive_doc_type("renr9999_service.pdf") == "service"

    def test_senr_prefix(self):
        assert derive_doc_type("senr0001_general.pdf") == "service"

    def test_uenr_prefix(self):
        assert derive_doc_type("uenr4444_general.pdf") == "service"

    def test_unknown_prefix(self):
        assert derive_doc_type("random_document.pdf") == "unknown"

    def test_schematic_wins_over_prefix(self):
        # "schematic" in name takes priority
        assert derive_doc_type("kenr1234_schematic.pdf") == "schematic"

    def test_troubleshooting_wins_over_prefix(self):
        assert derive_doc_type("kenr1234_troubleshooting.pdf") == "troubleshooting"


# ─────────────────────────────────────────────────────────────────
# compute_file_hash
# ─────────────────────────────────────────────────────────────────

class TestComputeFileHash:

    def test_deterministic(self, tmp_path):
        f = tmp_path / "test.pdf"
        f.write_bytes(b"hello world")

        h1 = compute_file_hash(f)
        h2 = compute_file_hash(f)
        assert h1 == h2

    def test_truncated_to_16_chars(self, tmp_path):
        f = tmp_path / "test.pdf"
        f.write_bytes(b"content")

        h = compute_file_hash(f)
        assert len(h) == 16

    def test_different_content_different_hash(self, tmp_path):
        f1 = tmp_path / "a.pdf"
        f1.write_bytes(b"aaa")
        f2 = tmp_path / "b.pdf"
        f2.write_bytes(b"bbb")

        assert compute_file_hash(f1) != compute_file_hash(f2)


# ─────────────────────────────────────────────────────────────────
# extract_pdf_text
# ─────────────────────────────────────────────────────────────────

class TestExtractPdfText:

    @patch("services.manuals_indexer.pdfplumber.open")
    def test_extracts_pages(self, mock_open):
        mock_pdf = MagicMock()
        page1 = MagicMock()
        page1.extract_text.return_value = "  Page one content  "
        page2 = MagicMock()
        page2.extract_text.return_value = "Page two content"
        mock_pdf.pages = [page1, page2]
        mock_open.return_value.__enter__ = MagicMock(return_value=mock_pdf)
        mock_open.return_value.__exit__ = MagicMock(return_value=False)

        pages = extract_pdf_text(Path("/fake/doc.pdf"))

        assert len(pages) == 2
        assert pages[0]["page_num"] == 1
        assert pages[0]["text"] == "Page one content"  # stripped
        assert pages[0]["char_count"] == 20  # len of "  Page one content  "
        assert pages[1]["page_num"] == 2

    @patch("services.manuals_indexer.pdfplumber.open")
    def test_empty_page_returns_empty_text(self, mock_open):
        mock_pdf = MagicMock()
        page = MagicMock()
        page.extract_text.return_value = None
        mock_pdf.pages = [page]
        mock_open.return_value.__enter__ = MagicMock(return_value=mock_pdf)
        mock_open.return_value.__exit__ = MagicMock(return_value=False)

        pages = extract_pdf_text(Path("/fake/empty.pdf"))

        assert len(pages) == 1
        assert pages[0]["text"] == ""
        assert pages[0]["char_count"] == 0

    @patch("services.manuals_indexer.pdfplumber.open")
    def test_corrupt_pdf_returns_empty_list(self, mock_open):
        mock_open.side_effect = Exception("corrupt PDF")

        pages = extract_pdf_text(Path("/fake/corrupt.pdf"))
        assert pages == []

    @patch("services.manuals_indexer.pdfplumber.open")
    def test_pdf_with_no_pages(self, mock_open):
        mock_pdf = MagicMock()
        mock_pdf.pages = []
        mock_open.return_value.__enter__ = MagicMock(return_value=mock_pdf)
        mock_open.return_value.__exit__ = MagicMock(return_value=False)

        pages = extract_pdf_text(Path("/fake/no_pages.pdf"))
        assert pages == []


# ─────────────────────────────────────────────────────────────────
# create_database
# ─────────────────────────────────────────────────────────────────

class TestCreateDatabase:

    def test_creates_tables(self, tmp_path):
        db_path = tmp_path / "test.db"
        conn = create_database(db_path)

        cursor = conn.cursor()

        # Check pages table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='pages'")
        assert cursor.fetchone() is not None

        # Check FTS5 virtual table
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='pages_fts'")
        assert cursor.fetchone() is not None

        conn.close()

    def test_creates_indexes(self, tmp_path):
        db_path = tmp_path / "test.db"
        conn = create_database(db_path)
        cursor = conn.cursor()

        cursor.execute("SELECT name FROM sqlite_master WHERE type='index'")
        indexes = {row[0] for row in cursor.fetchall()}

        assert "idx_equipment" in indexes
        assert "idx_doc_type" in indexes
        assert "idx_filename" in indexes

        conn.close()

    def test_creates_triggers(self, tmp_path):
        db_path = tmp_path / "test.db"
        conn = create_database(db_path)
        cursor = conn.cursor()

        cursor.execute("SELECT name FROM sqlite_master WHERE type='trigger'")
        triggers = {row[0] for row in cursor.fetchall()}

        assert "pages_ai" in triggers
        assert "pages_ad" in triggers
        assert "pages_au" in triggers

        conn.close()

    def test_replaces_existing_db(self, tmp_path):
        db_path = tmp_path / "test.db"
        db_path.write_text("old content")

        conn = create_database(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='pages'")
        assert cursor.fetchone() is not None

        conn.close()

    def test_fts5_sync_via_trigger(self, tmp_path):
        """Inserting into pages should auto-populate pages_fts via trigger."""
        db_path = tmp_path / "test.db"
        conn = create_database(db_path)
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO pages (filepath, filename, equipment, doc_type, page_num, content)
            VALUES ('/path', 'doc.pdf', '3516', 'testing', 1, 'valve lash adjustment')
        """)
        conn.commit()

        # FTS5 search should find it
        cursor.execute("SELECT rowid FROM pages_fts WHERE pages_fts MATCH 'valve'")
        rows = cursor.fetchall()
        assert len(rows) == 1

        conn.close()


# ─────────────────────────────────────────────────────────────────
# scan_pdfs
# ─────────────────────────────────────────────────────────────────

class TestScanPdfs:

    def test_discovers_pdfs(self, tmp_path):
        # Create equipment folder with a PDF
        folder = tmp_path / "Main_Engine_3516"
        folder.mkdir()
        (folder / "sebu8145-00_om.pdf").write_bytes(b"fake pdf")
        (folder / "readme.txt").write_bytes(b"not a pdf")

        pdfs = scan_pdfs(tmp_path)
        assert len(pdfs) == 1
        assert pdfs[0]["equipment"] == "3516"
        assert pdfs[0]["doc_type"] == "O&M"
        assert pdfs[0]["filename"] == "sebu8145-00_om.pdf"

    def test_skips_missing_folders(self, tmp_path):
        # No folders created → should log warnings but not crash
        pdfs = scan_pdfs(tmp_path)
        assert pdfs == []

    def test_multiple_folders(self, tmp_path):
        for folder_name in ["Main_Engine_3516", "GenSet_C18"]:
            folder = tmp_path / folder_name
            folder.mkdir()
            (folder / "doc.pdf").write_bytes(b"content")

        pdfs = scan_pdfs(tmp_path)
        assert len(pdfs) == 2
        equipments = {p["equipment"] for p in pdfs}
        assert equipments == {"3516", "C18"}

    def test_derives_doc_type_from_filename(self, tmp_path):
        folder = tmp_path / "Thruster_C32"
        folder.mkdir()
        (folder / "kenr9999_troubleshooting.pdf").write_bytes(b"content")

        pdfs = scan_pdfs(tmp_path)
        assert pdfs[0]["doc_type"] == "troubleshooting"


# ─────────────────────────────────────────────────────────────────
# build_index
# ─────────────────────────────────────────────────────────────────

class TestBuildIndex:

    @patch("services.manuals_indexer.compute_file_hash", return_value="abc123")
    @patch("services.manuals_indexer.extract_pdf_text")
    def test_inserts_pages_and_tracks_stats(self, mock_extract, mock_hash, tmp_path):
        mock_extract.return_value = [
            {"page_num": 1, "text": "Page one", "char_count": 8},
            {"page_num": 2, "text": "Page two", "char_count": 8},
        ]

        db_path = tmp_path / "test.db"
        conn = create_database(db_path)

        pdfs = [{
            "filepath": Path("/fake/doc.pdf"),
            "filename": "doc.pdf",
            "equipment": "3516",
            "doc_type": "testing",
            "folder": "Main_Engine_3516",
        }]

        metadata = build_index(pdfs, conn)

        assert metadata["stats"]["total_files"] == 1
        assert metadata["stats"]["total_pages"] == 2
        assert metadata["stats"]["total_chars"] == 16
        assert metadata["stats"]["by_equipment"]["3516"] == 1
        assert metadata["stats"]["by_doc_type"]["testing"] == 1

        # Verify actual DB rows
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM pages")
        assert cursor.fetchone()[0] == 2

        conn.close()

    @patch("services.manuals_indexer.compute_file_hash", return_value="abc123")
    @patch("services.manuals_indexer.extract_pdf_text")
    def test_skips_pdf_with_no_text(self, mock_extract, mock_hash, tmp_path):
        mock_extract.return_value = []  # Empty — no pages extracted

        db_path = tmp_path / "test.db"
        conn = create_database(db_path)

        pdfs = [{
            "filepath": Path("/fake/empty.pdf"),
            "filename": "empty.pdf",
            "equipment": "C18",
            "doc_type": "O&M",
            "folder": "GenSet_C18",
        }]

        metadata = build_index(pdfs, conn)
        assert metadata["stats"]["total_files"] == 0
        assert metadata["stats"]["total_pages"] == 0

        conn.close()

    @patch("services.manuals_indexer.compute_file_hash", return_value="abc123")
    @patch("services.manuals_indexer.extract_pdf_text")
    def test_progress_callback(self, mock_extract, mock_hash, tmp_path):
        mock_extract.return_value = [
            {"page_num": 1, "text": "Content", "char_count": 7},
        ]

        db_path = tmp_path / "test.db"
        conn = create_database(db_path)

        callback = MagicMock()
        pdfs = [{
            "filepath": Path("/fake/doc.pdf"),
            "filename": "doc.pdf",
            "equipment": "3516",
            "doc_type": "testing",
            "folder": "Main_Engine_3516",
        }]

        build_index(pdfs, conn, progress_callback=callback)
        callback.assert_called_once_with(1, 1, "doc.pdf")

        conn.close()

    @patch("services.manuals_indexer.compute_file_hash", return_value="abc123")
    @patch("services.manuals_indexer.extract_pdf_text")
    def test_metadata_file_entries(self, mock_extract, mock_hash, tmp_path):
        mock_extract.return_value = [
            {"page_num": 1, "text": "Content", "char_count": 7},
        ]

        db_path = tmp_path / "test.db"
        conn = create_database(db_path)

        pdfs = [{
            "filepath": Path("/fake/doc.pdf"),
            "filename": "doc.pdf",
            "equipment": "3516",
            "doc_type": "testing",
            "folder": "Main_Engine_3516",
        }]

        metadata = build_index(pdfs, conn)

        file_key = "Main_Engine_3516/doc.pdf"
        assert file_key in metadata["files"]
        entry = metadata["files"][file_key]
        assert entry["equipment"] == "3516"
        assert entry["page_count"] == 1
        assert entry["hash"] == "abc123"

        conn.close()


# ─────────────────────────────────────────────────────────────────
# run_indexer (end-to-end)
# ─────────────────────────────────────────────────────────────────

class TestRunIndexer:

    @patch("services.manuals_indexer.extract_pdf_text")
    def test_end_to_end(self, mock_extract, tmp_path):
        mock_extract.return_value = [
            {"page_num": 1, "text": "Valve lash procedure", "char_count": 20},
        ]

        # Create equipment folder with a fake PDF
        folder = tmp_path / "Main_Engine_3516"
        folder.mkdir()
        pdf = folder / "sebu8145-00_om.pdf"
        pdf.write_bytes(b"fake pdf content")

        db_path = tmp_path / "engine_search.db"
        meta_path = tmp_path / "metadata.json"

        metadata = run_indexer(tmp_path, db_path, metadata_path=meta_path)

        assert metadata["stats"]["total_files"] == 1
        assert metadata["stats"]["total_pages"] == 1
        assert db_path.exists()

        # Metadata JSON written
        assert meta_path.exists()
        saved = json.loads(meta_path.read_text())
        assert saved["stats"]["total_files"] == 1

    @patch("services.manuals_indexer.extract_pdf_text")
    def test_no_pdfs_returns_error(self, mock_extract, tmp_path):
        # No folders → no PDFs
        metadata = run_indexer(tmp_path, tmp_path / "out.db")
        assert "error" in metadata

    @patch("services.manuals_indexer.extract_pdf_text")
    def test_no_metadata_path(self, mock_extract, tmp_path):
        """When metadata_path is None, no JSON file is written."""
        mock_extract.return_value = [
            {"page_num": 1, "text": "Content", "char_count": 7},
        ]

        folder = tmp_path / "Main_Engine_3516"
        folder.mkdir()
        (folder / "doc.pdf").write_bytes(b"content")

        db_path = tmp_path / "out.db"
        metadata = run_indexer(tmp_path, db_path, metadata_path=None)

        assert metadata["stats"]["total_files"] == 1
        # No metadata JSON file should exist
        assert not (tmp_path / "doc_metadata.json").exists()

    @patch("services.manuals_indexer.extract_pdf_text")
    def test_fts5_searchable_after_indexing(self, mock_extract, tmp_path):
        """After run_indexer, FTS5 search should work on the DB."""
        mock_extract.return_value = [
            {"page_num": 1, "text": "valve lash adjustment procedure", "char_count": 31},
        ]

        folder = tmp_path / "Main_Engine_3516"
        folder.mkdir()
        (folder / "doc.pdf").write_bytes(b"content")

        db_path = tmp_path / "search.db"
        run_indexer(tmp_path, db_path)

        # Open the DB and search
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT p.filename, p.page_num FROM pages p "
            "JOIN pages_fts ON p.id = pages_fts.rowid "
            "WHERE pages_fts MATCH 'valve'"
        )
        rows = cursor.fetchall()
        assert len(rows) == 1
        assert rows[0][0] == "doc.pdf"
        conn.close()

    @patch("services.manuals_indexer.extract_pdf_text")
    def test_progress_callback_called(self, mock_extract, tmp_path):
        mock_extract.return_value = [
            {"page_num": 1, "text": "Content", "char_count": 7},
        ]

        folder = tmp_path / "Main_Engine_3516"
        folder.mkdir()
        (folder / "doc.pdf").write_bytes(b"content")

        callback = MagicMock()
        run_indexer(tmp_path, tmp_path / "out.db", progress_callback=callback)
        assert callback.call_count == 1
