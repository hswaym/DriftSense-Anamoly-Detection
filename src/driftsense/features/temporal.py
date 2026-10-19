"""Temporal feature engineering module for DriftSense.

Generates calendar features, lag features, and rolling statistics per service series.
Enforces strict anti-leakage invariants:
- Rolling statistics are computed over shifted series (shift(1)) to exclude current-row target.
- Lags strictly reference historical time steps (t - k for k >= 1).
"""

from __future__ import annotations

import logging
from collections.abc import Sequence

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


def add_calendar_features(
    df: pd.DataFrame,
    time_col: str = "ChargePeriodStart",
) -> pd.DataFrame:
    """Generate calendar and cyclical time features from timestamp.

    Args:
        df: Input DataFrame containing timestamp column.
        time_col: Name of datetime column.

    Returns:
        pd.DataFrame: DataFrame with calendar feature columns added.
    """
    df_out = df.copy()
    if not pd.api.types.is_datetime64_any_dtype(df_out[time_col]):
        df_out[time_col] = pd.to_datetime(df_out[time_col], utc=True)

    dt = df_out[time_col].dt
    hour = dt.hour
    dow = dt.dayofweek

    df_out["hour_of_day"] = hour.astype(int)
    df_out["day_of_week"] = dow.astype(int)
    df_out["is_weekend"] = (dow >= 5).astype(int)
    df_out["day_of_month"] = dt.day.astype(int)

    # Cyclical encodings (smooth circular continuity for hours and days)
    df_out["sin_hour"] = np.sin(2 * np.pi * hour / 24.0)
    df_out["cos_hour"] = np.cos(2 * np.pi * hour / 24.0)
    df_out["sin_dow"] = np.sin(2 * np.pi * dow / 7.0)
    df_out["cos_dow"] = np.cos(2 * np.pi * dow / 7.0)

    return df_out


def add_lag_features(
    df: pd.DataFrame,
    target_col: str = "EffectiveCost",
    service_col: str = "ServiceName",
    time_col: str = "ChargePeriodStart",
    lags: Sequence[int] = (1, 2, 3, 24, 168),
) -> pd.DataFrame:
    """Compute strictly historical lag features per service series.

    Invariant: For lag k, feature at time t equals target at time t-k.
    Current-row target at time t is never included.

    Args:
        df: Input DataFrame.
        target_col: Column to lag (e.g. EffectiveCost).
        service_col: Column identifying time series panel.
        time_col: Timestamp column.
        lags: Sequence of integer lag steps (must all be >= 1).

    Returns:
        pd.DataFrame: DataFrame with lag columns added.
    """
    for lag in lags:
        if lag < 1:
            raise ValueError(f"Lag must be >= 1 to prevent data leakage. Got lag={lag}")

    df_out = df.sort_values(by=[service_col, time_col]).copy()

    for lag in lags:
        col_name = f"{target_col}_lag_{lag}"
        df_out[col_name] = df_out.groupby(service_col)[target_col].shift(lag)

    return df_out


def add_rolling_features(
    df: pd.DataFrame,
    target_col: str = "EffectiveCost",
    service_col: str = "ServiceName",
    time_col: str = "ChargePeriodStart",
    windows: Sequence[int] = (3, 6, 24, 168),
    min_periods: int = 1,
) -> pd.DataFrame:
    """Compute rolling statistics over historical windows per service series.

    Invariant: Strictly left-closed / shifted historical window.
    The value of target_col at time t is shifted by 1 before rolling calculation,
    ensuring that the rolling statistic for row t uses only observations <= t - 1.

    Args:
        df: Input DataFrame.
        target_col: Column to compute rolling statistics on.
        service_col: Column identifying time series panel.
        time_col: Timestamp column.
        windows: Window sizes in units of time steps (hours).
        min_periods: Minimum observations in window to compute statistic.

    Returns:
        pd.DataFrame: DataFrame with rolling mean, std, and max columns added.
    """
    df_out = df.sort_values(by=[service_col, time_col]).copy()

    # Shift by 1 first to guarantee zero current-row lookahead leakage
    shifted = df_out.groupby(service_col)[target_col].shift(1)

    for w in windows:
        if w < 1:
            raise ValueError(f"Rolling window must be >= 1. Got window={w}")

        roll = shifted.groupby(df_out[service_col]).rolling(
            window=w, min_periods=min_periods
        )

        # Reset multiindex created by groupby-rolling
        mean_series = roll.mean().reset_index(level=0, drop=True)
        std_series = roll.std().reset_index(level=0, drop=True)
        max_series = roll.max().reset_index(level=0, drop=True)

        df_out[f"{target_col}_roll_mean_{w}h"] = mean_series
        df_out[f"{target_col}_roll_std_{w}h"] = std_series.fillna(0.0)
        df_out[f"{target_col}_roll_max_{w}h"] = max_series

    return df_out
