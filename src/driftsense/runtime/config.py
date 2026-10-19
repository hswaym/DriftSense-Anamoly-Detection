"""Configuration loading, validation, and checksum utilities."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import yaml


def compute_file_sha256(file_path: str | Path) -> str:
    """Compute standard SHA256 hex digest of a file in 64KB chunks."""
    path = Path(file_path)
    if not path.is_file():
        raise FileNotFoundError(f"Target file not found for checksum: {file_path}")
    hasher = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


def load_config(config_path: str | Path) -> tuple[dict[str, Any], str]:
    """Load and parse YAML configuration file.

    Returns:
        tuple[dict, str]: Parsed configuration dictionary and its SHA256 hex digest.
    """
    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(f"Configuration file not found: {path}")

    config_sha256 = compute_file_sha256(path)

    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    if not isinstance(data, dict):
        raise TypeError(f"Configuration must be a mapping, got {type(data).__name__}")

    return data, config_sha256
