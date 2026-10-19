"""Explanation consistency, stability, and synthetic ground-truth agreement checks.

Verifies:
1. Stability: Feature importance rank correlation (Spearman rho, Kendall tau) across different seeds.
2. Agreement: Whether top local explanation drivers align with the known injected cause on the synthetic track.
"""

from __future__ import annotations

import logging
from typing import Any

import numpy as np
import pandas as pd
from scipy.stats import kendalltau, spearmanr

logger = logging.getLogger(__name__)


def compute_explanation_stability(
    importance_dfs: list[pd.DataFrame],
    top_k: int = 10,
) -> dict[str, Any]:
    """Compute stability of feature importance rankings across multiple seeds/runs.

    Args:
        importance_dfs: List of DataFrames returned by `compute_global_importance`, one per seed.
        top_k: Number of top features to evaluate overlap and correlation for.

    Returns:
        dict containing pairwise and mean Spearman rho, Kendall tau, and Top-k Jaccard index.
    """
    n_runs = len(importance_dfs)
    if n_runs < 2:
        return {
            "num_runs": n_runs,
            "mean_spearman_rho": 1.0,
            "mean_kendall_tau": 1.0,
            "mean_top_k_jaccard": 1.0,
            "pairwise_spearman": [],
            "top_k_features_shared": list(importance_dfs[0]["feature"].head(top_k))
            if n_runs == 1
            else [],
        }

    spearman_rhos = []
    kendall_taus = []
    top_k_sets = [set(df["feature"].head(top_k)) for df in importance_dfs]
    jaccard_scores = []

    # Get union of all features across runs
    all_features = sorted(set().union(*[set(df["feature"]) for df in importance_dfs]))

    # Compute pairwise rank correlations
    for i in range(n_runs):
        for j in range(i + 1, n_runs):
            df_i = importance_dfs[i].set_index("feature")["rank"].to_dict()
            df_j = importance_dfs[j].set_index("feature")["rank"].to_dict()

            # Align ranks
            ranks_i = [df_i.get(f, len(all_features)) for f in all_features]
            ranks_j = [df_j.get(f, len(all_features)) for f in all_features]

            s_rho, _ = spearmanr(ranks_i, ranks_j)
            k_tau, _ = kendalltau(ranks_i, ranks_j)

            # Jaccard overlap of top-k sets
            set_i = top_k_sets[i]
            set_j = top_k_sets[j]
            jaccard = (
                len(set_i & set_j) / len(set_i | set_j)
                if len(set_i | set_j) > 0
                else 0.0
            )

            if not np.isnan(s_rho):
                spearman_rhos.append(float(s_rho))
            if not np.isnan(k_tau):
                kendall_taus.append(float(k_tau))
            jaccard_scores.append(float(jaccard))

    shared_top_k = sorted(set.intersection(*top_k_sets)) if top_k_sets else []

    return {
        "num_runs": n_runs,
        "mean_spearman_rho": float(np.mean(spearman_rhos)) if spearman_rhos else 0.0,
        "mean_kendall_tau": float(np.mean(kendall_taus)) if kendall_taus else 0.0,
        "mean_top_k_jaccard": float(np.mean(jaccard_scores)) if jaccard_scores else 0.0,
        "pairwise_spearman": spearman_rhos,
        "top_k_features_shared": shared_top_k,
    }


def compute_cause_agreement(
    instance_explanations: list[dict[str, Any]],
    ground_truth_labels: list[dict[str, Any]],
    top_k: int = 3,
) -> dict[str, Any]:
    """Evaluate agreement between top local explanation features and known injected cause.

    Matches synthetic fault signatures to top explanation features:
    - DEPLOYMENT_DEFECT -> deployment / rollout / lag features
    - AUTOSCALING_OVERPROVISION -> usage / quantity / jump features
    - EXTERNAL_TRAFFIC_SURGE -> traffic / request / cost surge features
    - CONFIG_MODIFICATION -> config / param features
    - RUNAWAY_BATCH_PROCESS -> off-peak / night / batch features

    Args:
        instance_explanations: List of InstanceExplanation dicts for anomaly points.
        ground_truth_labels: Corresponding ground-truth incident records.
        top_k: Top-k explanation drivers to inspect for cause match.

    Returns:
        dict containing overall agreement rate and per-cause breakdown.
    """
    if len(instance_explanations) == 0:
        return {"total_evaluated": 0, "agreement_rate": 0.0, "per_cause_agreement": {}}

    # Keyword mappings linking cause taxonomy to feature naming patterns
    cause_signatures = {
        "DEPLOYMENT_DEFECT": ["deploy", "rollout", "defect", "lag_1", "window_3"],
        "AUTOSCALING_OVERPROVISION": [
            "usage",
            "consumed",
            "quantity",
            "scale",
            "overprovision",
        ],
        "EXTERNAL_TRAFFIC_SURGE": ["traffic", "request", "surge", "cost", "spike"],
        "CONFIG_MODIFICATION": ["config", "modify", "param"],
        "ORPHANED_STORAGE_ACCUMULATION": ["storage", "disk", "accumulat", "volume"],
        "RUNAWAY_BATCH_PROCESS": ["batch", "runaway", "hour", "process"],
    }

    matches = 0
    per_cause_counts: dict[str, int] = {}
    per_cause_matches: dict[str, int] = {}

    for exp, label in zip(instance_explanations, ground_truth_labels):
        cause = str(label.get("primary_cause", label.get("cause", "UNKNOWN")))
        per_cause_counts[cause] = per_cause_counts.get(cause, 0) + 1

        top_drivers = [
            driver for driver, _ in exp.get("top_positive_drivers", [])[:top_k]
        ]
        keywords = cause_signatures.get(cause, [cause.lower()])

        # Check if any top driver matches a signature keyword or the cause directly
        agreed = any(
            any(kw in driver.lower() for kw in keywords)
            or cause.lower() in driver.lower()
            for driver in top_drivers
        )

        if agreed:
            matches += 1
            per_cause_matches[cause] = per_cause_matches.get(cause, 0) + 1

    overall_rate = (
        float(matches / len(instance_explanations)) if instance_explanations else 0.0
    )
    per_cause_breakdown = {
        c: {
            "total": count,
            "matched": per_cause_matches.get(c, 0),
            "agreement_rate": float(per_cause_matches.get(c, 0) / count)
            if count > 0
            else 0.0,
        }
        for c, count in per_cause_counts.items()
    }

    return {
        "total_evaluated": len(instance_explanations),
        "matches": matches,
        "agreement_rate": overall_rate,
        "per_cause_agreement": per_cause_breakdown,
    }
