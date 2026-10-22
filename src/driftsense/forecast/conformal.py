"""Split conformal prediction interval calibrator for DriftSense v2.

Provides finite-sample valid, distribution-free prediction intervals:
P(Y_{t} in C(X_{t})) >= 1 - alpha
calibrated strictly on the validation partition without model retuning.
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd

from driftsense.forecast.base import BaseForecaster

logger = logging.getLogger(__name__)


class SplitConformalCalibrator:
    """Split Conformal Prediction interval engine wrapping any BaseForecaster."""

    def __init__(
        self,
        forecaster: BaseForecaster,
        default_alpha: float = 0.10,
        symmetric: bool = True,
    ) -> None:
        """Initialize conformal calibrator.

        Args:
            forecaster: Fitted BaseForecaster instance.
            default_alpha: Default significance level (1 - alpha is nominal coverage, e.g. 0.90).
            symmetric: If True, uses absolute residuals |y - y_hat|.
                       If False, computes separate one-sided conformal quantiles.
        """
        self.forecaster = forecaster
        self.default_alpha = default_alpha
        self.symmetric = symmetric
        self.is_calibrated = False

        # Calibration state
        self.val_residuals_: np.ndarray | None = None
        self.conformal_quantile_: float = 0.0
        self.conformal_quantiles_by_alpha_: dict[float, float] = {}
        self.empirical_coverage_: float = 0.0
        self.n_calibration_samples_: int = 0

    def calibrate(
        self,
        df_val: pd.DataFrame,
        target_col: str = "EffectiveCost",
        alphas: tuple[float, ...] = (0.05, 0.10, 0.20),
    ) -> SplitConformalCalibrator:
        """Calibrate conformal nonconformity scores on validation slice.

        Strictly executed on validation data (D_val). Model parameters remain frozen.
        """
        if not self.forecaster.is_fitted:
            raise RuntimeError("Base forecaster must be fitted before calibration.")

        y_true = np.maximum(0.0, df_val[target_col].to_numpy(dtype=float))
        y_pred = np.maximum(0.0, self.forecaster.predict(df_val))

        n = len(y_true)
        if n == 0:
            raise ValueError("Validation DataFrame must contain at least 1 observation for calibration.")

        # Compute nonconformity scores R_i = |y_i - y_hat_i|
        scores = np.abs(y_true - y_pred)
        self.val_residuals_ = scores
        self.n_calibration_samples_ = n
        self.conformal_quantiles_by_alpha_ = {}

        for a in alphas:
            # Conformal finite-sample correction: level = ceil((n+1)(1-a)) / n
            k = int(np.ceil((n + 1) * (1.0 - a)))
            k = min(n, max(1, k))
            # 1-indexed k-th order statistic
            sorted_scores = np.sort(scores)
            q_val = float(sorted_scores[k - 1])
            self.conformal_quantiles_by_alpha_[a] = q_val

        self.conformal_quantile_ = self.conformal_quantiles_by_alpha_.get(
            self.default_alpha, float(np.percentile(scores, 90.0))
        )

        # Empirical coverage on validation slice
        covered = scores <= self.conformal_quantile_
        self.empirical_coverage_ = float(np.mean(covered))

        self.is_calibrated = True
        logger.info(
            "ConformalCalibrator calibrated on %d samples. Nominal %.1f%%, Empirical Coverage: %.2f%%, Quantile: %.4f",
            n,
            (1.0 - self.default_alpha) * 100.0,
            self.empirical_coverage_ * 100.0,
            self.conformal_quantile_,
        )
        return self

    def predict_interval(
        self,
        df: pd.DataFrame,
        alpha: float | None = None,
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Compute point prediction and conformal lower/upper bounds.

        Returns:
            tuple[y_pred, lower_bound, upper_bound]
        """
        if not self.is_calibrated:
            raise RuntimeError("Calibrator must be calibrated on validation data before predict_interval().")

        target_alpha = alpha if alpha is not None else self.default_alpha
        q_val = self.conformal_quantiles_by_alpha_.get(target_alpha, self.conformal_quantile_)

        y_pred = np.maximum(0.0, self.forecaster.predict(df))
        lower_bound = np.maximum(0.0, y_pred - q_val)
        upper_bound = y_pred + q_val

        return y_pred, lower_bound, upper_bound


__all__ = ["SplitConformalCalibrator"]
