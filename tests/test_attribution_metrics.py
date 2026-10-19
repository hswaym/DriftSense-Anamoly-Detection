"""Unit tests for cause attribution evaluation metrics."""

from __future__ import annotations

import pytest

from driftsense.eval.attribution_metrics import (
    evaluate_attribution_suite,
    multi_label_incident_metrics,
    taxonomy_confusion_matrix,
    top_1_accuracy,
    top_k_accuracy,
)


def test_hand_computed_top_k_accuracy() -> None:
    """Verify hand-computed Top-1, Top-2, and Top-3 ranking accuracy (A8.1)."""
    # 4 incidents
    y_true = [
        "DEPLOYMENT_DEFECT",
        "CONFIG_MODIFICATION",
        "EXTERNAL_TRAFFIC_SURGE",
        "RUNAWAY_BATCH_PROCESS",
    ]

    # Predictions
    # Incident 0: Rank 1 matches (Hit for Top-1, Top-2, Top-3)
    # Incident 1: Rank 2 matches (Hit for Top-2, Top-3, Miss for Top-1)
    # Incident 2: Rank 3 matches (Hit for Top-3, Miss for Top-1, Top-2)
    # Incident 3: Rank 4 matches (Miss for Top-1, Top-2, Top-3)
    ranked_preds = [
        ["DEPLOYMENT_DEFECT", "AUTOSCALING_OVERPROVISION", "CONFIG_MODIFICATION"],
        ["AUTOSCALING_OVERPROVISION", "CONFIG_MODIFICATION", "DEPLOYMENT_DEFECT"],
        ["AUTOSCALING_OVERPROVISION", "DEPLOYMENT_DEFECT", "EXTERNAL_TRAFFIC_SURGE"],
        [
            "AUTOSCALING_OVERPROVISION",
            "DEPLOYMENT_DEFECT",
            "CONFIG_MODIFICATION",
            "RUNAWAY_BATCH_PROCESS",
        ],
    ]

    # Top-1: 1 / 4 = 0.25
    assert top_1_accuracy(y_true, ranked_preds) == pytest.approx(0.25)
    # Top-2: 2 / 4 = 0.50
    assert top_k_accuracy(y_true, ranked_preds, k=2) == pytest.approx(0.50)
    # Top-3: 3 / 4 = 0.75
    assert top_k_accuracy(y_true, ranked_preds, k=3) == pytest.approx(0.75)


def test_multi_label_incident_metrics() -> None:
    """Verify multi-label precision, recall, and Jaccard similarity for cascades."""
    # Incident 0: True {DEPLOYMENT_DEFECT, AUTOSCALING_OVERPROVISION}, Pred {DEPLOYMENT_DEFECT, AUTOSCALING_OVERPROVISION}
    # Intersection = 2, Union = 2 -> P=1.0, R=1.0, J=1.0
    # Incident 1: True {CONFIG_MODIFICATION}, Pred {CONFIG_MODIFICATION, DEPLOYMENT_DEFECT}
    # Intersection = 1, Union = 2 -> P=0.5, R=1.0, J=0.5
    true_sets = [
        ["DEPLOYMENT_DEFECT", "AUTOSCALING_OVERPROVISION"],
        ["CONFIG_MODIFICATION"],
    ]
    pred_sets = [
        ["DEPLOYMENT_DEFECT", "AUTOSCALING_OVERPROVISION"],
        ["CONFIG_MODIFICATION", "DEPLOYMENT_DEFECT"],
    ]

    res = multi_label_incident_metrics(true_sets, pred_sets)
    assert res["precision"] == pytest.approx(0.75)  # (1.0 + 0.5) / 2
    assert res["recall"] == pytest.approx(1.0)  # (1.0 + 1.0) / 2
    assert res["jaccard"] == pytest.approx(0.75)  # (1.0 + 0.5) / 2


def test_taxonomy_confusion_matrix() -> None:
    """Verify confusion matrix computation across cause taxonomy classes."""
    classes = ["AUTOSCALING_OVERPROVISION", "CONFIG_MODIFICATION", "DEPLOYMENT_DEFECT"]
    y_true = ["DEPLOYMENT_DEFECT", "DEPLOYMENT_DEFECT", "CONFIG_MODIFICATION"]
    y_pred = ["DEPLOYMENT_DEFECT", "AUTOSCALING_OVERPROVISION", "CONFIG_MODIFICATION"]

    cm = taxonomy_confusion_matrix(y_true, y_pred, classes=classes)
    assert cm["classes"] == classes
    # DEPLOYMENT_DEFECT: 1 correct, 1 confused with AUTOSCALING_OVERPROVISION -> recall = 0.5
    assert cm["per_class_recall"]["DEPLOYMENT_DEFECT"] == pytest.approx(0.5)
    # CONFIG_MODIFICATION: 1 correct out of 1 -> recall = 1.0
    assert cm["per_class_recall"]["CONFIG_MODIFICATION"] == pytest.approx(1.0)


def test_evaluate_attribution_suite() -> None:
    """Verify full evaluation suite aggregation."""
    y_true = ["DEPLOYMENT_DEFECT", "CONFIG_MODIFICATION"]
    preds = [
        ["DEPLOYMENT_DEFECT", "CONFIG_MODIFICATION"],
        ["CONFIG_MODIFICATION", "DEPLOYMENT_DEFECT"],
    ]
    suite = evaluate_attribution_suite(
        y_true, preds, true_all_causes=[["DEPLOYMENT_DEFECT"], ["CONFIG_MODIFICATION"]]
    )
    assert suite["top_1_accuracy"] == pytest.approx(1.0)
    assert suite["top_2_accuracy"] == pytest.approx(1.0)
    assert suite["top_3_accuracy"] == pytest.approx(1.0)
    assert "multi_label_top3" in suite
