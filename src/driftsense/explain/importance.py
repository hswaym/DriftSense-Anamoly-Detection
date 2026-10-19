"""Global feature importance aggregation based on TreeSHAP and tree metrics."""

from __future__ import annotations

import logging
from typing import Any

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


def compute_global_importance(
    shap_values: np.ndarray,
    feature_names: list[str],
    model: Any = None,
) -> pd.DataFrame:
    """Compute global feature importance ranking from SHAP values.

    Args:
        shap_values: 2D array (N_samples, N_features) of SHAP values.
        feature_names: List of feature names.
        model: Optional tree model to extract native gain / split importances.

    Returns:
        DataFrame with columns ['rank', 'feature', 'mean_abs_shap', 'relative_importance_pct', 'cumulative_importance_pct'].
    """
    if isinstance(shap_values, list):
        # Multi-class: average mean absolute SHAP across classes
        abs_means = np.mean([np.mean(np.abs(sv), axis=0) for sv in shap_values], axis=0)
    elif shap_values.ndim == 3:
        abs_means = np.mean(np.mean(np.abs(shap_values), axis=0), axis=1)
    else:
        abs_means = np.mean(np.abs(shap_values), axis=0)

    total_imp = np.sum(abs_means)
    rel_pct = (
        (abs_means / total_imp * 100.0) if total_imp > 0 else np.zeros_like(abs_means)
    )

    df = pd.DataFrame(
        {
            "feature": feature_names,
            "mean_abs_shap": abs_means,
            "relative_importance_pct": rel_pct,
        }
    )

    # Sort descending by mean_abs_shap
    df = df.sort_values(by="mean_abs_shap", ascending=False).reset_index(drop=True)
    df["rank"] = df.index + 1
    df["cumulative_importance_pct"] = df["relative_importance_pct"].cumsum()

    # Reorder columns
    cols = [
        "rank",
        "feature",
        "mean_abs_shap",
        "relative_importance_pct",
        "cumulative_importance_pct",
    ]

    # Incorporate native model gain if available
    if model is not None:
        try:
            if hasattr(model, "feature_importances_"):
                native_imp = model.feature_importances_
                native_map = dict(zip(feature_names, native_imp))
                df["native_gain"] = df["feature"].map(native_map)
                cols.append("native_gain")
        except (AttributeError, ValueError, TypeError) as e:
            logger.debug("Could not extract native feature_importances_: %s", e)

    return df[cols]
