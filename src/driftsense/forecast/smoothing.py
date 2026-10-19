"""Exponential smoothing forecasting model for DriftSense."""

from __future__ import annotations

import datetime
from typing import Any

import numpy as np
import pandas as pd

from driftsense.forecast.base import BaseForecaster


class ExponentialSmoothingForecaster(BaseForecaster):
    """Exponential Smoothing forecaster per service series."""

    def __init__(
        self,
        name: str = "exponential_smoothing",
        alpha: float = 0.25,
        config: dict[str, Any] | None = None,
        version: str = "1.0.0",
    ) -> None:
        cfg = config or {}
        cfg["alpha"] = alpha
        super().__init__(name=name, config=cfg, version=version)
        self.alpha = alpha
        self.service_levels_: dict[str, float] = {}
        self.global_level_: float = 0.0

    def fit(
        self,
        df_train: pd.DataFrame,
        target_col: str = "EffectiveCost",
        time_col: str = "ChargePeriodStart",
        service_col: str = "ServiceName",
        feature_cols: list[str] | None = None,
    ) -> ExponentialSmoothingForecaster:
        self.target_col = target_col
        self.time_col = time_col
        self.service_col = service_col

        df = df_train.sort_values(by=[service_col, time_col]).copy()
        self.global_level_ = float(df[target_col].mean()) if not df.empty else 0.0
        self.service_levels_ = {}

        # Recursively calculate exponential smoothing level per service
        for svc, svc_df in df.groupby(service_col):
            vals = svc_df[target_col].to_numpy(dtype=float)
            if len(vals) == 0:
                self.service_levels_[str(svc)] = self.global_level_
                continue

            level = vals[0]
            for v in vals[1:]:
                level = self.alpha * v + (1.0 - self.alpha) * level
            self.service_levels_[str(svc)] = float(level)

        self.is_fitted = True
        self.training_timestamp_utc = datetime.datetime.now(
            datetime.timezone.utc
        ).isoformat()
        return self

    def predict(self, df: pd.DataFrame) -> np.ndarray:
        if not self.is_fitted:
            raise RuntimeError(f"Model '{self.name}' must be fitted before predict().")

        preds = np.zeros(len(df), dtype=float)
        for i, (_, row) in enumerate(df.iterrows()):
            svc = str(row.get(self.service_col, ""))
            preds[i] = self.service_levels_.get(svc, self.global_level_)

        return np.maximum(preds, 0.0)

    def _get_model_state(self) -> dict[str, Any]:
        return {
            "alpha": self.alpha,
            "service_levels": self.service_levels_,
            "global_level": self.global_level_,
        }

    def _set_model_state(self, state: dict[str, Any]) -> None:
        self.alpha = state["alpha"]
        self.service_levels_ = state["service_levels"]
        self.global_level_ = state["global_level"]
