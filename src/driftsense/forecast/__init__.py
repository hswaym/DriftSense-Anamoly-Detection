"""Forecasting models, prediction intervals, and reconciliation for DriftSense v2.

Provides:
- BaseForecaster: Abstract base class for all forecasters
- Baselines: SeasonalNaiveForecaster, MovingAverageForecaster
- Exponential Smoothing: ETSForecaster, ExponentialSmoothingForecaster
- SARIMA: SARIMAForecaster with robust seasonal auto-regression
- Boosted Trees: BoostedTreeForecaster (Tweedie / squared error), XGBoostForecaster
- Probabilistic & Conformal: QuantileForecaster, SplitConformalCalibrator
- Hierarchical Reconciliation: HierarchicalReconciler
"""

from __future__ import annotations

from driftsense.forecast.base import BaseForecaster
from driftsense.forecast.baselines import (
    MovingAverageForecaster,
    SeasonalNaiveForecaster,
)
from driftsense.forecast.boosted import (
    BoostedTreeForecaster,
    XGBoostForecaster,
)
from driftsense.forecast.conformal import SplitConformalCalibrator
from driftsense.forecast.ets import (
    ETSForecaster,
    ExponentialSmoothingForecaster,
)
from driftsense.forecast.quantile import QuantileForecaster
from driftsense.forecast.reconcile import HierarchicalReconciler
from driftsense.forecast.sarima import SARIMAForecaster

__all__ = [
    "BaseForecaster",
    "BoostedTreeForecaster",
    "ETSForecaster",
    "ExponentialSmoothingForecaster",
    "HierarchicalReconciler",
    "MovingAverageForecaster",
    "QuantileForecaster",
    "SARIMAForecaster",
    "SeasonalNaiveForecaster",
    "SplitConformalCalibrator",
    "XGBoostForecaster",
]
