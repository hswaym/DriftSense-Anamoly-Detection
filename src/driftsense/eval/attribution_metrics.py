"""Attribution evaluation metrics for DriftSense v2.

Implements ranking accuracy, calibration error, abstention coverage, and multi-label metrics:
- Top-1 and Top-k Accuracy (Top-3)
- Mean Reciprocal Rank (MRR)
- Per-class Precision, Recall, and F1 (with macro-F1)
- Expected Calibration Error (ECE)
- Selective Classification / Abstention Metrics (Coverage, Non-abstained Accuracy)
- Multi-label metrics: Precision, Recall, and Jaccard similarity for multi-cause incidents
- Taxonomy-stratified confusion matrix
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


def mean_reciprocal_rank(
    y_true: list[str] | np.ndarray,
    ranked_preds: list[list[str]],
) -> float:
    """Compute Mean Reciprocal Rank (MRR) across incidents."""
    if len(y_true) == 0:
        return 0.0

    reciprocal_ranks = []
    for true_c, preds in zip(y_true, ranked_preds):
        if true_c in preds:
            rank = preds.index(true_c) + 1
            reciprocal_ranks.append(1.0 / rank)
        else:
            reciprocal_ranks.append(0.0)

    return float(np.mean(reciprocal_ranks))


def multi_label_incident_metrics(
    true_causes_list: list[list[str]],
    predicted_top_k_list: list[list[str]],
) -> dict[str, float]:
    """Compute multi-label precision, recall, and Jaccard similarity for multi-cause cascades."""
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


def per_class_f1_scores(
    y_true: list[str],
    y_pred_top1: list[str],
    classes: list[str] | None = None,
) -> dict[str, Any]:
    """Compute per-class precision, recall, and F1, along with unweighted macro-F1."""
    if classes is None:
        classes = sorted(set(y_true) | set(y_pred_top1))

    per_class = {}
    f1_list = []

    for c in classes:
        tp = sum(1 for yt, yp in zip(y_true, y_pred_top1) if yt == c and yp == c)
        fp = sum(1 for yt, yp in zip(y_true, y_pred_top1) if yt != c and yp == c)
        fn = sum(1 for yt, yp in zip(y_true, y_pred_top1) if yt == c and yp != c)

        prec = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        rec = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = (2 * prec * rec) / (prec + rec) if (prec + rec) > 0 else 0.0

        per_class[c] = {
            "precision": float(prec),
            "recall": float(rec),
            "f1": float(f1),
            "support": sum(1 for yt in y_true if yt == c),
        }
        f1_list.append(f1)

    macro_f1 = float(np.mean(f1_list)) if f1_list else 0.0
    return {
        "per_class": per_class,
        "macro_f1": macro_f1,
    }


def expected_calibration_error(
    y_true: list[str],
    y_pred_top1: list[str],
    confidences: list[float] | np.ndarray,
    n_bins: int = 10,
) -> float:
    """Compute Expected Calibration Error (ECE) for predicted probabilities."""
    if len(y_true) == 0 or len(confidences) == 0:
        return 0.0

    confidences_arr = np.clip(np.array(confidences, dtype=float), 0.0, 1.0)
    accuracies = np.array([1.0 if yt == yp else 0.0 for yt, yp in zip(y_true, y_pred_top1)])

    bin_boundaries = np.linspace(0.0, 1.0, n_bins + 1)
    ece = 0.0
    total_samples = len(accuracies)

    for i in range(n_bins):
        bin_lower = bin_boundaries[i]
        bin_upper = bin_boundaries[i + 1]

        if i == n_bins - 1:
            in_bin = (confidences_arr >= bin_lower) & (confidences_arr <= bin_upper)
        else:
            in_bin = (confidences_arr >= bin_lower) & (confidences_arr < bin_upper)

        prop_in_bin = np.mean(in_bin)
        if prop_in_bin > 0:
            avg_acc = np.mean(accuracies[in_bin])
            avg_conf = np.mean(confidences_arr[in_bin])
            ece += np.abs(avg_acc - avg_conf) * (np.sum(in_bin) / total_samples)

    return float(ece)


def abstention_metrics(
    y_true: list[str],
    y_pred_top1: list[str],
    is_abstained: list[bool],
) -> dict[str, float]:
    """Compute selective classification metrics under abstention."""
    total = len(y_true)
    if total == 0:
        return {
            "abstention_rate": 0.0,
            "coverage": 0.0,
            "non_abstained_accuracy": 0.0,
            "overall_accuracy": 0.0,
        }

    n_abstained = sum(1 for a in is_abstained if a)
    abstention_rate = float(n_abstained / total)
    coverage = float(1.0 - abstention_rate)

    # Evaluate accuracy on covered subset
    covered_hits = 0
    covered_total = 0
    total_hits = 0

    for yt, yp, abst in zip(y_true, y_pred_top1, is_abstained):
        is_hit = (yt == yp)
        if is_hit:
            total_hits += 1
        if not abst:
            covered_total += 1
            if is_hit:
                covered_hits += 1

    non_abstained_acc = float(covered_hits / covered_total) if covered_total > 0 else 0.0
    overall_acc = float(total_hits / total)

    return {
        "abstention_rate": abstention_rate,
        "coverage": coverage,
        "non_abstained_accuracy": non_abstained_acc,
        "overall_accuracy": overall_acc,
    }


def taxonomy_confusion_matrix(
    y_true: list[str],
    y_pred_top1: list[str],
    classes: list[str] | None = None,
) -> dict[str, Any]:
    """Compute confusion matrix across cause taxonomy classes."""
    # If passed top-k ranked predictions, extract top-1
    if y_pred_top1 and isinstance(y_pred_top1[0], (list, tuple)):
        top1_flat = [p[0] if len(p) > 0 else "" for p in y_pred_top1]
    else:
        top1_flat = list(y_pred_top1)

    if classes is None:
        classes = sorted(set(y_true) | set(top1_flat))

    idx_map = {c: i for i, c in enumerate(classes)}
    matrix = np.zeros((len(classes), len(classes)), dtype=int)

    for yt, yp in zip(y_true, top1_flat):
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


compute_taxonomy_confusion_matrix = taxonomy_confusion_matrix


def evaluate_attribution_suite(
    y_true_primary: list[str],
    ranked_predictions: list[list[str]],
    true_all_causes: list[list[str]] | None = None,
    confidences: list[float] | None = None,
    is_abstained: list[bool] | None = None,
    classes: list[str] | None = None,
) -> dict[str, Any]:
    """Evaluate full suite of cause attribution metrics."""
    top1 = top_1_accuracy(y_true_primary, ranked_predictions)
    top2 = top_k_accuracy(y_true_primary, ranked_predictions, k=2)
    top3 = top_k_accuracy(y_true_primary, ranked_predictions, k=3)
    mrr = mean_reciprocal_rank(y_true_primary, ranked_predictions)

    pred_top1 = [p[0] if len(p) > 0 else "UNKNOWN" for p in ranked_predictions]
    cm = taxonomy_confusion_matrix(y_true_primary, pred_top1, classes=classes)
    f1_report = per_class_f1_scores(y_true_primary, pred_top1, classes=classes)

    res: dict[str, Any] = {
        "top_1_accuracy": top1,
        "top_2_accuracy": top2,
        "top_3_accuracy": top3,
        "mrr": mrr,
        "macro_f1": f1_report["macro_f1"],
        "per_class_f1": f1_report["per_class"],
        "total_evaluated_incidents": len(y_true_primary),
        "confusion_matrix": cm,
    }

    if confidences is not None:
        ece = expected_calibration_error(y_true_primary, pred_top1, confidences)
        res["expected_calibration_error"] = ece

    if is_abstained is not None:
        abst_metrics = abstention_metrics(y_true_primary, pred_top1, is_abstained)
        res["abstention"] = abst_metrics

    if true_all_causes is not None:
        top3_preds = [p[:3] for p in ranked_predictions]
        ml_metrics = multi_label_incident_metrics(true_all_causes, top3_preds)
        res["multi_label_top3"] = ml_metrics

    return res
