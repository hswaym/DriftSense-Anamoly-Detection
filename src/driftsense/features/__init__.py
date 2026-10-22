"""Feature engineering package for DriftSense v2.

Provides leak-free feature pipelines supporting Mode A (history-expected)
and Mode B (usage-expected) forecasting paradigms:
- calendar: Deterministic calendar & cyclical trigonometric encodings
- autoregressive: Strictly historical lags, shifted rolling windows, velocity deltas, sparsity
- usage: Historical usage telemetry (Mode A) and contemporaneous usage (Mode B)
- events: Operational event alignment with strict causal timing
- hierarchy: Multi-grain aggregation and cross-series spend share
- builder: Unified FeaturePipeline and FeatureContract management
"""

from __future__ import annotations

from driftsense.features.autoregressive import (
    add_autoregressive_deltas,
    add_lag_features,
    add_rolling_features,
)
from driftsense.features.builder import (
    FORBIDDEN_CONTEMPORANEOUS_COST_COLUMNS,
    FORBIDDEN_FEATURE_LABELS,
    FeatureMetadata,
    FeaturePipeline,
    build_features,
)
from driftsense.features.calendar import add_calendar_features
from driftsense.features.events import (
    CANONICAL_EVENT_TYPES,
    FORBIDDEN_LABEL_COLUMNS,
    add_event_features,
)
from driftsense.features.hierarchy import add_hierarchy_features, aggregate_grain
from driftsense.features.usage import add_usage_features

__all__ = [
    "CANONICAL_EVENT_TYPES",
    "FORBIDDEN_CONTEMPORANEOUS_COST_COLUMNS",
    "FORBIDDEN_FEATURE_LABELS",
    "FORBIDDEN_LABEL_COLUMNS",
    "FeatureMetadata",
    "FeaturePipeline",
    "add_autoregressive_deltas",
    "add_calendar_features",
    "add_event_features",
    "add_hierarchy_features",
    "add_lag_features",
    "add_rolling_features",
    "add_usage_features",
    "aggregate_grain",
    "build_features",
]
