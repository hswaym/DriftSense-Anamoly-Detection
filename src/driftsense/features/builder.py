"""Unified feature engineering pipeline for DriftSense v2.

Coordinates calendar features, autoregressive lags, rolling statistics,
usage telemetry, operational events, and hierarchical spend dynamics
into a leak-free, validated feature matrix.

Enforces strict anti-leakage invariants:
- Mode A (history-expected): Flags usage-driven spikes. Strictly excludes
  contemporaneous usage (ConsumedQuantity at time t).
- Mode B (usage-expected): Detects rate / efficiency anomalies. Adds
  contemporaneous usage (ConsumedQuantity at time t) with explicit labeling.
- Target Isolation: Contemporaneous cost columns (BilledCost, ListCost, ContractedCost)
  are strictly prohibited from entering the feature matrix (Rule C6).
- Label Isolation: Ground truth anomaly labels are quarantined and raise ValueError
  if detected in feature inputs.
- Fit-on-train Semantics: Feature statistics (mean, std, min, max) are fit strictly
  on the training partition and frozen for validation / testing.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

import pandas as pd

from driftsense.features.autoregressive import (
    add_autoregressive_deltas,
    add_lag_features,
    add_rolling_features,
)
from driftsense.features.calendar import add_calendar_features
from driftsense.features.events import FORBIDDEN_LABEL_COLUMNS, add_event_features
from driftsense.features.hierarchy import add_hierarchy_features, aggregate_grain
from driftsense.features.usage import add_usage_features

logger = logging.getLogger(__name__)

# Target cost variants that must NEVER leak into features predicting EffectiveCost
FORBIDDEN_CONTEMPORANEOUS_COST_COLUMNS: set[str] = {
    "EffectiveCost",
    "BilledCost",
    "ListCost",
    "ContractedCost",
    "EffectiveCostRaw",
    "BilledCostRaw",
    "ListCostRaw",
    "ContractedCostRaw",
}

# Extended label isolation set including synthetic scenario generator labels
FORBIDDEN_FEATURE_LABELS: set[str] = FORBIDDEN_LABEL_COLUMNS.union(
    {
        "is_anomaly",
        "incident_id",
        "fault_family",
        "true_cause",
        "is_synthetic",
        "is_decoy",
    }
)


@dataclass(frozen=True)
class FeatureMetadata:
    """Metadata specification for a single engineered feature."""

    name: str
    formula: str
    window: str
    includes_current_row: bool
    known_at_prediction_time: bool
    source_column: str
    mode: str  # "A", "B", or "Both"
    description: str


class FeaturePipeline:
    """End-to-end feature pipeline adhering strictly to anti-leakage invariants."""

    def __init__(
        self,
        mode: str = "A",
        grain: str = "1h",
        target_col: str = "EffectiveCost",
        service_col: str = "ServiceName",
        time_col: str = "ChargePeriodStart",
        usage_col: str = "ConsumedQuantity",
        cost_lags: Sequence[int] = (1, 2, 3, 24, 168),
        cost_windows: Sequence[int] = (3, 6, 24, 168),
        usage_lags: Sequence[int] = (1, 2, 24),
        usage_windows: Sequence[int] = (6, 24),
        include_hierarchy: bool = True,
        include_deltas: bool = True,
        scale_features: bool = False,
    ) -> None:
        """Initialize FeaturePipeline.

        Args:
            mode: Forecasting mode: 'A' (history-expected) or 'B' (usage-expected).
            grain: Temporal grain ('1h' or '1d').
            target_col: Prediction target column.
            service_col: Column identifying time series panel.
            time_col: Charge period start timestamp column.
            usage_col: Resource consumption telemetry column.
            cost_lags: Sequence of historical lag steps for target cost.
            cost_windows: Sequence of rolling window sizes for target cost.
            usage_lags: Sequence of historical lag steps for resource usage.
            usage_windows: Sequence of rolling window sizes for resource usage.
            include_hierarchy: Whether to include cross-series total spend features.
            include_deltas: Whether to include velocity deltas and zero-spend indicators.
            scale_features: Whether to apply train-fitted standard scaling.
        """
        if mode not in ("A", "B"):
            raise ValueError(f"Invalid mode '{mode}'. Supported modes are 'A' and 'B'.")
        if grain not in ("1h", "1d"):
            raise ValueError(f"Invalid grain '{grain}'. Supported grains are '1h' and '1d'.")

        self.mode = mode
        self.grain = grain
        self.target_col = target_col
        self.service_col = service_col
        self.time_col = time_col
        self.usage_col = usage_col
        self.cost_lags = tuple(cost_lags)
        self.cost_windows = tuple(cost_windows)
        self.usage_lags = tuple(usage_lags)
        self.usage_windows = tuple(usage_windows)
        self.include_hierarchy = include_hierarchy
        self.include_deltas = include_deltas
        self.scale_features = scale_features

        # State tracking (frozen from training partition)
        self.is_fitted = False
        self.fit_statistics_: dict[str, dict[str, float]] = {}
        self.feature_names_: list[str] = []

    def _generate_raw_features(
        self,
        df: pd.DataFrame,
        events_df: pd.DataFrame | None = None,
    ) -> pd.DataFrame:
        """Apply sequential feature transformations without fitting scalers."""
        # Check label isolation on input dataframe
        found_forbidden = FORBIDDEN_FEATURE_LABELS.intersection(df.columns)
        if found_forbidden:
            raise ValueError(
                f"LABEL ISOLATION ERROR: Forbidden ground-truth columns present in input dataframe: {found_forbidden}"
            )

        # 0. Grain roll-up if requested
        df_feats = aggregate_grain(
            df,
            grain=self.grain,
            time_col=self.time_col,
            service_col=self.service_col,
            cost_cols=(self.target_col, "BilledCost"),
            usage_col=self.usage_col,
        )

        # 1. Calendar & cyclical features (deterministic from timestamp t)
        df_feats = add_calendar_features(df_feats, time_col=self.time_col)

        # 2. Cost lags (historical t-k for k >= 1)
        df_feats = add_lag_features(
            df_feats,
            target_col=self.target_col,
            service_col=self.service_col,
            time_col=self.time_col,
            lags=self.cost_lags,
        )

        # 3. Cost rolling stats (strictly shifted by 1)
        df_feats = add_rolling_features(
            df_feats,
            target_col=self.target_col,
            service_col=self.service_col,
            time_col=self.time_col,
            windows=self.cost_windows,
        )

        # 4. Cost deltas and sparsity tracking
        if self.include_deltas:
            df_feats = add_autoregressive_deltas(
                df_feats,
                target_col=self.target_col,
                service_col=self.service_col,
                time_col=self.time_col,
            )

        # 5. Usage features (historical for Mode A, contemporaneous for Mode B)
        if self.usage_col in df_feats.columns:
            include_contemp = (self.mode == "B")
            df_feats = add_usage_features(
                df_feats,
                usage_col=self.usage_col,
                service_col=self.service_col,
                time_col=self.time_col,
                lags=self.usage_lags,
                rolling_windows=self.usage_windows,
                include_contemporaneous=include_contemp,
            )

        # 6. Operational event features
        df_feats = add_event_features(
            df_feats,
            events_df=events_df,
            service_col=self.service_col,
            time_col=self.time_col,
        )

        # 7. Hierarchy features (historical share at t-1)
        if self.include_hierarchy:
            df_feats = add_hierarchy_features(
                df_feats,
                target_col=self.target_col,
                service_col=self.service_col,
                time_col=self.time_col,
            )

        # Post-transformation verification of Label Isolation
        forbidden_present = FORBIDDEN_FEATURE_LABELS.intersection(df_feats.columns)
        if forbidden_present:
            raise ValueError(
                f"LABEL ISOLATION ERROR: Forbidden ground-truth columns present in feature matrix: {forbidden_present}"
            )

        return df_feats

    def fit(
        self,
        df_train: pd.DataFrame,
        events_df: pd.DataFrame | None = None,
    ) -> FeaturePipeline:
        """Fit feature pipeline strictly on the training partition.

        Identifies feature columns, excluding target, identifier, and contemporaneous
        cost columns, and computes mean, std, min, and max strictly on df_train.
        """
        df_raw_feats = self._generate_raw_features(df_train, events_df=events_df)

        # Base columns to exclude from feature matrix
        exclude_cols = {
            self.target_col,
            self.service_col,
            self.time_col,
            "ChargePeriodEnd",
            "Id",
            "Tags",
            "ProviderName",
            "SubAccountId",
            "BillingAccountId",
            "RegionId",
        }
        # Always exclude raw usage_col; Mode B provides ConsumedQuantity_contemporaneous explicitly
        exclude_cols.add(self.usage_col)

        # Contemporaneous cost columns MUST NEVER be features (Rule C6 / H1 audit)
        exclude_cols.update(FORBIDDEN_CONTEMPORANEOUS_COST_COLUMNS)

        numeric_cols = [
            c
            for c in df_raw_feats.columns
            if c not in exclude_cols and pd.api.types.is_numeric_dtype(df_raw_feats[c])
        ]

        self.feature_names_ = sorted(numeric_cols)
        self.fit_statistics_ = {}

        for col in self.feature_names_:
            col_vals = df_raw_feats[col].dropna()
            mean_val = float(col_vals.mean()) if not col_vals.empty else 0.0
            std_val = (
                float(col_vals.std())
                if len(col_vals) > 1 and col_vals.std() > 0
                else 1.0
            )
            self.fit_statistics_[col] = {
                "mean": mean_val,
                "std": std_val,
                "min": float(col_vals.min()) if not col_vals.empty else 0.0,
                "max": float(col_vals.max()) if not col_vals.empty else 1.0,
            }

        self.is_fitted = True
        logger.info(
            "FeaturePipeline (mode=%s, grain=%s) successfully fit on %d training rows (%d features).",
            self.mode,
            self.grain,
            len(df_train),
            len(self.feature_names_),
        )
        return self

    def transform(
        self,
        df: pd.DataFrame,
        events_df: pd.DataFrame | None = None,
    ) -> pd.DataFrame:
        """Transform a partition using frozen parameters from fit()."""
        if not self.is_fitted:
            raise RuntimeError(
                "FeaturePipeline must be fit on training data before calling transform()!"
            )

        df_feats = self._generate_raw_features(df, events_df=events_df)

        if self.scale_features:
            for col in self.feature_names_:
                stats = self.fit_statistics_.get(col)
                if stats and col in df_feats.columns:
                    mean = stats["mean"]
                    std = stats["std"]
                    df_feats[f"{col}_scaled"] = (df_feats[col] - mean) / std

        return df_feats

    def fit_transform(
        self,
        df_train: pd.DataFrame,
        events_df: pd.DataFrame | None = None,
    ) -> pd.DataFrame:
        """Fit on train and transform."""
        return self.fit(df_train, events_df=events_df).transform(
            df_train, events_df=events_df
        )

    def get_feature_contract(self) -> dict[str, FeatureMetadata]:
        """Return structured contract metadata for all features in this pipeline."""
        contract: dict[str, FeatureMetadata] = {}

        for name in self.feature_names_:
            includes_current = False
            known_at_t = True
            mode_app = "Both"
            window = "1h"
            source = "Engineered"
            formula = name
            desc = ""

            if name in ("hour_of_day", "day_of_week", "day_of_month", "is_weekend",
                        "is_month_end", "days_until_month_end", "billing_cycle_day"):
                includes_current = True
                source = self.time_col
                desc = f"Calendar dimension derived deterministically from {self.time_col}"
            elif name in ("sin_hour", "cos_hour", "sin_dow", "cos_dow"):
                includes_current = True
                source = self.time_col
                desc = f"Trigonometric circular encoding of {self.time_col}"
            elif "_lag_" in name:
                parts = name.split("_lag_")
                source = parts[0]
                lag_k = parts[1]
                formula = f"{source}(t - {lag_k})"
                window = f"{lag_k}h"
                desc = f"Historical observation of {source} lagged by {lag_k} steps"
            elif "_roll_mean_" in name or "_roll_std_" in name or "_roll_max_" in name:
                parts = name.split("_roll_")
                source = parts[0]
                stat_win = parts[1].split("_")
                stat = stat_win[0]
                win = stat_win[1]
                formula = f"{stat}({source}[t-{win}, t-1])"
                window = win
                desc = f"Historical rolling {stat} of {source} over shifted window {win}"
            elif "_diff_" in name:
                parts = name.split("_diff_")
                source = parts[0]
                step = parts[1]
                formula = f"{source}(t-1) - {source}(t-{step})"
                desc = f"Historical velocity difference of {source}"
            elif "_growth_pct_" in name:
                parts = name.split("_growth_pct_")
                source = parts[0]
                step = parts[1]
                formula = f"({source}(t-1) - {source}(t-{step})) / |{source}(t-{step})|"
                desc = f"Historical percentage change of {source}"
            elif name == "is_zero_spend_lag1":
                formula = "1 if EffectiveCost(t-1) == 0 else 0"
                desc = "Indicator of zero spend in immediately preceding interval"
            elif name == "zero_spend_streak_hours":
                formula = "consecutive zero-spend hours ending at t-1"
                desc = "Duration streak of zero cost up to previous step"
            elif name == "total_spend_lag1":
                formula = "sum_{services}(EffectiveCost(t-1))"
                desc = "Total account spend across all services at time t-1"
            elif name == "service_spend_share_lag1":
                formula = "EffectiveCost_{svc}(t-1) / total_spend_lag1"
                desc = "Proportion of total account spend contributed by this service at t-1"
            elif name == f"{self.usage_col}_contemporaneous":
                includes_current = True
                known_at_t = True  # In Mode B, current usage is known/given
                mode_app = "B"
                source = self.usage_col
                formula = f"{self.usage_col}(t)"
                desc = "Contemporaneous resource consumption quantity at time t (Mode B only)"
            elif name.startswith("event_active_"):
                etype = name.replace("event_active_", "").upper()
                formula = f"1 if active event of type {etype} at time t else 0"
                desc = f"Operational event of type {etype} active at time t"
            elif name == "hours_since_last_event":
                formula = "t - max(ts_start <= t)"
                desc = "Elapsed hours since the start of the most recent event"
            elif name == "recent_event_count_24h":
                formula = "count(events with ts_start in [t-24h, t])"
                desc = "Count of operational events initiated within trailing 24 hours"

            contract[name] = FeatureMetadata(
                name=name,
                formula=formula,
                window=window,
                includes_current_row=includes_current,
                known_at_prediction_time=known_at_t,
                source_column=source,
                mode=mode_app,
                description=desc,
            )

        return contract


def build_features(
    df: pd.DataFrame,
    events_df: pd.DataFrame | None = None,
    config: dict[str, Any] | None = None,
) -> tuple[pd.DataFrame, FeaturePipeline]:
    """Convenience factory function to build features and return pipeline.

    Args:
        df: Input DataFrame (e.g. canonical aggregated 1h).
        events_df: Optional operational events DataFrame.
        config: Optional configuration dictionary.

    Returns:
        tuple[pd.DataFrame, FeaturePipeline]: (Transformed DataFrame, fitted FeaturePipeline)
    """
    cfg = config or {}
    pipeline = FeaturePipeline(
        mode=cfg.get("mode", "A"),
        grain=cfg.get("grain", "1h"),
        target_col=cfg.get("target_col", "EffectiveCost"),
        service_col=cfg.get("service_col", "ServiceName"),
        time_col=cfg.get("time_col", "ChargePeriodStart"),
        usage_col=cfg.get("usage_col", "ConsumedQuantity"),
        cost_lags=cfg.get("cost_lags", [1, 2, 3, 24, 168]),
        cost_windows=cfg.get("cost_windows", [3, 6, 24, 168]),
        usage_lags=cfg.get("usage_lags", [1, 2, 24]),
        usage_windows=cfg.get("usage_windows", [6, 24]),
        include_hierarchy=cfg.get("include_hierarchy", True),
        include_deltas=cfg.get("include_deltas", True),
        scale_features=cfg.get("scale_features", False),
    )

    transformed_df = pipeline.fit_transform(df, events_df=events_df)
    return transformed_df, pipeline
