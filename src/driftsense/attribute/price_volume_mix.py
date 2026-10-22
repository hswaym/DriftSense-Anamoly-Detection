"""Price-Volume-Mix (Rate-Volume-Mix) Decomposition.

Separates the aggregate cost delta ΔCost between baseline/expected and actual spend
into Volume (quantity), Rate/Price, and Mix (interaction) effects.

Identity:
    ΔCost = Volume_Effect + Price_Effect + Mix_Effect

For each item/service i:
    Baseline: C_0 = P_0 * Q_0
    Actual:   C_1 = P_1 * Q_1
    ΔC = C_1 - C_0
    Volume Effect = (Q_1 - Q_0) * P_0
    Price Effect  = (P_1 - P_0) * Q_0
    Mix Effect    = (P_1 - P_0) * (Q_1 - Q_0)

    Sum: Volume + Price + Mix = Q_1*P_0 - Q_0*P_0 + P_1*Q_0 - P_0*Q_0 + P_1*Q_1 - P_1*Q_0 - P_0*Q_1 + P_0*Q_0
                               = P_1*Q_1 - P_0*Q_0 = C_1 - C_0 = ΔC.

The identity is verified numerically to within a tight tolerance (e.g., 1e-4).
"""

from __future__ import annotations

import logging
from dataclasses import asdict, dataclass, field
from typing import Any

import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class PriceVolumeMixItem:
    """Item-level price-volume-mix decomposition."""

    item_id: str
    baseline_cost: float
    actual_cost: float
    delta_cost: float
    baseline_quantity: float
    actual_quantity: float
    delta_quantity: float
    baseline_rate: float
    actual_rate: float
    delta_rate: float
    volume_effect: float
    price_effect: float
    mix_effect: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class PriceVolumeMixResult:
    """Aggregate result of price-volume-mix decomposition with identity verification."""

    total_baseline_cost: float
    total_actual_cost: float
    total_delta_cost: float
    volume_effect: float
    price_effect: float
    mix_effect: float
    volume_share: float  # volume_effect / total_delta_cost if total_delta_cost != 0 else 0
    price_share: float   # price_effect / total_delta_cost if total_delta_cost != 0 else 0
    mix_share: float     # mix_effect / total_delta_cost if total_delta_cost != 0 else 0
    identity_holds: bool
    discrepancy: float
    tolerance: float = 1e-4
    item_breakdowns: list[PriceVolumeMixItem] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["item_breakdowns"] = [b.to_dict() for b in self.item_breakdowns]
        return d


