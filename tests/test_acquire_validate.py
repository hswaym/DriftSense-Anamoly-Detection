"""Unit tests for dataset acquisition and validation logic."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from driftsense.data.acquire import acquire_dataset
from driftsense.data.validate import validate_dataset
from driftsense.runtime.config import compute_file_sha256


def test_acquire_dataset_idempotent_and_overwrite(tmp_path: Path):
    """Test idempotent acquisition and overwrite protection."""
    dest_file = tmp_path / "sample.csv"
    dest_file.write_text("colA,colB\n1,2\n", encoding="utf-8")
    original_sha = compute_file_sha256(dest_file)

    # 1. Existing file with matching hash should be skipped (cached: True)
    res_cached = acquire_dataset(
        url="http://fake-domain-not-called.local/data.csv",
        destination=dest_file,
        expected_sha256=original_sha,
        overwrite=False,
    )
    assert res_cached["cached"] is True
    assert res_cached["sha256"] == original_sha

    # 2. Existing file with different hash and overwrite=False should raise FileExistsError
    with pytest.raises(FileExistsError, match="Refusing to overwrite"):
        acquire_dataset(
            url="http://fake-domain-not-called.local/data.csv",
            destination=dest_file,
            expected_sha256="different_hash_12345",
            overwrite=False,
        )


def test_validate_tiny_focus_fixture(tiny_focus_csv: Path, tmp_path: Path):
    """Verify validate_dataset on conforming tiny FOCUS fixture."""
    report_file = tmp_path / "data_quality_report.json"
    report = validate_dataset(
        data_path=tiny_focus_csv,
        output_report_path=report_file,
    )

    assert report["status"] == "PASSED"
    assert report["total_rows"] == 20
    assert report["total_columns"] >= 20
    assert report["checks"]["core_columns_present"] is True
    assert report["checks"]["timestamp_parse_utc"] is True
    assert report["checks"]["monotonic_order_per_series"] is True
    assert report["checks"]["duplicate_rows_count"] == 0
    assert report_file.is_file()

    with report_file.open("r", encoding="utf-8") as f:
        saved_report = json.load(f)
    assert saved_report["status"] == "PASSED"


def test_validate_detects_data_issues(
    tmp_path: Path, tiny_focus_dataframe: pd.DataFrame
):
    """Verify validator flags negative cost, missing column, and duplicates."""
    corrupted_df = tiny_focus_dataframe.copy()
    # Introduce negative cost
    corrupted_df.loc[0, "EffectiveCost"] = -15.50
    # Introduce duplicate row
    corrupted_df = pd.concat([corrupted_df, corrupted_df.iloc[[0]]], ignore_index=True)
    # Drop a core column
    corrupted_df = corrupted_df.drop(columns=["ConsumedQuantity"])

    corrupted_csv = tmp_path / "corrupted_focus.csv"
    corrupted_df.to_csv(corrupted_csv, index=False)

    report = validate_dataset(data_path=corrupted_csv)
    assert report["status"] == "WARNINGS"
    assert report["checks"]["core_columns_present"] is False
    assert "ConsumedQuantity" in report["checks"]["missing_core_columns"]
    assert report["checks"]["duplicate_rows_count"] == 1
    assert report["checks"]["cost_validity"]["EffectiveCost"]["negative_count"] == 2
