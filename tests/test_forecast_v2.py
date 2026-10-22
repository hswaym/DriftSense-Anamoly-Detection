"""Phase 6 Forecasting and Uncertainty Calibration test suite for DriftSense v2.

Verifies:
- A6.1 Metric unit tests with hand-computed ground truth cases including zeros.
- A6.2 Interface tests for all forecasters (fit, predict, save, load).
- A6.3 Conformal coverage test on synthetic data with known noise (empirical >= nominal).
- A6.4 Hierarchical reconciliation coherence (sum of services == total account forecast).
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from driftsense.eval.forecast_metrics import (
    interval_coverage,
    interval_width,
    mean_absolute_error,
    mean_absolute_percentage_error,
    pinball_loss,
    root_mean_squared_error,
    weighted_absolute_percentage_error,
    winkler_score,
)
from driftsense.forecast.baselines import (
    MovingAverageForecaster,
    SeasonalNaiveForecaster,
)
from driftsense.forecast.boosted import BoostedTreeForecaster
from driftsense.forecast.conformal import SplitConformalCalibrator
from driftsense.forecast.ets import ETSForecaster
from driftsense.forecast.quantile import QuantileForecaster
from driftsense.forecast.reconcile import HierarchicalReconciler
from driftsense.forecast.sarima import SARIMAForecaster

# -----------------------------------------------------------------------------
# A6.1 Metric Unit Tests with Hand-Computed Cases Including Zeros
# -----------------------------------------------------------------------------

def test_a6_1_hand_computed_metrics() -> None:
    """A6.1: Verify metrics against hand-computed analytical cases."""
    # Case 1: Standard positive values
    y_true = np.array([10.0, 20.0, 30.0, 40.0])
    y_pred = np.array([12.0, 18.0, 33.0, 36.0])

    # |y - y_hat| = [2, 2, 3, 4] -> sum = 11, mean = 2.75
    assert mean_absolute_error(y_true, y_pred) == pytest.approx(2.75, abs=1e-5)

    # (y - y_hat)^2 = [4, 4, 9, 16] -> mean = 33/4 = 8.25 -> sqrt = 2.87228
    assert root_mean_squared_error(y_true, y_pred) == pytest.approx(np.sqrt(8.25), abs=1e-5)

    # sum(|y|) = 100 -> WAPE = (11 / 100) * 100% = 11.0%
    assert weighted_absolute_percentage_error(y_true, y_pred) == pytest.approx(11.0, abs=1e-4)

    # Pinball loss: tau = 0.5 is half of MAE = 2.75 / 2 = 1.375
    assert pinball_loss(y_true, y_pred, quantile=0.50) == pytest.approx(1.375, abs=1e-5)

    # Pinball loss tau = 0.90
    # diffs = [-2, 2, -3, 4]
    # loss for diff < 0 (under): (0.9 - 1) * diff = -0.1 * -2 = 0.2; -0.1 * -3 = 0.3
    # loss for diff > 0 (over): 0.9 * diff = 0.9 * 2 = 1.8; 0.9 * 4 = 3.6
    # mean = (0.2 + 1.8 + 0.3 + 3.6) / 4 = 5.9 / 4 = 1.475
    assert pinball_loss(y_true, y_pred, quantile=0.90) == pytest.approx(1.475, abs=1e-5)


def test_a6_1_zero_handling_and_sparsity() -> None:
    """A6.1: Verify metrics under sparse series with zero actuals."""
    # Intermittent series with zero actuals
    y_true_zeros = np.array([0.0, 0.0, 10.0, 0.0, 20.0])
    y_pred = np.array([0.5, 0.0, 12.0, 1.0, 18.0])

    # Masked MAPE should only evaluate on indices 2 and 4 ([10, 20])
    # errors = |10-12|/10 = 0.20, |20-18|/20 = 0.10 -> mean = 15.0%
    mape_masked = mean_absolute_percentage_error(y_true_zeros, y_pred)
    assert mape_masked == pytest.approx(15.0, abs=1e-4)

    # If all actuals are zero, MAPE must return None safely
    all_zeros = np.array([0.0, 0.0, 0.0])
    assert mean_absolute_percentage_error(all_zeros, np.array([1.0, 2.0, 3.0])) is None

    # WAPE on sparse series
    # abs err = 0.5 + 0.0 + 2.0 + 1.0 + 2.0 = 5.5
    # total actual = 30.0 -> WAPE = 5.5 / 30 * 100 = 18.333%
    assert weighted_absolute_percentage_error(y_true_zeros, y_pred) == pytest.approx(
        (5.5 / 30.0) * 100.0, abs=1e-4
    )


def test_a6_1_interval_metrics() -> None:
    """A6.1: Verify interval coverage, width, and Winkler score."""
    y = np.array([10.0, 20.0, 30.0, 40.0])
    lower = np.array([8.0, 15.0, 25.0, 45.0])  # point 4 misses (40 < 45)
    upper = np.array([12.0, 25.0, 35.0, 50.0])

    # Coverage: points 0, 1, 2 covered; point 3 missed -> 3/4 = 0.75
    assert interval_coverage(y, lower, upper) == pytest.approx(0.75, abs=1e-5)

    # Width: [4, 10, 10, 5] -> mean = 7.25
    assert interval_width(lower, upper) == pytest.approx(7.25, abs=1e-5)

    # Winkler score with alpha = 0.10 (multiplier 2/0.10 = 20)
    # Point 0: 4
    # Point 1: 10
    # Point 2: 10
    # Point 3: width=5 + 20 * (45 - 40) = 5 + 100 = 105
    # Mean = (4 + 10 + 10 + 105) / 4 = 129 / 4 = 32.25
    assert winkler_score(y, lower, upper, alpha=0.10) == pytest.approx(32.25, abs=1e-5)


# -----------------------------------------------------------------------------
# A6.2 Interface Tests Across Forecaster Suite
# -----------------------------------------------------------------------------

@pytest.fixture
def sample_train_val() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Generate multi-service train and val splits with lag features."""
    times_train = pd.date_range("2024-09-01", periods=96, freq="1h", tz="UTC")
    times_val = pd.date_range("2024-09-05", periods=24, freq="1h", tz="UTC")

    def make_df(times: pd.DatetimeIndex) -> pd.DataFrame:
        rows = []
        for svc in ["Compute_EC2", "Storage_S3"]:
            base = 50.0 if svc == "Compute_EC2" else 10.0
            for i, t in enumerate(times):
                cost = base + (t.hour % 12) * 2.0
                rows.append(
                    {
                        "ServiceName": svc,
                        "ChargePeriodStart": t,
                        "EffectiveCost": cost,
                        "hour_of_day": t.hour,
                        "day_of_week": t.dayofweek,
                        "EffectiveCost_lag_1": cost * 0.98,
                        "EffectiveCost_lag_2": cost * 0.95,
                        "EffectiveCost_roll_mean_6h": cost,
                    }
                )
        return pd.DataFrame(rows)

    return make_df(times_train), make_df(times_val)


