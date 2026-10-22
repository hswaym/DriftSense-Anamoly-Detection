"""DriftSense explainability package (Phase 9).

Provides TreeSHAP feature attributions with additivity verification,
calibrated confidence scoring, versioned executive narrative templates,
non-causal copy validation, and numerical faithfulness audits.
"""

from driftsense.explain.confidence import (
    CalibratedConfidenceScorer,
    ConfidenceAssessment,
)
from driftsense.explain.consistency import (
    compute_cause_agreement,
    compute_explanation_stability,
)
from driftsense.explain.faithfulness import (
    check_plain_language_readability,
    verify_narrative_faithfulness,
)
from driftsense.explain.importance import compute_global_importance
from driftsense.explain.narrative import (
    DISCLAIMER_TEXT,
    synthesize_cost_narrative,
)
from driftsense.explain.narrative_templates import (
    KNOWN_UNKNOWNS_ITEMS,
    SUGGESTED_NEXT_CHECKS,
    TEMPLATE_VERSION,
    render_narrative_template_v2,
)
from driftsense.explain.plain_language import (
    PlainLanguageExplanation,
    PlainLanguageSynthesizer,
)
from driftsense.explain.shap_explainer import (
    InstanceExplanation,
    TreeSHAPExplainer,
)
from driftsense.explain.shap_layer import TreeSHAPLayer
from driftsense.explain.validator import (
    find_forbidden_phrases,
    validate_all_templates,
    validate_non_causal_text,
)

__all__ = [
    "DISCLAIMER_TEXT",
    "KNOWN_UNKNOWNS_ITEMS",
    "SUGGESTED_NEXT_CHECKS",
    "TEMPLATE_VERSION",
    "CalibratedConfidenceScorer",
    "ConfidenceAssessment",
    "InstanceExplanation",
    "PlainLanguageExplanation",
    "PlainLanguageSynthesizer",
    "TreeSHAPExplainer",
    "TreeSHAPLayer",
    "check_plain_language_readability",
    "compute_cause_agreement",
    "compute_explanation_stability",
    "compute_global_importance",
    "find_forbidden_phrases",
    "render_narrative_template_v2",
    "synthesize_cost_narrative",
    "validate_all_templates",
    "validate_non_causal_text",
    "verify_narrative_faithfulness",
]
