"""Driver decomposition layer for DriftSense attribution.

Always available, even when a customer uploads billing data only with zero event logs.
Splits the cost gap ΔCost across:
1. Dimensional hierarchies (Service, Account, Region, UsageType) via DimensionRanker
2. Price-Volume-Mix decomposition (Volume vs Rate vs Interaction) via PriceVolumeMixDecomposer

Maps structural billing movements into initial attribution hypotheses with concrete
evidence items.
"""

from __future__ import annotations

import logging
from typing import Any

import pandas as pd

from driftsense.attribute.dimension_rank import DimensionRanker
from driftsense.attribute.evidence import AttributionReason, EvidenceItem
from driftsense.attribute.price_volume_mix import (
    PriceVolumeMixDecomposer,
)

logger = logging.getLogger(__name__)


class DriverDecomposer:
    """Decomposes an incident cost gap into dimensional drivers and rate/volume effects."""

    def __init__(
        self,
        dimensions: list[str] | None = None,
        cost_col: str = "BilledCost",
        quantity_col: str = "ConsumedQuantity",
        service_col: str = "ServiceName",
        tolerance: float = 1e-4,
    ) -> None:
        self.dimensions = dimensions or ["ServiceName", "SubAccountId", "RegionId", "UsageType"]
        self.cost_col = cost_col
        self.quantity_col = quantity_col
        self.service_col = service_col
        self.dim_ranker = DimensionRanker(dimensions=self.dimensions, cost_col=cost_col)
        self.pvm_decomposer = PriceVolumeMixDecomposer(tolerance=tolerance)

    def decompose(
        self,
        baseline_df: pd.DataFrame,
        actual_df: pd.DataFrame,
    ) -> dict[str, Any]:
        """Run full driver and price-volume-mix decomposition."""
        dim_ranks = self.dim_ranker.rank_all_dimensions(baseline_df, actual_df)
        pvm_result = self.pvm_decomposer.decompose(
            baseline_df=baseline_df,
            actual_df=actual_df,
            cost_col=self.cost_col,
            quantity_col=self.quantity_col,
            item_col=self.service_col,
        )

        return {
            "dimensions": {dim: [c.to_dict() for c in contribs] for dim, contribs in dim_ranks.items()},
            "price_volume_mix": pvm_result.to_dict(),
        }

    def infer_billing_reasons(
        self,
        baseline_df: pd.DataFrame,
        actual_df: pd.DataFrame,
        top_k: int = 3,
    ) -> list[AttributionReason]:
        """Infer candidate root causes directly from billing and usage patterns."""
        pvm_result = self.pvm_decomposer.decompose(
            baseline_df=baseline_df,
            actual_df=actual_df,
            cost_col=self.cost_col,
            quantity_col=self.quantity_col,
            item_col=self.service_col,
        )
        dim_ranks = self.dim_ranker.rank_all_dimensions(baseline_df, actual_df)

        evidence_items: list[EvidenceItem] = []

        # Add PVM evidence
        if abs(pvm_result.total_delta_cost) > 1e-6:
            evidence_items.append(
                EvidenceItem(
                    evidence_type="PRICE_VOLUME_MIX",
                    dimension="CostComponent",
                    key="VolumeEffect",
                    dollar_impact=pvm_result.volume_effect,
                    percentage_share=pvm_result.volume_share,
                    details={"volume_share": pvm_result.volume_share},
                )
            )
            evidence_items.append(
                EvidenceItem(
                    evidence_type="PRICE_VOLUME_MIX",
                    dimension="CostComponent",
                    key="PriceEffect",
                    dollar_impact=pvm_result.price_effect,
                    percentage_share=pvm_result.price_share,
                    details={"price_share": pvm_result.price_share},
                )
            )

        # Add top dimensional drivers
        top_service_key = ""
        top_service_share = 0.0
        if dim_ranks.get(self.service_col):
            top_svc = dim_ranks[self.service_col][0]
            top_service_key = top_svc.key
            top_service_share = top_svc.percentage_share
            evidence_items.append(top_svc.to_evidence_item())

        candidate_scores: dict[str, float] = {
            "EXTERNAL_TRAFFIC_SURGE": 0.1,
            "AUTOSCALING_OVERPROVISION": 0.1,
            "RUNAWAY_BATCH_PROCESS": 0.1,
            "CONFIG_MODIFICATION": 0.1,
            "ORPHANED_STORAGE_ACCUMULATION": 0.05,
            "DEPLOYMENT_DEFECT": 0.1,
        }

        # Billing heuristic mapping
        # 1. Storage keywords
        is_storage = any(
            term in top_service_key.lower()
            for term in ["s3", "storage", "blob", "gcs", "ebs", "disk", "volume"]
        )
        if is_storage:
            candidate_scores["ORPHANED_STORAGE_ACCUMULATION"] += 0.45

        # 2. Volume vs Price dominance
        if pvm_result.volume_share > 0.65:
            # Volume surge: traffic, batch, or autoscaling
            candidate_scores["EXTERNAL_TRAFFIC_SURGE"] += 0.35
            candidate_scores["AUTOSCALING_OVERPROVISION"] += 0.25
            candidate_scores["RUNAWAY_BATCH_PROCESS"] += 0.20
        elif pvm_result.price_share > 0.50:
            # Price/rate change without proportional volume change: config / discount drop
            candidate_scores["CONFIG_MODIFICATION"] += 0.50

        # 3. High service concentration
        if top_service_share > 0.70 and not is_storage:
            candidate_scores["DEPLOYMENT_DEFECT"] += 0.20
            candidate_scores["RUNAWAY_BATCH_PROCESS"] += 0.20

        # Normalize scores to [0.0, 1.0]
        total_score = sum(candidate_scores.values())
        norm_scores = {k: v / total_score for k, v in candidate_scores.items()}

        sorted_candidates = sorted(norm_scores.items(), key=lambda x: x[1], reverse=True)[:top_k]

        reasons: list[AttributionReason] = []
        for cause, score in sorted_candidates:
            if score >= 0.70:
                tier = "High"
            elif score >= 0.35:
                tier = "Medium"
            else:
                tier = "Low"

            summary = (
                f"Billing patterns show {pvm_result.volume_share:.1%} volume and "
                f"{pvm_result.price_share:.1%} rate contributions, with '{top_service_key}' as primary mover."
            )

            reasons.append(
                AttributionReason(
                    cause=cause,
                    confidence_score=float(score),
                    confidence_tier=tier,
                    dollar_impact=float(pvm_result.total_delta_cost),
                    percentage_share=float(score),
                    supporting_evidence=evidence_items,
                    summary=summary,
                )
            )

        return reasons
