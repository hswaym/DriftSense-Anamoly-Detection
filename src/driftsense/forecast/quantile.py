"""Quantile regression forecaster for probabilistic intervals in DriftSense v2.

Fits separate gradient boosted tree models for specified quantile levels tau (e.g., 0.10, 0.50, 0.90)
using quantile regression objective (reg:quantileerror in XGBoost or pinball loss).
"""

from __future__ import annotations

import datetime
import logging
from typing import Any

import numpy as np
import pandas as pd
import xgboost as xgb

from driftsense.forecast.base import BaseForecaster

logger = logging.getLogger(__name__)


class QuantileForecaster(BaseForecaster):
    """Multi-quantile regression forecaster providing parametric prediction intervals."""

    def __init__(
        self,
        name: str = "quantile_forecaster",
        quantiles: tuple[float, ...] = (0.10, 0.50, 0.90),
        n_estimators: int = 80,
        max_depth: int = 4,
        learning_rate: float = 0.05,
        device: str = "cpu",
        seed: int = 42,
        config: dict[str, Any] | None = None,
        version: str = "2.0.0",
    ) -> None:
        cfg = config or {}
        cfg.update(
            {
                "quantiles": list(quantiles),
                "n_estimators": n_estimators,
                "max_depth": max_depth,
                "learning_rate": learning_rate,
                "device": device,
                "seed": seed,
            }
        )
        super().__init__(name=name, config=cfg, version=version)
        self.quantiles = tuple(sorted(quantiles))
        self.n_estimators = n_estimators
        self.max_depth = max_depth
        self.learning_rate = learning_rate
        self.device = device
        self.seed = seed

        self.models_: dict[float, xgb.XGBRegressor] = {}
        self.feature_cols_: list[str] = []

    def fit(
        self,
        df_train: pd.DataFrame,
        target_col: str = "EffectiveCost",
        time_col: str = "ChargePeriodStart",
        service_col: str = "ServiceName",
        feature_cols: list[str] | None = None,
    ) -> QuantileForecaster:
        self.target_col = target_col
        self.time_col = time_col
        self.service_col = service_col

        df = df_train.copy()
        if feature_cols is not None:
            self.feature_cols_ = [c for c in feature_cols if c in df.columns]
        else:
            exclude = {
                target_col,
                service_col,
                time_col,
                "ChargePeriodEnd",
                "Id",
                "Tags",
                "ProviderName",
                "SubAccountId",
                "BillingAccountId",
                "RegionId",
                "BilledCost",
                "ListCost",
                "ContractedCost",
            }
            self.feature_cols_ = [
                c for c in df.columns if c not in exclude and pd.api.types.is_numeric_dtype(df[c])
            ]

        X_train = df[self.feature_cols_].fillna(0.0)
        y_train = np.maximum(0.0, df[target_col].to_numpy(dtype=float))

        self.models_ = {}
        for q in self.quantiles:
            reg = xgb.XGBRegressor(
                objective="reg:quantileerror",
                quantile_alpha=q,
                n_estimators=self.n_estimators,
                max_depth=self.max_depth,
                learning_rate=self.learning_rate,
                random_state=self.seed,
                n_jobs=-1,
            )
            reg.fit(X_train, y_train)
            self.models_[q] = reg

        self.is_fitted = True
        self.training_timestamp_utc = datetime.datetime.now(datetime.timezone.utc).isoformat()
        return self

    def predict(self, df: pd.DataFrame) -> np.ndarray:
        """Predict median (q=0.50) point forecast."""
        if not self.is_fitted:
            raise RuntimeError("Model must be fitted before predict() is called.")

        median_q = 0.50 if 0.50 in self.models_ else self.quantiles[len(self.quantiles) // 2]
        X = df.reindex(columns=self.feature_cols_).fillna(0.0)
        return np.maximum(0.0, self.models_[median_q].predict(X))

    def predict_quantiles(self, df: pd.DataFrame) -> dict[float, np.ndarray]:
        """Predict values for all fitted quantile levels."""
        if not self.is_fitted:
            raise RuntimeError("Model must be fitted before predict_quantiles() is called.")

        X = df.reindex(columns=self.feature_cols_).fillna(0.0)
        preds = {}
        for q, model in self.models_.items():
            preds[q] = np.maximum(0.0, model.predict(X))
        return preds

    def predict_interval(
        self,
        df: pd.DataFrame,
        lower_q: float = 0.10,
        upper_q: float = 0.90,
    ) -> tuple[np.ndarray, np.ndarray]:
        """Predict lower and upper bounds for requested quantiles."""
        q_preds = self.predict_quantiles(df)
        if lower_q not in q_preds or upper_q not in q_preds:
            raise ValueError(
                f"Requested quantiles ({lower_q}, {upper_q}) not in fitted quantiles: {list(self.models_.keys())}"
            )
        lower = np.minimum(q_preds[lower_q], q_preds[upper_q])
        upper = np.maximum(q_preds[lower_q], q_preds[upper_q])
        return lower, upper

    def _get_model_state(self) -> dict[str, Any]:
        return {
            "models": self.models_,
            "quantiles": self.quantiles,
            "feature_cols": self.feature_cols_,
        }

    def _set_model_state(self, state: dict[str, Any]) -> None:
        self.models_ = state.get("models", {})
        self.quantiles = tuple(state.get("quantiles", self.quantiles))
        self.feature_cols_ = state.get("feature_cols", [])


__all__ = ["QuantileForecaster"]
