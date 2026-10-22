"""ETS (Error, Trend, Seasonal) exponential smoothing forecasters for DriftSense v2.

Implements:
- ETSForecaster: Holt-Winters style exponential smoothing with level and seasonal factors.
- ExponentialSmoothingForecaster: Simple exponential smoothing baseline per service.
"""

from __future__ import annotations

import datetime
from typing import Any

import numpy as np
import pandas as pd

from driftsense.forecast.base import BaseForecaster
from driftsense.forecast.smoothing import ExponentialSmoothingForecaster


class ETSForecaster(BaseForecaster):
    """Holt-Winters style additive/multiplicative ETS forecaster."""

    def __init__(
        self,
        name: str = "ets",
        alpha: float = 0.2,
        beta: float = 0.05,
        gamma: float = 0.1,
        seasonality: int = 24,
        config: dict[str, Any] | None = None,
        version: str = "2.0.0",
    ) -> None:
        cfg = config or {}
        cfg.update({"alpha": alpha, "beta": beta, "gamma": gamma, "seasonality": seasonality})
        super().__init__(name=name, config=cfg, version=version)
        self.alpha = alpha
        self.beta = beta
        self.gamma = gamma
        self.seasonality = seasonality
        self.service_models_: dict[str, dict[str, Any]] = {}
        self.global_mean_: float = 0.0

    def fit(
        self,
        df_train: pd.DataFrame,
        target_col: str = "EffectiveCost",
        time_col: str = "ChargePeriodStart",
        service_col: str = "ServiceName",
        feature_cols: list[str] | None = None,
    ) -> ETSForecaster:
        self.target_col = target_col
        self.time_col = time_col
        self.service_col = service_col

        df = df_train.sort_values(by=[service_col, time_col]).copy()
        if not pd.api.types.is_datetime64_any_dtype(df[time_col]):
            df[time_col] = pd.to_datetime(df[time_col], utc=True)

        self.global_mean_ = float(df[target_col].mean()) if not df.empty else 0.0
        self.service_models_ = {}

        for svc, svc_df in df.groupby(service_col):
            vals = svc_df[target_col].to_numpy(dtype=float)
            n = len(vals)
            if n < self.seasonality:
                # Fall back to simple mean/level if insufficient length
                self.service_models_[str(svc)] = {
                    "level": float(np.mean(vals)) if n > 0 else self.global_mean_,
                    "trend": 0.0,
                    "seasonals": {h: 0.0 for h in range(self.seasonality)},
                }
                continue

            # Initial level and trend from first season
            level = float(np.mean(vals[:self.seasonality]))
            trend = 0.0
            seasonals: dict[int, float] = {}

            # Initial seasonal indices
            hours = svc_df[time_col].dt.hour.to_numpy()
            for h in range(self.seasonality):
                h_vals = vals[hours == h]
                seasonals[h] = float(np.mean(h_vals) - level) if len(h_vals) > 0 else 0.0

            # Single-pass updating
            for i in range(self.seasonality, n):
                val = vals[i]
                h = int(hours[i] % self.seasonality)
                prev_level = level
                prev_trend = trend
                prev_seas = seasonals[h]

                # Update level
                level = self.alpha * (val - prev_seas) + (1.0 - self.alpha) * (prev_level + prev_trend)
                # Update trend
                trend = self.beta * (level - prev_level) + (1.0 - self.beta) * prev_trend
                # Update seasonal
                seasonals[h] = self.gamma * (val - level) + (1.0 - self.gamma) * prev_seas

            self.service_models_[str(svc)] = {
                "level": level,
                "trend": trend,
                "seasonals": seasonals,
            }

        self.is_fitted = True
        self.training_timestamp_utc = datetime.datetime.now(datetime.timezone.utc).isoformat()
        return self

    def predict(self, df: pd.DataFrame) -> np.ndarray:
        if not self.is_fitted:
            raise RuntimeError("Model must be fitted before predict() is called.")

        df_in = df.copy()
        if not pd.api.types.is_datetime64_any_dtype(df_in[self.time_col]):
            df_in[self.time_col] = pd.to_datetime(df_in[self.time_col], utc=True)

        preds = np.zeros(len(df_in), dtype=float)
        hours = df_in[self.time_col].dt.hour.to_numpy()
        services = df_in[self.service_col].astype(str).to_numpy()

        for i, (svc, h) in enumerate(zip(services, hours)):
            model = self.service_models_.get(svc)
            if model is None:
                preds[i] = max(0.0, self.global_mean_)
            else:
                level = model["level"]
                trend = model["trend"]
                seas = model["seasonals"].get(int(h % self.seasonality), 0.0)
                preds[i] = max(0.0, level + trend + seas)

        return preds

    def _get_model_state(self) -> dict[str, Any]:
        return {
            "service_models": self.service_models_,
            "global_mean": self.global_mean_,
            "alpha": self.alpha,
            "beta": self.beta,
            "gamma": self.gamma,
            "seasonality": self.seasonality,
        }

    def _set_model_state(self, state: dict[str, Any]) -> None:
        self.service_models_ = state.get("service_models", {})
        self.global_mean_ = state.get("global_mean", 0.0)
        self.alpha = state.get("alpha", self.alpha)
        self.beta = state.get("beta", self.beta)
        self.gamma = state.get("gamma", self.gamma)
        self.seasonality = state.get("seasonality", self.seasonality)


__all__ = ["ETSForecaster", "ExponentialSmoothingForecaster"]
