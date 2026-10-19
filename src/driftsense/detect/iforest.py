"""Isolation Forest multi-feature anomaly detector for DriftSense."""

from __future__ import annotations

import datetime
from typing import Any

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest

from driftsense.detect.base import BaseAnomalyDetector


class IsolationForestDetector(BaseAnomalyDetector):
    """Multi-feature Isolation Forest detector on residual and telemetry signals.

    Evaluates multidimensional isolation depth over:
    - cost residual e(t) = y(t) - y_hat(t)
    - relative error e(t) / (y_hat(t) + eps)
    - usage telemetry and temporal context features.
    """

    def __init__(
        self,
        name: str = "iforest",
        n_estimators: int = 100,
        contamination: float = 0.05,
        max_samples: str | float = "auto",
        threshold: float = 0.55,
        seed: int = 42,
        config: dict[str, Any] | None = None,
        version: str = "1.0.0",
    ) -> None:
        cfg = config or {}
        cfg.update(
            {
                "n_estimators": n_estimators,
                "contamination": contamination,
                "max_samples": max_samples,
                "threshold": threshold,
                "seed": seed,
            }
        )
        super().__init__(name=name, threshold=threshold, config=cfg, version=version)
        self.n_estimators = n_estimators
        self.contamination = contamination
        self.max_samples = max_samples
        self.seed = seed
        self.model_: IsolationForest | None = None

    def _prepare_features(self, df: pd.DataFrame, residual_col: str) -> pd.DataFrame:
        """Extract numeric features suitable for tree-based isolation."""
        res = df[residual_col].to_numpy(dtype=float)
        feats: dict[str, Any] = {
            "residual": res,
            "abs_residual": np.abs(res),
            "pos_residual": np.maximum(res, 0.0),
        }

        # Check for usage or temporal columns
        if "ConsumedQuantity" in df.columns:
            feats["ConsumedQuantity"] = df["ConsumedQuantity"].to_numpy(dtype=float)
        if "hour_of_day" in df.columns:
            feats["hour_of_day"] = df["hour_of_day"].to_numpy(dtype=float)
        if "day_of_week" in df.columns:
            feats["day_of_week"] = df["day_of_week"].to_numpy(dtype=float)

        return pd.DataFrame(feats).fillna(0.0)

    def fit(
        self,
        df_train: pd.DataFrame,
        residual_col: str = "residual",
        service_col: str = "ServiceName",
        time_col: str = "ChargePeriodStart",
        feature_cols: list[str] | None = None,
    ) -> IsolationForestDetector:
        self.residual_col = residual_col
        self.service_col = service_col
        self.time_col = time_col

        X_train = (
            df_train[feature_cols].fillna(0.0)
            if feature_cols is not None
            else self._prepare_features(df_train, residual_col)
        )
        self.feature_cols_ = list(X_train.columns)

        self.model_ = IsolationForest(
            n_estimators=self.n_estimators,
            contamination=self.contamination,
            max_samples=self.max_samples,
            random_state=self.seed,
            n_jobs=-1,
        )
        self.model_.fit(X_train)

        self.is_fitted = True
        self.training_timestamp_utc = datetime.datetime.now(
            datetime.timezone.utc
        ).isoformat()
        return self

    def score(self, df: pd.DataFrame) -> np.ndarray:
        if not self.is_fitted or self.model_ is None:
            raise RuntimeError(f"Detector '{self.name}' must be fitted before score().")

        if self.feature_cols_:
            # Reindex to ensure feature alignment
            X = (
                df.reindex(columns=self.feature_cols_, fill_value=0.0)
                if all(c in df.columns for c in self.feature_cols_)
                else self._prepare_features(df, self.residual_col).reindex(
                    columns=self.feature_cols_, fill_value=0.0
                )
            )
        else:
            X = self._prepare_features(df, self.residual_col)

        # score_samples returns negative anomaly score (-1.0 to 0.0), where more negative = more abnormal.
        # Invert so higher positive score = more anomalous.
        raw_scores = self.model_.score_samples(X)
        return -raw_scores

    def _get_model_state(self) -> dict[str, Any]:
        return {
            "model": self.model_,
            "feature_cols": self.feature_cols_,
            "n_estimators": self.n_estimators,
            "contamination": self.contamination,
            "max_samples": self.max_samples,
            "seed": self.seed,
        }

    def _set_model_state(self, state: dict[str, Any]) -> None:
        self.model_ = state["model"]
        self.feature_cols_ = state["feature_cols"]
        self.n_estimators = state["n_estimators"]
        self.contamination = state["contamination"]
        self.max_samples = state["max_samples"]
        self.seed = state["seed"]
