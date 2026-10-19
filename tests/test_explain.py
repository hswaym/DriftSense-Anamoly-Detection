"""Unit tests for DriftSense explainability engine, SHAP additivity, and narrative synthesis."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
import xgboost as xgb

from driftsense.explain.consistency import (
    compute_cause_agreement,
    compute_explanation_stability,
)
from driftsense.explain.importance import compute_global_importance
from driftsense.explain.narrative import (
    DISCLAIMER_TEXT,
    synthesize_cost_narrative,
    validate_non_causal_text,
)
from driftsense.explain.shap_explainer import TreeSHAPExplainer


@pytest.fixture
def synthetic_tree_model():
    """Create a fitted XGBoost model and dataset for SHAP testing."""
    np.random.seed(42)
    n_samples = 60
    X = np.random.randn(n_samples, 5)
    # y depends strongly on feature 0 and feature 1
    y = (
        2.0 * X[:, 0]
        + 1.5 * X[:, 1]
        - 0.5 * X[:, 2]
        + np.random.normal(0, 0.1, n_samples)
    )
    feature_names = [
        "cost_lag_1",
        "usage_lag_1",
        "rolling_mean_24",
        "event_count",
        "hour_of_day",
    ]
    df = pd.DataFrame(X, columns=feature_names)

    model = xgb.XGBRegressor(n_estimators=15, max_depth=3, random_state=42)
    model.fit(df, y)
    return model, df, y, feature_names


def test_shap_explainer_additivity_invariant(synthetic_tree_model):
    """A9.1: Verify TreeSHAP additivity holds: f(x) = phi_0 + sum(phi_j)."""
    model, df, _, feature_names = synthetic_tree_model

    explainer = TreeSHAPExplainer(model, feature_names=feature_names, atol=1e-3)
    shap_vals = explainer.explain(df, check_additivity=True)

    assert shap_vals.shape == df.shape

    # Hand-verify additivity across all samples
    base_val = explainer.expected_value
    reconstructed = np.sum(shap_vals, axis=1) + base_val
    preds = model.predict(df)

    max_err = np.max(np.abs(reconstructed - preds))
    assert max_err < 1e-3, (
        f"A9.1 Additivity violation: max error {max_err} exceeds 1e-3"
    )


def test_shap_explainer_instance_explanation(synthetic_tree_model):
    """Verify local instance explanation structure and top driver extraction."""
    model, df, _, feature_names = synthetic_tree_model
    explainer = TreeSHAPExplainer(model, feature_names=feature_names)

    exp = explainer.explain_instance(df.iloc[0], prediction_id="test_pred_0", top_k=2)

    assert exp.prediction_id == "test_pred_0"
    assert exp.additivity_verified is True
    assert exp.additivity_error < 1e-3
    assert len(exp.top_positive_drivers) <= 2
    assert len(exp.top_negative_drivers) <= 2

    # Check serialization
    d = exp.to_dict()
    assert d["prediction_id"] == "test_pred_0"
    assert "cost_lag_1" in d["attribution_values"]
    assert isinstance(d["model_output"], float)


def test_global_importance_properties(synthetic_tree_model):
    """Verify global feature importance calculation and ordering."""
    model, df, _, feature_names = synthetic_tree_model
    explainer = TreeSHAPExplainer(model, feature_names=feature_names)
    shap_vals = explainer.explain(df)

    imp_df = compute_global_importance(shap_vals, feature_names, model=model)

    assert len(imp_df) == len(feature_names)
    assert list(imp_df.columns)[:5] == [
        "rank",
        "feature",
        "mean_abs_shap",
        "relative_importance_pct",
        "cumulative_importance_pct",
    ]
    # Check descending order
    assert imp_df["mean_abs_shap"].is_monotonic_decreasing
    # Sum of relative importance should be ~100%
    assert abs(imp_df["relative_importance_pct"].sum() - 100.0) < 1e-2


def test_explanation_stability_across_seeds():
    """Verify rank correlation stability across repeated runs."""
    np.random.seed(42)

    # Run 1: High importance on feat_A and feat_B
    df1 = pd.DataFrame(
        {
            "rank": [1, 2, 3, 4],
            "feature": ["feat_A", "feat_B", "feat_C", "feat_D"],
            "mean_abs_shap": [0.8, 0.6, 0.2, 0.1],
        }
    )
    # Run 2: Nearly identical ranking
    df2 = pd.DataFrame(
        {
            "rank": [1, 2, 3, 4],
            "feature": ["feat_A", "feat_B", "feat_D", "feat_C"],
            "mean_abs_shap": [0.85, 0.55, 0.22, 0.18],
        }
    )

    stability = compute_explanation_stability([df1, df2], top_k=2)

    assert stability["num_runs"] == 2
    assert stability["mean_spearman_rho"] >= 0.79
    assert stability["mean_top_k_jaccard"] == 1.0
    assert "feat_A" in stability["top_k_features_shared"]


def test_cause_agreement_synthetic():
    """Verify agreement check between top driver keywords and injected causes."""
    explanations = [
        {
            "prediction_id": "p1",
            "top_positive_drivers": [
                ("deployment_proximity_delta", 1.5),
                ("cost_lag_1", 0.8),
            ],
        },
        {
            "prediction_id": "p2",
            "top_positive_drivers": [
                ("consumed_quantity_surge", 2.2),
                ("usage_window_3", 1.1),
            ],
        },
    ]
    ground_truth = [
        {"primary_cause": "DEPLOYMENT_DEFECT"},
        {"primary_cause": "AUTOSCALING_OVERPROVISION"},
    ]

    agreement = compute_cause_agreement(explanations, ground_truth, top_k=2)

    assert agreement["total_evaluated"] == 2
    assert agreement["matches"] == 2
    assert agreement["agreement_rate"] == 1.0


def test_narrative_synthesis_and_non_causal_wording_invariant():
    """A9.2: Verify natural language explanations strictly exclude causal-proof phrasing."""
    narrative = synthesize_cost_narrative(
        service_name="AmazonEC2",
        timestamp="2026-10-19T14:00:00Z",
        actual_cost=1500.0,
        expected_cost=1000.0,
        top_positive_drivers=[
            ("usage_quantity_spike", 320.0),
            ("deployment_proximity", 180.0),
        ],
        coincident_events=[
            {"event_type": "DEPLOYMENT", "timestamp": "2026-10-19T13:30:00Z"}
        ],
        attributed_cause="DEPLOYMENT_DEFECT",
    )

    # Narrative must contain non-causal associations and mandatory disclaimer
    assert "AmazonEC2" in narrative
    assert "Associated with" in narrative
    assert "Top Statistical Cost Drivers" in narrative
    assert DISCLAIMER_TEXT in narrative

    # A9.2 Invariant: Forbidden phrases must raise error if introduced
    forbidden = [
        "caused by",
        "proves that",
        "is the cause",
        "is responsible for",
        "definitive cause",
    ]
    for phrase in forbidden:
        assert phrase not in narrative.lower(), (
            f"A9.2 Violation: Forbidden phrase '{phrase}' in narrative"
        )

    # Verify validator catches violations
    with pytest.raises(ValueError, match="A9.2 Non-Causal Wording Violation"):
        validate_non_causal_text("The cost surge was caused by the deployment defect.")
