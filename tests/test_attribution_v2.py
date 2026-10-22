"""Unit and integration tests for DriftSense Attribution v2 (Phase 8).

Validates:
- A8.1: Price-Volume-Mix decomposition identity (Volume + Price + Mix == ΔCost within tolerance)
- A8.2: Attribution metric suite tests against hand-computed expected cases
- A8.3: Selective classification and abstention on pure-noise and ambiguous cases
- A8.4: Label isolation invariant (labels never contaminate feature extraction or test sets)
- Layer 1 (Driver decomposition), Layer 2 (Event proximity kernel), and Layer 5 (Evidence objects)
"""

from __future__ import annotations

import pandas as pd
import pytest

from driftsense.attribute.abstain import (
    AbstentionConfig,
    ConfidenceCalibrator,
)
from driftsense.attribute.decompose import DriverDecomposer
from driftsense.attribute.dimension_rank import DimensionRanker
from driftsense.attribute.events_kernel import EventEvidenceMatcher, EventKernelConfig
from driftsense.attribute.price_volume_mix import PriceVolumeMixDecomposer
from driftsense.attribute.ranker import MultiLayerAttributor
from driftsense.eval.attribution_metrics import (
    abstention_metrics,
    evaluate_attribution_suite,
    expected_calibration_error,
    mean_reciprocal_rank,
    per_class_f1_scores,
    top_1_accuracy,
    top_k_accuracy,
)

# =========================================================================
# A8.1: Price-Volume-Mix Mathematical Identity Tests
# =========================================================================

def test_price_volume_mix_identity_single_item():
    """Verify that Volume + Price + Mix exactly equals ΔCost for single items."""
    decomposer = PriceVolumeMixDecomposer(tolerance=1e-5)

    # Case 1: Both price and volume increase
    # Baseline: Q0 = 100, C0 = $500 -> P0 = $5/unit
    # Actual:   Q1 = 150, C1 = $1050 -> P1 = $7/unit
    # ΔC = 1050 - 500 = $550
    # Volume Effect = ΔQ * P0 = (150 - 100) * 5 = $250
    # Price Effect  = ΔP * Q0 = (7 - 5) * 100   = $200
    # Mix Effect    = ΔP * ΔQ = (7 - 5) * (150 - 100) = $100
    # Sum: 250 + 200 + 100 = $550.
    res = decomposer.decompose_values(
        baseline_cost=500.0,
        baseline_quantity=100.0,
        actual_cost=1050.0,
        actual_quantity=150.0,
        item_id="EC2_Compute",
    )

    assert res.identity_holds is True
    assert pytest.approx(res.total_delta_cost, rel=1e-5) == 550.0
    assert pytest.approx(res.volume_effect, rel=1e-5) == 250.0
    assert pytest.approx(res.price_effect, rel=1e-5) == 200.0
    assert pytest.approx(res.mix_effect, rel=1e-5) == 100.0
    assert pytest.approx(res.volume_effect + res.price_effect + res.mix_effect, rel=1e-5) == res.total_delta_cost
    assert res.discrepancy <= 1e-5


def test_price_volume_mix_multi_item_dataframe():
    """Verify aggregate identity holds across multi-item dataframes."""
    decomposer = PriceVolumeMixDecomposer(tolerance=1e-4)

    baseline_data = pd.DataFrame([
        {"ServiceName": "AmazonEC2", "BilledCost": 1000.0, "ConsumedQuantity": 200.0},
        {"ServiceName": "AmazonS3", "BilledCost": 300.0, "ConsumedQuantity": 3000.0},
        {"ServiceName": "AmazonRDS", "BilledCost": 500.0, "ConsumedQuantity": 50.0},
    ])

    actual_data = pd.DataFrame([
        {"ServiceName": "AmazonEC2", "BilledCost": 1800.0, "ConsumedQuantity": 300.0},  # +800
        {"ServiceName": "AmazonS3", "BilledCost": 450.0, "ConsumedQuantity": 4500.0},   # +150
        {"ServiceName": "AmazonRDS", "BilledCost": 600.0, "ConsumedQuantity": 50.0},    # +100
        {"ServiceName": "AmazonDynamoDB", "BilledCost": 150.0, "ConsumedQuantity": 15.0}, # New item (+150)
    ])

    res = decomposer.decompose(
        baseline_df=baseline_data,
        actual_df=actual_data,
        cost_col="BilledCost",
        quantity_col="ConsumedQuantity",
        item_col="ServiceName",
    )

    # Expected total delta: (1800 + 450 + 600 + 150) - (1000 + 300 + 500) = 3000 - 1800 = 1200
    assert pytest.approx(res.total_delta_cost, rel=1e-4) == 1200.0
    assert res.identity_holds is True
    reconstructed = res.volume_effect + res.price_effect + res.mix_effect
    assert pytest.approx(reconstructed, rel=1e-4) == 1200.0
    assert len(res.item_breakdowns) == 4


