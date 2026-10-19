"""Forecasting evaluation metrics for DriftSense.

Implements standard and scale-independent metrics:
- MAE (Mean Absolute Error)
- RMSE (Root Mean Squared Error)
- MAPE (Mean Absolute Percentage Error with explicit zero handling)
- sMAPE (Symmetric Mean Absolute Percentage Error)
- WAPE (Weighted Absolute Percentage Error / Normalized MAE)
- MASE (Mean Absolute Scaled Error)
"""

from __future__ import annotations

import logging

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


def mean_absolute_percentage_error(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    eps: float = 1e-4,
    mode: str = "epsilon_floor",
) -> float:
    """Compute Mean Absolute Percentage Error (MAPE) with explicit zero handling.

    Args:
        y_true: Ground truth observations.
        y_pred: Predicted values.
        eps: Small positive constant to prevent division by zero.
        mode: Zero-handling policy:
              - 'epsilon_floor': denominator is max(|y_true|, eps).
              - 'masked': percentage error computed only where |y_true| > eps.

    Returns:
        float: MAPE percentage (0 to 100+).
    """
    y_t = np.asarray(y_true, dtype=float)
    y_p = np.asarray(y_pred, dtype=float)

    if mode == "masked":
        mask = np.abs(y_t) > eps
        if not np.any(mask):
            return 0.0
        return float(np.mean(np.abs((y_t[mask] - y_p[mask]) / y_t[mask])) * 100.0)
    else:  # epsilon_floor
        denom = np.maximum(np.abs(y_t), eps)
        return float(np.mean(np.abs((y_t - y_p) / denom)) * 100.0)


def symmetric_mean_absolute_percentage_error(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    eps: float = 1e-6,
) -> float:
    """Compute Symmetric Mean Absolute Percentage Error (sMAPE).

    Formula: (100% / n) * sum( 2 * |y - y_hat| / (|y| + |y_hat| + eps) )
    Bounded between 0% and 200%. Well-behaved when y_true or y_pred is near zero.
    """
    y_t = np.asarray(y_true, dtype=float)
    y_p = np.asarray(y_pred, dtype=float)
    denom = np.abs(y_t) + np.abs(y_p) + eps
    return float(np.mean(2.0 * np.abs(y_t - y_p) / denom) * 100.0)


def weighted_absolute_percentage_error(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    eps: float = 1e-6,
) -> float:
    """Compute Weighted Absolute Percentage Error (WAPE).

    Formula: sum(|y - y_hat|) / (sum(|y|) + eps) * 100%
    Ideal for intermittent or sparse cloud cost time series because it avoids
    per-point division by near-zero denominators.
    """
    y_t = np.asarray(y_true, dtype=float)
    y_p = np.asarray(y_pred, dtype=float)
    total_abs_err = np.sum(np.abs(y_t - y_p))
    total_actual = np.sum(np.abs(y_t)) + eps
    return float((total_abs_err / total_actual) * 100.0)


def mean_absolute_scaled_error(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    y_train: np.ndarray | None = None,
    seasonality: int = 1,
    eps: float = 1e-6,
) -> float:
    """Compute Mean Absolute Scaled Error (MASE).

    Scales MAE by the in-sample mean absolute error of a naive benchmark.
    MASE < 1.0 indicates model outperforms the naive benchmark.
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


def compute_all_metrics(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    y_train: np.ndarray | None = None,
    eps: float = 1e-4,
) -> dict[str, float]:
    """Compute full suite of evaluation metrics."""
    return {
        "mae": mean_absolute_error(y_true, y_pred),
        "rmse": root_mean_squared_error(y_true, y_pred),
        "mape": mean_absolute_percentage_error(
            y_true, y_pred, eps=eps, mode="epsilon_floor"
        ),
        "mape_masked": mean_absolute_percentage_error(
            y_true, y_pred, eps=eps, mode="masked"
        ),
        "smape": symmetric_mean_absolute_percentage_error(y_true, y_pred),
        "wape": weighted_absolute_percentage_error(y_true, y_pred),
        "mase": mean_absolute_scaled_error(y_true, y_pred, y_train=y_train),
    }
