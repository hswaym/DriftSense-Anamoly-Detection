"""Phase 7 Anomaly Detection, Materiality, and Severity test suite for DriftSense v2.

Verifies:
- A7.1 Event-level detection metrics and detection latency against hand-computed ground truth.
- A7.2 Materiality filtering and k-of-n temporal persistence rules.
- A7.3 Forecast-interval exceedance detector interface and sensitivity presets (Low, Balanced, High).
- A7.4 Multidimensional severity scoring and tier classification.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from driftsense.detect.changepoint import LevelShiftDetector
from driftsense.detect.interval import ForecastIntervalExceedanceDetector
from driftsense.detect.materiality import MaterialityFilter
from driftsense.detect.persistence import PersistenceRule
from driftsense.detect.severity import SeverityScorer
from driftsense.eval.detection_metrics import (
    alerts_per_spend,
    alerts_per_week,
    event_level_metrics,
    precision_recall_auc,
    presumed_normal_alert_rate,
)

# -----------------------------------------------------------------------------
# A7.1 Event-Level Metrics & Delay Hand-Computed Verification
# -----------------------------------------------------------------------------

def test_a7_1_hand_computed_event_metrics() -> None:
    """A7.1: Verify event-level metrics and delay against hand-computed analytical cases."""
    # 10 hourly steps
    times = pd.date_range("2024-09-01 00:00:00", periods=10, freq="1h", tz="UTC")

    # Ground truth: 2 events
    # Event 1: steps 1, 2 (onset hour 1)
    # Event 2: steps 6, 7, 8 (onset hour 6)
    y_true = np.array([0, 1, 1, 0, 0, 0, 1, 1, 1, 0])

    # Predictions:
    # Event 1 detected at step 2 (delay = 1 hour = 3600 sec)
    # Step 4: False Positive alarm (outside any event -> 1 FP episode)
    # Event 2 detected at step 6 immediately (delay = 0 hours = 0 sec)
    y_pred = np.array([0, 0, 1, 0, 1, 0, 1, 1, 0, 0])

    ev_m = event_level_metrics(times, y_true, y_pred)

    assert ev_m["total_true_events"] == 2
    assert ev_m["detected_events"] == 2
    assert ev_m["missed_events"] == 0
    assert ev_m["false_positive_events"] == 1

    # Event Recall = 2 / 2 = 1.0
    assert ev_m["event_recall"] == pytest.approx(1.0, abs=1e-5)
    # Event Precision = 2 / (2 + 1) = 2/3 = 0.66667
    assert ev_m["event_precision"] == pytest.approx(2.0 / 3.0, abs=1e-5)
    # Event F1 = 2 * (1.0 * 2/3) / (1.0 + 2/3) = (4/3) / (5/3) = 4/5 = 0.80
    assert ev_m["event_f1"] == pytest.approx(0.80, abs=1e-5)

    # Delays: [3600.0, 0.0] -> mean = 1800.0s = 0.5h
    assert ev_m["mean_delay_seconds"] == pytest.approx(1800.0, abs=1e-5)
    assert ev_m["mean_delay_hours"] == pytest.approx(0.5, abs=1e-5)


def test_a7_1_operational_alert_metrics() -> None:
    """A7.1: Verify alerts_per_week, alerts_per_spend, PR-AUC, and presumed normal alert rate."""
    # 336 hours = exactly 2.0 weeks
    times = pd.date_range("2024-09-01 00:00:00", periods=336, freq="1h", tz="UTC")
    y_pred = np.zeros(336, dtype=int)
    y_pred[10:14] = 1  # 4 alerts total

    # 4 alerts / 2 weeks = 2.0 alerts/week
    assert alerts_per_week(y_pred, times) == pytest.approx(2.0, abs=1e-4)

    # Spend: $5,000 total spend -> 4 alerts / ($5000 / $1000) = 4 / 5 = 0.80 alerts per $1k
    costs = np.full(336, 5000.0 / 336.0)
    assert alerts_per_spend(y_pred, costs) == pytest.approx(0.80, abs=1e-4)

    # Presumed normal alert rate: 4 / 336
    assert presumed_normal_alert_rate(y_pred) == pytest.approx(4.0 / 336.0, abs=1e-5)

    # PR-AUC
    y_true = np.zeros(336, dtype=int)
    y_true[10:14] = 1
    scores = np.linspace(0.1, 0.9, 336)
    scores[10:14] = [0.85, 0.88, 0.92, 0.95]
    pr_auc = precision_recall_auc(y_true, scores)
    assert 0.0 < pr_auc <= 1.0


# -----------------------------------------------------------------------------
# A7.2 Materiality & Persistence Unit Tests
# -----------------------------------------------------------------------------

def test_a7_2_materiality_filtering() -> None:
    """A7.2: Verify materiality filter suppresses economically insignificant micro-spikes."""
    mat_filter = MaterialityFilter(min_dollar_exceedance=10.0, min_pct_exceedance=20.0)

    # Case 1: Micro-spike from $0.01 to $0.05
    # Delta = $0.04 (< $10), Pct = 400% (>= 20%) -> MUST BE SUPPRESSED
    raw_flags = np.array([1, 1])
    actuals = np.array([0.05, 100.0])
    expecteds = np.array([0.01, 50.0])

    # Case 2: Genuine spike from $50 to $100
    # Delta = $50 (>= $10), Pct = 100% (>= 20%) -> MUST BE ACCEPTED

    filtered = mat_filter.apply(raw_flags, actuals, expecteds)
    assert filtered[0] == 0, "Materiality violation: Micro-spike was not suppressed!"
    assert filtered[1] == 1, "Materiality violation: Genuine economic spike was suppressed!"


def test_a7_2_persistence_rule() -> None:
    """A7.2: Verify k-of-n persistence suppresses isolated 1h spikes and confirms 2h sustained."""
    rule = PersistenceRule(k=2, n=3)

    # Panel for 1 service over 6 hours
    df = pd.DataFrame(
        {
            "ServiceName": ["Compute"] * 6,
            "ChargePeriodStart": pd.date_range("2024-09-01", periods=6, freq="1h", tz="UTC"),
        }
    )

    # Flag pattern:
    # Hour 0: 0
    # Hour 1: 1 (isolated spike -> 1 of 3 -> rejected)
    # Hour 2: 0
    # Hour 3: 1
    # Hour 4: 1 (sustained 2nd hour -> 2 of 3 -> accepted!)
    # Hour 5: 0
    raw_flags = np.array([0, 1, 0, 1, 1, 0])

    persisted = rule.apply(df, raw_flags)

    assert persisted[1] == 0, "Persistence violation: Single isolated spike should be suppressed!"
    assert persisted[4] == 1, "Persistence violation: 2-of-3 sustained anomaly should be accepted!"


# -----------------------------------------------------------------------------
# A7.3 Primary Interval Detector & Sensitivity Presets
# -----------------------------------------------------------------------------

def test_a7_3_interval_detector_sensitivity_hierarchy() -> None:
    """A7.3: Verify High sensitivity yields >= alerts than Balanced, and Balanced >= Low."""
    times = pd.date_range("2024-09-01", periods=24, freq="1h", tz="UTC")
    df = pd.DataFrame(
        {
            "ServiceName": "Compute_EC2",
            "ChargePeriodStart": times,
            "EffectiveCost": [10.0] * 10 + [25.0, 30.0, 35.0] + [10.0] * 11,
            "EffectiveCost_expected": [10.0] * 24,
            "EffectiveCost_upper_bound": [15.0] * 24,
        }
    )

    det_low = ForecastIntervalExceedanceDetector(sensitivity="Low")
    det_bal = ForecastIntervalExceedanceDetector(sensitivity="Balanced")
    det_high = ForecastIntervalExceedanceDetector(sensitivity="High")

    det_low.fit(df)
    det_bal.fit(df)
    det_high.fit(df)

    flags_low = det_low.predict(df)
    flags_bal = det_bal.predict(df)
    flags_high = det_high.predict(df)

    count_low = np.sum(flags_low)
    count_bal = np.sum(flags_bal)
    count_high = np.sum(flags_high)

    assert count_high >= count_bal >= count_low, (
        f"Sensitivity ordering violation: High={count_high}, Bal={count_bal}, Low={count_low}"
    )


def test_a7_3_interval_detector_serialization() -> None:
    """A7.3: Verify save and load checkpointing for ForecastIntervalExceedanceDetector."""
    det = ForecastIntervalExceedanceDetector(sensitivity="Balanced")
    df = pd.DataFrame(
        {
            "ServiceName": "Compute",
            "ChargePeriodStart": pd.date_range("2024-09-01", periods=6, freq="1h", tz="UTC"),
            "EffectiveCost": [10.0, 20.0, 30.0, 10.0, 10.0, 10.0],
            "EffectiveCost_expected": [10.0] * 6,
            "EffectiveCost_upper_bound": [12.0] * 6,
        }
    )
    det.fit(df)
    orig_preds = det.predict(df)

    with tempfile.TemporaryDirectory() as tmpdir:
        save_path = Path(tmpdir) / "interval_det.joblib"
        det.save(save_path)
        assert save_path.exists()

        loaded_det = ForecastIntervalExceedanceDetector.load(save_path)
        loaded_preds = loaded_det.predict(df)
        np.testing.assert_array_equal(orig_preds, loaded_preds)


# -----------------------------------------------------------------------------
# A7.4 Severity Scoring & Tier Classification
# -----------------------------------------------------------------------------

def test_a7_4_severity_scoring() -> None:
    """A7.4: Verify multidimensional severity scoring maps to valid tiers."""
    scorer = SeverityScorer()

    # Low impact ($2 above expected, 1h duration)
    s_info, t_info = scorer.score_single(actual=12.0, expected=10.0, duration_hours=1)
    assert t_info in ("Info", "Low")
    assert 0.0 <= s_info <= 50.0

    # Catastrophic runaway ($500 above expected, 4h duration)
    s_high, t_high = scorer.score_single(actual=550.0, expected=50.0, duration_hours=4)
    assert t_high == "High"
    assert s_high >= 75.0


def test_a7_4_level_shift_detector() -> None:
    """A7.4: Verify LevelShiftDetector flags sustained mean shifts."""
    det = LevelShiftDetector(window=6, threshold=3.0)

    # 36 hours: first 18h at residual=0, next 18h jump to residual=15
    times = pd.date_range("2024-09-01", periods=36, freq="1h", tz="UTC")
    residuals = np.array([0.0] * 18 + [15.0] * 18)
    df = pd.DataFrame(
        {
            "ServiceName": "Compute",
            "ChargePeriodStart": times,
            "residual": residuals,
        }
    )
    det.fit(df)
    _ = det.score(df)
    flags = det.predict(df)

    # Level shift should be detected during the second window
    assert np.any(flags[18:] == 1), "LevelShiftDetector failed to detect sustained step shift!"
