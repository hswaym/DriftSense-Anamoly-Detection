"""Hierarchical and multi-grain aggregation features for DriftSense.

Handles:
- Multi-grain aggregation (hourly '1h', daily '1d').
- Hierarchical spend share features at strictly historical intervals (t - 1).
- Cross-series total spend reconciliation keys.
"""

from __future__ import annotations

import logging

import pandas as pd

logger = logging.getLogger(__name__)


def aggregate_grain(
    df: pd.DataFrame,
    grain: str = "1h",
    time_col: str = "ChargePeriodStart",
    service_col: str = "ServiceName",
    cost_cols: tuple[str, ...] = ("EffectiveCost", "BilledCost"),
    usage_col: str = "ConsumedQuantity",
) -> pd.DataFrame:
    """Aggregate canonical billing data to specified temporal grain.

    Supported grains:
    - '1h': hourly (default canonical grain)
    - '1d': daily roll-up

    Args:
        df: Input DataFrame with timestamp and cost columns.
        grain: Target grain string ('1h' or '1d').
        time_col: Name of charge period start timestamp column.
        service_col: Series partition column.
        cost_cols: Cost columns to sum.
        usage_col: Usage column to sum.

    Returns:
        pd.DataFrame: Aggregated DataFrame.
    """
    if grain == "1h":
        return df.copy()

    if grain != "1d":
        raise ValueError(f"Unsupported grain '{grain}'. Supported grains are '1h' and '1d'.")

    df_out = df.copy()
    if not pd.api.types.is_datetime64_any_dtype(df_out[time_col]):
        df_out[time_col] = pd.to_datetime(df_out[time_col], utc=True)

    # Truncate to start of day UTC
    df_out[time_col] = df_out[time_col].dt.floor("D")

    agg_dict: dict[str, str] = {}
    for c in cost_cols:
        if c in df_out.columns:
            agg_dict[c] = "sum"
    if usage_col in df_out.columns:
        agg_dict[usage_col] = "sum"

    # Retain non-numeric dimensions if uniform
    group_cols = [time_col, service_col]
    for opt_dim in ("SubAccountId", "BillingAccountId", "RegionId", "ProviderName"):
        if opt_dim in df_out.columns:
            group_cols.append(opt_dim)

    aggregated = (
        df_out.groupby(group_cols, as_index=False)[list(agg_dict.keys())]
        .sum()
        .sort_values(by=group_cols)
        .reset_index(drop=True)
    )
    return aggregated


def add_hierarchy_features(
    df: pd.DataFrame,
    target_col: str = "EffectiveCost",
    service_col: str = "ServiceName",
    time_col: str = "ChargePeriodStart",
    eps: float = 1e-6,
) -> pd.DataFrame:
    """Compute hierarchical spend share and total account spend features.

    Anti-leakage invariant:
    The total spend and service share are computed at time t-1 (strictly shifted)
    so that contemporaneous spend at time t is never leaked.

    Features generated:
    - total_spend_lag1: Total spend across all services at time t-1.
    - service_spend_share_lag1: Service spend at t-1 divided by total spend at t-1.
    """
    df_out = df.sort_values(by=[service_col, time_col]).copy()

    # Compute total spend per timestamp
    total_spend_per_t = df_out.groupby(time_col)[target_col].sum().rename("total_spend_curr")

    # Merge back to compute historical total spend
    df_merged = df_out.merge(total_spend_per_t, on=time_col, how="left")

    # Shift total spend strictly by 1 per service to represent t-1
    df_merged["total_spend_lag1"] = df_merged.groupby(service_col)["total_spend_curr"].shift(1).fillna(0.0)

    # Compute service target at t-1
    service_spend_lag1 = df_merged.groupby(service_col)[target_col].shift(1).fillna(0.0)

    # Compute historical share of total spend
    df_merged["service_spend_share_lag1"] = (
        service_spend_lag1 / (df_merged["total_spend_lag1"] + eps)
    ).clip(0.0, 1.0)

    df_merged.drop(columns=["total_spend_curr"], inplace=True)
    return df_merged
