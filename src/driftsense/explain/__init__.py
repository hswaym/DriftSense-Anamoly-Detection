"""DriftSense explainability package.

Provides TreeSHAP feature attributions, additivity verification,
stability and agreement evaluations, and non-causal narrative reporting.
"""

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
from driftsense.explain.shap_explainer import (
    InstanceExplanation,
    TreeSHAPExplainer,
)

__all__ = [
    "DISCLAIMER_TEXT",
    "InstanceExplanation",
    "TreeSHAPExplainer",
    "compute_cause_agreement",
    "compute_explanation_stability",
    "compute_global_importance",
    "synthesize_cost_narrative",
    "validate_non_causal_text",
]
