"""Anomaly detection evaluation metrics for DriftSense v2.

Implements point-level, event-level, operational alert rate, and temporal latency metrics:
- Point-level: Precision, Recall, F1-Score, PR-AUC, Specificity.
- Event-level: True Positive Events, False Positive Events, Event-F1.
- Detection latency: Delay from event onset to first triggered alert.
- Operational metrics: Alerts per week, alerts per $1k of spend.
- Presumed-normal alert rate: Alert frequency during presumed clean/seasonal intervals.
"""

from __future__ import annotations

import logging
from typing import Any

import numpy as np
import pandas as pd
from sklearn.metrics import auc, precision_recall_curve

logger = logging.getLogger(__name__)


def point_confusion_matrix(y_true: np.ndarray, y_pred: np.ndarray) -> dict[str, int]:
    """Compute point-level confusion matrix components (TP, FP, TN, FN)."""
    yt = np.asarray(y_true, dtype=int)
    yp = np.asarray(y_pred, dtype=int)

    tp = int(np.sum((yt == 1) & (yp == 1)))
    fp = int(np.sum((yt == 0) & (yp == 1)))
    tn = int(np.sum((yt == 0) & (yp == 0)))
    fn = int(np.sum((yt == 1) & (yp == 0)))

    return {"tp": tp, "fp": fp, "tn": tn, "fn": fn}


