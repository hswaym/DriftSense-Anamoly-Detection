"""Unit tests for malformed file rejection and clear error generation (Acceptance A3.2)."""

from pathlib import Path

import pytest

from driftsense.data.chunked_io import read_billing_chunks
from driftsense.ingest import detect_format, ingest_file

FIXTURES_DIR = Path("tests/fixtures")


def test_malformed_duplicate_headers():
    """Verify that duplicate column headers raise a clear ValueError."""
    path = FIXTURES_DIR / "malformed_dup_headers.csv"
    with pytest.raises(ValueError, match="duplicate column names in header"):
        detect_format(path)


def test_malformed_bad_encoding():
    """Verify that corrupt byte sequences raise a clear ValueError."""
    path = FIXTURES_DIR / "malformed_bad_encoding.csv"
    with pytest.raises(ValueError, match="Failed to decode"):
        detect_format(path)


def test_malformed_multi_currency():
    """Verify that datasets mixing multiple currencies fail with single-currency error."""
    path = FIXTURES_DIR / "malformed_multi_currency.csv"
    with pytest.raises(ValueError, match="Multi-currency billing detected"):
        ingest_file(path)


def test_malformed_nonexistent_file():
    """Verify FileNotFoundError on missing file path."""
    with pytest.raises(FileNotFoundError, match="Billing file not found"):
        ingest_file("tests/fixtures/non_existent_file_xyz.csv")


def test_chunked_io_row_limit_enforcement():
    """Verify that chunked reader raises ValueError when max_rows limit is exceeded."""
    path = FIXTURES_DIR / "focus_100.csv"
    # Set max_rows = 50 while file has 100 rows
    with pytest.raises(ValueError, match="exceeded maximum row limit of 50 rows"):
        list(read_billing_chunks(path, chunk_size=20, max_rows=50))


def test_chunked_io_file_size_limit_enforcement():
    """Verify that chunked reader raises ValueError when max_file_size_mb is exceeded."""
    path = FIXTURES_DIR / "focus_100.csv"
    # Set max_file_size_mb to an impossibly low threshold (e.g., 0.00001 MB = ~10 bytes)
    with pytest.raises(ValueError, match="exceeds maximum allowed limit"):
        list(read_billing_chunks(path, max_file_size_mb=0.00001))
