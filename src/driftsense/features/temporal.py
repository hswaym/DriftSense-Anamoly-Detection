"""Temporal feature engineering module for DriftSense (backwards compatibility).

Re-exports calendar and autoregressive feature generators from specialized modules:
- calendar.py: add_calendar_features
- autoregressive.py: add_lag_features, add_rolling_features, add_autoregressive_deltas
"""

from __future__ import annotations

from driftsense.features.autoregressive import (
    add_autoregressive_deltas,
    add_lag_features,
    add_rolling_features,
)
from driftsense.features.calendar import add_calendar_features

__all__ = [
    "add_autoregressive_deltas",
    "add_calendar_features",
    "add_lag_features",
    "add_rolling_features",
]
