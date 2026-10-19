"""Unit tests for DriftSense data cleaning and aggregation modules.

Covers all Phase 4 cleaning rules:
- Deduplication
- Critical null dropping (ServiceName, ChargePeriodStart)
- Invalid timestamp parsing
- ConsumedQuantity imputation
- Unit string normalization
- Negative cost (refund/credit) handling
- Genuine cost spike preservation
- Monotonic sorting
- Canonical grain aggregation (hourly, daily)
- Continuous grid interpolation
- Cleaning log rule counters
- CLI 'clean' command integration
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from driftsense.cli import main
from driftsense.data.aggregate import aggregate_to_canonical_grain
from driftsense.data.clean import clean_focus_data


def test_clean_exact_duplicates(tiny_focus_dataframe: pd.DataFrame) -> None:
    """Test that exact duplicate rows are dropped and logged."""
    df_with_dups = pd.concat(
        [tiny_focus_dataframe, tiny_focus_dataframe.iloc[:3]], ignore_index=True
    )
    assert len(df_with_dups) == len(tiny_focus_dataframe) + 3

    df_cleaned, log = clean_focus_data(df_with_dups)
    assert log["exact_duplicates_dropped"] == 3
    assert len(df_cleaned) == len(tiny_focus_dataframe)
    assert log["final_rows"] == len(tiny_focus_dataframe)


def test_clean_missing_critical_keys(tiny_focus_dataframe: pd.DataFrame) -> None:
    """Test that rows missing ServiceName or ChargePeriodStart are dropped."""
    df = tiny_focus_dataframe.copy()
    df.loc[0, "ServiceName"] = None
    df.loc[1, "ChargePeriodStart"] = None

    df_cleaned, log = clean_focus_data(df)
    assert log["missing_services_dropped"] == 1
    assert log["missing_timestamps_dropped"] == 1
    assert len(df_cleaned) == len(tiny_focus_dataframe) - 2


def test_clean_invalid_timestamps(tiny_focus_dataframe: pd.DataFrame) -> None:
    """Test that unparseable timestamps are dropped and logged."""
    df = tiny_focus_dataframe.copy()
    df.loc[0, "ChargePeriodStart"] = "NOT_A_VALID_DATE_STRING"

    df_cleaned, log = clean_focus_data(df)
    assert log["invalid_timestamps_dropped"] == 1
    assert len(df_cleaned) == len(tiny_focus_dataframe) - 1


def test_clean_impute_consumed_quantity(tiny_focus_dataframe: pd.DataFrame) -> None:
    """Test that null ConsumedQuantity values are imputed with 0.0 and counted."""
    df = tiny_focus_dataframe.copy()
    df.loc[0, "ConsumedQuantity"] = np.nan
    df.loc[1, "ConsumedQuantity"] = np.nan

    df_cleaned, log = clean_focus_data(df)
    assert log["missing_consumed_quantity_imputed"] == 2
    assert df_cleaned.loc[0, "ConsumedQuantity"] == 0.0
    assert df_cleaned.loc[1, "ConsumedQuantity"] == 0.0


def test_clean_unit_normalization(tiny_focus_dataframe: pd.DataFrame) -> None:
    """Test that text units with whitespace are trimmed and logged."""
    df = tiny_focus_dataframe.copy()
    df.loc[0, "ConsumedUnit"] = "  Hours  "
    df.loc[1, "PricingUnit"] = "Hours\n"

    df_cleaned, log = clean_focus_data(df)
    assert log["unit_normalization_changes"] >= 2
    assert df_cleaned.loc[0, "ConsumedUnit"] == "Hours"
    assert df_cleaned.loc[1, "PricingUnit"] == "Hours"


def test_clean_negative_costs(tiny_focus_dataframe: pd.DataFrame) -> None:
    """Test that negative costs are segregated into credit columns and clipped to 0."""
    df = tiny_focus_dataframe.copy()
    df.loc[0, "EffectiveCost"] = -12.50
    df.loc[1, "BilledCost"] = -25.00

    df_cleaned, log = clean_focus_data(df)
    assert log["negative_effective_cost_handled"] == 1
    assert log["negative_billed_cost_handled"] == 1

    # Credit amounts capture absolute negative magnitudes
    assert df_cleaned.loc[0, "EffectiveCreditAmount"] == pytest.approx(12.50)
    assert df_cleaned.loc[1, "BilledCreditAmount"] == pytest.approx(25.00)

    # EffectiveCost and BilledCost are clipped non-negative
    assert df_cleaned.loc[0, "EffectiveCost"] == 0.0
    assert df_cleaned.loc[1, "BilledCost"] == 0.0


def test_clean_preserves_true_cost_spikes(tiny_focus_dataframe: pd.DataFrame) -> None:
    """Verify that genuine positive cost spikes are not modified during cleaning."""
    df = tiny_focus_dataframe.copy()
    spike_val = 50000.0
    df.loc[2, "EffectiveCost"] = spike_val

    df_cleaned, _ = clean_focus_data(df)
    assert df_cleaned.loc[2, "EffectiveCost"] == pytest.approx(spike_val)


def test_clean_monotonic_sorting(tiny_focus_dataframe: pd.DataFrame) -> None:
    """Test that cleaned data is sorted monotonically by ServiceName and ChargePeriodStart."""
    shuffled = tiny_focus_dataframe.sample(frac=1.0, random_state=42).reset_index(
        drop=True
    )
    df_cleaned, _ = clean_focus_data(shuffled)

    for svc in df_cleaned["ServiceName"].unique():
        svc_times = df_cleaned[df_cleaned["ServiceName"] == svc]["ChargePeriodStart"]
        assert svc_times.is_monotonic_increasing


def test_aggregate_hourly_grain(tiny_focus_dataframe: pd.DataFrame) -> None:
    """Test aggregation of cleaned records to hourly canonical grain."""
    df_cleaned, _ = clean_focus_data(tiny_focus_dataframe)
    df_agg, summary = aggregate_to_canonical_grain(df_cleaned, grain="1h")

    assert summary["distinct_services"] == 2
    assert summary["grain"] == "1h"
    assert "EffectiveCost" in df_agg.columns
    assert "ConsumedQuantity" in df_agg.columns
    assert "RecordCount" in df_agg.columns

    # Each service in fixture has 10 distinct hours
    assert summary["output_rows"] == 20
    assert df_agg["EffectiveCost"].sum() == pytest.approx(
        df_cleaned["EffectiveCost"].sum()
    )


def test_aggregate_daily_grain(tiny_focus_dataframe: pd.DataFrame) -> None:
    """Test aggregation of hourly records to daily canonical grain."""
    df_cleaned, _ = clean_focus_data(tiny_focus_dataframe)
    df_agg, summary = aggregate_to_canonical_grain(df_cleaned, grain="1D")

    # All fixture rows are on the same day (2024-09-18), so 2 services -> 2 daily rows
    assert summary["output_rows"] == 2
    assert summary["distinct_services"] == 2
    assert df_agg["EffectiveCost"].sum() == pytest.approx(
        df_cleaned["EffectiveCost"].sum()
    )


def test_aggregate_continuous_grid_gap_fill() -> None:
    """Test that missing time intervals are filled with 0.0 when continuous_grid=True."""
    # Create 3 points with missing intervals (hours 0, 1, and 4)
    records = [
        {
            "ServiceName": "S1",
            "ChargePeriodStart": "2024-09-18 00:00:00",
            "EffectiveCost": 1.0,
            "BilledCost": 1.0,
            "ConsumedQuantity": 1.0,
        },
        {
            "ServiceName": "S1",
            "ChargePeriodStart": "2024-09-18 01:00:00",
            "EffectiveCost": 2.0,
            "BilledCost": 2.0,
            "ConsumedQuantity": 2.0,
        },
        {
            "ServiceName": "S1",
            "ChargePeriodStart": "2024-09-18 04:00:00",
            "EffectiveCost": 5.0,
            "BilledCost": 5.0,
            "ConsumedQuantity": 5.0,
        },
    ]
    df = pd.DataFrame(records)
    df_agg, summary = aggregate_to_canonical_grain(df, grain="1h", continuous_grid=True)

    # Expected: hours 0, 1, 2, 3, 4 -> 5 total points (2 added)
    assert summary["output_rows"] == 5
    assert summary["grid_points_added"] == 2
    assert len(df_agg) == 5

    # Hours 2 and 3 should have cost 0.0 and RecordCount 0
    hour2 = df_agg[
        df_agg["ChargePeriodStart"] == pd.Timestamp("2024-09-18 02:00:00", tz="UTC")
    ]
    assert len(hour2) == 1
    assert hour2.iloc[0]["EffectiveCost"] == 0.0
    assert hour2.iloc[0]["RecordCount"] == 0


def test_cli_clean_command(tmp_path: Path, tiny_focus_csv: Path) -> None:
    """Test end-to-end driftsense clean CLI command with aggregation."""
    out_csv = tmp_path / "cleaned.csv"
    log_json = tmp_path / "clean_log.json"
    agg_csv = tmp_path / "aggregated.csv"

    exit_code = main(
        [
            "clean",
            "--input",
            str(tiny_focus_csv),
            "--output",
            str(out_csv),
            "--log-out",
            str(log_json),
            "--aggregate",
            "--grain",
            "1h",
            "--agg-output",
            str(agg_csv),
        ]
    )

    assert exit_code == 0
    assert out_csv.is_file()
    assert log_json.is_file()
    assert agg_csv.is_file()

    with open(log_json, encoding="utf-8") as f:
        log_data = json.load(f)

    assert "initial_rows" in log_data
    assert "final_rows" in log_data
    assert "negative_effective_cost_handled" in log_data
    assert log_data["initial_rows"] == 20
