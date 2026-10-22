"""Usage and consumption telemetry feature engineering for DriftSense.

Computes historical usage lags, consumption deltas, percentage growth,
and rolling usage statistics.
Supports two operational forecasting modes:
- Mode A (history-expected): No contemporaneous usage features at time t.
  All usage metrics reference historical measurements (< t). Detects usage-driven spikes.
- Mode B (usage-expected): Adds contemporaneous usage (ConsumedQuantity at time t).
  Detects rate / price / efficiency anomalies given observed consumption.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence

import pandas as pd

logger = logging.getLogger(__name__)


def add_usage_features(
    df: pd.DataFrame,
    usage_col: str = "ConsumedQuantity",
    service_col: str = "ServiceName",
    time_col: str = "ChargePeriodStart",
    lags: Sequence[int] = (1, 2, 24),
    rolling_windows: Sequence[int] = (6, 24),
    include_contemporaneous: bool = False,
    eps: float = 1e-6,
) -> pd.DataFrame:
    """Compute resource usage features for Mode A or Mode B.

    Args:
        df: Input DataFrame.
        usage_col: Column containing consumed resource quantity.
        service_col: Column identifying time series panel.
        time_col: Timestamp column.
        lags: Lag intervals to compute (all >= 1).
        rolling_windows: Rolling window sizes in hours.
        include_contemporaneous: If True (Mode B), retains contemporaneous usage
            at time t. If False (Mode A, default), uses strictly historical usage (< t).
        eps: Small epsilon to prevent division by zero in percentage growth.

    Returns:
        pd.DataFrame: DataFrame with usage feature columns added.
    """
    if usage_col not in df.columns:
        logger.warning(
            "Usage column '%s' not present in DataFrame. Skipping usage features.",
            usage_col,
        )
        return df.copy()

    df_out = df.sort_values(by=[service_col, time_col]).copy()
    usage_series = df_out.groupby(service_col)[usage_col]

    # Contemporaneous usage for Mode B
    if include_contemporaneous:
        df_out[f"{usage_col}_contemporaneous"] = df_out[usage_col]

    # Historical usage lags (strictly >= 1)
    for lag in lags:
        if lag < 1:
            raise ValueError(f"Usage lag must be >= 1. Got lag={lag}")
        df_out[f"{usage_col}_lag_{lag}"] = usage_series.shift(lag)

    # Usage differences and percentage changes based strictly on historical lags
    lag1 = df_out.get(f"{usage_col}_lag_1")
    lag2 = df_out.get(f"{usage_col}_lag_2")
    lag24 = df_out.get(f"{usage_col}_lag_24")

    if lag1 is not None and lag2 is not None:
        df_out[f"{usage_col}_diff_1h"] = lag1 - lag2
        df_out[f"{usage_col}_growth_pct_1h"] = (lag1 - lag2) / (lag2.abs() + eps)

    if lag1 is not None and lag24 is not None:
        df_out[f"{usage_col}_diff_24h"] = lag1 - lag24
        df_out[f"{usage_col}_growth_pct_24h"] = (lag1 - lag24) / (lag24.abs() + eps)

    # Rolling usage stats computed strictly on shift(1)
    shifted_usage = usage_series.shift(1)
    for w in rolling_windows:
        roll = shifted_usage.groupby(df_out[service_col]).rolling(
            window=w, min_periods=1
        )
        mean_s = roll.mean().reset_index(level=0, drop=True)
        std_s = roll.std().reset_index(level=0, drop=True)

        df_out[f"{usage_col}_roll_mean_{w}h"] = mean_s
        df_out[f"{usage_col}_roll_std_{w}h"] = std_s.fillna(0.0)

    return df_out
