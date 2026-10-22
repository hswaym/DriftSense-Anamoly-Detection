"""Calendar and cyclical feature engineering for DriftSense.

Generates temporal features from charge period timestamps without target lookahead:
- hour_of_day, day_of_week, day_of_month, is_weekend
- is_month_end, days_until_month_end, billing_cycle_day
- continuous circular trigonometric encodings (sin/cos of hour and day of week)
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


def add_calendar_features(
    df: pd.DataFrame,
    time_col: str = "ChargePeriodStart",
    billing_cycle_start_day: int = 1,
) -> pd.DataFrame:
    """Generate calendar and cyclical time features from timestamp.

    All calendar features are deterministic functions of the timestamp t
    and are therefore strictly known at prediction time without lookahead leakage.

    Args:
        df: Input DataFrame containing timestamp column.
        time_col: Name of datetime column.
        billing_cycle_start_day: Day of the month when billing cycle resets (default: 1).

    Returns:
        pd.DataFrame: DataFrame with calendar feature columns added.
    """
    df_out = df.copy()
    if not pd.api.types.is_datetime64_any_dtype(df_out[time_col]):
        df_out[time_col] = pd.to_datetime(df_out[time_col], utc=True)

    dt = df_out[time_col].dt
    hour = dt.hour
    dow = dt.dayofweek
    day = dt.day
    days_in_month = dt.days_in_month

    df_out["hour_of_day"] = hour.astype(int)
    df_out["day_of_week"] = dow.astype(int)
    df_out["is_weekend"] = (dow >= 5).astype(int)
    df_out["day_of_month"] = day.astype(int)

    # Month-end and billing cycle dynamics
    df_out["is_month_end"] = (day == days_in_month).astype(int)
    df_out["days_until_month_end"] = (days_in_month - day).astype(int)
    df_out["billing_cycle_day"] = (
        (day - billing_cycle_start_day) % days_in_month + 1
    ).astype(int)

    # Cyclical encodings (smooth circular continuity for hours and days)
    df_out["sin_hour"] = np.sin(2 * np.pi * hour / 24.0)
    df_out["cos_hour"] = np.cos(2 * np.pi * hour / 24.0)
    df_out["sin_dow"] = np.sin(2 * np.pi * dow / 7.0)
    df_out["cos_dow"] = np.cos(2 * np.pi * dow / 7.0)

    return df_out
