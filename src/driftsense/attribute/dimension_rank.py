"""Dimension-level contribution ranking and explanatory power calculation.

Computes how much each slice of a dimension (ServiceName, SubAccountId, RegionId,
UsageType, Tags) explains an observed cost anomaly gap ΔCost = Actual - Expected.

Inspired by Adtributor (explanatory power + surprise) and additive Shapley-style
single-dimension attribution.
"""

from __future__ import annotations

import logging
from dataclasses import asdict, dataclass
from typing import Any

import pandas as pd

from driftsense.attribute.evidence import EvidenceItem

logger = logging.getLogger(__name__)


@dataclass
class DimensionContribution:
    """Individual slice contribution along a categorical dimension."""

    dimension: str
    key: str
    baseline_cost: float
    actual_cost: float
    delta_cost: float
    percentage_share: float  # Share of total delta
    explanatory_power: float  # ΔC_k / ΔC_total (can be negative if slice dropped)
    surprise_score: float    # Relative divergence / surprise metric

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_evidence_item(self) -> EvidenceItem:
        return EvidenceItem(
            evidence_type="DIMENSION_DECOMPOSITION",
            dimension=self.dimension,
            key=self.key,
            dollar_impact=self.delta_cost,
            percentage_share=self.percentage_share,
            details={
                "baseline_cost": self.baseline_cost,
                "actual_cost": self.actual_cost,
                "explanatory_power": self.explanatory_power,
                "surprise_score": self.surprise_score,
            },
        )


class DimensionRanker:
    """Ranks categorical dimensions by contribution to an anomalous cost spike."""

    def __init__(
        self,
        dimensions: list[str] | None = None,
        cost_col: str = "BilledCost",
        min_share_threshold: float = 0.05,
    ) -> None:
        self.dimensions = dimensions or ["ServiceName", "SubAccountId", "RegionId", "UsageType"]
        self.cost_col = cost_col
        self.min_share_threshold = min_share_threshold

    def rank_dimension(
        self,
        baseline_df: pd.DataFrame,
        actual_df: pd.DataFrame,
        dimension: str,
    ) -> list[DimensionContribution]:
        """Rank slices within a single dimension by contribution to cost gap."""
        if dimension not in baseline_df.columns and dimension not in actual_df.columns:
            return []

        b_costs = baseline_df.groupby(dimension)[self.cost_col].sum() if dimension in baseline_df.columns else pd.Series(dtype=float)
        a_costs = actual_df.groupby(dimension)[self.cost_col].sum() if dimension in actual_df.columns else pd.Series(dtype=float)

        all_keys = sorted(set(b_costs.index) | set(a_costs.index))
        total_b = float(b_costs.sum())
        total_a = float(a_costs.sum())
        total_delta = total_a - total_b

        contributions: list[DimensionContribution] = []

        for key in all_keys:
            b_val = float(b_costs.get(key, 0.0))
            a_val = float(a_costs.get(key, 0.0))
            d_val = a_val - b_val

            # Explanatory power (EP)
            ep = d_val / total_delta if abs(total_delta) > 1e-9 else 0.0
            share = max(0.0, d_val) / max(1e-9, total_delta) if total_delta > 0 else 0.0

            # Surprise score (Adtributor style: difference between actual share and expected baseline share)
            expected_share = b_val / total_b if total_b > 1e-9 else (1.0 / len(all_keys) if all_keys else 0.0)
            actual_share = a_val / total_a if total_a > 1e-9 else 0.0
            surprise = actual_share - expected_share

            contributions.append(
                DimensionContribution(
                    dimension=dimension,
                    key=str(key),
                    baseline_cost=b_val,
                    actual_cost=a_val,
                    delta_cost=d_val,
                    percentage_share=share,
                    explanatory_power=ep,
                    surprise_score=surprise,
                )
            )

        # Sort descending by delta_cost
        contributions.sort(key=lambda c: c.delta_cost, reverse=True)
        return contributions

    def rank_all_dimensions(
        self,
        baseline_df: pd.DataFrame,
        actual_df: pd.DataFrame,
    ) -> dict[str, list[DimensionContribution]]:
        """Rank slices across all configured dimensions."""
        results: dict[str, list[DimensionContribution]] = {}
        for dim in self.dimensions:
            contribs = self.rank_dimension(baseline_df, actual_df, dim)
            if contribs:
                results[dim] = contribs
        return results
