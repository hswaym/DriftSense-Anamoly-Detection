"""Z-Score dynamic residual sigma anomaly detector for DriftSense."""

from __future__ import annotations

import datetime
from typing import Any

import numpy as np
import pandas as pd

from driftsense.detect.base import BaseAnomalyDetector


class ZScoreDetector(BaseAnomalyDetector):
    """Statistical Z-Score detector evaluated on forecast residuals: e(t) = y(t) - y_hat(t).

    Calculates mean and standard deviation per service series on training residuals.
    Score = (e(t) - mu_res) / (sigma_res + eps).
    """

    def __init__(
        self,
        name: str = "zscore",
        threshold: float = 3.0,
        per_service: bool = True,
        one_sided: bool = True,
        eps: float = 1e-4,
        config: dict[str, Any] | None = None,
        version: str = "1.0.0",
    ) -> None:
        cfg = config or {}
        cfg.update(
            {
                "threshold": threshold,
                "per_service": per_service,
                "one_sided": one_sided,
                "eps": eps,
            }
        )
        super().__init__(name=name, threshold=threshold, config=cfg, version=version)
        self.per_service = per_service
        self.one_sided = one_sided
        self.eps = eps
        self.global_mean_: float = 0.0
        self.global_std_: float = 1.0
        self.service_stats_: dict[str, dict[str, float]] = {}

    def fit(
        self,
        df_train: pd.DataFrame,
        residual_col: str = "residual",
        service_col: str = "ServiceName",
        time_col: str = "ChargePeriodStart",
        feature_cols: list[str] | None = None,
    ) -> ZScoreDetector:
        self.residual_col = residual_col
        self.service_col = service_col
        self.time_col = time_col

        residuals = df_train[residual_col].to_numpy(dtype=float)
        self.global_mean_ = float(np.mean(residuals)) if len(residuals) > 0 else 0.0
        self.global_std_ = float(np.std(residuals)) if len(residuals) > 0 else 1.0
        self.global_std_ = max(self.global_std_, self.eps)

        self.service_stats_ = {}
        if self.per_service and service_col in df_train.columns:
            for svc, svc_df in df_train.groupby(service_col):
                svc_res = svc_df[residual_col].to_numpy(dtype=float)
                s_mean = (
                    float(np.mean(svc_res)) if len(svc_res) > 0 else self.global_mean_
                )
                s_std = float(np.std(svc_res)) if len(svc_res) > 0 else self.global_std_
                if s_std < self.eps:
                    s_std = self.global_std_
                self.service_stats_[str(svc)] = {"mean": s_mean, "std": s_std}

        self.is_fitted = True
        self.training_timestamp_utc = datetime.datetime.now(
            datetime.timezone.utc
        ).isoformat()
        return self

    def score(self, df: pd.DataFrame) -> np.ndarray:
        if not self.is_fitted:
            raise RuntimeError(f"Detector '{self.name}' must be fitted before score().")

        res_vals = df[self.residual_col].to_numpy(dtype=float)
        scores = np.zeros(len(df), dtype=float)

        if self.per_service and self.service_col in df.columns:
            services = df[self.service_col].astype(str).to_numpy()
            for i in range(len(df)):
                svc = services[i]
                stats = self.service_stats_.get(
                    svc, {"mean": self.global_mean_, "std": self.global_std_}
                )
                z = (res_vals[i] - stats["mean"]) / stats["std"]
                scores[i] = z if self.one_sided else abs(z)
        else:
            z = (res_vals - self.global_mean_) / self.global_std_
            scores = z if self.one_sided else np.abs(z)

        return scores

    def _get_model_state(self) -> dict[str, Any]:
        return {
            "per_service": self.per_service,
            "one_sided": self.one_sided,
            "eps": self.eps,
            "global_mean": self.global_mean_,
            "global_std": self.global_std_,
            "service_stats": self.service_stats_,
        }

    def _set_model_state(self, state: dict[str, Any]) -> None:
        self.per_service = state["per_service"]
        self.one_sided = state["one_sided"]
        self.eps = state["eps"]
        self.global_mean_ = state["global_mean"]
        self.global_std_ = state["global_std"]
        self.service_stats_ = state["service_stats"]
