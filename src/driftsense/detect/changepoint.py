"""Change-point and sustained level-shift detector for DriftSense v2.

Detects structural shifts in cloud spend (e.g., new baseline architectures,
permanent capacity changes) by comparing adjacent historical windows:
W1 = [t - 2*window, t - window - 1] vs W2 = [t - window, t]
via two-sample Welch t-statistic.
"""

from __future__ import annotations

import datetime
from typing import Any

import numpy as np
import pandas as pd

from driftsense.detect.base import BaseAnomalyDetector


class LevelShiftDetector(BaseAnomalyDetector):
    """Detects structural level shifts and change-points using rolling two-sample test."""

    def __init__(
        self,
        name: str = "level_shift",
        window: int = 12,
        threshold: float = 3.5,
        config: dict[str, Any] | None = None,
        version: str = "2.0.0",
    ) -> None:
        cfg = config or {}
        cfg.update({"window": window, "threshold": threshold})
        super().__init__(name=name, threshold=threshold, config=cfg, version=version)
        self.window = window
        self.eps = 1e-6

    def fit(
        self,
        df_train: pd.DataFrame,
        residual_col: str = "residual",
        service_col: str = "ServiceName",
        time_col: str = "ChargePeriodStart",
        feature_cols: list[str] | None = None,
    ) -> LevelShiftDetector:
        self.residual_col = residual_col
        self.service_col = service_col
        self.time_col = time_col
        self.is_fitted = True
        self.training_timestamp_utc = datetime.datetime.now(datetime.timezone.utc).isoformat()
        return self

    def score(self, df: pd.DataFrame) -> np.ndarray:
        if not self.is_fitted:
            raise RuntimeError("Detector must be fitted before score() is called.")

        df_sorted = df.sort_values(by=[self.service_col, self.time_col]).copy()
        df_sorted["_orig_idx"] = np.arange(len(df_sorted))

        w = self.window
        t_stats = np.zeros(len(df_sorted), dtype=float)

        for svc, group in df_sorted.groupby(self.service_col):
            vals = group[self.residual_col].to_numpy(dtype=float)
            n = len(vals)
            if n < 2 * w:
                continue

            grp_indices = group["_orig_idx"].to_numpy()

            # For each step t >= 2*w
            for i in range(2 * w, n):
                w1 = vals[i - 2 * w : i - w]
                w2 = vals[i - w : i]

                m1, m2 = float(np.mean(w1)), float(np.mean(w2))
                v1, v2 = float(np.var(w1, ddof=1)), float(np.var(w2, ddof=1))

                denom = np.sqrt((v1 / w) + (v2 / w) + self.eps)
                t_stat = abs(m2 - m1) / denom
                t_stats[grp_indices[i]] = t_stat

        return t_stats

    def _get_model_state(self) -> dict[str, Any]:
        return {
            "window": self.window,
            "threshold": self.threshold,
            "residual_col": self.residual_col,
        }

    def _set_model_state(self, state: dict[str, Any]) -> None:
        self.window = state.get("window", self.window)
        self.threshold = state.get("threshold", self.threshold)
        self.residual_col = state.get("residual_col", self.residual_col)


__all__ = ["LevelShiftDetector"]
