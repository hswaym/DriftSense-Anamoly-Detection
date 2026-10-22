"""Baseline naive and moving-average forecasting models for DriftSense v2.

Implements:
- SeasonalNaiveForecaster: Y(t) = Y(t - S) with S=24 (diurnal) or S=168 (weekly).
- MovingAverageForecaster: rolling average over historical window W on shifted target.
"""

from __future__ import annotations

from driftsense.forecast.naive import MovingAverageForecaster, SeasonalNaiveForecaster

__all__ = ["MovingAverageForecaster", "SeasonalNaiveForecaster"]
