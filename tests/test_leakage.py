"""Mandatory anti-leakage verification suite for DriftSense.

Implements rigorous tests:
1. Perturbation test: Future data mutations never alter past feature values (bit-identical).
2. Fit-on-train test: Scaler statistics equal train-only values, never full dataset values.
3. Label isolation test: Ground-truth anomaly labels cannot enter feature matrices.
4. Event timing test: Events starting at T have zero influence on features at t < T.
5. Split test: Partitions are strictly forward-chaining with zero overlap and respected gaps.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from driftsense.eval.splits import chronological_split
from driftsense.features.builder import FeaturePipeline
from driftsense.features.events import add_event_features


@pytest.fixture
def panel_time_series() -> pd.DataFrame:
    """Generate a clean synthetic 48-hour panel for 2 services."""
    rows = []
    times = pd.date_range("2024-09-01 00:00:00", periods=48, freq="1h", tz="UTC")
    for svc in ["Compute_EC2", "Storage_S3"]:
        for i, t in enumerate(times):
            base_cost = 10.0 if svc == "Compute_EC2" else 2.0
            base_usage = 100.0 if svc == "Compute_EC2" else 500.0
            rows.append(
                {
                    "ServiceName": svc,
                    "ChargePeriodStart": t,
                    "EffectiveCost": base_cost + float(i % 5),
                    "BilledCost": base_cost + float(i % 5),
                    "ConsumedQuantity": base_usage + float(i * 2),
                }
            )
    return pd.DataFrame(rows)


def test_perturbation_leakage_invariance(panel_time_series: pd.DataFrame) -> None:
    """Perturbation Test: Modifying all data after T must leave features for <= T bit-identical."""
    df_orig = panel_time_series.copy()
    pipeline = FeaturePipeline()

    # 1. Compute features on unperturbed data
    feats_orig = pipeline.fit_transform(df_orig)

    # Choose cutoff timestamp T (hour 24)
    cutoff_t = pd.Timestamp("2024-09-02 00:00:00", tz="UTC")

    # 2. Mutate future data (> T) violently
    df_perturbed = df_orig.copy()
    future_mask = df_perturbed["ChargePeriodStart"] > cutoff_t
    df_perturbed.loc[future_mask, "EffectiveCost"] *= 1000.0
    df_perturbed.loc[future_mask, "ConsumedQuantity"] = np.random.RandomState(
        42
    ).uniform(10000, 50000, size=future_mask.sum())

    # 3. Compute features on perturbed data with a fresh pipeline
    pipeline_pert = FeaturePipeline()
    feats_pert = pipeline_pert.fit_transform(df_perturbed)

    # 4. Filter both matrices to historical window (<= T)
    hist_orig = (
        feats_orig[feats_orig["ChargePeriodStart"] <= cutoff_t]
        .sort_values(["ServiceName", "ChargePeriodStart"])
        .reset_index(drop=True)
    )
    hist_pert = (
        feats_pert[feats_pert["ChargePeriodStart"] <= cutoff_t]
        .sort_values(["ServiceName", "ChargePeriodStart"])
        .reset_index(drop=True)
    )

    # 5. Assert BIT-IDENTICAL equality across all feature columns
    feature_cols = [
        c for c in hist_orig.columns if c not in ["ServiceName", "ChargePeriodStart"]
    ]
    for col in feature_cols:
        pd.testing.assert_series_equal(
            hist_orig[col],
            hist_pert[col],
            obj=f"Perturbation Leakage Violation on feature '{col}' at or before T",
            check_exact=True,
        )


def test_fit_on_train_statistics(panel_time_series: pd.DataFrame) -> None:
    """Fit-on-Train Test: Scalers expose statistics equal to train slice only, not full data."""
    train_df, _, _, _ = chronological_split(
        panel_time_series, train_frac=0.6, val_frac=0.2, test_frac=0.2
    )

    pipeline = FeaturePipeline(scale_features=True)
    pipeline.fit(train_df)

    # Expose fit statistics
    train_stats = pipeline.fit_statistics_

    # Verify each feature's mean and std match train partition ONLY
    raw_train_feats = pipeline._generate_raw_features(train_df)
    for col in pipeline.feature_names_:
        col_vals = raw_train_feats[col].dropna()
        if col_vals.empty:
            assert train_stats[col]["mean"] == 0.0
        else:
            expected_mean = float(col_vals.mean())
            actual_mean = train_stats[col]["mean"]
            assert actual_mean == pytest.approx(expected_mean, rel=1e-5), (
                f"Scaler mean for {col} does not match train-slice mean"
            )

    # Compute full dataset raw feature mean to prove it differs from train statistics
    raw_full_feats = pipeline._generate_raw_features(panel_time_series)
    full_usage_mean = float(raw_full_feats["ConsumedQuantity_lag_1"].dropna().mean())
    train_usage_mean = train_stats["ConsumedQuantity_lag_1"]["mean"]
    # Train usage has lower mean because usage grows linearly over time in fixture
    assert train_usage_mean < full_usage_mean, (
        "Leakage: Train mean was computed over full data!"
    )


def test_label_isolation_enforcement(panel_time_series: pd.DataFrame) -> None:
    """Label Isolation Test: Ground truth label table columns are strictly blocked from feature pipeline."""
    # Create malicious DataFrame containing ground-truth anomaly label columns
    bad_events_df = pd.DataFrame(
        [
            {
                "service_id": "Compute_EC2",
                "ts_start": "2024-09-01 10:00:00",
                "ts_end": "2024-09-01 12:00:00",
                "primary_cause": "ROGUE_PROCESS_MEMORY_LEAK",  # FORBIDDEN
                "severity_score": 0.95,  # FORBIDDEN
                "label_id": "lbl_001",  # FORBIDDEN
            }
        ]
    )

    pipeline = FeaturePipeline()
    with pytest.raises(ValueError, match="LABEL ISOLATION"):
        pipeline.fit_transform(panel_time_series, events_df=bad_events_df)


def test_event_timing_invariance(panel_time_series: pd.DataFrame) -> None:
    """Event Timing Test: An event starting at T has ZERO effect on features for rows < T."""
    df = panel_time_series.copy()
    event_t = pd.Timestamp("2024-09-01 15:00:00", tz="UTC")

    events_df = pd.DataFrame(
        [
            {
                "service_id": "Compute_EC2",
                "ts_start": "2024-09-01 15:00:00",
                "ts_end": "2024-09-01 18:00:00",
                "event_type": "DEPLOYMENT",
                "event_source": "GitHub",
                "is_synthetic": False,
            }
        ]
    )

    # 1. Feature generation with event
    feats_with_event = add_event_features(df, events_df=events_df)

    # 2. Feature generation with NO events
    feats_no_event = add_event_features(df, events_df=None)

    # Compare features prior to event onset (< event_t)
    past_with = feats_with_event[feats_with_event["ChargePeriodStart"] < event_t]
    past_no = feats_no_event[feats_no_event["ChargePeriodStart"] < event_t]

    event_cols = [
        c for c in past_with.columns if c.startswith(("event_", "hours_since"))
    ]
    for col in event_cols:
        pd.testing.assert_series_equal(
            past_with[col],
            past_no[col],
            obj=f"Event timing violation: feature '{col}' was altered prior to event start time",
            check_exact=True,
        )

    # Check active state at and after event onset for target service
    active_mask = (
        (feats_with_event["ServiceName"] == "Compute_EC2")
        & (feats_with_event["ChargePeriodStart"] >= event_t)
        & (
            feats_with_event["ChargePeriodStart"]
            <= pd.Timestamp("2024-09-01 18:00:00", tz="UTC")
        )
    )
    assert (feats_with_event.loc[active_mask, "event_active_deployment"] == 1).all()


def test_chronological_split_strictness(panel_time_series: pd.DataFrame) -> None:
    """Split Test: Partitions satisfy train < val < test with zero overlap and respected purge gap."""
    purge_gap = 2
    train, val, test, info = chronological_split(
        panel_time_series,
        train_frac=0.60,
        val_frac=0.20,
        test_frac=0.20,
        purge_gap_hours=purge_gap,
    )

    # Strict temporal ordering
    assert info.train_end < info.val_start, "Train must strictly precede Validation"
    assert info.val_end < info.test_start, "Validation must strictly precede Test"

    # Purge gap duration enforcement
    val_gap_hours = (info.val_start - info.train_end).total_seconds() / 3600.0
    test_gap_hours = (info.test_start - info.val_end).total_seconds() / 3600.0
    assert val_gap_hours >= purge_gap, (
        f"Validation purge gap not respected: {val_gap_hours} < {purge_gap}"
    )
    assert test_gap_hours >= purge_gap, (
        f"Test purge gap not respected: {test_gap_hours} < {purge_gap}"
    )

    # Zero overlapping rows / indices
    assert len(set(train.index).intersection(val.index)) == 0
    assert len(set(val.index).intersection(test.index)) == 0
    assert len(set(train.index).intersection(test.index)) == 0