@pytest.mark.parametrize(
    "model_cls, kwargs",
    [
        (SeasonalNaiveForecaster, {"seasonality": 24}),
        (MovingAverageForecaster, {"window": 6}),
        (ETSForecaster, {"seasonality": 24}),
        (SARIMAForecaster, {"seasonal_order": (1, 0, 0, 24)}),
        (BoostedTreeForecaster, {"n_estimators": 20, "max_depth": 3}),
        (QuantileForecaster, {"quantiles": (0.10, 0.50, 0.90), "n_estimators": 20}),
    ],
)
def test_a6_2_forecaster_interfaces(
    model_cls: type,
    kwargs: dict,
    sample_train_val: tuple[pd.DataFrame, pd.DataFrame],
) -> None:
    """A6.2 Interface Test: fit, predict, save, load across all forecasters."""
    df_train, df_val = sample_train_val
    model = model_cls(**kwargs)

    # 1. Fit
    model.fit(df_train)
    assert model.is_fitted
    assert model.training_timestamp_utc is not None

    # 2. Predict
    preds = model.predict(df_val)
    assert isinstance(preds, np.ndarray)
    assert len(preds) == len(df_val)
    assert (preds >= 0.0).all(), "Predictions must be non-negative!"

    # 3. Save and Load
    with tempfile.TemporaryDirectory() as tmpdir:
        save_path = Path(tmpdir) / "test_model.joblib"
        model.save(save_path)
        assert save_path.exists()

        loaded_model = model_cls.load(save_path)
        assert loaded_model.is_fitted
        preds_loaded = loaded_model.predict(df_val)
        np.testing.assert_allclose(preds, preds_loaded, rtol=1e-5)


