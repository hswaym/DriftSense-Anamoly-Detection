"""Unit tests for point-level, event-level, and delay detection metrics."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from driftsense.eval.detection_metrics import (
    event_level_metrics,
    false_positive_rate,
    point_confusion_matrix,
    point_f1_score,
    point_level_metrics,
    point_precision,
    point_recall,
    stratified_fp_analysis,
)


def test_hand_computed_point_level_metrics() -> None:
    """Verify hand-computed point-level metrics: Precision, Recall, F1, FPR."""
    # Ground truth: 2 anomalies, 3 normals
    y_true = np.array([0, 0, 1, 1, 0])
    # Predictions: flags point 1 (FP), point 2 (TP), misses point 3 (FN)
    y_pred = np.array([0, 1, 1, 0, 0])

    cm = point_confusion_matrix(y_true, y_pred)
    assert cm["tp"] == 1
    assert cm["fp"] == 1
    assert cm["fn"] == 1
    assert cm["tn"] == 2

    # Precision = 1 / (1 + 1) = 0.5
    assert point_precision(y_true, y_pred) == pytest.approx(0.5)
    # Recall = 1 / (1 + 1) = 0.5
    assert point_recall(y_true, y_pred) == pytest.approx(0.5)
    # F1 = 2 * (0.5 * 0.5) / (0.5 + 0.5) = 0.5
    assert point_f1_score(y_true, y_pred) == pytest.approx(0.5)
    # FPR = FP / (FP + TN) = 1 / (1 + 2) = 1/3
    assert false_positive_rate(y_true, y_pred) == pytest.approx(1.0 / 3.0)

    summary = point_level_metrics(y_true, y_pred)
    assert summary["specificity"] == pytest.approx(2.0 / 3.0)
    assert summary["total_samples"] == 5


def test_hand_computed_event_level_and_delay_metrics() -> None:
    """Verify hand-computed event-level metrics and temporal detection delay (A7.1)."""
    # 10 hourly points from 00:00 to 09:00
    timestamps = pd.date_range("2024-09-01 00:00:00", periods=10, freq="h", tz="UTC")

    # Ground truth events:
    # Event A: indices 2, 3, 4 (starts at 02:00, ends at 04:00)
    # Event B: indices 7, 8 (starts at 07:00, ends at 08:00)
    y_true = np.array([0, 0, 1, 1, 1, 0, 0, 1, 1, 0])

    # Predictions:
    # Index 3: inside Event A (first alert at 03:00 -> delay = 1 hour / 3600s)
    # Index 4: inside Event A (subsequent alert, delay still measured from onset)
    # Index 5: outside all events (False Positive Episode 1)
    # Index 7, 8: no alerts (Event B is missed)
    y_pred = np.array([0, 0, 0, 1, 1, 1, 0, 0, 0, 0])

    res = event_level_metrics(timestamps, y_true, y_pred)

    assert res["total_true_events"] == 2
    assert res["detected_events"] == 1
    assert res["missed_events"] == 1
    assert res["false_positive_events"] == 1

    # Event Recall = 1 / 2 = 0.5
    assert res["event_recall"] == pytest.approx(0.5)
    # Event Precision = 1 / (1 detected + 1 fp) = 0.5
    assert res["event_precision"] == pytest.approx(0.5)
    # Event F1 = 0.5
    assert res["event_f1"] == pytest.approx(0.5)

    # Delay: 03:00 - 02:00 = 3600 seconds (1.0 hour)
    assert res["mean_delay_seconds"] == pytest.approx(3600.0)
    assert res["mean_delay_hours"] == pytest.approx(1.0)
    assert res["median_delay_hours"] == pytest.approx(1.0)


def test_event_level_immediate_detection() -> None:
    """Verify delay is zero when detector alerts at the very first point of an event."""
    timestamps = pd.date_range("2024-09-01 00:00:00", periods=5, freq="h", tz="UTC")
    y_true = np.array([0, 1, 1, 0, 0])
    y_pred = np.array([0, 1, 0, 0, 0])

    res = event_level_metrics(timestamps, y_true, y_pred)
    assert res["detected_events"] == 1
    assert res["mean_delay_seconds"] == pytest.approx(0.0)
    assert res["mean_delay_hours"] == pytest.approx(0.0)


def test_stratified_false_positive_analysis() -> None:
    """Verify false positive rate breakdown between weekday and weekend regimes."""
    df = pd.DataFrame(
        {
            "y_true": [0, 0, 0, 0, 0, 0],
            "y_pred": [0, 1, 0, 0, 0, 1],  # 2 FPs
            "is_weekend": [0, 0, 0, 1, 1, 1],  # 3 weekday, 3 weekend
        }
    )

    res = stratified_fp_analysis(df, y_true_col="y_true", y_pred_col="y_pred")
    assert res["total_normal_points"] == 6
    assert res["total_false_positives"] == 2
    assert res["overall_fpr"] == pytest.approx(2.0 / 6.0)

    # Weekday: 1 FP out of 3 -> FPR = 1/3
    assert res["weekday_normal_points"] == 3
    assert res["weekday_false_positives"] == 1
    assert res["weekday_fpr"] == pytest.approx(1.0 / 3.0)

    # Weekend: 1 FP out of 3 -> FPR = 1/3
    assert res["weekend_normal_points"] == 3
    assert res["weekend_false_positives"] == 1
    assert res["weekend_fpr"] == pytest.approx(1.0 / 3.0)
