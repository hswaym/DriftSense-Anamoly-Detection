"""XGBoost regression forecasting model for DriftSense."""

from __future__ import annotations

import datetime
import logging
from typing import Any

import numpy as np
import pandas as pd
import xgboost as xgb

from driftsense.forecast.base import BaseForecaster

logger = logging.getLogger(__name__)


class XGBoostForecaster(BaseForecaster):
    """Gradient boosted tree forecaster using engineered lag and telemetry features."""

    def __init__(
        self,
        name: str = "xgboost",
        n_estimators: int = 100,
        max_depth: int = 4,
        learning_rate: float = 0.05,
        subsample: float = 0.8,
        colsample_bytree: float = 0.8,
        device: str = "cpu",
        seed: int = 42,
        log_transform: bool = True,
        config: dict[str, Any] | None = None,
        version: str = "1.0.0",
    ) -> None:
        cfg = config or {}
        cfg.update(
            {
                "n_estimators": n_estimators,
                "max_depth": max_depth,
                "learning_rate": learning_rate,
                "subsample": subsample,
                "colsample_bytree": colsample_bytree,
                "device": device,
                "seed": seed,
                "log_transform": log_transform,
            }
        )
        super().__init__(name=name, config=cfg, version=version)
        self.n_estimators = n_estimators
        self.max_depth = max_depth
        self.learning_rate = learning_rate
        self.subsample = subsample
        self.colsample_bytree = colsample_bytree
        self.device = device
        self.seed = seed
        self.log_transform = log_transform

        self.model_: xgb.XGBRegressor | None = None
        self.feature_cols_: list[str] = []
        self.feature_importances_: dict[str, float] = {}

    @property
    def feature_names_(self) -> list[str]:
        """Convenience alias for feature_cols_."""
        return self.feature_cols_

    def fit(
        self,
        df_train: pd.DataFrame,
        target_col: str = "EffectiveCost",
        time_col: str = "ChargePeriodStart",
        service_col: str = "ServiceName",
        feature_cols: list[str] | None = None,
    ) -> XGBoostForecaster:
        self.target_col = target_col
        self.time_col = time_col
        self.service_col = service_col

        # Determine feature columns
        if feature_cols is not None:
            self.feature_cols_ = feature_cols
        else:
            exclude_cols = {
                target_col,
                f"{target_col}Raw",
                service_col,
                time_col,
                "ChargePeriodEnd",
                "Id",
                "Tags",
            }
            self.feature_cols_ = [
                c
                for c in df_train.columns
                if c not in exclude_cols and pd.api.types.is_numeric_dtype(df_train[c])
            ]

        X_train = df_train[self.feature_cols_]
        y_train = df_train[target_col].to_numpy(dtype=float)

        if self.log_transform:
            y_train = np.log1p(np.maximum(y_train, 0.0))

        # Explicit device and seed configuration
        self.model_ = xgb.XGBRegressor(
            n_estimators=self.n_estimators,
            max_depth=self.max_depth,
            learning_rate=self.learning_rate,
            subsample=self.subsample,
            colsample_bytree=self.colsample_bytree,
            random_state=self.seed,
            device=self.device,
            tree_method="hist",
            verbosity=0,
        )

        self.model_.fit(X_train, y_train)

        # Record feature importances
        importances = self.model_.feature_importances_
        self.feature_importances_ = {
            col: float(imp) for col, imp in zip(self.feature_cols_, importances)
        }

        self.is_fitted = True
        self.training_timestamp_utc = datetime.datetime.now(
            datetime.timezone.utc
        ).isoformat()
        logger.info(
            "Fitted XGBoostForecaster on %d rows with %d features.",
            len(df_train),
            len(self.feature_cols_),
        )
        return self

    def predict(self, df: pd.DataFrame) -> np.ndarray:
        if not self.is_fitted or self.model_ is None:
            raise RuntimeError(f"Model '{self.name}' must be fitted before predict().")

        # Fill missing features with 0 if any new columns are absent
        X = df.reindex(columns=self.feature_cols_, fill_value=0.0)
        preds = self.model_.predict(X)

        if self.log_transform:
            preds = np.expm1(preds)

        return np.maximum(preds, 0.0)

    def _get_model_state(self) -> dict[str, Any]:
        return {
            "model": self.model_,
            "feature_cols": self.feature_cols_,
            "feature_importances": self.feature_importances_,
            "log_transform": self.log_transform,
            "device": self.device,
            "seed": self.seed,
        }

    def _set_model_state(self, state: dict[str, Any]) -> None:
        self.model_ = state["model"]
        self.feature_cols_ = state["feature_cols"]
        self.feature_importances_ = state["feature_importances"]
        self.log_transform = state["log_transform"]
        self.device = state["device"]
        self.seed = state["seed"]
