"""Idempotent dataset acquisition with SHA256 integrity verification."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import requests

from driftsense.runtime.config import compute_file_sha256

logger = logging.getLogger(__name__)


def acquire_dataset(
    url: str,
    destination: str | Path,
    expected_sha256: str | None = None,
    overwrite: bool = False,
    timeout_sec: int = 60,
) -> dict[str, Any]:
    """Idempotently download a dataset file and record its SHA256 digest.

    Args:
        url: Direct download URL for the target dataset.
        destination: Local path where the downloaded file should reside.
        expected_sha256: Optional expected SHA256 hash to verify against.
        overwrite: If True, allow replacing an existing destination file.
                   If False and file exists, raises FileExistsError (or skips if hash matches).
        timeout_sec: Network request timeout in seconds.

    Returns:
        dict[str, Any]: Status summary containing path, sha256, bytes, and cached flag.
    """
    dest_path = Path(destination)
    dest_path.parent.mkdir(parents=True, exist_ok=True)

    # 1. Idempotency check: if destination already exists
    if dest_path.is_file():
        existing_sha = compute_file_sha256(dest_path)
        if expected_sha256 and existing_sha.lower() == expected_sha256.lower():
            logger.info(
                "Destination file already exists with matching SHA256. Skipping download."
            )
            return {
                "path": dest_path.as_posix(),
                "sha256": existing_sha,
                "bytes": dest_path.stat().st_size,
                "cached": True,
            }

        if not overwrite:
            raise FileExistsError(
                f"Destination file '{dest_path}' already exists. "
                "Refusing to overwrite without explicit overwrite=True / --overwrite flag."
            )

    # 2. Perform streaming download
    logger.info("Downloading dataset from: %s", url)
    response = requests.get(url, stream=True, timeout=timeout_sec)
    response.raise_for_status()

    temp_path = dest_path.with_suffix(dest_path.suffix + ".tmp")
    try:
        with temp_path.open("wb") as f:
            for chunk in response.iter_content(chunk_size=65536):
                if chunk:
                    f.write(chunk)

        downloaded_sha = compute_file_sha256(temp_path)

        if expected_sha256 and downloaded_sha.lower() != expected_sha256.lower():
            temp_path.unlink(missing_ok=True)
            raise ValueError(
                f"Downloaded file checksum mismatch! Expected '{expected_sha256}', got '{downloaded_sha}'"
            )

        temp_path.replace(dest_path)
    finally:
        if temp_path.exists():
            temp_path.unlink(missing_ok=True)

    file_bytes = dest_path.stat().st_size
    return {
        "path": dest_path.as_posix(),
        "sha256": downloaded_sha,
        "bytes": file_bytes,
        "cached": False,
    }
