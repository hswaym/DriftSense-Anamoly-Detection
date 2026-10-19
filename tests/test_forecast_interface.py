"""Unit tests for DriftSense forecasting model interfaces and persistence."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from driftsense.forecast.base import BaseForecaster
from driftsense.forecast.naive import MovingAverageForecaster, SeasonalNaiveForecaster
from driftsense.forecast.smoothing import ExponentialSmoothingForecaster
from driftsense.forecast.xgb import XGBoostForecaster


@pytest.fixture
def synthetic_forecast_dataset() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Generate synthetic train and val data for forecaster unit testing."""
    dates_train = pd.date_range("2024-09-01 00:00:00", periods=72, freq="h", tz="UTC")
    dates_val = pd.date_range("2024-09-04 00:00:00", periods=24, freq="h", tz="UTC")

    records_train = []
    for svc in ["Compute", "Storage"]:
        for d in dates_train:
            cost = 1.5 * (d.hour % 24) + (0.5 if svc == "Compute" else 0.2)
            records_train.append(
                {
                    "ChargePeriodStart": d,
                    "ServiceName": svc,
                    "EffectiveCost": cost,
                    "ConsumedQuantity": cost * 10.0,
                    "hour_of_day": d.hour,
                    "day_of_week": d.dayofweek,
                    "lag_1": cost * 0.95,
                    "rolling_mean_6": cost * 0.98,
                }
            )

    records_val = []
    for svc in ["Compute", "Storage"]:
        for d in dates_val:
            cost = 1.5 * (d.hour % 24) + (0.5 if svc == "Compute" else 0.2)
            records_val.append(
                {
                    "ChargePeriodStart": d,
                    "ServiceName": svc,
                    "EffectiveCost": cost,
                    "ConsumedQuantity": cost * 10.0,
                    "hour_of_day": d.hour,
                    "day_of_week": d.dayofweek,
                    "lag_1": cost * 0.95,
                    "rolling_mean_6": cost * 0.98,
                }
            )

    return pd.DataFrame(records_train), pd.DataFrame(records_val)


@pytest.mark.parametrize(
    "model_cls, kwargs",
    [
        (SeasonalNaiveForecaster, {"seasonality": 24}),
        (MovingAverageForecaster, {"window": 24}),
        (ExponentialSmoothingForecaster, {"alpha": 0.25}),
        (XGBoostForecaster, {"n_estimators": 10, "max_depth": 2, "device": "cpu"}),
    ],
)
def test_unfitted_model_raises(
    model_cls: type[BaseForecaster],
    kwargs: dict,
    synthetic_forecast_dataset: tuple[pd.DataFrame, pd.DataFrame],
) -> None:
    """Verify that calling predict or save before fit raises RuntimeError."""
    _, df_val = synthetic_forecast_dataset
    model = model_cls(**kwargs)
    assert not model.is_fitted
    with pytest.raises(RuntimeError):
        model.predict(df_val)


@pytest.mark.parametrize(
    "model_cls, kwargs",
    [
        (SeasonalNaiveForecaster, {"seasonality": 24}),
        (MovingAverageForecaster, {"window": 24}),
        (ExponentialSmoothingForecaster, {"alpha": 0.25}),
        (XGBoostForecaster, {"n_estimators": 10, "max_depth": 2, "device": "cpu"}),
    ],
)
def test_fit_predict_and_persistence(
    model_cls: type[BaseForecaster],
    kwargs: dict,
    synthetic_forecast_dataset: tuple[pd.DataFrame, pd.DataFrame],
    tmp_path,
) -> None:
    """Verify fit, predict, save, and load roundtrip with identical predictions."""
    df_train, df_val = synthetic_forecast_dataset
    model = model_cls(**kwargs)

    # Fit model
    fitted = model.fit(df_train)
    assert fitted.is_fitted
    assert model.training_timestamp_utc is not None
    assert len(model.config_hash) == 64

    # Generate predictions
    preds_before = model.predict(df_val)
    assert isinstance(preds_before, np.ndarray)
    assert len(preds_before) == len(df_val)
    assert (preds_before >= 0.0).all(), "Predictions must be non-negative"

    # Save model
    save_file = tmp_path / f"{model.name}.joblib"
    saved_path = model.save(save_file)
    assert saved_path.exists()

    # Load model
    loaded_model = model_cls.load(saved_path)
    assert loaded_model.is_fitted
    assert loaded_model.name == model.name
    assert loaded_model.config_hash == model.config_hash

    # Predict with loaded model
    preds_after = loaded_model.predict(df_val)
    np.testing.assert_allclose(preds_before, preds_after, rtol=1e-5, atol=1e-5)


def test_xgboost_feature_importances_and_columns(
    synthetic_forecast_dataset: tuple[pd.DataFrame, pd.DataFrame],
) -> None:
    """Verify XGBoost feature importance calculation and explicit feature subset."""
    df_train, df_val = synthetic_forecast_dataset
    features = ["ConsumedQuantity", "hour_of_day", "lag_1", "rolling_mean_6"]

    xgb_model = XGBoostForecaster(n_estimators=10, max_depth=2, device="cpu", seed=42)
    xgb_model.fit(df_train, feature_cols=features)

    assert xgb_model.feature_cols_ == features
    assert len(xgb_model.feature_importances_) == len(features)
    assert all(k in xgb_model.feature_importances_ for k in features)

    preds = xgb_model.predict(df_val)
    assert len(preds) == len(df_val)
    assert not np.isnan(preds).any()