# =========================================================================
# Driver Decomposition & Dimension Ranking Tests
# =========================================================================

def test_dimension_ranker_and_driver_decomposer():
    """Verify multi-dimensional driver ranking and explanatory power."""
    baseline = pd.DataFrame({
        "ServiceName": ["AmazonEC2", "AmazonEC2", "AmazonS3"],
        "RegionId": ["us-east-1", "us-west-2", "us-east-1"],
        "SubAccountId": ["acc-1", "acc-1", "acc-2"],
        "BilledCost": [100.0, 100.0, 50.0],
        "ConsumedQuantity": [20.0, 20.0, 500.0],
    })

    actual = pd.DataFrame({
        "ServiceName": ["AmazonEC2", "AmazonEC2", "AmazonS3"],
        "RegionId": ["us-east-1", "us-west-2", "us-east-1"],
        "SubAccountId": ["acc-1", "acc-1", "acc-2"],
        "BilledCost": [400.0, 100.0, 50.0],  # us-east-1 EC2 jumped +300
        "ConsumedQuantity": [80.0, 20.0, 500.0],
    })

    ranker = DimensionRanker(cost_col="BilledCost")
    ranks = ranker.rank_all_dimensions(baseline, actual)

    assert "ServiceName" in ranks
    assert "RegionId" in ranks

    # Top service should be AmazonEC2
    top_svc = ranks["ServiceName"][0]
    assert top_svc.key == "AmazonEC2"
    assert pytest.approx(top_svc.delta_cost) == 300.0
    assert pytest.approx(top_svc.percentage_share) == 1.0

    # Top region should be us-east-1
    top_reg = ranks["RegionId"][0]
    assert top_reg.key == "us-east-1"
    assert pytest.approx(top_reg.delta_cost) == 300.0

    # Test driver decomposer integration
    decomposer = DriverDecomposer()
    reasons = decomposer.infer_billing_reasons(baseline, actual)
    assert len(reasons) > 0
    # Inferred reasons must have supporting evidence objects
    assert len(reasons[0].supporting_evidence) > 0


# =========================================================================
# Layer 2: Event Proximity Kernel Tests
# =========================================================================

