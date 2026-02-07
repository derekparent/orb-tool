#!/usr/bin/env python3
"""
PDF Indexer for Manuals Search Module

Scans equipment folders, extracts text page-by-page, builds SQLite FTS5 index.
Each page becomes a separate indexed document for page-level search results.

Consolidated from engine_tool into orb-tool.
"""

import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Callable, Optional

import pdfplumber
from tqdm import tqdm

# Equipment folders to index (relative to MANUALS_PDF_DIR)
EQUIPMENT_FOLDERS = [
    "Main_Engine_3516",
    "GenSet_C18",
    "Thruster_C32",
    "Emergency_C4.4",
]

# Metadata storage
METADATA_FILE = "doc_metadata.json"


def derive_equipment(folder_name: str) -> str:
    """Extract equipment model from folder name."""
    mapping = {
        "Main_Engine_3516": "3516",
        "GenSet_C18": "C18",
        "Thruster_C32": "C32",
        "Emergency_C4.4": "C4.4",
    }
    return mapping.get(folder_name, folder_name)


def derive_doc_type(filename: str) -> str:
    """
    Derive document type from filename prefix/content.

    Prefixes:
    - sebu* = Operation & Maintenance (O&M)
    - kenr*, renr*, senr*, uenr* = Service manuals
    - *schematic* or *_pub_schematics* = Wiring/electrical diagrams
    - *troubleshooting* = Troubleshooting guides
    """
    filename_lower = filename.lower()

    if "schematic" in filename_lower:
        return "schematic"

    if "troubleshooting" in filename_lower:
        return "troubleshooting"

    if filename_lower.startswith("sebu"):
        return "O&M"

    if any(filename_lower.startswith(p) for p in ["kenr", "renr", "senr", "uenr"]):
        if "disassembly" in filename_lower or "assembly" in filename_lower:
            return "disassembly"
        if "testing" in filename_lower or "adjusting" in filename_lower:
            return "testing"
        if "specification" in filename_lower:
            return "specifications"
        if "systems-operations" in filename_lower:
            return "systems"
        if "special-instructions" in filename_lower:
            return "special-instructions"
        return "service"

    return "unknown"


def compute_file_hash(filepath: Path) -> str:
    """Compute SHA256 hash of file for duplicate detection."""
    sha256 = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256.update(chunk)
    return sha256.hexdigest()[:16]


def extract_pdf_text(filepath: Path) -> list[dict]:
    """
    Extract text from PDF, page by page.

    Returns list of dicts with page_num, text, char_count.
    """
    pages = []
    try:
        with pdfplumber.open(filepath) as pdf:
            for page_num, page in enumerate(pdf.pages, start=1):
                text = page.extract_text() or ""
                pages.append({
                    "page_num": page_num,
                    "text": text.strip(),
                    "char_count": len(text),
                })
    except Exception as e:
        print(f"  ERROR extracting {filepath.name}: {e}")
    return pages


def create_database(db_path: Path) -> sqlite3.Connection:
    """
    Create SQLite database with FTS5 virtual table for full-text search.
    """
    # Remove existing database
    if db_path.exists():
        db_path.unlink()

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Create main pages table with metadata
    cursor.execute("""
        CREATE TABLE pages (
            id INTEGER PRIMARY KEY,
            filepath TEXT NOT NULL,
            filename TEXT NOT NULL,
            equipment TEXT NOT NULL,
            doc_type TEXT NOT NULL,
            page_num INTEGER NOT NULL,
            content TEXT NOT NULL
        )
    """)

    # Create FTS5 virtual table for full-text search
    # Using porter tokenizer for stemming and better matching
    cursor.execute("""
        CREATE VIRTUAL TABLE pages_fts USING fts5(
            content,
            content='pages',
            content_rowid='id',
            tokenize='porter unicode61'
        )
    """)

    # Create triggers to keep FTS in sync
    cursor.execute("""
        CREATE TRIGGER pages_ai AFTER INSERT ON pages BEGIN
            INSERT INTO pages_fts(rowid, content) VALUES (new.id, new.content);
        END
    """)

    cursor.execute("""
        CREATE TRIGGER pages_ad AFTER DELETE ON pages BEGIN
            INSERT INTO pages_fts(pages_fts, rowid, content) VALUES('delete', old.id, old.content);
        END
    """)

    cursor.execute("""
        CREATE TRIGGER pages_au AFTER UPDATE ON pages BEGIN
            INSERT INTO pages_fts(pages_fts, rowid, content) VALUES('delete', old.id, old.content);
            INSERT INTO pages_fts(rowid, content) VALUES (new.id, new.content);
        END
    """)

    # Create indexes for filtering
    cursor.execute("CREATE INDEX idx_equipment ON pages(equipment)")
    cursor.execute("CREATE INDEX idx_doc_type ON pages(doc_type)")
    cursor.execute("CREATE INDEX idx_filename ON pages(filename)")

    conn.commit()
    return conn