def point_precision(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    """Compute point-level Precision: TP / (TP + FP)."""
    cm = point_confusion_matrix(y_true, y_pred)
    denom = cm["tp"] + cm["fp"]
    return float(cm["tp"] / denom) if denom > 0 else 0.0


def point_recall(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    """Compute point-level Recall: TP / (TP + FN)."""
    cm = point_confusion_matrix(y_true, y_pred)
    denom = cm["tp"] + cm["fn"]
    return float(cm["tp"] / denom) if denom > 0 else 0.0


def point_f1_score(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    """Compute point-level F1-Score: 2 * P * R / (P + R)."""
    p = point_precision(y_true, y_pred)
    r = point_recall(y_true, y_pred)
    return float(2.0 * p * r / (p + r)) if (p + r) > 0 else 0.0


def precision_recall_auc(y_true: np.ndarray, scores: np.ndarray) -> float:
    """Compute Area Under the Precision-Recall Curve (PR-AUC)."""
    yt = np.asarray(y_true, dtype=int)
    sc = np.asarray(scores, dtype=float)
    if np.sum(yt == 1) == 0:
        return 0.0
    precisions, recalls, _ = precision_recall_curve(yt, sc)
    return float(auc(recalls, precisions))


def false_positive_rate(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    """Compute False Positive Rate (FPR): FP / (FP + TN)."""
    cm = point_confusion_matrix(y_true, y_pred)
    denom = cm["fp"] + cm["tn"]
    return float(cm["fp"] / denom) if denom > 0 else 0.0


def alerts_per_week(
    y_pred: np.ndarray,
    timestamps: list[Any] | pd.Series | np.ndarray,
) -> float:
    """Compute normalized alert frequency per 168 hours of monitored timeline."""
    ts = pd.to_datetime(timestamps, utc=True)
    if len(ts) < 2:
        return float(np.sum(y_pred == 1))

    total_hours = float(len(ts))
    total_alerts = float(np.sum(y_pred == 1))
    weeks = total_hours / 168.0
    return float(total_alerts / weeks) if weeks > 0 else total_alerts


def alerts_per_spend(
    y_pred: np.ndarray,
    actual_costs: np.ndarray,
    unit_dollars: float = 1000.0,
    eps: float = 1e-4,
) -> float:
    """Compute alert rate per unit dollars of monitored spend (default per $1,000)."""
    yp = np.asarray(y_pred, dtype=int)
    costs = np.asarray(actual_costs, dtype=float)

    total_alerts = float(np.sum(yp == 1))
    total_spend = float(np.sum(costs))
    spend_units = (total_spend + eps) / unit_dollars
    return float(total_alerts / spend_units)


def presumed_normal_alert_rate(y_pred: np.ndarray) -> float:
    """Compute alert rate over presumed normal periods (fraction of steps flagged).

    Reported explicitly as 'alert rate on presumed-normal data', NOT as FPR.
    """
    yp = np.asarray(y_pred, dtype=int)
    if len(yp) == 0:
        return 0.0
    return float(np.mean(yp == 1))


def point_level_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> dict[str, float]:
    """Compute comprehensive point-level classification metrics."""
    cm = point_confusion_matrix(y_true, y_pred)
    p = point_precision(y_true, y_pred)
    r = point_recall(y_true, y_pred)
    f1 = point_f1_score(y_true, y_pred)
    fpr = false_positive_rate(y_true, y_pred)
    specificity = (
        float(cm["tn"] / (cm["tn"] + cm["fp"])) if (cm["tn"] + cm["fp"]) > 0 else 0.0
    )

    return {
        "precision": p,
        "recall": r,
        "f1": f1,
        "fpr": fpr,
        "specificity": specificity,
        "tp": cm["tp"],
        "fp": cm["fp"],
        "tn": cm["tn"],
        "fn": cm["fn"],
        "total_samples": len(y_true),
    }


def event_level_metrics(
    timestamps: list[Any] | pd.Series | np.ndarray,
    y_true: np.ndarray,
    y_pred: np.ndarray,
) -> dict[str, Any]:
    """Compute event-level (window-based) anomaly detection metrics and detection delay."""
    ts = pd.to_datetime(timestamps, utc=True)
    yt = np.asarray(y_true, dtype=int)
    yp = np.asarray(y_pred, dtype=int)

    # Identify contiguous ground truth event windows
    events: list[dict[str, Any]] = []
    in_event = False
    start_idx = 0

    for i in range(len(yt)):
        if yt[i] == 1 and not in_event:
            in_event = True
            start_idx = i
        elif yt[i] == 0 and in_event:
            in_event = False
            events.append(
                {
                    "start_idx": start_idx,
                    "end_idx": i - 1,
                    "start_time": ts[start_idx],
                    "end_time": ts[i - 1],
                }
            )
    if in_event:
        events.append(
            {
                "start_idx": start_idx,
                "end_idx": len(yt) - 1,
                "start_time": ts[start_idx],
                "end_time": ts[len(yt) - 1],
            }
        )

    # Evaluate each ground truth event
    detected_events = 0
    delays_seconds: list[float] = []

    for ev in events:
        s_idx, e_idx = ev["start_idx"], ev["end_idx"]
        ev_preds = yp[s_idx : e_idx + 1]
        if np.any(ev_preds == 1):
            detected_events += 1
            first_alarm_rel_idx = int(np.argmax(ev_preds == 1))
            first_alarm_idx = s_idx + first_alarm_rel_idx
            delay = (ts[first_alarm_idx] - ev["start_time"]).total_seconds()
            delays_seconds.append(max(0.0, float(delay)))

    total_true_events = len(events)
    fn_events = total_true_events - detected_events
    event_recall = (
        float(detected_events / total_true_events) if total_true_events > 0 else 1.0
    )

    outside_mask = (yt == 0) & (yp == 1)
    fp_episodes = 0
    in_fp = False
    for i in range(len(outside_mask)):
        if outside_mask[i] and not in_fp:
            in_fp = True
            fp_episodes += 1
        elif not outside_mask[i] and in_fp:
            in_fp = False

    event_denom = detected_events + fp_episodes
    event_precision = (
        float(detected_events / event_denom)
        if event_denom > 0
        else (1.0 if total_true_events == 0 else 0.0)
    )
    event_f1 = (
        float(2.0 * event_precision * event_recall / (event_precision + event_recall))
        if (event_precision + event_recall) > 0
        else 0.0
    )

    mean_delay_sec = float(np.mean(delays_seconds)) if delays_seconds else 0.0
    median_delay_sec = float(np.median(delays_seconds)) if delays_seconds else 0.0

    return {
        "total_true_events": total_true_events,
        "detected_events": detected_events,
        "missed_events": fn_events,
        "false_positive_events": fp_episodes,
        "event_precision": event_precision,
        "event_recall": event_recall,
        "event_f1": event_f1,
        "mean_delay_seconds": mean_delay_sec,
        "mean_delay_hours": mean_delay_sec / 3600.0,
        "median_delay_seconds": median_delay_sec,
        "median_delay_hours": median_delay_sec / 3600.0,
        "event_delays_seconds": delays_seconds,
    }


def stratified_fp_analysis(
    df: pd.DataFrame,
    y_true_col: str,
    y_pred_col: str,
    is_weekend_col: str = "is_weekend",
    hour_col: str = "hour_of_day",
) -> dict[str, Any]:
    """Analyze False Positive distributions across normal seasonality vs shift regimes."""
    df_eval = df.copy()
    yt = df_eval[y_true_col].to_numpy(dtype=int)
    yp = df_eval[y_pred_col].to_numpy(dtype=int)

    normal_mask = yt == 0
    total_normal = int(np.sum(normal_mask))

    if total_normal == 0:
        return {"total_normal_points": 0, "overall_fpr": 0.0}

    overall_fp = int(np.sum(normal_mask & (yp == 1)))
    overall_fpr = float(overall_fp / total_normal)

    report: dict[str, Any] = {
        "total_normal_points": total_normal,
        "total_false_positives": overall_fp,
        "overall_fpr": overall_fpr,
    }

    if is_weekend_col in df_eval.columns:
        weekend_mask = normal_mask & (df_eval[is_weekend_col] == 1)
        weekday_mask = normal_mask & (df_eval[is_weekend_col] == 0)

        n_weekend = int(np.sum(weekend_mask))
        fp_weekend = int(np.sum(weekend_mask & (yp == 1)))
        fpr_weekend = float(fp_weekend / n_weekend) if n_weekend > 0 else 0.0

        n_weekday = int(np.sum(weekday_mask))
        fp_weekday = int(np.sum(weekday_mask & (yp == 1)))
        fpr_weekday = float(fp_weekday / n_weekday) if n_weekday > 0 else 0.0

        report["weekday_normal_points"] = n_weekday
        report["weekday_false_positives"] = fp_weekday
        report["weekday_fpr"] = fpr_weekday

        report["weekend_normal_points"] = n_weekend
        report["weekend_false_positives"] = fp_weekend
        report["weekend_fpr"] = fpr_weekend

    return report
