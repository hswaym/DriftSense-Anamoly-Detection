"""Unit and integration tests for DriftSense Explainability & Trust Layer (Phase 9).

Validates:
- A9.1: TreeSHAP Additivity Invariant: f(x) = phi_0 + sum_j phi_j(x) within tolerance <= 1e-3
- A9.2: Narrative-Number Consistency: All numbers in narrative equal underlying artifact numbers
- A9.3: Extended Non-Causal Copy Validator: All templates and rendered copy strictly reject forbidden causal verbs
- A9.4: Executive Readability Check: No unexplained technical glossary terms appear in default view
- Confidence derivation from calibrated scores, guarding strictly against raw SHAP
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
import xgboost as xgb

from driftsense.explain import (
    CalibratedConfidenceScorer,
    PlainLanguageSynthesizer,
    TreeSHAPLayer,
    check_plain_language_readability,
    find_forbidden_phrases,
    render_narrative_template_v2,
    validate_all_templates,
    validate_non_causal_text,
    verify_narrative_faithfulness,
)
from driftsense.explain.narrative_templates import (
    TEMPLATE_VERSION,
)


@pytest.fixture
def trained_tree_model():
    """Create a fitted XGBoost regressor and test samples for TreeSHAP testing."""
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
        "consumed_quantity_lag_1",
        "effective_cost_lag_1",
        "rolling_mean_24",
        "event_count",
        "hour_of_day",
    ]
    df = pd.DataFrame(X, columns=feature_names)

    model = xgb.XGBRegressor(n_estimators=15, max_depth=3, random_state=42)
    model.fit(df, y)
    return model, df, feature_names


# =========================================================================
# A9.1: TreeSHAP Additivity Invariant Tests
# =========================================================================

def test_treeshap_additivity_invariant(trained_tree_model):
    """A9.1: Verify TreeSHAP additivity holds: f(x) == phi_0 + sum(phi_j) within 1e-3."""
    model, df, feature_names = trained_tree_model

    layer = TreeSHAPLayer(model, feature_names=feature_names, atol=1e-3)
    shap_vals = layer.explain(df, check_additivity=True)

    assert shap_vals.shape == df.shape

    # Exact additivity verification across all rows
    preds = model.predict(df)
    reconstructed = np.sum(shap_vals, axis=1) + layer.expected_value
    max_discrepancy = np.max(np.abs(reconstructed - preds))

    assert max_discrepancy <= 1e-3, f"A9.1 Violation: Additivity error {max_discrepancy} > 1e-3"


def test_treeshap_instance_explanation_formatting(trained_tree_model):
    """Verify instance explanation payload and top drivers ranking."""
    model, df, feature_names = trained_tree_model
    layer = TreeSHAPLayer(model, feature_names=feature_names, model_id="TestXGBoost", atol=1e-3)

    exp = layer.explain_instance(df.iloc[0], prediction_id="pred_123", top_k=2)

    assert exp.prediction_id == "pred_123"
    assert exp.model_id == "TestXGBoost"
    assert exp.additivity_verified is True
    assert exp.additivity_error <= 1e-3
    assert len(exp.top_positive_drivers) <= 2
    assert len(exp.top_negative_drivers) <= 2

    d = exp.to_dict()
    assert d["prediction_id"] == "pred_123"
    assert "consumed_quantity_lag_1" in d["attribution_values"]


# =========================================================================
# A9.2: Narrative-Number Consistency & Faithfulness Tests
# =========================================================================

def test_narrative_number_faithfulness():
    """A9.2: Verify that narrative numbers strictly match underlying artifact numbers."""
    actual = 1450.75
    expected = 1000.25
    timestamp = "2026-10-22T14:00:00Z"

    rendered = render_narrative_template_v2(
        service_name="AmazonEC2",
        timestamp=timestamp,
        actual_cost=actual,
        expected_cost=expected,
        sub_account_id="acc-prod-01",
        region_id="us-east-1",
        duration_hours=3.5,
    )

    ground_truth = {
        "actual_cost": actual,
        "expected_cost": expected,
        "timestamp": timestamp,
    }

    res = verify_narrative_faithfulness(rendered, ground_truth)
    assert res["is_faithful"] is True
    assert res["actual_cost_verified"] is True
    assert res["expected_cost_verified"] is True
    assert len(res["errors"]) == 0

    # Test error detection when numbers are deliberately corrupted
    corrupted_ground_truth = {
        "actual_cost": 9999.99,  # Wrong amount
        "expected_cost": expected,
        "timestamp": timestamp,
    }
    bad_res = verify_narrative_faithfulness(rendered, corrupted_ground_truth)
    assert bad_res["is_faithful"] is False
    assert any("Actual cost $9,999.99 not found" in err for err in bad_res["errors"])


# =========================================================================
# A9.3: Extended Non-Causal Copy Validator Tests
# =========================================================================

def test_non_causal_validator_forbidden_verbs():
    """A9.3: Extended validator must detect all forbidden certainty verbs."""
    forbidden_samples = [
        "The cost surge was caused by an unannounced deployment.",
        "The spike was triggered by an autoscaling policy change.",
        "High memory usage resulted from a memory leak.",
        "The invoice anomaly was due to storage accumulation.",
        "This metric proves that the microservice failed.",
        "Engineering team is responsible for the spend jump.",
        "The runaway batch job is the definitive cause of this incident.",
    ]

    for sample in forbidden_samples:
        with pytest.raises(ValueError, match="A9.3 Non-Causal Wording Violation"):
            validate_non_causal_text(sample)


def test_validator_passes_compliant_templates():
    """A9.3: Verify that all standard templates pass non-causal validation."""
    templates = {
        "v2_default": render_narrative_template_v2(
            service_name="AmazonEC2",
            timestamp="2026-10-22T12:00:00Z",
            actual_cost=500.0,
            expected_cost=400.0,
        )
    }
    validate_all_templates(templates)
    assert len(find_forbidden_phrases(templates["v2_default"])) == 0


# =========================================================================
# A9.4: Executive Readability Tests
# =========================================================================

def test_executive_readability_check():
    """A9.4: Verify no unexplained technical ML jargon appears in default executive text."""
    clean_text = (
        "Observed cloud spend reached $1,500.00, departing from expected $1,000.00. "
        "Top associated service was AmazonEC2."
    )
    res_clean = check_plain_language_readability(clean_text)
    assert res_clean["is_compliant"] is True
    assert len(res_clean["found_jargon"]) == 0

    # Jargon outside details must fail
    jargon_text = (
        "The residual distribution exhibited high heteroscedasticity and nonconformity score deviations."
    )
    res_jargon = check_plain_language_readability(jargon_text)
    assert res_jargon["is_compliant"] is False
    assert "heteroscedasticity" in res_jargon["found_jargon"]
    assert "nonconformity score" in res_jargon["found_jargon"]

    # Technical jargon sequestered inside <details>...</details> is permitted for expert audit
    sequestered_text = (
        "Observed cloud spend reached $1,500.00.\n"
        "<details>\n"
        "Technical diagnostic: Conformal prediction nonconformity score was calibrated at alpha=0.05.\n"
        "</details>"
    )
    res_seq = check_plain_language_readability(sequestered_text)
    assert res_seq["is_compliant"] is True


# =========================================================================
# Calibrated Confidence Derivation & SHAP Guard Tests
# =========================================================================

def test_calibrated_confidence_derivation():
    """Verify confidence tier assignment and guard against raw SHAP input."""
    scorer = CalibratedConfidenceScorer()

    # High confidence: probability >= 0.75, margin >= 0.15
    high = scorer.assess_confidence(calibrated_score=0.85, margin=0.25, evidence_count=2)
    assert high.tier == "High"

    # Medium confidence
    med = scorer.assess_confidence(calibrated_score=0.55, margin=0.08, evidence_count=1)
    assert med.tier == "Medium"

    # Low confidence
    low = scorer.assess_confidence(calibrated_score=0.25, margin=0.02, evidence_count=0)
    assert low.tier == "Low"

    # Abstained must return Low tier
    abst = scorer.assess_confidence(calibrated_score=0.90, margin=0.30, is_abstained=True)
    assert abst.tier == "Low"

    # Strict guard against raw SHAP
    with pytest.raises(TypeError, match="Phase 9 Invariant Violation"):
        scorer.guard_against_raw_shap([12.5, -4.2, 0.8])


# =========================================================================
# PlainLanguageSynthesizer End-to-End Integration
# =========================================================================

def test_plain_language_synthesizer_e2e(trained_tree_model):
    """Test full end-to-end narrative synthesis with TreeSHAP and faithfulness audits."""
    model, df, feature_names = trained_tree_model
    layer = TreeSHAPLayer(model, feature_names=feature_names, model_id="ChampionXGBoost")

    instance_shap = layer.explain_instance(df.iloc[0], prediction_id="pred_test_01", top_k=3)
    synthesizer = PlainLanguageSynthesizer()

    ranked_causes = [
        {
            "cause": "DEPLOYMENT_DEFECT",
            "probability": 0.82,
            "margin": 0.35,
            "evidence_count": 2,
            "rationale": "Strong correlation with deployment event deploy-124 within 30m of onset.",
            "percentage_share": 0.65,
        },
        {
            "cause": "AUTOSCALING_OVERPROVISION",
            "probability": 0.12,
            "margin": 0.35,
            "evidence_count": 0,
            "rationale": "Secondary usage fluctuation.",
            "percentage_share": 0.20,
        },
    ]

    explanation = synthesizer.generate_explanation(
        prediction_id="pred_test_01",
        service_name="AmazonEC2",
        timestamp="2026-10-22T16:00:00Z",
        actual_cost=1850.50,
        expected_cost=1200.00,
        sub_account_id="acc-core-infra",
        region_id="us-east-1",
        duration_hours=2.0,
        ranked_causes=ranked_causes,
        instance_shap=instance_shap,
        evidence_refs=["event_deploy_124", "event_hpa_config"],
    )

    assert explanation.prediction_id == "pred_test_01"
    assert explanation.service_name == "AmazonEC2"
    assert explanation.top_cause == "DEPLOYMENT_DEFECT"
    assert explanation.confidence_tier == "High"
    assert explanation.is_faithful is True
    assert explanation.is_readable is True
    assert "Executive Cost Anomaly Brief" in explanation.narrative_markdown
    assert f"Template Version: {TEMPLATE_VERSION}" in explanation.narrative_markdown
    assert "Click to expand technical TreeSHAP attributions" in explanation.narrative_markdown
    assert "pred_test_01" in explanation.narrative_markdown
