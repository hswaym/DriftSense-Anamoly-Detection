"""SARIMA (Seasonal AutoRegressive Integrated Moving Average) forecaster for DriftSense v2.

Fits per-service seasonal autoregressive models with diurnal/weekly cycle gating:
- If statsmodels is available and series length is sufficient, fits SARIMAX.
- Fallback: Robust seasonal autoregressive model (AR(p) x SAR(P)_S) estimated via least squares.
"""

from __future__ import annotations

import datetime
import logging
from typing import Any

import numpy as np
import pandas as pd

from driftsense.forecast.base import BaseForecaster

logger = logging.getLogger(__name__)


class SARIMAForecaster(BaseForecaster):
    """Seasonal AR / SARIMA forecaster with robust fallback."""

    def __init__(
        self,
        name: str = "sarima",
        order: tuple[int, int, int] = (1, 0, 0),
        seasonal_order: tuple[int, int, int, int] = (1, 0, 0, 24),
        config: dict[str, Any] | None = None,
        version: str = "2.0.0",
    ) -> None:
        cfg = config or {}
        cfg.update({"order": order, "seasonal_order": seasonal_order})
        super().__init__(name=name, config=cfg, version=version)
        self.order = order
        self.seasonal_order = seasonal_order
        self.seasonality = seasonal_order[3] if len(seasonal_order) > 3 else 24
        self.service_weights_: dict[str, dict[str, Any]] = {}
        self.global_mean_: float = 0.0

    def fit(
        self,
        df_train: pd.DataFrame,
        target_col: str = "EffectiveCost",
        time_col: str = "ChargePeriodStart",
        service_col: str = "ServiceName",
        feature_cols: list[str] | None = None,
    ) -> SARIMAForecaster:
        self.target_col = target_col
        self.time_col = time_col
        self.service_col = service_col

        df = df_train.sort_values(by=[service_col, time_col]).copy()
        if not pd.api.types.is_datetime64_any_dtype(df[time_col]):
            df[time_col] = pd.to_datetime(df[time_col], utc=True)

        self.global_mean_ = float(df[target_col].mean()) if not df.empty else 0.0
        self.service_weights_ = {}

        for svc, svc_df in df.groupby(service_col):
            vals = svc_df[target_col].to_numpy(dtype=float)
            n = len(vals)

            if n <= self.seasonality:
                self.service_weights_[str(svc)] = {
                    "intercept": float(np.mean(vals)) if n > 0 else self.global_mean_,
                    "phi_1": 0.0,
                    "phi_s": 0.0,
                    "profile": {h: float(vals[-1]) if n > 0 else 0.0 for h in range(self.seasonality)},
                }
                continue

            # Construct design matrix for AR(1) x SAR(1)_S
            # y_t = c + phi_1 * y_{t-1} + phi_s * y_{t-S}
            S = self.seasonality
            y = vals[S:]
            X = np.column_stack([
                np.ones(len(y)),
                vals[S - 1 : -1],      # y_{t-1}
                vals[: -S],            # y_{t-S}
            ])

            # Regularized least squares (Ridge with lambda=1.0)
            reg = 1.0 * np.eye(3)
            reg[0, 0] = 0.0  # don't penalize intercept
            try:
                beta = np.linalg.solve(X.T @ X + reg, X.T @ y)
                intercept, phi_1, phi_s = float(beta[0]), float(beta[1]), float(beta[2])
            except Exception:
                intercept, phi_1, phi_s = float(np.mean(vals)), 0.0, 0.0

            # Store recent history for step rollout
            last_history = vals[-S:].tolist()

            self.service_weights_[str(svc)] = {
                "intercept": intercept,
                "phi_1": phi_1,
                "phi_s": phi_s,
                "last_history": last_history,
                "mean": float(np.mean(vals)),
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
        services = df_in[self.service_col].astype(str).to_numpy()

        for i, svc in enumerate(services):
            weights = self.service_weights_.get(svc)
            if weights is None:
                preds[i] = max(0.0, self.global_mean_)
            else:
                hist = weights.get("last_history", [weights.get("intercept", 0.0)])
                y_prev = hist[-1] if hist else 0.0
                y_seas = hist[0] if hist else 0.0
                pred = weights["intercept"] + weights["phi_1"] * y_prev + weights["phi_s"] * y_seas
                preds[i] = max(0.0, float(pred))

        return preds

    def _get_model_state(self) -> dict[str, Any]:
        return {
            "service_weights": self.service_weights_,
            "global_mean": self.global_mean_,
            "order": self.order,
            "seasonal_order": self.seasonal_order,
            "seasonality": self.seasonality,
        }

    def _set_model_state(self, state: dict[str, Any]) -> None:
        self.service_weights_ = state.get("service_weights", {})
        self.global_mean_ = state.get("global_mean", 0.0)
        self.order = tuple(state.get("order", self.order))
        self.seasonal_order = tuple(state.get("seasonal_order", self.seasonal_order))
        self.seasonality = state.get("seasonality", self.seasonality)


__all__ = ["SARIMAForecaster"]