def test_event_proximity_decay_kernel():
    """Verify temporal proximity decay and service matching."""
    config = EventKernelConfig(lookback_hours=24.0, half_life_hours=6.0, service_match_multiplier=2.0)
    matcher = EventEvidenceMatcher(config=config)

    incident_time = "2026-03-15T12:00:00Z"
    events = [
        # Exactly coincident event, exact service match (delta = 0h -> weight = 1.0 * 2.0 = 2.0)
        {"event_id": "ev_deploy_0", "timestamp": "2026-03-15T12:00:00Z", "service": "AmazonEC2", "event_type": "DEPLOYMENT"},
        # 6h prior event, exact service match (delta = 6h -> weight = 0.5 * 2.0 = 1.0)
        {"event_id": "ev_deploy_6", "timestamp": "2026-03-15T06:00:00Z", "service": "AmazonEC2", "event_type": "DEPLOYMENT"},
        # 12h prior event, cross-service (delta = 12h -> weight = 0.25 * 0.2 = 0.05)
        {"event_id": "ev_rds_12", "timestamp": "2026-03-15T00:00:00Z", "service": "AmazonRDS", "event_type": "CONFIG_CHANGE"},
        # 30h prior event (exceeds lookback of 24h -> weight = 0.0)
        {"event_id": "ev_old_30", "timestamp": "2026-03-14T06:00:00Z", "service": "AmazonEC2", "event_type": "DEPLOYMENT"},
        # Decoy event (is_decoy=True -> severely attenuated)
        {"event_id": "ev_decoy", "timestamp": "2026-03-15T11:00:00Z", "service": "AmazonEC2", "event_type": "DEPLOYMENT", "is_decoy": True},
    ]

    cause_scores, evidence = matcher.match_events(
        incident_time=incident_time,
        incident_service="AmazonEC2",
        events=events,
    )

    assert "DEPLOYMENT_DEFECT" in cause_scores
    # DEPLOYMENT_DEFECT must dominate
    assert cause_scores["DEPLOYMENT_DEFECT"] > cause_scores.get("CONFIG_MODIFICATION", 0.0)

    # Check evidence item details
    ev_ids = [e.key for e in evidence]
    assert "ev_deploy_0" in ev_ids
    assert "ev_deploy_6" in ev_ids
    assert "ev_old_30" not in ev_ids  # Filtered out by lookback window


# =========================================================================
# A8.3: Selective Abstention on Pure-Noise Cases
# =========================================================================

def test_abstention_pure_noise_and_ambiguity():
    """Verify that pure noise or highly ambiguous incidents trigger abstention."""
    attributor = MultiLayerAttributor(
        abstention_config=AbstentionConfig(min_confidence=0.35, min_margin=0.08),
        enable_abstention=True,
    )
    attributor.fit([], [])

    # Case 1: Pure noise / zero evidence
    noise_incident = {
        "incident_id": "inc_pure_noise",
        "timestamp": "2026-03-15T12:00:00Z",
        "service": "AmazonEC2",
        "excess_spend": 0.0,
    }

    res = attributor.attribute_incident(noise_incident, nearby_events=[])
    assert res.is_abstained is True
    assert res.top_cause == "NOT_ENOUGH_EVIDENCE"

    # Case 2: predict_top_k reports NOT_ENOUGH_EVIDENCE
    preds = attributor.predict_top_k([noise_incident], events=[], k=3)
    assert preds == [["NOT_ENOUGH_EVIDENCE"]]

    # Case 3: Confident event evidence does NOT abstain
    active_events = [
        {"timestamp": "2026-03-15T11:30:00Z", "service": "AmazonEC2", "event_type": "DEPLOYMENT"}
    ]
    res_confident = attributor.attribute_incident(noise_incident, nearby_events=active_events)
    assert res_confident.is_abstained is False
    assert res_confident.top_cause == "DEPLOYMENT_DEFECT"


def test_confidence_calibration_tiers():
    """Verify confidence calibrator tier assignment."""
    calibrator = ConfidenceCalibrator()
    assert calibrator.get_tier(0.90) == "High"
    assert calibrator.get_tier(0.75) == "High"
    assert calibrator.get_tier(0.60) == "Medium"
    assert calibrator.get_tier(0.45) == "Medium"
    assert calibrator.get_tier(0.30) == "Low"


# =========================================================================
# A8.2: Attribution Metrics Suite Hand-Computed Tests
# =========================================================================

