"""Anomaly detection engines, materiality filters, and severity scoring for DriftSense v2.

Provides:
- BaseAnomalyDetector: Abstract detector interface
- ForecastIntervalExceedanceDetector: Primary conformal interval exceedance detector
- MaterialityFilter, MaterialityThresholds: Economic materiality thresholding
- PersistenceRule: Temporal k-of-n persistence filtering
- SeverityScorer, SeverityTier: Multidimensional business severity scoring
- LevelShiftDetector: Sustained structural change-point detector
- Baselines: ZScoreDetector, RollingThresholdDetector, IsolationForestDetector, OneClassSVMDetector
"""

from __future__ import annotations

from driftsense.detect.base import BaseAnomalyDetector
from driftsense.detect.changepoint import LevelShiftDetector
from driftsense.detect.iforest import IsolationForestDetector
from driftsense.detect.interval import ForecastIntervalExceedanceDetector
from driftsense.detect.materiality import (
    MaterialityFilter,
    MaterialityThresholds,
)
from driftsense.detect.ocsvm import OneClassSVMDetector
from driftsense.detect.persistence import PersistenceRule
from driftsense.detect.rolling import RollingThresholdDetector
from driftsense.detect.severity import SeverityScorer, SeverityTier
from driftsense.detect.zscore import ZScoreDetector

__all__ = [
    "BaseAnomalyDetector",
    "ForecastIntervalExceedanceDetector",
    "IsolationForestDetector",
    "LevelShiftDetector",
    "MaterialityFilter",
    "MaterialityThresholds",
    "OneClassSVMDetector",
    "PersistenceRule",
    "RollingThresholdDetector",
    "SeverityScorer",
    "SeverityTier",
    "ZScoreDetector",
]
