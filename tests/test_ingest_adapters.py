"""Unit tests for multi-cloud billing ingestion adapters (Acceptance A3.1)."""

from pathlib import Path

import pandas as pd
import pytest

from driftsense.ingest import (
    REQUIRED_CANONICAL_COLUMNS,
    detect_format,
    ingest_file,
)

FIXTURES_DIR = Path("tests/fixtures")


def test_detect_format_providers():
    """Verify format auto-detection across all 4 cloud providers."""
    # FOCUS
    res_focus = detect_format(FIXTURES_DIR / "focus_100.csv")
    assert res_focus.provider == "FOCUS"
    assert res_focus.confidence > 0.8

    # AWS CUR
    res_aws = detect_format(FIXTURES_DIR / "aws_cur_100.csv")
    assert res_aws.provider == "AWS_CUR"
    assert res_aws.confidence > 0.8

    # Azure Cost Management
    res_azure = detect_format(FIXTURES_DIR / "azure_100.csv")
    assert res_azure.provider == "AZURE_COST"
    assert res_azure.confidence > 0.7

    # GCP Billing
    res_gcp = detect_format(FIXTURES_DIR / "gcp_100.csv")
    assert res_gcp.provider == "GCP_BILLING"
    assert res_gcp.confidence > 0.7


@pytest.mark.parametrize(
    "fixture_name, expected_provider",
    [
        ("focus_100.csv", "FOCUS"),
        ("aws_cur_100.csv", "AWS"),
        ("azure_100.csv", "AZURE"),
        ("gcp_100.csv", "GCP"),
    ],
)
def test_ingest_adapters_produce_canonical_schema(fixture_name, expected_provider):
    """Verify that all adapters normalize to the canonical schema and required columns."""
    file_path = FIXTURES_DIR / fixture_name
    df_canon, meta = ingest_file(
        file_path=file_path,
        provider="auto",
        tenant_id="11111111-2222-3333-4444-555555555555",
        default_currency="USD",
    )

    assert not df_canon.empty
    assert len(df_canon) == 100
    assert meta["canonical_rows"] == 100
    assert df_canon["tenant_id"].iloc[0] == "11111111-2222-3333-4444-555555555555"

    # Required columns must be present and non-null
    for col in REQUIRED_CANONICAL_COLUMNS:
        assert col in df_canon.columns, f"Missing required canonical column: {col}"
        assert not df_canon[col].isnull().all(), f"Column {col} is completely null"

    # Check timestamps are UTC
    assert pd.api.types.is_datetime64_any_dtype(df_canon["ChargePeriodStart"])
    assert pd.api.types.is_datetime64_any_dtype(df_canon["ChargePeriodEnd"])
    assert str(df_canon["ChargePeriodStart"].dt.tz).upper() == "UTC"

    # End timestamp must be strictly greater than start timestamp
    assert (df_canon["ChargePeriodEnd"] > df_canon["ChargePeriodStart"]).all()

    # Costs and quantities must be numeric
    assert pd.api.types.is_numeric_dtype(df_canon["EffectiveCost"])
    assert pd.api.types.is_numeric_dtype(df_canon["BilledCost"])
    assert pd.api.types.is_numeric_dtype(df_canon["ConsumedQuantity"])

    # Single currency invariant
    assert (df_canon["Currency"] == "USD").all()


def test_ingest_deduplication():
    """Verify that deduplication correctly drops duplicate rows when requested."""
    file_path = FIXTURES_DIR / "focus_100.csv"
    df_raw = pd.read_csv(file_path)

    # Append 10 duplicate rows
    df_with_dups = pd.concat([df_raw, df_raw.head(10)], ignore_index=True)
    temp_dup_path = FIXTURES_DIR / "temp_with_dups.csv"
    try:
        df_with_dups.to_csv(temp_dup_path, index=False)

        # Ingest with dedup='drop'
        df_dropped, meta_dropped = ingest_file(temp_dup_path, dedup="drop")
        assert len(df_dropped) == 100
        assert meta_dropped["dropped_duplicates"] == 10

        # Ingest with dedup='keep'
        df_kept, meta_kept = ingest_file(temp_dup_path, dedup="keep")
        assert len(df_kept) == 110
        assert meta_kept["dropped_duplicates"] == 0
    finally:
        if temp_dup_path.exists():
            temp_dup_path.unlink()


def test_ingest_refund_handling():
    """Verify refund handling policies ('include', 'exclude', 'zero_clamp')."""
    file_path = FIXTURES_DIR / "focus_100.csv"
    df_raw = pd.read_csv(file_path)

    # Inject negative refund costs into 5 rows
    df_raw.loc[:4, "EffectiveCost"] = -25.0
    temp_path = FIXTURES_DIR / "temp_refunds.csv"
    try:
        df_raw.to_csv(temp_path, index=False)

        # Policy: include
        df_inc, _ = ingest_file(temp_path, handle_refunds="include")
        assert (df_inc["EffectiveCost"] < 0).sum() == 5

        # Policy: exclude
        df_exc, _ = ingest_file(temp_path, handle_refunds="exclude")
        assert len(df_exc) == 95
        assert (df_exc["EffectiveCost"] < 0).sum() == 0

        # Policy: zero_clamp
        df_clamp, _ = ingest_file(temp_path, handle_refunds="zero_clamp")
        assert len(df_clamp) == 100
        assert (df_clamp["EffectiveCost"] < 0).sum() == 0
        assert (df_clamp["EffectiveCost"] == 0.0).sum() == 5
    finally:
        if temp_path.exists():
            temp_path.unlink()