def scan_pdfs(pdf_dir: Path) -> list[dict]:
    """Scan equipment folders for PDFs."""
    pdfs = []
    for folder_name in EQUIPMENT_FOLDERS:
        folder_path = pdf_dir / folder_name
        if not folder_path.exists():
            print(f"WARNING: Folder not found: {folder_path}")
            continue

        equipment = derive_equipment(folder_name)

        for pdf_file in folder_path.glob("*.pdf"):
            doc_type = derive_doc_type(pdf_file.name)
            pdfs.append({
                "filepath": pdf_file,
                "filename": pdf_file.name,
                "equipment": equipment,
                "doc_type": doc_type,
                "folder": folder_name,
            })

    return pdfs


def build_index(
    pdfs: list[dict],
    conn: sqlite3.Connection,
    progress_callback: Optional[Callable[[int, int, str], None]] = None,
) -> dict:
    """
    Build SQLite FTS5 index from PDFs.

    Args:
        pdfs: List of PDF info dicts
        conn: Database connection
        progress_callback: Optional callback(current, total, filename) for progress updates

    Returns:
        Metadata dict with stats and file info.
    """
    cursor = conn.cursor()

    metadata = {
        "files": {},
        "stats": {
            "total_files": 0,
            "total_pages": 0,
            "total_chars": 0,
            "by_equipment": {},
            "by_doc_type": {},
        }
    }

    print(f"\nIndexing {len(pdfs)} PDFs...")

    for idx, pdf_info in enumerate(tqdm(pdfs, desc="Processing PDFs")):
        filepath = pdf_info["filepath"]
        filename = pdf_info["filename"]
        equipment = pdf_info["equipment"]
        doc_type = pdf_info["doc_type"]

        if progress_callback:
            progress_callback(idx + 1, len(pdfs), filename)

        # Extract text
        pages = extract_pdf_text(filepath)
        if not pages:
            print(f"  WARNING: No text extracted from {filename}")
            continue

        # Compute hash for duplicate detection
        file_hash = compute_file_hash(filepath)

        # Store file metadata (use filepath as key to handle duplicate filenames)
        file_key = f"{pdf_info['folder']}/{filename}"
        metadata["files"][file_key] = {
            "filepath": str(filepath),
            "equipment": equipment,
            "doc_type": doc_type,
            "page_count": len(pages),
            "total_chars": sum(p["char_count"] for p in pages),
            "hash": file_hash,
        }

        # Index each page
        for page in pages:
            cursor.execute("""
                INSERT INTO pages (filepath, filename, equipment, doc_type, page_num, content)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                str(filepath),
                filename,
                equipment,
                doc_type,
                page["page_num"],
                page["text"],
            ))

            metadata["stats"]["total_pages"] += 1
            metadata["stats"]["total_chars"] += page["char_count"]

        metadata["stats"]["total_files"] += 1

        # Update equipment stats
        if equipment not in metadata["stats"]["by_equipment"]:
            metadata["stats"]["by_equipment"][equipment] = 0
        metadata["stats"]["by_equipment"][equipment] += 1

        # Update doc_type stats
        if doc_type not in metadata["stats"]["by_doc_type"]:
            metadata["stats"]["by_doc_type"][doc_type] = 0
        metadata["stats"]["by_doc_type"][doc_type] += 1

    conn.commit()
    return metadata


def run_indexer(
    pdf_dir: Path,
    db_path: Path,
    metadata_path: Optional[Path] = None,
    progress_callback: Optional[Callable[[int, int, str], None]] = None,
) -> dict:
    """
    Main entry point for indexer.

    Args:
        pdf_dir: Path to directory containing equipment folders
        db_path: Path to output database file
        metadata_path: Optional path to save metadata JSON
        progress_callback: Optional progress callback(current, total, filename)

    Returns:
        Metadata dict with indexing stats
    """
    print("=" * 60)
    print("Marine Engineering Troubleshooting Hub - PDF Indexer")
    print("=" * 60)

    # Scan for PDFs
    print(f"\nScanning equipment folders in: {pdf_dir}")
    pdfs = scan_pdfs(pdf_dir)
    print(f"Found {len(pdfs)} PDF files")

    if not pdfs:
        print("ERROR: No PDFs found. Check folder paths.")
        return {"error": "No PDFs found"}

    # Create database
    print(f"\nCreating search index at: {db_path}")
    conn = create_database(db_path)

    # Build index
    metadata = build_index(pdfs, conn, progress_callback)
    conn.close()

    # Save metadata if path provided
    if metadata_path:
        with open(metadata_path, "w") as f:
            json.dump(metadata, f, indent=2)
        print(f"Metadata saved to: {metadata_path}")

    # Print summary
    print("\n" + "=" * 60)
    print("INDEXING COMPLETE")
    print("=" * 60)
    print(f"\nFiles indexed: {metadata['stats']['total_files']}")
    print(f"Pages indexed: {metadata['stats']['total_pages']}")
    print(f"Total characters: {metadata['stats']['total_chars']:,}")

    print("\nBy Equipment:")
    for equip, count in sorted(metadata["stats"]["by_equipment"].items()):
        print(f"  {equip}: {count} files")

    print("\nBy Document Type:")
    for doc_type, count in sorted(metadata["stats"]["by_doc_type"].items()):
        print(f"  {doc_type}: {count} files")

    print(f"\nDatabase saved to: {db_path}")

    return metadata
