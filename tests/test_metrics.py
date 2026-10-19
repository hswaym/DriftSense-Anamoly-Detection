"""Unit tests for forecasting evaluation metrics and zero-actual handling."""

from __future__ import annotations

import numpy as np
import pytest

from driftsense.eval.metrics import (
    compute_all_metrics,
    mean_absolute_error,
    mean_absolute_percentage_error,
    mean_absolute_scaled_error,
    root_mean_squared_error,
    symmetric_mean_absolute_percentage_error,
    weighted_absolute_percentage_error,
)


def test_standard_metrics_perfect_predictions() -> None:
    """Test that metrics return 0.0 when predictions match ground truth exactly."""
    y = np.array([10.0, 20.0, 30.0, 40.0])
    metrics = compute_all_metrics(y, y)

    assert metrics["mae"] == pytest.approx(0.0)
    assert metrics["rmse"] == pytest.approx(0.0)
    assert metrics["mape"] == pytest.approx(0.0)
    assert metrics["smape"] == pytest.approx(0.0)
    assert metrics["wape"] == pytest.approx(0.0)
    assert metrics["mase"] == pytest.approx(0.0)


def test_known_metric_values() -> None:
    """Test metrics against analytical known values."""
    y_true = np.array([100.0, 200.0])
    y_pred = np.array([110.0, 180.0])  # Errors: +10, -20 -> MAE = 15

    assert mean_absolute_error(y_true, y_pred) == pytest.approx(15.0)
    assert root_mean_squared_error(y_true, y_pred) == pytest.approx(
        np.sqrt((100 + 400) / 2)
    )

    # MAPE: (10/100 + 20/200) / 2 = (0.10 + 0.10) / 2 = 10%
    assert mean_absolute_percentage_error(y_true, y_pred) == pytest.approx(10.0)

    # WAPE: (10 + 20) / (100 + 200) = 30 / 300 = 10%
    assert weighted_absolute_percentage_error(y_true, y_pred) == pytest.approx(10.0)


def test_mape_zero_actual_handling() -> None:
    """Test MAPE behavior when ground truth contains zero values (A6.1 requirement)."""
    # y_true has zeros (e.g. intermittent services in cloud billing)
    y_true = np.array([0.0, 0.0, 50.0, 100.0])
    y_pred = np.array([0.0, 5.0, 50.0, 100.0])

    # Epsilon floor mode must NOT raise ZeroDivisionError or return inf / nan
    mape_eps = mean_absolute_percentage_error(
        y_true, y_pred, eps=1e-4, mode="epsilon_floor"
    )
    assert np.isfinite(mape_eps)
    assert mape_eps >= 0.0

    # Masked mode should compute MAPE only over non-zero elements
    # Non-zero elements have 0 error -> masked MAPE = 0.0%
    mape_masked = mean_absolute_percentage_error(
        y_true, y_pred, eps=1e-4, mode="masked"
    )
    assert mape_masked == pytest.approx(0.0)


def test_smape_properties() -> None:
    """Test sMAPE bounds and symmetry."""
    y_true = np.array([0.0, 10.0, 20.0])
    y_pred = np.array([10.0, 0.0, 20.0])

    smape = symmetric_mean_absolute_percentage_error(y_true, y_pred)
    # sMAPE is bounded in [0, 200]
    assert 0.0 <= smape <= 200.0
    assert np.isfinite(smape)


def test_wape_robustness_on_sparse_series() -> None:
    """Test WAPE on sparse cloud billing series with 90% zeros."""
    y_true = np.zeros(100)
    y_true[10] = 50.0
    y_true[50] = 100.0  # Sum = 150.0

    y_pred = np.zeros(100)
    y_pred[10] = 40.0  # error 10
    y_pred[50] = 120.0  # error 20
    # Total error = 30. WAPE = 30 / 150 * 100% = 20%

    wape = weighted_absolute_percentage_error(y_true, y_pred)
    assert wape == pytest.approx(20.0)


def test_mase_calculation() -> None:
    """Test MASE scaling against in-sample naive differences."""
    y_train = np.array(
        [10.0, 12.0, 14.0, 16.0, 18.0]
    )  # diffs: 2, 2, 2, 2 -> scale = 2.0
    y_true = np.array([20.0, 22.0])
    y_pred = np.array([21.0, 23.0])  # errors: 1, 1 -> MAE = 1.0

    # MASE = MAE / scale = 1.0 / 2.0 = 0.5 (< 1.0 indicates improvement over naive)
    mase = mean_absolute_scaled_error(y_true, y_pred, y_train=y_train, seasonality=1)
    assert mase == pytest.approx(0.5)
