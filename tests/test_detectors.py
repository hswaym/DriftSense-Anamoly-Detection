"""Unit tests for DriftSense anomaly detectors and synthetic injector."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from driftsense.detect.base import BaseAnomalyDetector
from driftsense.detect.iforest import IsolationForestDetector
from driftsense.detect.ocsvm import OneClassSVMDetector
from driftsense.detect.rolling_threshold import RollingThresholdDetector
from driftsense.detect.zscore import ZScoreDetector
from driftsense.synth.injector import SyntheticInjector


@pytest.fixture
def synthetic_residual_data() -> pd.DataFrame:
    """Generate synthetic residual and telemetry dataframe for detector testing."""
    dates = pd.date_range("2024-09-01 00:00:00", periods=72, freq="h", tz="UTC")
    rng = np.random.default_rng(42)

    rows = []
    for svc in ["Compute", "Storage"]:
        for d in dates:
            # Baseline normal residuals centered near 0
            res = float(rng.normal(loc=0.0, scale=0.1))
            rows.append(
                {
                    "ChargePeriodStart": d,
                    "ServiceName": svc,
                    "residual": res,
                    "EffectiveCost": max(0.0, 1.0 + res),
                    "ConsumedQuantity": 10.0,
                    "hour_of_day": d.hour,
                    "day_of_week": d.dayofweek,
                }
            )

    return pd.DataFrame(rows)


@pytest.mark.parametrize(
    "detector_cls, kwargs",
    [
        (ZScoreDetector, {"threshold": 2.5}),
        (RollingThresholdDetector, {"window": 12, "threshold": 2.5}),
        (IsolationForestDetector, {"n_estimators": 10, "threshold": 0.5}),
        (OneClassSVMDetector, {"threshold": 0.0}),
    ],
)
def test_unfitted_detector_raises(
    detector_cls: type[BaseAnomalyDetector],
    kwargs: dict,
    synthetic_residual_data: pd.DataFrame,
) -> None:
    """Verify calling score or predict before fit raises RuntimeError."""
    det = detector_cls(**kwargs)
    assert not det.is_fitted
    with pytest.raises(RuntimeError):
        det.score(synthetic_residual_data)
    with pytest.raises(RuntimeError):
        det.predict(synthetic_residual_data)


@pytest.mark.parametrize(
    "detector_cls, kwargs",
    [
        (ZScoreDetector, {"threshold": 2.5}),
        (RollingThresholdDetector, {"window": 12, "threshold": 2.5}),
        (IsolationForestDetector, {"n_estimators": 20, "threshold": 0.5}),
        (OneClassSVMDetector, {"threshold": 0.0}),
    ],
)
def test_fit_score_predict_and_persistence(
    detector_cls: type[BaseAnomalyDetector],
    kwargs: dict,
    synthetic_residual_data: pd.DataFrame,
    tmp_path,
) -> None:
    """Verify fit, score, predict, save, and load roundtrip with identical outputs."""
    det = detector_cls(**kwargs)

    # Fit detector
    fitted = det.fit(synthetic_residual_data)
    assert fitted.is_fitted
    assert det.training_timestamp_utc is not None
    assert len(det.config_hash) == 64

    # Score and predict
    scores_before = det.score(synthetic_residual_data)
    preds_before = det.predict(synthetic_residual_data)

    assert isinstance(scores_before, np.ndarray)
    assert isinstance(preds_before, np.ndarray)
    assert len(scores_before) == len(synthetic_residual_data)
    assert len(preds_before) == len(synthetic_residual_data)
    assert set(np.unique(preds_before)).issubset({0, 1})

    # Save detector
    save_file = tmp_path / f"{det.name}.joblib"
    saved_path = det.save(save_file)
    assert saved_path.exists()

    # Load detector
    loaded_det = detector_cls.load(saved_path)
    assert loaded_det.is_fitted
    assert loaded_det.name == det.name
    assert loaded_det.config_hash == det.config_hash

    # Score and predict with loaded detector
    scores_after = loaded_det.score(synthetic_residual_data)
    preds_after = loaded_det.predict(synthetic_residual_data)

    np.testing.assert_allclose(scores_before, scores_after, rtol=1e-5, atol=1e-5)
    np.testing.assert_array_equal(preds_before, preds_after)


def test_synthetic_injector(synthetic_residual_data: pd.DataFrame) -> None:
    """Verify synthetic anomaly and event injector conforms to Contracts 5 & 6."""
    injector = SyntheticInjector(
        seed=42, injection_rate=0.1, min_duration_hours=2, max_duration_hours=4
    )
    df_inj, labels, events = injector.inject(
        synthetic_residual_data,
        cost_col="EffectiveCost",
        service_col="ServiceName",
        time_col="ChargePeriodStart",
    )

    assert "is_anomaly" in df_inj.columns
    assert df_inj["is_anomaly"].sum() > 0
    assert len(labels) > 0
    assert len(events) > 0

    # Verify Contract 6 schema compliance
    lbl = labels[0]
    assert "label_id" in lbl
    assert "service_id" in lbl
    assert "onset_timestamp" in lbl
    assert "offset_timestamp" in lbl
    assert lbl["is_synthetic"] is True
    assert lbl["primary_cause"] in [
        "DEPLOYMENT_DEFECT",
        "AUTOSCALING_OVERPROVISION",
        "CONFIG_MODIFICATION",
        "EXTERNAL_TRAFFIC_SURGE",
        "RUNAWAY_BATCH_PROCESS",
    ]

    # Verify Contract 5 schema compliance
    evt = events[0]
    assert "event_id" in evt
    assert "ts_start" in evt
    assert "ts_end" in evt
    assert evt["is_synthetic"] is True
