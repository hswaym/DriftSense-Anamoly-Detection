"""TreeSHAP attribution layer with strict local additivity checks (Phase 9).

CRITICAL INVARIANT (A9.1):
    TreeSHAP explanations must satisfy the local efficiency / additivity property:
        f(x) = phi_0 + sum_{j=1}^M phi_j(x)
    within numerical tolerance <= 1e-3.
"""

from __future__ import annotations

import logging
from typing import Any

import numpy as np
import pandas as pd

from driftsense.explain.shap_explainer import (
    InstanceExplanation,
    TreeSHAPExplainer,
)

logger = logging.getLogger(__name__)


class TreeSHAPLayer(TreeSHAPExplainer):
    """Production TreeSHAP layer inheriting from TreeSHAPExplainer with strict additivity."""

    def __init__(
        self,
        tree_model: Any,
        feature_names: list[str] | None = None,
        model_id: str = "TreeModel",
        atol: float = 1e-3,
    ) -> None:
        super().__init__(model=tree_model, feature_names=feature_names, atol=atol)
        self.tree_model = self.raw_model
        self.model_id = model_id

    def explain_instance(
        self,
        row: pd.Series | dict[str, Any] | np.ndarray,
        prediction_id: str = "pred_0",
        top_k: int = 5,
    ) -> InstanceExplanation:
        """Generate a single instance explanation with top positive/negative drivers."""
        exp = super().explain_instance(row=row, prediction_id=prediction_id, top_k=top_k)
        exp.model_id = self.model_id
        return exp
