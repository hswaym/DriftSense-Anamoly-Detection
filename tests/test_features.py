"""Functional unit tests for DriftSense feature engineering modules."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from driftsense.features.builder import build_features
from driftsense.features.events import add_event_features
from driftsense.features.temporal import (
    add_calendar_features,
    add_lag_features,
    add_rolling_features,
)
from driftsense.features.usage import add_usage_features


def test_calendar_features(tiny_focus_dataframe: pd.DataFrame) -> None:
    """Test calendar and cyclical trigonometric feature creation."""
    df_cal = add_calendar_features(tiny_focus_dataframe)

    assert "hour_of_day" in df_cal.columns
    assert "day_of_week" in df_cal.columns
    assert "is_weekend" in df_cal.columns
    assert "sin_hour" in df_cal.columns
    assert "cos_hour" in df_cal.columns

    # Check bounds
    assert df_cal["hour_of_day"].between(0, 23).all()
    assert df_cal["day_of_week"].between(0, 6).all()
    assert df_cal["is_weekend"].isin([0, 1]).all()
    assert df_cal["sin_hour"].between(-1.0, 1.0).all()
    assert df_cal["cos_hour"].between(-1.0, 1.0).all()


def test_lag_features(tiny_focus_dataframe: pd.DataFrame) -> None:
    """Test lag feature generation and input validation."""
    df_lag = add_lag_features(tiny_focus_dataframe, lags=[1, 2])
    assert "EffectiveCost_lag_1" in df_lag.columns
    assert "EffectiveCost_lag_2" in df_lag.columns

    # Verify invalid non-positive lag raises ValueError
    with pytest.raises(ValueError, match="Lag must be >= 1"):
        add_lag_features(tiny_focus_dataframe, lags=[0])


def test_rolling_features(tiny_focus_dataframe: pd.DataFrame) -> None:
    """Test rolling feature calculation and window validation."""
    df_roll = add_rolling_features(tiny_focus_dataframe, windows=[3])
    assert "EffectiveCost_roll_mean_3h" in df_roll.columns
    assert "EffectiveCost_roll_std_3h" in df_roll.columns
    assert "EffectiveCost_roll_max_3h" in df_roll.columns

    with pytest.raises(ValueError, match="Rolling window must be >= 1"):
        add_rolling_features(tiny_focus_dataframe, windows=[0])


def test_usage_features(tiny_focus_dataframe: pd.DataFrame) -> None:
    """Test usage features, growth metrics, and division safety."""
    df_usage = add_usage_features(
        tiny_focus_dataframe, lags=[1, 2], rolling_windows=[3]
    )
    assert "ConsumedQuantity_lag_1" in df_usage.columns
    assert "ConsumedQuantity_diff_1h" in df_usage.columns
    assert "ConsumedQuantity_growth_pct_1h" in df_usage.columns
    assert "ConsumedQuantity_roll_mean_3h" in df_usage.columns

    # Growth rate must not produce infs or NaNs from zero division
    assert not np.isinf(df_usage["ConsumedQuantity_growth_pct_1h"].dropna()).any()


def test_event_features_empty(tiny_focus_dataframe: pd.DataFrame) -> None:
    """Test event features with empty / None events table."""
    df_events = add_event_features(tiny_focus_dataframe, events_df=None)
    assert "event_active_deployment" in df_events.columns
    assert "hours_since_last_event" in df_events.columns
    assert (df_events["event_active_deployment"] == 0).all()
    assert (df_events["hours_since_last_event"] == 720.0).all()


def test_feature_pipeline_integration(tiny_focus_dataframe: pd.DataFrame) -> None:
    """Test end-to-end feature pipeline execution."""
    df_feats, pipeline = build_features(
        tiny_focus_dataframe,
        config={
            "cost_lags": [1, 2],
            "cost_windows": [3],
            "usage_lags": [1],
            "usage_windows": [3],
        },
    )

    assert pipeline.is_fitted
    assert len(pipeline.feature_names_) > 10
    assert "hour_of_day" in df_feats.columns
    assert "EffectiveCost_lag_1" in df_feats.columns
    assert "EffectiveCost_roll_mean_3h" in df_feats.columns
    assert "ConsumedQuantity_lag_1" in df_feats.columns
    assert "event_active_deployment" in df_feats.columns
