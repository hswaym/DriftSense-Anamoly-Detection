"""Temporal aggregation module for DriftSense datasets.

Aggregates individual billing charge lines to the canonical grain:
  ServiceName x Timestamp (hourly '1h' or daily '1D')
Supports continuous grid reindexing to guarantee no missing intervals for time-series forecasting.
"""

from __future__ import annotations

import logging
from typing import Any

import pandas as pd

logger = logging.getLogger(__name__)


def aggregate_to_canonical_grain(
    df: pd.DataFrame,
    grain: str = "1h",
    service_col: str = "ServiceName",
    time_col: str = "ChargePeriodStart",
    continuous_grid: bool = True,
    grid_scope: str = "per_service",
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Aggregate cleaned FOCUS billing records to canonical time series grain.

    Args:
        df: Cleaned FOCUS DataFrame with UTC datetime in `time_col`.
        grain: Temporal frequency ('1h', '1D', etc.).
        service_col: Column identifying the cloud service series.
        time_col: Column containing timestamp of interval onset.
        continuous_grid: If True, fills missing temporal steps with zeros.
        grid_scope: 'per_service' (service min-max) or 'global' (dataset min-max).

    Returns:
        tuple[pd.DataFrame, dict[str, Any]]: (Aggregated DataFrame, aggregation summary dict)
    """
    if df.empty:
        empty_summary = {
            "input_rows": 0,
            "output_rows": 0,
            "distinct_services": 0,
            "grain": grain,
            "grid_points_added": 0,
        }
        return pd.DataFrame(), empty_summary

    df_agg_input = df.copy()
    if not pd.api.types.is_datetime64_any_dtype(df_agg_input[time_col]):
        df_agg_input[time_col] = pd.to_datetime(df_agg_input[time_col], utc=True)

    # Floor timestamps to the specified grain
    df_agg_input["_grain_timestamp"] = df_agg_input[time_col].dt.floor(grain)

    # Define numeric aggregations
    agg_dict: dict[str, Any] = {
        "EffectiveCost": "sum",
        "BilledCost": "sum",
    }
    if "EffectiveCreditAmount" in df_agg_input.columns:
        agg_dict["EffectiveCreditAmount"] = "sum"
    if "BilledCreditAmount" in df_agg_input.columns:
        agg_dict["BilledCreditAmount"] = "sum"
    if "ConsumedQuantity" in df_agg_input.columns:
        agg_dict["ConsumedQuantity"] = "sum"

    # Group by service and grain timestamp
    grouped = df_agg_input.groupby(
        [service_col, "_grain_timestamp"], as_index=False
    ).agg(
        **{k: (k, v) for k, v in agg_dict.items()},
        RecordCount=(service_col, "size"),
    )

    grouped = grouped.rename(columns={"_grain_timestamp": time_col})

    grid_points_added = 0
    if continuous_grid and not grouped.empty:
        distinct_services = grouped[service_col].unique()
        reindexed_frames = []

        if grid_scope == "global":
            global_min = grouped[time_col].min()
            global_max = grouped[time_col].max()

        for svc in distinct_services:
            svc_df = grouped[grouped[service_col] == svc].copy()
            if grid_scope == "global":
                s_min, s_max = global_min, global_max
            else:
                s_min = svc_df[time_col].min()
                s_max = svc_df[time_col].max()

            full_idx = pd.date_range(
                start=s_min, end=s_max, freq=grain, tz="UTC", name=time_col
            )
            svc_df = svc_df.set_index(time_col)
            original_len = len(svc_df)

            svc_reindexed = svc_df.reindex(full_idx)
            grid_points_added += len(svc_reindexed) - original_len

            svc_reindexed[service_col] = svc
            for col in agg_dict:
                svc_reindexed[col] = svc_reindexed[col].fillna(0.0)
            svc_reindexed["RecordCount"] = (
                svc_reindexed["RecordCount"].fillna(0).astype(int)
            )

            reindexed_frames.append(svc_reindexed.reset_index())

        grouped = pd.concat(reindexed_frames, ignore_index=True)

    grouped = grouped.sort_values(by=[service_col, time_col]).reset_index(drop=True)

    summary = {
        "input_rows": len(df),
        "output_rows": len(grouped),
        "distinct_services": int(grouped[service_col].nunique())
        if not grouped.empty
        else 0,
        "grain": grain,
        "grid_points_added": grid_points_added,
        "min_timestamp": str(grouped[time_col].min()) if not grouped.empty else None,
        "max_timestamp": str(grouped[time_col].max()) if not grouped.empty else None,
    }

    return grouped, summary
