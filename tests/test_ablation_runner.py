"""Unit tests for Phase 10 controlled experiments and ablation runner."""

from __future__ import annotations

import pandas as pd
import pytest

from driftsense.eval.ablation import (
    SYNTHETIC_EVENT_CIRCULARITY_CAVEAT,
    AblationRunner,
    hash_file_sha256,
    select_arm_features,
    validate_splits_invariants,
)


def test_hash_protocol_file(tmp_path):
    """Test SHA-256 calculation for experiment protocol."""
    test_file = tmp_path / "protocol_test.md"
    test_file.write_text("Protocol specification contents", encoding="utf-8")
    h = hash_file_sha256(test_file)
    assert len(h) == 64
    assert h.isalnum()


def test_validate_splits_invariants_pass():
    """Verify chronological split validation passes on clean sequential partitions."""
    train_df = pd.DataFrame(
        {
            "ChargePeriodStart": pd.date_range("2024-09-01", periods=10, freq="h"),
            "EffectiveCost": [1.0] * 10,
        }
    )
    val_df = pd.DataFrame(
        {
            "ChargePeriodStart": pd.date_range("2024-09-01 11:00", periods=5, freq="h"),
            "EffectiveCost": [1.0] * 5,
        }
    )
    info = validate_splits_invariants(train_df, val_df)
    assert info["leakage_free"] is True
    assert info["train_rows"] == 10
    assert info["val_rows"] == 5


def test_validate_splits_invariants_detects_leakage():
    """Verify chronological split validation catches temporal overlap."""
    train_df = pd.DataFrame(
        {
            "ChargePeriodStart": pd.date_range(
                "2024-09-01 00:00", periods=10, freq="h"
            ),
            "EffectiveCost": [1.0] * 10,
        }
    )
    val_df = pd.DataFrame(
        {
            "ChargePeriodStart": pd.date_range("2024-09-01 05:00", periods=5, freq="h"),
            "EffectiveCost": [1.0] * 5,
        }
    )
    with pytest.raises(ValueError, match="CHRONOLOGICAL LEAKAGE DETECTED"):
        validate_splits_invariants(train_df, val_df)


def test_select_arm_features():
    """Verify feature selection logic isolates cost, usage, and event subsets."""
    cols = [
        "EffectiveCost",
        "ChargePeriodStart",
        "ServiceName",
        "EffectiveCost_lag_1h",
        "EffectiveCost_roll_mean_24h",
        "hour_of_day",
        "is_weekend",
        "ConsumedQuantity",
        "ConsumedQuantity_lag_1h",
        "ConsumedQuantity_roll_mean_24h",
        "event_active_deployment",
        "recent_event_count_24h",
        "anomaly_label",
    ]

    # Arm 1: Cost-Only
    cost_only = select_arm_features(cols, "cost_only")
    assert "EffectiveCost_lag_1h" in cost_only
    assert "EffectiveCost_roll_mean_24h" in cost_only
    assert "hour_of_day" in cost_only
    assert "ConsumedQuantity" not in cost_only
    assert "event_active_deployment" not in cost_only
    assert "anomaly_label" not in cost_only

    # Arm 2: Cost + Usage
    cost_usage = select_arm_features(cols, "cost_usage")
    assert "EffectiveCost_lag_1h" in cost_usage
    assert "ConsumedQuantity" in cost_usage
    assert "ConsumedQuantity_lag_1h" in cost_usage
    assert "event_active_deployment" not in cost_usage

    # Arm 3: Cost + Usage + Events
    cost_events = select_arm_features(cols, "cost_usage_events")
    assert "EffectiveCost_lag_1h" in cost_events
    assert "ConsumedQuantity" in cost_events
    assert "event_active_deployment" in cost_events
    assert "recent_event_count_24h" in cost_events
    assert "anomaly_label" not in cost_events


def test_ablation_runner_smoke():
    """Smoke test of AblationRunner on synthetic data across 3 random seeds."""
    # Build synthetic train and val partitions
    train_times = pd.date_range("2024-09-01 00:00", periods=72, freq="h")
    val_times = pd.date_range("2024-09-04 00:00", periods=36, freq="h")

    def make_df(times):
        df = pd.DataFrame(
            {
                "ChargePeriodStart": times,
                "ServiceName": "TestCompute",
                "EffectiveCost": [10.0 + (i % 24) * 0.5 for i in range(len(times))],
                "EffectiveCost_lag_1h": [10.0] * len(times),
                "EffectiveCost_lag_24h": [10.0] * len(times),
                "EffectiveCost_roll_mean_24h": [10.0] * len(times),
                "hour_of_day": [t.hour for t in times],
                "day_of_week": [t.dayofweek for t in times],
                "is_weekend": [1 if t.dayofweek >= 5 else 0 for t in times],
                "ConsumedQuantity": [5.0] * len(times),
                "ConsumedQuantity_lag_1h": [5.0] * len(times),
                "event_active_deployment": [0] * len(times),
                "recent_event_count_24h": [0] * len(times),
            }
        )
        return df

    df_train = make_df(train_times)
    df_val = make_df(val_times)

    config = {
        "experiment": {
            "seeds": [42, 123, 999],
            "models": {
                "xgboost": {"n_estimators": 5, "max_depth": 3, "learning_rate": 0.1}
            },
        },
        "dataset": {
            "target_col": "EffectiveCost",
            "time_col": "ChargePeriodStart",
            "service_col": "ServiceName",
        },
    }

    runner = AblationRunner(config=config)
    res = runner.run_all(df_train, df_val)

    assert "arms" in res
    assert "arm_1" in res["arms"]
    assert "arm_2" in res["arms"]
    assert "arm_3" in res["arms"]
    assert "arm_4" in res["arms"]
    assert "arm_5" in res["arms"]
    assert "arm_6" in res["arms"]
    assert "arm_7" in res["arms"]

    # Verify seed variance reporting (A10.2)
    arm1 = res["arms"]["arm_1"]
    assert len(arm1["per_seed"]) == 3
    assert "mean_wape" in arm1
    assert "std_wape" in arm1

    # Verify circularity caveat is documented (A10.3)
    assert res["circularity_caveat"] == SYNTHETIC_EVENT_CIRCULARITY_CAVEAT

    # Verify summary table
    assert len(res["summary_records"]) >= 6


def test_ablation_runner_quarantines_test_split():
    """Verify test split paths are strictly rejected to prevent Phase 10 leakage."""
    from driftsense.eval.ablation import validate_split_paths

    with pytest.raises(PermissionError, match="TEST QUARANTINE VIOLATION"):
        validate_split_paths(
            "data/splits/train_features.csv", "data/splits/test_features.csv"
        )
