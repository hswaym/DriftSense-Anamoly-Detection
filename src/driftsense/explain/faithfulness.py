"""Faithfulness and readability evaluation suite for DriftSense v2 (Phase 9).

Validates:
- A9.2 Narrative-Number Consistency: Ensures all numbers cited in plain-language
  narratives strictly equal the underlying numerical artifacts within rounding.
- A9.4 Readability Invariant: Asserts no unexplained technical machine learning
  glossary terms appear in the default executive summary view.
- Explanation Stability across seeds (Spearman rho, Jaccard overlap).
"""

from __future__ import annotations

import re
from typing import Any

import numpy as np
import pandas as pd
from scipy.stats import kendalltau, spearmanr

# Forbidden technical jargon in the default executive view (A9.4 readability rule)
EXECUTIVE_FORBIDDEN_JARGON = [
    "heteroscedasticity",
    "eigenvalues",
    "log-loss",
    "nonconformity score",
    "hyperplane",
    "multicollinearity",
    "kernel trick",
    "stochastic gradient descent",
    "backpropagation",
    "kolmogorov-smirnov",
    "conformal prediction",
]


def check_plain_language_readability(text: str) -> dict[str, Any]:
    """Verify that no unexplained technical ML jargon appears in default executive text (A9.4).

    Any technical diagnostics must be sequestered behind <details> tags.
    """
    # Strip content within <details>...</details>
    cleaned_text = re.sub(r"<details>.*?</details>", "", text, flags=re.DOTALL)
    cleaned_lower = cleaned_text.lower()

    found_jargon = []
    for term in EXECUTIVE_FORBIDDEN_JARGON:
        if term in cleaned_lower:
            found_jargon.append(term)

    is_compliant = len(found_jargon) == 0
    return {
        "is_compliant": is_compliant,
        "found_jargon": found_jargon,
        "checked_terms_count": len(EXECUTIVE_FORBIDDEN_JARGON),
    }


def verify_narrative_faithfulness(
    narrative_text: str,
    ground_values: dict[str, Any],
    dollar_tolerance: float = 0.05,
    pct_tolerance: float = 0.5,
) -> dict[str, Any]:
    """Automated check that narrative numbers equal underlying artifact values (A9.2).

    Args:
        narrative_text: Rendered executive narrative string.
        ground_values: Dictionary containing true numerical parameters:
            - 'actual_cost': float
            - 'expected_cost': float
            - 'timestamp': str
        dollar_tolerance: Acceptable deviation due to rounding ($).
        pct_tolerance: Acceptable deviation due to rounding (%).

    Returns:
        Dictionary reporting verification status and matched values.
    """
    errors: list[str] = []

    actual_true = float(ground_values.get("actual_cost", 0.0))
    expected_true = float(ground_values.get("expected_cost", 0.0))
    delta_true = actual_true - expected_true

    # Extract all dollar amounts from text ($1,234.56 or $123.45)
    dollar_matches = re.findall(r"\$([0-9,]+\.[0-9]{2})", narrative_text)
    extracted_dollars = [float(m.replace(",", "")) for m in dollar_matches]

    # Verify actual cost appears in text
    if not any(abs(d - actual_true) <= dollar_tolerance for d in extracted_dollars):
        errors.append(
            f"Faithfulness error: Actual cost ${actual_true:,.2f} not found in narrative numbers {extracted_dollars}"
        )

    # Verify expected cost appears in text
    if not any(abs(d - expected_true) <= dollar_tolerance for d in extracted_dollars):
        errors.append(
            f"Faithfulness error: Expected cost ${expected_true:,.2f} not found in narrative numbers {extracted_dollars}"
        )

    # Verify delta appears in text
    if not any(abs(d - abs(delta_true)) <= dollar_tolerance for d in extracted_dollars):
        errors.append(
            f"Faithfulness error: Deviation amount ${abs(delta_true):,.2f} not found in narrative numbers {extracted_dollars}"
        )

    # Verify timestamp appears in text
    ts = ground_values.get("timestamp")
    if ts and ts not in narrative_text:
        errors.append(f"Faithfulness error: Timestamp '{ts}' missing from narrative text.")

    is_faithful = len(errors) == 0
    return {
        "is_faithful": is_faithful,
        "errors": errors,
        "extracted_dollars": extracted_dollars,
        "actual_cost_verified": any(abs(d - actual_true) <= dollar_tolerance for d in extracted_dollars),
        "expected_cost_verified": any(abs(d - expected_true) <= dollar_tolerance for d in extracted_dollars),
    }


def compute_explanation_stability(
    importance_dfs: list[pd.DataFrame],
    top_k: int = 5,
) -> dict[str, Any]:
    """Compute stability of global feature importance across random seeds.

    Measures:
    - Mean pairwise Spearman rank correlation (rho)
    - Mean pairwise Kendall tau rank correlation (tau)
    - Mean pairwise Top-k Jaccard set overlap
    - Top-k features shared across all seeds
    """
    if len(importance_dfs) < 2:
        return {
            "num_runs": len(importance_dfs),
            "mean_spearman_rho": 1.0,
            "mean_kendall_tau": 1.0,
            "mean_top_k_jaccard": 1.0,
            "top_k_features_shared": (
                importance_dfs[0]["feature"].head(top_k).tolist()
                if importance_dfs
                else []
            ),
        }

    spearman_rhos: list[float] = []
    kendall_taus: list[float] = []
    jaccards: list[float] = []
    top_k_sets: list[set[str]] = []

    for df in importance_dfs:
        top_k_sets.append(set(df["feature"].head(top_k)))

    for i in range(len(importance_dfs)):
        for j in range(i + 1, len(importance_dfs)):
            df1 = importance_dfs[i].set_index("feature")
            df2 = importance_dfs[j].set_index("feature")

            common = df1.index.intersection(df2.index)
            if len(common) > 1:
                r1 = df1.loc[common, "rank"]
                r2 = df2.loc[common, "rank"]

                rho, _ = spearmanr(r1, r2)
                tau, _ = kendalltau(r1, r2)

                spearman_rhos.append(float(rho) if not np.isnan(rho) else 1.0)
                kendall_taus.append(float(tau) if not np.isnan(tau) else 1.0)

            # Jaccard overlap on top-k features
            s1 = top_k_sets[i]
            s2 = top_k_sets[j]
            union = s1.union(s2)
            inter = s1.intersection(s2)
            jaccard = len(inter) / len(union) if union else 1.0
            jaccards.append(jaccard)

    shared_top_k = list(set.intersection(*top_k_sets)) if top_k_sets else []

    return {
        "num_runs": len(importance_dfs),
        "mean_spearman_rho": float(np.mean(spearman_rhos)) if spearman_rhos else 1.0,
        "mean_kendall_tau": float(np.mean(kendall_taus)) if kendall_taus else 1.0,
        "mean_top_k_jaccard": float(np.mean(jaccards)) if jaccards else 1.0,
        "top_k_features_shared": sorted(shared_top_k),
    }
