"""Autoregressive and historical statistical feature engineering for DriftSense.

Generates strictly historical lag features, shifted rolling windows,
velocity deltas, and sparsity indicators per service series.
Enforces anti-leakage invariants:
- Lags strictly reference historical time steps (t - k for k >= 1).
- Rolling statistics are computed over shifted series (shift(1)) to exclude current-row target.
- Velocity deltas reference strictly historical lags.
- Zero-spend indicators reflect historical status (<= t - 1).
"""

from __future__ import annotations

import logging
from collections.abc import Sequence

import pandas as pd

logger = logging.getLogger(__name__)


def add_lag_features(
    df: pd.DataFrame,
    target_col: str = "EffectiveCost",
    service_col: str = "ServiceName",
    time_col: str = "ChargePeriodStart",
    lags: Sequence[int] = (1, 2, 3, 24, 168),
) -> pd.DataFrame:
    """Compute strictly historical lag features per service series.

    Invariant: For lag k, feature at time t equals target at time t-k.
    Current-row target at time t is NEVER included.

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
        windows: Window sizes in units of time steps (e.g. hours).
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

        mean_series = roll.mean().reset_index(level=0, drop=True)
        std_series = roll.std().reset_index(level=0, drop=True)
        max_series = roll.max().reset_index(level=0, drop=True)

        df_out[f"{target_col}_roll_mean_{w}h"] = mean_series
        df_out[f"{target_col}_roll_std_{w}h"] = std_series.fillna(0.0)
        df_out[f"{target_col}_roll_max_{w}h"] = max_series

    return df_out


def add_autoregressive_deltas(
    df: pd.DataFrame,
    target_col: str = "EffectiveCost",
    service_col: str = "ServiceName",
    time_col: str = "ChargePeriodStart",
) -> pd.DataFrame:
    """Compute historical velocity differences and sparsity indicators.

    All metrics are computed strictly using historical values (<= t - 1):
    - diff_1h: lag_1 - lag_2 (change over previous hour)
    - diff_24h: lag_1 - lag_24 (change over 24 hours ago)
    - is_zero_spend_lag1: binary flag indicating if lag_1 == 0
    - zero_spend_streak_hours: consecutive hours with zero spend up to t-1
    """
    df_out = df.sort_values(by=[service_col, time_col]).copy()

    # Ensure required lags exist
    lag1_col = f"{target_col}_lag_1"
    lag2_col = f"{target_col}_lag_2"
    lag24_col = f"{target_col}_lag_24"

    if lag1_col not in df_out.columns:
        df_out[lag1_col] = df_out.groupby(service_col)[target_col].shift(1)
    if lag2_col not in df_out.columns:
        df_out[lag2_col] = df_out.groupby(service_col)[target_col].shift(2)
    if lag24_col not in df_out.columns:
        df_out[lag24_col] = df_out.groupby(service_col)[target_col].shift(24)

    df_out[f"{target_col}_diff_1h"] = df_out[lag1_col] - df_out[lag2_col]
    df_out[f"{target_col}_diff_24h"] = df_out[lag1_col] - df_out[lag24_col]

    # Sparsity / zero-inflation features
    lag1_val = df_out[lag1_col].fillna(0.0)
    df_out["is_zero_spend_lag1"] = (lag1_val <= 1e-6).astype(int)

    # Streak of zero spend up to t-1
    # Cumulative streak per group
    streaks = []
    for _, group in df_out.groupby(service_col):
        z = (group[target_col].shift(1).fillna(0.0) <= 1e-6).astype(int)
        # Compute streak: reset on 0
        streak = z * (z.groupby((z != z.shift()).cumsum()).cumcount() + 1)
        streaks.append(streak)

    if streaks:
        df_out["zero_spend_streak_hours"] = pd.concat(streaks).sort_index().astype(float)
    else:
        df_out["zero_spend_streak_hours"] = 0.0

    return df_out
