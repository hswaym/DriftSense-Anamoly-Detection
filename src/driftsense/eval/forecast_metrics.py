"""Comprehensive forecasting evaluation metrics for DriftSense v2.

Implements:
1. Point Forecast Metrics:
   - MAE (Mean Absolute Error)
   - RMSE (Root Mean Squared Error)
   - WAPE (Weighted Absolute Percentage Error / Normalized MAE)
   - sMAPE (Symmetric Mean Absolute Percentage Error)
   - MASE (Mean Absolute Scaled Error)
   - MAPE (Mean Absolute Percentage Error with explicit zero masking)
2. Probabilistic and Interval Metrics:
   - Pinball Loss (Quantile Loss) for specified quantile tau
   - Prediction Interval Coverage Probability (PICP)
   - Mean Prediction Interval Width (MPIW)
   - Winkler Score (Penalized interval quality score)
"""

from __future__ import annotations

import logging
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)


def mean_absolute_error(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    """Compute Mean Absolute Error (MAE)."""
    y_t = np.asarray(y_true, dtype=float)
    y_p = np.asarray(y_pred, dtype=float)
    return float(np.mean(np.abs(y_t - y_p)))


def root_mean_squared_error(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    """Compute Root Mean Squared Error (RMSE)."""
    y_t = np.asarray(y_true, dtype=float)
    y_p = np.asarray(y_pred, dtype=float)
    return float(np.sqrt(np.mean((y_t - y_p) ** 2)))


def weighted_absolute_percentage_error(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    eps: float = 1e-6,
) -> float:
    """Compute Weighted Absolute Percentage Error (WAPE).

    Formula: sum(|y - y_hat|) / (sum(|y|) + eps) * 100%
    Ideal for zero-inflated and sparse cloud billing series.
    """
    y_t = np.asarray(y_true, dtype=float)
    y_p = np.asarray(y_pred, dtype=float)
    total_abs_err = np.sum(np.abs(y_t - y_p))
    total_actual = np.sum(np.abs(y_t)) + eps
    return float((total_abs_err / total_actual) * 100.0)


def symmetric_mean_absolute_percentage_error(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    eps: float = 1e-6,
) -> float:
    """Compute Symmetric Mean Absolute Percentage Error (sMAPE).

    Formula: (100% / n) * sum( 2 * |y - y_hat| / (|y| + |y_hat| + eps) )
    Bounded in [0%, 200%].
    """
    y_t = np.asarray(y_true, dtype=float)
    y_p = np.asarray(y_pred, dtype=float)
    denom = np.abs(y_t) + np.abs(y_p) + eps
    return float(np.mean(2.0 * np.abs(y_t - y_p) / denom) * 100.0)


def mean_absolute_percentage_error(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    eps: float = 1e-6,
) -> float | None:
    """Compute MAPE strictly masked to non-zero actuals.

    Returns None if all actual values are zero (to avoid false division by zero).
    """
    y_t = np.asarray(y_true, dtype=float)
    y_p = np.asarray(y_pred, dtype=float)
    nonzero_mask = np.abs(y_t) > eps

    if not np.any(nonzero_mask):
        return None

    return float(
        np.mean(np.abs((y_t[nonzero_mask] - y_p[nonzero_mask]) / y_t[nonzero_mask]))
        * 100.0
    )


def mean_absolute_scaled_error(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    y_train: np.ndarray | None = None,
    seasonality: int = 1,
    eps: float = 1e-6,
) -> float:
    """Compute Mean Absolute Scaled Error (MASE).

    Scales MAE by in-sample seasonal naive error on training partition.
    """
    y_t = np.asarray(y_true, dtype=float)
    y_p = np.asarray(y_pred, dtype=float)
    mae = mean_absolute_error(y_t, y_p)

    ref = np.asarray(y_train, dtype=float) if y_train is not None else y_t
    if len(ref) <= seasonality:
        return float(mae / (np.mean(np.abs(ref)) + eps))

    naive_diff = np.abs(ref[seasonality:] - ref[:-seasonality])
    scale = float(np.mean(naive_diff)) + eps
    return float(mae / scale)


def pinball_loss(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    quantile: float,
) -> float:
    """Compute Pinball Loss (Quantile Loss) for a given quantile tau.

    Formula: mean( max(tau * (y - y_hat), (tau - 1) * (y - y_hat)) )
    """
    if not 0.0 < quantile < 1.0:
        raise ValueError(f"Quantile must be in (0, 1). Got {quantile}")

    y_t = np.asarray(y_true, dtype=float)
    y_p = np.asarray(y_pred, dtype=float)
    diff = y_t - y_p
    loss = np.maximum(quantile * diff, (quantile - 1.0) * diff)
    return float(np.mean(loss))


def interval_coverage(
    y_true: np.ndarray,
    lower: np.ndarray,
    upper: np.ndarray,
) -> float:
    """Compute Prediction Interval Coverage Probability (PICP).

    Fraction of true observations falling within [lower, upper].
    """
    y_t = np.asarray(y_true, dtype=float)
    l_bound = np.asarray(lower, dtype=float)
    u_bound = np.asarray(upper, dtype=float)
    covered = (y_t >= l_bound) & (y_t <= u_bound)
    return float(np.mean(covered))


def interval_width(
    lower: np.ndarray,
    upper: np.ndarray,
) -> float:
    """Compute Mean Prediction Interval Width (MPIW)."""
    l_bound = np.asarray(lower, dtype=float)
    u_bound = np.asarray(upper, dtype=float)
    return float(np.mean(np.maximum(0.0, u_bound - l_bound)))


def winkler_score(
    y_true: np.ndarray,
    lower: np.ndarray,
    upper: np.ndarray,
    alpha: float = 0.05,
) -> float:
    """Compute Winkler Score for prediction interval at nominal coverage (1 - alpha).

    Penalizes intervals that fail to cover actuals proportionally to the miss distance:
    - If lower <= y <= upper: width
    - If y < lower: width + 2/alpha * (lower - y)
    - If y > upper: width + 2/alpha * (y - upper)
    """
    if not 0.0 < alpha < 1.0:
        raise ValueError(f"Alpha must be in (0, 1). Got {alpha}")

    y_t = np.asarray(y_true, dtype=float)
    l_bound = np.asarray(lower, dtype=float)
    u_bound = np.asarray(upper, dtype=float)
    width = np.maximum(0.0, u_bound - l_bound)

    multiplier = 2.0 / alpha
    below_penalty = np.where(y_t < l_bound, multiplier * (l_bound - y_t), 0.0)
    above_penalty = np.where(y_t > u_bound, multiplier * (y_t - u_bound), 0.0)

    scores = width + below_penalty + above_penalty
    return float(np.mean(scores))


def compute_forecast_evaluation_suite(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    y_train: np.ndarray | None = None,
    lower: np.ndarray | None = None,
    upper: np.ndarray | None = None,
    alpha: float = 0.10,
) -> dict[str, Any]:
    """Compute comprehensive forecast evaluation metrics dictionary."""
    metrics: dict[str, Any] = {
        "mae": mean_absolute_error(y_true, y_pred),
        "rmse": root_mean_squared_error(y_true, y_pred),
        "wape": weighted_absolute_percentage_error(y_true, y_pred),
        "smape": symmetric_mean_absolute_percentage_error(y_true, y_pred),
        "mape": mean_absolute_percentage_error(y_true, y_pred),
        "mase": mean_absolute_scaled_error(y_true, y_pred, y_train=y_train),
    }

    if lower is not None and upper is not None:
        metrics["coverage"] = interval_coverage(y_true, lower, upper)
        metrics["interval_width"] = interval_width(lower, upper)
        metrics["winkler_score"] = winkler_score(y_true, lower, upper, alpha=alpha)

    return metrics
