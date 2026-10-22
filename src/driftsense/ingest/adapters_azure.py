"""Microsoft Azure Cost Management Export Ingestion Adapter."""

from __future__ import annotations

import pandas as pd

from driftsense.ingest.canonical import enforce_canonical_types, normalize_tags_json

AZURE_COST_MAP: dict[str, str] = {
    "Date": "ChargePeriodStart",
    "BillingPeriodStartDate": "ChargePeriodStart",
    "CostInBillingCurrency": "BilledCost",
    "UsageQuantity": "ConsumedQuantity",
    "UnitOfMeasure": "ConsumedUnit",
    "MeterCategory": "ServiceName",
    "SubscriptionId": "SubAccountId",
    "SubscriptionName": "SubAccountName",
    "ResourceId": "ResourceId",
    "ResourceLocation": "RegionId",
    "ChargeType": "ChargeCategory",
    "BillingCurrency": "Currency",
    "Tags": "Tags",
}


def adapt_azure_data(
    df: pd.DataFrame,
    tenant_id: str = "00000000-0000-0000-0000-000000000000",
    default_currency: str = "USD",
    handle_refunds: str = "include",
) -> pd.DataFrame:
    """Transform Azure Cost Management export DataFrame into validated canonical FOCUS representation."""
    out = pd.DataFrame()

    # 1. Map columns
    for azure_col, canon_col in AZURE_COST_MAP.items():
        if azure_col in df.columns and canon_col not in out.columns:
            out[canon_col] = df[azure_col]

    # EffectiveCost defaults to CostInBillingCurrency / BilledCost
    if "EffectiveCost" not in out.columns and "BilledCost" in out.columns:
        out["EffectiveCost"] = out["BilledCost"]

    # Provider
    out["ProviderName"] = "Azure"

    # End date: If ChargePeriodStart exists, compute ChargePeriodEnd as start + 1h or 1d
    if "ChargePeriodStart" in out.columns:
        start_dt = pd.to_datetime(out["ChargePeriodStart"], utc=True, errors="coerce")
        out["ChargePeriodStart"] = start_dt
        if "ChargePeriodEnd" not in out.columns:
            out["ChargePeriodEnd"] = start_dt + pd.Timedelta(hours=1)

    # Tags normalization
    if "Tags" in out.columns:
        out["Tags"] = out["Tags"].apply(normalize_tags_json)
    else:
        out["Tags"] = "{}"

    # ChargeCategory
    if "ChargeCategory" not in out.columns:
        out["ChargeCategory"] = "Usage"

    # ConsumedUnit fallback
    if "ConsumedUnit" not in out.columns:
        out["ConsumedUnit"] = "Units"

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
