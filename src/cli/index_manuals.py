#!/usr/bin/env python3
"""
CLI command to re-index CAT engine PDFs for manuals search.

Usage:
    python -m cli.index_manuals
    python -m cli.index_manuals --pdf-dir /path/to/engine_tool
"""

import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

import click

from config import Config
from services.manuals_indexer import run_indexer


@click.command()
@click.option(
    "--pdf-dir",
    type=click.Path(exists=True, path_type=Path),
    default=None,
    help="Path to equipment folders (default: from MANUALS_PDF_DIR env or config)",
)
@click.option(
    "--db-path",
    type=click.Path(path_type=Path),
    default=None,
    help="Path to output database (default: data/engine_search.db)",
)
@click.option(
    "--save-metadata",
    is_flag=True,
    default=False,
    help="Save doc_metadata.json alongside database",
)
def index(pdf_dir: Path | None, db_path: Path | None, save_metadata: bool) -> None:
    """Re-index all PDFs in equipment folders."""
    # Use config defaults if not specified
    if pdf_dir is None:
        pdf_dir = Config.MANUALS_PDF_DIR

    if db_path is None:
        db_path = Config.MANUALS_DB_PATH

    # Ensure data directory exists
    db_path.parent.mkdir(parents=True, exist_ok=True)

    # Set metadata path if requested
    metadata_path = db_path.parent / "doc_metadata.json" if save_metadata else None

    # Run indexer
    result = run_indexer(
        pdf_dir=pdf_dir,
        db_path=db_path,
        metadata_path=metadata_path,
    )

    if "error" in result:
        click.echo(f"Indexing failed: {result['error']}", err=True)
        raise SystemExit(1)

    click.echo("\nIndexing complete!")


if __name__ == "__main__":
    index()
