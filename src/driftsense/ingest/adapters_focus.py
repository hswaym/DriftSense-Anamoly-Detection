"""FOCUS Ingestion Adapter for FinOps Open Cost and Usage Specification (1.0–1.4)."""

from __future__ import annotations

import pandas as pd

from driftsense.ingest.canonical import enforce_canonical_types


def adapt_focus_data(
    df: pd.DataFrame,
    tenant_id: str = "00000000-0000-0000-0000-000000000000",
    default_currency: str = "USD",
    handle_refunds: str = "include",  # 'include', 'exclude', 'zero_clamp'
) -> pd.DataFrame:
    """Transform FOCUS raw DataFrame into validated canonical representation."""
    out = df.copy()

    # Normalize case of standard columns if slightly varied
    col_case_map = {
        c.lower(): c
        for c in [
            "ChargePeriodStart",
            "ChargePeriodEnd",
            "BilledCost",
            "EffectiveCost",
            "ConsumedQuantity",
            "ConsumedUnit",
            "ServiceName",
            "ProviderName",
            "SubAccountId",
            "ResourceId",
            "RegionId",
            "ChargeCategory",
            "Currency",
            "Tags",
        ]
    }
    rename_dict = {}
    for col in out.columns:
        low = col.lower()
        if low in col_case_map and col != col_case_map[low]:
            rename_dict[col] = col_case_map[low]
    if rename_dict:
        out = out.rename(columns=rename_dict)

    # ProviderName default
    if "ProviderName" not in out.columns:
        out["ProviderName"] = "FOCUS"

    # EffectiveCost fallback to BilledCost if missing
    if "EffectiveCost" not in out.columns and "BilledCost" in out.columns:
        out["EffectiveCost"] = out["BilledCost"]

    # ChargeCategory default
    if "ChargeCategory" not in out.columns:
        out["ChargeCategory"] = "Usage"

    # Refund / Negative adjustment handling
    if handle_refunds == "exclude":
        if "EffectiveCost" in out.columns:
            out = out[out["EffectiveCost"] >= 0].copy()
    elif handle_refunds == "zero_clamp":
        if "EffectiveCost" in out.columns:
            out["EffectiveCost"] = out["EffectiveCost"].clip(lower=0.0)
        if "BilledCost" in out.columns:
            out["BilledCost"] = out["BilledCost"].clip(lower=0.0)

    return enforce_canonical_types(out, tenant_id=tenant_id, default_currency=default_currency)
