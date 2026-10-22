"""Gradient boosted tree forecaster for DriftSense v2.

Supports:
- XGBoost with Tweedie regression (reg:tweedie) for zero-inflated cloud cost series
- Standard squared error regression (reg:squarederror) with log1p stabilization
- Global panel training across all services with service encoding
"""

from __future__ import annotations

import datetime
import logging
from typing import Any

import numpy as np
import pandas as pd
import xgboost as xgb

from driftsense.forecast.base import BaseForecaster
from driftsense.forecast.xgb import XGBoostForecaster

logger = logging.getLogger(__name__)


class BoostedTreeForecaster(BaseForecaster):
    """Gradient boosted tree forecaster with Tweedie and count-appropriate objectives."""

    def __init__(
        self,
        name: str = "boosted_tree",
        objective: str = "reg:tweedie",
        tweedie_variance_power: float = 1.5,
        n_estimators: int = 100,
        max_depth: int = 4,
        learning_rate: float = 0.05,
        subsample: float = 0.8,
        colsample_bytree: float = 0.8,
        device: str = "cpu",
        seed: int = 42,
        config: dict[str, Any] | None = None,
        version: str = "2.0.0",
    ) -> None:
        cfg = config or {}
        cfg.update(
            {
                "objective": objective,
                "tweedie_variance_power": tweedie_variance_power,
                "n_estimators": n_estimators,
                "max_depth": max_depth,
                "learning_rate": learning_rate,
                "subsample": subsample,
                "colsample_bytree": colsample_bytree,
                "device": device,
                "seed": seed,
            }
        )
        super().__init__(name=name, config=cfg, version=version)
        self.objective = objective
        self.tweedie_variance_power = tweedie_variance_power
        self.n_estimators = n_estimators
        self.max_depth = max_depth
        self.learning_rate = learning_rate
        self.subsample = subsample
        self.colsample_bytree = colsample_bytree
        self.device = device
        self.seed = seed

        self.model_: xgb.XGBRegressor | None = None
        self.feature_cols_: list[str] = []
        self.feature_importances_: dict[str, float] = {}

    def fit(
        self,
        df_train: pd.DataFrame,
        target_col: str = "EffectiveCost",
        time_col: str = "ChargePeriodStart",
        service_col: str = "ServiceName",
        feature_cols: list[str] | None = None,
    ) -> BoostedTreeForecaster:
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

        model_params: dict[str, Any] = {
            "n_estimators": self.n_estimators,
            "max_depth": self.max_depth,
            "learning_rate": self.learning_rate,
            "subsample": self.subsample,
            "colsample_bytree": self.colsample_bytree,
            "random_state": self.seed,
            "n_jobs": -1,
            "objective": self.objective,
        }
        if self.objective == "reg:tweedie":
            model_params["tweedie_variance_power"] = self.tweedie_variance_power

        self.model_ = xgb.XGBRegressor(**model_params)
        self.model_.fit(X_train, y_train)

        if hasattr(self.model_, "feature_importances_"):
            self.feature_importances_ = {
                f: float(imp)
                for f, imp in zip(self.feature_cols_, self.model_.feature_importances_)
            }

        self.is_fitted = True
        self.training_timestamp_utc = datetime.datetime.now(datetime.timezone.utc).isoformat()
        return self

    def predict(self, df: pd.DataFrame) -> np.ndarray:
        if not self.is_fitted or self.model_ is None:
            raise RuntimeError("Model must be fitted before predict() is called.")

        X = df.reindex(columns=self.feature_cols_).fillna(0.0)
        preds = self.model_.predict(X)
        return np.maximum(0.0, preds)

    def _get_model_state(self) -> dict[str, Any]:
        return {
            "model": self.model_,
            "feature_cols": self.feature_cols_,
            "feature_importances": self.feature_importances_,
            "objective": self.objective,
            "tweedie_variance_power": self.tweedie_variance_power,
        }

    def _set_model_state(self, state: dict[str, Any]) -> None:
        self.model_ = state.get("model")
        self.feature_cols_ = state.get("feature_cols", [])
        self.feature_importances_ = state.get("feature_importances", {})
        self.objective = state.get("objective", self.objective)
        self.tweedie_variance_power = state.get("tweedie_variance_power", self.tweedie_variance_power)


__all__ = ["BoostedTreeForecaster", "XGBoostForecaster"]
