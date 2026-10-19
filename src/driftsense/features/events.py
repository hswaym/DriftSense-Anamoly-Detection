"""Operational event alignment and feature generation for DriftSense.

Aligns deployment, scaling, configuration, and traffic change events
with time series billing intervals.
Enforces strict anti-leakage invariants:
- Event timing rule: An event starting at time T NEVER influences any feature for t < T.
- Label isolation: Ground-truth anomaly labels (causes, severity, label_id) are strictly quarantined.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence

import pandas as pd

logger = logging.getLogger(__name__)

CANONICAL_EVENT_TYPES: Sequence[str] = (
    "DEPLOYMENT",
    "SCALING",
    "CONFIG_CHANGE",
    "TRAFFIC",
    "BATCH",
)

# Columns forbidden in feature matrices to enforce label isolation
FORBIDDEN_LABEL_COLUMNS: set[str] = {
    "label_id",
    "onset_timestamp",
    "offset_timestamp",
    "primary_cause",
    "contributing_causes",
    "severity_score",
    "verification_src",
}


def add_event_features(
    df: pd.DataFrame,
    events_df: pd.DataFrame | None = None,
    service_col: str = "ServiceName",
    time_col: str = "ChargePeriodStart",
    default_hours_since: float = 720.0,
) -> pd.DataFrame:
    """Align operational events with panel time series without lookahead leakage.

    Args:
        df: Input panel DataFrame with datetime `time_col`.
        events_df: Optional DataFrame conforming to Contract 5 (operational_events).
        service_col: Column identifying cloud service series.
        time_col: Column identifying time interval onset.
        default_hours_since: Default elapsed hours when no historical event exists.

    Returns:
        pd.DataFrame: DataFrame with event indicators and timing features.
    """
    df_out = df.copy()
    if not pd.api.types.is_datetime64_any_dtype(df_out[time_col]):
        df_out[time_col] = pd.to_datetime(df_out[time_col], utc=True)

    # Initialize default event feature columns
    for etype in CANONICAL_EVENT_TYPES:
        df_out[f"event_active_{etype.lower()}"] = 0
    df_out["hours_since_last_event"] = default_hours_since
    df_out["recent_event_count_24h"] = 0

    if events_df is None or events_df.empty:
        return df_out

    # Verify label isolation: forbid accidental ingestion of label table
    found_forbidden = FORBIDDEN_LABEL_COLUMNS.intersection(events_df.columns)
    if found_forbidden:
        raise ValueError(
            f"LABEL ISOLATION VIOLATION: Forbidden label table columns found in event DataFrame: {found_forbidden}"
        )

    ev = events_df.copy()
    ev["ts_start"] = pd.to_datetime(ev["ts_start"], utc=True)
    ev["ts_end"] = pd.to_datetime(ev["ts_end"], utc=True)

    # Align per service series
    for svc in df_out[service_col].unique():
        svc_mask = df_out[service_col] == svc
        svc_times = df_out.loc[svc_mask, time_col]

        # Relevant events are matching service or global 'ALL'
        svc_events = ev[
            (ev["service_id"] == svc) | (ev["service_id"] == "ALL")
        ].sort_values("ts_start")

        if svc_events.empty:
            continue

        for idx, t in svc_times.items():
            # STRICT ANTI-LEAKAGE: Only events starting at or before t can be seen at time t
            past_and_curr_events = svc_events[svc_events["ts_start"] <= t]
            if past_and_curr_events.empty:
                continue

            # Active events: started <= t and ended >= t
            active_events = past_and_curr_events[past_and_curr_events["ts_end"] >= t]
            for _, event_row in active_events.iterrows():
                etype = str(event_row.get("event_type", "")).upper()
                col = f"event_active_{etype.lower()}"
                if col in df_out.columns:
                    df_out.loc[idx, col] = 1

            # Time since most recent started event
            latest_start = past_and_curr_events["ts_start"].max()
            delta_hours = (t - latest_start).total_seconds() / 3600.0
            df_out.loc[idx, "hours_since_last_event"] = max(0.0, float(delta_hours))

            # Events within the last 24 hours
            window_24h = past_and_curr_events[
                past_and_curr_events["ts_start"] >= (t - pd.Timedelta(hours=24))
            ]
            df_out.loc[idx, "recent_event_count_24h"] = len(window_24h)

    return df_out
