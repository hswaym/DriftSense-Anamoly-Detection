"""Dynamic rolling threshold anomaly detector for DriftSense."""

from __future__ import annotations

import datetime
from typing import Any

import numpy as np
import pandas as pd

from driftsense.detect.base import BaseAnomalyDetector


class RollingThresholdDetector(BaseAnomalyDetector):
    """Dynamic rolling control-limit anomaly detector.

    Maintains a trailing window W (default 24h) of historical residuals per service:
    score(t) = (e(t) - mu_rolling(t)) / (sigma_rolling(t) + eps).
    Points exceeding threshold (default 3.0) are flagged as anomalies.
    """

    def __init__(
        self,
        name: str = "rolling_threshold",
        window: int = 24,
        threshold: float = 3.0,
        eps: float = 1e-4,
        config: dict[str, Any] | None = None,
        version: str = "1.0.0",
    ) -> None:
        cfg = config or {}
        cfg.update({"window": window, "threshold": threshold, "eps": eps})
        super().__init__(name=name, threshold=threshold, config=cfg, version=version)
        self.window = window
        self.eps = eps
        self.global_std_: float = 1.0
        self.service_tail_residuals_: dict[str, list[float]] = {}

    def fit(
        self,
        df_train: pd.DataFrame,
        residual_col: str = "residual",
        service_col: str = "ServiceName",
        time_col: str = "ChargePeriodStart",
        feature_cols: list[str] | None = None,
    ) -> RollingThresholdDetector:
        self.residual_col = residual_col
        self.service_col = service_col
        self.time_col = time_col

        residuals = df_train[residual_col].to_numpy(dtype=float)
        self.global_std_ = float(np.std(residuals)) if len(residuals) > 0 else 1.0
        self.global_std_ = max(self.global_std_, self.eps)

        df_sorted = df_train.sort_values(by=[service_col, time_col]).copy()
        self.service_tail_residuals_ = {}

        if service_col in df_sorted.columns:
            for svc, svc_df in df_sorted.groupby(service_col):
                tail = svc_df[residual_col].tail(self.window).tolist()
                self.service_tail_residuals_[str(svc)] = [float(x) for x in tail]

        self.is_fitted = True
        self.training_timestamp_utc = datetime.datetime.now(
            datetime.timezone.utc
        ).isoformat()
        return self

    def score(self, df: pd.DataFrame) -> np.ndarray:
        if not self.is_fitted:
            raise RuntimeError(f"Detector '{self.name}' must be fitted before score().")

        df_sorted = df.copy()
        is_df_has_time = self.time_col in df_sorted.columns
        if is_df_has_time and not pd.api.types.is_datetime64_any_dtype(
            df_sorted[self.time_col]
        ):
            df_sorted[self.time_col] = pd.to_datetime(
                df_sorted[self.time_col], utc=True
            )

        scores = np.zeros(len(df), dtype=float)
        # Process service by service to preserve chronological rolling context
        if self.service_col in df_sorted.columns:
            for svc, svc_df in df_sorted.groupby(self.service_col):
                indices = svc_df.index
                tail = list(self.service_tail_residuals_.get(str(svc), []))
                res_vals = svc_df[self.residual_col].to_numpy(dtype=float)

                for k, idx in enumerate(indices):
                    val = res_vals[k]
                    if len(tail) > 0:
                        roll_mean = float(np.mean(tail))
                        roll_std = float(np.std(tail))
                        if roll_std < self.eps:
                            roll_std = self.global_std_
                    else:
                        roll_mean = 0.0
                        roll_std = self.global_std_

                    scores[idx] = (val - roll_mean) / roll_std
                    tail.append(val)
                    if len(tail) > self.window:
                        tail.pop(0)
        else:
            res_vals = df[self.residual_col].to_numpy(dtype=float)
            scores = res_vals / self.global_std_

        return scores

    def _get_model_state(self) -> dict[str, Any]:
        return {
            "window": self.window,
            "eps": self.eps,
            "global_std": self.global_std_,
            "service_tail_residuals": self.service_tail_residuals_,
        }

    def _set_model_state(self, state: dict[str, Any]) -> None:
        self.window = state["window"]
        self.eps = state["eps"]
        self.global_std_ = state["global_std"]
        self.service_tail_residuals_ = state["service_tail_residuals"]
