"""Attribution evaluation metrics for DriftSense.

Implements ranking accuracy, multi-label alignment, and confusion metrics:
- Top-1 Accuracy: True cause is ranked as rank-1 prediction.
- Top-k Accuracy (Top-3): True cause appears in top-k predictions.
- Multi-label metrics: Precision, Recall, and Jaccard similarity for multi-cause incidents.
- Taxonomy-stratified accuracy and confusion matrix.
"""

from __future__ import annotations

import logging
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)


def top_k_accuracy(
    y_true: list[str] | np.ndarray,
    ranked_preds: list[list[str]],
    k: int = 1,
) -> float:
    """Compute Top-k accuracy.

    Fraction of incidents where the true primary cause is in the top-k ranked predictions.

    Args:
        y_true: List of ground-truth primary cause strings.
        ranked_preds: List of ranked cause prediction lists.
        k: Cutoff rank (e.g., 1 for Top-1, 3 for Top-3).
    """
    if len(y_true) == 0:
        return 0.0

    hits = 0
    for true_cause, preds in zip(y_true, ranked_preds):
        top_slice = preds[:k]
        if true_cause in top_slice:
            hits += 1

    return float(hits / len(y_true))


def top_1_accuracy(
    y_true: list[str] | np.ndarray,
    ranked_preds: list[list[str]],
) -> float:
    """Compute Top-1 accuracy."""
    return top_k_accuracy(y_true, ranked_preds, k=1)


def multi_label_incident_metrics(
    true_causes_list: list[list[str]],
    predicted_top_k_list: list[list[str]],
) -> dict[str, float]:
    """Compute multi-label precision, recall, and Jaccard similarity.

    Used when incidents have primary and contributing causes (e.g., multi-cause cascades).
    """
    if len(true_causes_list) == 0:
        return {"precision": 0.0, "recall": 0.0, "jaccard": 0.0}

    precisions = []
    recalls = []
    jaccards = []

    for true_set_raw, pred_slice in zip(true_causes_list, predicted_top_k_list):
        true_set = set(true_set_raw)
        pred_set = set(pred_slice)

        intersection = len(true_set & pred_set)
        union = len(true_set | pred_set)

        p = float(intersection / len(pred_set)) if len(pred_set) > 0 else 0.0
        r = float(intersection / len(true_set)) if len(true_set) > 0 else 0.0
        j = float(intersection / union) if union > 0 else 0.0

        precisions.append(p)
        recalls.append(r)
        jaccards.append(j)

    return {
        "precision": float(np.mean(precisions)),
        "recall": float(np.mean(recalls)),
        "jaccard": float(np.mean(jaccards)),
    }


def taxonomy_confusion_matrix(
    y_true: list[str],
    y_pred_top1: list[str],
    classes: list[str] | None = None,
) -> dict[str, Any]:
    """Compute confusion matrix across cause taxonomy classes."""
    if classes is None:
        classes = sorted(set(y_true) | set(y_pred_top1))

    idx_map = {c: i for i, c in enumerate(classes)}
    matrix = np.zeros((len(classes), len(classes)), dtype=int)

    for yt, yp in zip(y_true, y_pred_top1):
        if yt in idx_map and yp in idx_map:
            matrix[idx_map[yt], idx_map[yp]] += 1

    per_class_recall = {}
    for c, i in idx_map.items():
        total_true = int(np.sum(matrix[i, :]))
        correct = int(matrix[i, i])
        per_class_recall[c] = float(correct / total_true) if total_true > 0 else 0.0

    return {
        "classes": classes,
        "matrix": matrix.tolist(),
        "per_class_recall": per_class_recall,
    }


def evaluate_attribution_suite(
    y_true_primary: list[str],
    ranked_predictions: list[list[str]],
    true_all_causes: list[list[str]] | None = None,
    classes: list[str] | None = None,
) -> dict[str, Any]:
    """Evaluate full suite of cause attribution metrics."""
    top1 = top_1_accuracy(y_true_primary, ranked_predictions)
    top2 = top_k_accuracy(y_true_primary, ranked_predictions, k=2)
    top3 = top_k_accuracy(y_true_primary, ranked_predictions, k=3)

    pred_top1 = [p[0] if len(p) > 0 else "UNKNOWN" for p in ranked_predictions]
    cm = taxonomy_confusion_matrix(y_true_primary, pred_top1, classes=classes)

    res: dict[str, Any] = {
        "top_1_accuracy": top1,
        "top_2_accuracy": top2,
        "top_3_accuracy": top3,
        "total_evaluated_incidents": len(y_true_primary),
        "confusion_matrix": cm,
    }

    if true_all_causes is not None:
        top3_preds = [p[:3] for p in ranked_predictions]
        ml_metrics = multi_label_incident_metrics(true_all_causes, top3_preds)
        res["multi_label_top3"] = ml_metrics

    return res