class PriceVolumeMixDecomposer:
    """Performs rate-volume-mix decomposition across items/services."""

    def __init__(self, tolerance: float = 1e-4) -> None:
        self.tolerance = tolerance

    def decompose_values(
        self,
        baseline_cost: float,
        baseline_quantity: float,
        actual_cost: float,
        actual_quantity: float,
        item_id: str = "TOTAL",
    ) -> PriceVolumeMixResult:
        """Decompose single aggregate or item values."""
        b_cost = float(baseline_cost)
        a_cost = float(actual_cost)
        delta_cost = a_cost - b_cost

        b_qty = float(baseline_quantity)
        a_qty = float(actual_quantity)
        delta_qty = a_qty - b_qty

        # Derive effective rates (unit prices)
        if b_qty > 0:
            b_rate = b_cost / b_qty
        elif a_qty > 0:
            b_rate = a_cost / a_qty  # Fallback to actual rate if baseline was zero
        else:
            b_rate = 0.0

        if a_qty > 0:
            a_rate = a_cost / a_qty
        elif b_qty > 0:
            a_rate = b_cost / b_qty  # Fallback to baseline rate if actual was zero
        else:
            a_rate = 0.0

        delta_rate = a_rate - b_rate

        # Three-way decomposition
        volume_effect = delta_qty * b_rate
        price_effect = delta_rate * b_qty
        mix_effect = delta_rate * delta_qty

        # Verify identity
        reconstructed = volume_effect + price_effect + mix_effect
        discrepancy = abs(delta_cost - reconstructed)
        identity_holds = discrepancy <= self.tolerance

        vol_share = volume_effect / delta_cost if abs(delta_cost) > 1e-9 else 0.0
        price_share = price_effect / delta_cost if abs(delta_cost) > 1e-9 else 0.0
        mix_share = mix_effect / delta_cost if abs(delta_cost) > 1e-9 else 0.0

        item = PriceVolumeMixItem(
            item_id=item_id,
            baseline_cost=b_cost,
            actual_cost=a_cost,
            delta_cost=delta_cost,
            baseline_quantity=b_qty,
            actual_quantity=a_qty,
            delta_quantity=delta_qty,
            baseline_rate=b_rate,
            actual_rate=a_rate,
            delta_rate=delta_rate,
            volume_effect=volume_effect,
            price_effect=price_effect,
            mix_effect=mix_effect,
        )

        return PriceVolumeMixResult(
            total_baseline_cost=b_cost,
            total_actual_cost=a_cost,
            total_delta_cost=delta_cost,
            volume_effect=volume_effect,
            price_effect=price_effect,
            mix_effect=mix_effect,
            volume_share=vol_share,
            price_share=price_share,
            mix_share=mix_share,
            identity_holds=identity_holds,
            discrepancy=discrepancy,
            tolerance=self.tolerance,
            item_breakdowns=[item],
        )

    def decompose(
        self,
        baseline_df: pd.DataFrame,
        actual_df: pd.DataFrame,
        cost_col: str = "BilledCost",
        quantity_col: str = "ConsumedQuantity",
        item_col: str = "ServiceName",
    ) -> PriceVolumeMixResult:
        """Decompose cost changes across items in dataframes.

        Aggregates baseline and actual periods per item, calculates item-level
        effects, and sums across all items to produce aggregate result.
        """
        # Group baseline
        if item_col in baseline_df.columns:
            b_grouped = baseline_df.groupby(item_col).agg(
                cost=(cost_col, "sum"),
                quantity=(quantity_col, "sum") if quantity_col in baseline_df.columns else (cost_col, lambda _: 1.0),
            ).reset_index()
        else:
            b_grouped = pd.DataFrame([{
                item_col: "ALL",
                "cost": baseline_df[cost_col].sum() if cost_col in baseline_df.columns else 0.0,
                "quantity": baseline_df[quantity_col].sum() if quantity_col in baseline_df.columns else 1.0,
            }])

        # Group actual
        if item_col in actual_df.columns:
            a_grouped = actual_df.groupby(item_col).agg(
                cost=(cost_col, "sum"),
                quantity=(quantity_col, "sum") if quantity_col in actual_df.columns else (cost_col, lambda _: 1.0),
            ).reset_index()
        else:
            a_grouped = pd.DataFrame([{
                item_col: "ALL",
                "cost": actual_df[cost_col].sum() if cost_col in actual_df.columns else 0.0,
                "quantity": actual_df[quantity_col].sum() if quantity_col in actual_df.columns else 1.0,
            }])

        merged = pd.merge(
            b_grouped,
            a_grouped,
            on=item_col,
            how="outer",
            suffixes=("_baseline", "_actual"),
        ).fillna(0.0)

        items: list[PriceVolumeMixItem] = []
        tot_b_cost = 0.0
        tot_a_cost = 0.0
        tot_vol_effect = 0.0
        tot_price_effect = 0.0
        tot_mix_effect = 0.0

        for _, row in merged.iterrows():
            item_id = str(row[item_col])
            b_cost = float(row["cost_baseline"])
            a_cost = float(row["cost_actual"])
            delta_cost = a_cost - b_cost

            b_qty = float(row["quantity_baseline"])
            a_qty = float(row["quantity_actual"])
            delta_qty = a_qty - b_qty

            if b_qty > 0:
                b_rate = b_cost / b_qty
            elif a_qty > 0:
                b_rate = a_cost / a_qty
            else:
                b_rate = 0.0

            if a_qty > 0:
                a_rate = a_cost / a_qty
            elif b_qty > 0:
                a_rate = b_cost / b_qty
            else:
                a_rate = 0.0

            delta_rate = a_rate - b_rate

            vol_eff = delta_qty * b_rate
            price_eff = delta_rate * b_qty
            mix_eff = delta_rate * delta_qty

            tot_b_cost += b_cost
            tot_a_cost += a_cost
            tot_vol_effect += vol_eff
            tot_price_effect += price_eff
            tot_mix_effect += mix_eff

            items.append(
                PriceVolumeMixItem(
                    item_id=item_id,
                    baseline_cost=b_cost,
                    actual_cost=a_cost,
                    delta_cost=delta_cost,
                    baseline_quantity=b_qty,
                    actual_quantity=a_qty,
                    delta_quantity=delta_qty,
                    baseline_rate=b_rate,
                    actual_rate=a_rate,
                    delta_rate=delta_rate,
                    volume_effect=vol_eff,
                    price_effect=price_eff,
                    mix_effect=mix_eff,
                )
            )

        total_delta = tot_a_cost - tot_b_cost
        reconstructed = tot_vol_effect + tot_price_effect + tot_mix_effect
        discrepancy = abs(total_delta - reconstructed)
        identity_holds = discrepancy <= self.tolerance

        vol_share = tot_vol_effect / total_delta if abs(total_delta) > 1e-9 else 0.0
        price_share = tot_price_effect / total_delta if abs(total_delta) > 1e-9 else 0.0
        mix_share = tot_mix_effect / total_delta if abs(total_delta) > 1e-9 else 0.0

        return PriceVolumeMixResult(
            total_baseline_cost=tot_b_cost,
            total_actual_cost=tot_a_cost,
            total_delta_cost=total_delta,
            volume_effect=tot_vol_effect,
            price_effect=tot_price_effect,
            mix_effect=tot_mix_effect,
            volume_share=vol_share,
            price_share=price_share,
            mix_share=mix_share,
            identity_holds=identity_holds,
            discrepancy=discrepancy,
            tolerance=self.tolerance,
            item_breakdowns=items,
        )
