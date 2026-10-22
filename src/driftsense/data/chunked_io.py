"""Chunked streaming IO for large multi-cloud billing files.

Enforces size and row limits, memory bounds, and streaming chunks for datasets up to 1M+ rows.
"""

from __future__ import annotations

import logging
from collections.abc import Generator
from pathlib import Path

import pandas as pd

from driftsense.ingest.detect_format import detect_file_encoding_and_delimiter

logger = logging.getLogger(__name__)

DEFAULT_CHUNK_SIZE = 50_000
DEFAULT_MAX_ROWS = 1_000_000
DEFAULT_MAX_FILE_SIZE_MB = 500  # 500 MB limit for single upload file


def read_billing_chunks(
    file_path: str | Path,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    max_rows: int = DEFAULT_MAX_ROWS,
    max_file_size_mb: int = DEFAULT_MAX_FILE_SIZE_MB,
) -> Generator[pd.DataFrame, None, None]:
    """Stream chunks of a cloud billing CSV file with safety limit enforcement.

    Yields:
        pd.DataFrame: Each chunk of data.

    Raises:
        FileNotFoundError: If file is absent.
        ValueError: If file exceeds size or row limits, or contains invalid encoding.
    """
    path = Path(file_path)
    if not path.is_file():
        raise FileNotFoundError(f"File not found: {path}")

    file_size_mb = path.stat().st_size / (1024 * 1024)
    if file_size_mb > max_file_size_mb:
        raise ValueError(
            f"File '{path.name}' size ({file_size_mb:.2f} MB) exceeds maximum allowed limit "
            f"of {max_file_size_mb} MB. Please partition into smaller archives."
        )

    encoding, delimiter = detect_file_encoding_and_delimiter(path)

    total_rows_read = 0
    try:
        reader = pd.read_csv(
            path,
            delimiter=delimiter,
            encoding=encoding,
            chunksize=chunk_size,
            low_memory=False,
        )
    except Exception as e:
        raise ValueError(f"Failed to open chunked reader for '{path.name}': {e}") from e

    for i, chunk in enumerate(reader):
        total_rows_read += len(chunk)
        if total_rows_read > max_rows:
            raise ValueError(
                f"File '{path.name}' exceeded maximum row limit of {max_rows:,} rows "
                f"(read {total_rows_read:,} rows). Aborting ingestion."
            )
        logger.debug("Yielding chunk %d with %d rows (total: %d)", i, len(chunk), total_rows_read)
        yield chunk


def read_full_dataset_bounded(
    file_path: str | Path,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    max_rows: int = DEFAULT_MAX_ROWS,
    max_file_size_mb: int = DEFAULT_MAX_FILE_SIZE_MB,
) -> pd.DataFrame:
    """Read full dataset by concatenating verified chunks up to memory budget."""
    chunks = list(
        read_billing_chunks(
            file_path=file_path,
            chunk_size=chunk_size,
            max_rows=max_rows,
            max_file_size_mb=max_file_size_mb,
        )
    )
    if not chunks:
        raise ValueError(f"No records read from '{file_path}'.")
    return pd.concat(chunks, ignore_index=True)