def test_attribution_metrics_suite_hand_computed():
    """Verify attribution metrics against exact hand-calculated values."""
    y_true = ["DEPLOYMENT_DEFECT", "AUTOSCALING_OVERPROVISION", "CONFIG_MODIFICATION", "RUNAWAY_BATCH_PROCESS"]
    preds = [
        ["DEPLOYMENT_DEFECT", "CONFIG_MODIFICATION", "AUTOSCALING_OVERPROVISION"],     # Rank 1 hit
        ["EXTERNAL_TRAFFIC_SURGE", "AUTOSCALING_OVERPROVISION", "DEPLOYMENT_DEFECT"], # Rank 2 hit
        ["DEPLOYMENT_DEFECT", "CONFIG_MODIFICATION", "RUNAWAY_BATCH_PROCESS"],         # Rank 2 hit
        ["EXTERNAL_TRAFFIC_SURGE", "AUTOSCALING_OVERPROVISION", "DEPLOYMENT_DEFECT"], # Miss (rank > 3)
    ]

    # Hand calculations:
    # Top-1 hits: 1 out of 4 = 0.25
    # Top-2 hits: 3 out of 4 = 0.75
    # Top-3 hits: 3 out of 4 = 0.75
    # MRR: (1/1 + 1/2 + 1/2 + 0.0) / 4 = (1.0 + 0.5 + 0.5 + 0.0) / 4 = 2.0 / 4 = 0.50
    assert pytest.approx(top_1_accuracy(y_true, preds)) == 0.25
    assert pytest.approx(top_k_accuracy(y_true, preds, k=2)) == 0.75
    assert pytest.approx(top_k_accuracy(y_true, preds, k=3)) == 0.75
    assert pytest.approx(mean_reciprocal_rank(y_true, preds)) == 0.50

    # Test per-class F1
    y_pred_top1 = [p[0] for p in preds]
    # y_true: [DEPLOY, AUTO, CONFIG, BATCH]
    # y_pred: [DEPLOY, TRAFFIC, DEPLOY, TRAFFIC]
    f1_res = per_class_f1_scores(y_true, y_pred_top1)
    # DEPLOY: TP=1, FP=1, FN=0 -> prec=0.5, rec=1.0, f1=2*(0.5*1)/(1.5) = 0.666667
    assert pytest.approx(f1_res["per_class"]["DEPLOYMENT_DEFECT"]["f1"], rel=1e-3) == 0.6667

    # Test ECE
    confs = [0.9, 0.8, 0.7, 0.6]
    ece = expected_calibration_error(y_true, y_pred_top1, confs, n_bins=5)
    assert 0.0 <= ece <= 1.0

    # Test abstention metrics
    is_abstained = [False, False, False, True]
    abst = abstention_metrics(y_true, y_pred_top1, is_abstained)
    assert pytest.approx(abst["abstention_rate"]) == 0.25
    assert pytest.approx(abst["coverage"]) == 0.75
    # For covered subset: [DEPLOY, AUTO, CONFIG] vs [DEPLOY, TRAFFIC, DEPLOY] -> 1 hit out of 3 = 0.333
    assert pytest.approx(abst["non_abstained_accuracy"], rel=1e-3) == 0.3333

    # Suite integration
    suite = evaluate_attribution_suite(
        y_true_primary=y_true,
        ranked_predictions=preds,
        confidences=confs,
        is_abstained=is_abstained,
    )
    assert suite["top_1_accuracy"] == 0.25
    assert suite["top_3_accuracy"] == 0.75
    assert suite["mrr"] == 0.50
    assert "abstention" in suite
    assert "expected_calibration_error" in suite


# =========================================================================
# A8.4: Label Isolation Invariant Test
# =========================================================================

def test_label_isolation_invariant_a8_4():
    """Verify that feature extraction and rankers do not consume ground-truth labels."""
    attributor = MultiLayerAttributor()

    incident_clean = {
        "incident_id": "inc_clean",
        "timestamp": "2026-03-15T12:00:00Z",
        "service": "AmazonEC2",
    }

    # Incident with adversarial poisoned ground truth
    incident_poisoned = dict(incident_clean)
    incident_poisoned["primary_cause"] = "ORPHANED_STORAGE_ACCUMULATION"
    incident_poisoned["true_causes"] = ["ORPHANED_STORAGE_ACCUMULATION"]
    incident_poisoned["ground_truth"] = "ORPHANED_STORAGE_ACCUMULATION"

    events = [
        {"timestamp": "2026-03-15T11:45:00Z", "service": "AmazonEC2", "event_type": "DEPLOYMENT"}
    ]

    # Model predictions must be identical regardless of label presence
    scores_clean = attributor.rank(incident_clean, events)
    scores_poisoned = attributor.rank(incident_poisoned, events)

    assert scores_clean == scores_poisoned
    assert scores_clean[0][0] == "DEPLOYMENT_DEFECT"
