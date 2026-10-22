"""Google Cloud Billing Export (BigQuery format) Ingestion Adapter."""

from __future__ import annotations

import pandas as pd

from driftsense.ingest.canonical import enforce_canonical_types, normalize_tags_json

GCP_COST_MAP: dict[str, str] = {
    "cost": "BilledCost",
    "usage_start_time": "ChargePeriodStart",
    "usage_end_time": "ChargePeriodEnd",
    "usage.amount": "ConsumedQuantity",
    "usage_amount": "ConsumedQuantity",
    "usage.unit": "ConsumedUnit",
    "usage_unit": "ConsumedUnit",
    "service.description": "ServiceName",
    "service_description": "ServiceName",
    "project.id": "SubAccountId",
    "project_id": "SubAccountId",
    "project.name": "SubAccountName",
    "project_name": "SubAccountName",
    "location.region": "RegionId",
    "region": "RegionId",
    "currency": "Currency",
    "labels": "Tags",
}


def adapt_gcp_data(
    df: pd.DataFrame,
    tenant_id: str = "00000000-0000-0000-0000-000000000000",
    default_currency: str = "USD",
    handle_refunds: str = "include",
) -> pd.DataFrame:
    """Transform GCP Cloud Billing export DataFrame into validated canonical FOCUS representation."""
    out = pd.DataFrame()

    # 1. Map columns
    for gcp_col, canon_col in GCP_COST_MAP.items():
        if gcp_col in df.columns and canon_col not in out.columns:
            out[canon_col] = df[gcp_col]

    # EffectiveCost calculation (BilledCost + credits)
    if "BilledCost" in out.columns:
        credit_col = None
        for cand in ["credits.amount", "credits_amount", "credit"]:
            if cand in df.columns:
                credit_col = cand
                break
        if credit_col:
            credits = pd.to_numeric(df[credit_col], errors="coerce").fillna(0.0)
            out["EffectiveCost"] = pd.to_numeric(out["BilledCost"], errors="coerce").fillna(0.0) + credits
        else:
            out["EffectiveCost"] = out["BilledCost"]

    # Provider
    out["ProviderName"] = "GCP"

    # ConsumedUnit fallback
    if "ConsumedUnit" not in out.columns:
        out["ConsumedUnit"] = "Requests"

    # Tags normalization
    if "Tags" in out.columns:
        out["Tags"] = out["Tags"].apply(normalize_tags_json)
    else:
        out["Tags"] = "{}"

    # ChargeCategory
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
