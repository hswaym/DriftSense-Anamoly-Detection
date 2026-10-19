"""Unit tests for runtime utilities (config, seed, hardware, manifest)."""

from __future__ import annotations

import random
from pathlib import Path

import numpy as np
import pytest

from driftsense.runtime.config import compute_file_sha256, load_config
from driftsense.runtime.hardware import check_hardware, get_gpu_info
from driftsense.runtime.manifest import ManifestBuilder, verify_manifest
from driftsense.runtime.seed import set_seed


def test_set_seed_reproducibility():
    """Verify set_seed produces identical random draws."""
    set_seed(123)
    val1 = random.random()
    np_val1 = np.random.rand()

    set_seed(123)
    val2 = random.random()
    np_val2 = np.random.rand()

    assert val1 == val2
    assert np_val1 == np_val2


def test_load_config_and_sha256(tmp_path: Path):
    """Verify YAML configuration loading and sha256 checksum."""
    cfg_file = tmp_path / "test_cfg.yaml"
    cfg_file.write_text(
        "dataset:\n  name: 'test'\nruntime:\n  seed: 42\n", encoding="utf-8"
    )

    data, sha = load_config(cfg_file)
    assert data["dataset"]["name"] == "test"
    assert data["runtime"]["seed"] == 42
    assert len(sha) == 64
    assert sha == compute_file_sha256(cfg_file)


def test_hardware_check():
    """Verify check_hardware returns expected keys."""
    hw = check_hardware(requested_device="cpu")
    assert "platform" in hw
    assert "cpu" in hw
    assert "ram_gb" in hw
    assert "disk_free_gb" in hw


def test_hardware_check_raises_on_missing_gpu():
    """Verify check_hardware raises RuntimeError when GPU is requested but unavailable."""
    if get_gpu_info() is None:
        with pytest.raises(
            RuntimeError, match="Requested execution device 'gpu' is absent"
        ):
            check_hardware(requested_device="gpu")


def test_manifest_build_and_verification(tmp_path: Path):
    """Verify manifest creation and checksum verification (happy path & tamper detection)."""
    # 1. Create a dummy artifact file
    art_file = tmp_path / "model_weights.bin"
    art_file.write_bytes(b"DRIFTSENSE_FAKE_WEIGHTS_DATA_12345")

    builder = ManifestBuilder(
        run_id="test_run_01",
        phase="PHASE_3",
        stage="test_stage",
        config_path="configs/data_focus.yaml",
        config_sha256="abc123sha",
        seed=42,
    )
    builder.add_artifact(art_file)
    manifest_path = builder.save(tmp_path)

    assert manifest_path.is_file()

    # Verify happy path
    is_valid, errors = verify_manifest(tmp_path)
    assert is_valid is True
    assert len(errors) == 0

    # Tamper with artifact file
    art_file.write_bytes(b"TAMPERED_CONTENT_67890")
    is_valid_tampered, errors_tampered = verify_manifest(tmp_path)
    assert is_valid_tampered is False
    assert any(
        "hash mismatch" in err.lower() or "size mismatch" in err.lower()
        for err in errors_tampered
    )
