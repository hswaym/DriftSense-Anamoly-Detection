"""Baseline naive and moving-average forecasting models for DriftSense."""

from __future__ import annotations

import datetime
from typing import Any

import numpy as np
import pandas as pd

from driftsense.forecast.base import BaseForecaster


class SeasonalNaiveForecaster(BaseForecaster):
    """Seasonal-Naive baseline forecaster: Y(t) = Y(t - S).

    Default seasonality S=24 hours (daily diurnal cycle).
    """

    def __init__(
        self,
        name: str = "seasonal_naive",
        seasonality: int = 24,
        config: dict[str, Any] | None = None,
        version: str = "1.0.0",
    ) -> None:
        cfg = config or {}
        cfg["seasonality"] = seasonality
        super().__init__(name=name, config=cfg, version=version)
        self.seasonality = seasonality
        self.service_profiles_: dict[str, dict[int, float]] = {}
        self.service_means_: dict[str, float] = {}
        self.global_mean_: float = 0.0

    def fit(
        self,
        df_train: pd.DataFrame,
        target_col: str = "EffectiveCost",
        time_col: str = "ChargePeriodStart",
        service_col: str = "ServiceName",
        feature_cols: list[str] | None = None,
    ) -> SeasonalNaiveForecaster:
        self.target_col = target_col
        self.time_col = time_col
        self.service_col = service_col

        df = df_train.copy()
        if not pd.api.types.is_datetime64_any_dtype(df[time_col]):
            df[time_col] = pd.to_datetime(df[time_col], utc=True)

        self.global_mean_ = float(df[target_col].mean()) if not df.empty else 0.0
        self.service_profiles_ = {}
        self.service_means_ = {}

        # Profile seasonality (e.g. hour-of-day profile if seasonality=24)
        for svc, svc_df in df.groupby(service_col):
            self.service_means_[str(svc)] = float(svc_df[target_col].mean())
            hour_mod = svc_df[time_col].dt.hour % self.seasonality
            profile = svc_df.groupby(hour_mod)[target_col].mean().to_dict()
            self.service_profiles_[str(svc)] = {
                int(k): float(v) for k, v in profile.items()
            }

        self.is_fitted = True
        self.training_timestamp_utc = datetime.datetime.now(
            datetime.timezone.utc
        ).isoformat()
        return self

    def predict(self, df: pd.DataFrame) -> np.ndarray:
        if not self.is_fitted:
            raise RuntimeError(f"Model '{self.name}' must be fitted before predict().")

        df_in = df.copy()
        if not pd.api.types.is_datetime64_any_dtype(df_in[self.time_col]):
            df_in[self.time_col] = pd.to_datetime(df_in[self.time_col], utc=True)

        preds = np.zeros(len(df_in), dtype=float)
        for i, (_, row) in enumerate(df_in.iterrows()):
            svc = str(row.get(self.service_col, ""))
            t = row[self.time_col]
            s_idx = int(t.hour % self.seasonality)

            svc_prof = self.service_profiles_.get(svc, {})
            if s_idx in svc_prof:
                preds[i] = svc_prof[s_idx]
            elif svc in self.service_means_:
                preds[i] = self.service_means_[svc]
            else:
                preds[i] = self.global_mean_

        return np.maximum(preds, 0.0)

    def _get_model_state(self) -> dict[str, Any]:
        return {
            "seasonality": self.seasonality,
            "service_profiles": self.service_profiles_,
            "service_means": self.service_means_,
            "global_mean": self.global_mean_,
        }

    def _set_model_state(self, state: dict[str, Any]) -> None:
        self.seasonality = state["seasonality"]
        self.service_profiles_ = state["service_profiles"]
        self.service_means_ = state["service_means"]
        self.global_mean_ = state["global_mean"]


class MovingAverageForecaster(BaseForecaster):
    """Historical moving average baseline: Y(t) = (1/W) * sum(Y(t-i))."""

    def __init__(
        self,
        name: str = "moving_average",
        window: int = 24,
        config: dict[str, Any] | None = None,
        version: str = "1.0.0",
    ) -> None:
        cfg = config or {}
        cfg["window"] = window
        super().__init__(name=name, config=cfg, version=version)
        self.window = window
        self.service_means_: dict[str, float] = {}
        self.global_mean_: float = 0.0

    def fit(
        self,
        df_train: pd.DataFrame,
        target_col: str = "EffectiveCost",
        time_col: str = "ChargePeriodStart",
        service_col: str = "ServiceName",
        feature_cols: list[str] | None = None,
    ) -> MovingAverageForecaster:
        self.target_col = target_col
        self.time_col = time_col
        self.service_col = service_col

        df = df_train.sort_values(by=[service_col, time_col]).copy()
        self.global_mean_ = float(df[target_col].mean()) if not df.empty else 0.0
        self.service_means_ = {}

        # Trailing window mean per service from training tail
        for svc, svc_df in df.groupby(service_col):
            tail_vals = svc_df[target_col].tail(self.window)
            self.service_means_[str(svc)] = (
                float(tail_vals.mean()) if not tail_vals.empty else self.global_mean_
            )

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
            preds[i] = self.service_means_.get(svc, self.global_mean_)

        return np.maximum(preds, 0.0)

    def _get_model_state(self) -> dict[str, Any]:
        return {
            "window": self.window,
            "service_means": self.service_means_,
            "global_mean": self.global_mean_,
        }

    def _set_model_state(self, state: dict[str, Any]) -> None:
        self.window = state["window"]
        self.service_means_ = state["service_means"]
        self.global_mean_ = state["global_mean"]
