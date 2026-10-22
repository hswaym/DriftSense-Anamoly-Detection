"""Primary forecast-interval exceedance detector for DriftSense v2.

Detects anomalies when observed spend exceeds calibrated conformal prediction bounds,
subject to temporal persistence (k-of-n) and economic materiality filtering.
Supports sensitivity presets: Low, Balanced, and High.
"""

from __future__ import annotations

import datetime
from typing import Any, Literal

import numpy as np
import pandas as pd

from driftsense.detect.base import BaseAnomalyDetector
from driftsense.detect.materiality import MaterialityFilter
from driftsense.detect.persistence import PersistenceRule

SensitivityPreset = Literal["Low", "Balanced", "High"]

PRESET_CONFIGS: dict[SensitivityPreset, dict[str, Any]] = {
    "Low": {
        "k": 3,
        "n": 4,
        "min_dollar_exceedance": 50.0,
        "min_pct_exceedance": 30.0,
    },
    "Balanced": {
        "k": 2,
        "n": 3,
        "min_dollar_exceedance": 20.0,
        "min_pct_exceedance": 15.0,
    },
    "High": {
        "k": 1,
        "n": 2,
        "min_dollar_exceedance": 5.0,
        "min_pct_exceedance": 10.0,
    },
}


class ForecastIntervalExceedanceDetector(BaseAnomalyDetector):
    """Primary v2 detector: Conformal interval exceedance with persistence & materiality."""

    def __init__(
        self,
        name: str = "conformal_interval",
        sensitivity: SensitivityPreset = "Balanced",
        actual_col: str = "EffectiveCost",
        expected_col: str = "EffectiveCost_expected",
        upper_bound_col: str = "EffectiveCost_upper_bound",
        k: int | None = None,
        n: int | None = None,
        min_dollar: float | None = None,
        min_pct: float | None = None,
        threshold: float = 0.0,  # Any positive exceedance above upper bound
        config: dict[str, Any] | None = None,
        version: str = "2.0.0",
    ) -> None:
        cfg = config or {}
        cfg.update(
            {
                "sensitivity": sensitivity,
                "actual_col": actual_col,
                "expected_col": expected_col,
                "upper_bound_col": upper_bound_col,
                "threshold": threshold,
            }
        )
        super().__init__(name=name, threshold=threshold, config=cfg, version=version)
        self.sensitivity = sensitivity
        self.actual_col = actual_col
        self.expected_col = expected_col
        self.upper_bound_col = upper_bound_col

        # Resolve parameters from preset or explicit overrides
        preset = PRESET_CONFIGS.get(sensitivity, PRESET_CONFIGS["Balanced"])
        self.k = k if k is not None else preset["k"]
        self.n = n if n is not None else preset["n"]
        self.min_dollar = min_dollar if min_dollar is not None else preset["min_dollar_exceedance"]
        self.min_pct = min_pct if min_pct is not None else preset["min_pct_exceedance"]

        self.persistence_filter = PersistenceRule(k=self.k, n=self.n)
        self.materiality_filter = MaterialityFilter(
            min_dollar_exceedance=self.min_dollar,
            min_pct_exceedance=self.min_pct,
        )

    def fit(
        self,
        df_train: pd.DataFrame,
        residual_col: str = "residual",
        service_col: str = "ServiceName",
        time_col: str = "ChargePeriodStart",
        feature_cols: list[str] | None = None,
    ) -> ForecastIntervalExceedanceDetector:
        self.service_col = service_col
        self.time_col = time_col
        self.residual_col = residual_col
        self.is_fitted = True
        self.training_timestamp_utc = datetime.datetime.now(datetime.timezone.utc).isoformat()
        return self

    def score(self, df: pd.DataFrame) -> np.ndarray:
        """Compute normalized exceedance score above the upper prediction bound."""
        if not self.is_fitted:
            raise RuntimeError("Detector must be fitted before score() is called.")

        actuals = df[self.actual_col].to_numpy(dtype=float)
        uppers = (
            df[self.upper_bound_col].to_numpy(dtype=float)
            if self.upper_bound_col in df.columns
            else actuals
        )
        expecteds = (
            df[self.expected_col].to_numpy(dtype=float)
            if self.expected_col in df.columns
            else uppers
        )

        exceedance = np.maximum(0.0, actuals - uppers)
        scores = exceedance / np.maximum(expecteds, 1.0)
        return scores

    def predict(self, df: pd.DataFrame, threshold: float | None = None) -> np.ndarray:
        """Apply full detection pipeline: exceedance -> persistence -> materiality."""
        thresh = threshold if threshold is not None else self.threshold
        scores = self.score(df)
        raw_flags = (scores > thresh).astype(int)

        # 1. Apply persistence filter (k-of-n)
        persisted = self.persistence_filter.apply(
            df=df,
            raw_flags=raw_flags,
            service_col=self.service_col,
            time_col=self.time_col,
        )

        # 2. Apply materiality filter (minimum dollars and percent)
        actuals = df[self.actual_col].to_numpy(dtype=float)
        expecteds = (
            df[self.expected_col].to_numpy(dtype=float)
            if self.expected_col in df.columns
            else actuals
        )
        material_flags = self.materiality_filter.apply(
            raw_flags=persisted,
            actuals=actuals,
            expecteds=expecteds,
        )

        return material_flags

    def _get_model_state(self) -> dict[str, Any]:
        return {
            "sensitivity": self.sensitivity,
            "k": self.k,
            "n": self.n,
            "min_dollar": self.min_dollar,
            "min_pct": self.min_pct,
            "threshold": self.threshold,
            "actual_col": self.actual_col,
            "expected_col": self.expected_col,
            "upper_bound_col": self.upper_bound_col,
        }

    def _set_model_state(self, state: dict[str, Any]) -> None:
        self.sensitivity = state.get("sensitivity", self.sensitivity)
        self.k = state.get("k", self.k)
        self.n = state.get("n", self.n)
        self.min_dollar = state.get("min_dollar", self.min_dollar)
        self.min_pct = state.get("min_pct", self.min_pct)
        self.threshold = state.get("threshold", self.threshold)
        self.actual_col = state.get("actual_col", self.actual_col)
        self.expected_col = state.get("expected_col", self.expected_col)
        self.upper_bound_col = state.get("upper_bound_col", self.upper_bound_col)
        self.persistence_filter = PersistenceRule(k=self.k, n=self.n)
        self.materiality_filter = MaterialityFilter(
            min_dollar_exceedance=self.min_dollar,
            min_pct_exceedance=self.min_pct,
        )


__all__ = ["PRESET_CONFIGS", "ForecastIntervalExceedanceDetector", "SensitivityPreset"]