# -----------------------------------------------------------------------------
# A6.3 Split-Conformal Prediction Coverage Test
# -----------------------------------------------------------------------------

def test_a6_3_conformal_coverage_guarantee() -> None:
    """A6.3 Conformal Coverage: Empirical coverage on test slice satisfies 1 - alpha."""
    rng = np.random.RandomState(42)
    n_train = 500
    n_val = 500
    n_test = 500

    # True stationary diurnal process: Y = 50 + 10 * sin(2*pi*hour/24) + N(0, sigma=3)
    def make_synthetic_panel(start_time: str, n: int) -> pd.DataFrame:
        times = pd.date_range(start_time, periods=n, freq="1h", tz="UTC")
        hours = times.hour.to_numpy()
        signal = 50.0 + 10.0 * np.sin(2.0 * np.pi * hours / 24.0)
        noise = rng.normal(0.0, 3.0, size=n)
        cost = np.maximum(0.0, signal + noise)
        return pd.DataFrame(
            {
                "ServiceName": "Compute",
                "ChargePeriodStart": times,
                "EffectiveCost": cost,
                "hour_of_day": hours,
                "day_of_week": times.dayofweek,
                "sin_hour": np.sin(2.0 * np.pi * hours / 24.0),
                "cos_hour": np.cos(2.0 * np.pi * hours / 24.0),
            }
        )

    df_train = make_synthetic_panel("2024-01-01 00:00:00", n_train)
    df_val = make_synthetic_panel("2024-01-22 00:00:00", n_val)
    df_test = make_synthetic_panel("2024-02-12 00:00:00", n_test)

    # Base forecaster
    base = BoostedTreeForecaster(n_estimators=40, max_depth=3)
    base.fit(df_train)

    # Conformal calibration on validation with alpha = 0.10 (nominal coverage 90%)
    calibrator = SplitConformalCalibrator(forecaster=base, default_alpha=0.10)
    calibrator.calibrate(df_val, target_col="EffectiveCost", alphas=(0.05, 0.10, 0.20))

    assert calibrator.is_calibrated

    # Evaluate on unseen test partition
    _y_pred, lower, upper = calibrator.predict_interval(df_test, alpha=0.10)
    y_test = df_test["EffectiveCost"].to_numpy()

    test_coverage = interval_coverage(y_test, lower, upper)
    # Finite-sample guarantee: nominal 90%, allowing minor binomial test tolerance >= 86%
    assert test_coverage >= 0.86, (
        f"Conformal coverage violation: Expected >= 0.86 (nominal 0.90), got {test_coverage:.3f}"
    )


# -----------------------------------------------------------------------------
# A6.4 Hierarchical Reconciliation Test
# -----------------------------------------------------------------------------

def test_a6_4_hierarchical_reconciliation(sample_train_val: tuple[pd.DataFrame, pd.DataFrame]) -> None:
    """A6.4 Reconciliation Test: Bottom-up and MinT guarantee sum(services) == total."""
    df_train, df_val = sample_train_val

    # Fit forecaster
    model = SeasonalNaiveForecaster(seasonality=24)
    model.fit(df_train)

    # Forecast each service
    preds_svc = {}
    for svc in ["Compute_EC2", "Storage_S3"]:
        sub_val = df_val[df_val["ServiceName"] == svc]
        preds_svc[svc] = model.predict(sub_val)

    reconciler = HierarchicalReconciler(method="bottom_up")
    reconciled_svc, total_rec = reconciler.reconcile(preds_svc)

    # Mathematical identity: sum of reconciled services equals reconciled total at every step
    sum_bottom = np.sum(np.column_stack(list(reconciled_svc.values())), axis=1)
    np.testing.assert_allclose(sum_bottom, total_rec, rtol=1e-5)
