"""Unified feature engineering pipeline for DriftSense.

Coordinates calendar features, historical lags, rolling statistics,
usage telemetry, and operational events into a validated feature matrix.
Enforces strict fit-on-train semantics:
- Feature scalers / statistics are fit strictly on the training partition.
- Validation and test slices are transformed using frozen train statistics.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from typing import Any

import pandas as pd

from driftsense.features.events import FORBIDDEN_LABEL_COLUMNS, add_event_features
from driftsense.features.temporal import (
    add_calendar_features,
    add_lag_features,
    add_rolling_features,
)
from driftsense.features.usage import add_usage_features

logger = logging.getLogger(__name__)


class FeaturePipeline:
    """End-to-end feature pipeline adhering strictly to anti-leakage invariants."""

    def __init__(
        self,
        target_col: str = "EffectiveCost",
        service_col: str = "ServiceName",
        time_col: str = "ChargePeriodStart",
        usage_col: str = "ConsumedQuantity",
        cost_lags: Sequence[int] = (1, 2, 3, 24, 168),
        cost_windows: Sequence[int] = (3, 6, 24, 168),
        usage_lags: Sequence[int] = (1, 2, 24),
        usage_windows: Sequence[int] = (6, 24),
        scale_features: bool = False,
    ) -> None:
        self.target_col = target_col
        self.service_col = service_col
        self.time_col = time_col
        self.usage_col = usage_col
        self.cost_lags = cost_lags
        self.cost_windows = cost_windows
        self.usage_lags = usage_lags
        self.usage_windows = usage_windows
        self.scale_features = scale_features

        # Fit statistics (frozen from training partition)
        self.is_fitted = False
        self.fit_statistics_: dict[str, dict[str, float]] = {}
        self.feature_names_: list[str] = []

    def _generate_raw_features(
        self,
        df: pd.DataFrame,
        events_df: pd.DataFrame | None = None,
    ) -> pd.DataFrame:
        """Apply sequential feature transformations without fitting scalers."""
        df_feats = df.copy()

        # 1. Calendar & cyclical
        df_feats = add_calendar_features(df_feats, time_col=self.time_col)

        # 2. Cost lags (historical)
        df_feats = add_lag_features(
            df_feats,
            target_col=self.target_col,
            service_col=self.service_col,
            time_col=self.time_col,
            lags=self.cost_lags,
        )

        # 3. Cost rolling stats (strictly shifted)
        df_feats = add_rolling_features(
            df_feats,
            target_col=self.target_col,
            service_col=self.service_col,
            time_col=self.time_col,
            windows=self.cost_windows,
        )

        # 4. Usage features (historical)
        if self.usage_col in df_feats.columns:
            df_feats = add_usage_features(
                df_feats,
                usage_col=self.usage_col,
                service_col=self.service_col,
                time_col=self.time_col,
                lags=self.usage_lags,
                rolling_windows=self.usage_windows,
            )

        # 5. Operational event features
        df_feats = add_event_features(
            df_feats,
            events_df=events_df,
            service_col=self.service_col,
            time_col=self.time_col,
        )

        # Verification of Label Isolation
        forbidden_present = FORBIDDEN_LABEL_COLUMNS.intersection(df_feats.columns)
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

        Computes mean and std for numerical features exclusively on df_train.
        """
        df_raw_feats = self._generate_raw_features(df_train, events_df=events_df)

        # Determine feature columns (exclude metadata / target columns)
        exclude_cols = {
            self.target_col,
            f"{self.target_col}Raw",
            self.service_col,
            self.time_col,
            "ChargePeriodEnd",
            "Id",
            "Tags",
        }
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
            "FeaturePipeline successfully fit on %d training rows (%d features).",
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


def build_features(
    df: pd.DataFrame,
    events_df: pd.DataFrame | None = None,
    config: dict[str, Any] | None = None,
) -> tuple[pd.DataFrame, FeaturePipeline]:
    """Convenience function to build features and return pipeline.

    Args:
        df: Input DataFrame (e.g. canonical aggregated 1h).
        events_df: Optional operational events DataFrame.
        config: Optional configuration dictionary.

    Returns:
        tuple[pd.DataFrame, FeaturePipeline]: (Transformed DataFrame, fitted FeaturePipeline)
    """
    cfg = config or {}
    pipeline = FeaturePipeline(
        target_col=cfg.get("target_col", "EffectiveCost"),
        service_col=cfg.get("service_col", "ServiceName"),
        time_col=cfg.get("time_col", "ChargePeriodStart"),
        usage_col=cfg.get("usage_col", "ConsumedQuantity"),
        cost_lags=cfg.get("cost_lags", [1, 2, 3, 24, 168]),
        cost_windows=cfg.get("cost_windows", [3, 6, 24, 168]),
        usage_lags=cfg.get("usage_lags", [1, 2, 24]),
        usage_windows=cfg.get("usage_windows", [6, 24]),
        scale_features=cfg.get("scale_features", False),
    )

    transformed_df = pipeline.fit_transform(df, events_df=events_df)
    return transformed_df, pipeline
