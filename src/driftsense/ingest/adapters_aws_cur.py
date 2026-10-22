"""AWS Cost and Usage Report (CUR 2.0 / Data Exports) Ingestion Adapter."""

from __future__ import annotations

import json

import pandas as pd

from driftsense.ingest.canonical import enforce_canonical_types

AWS_CUR_MAP: dict[str, str] = {
    "lineItem/UsageStartDate": "ChargePeriodStart",
    "lineItem/UsageEndDate": "ChargePeriodEnd",
    "lineItem/UnblendedCost": "BilledCost",
    "lineItem/NetUnblendedCost": "EffectiveCost",
    "lineItem/UsageAmount": "ConsumedQuantity",
    "pricing/unit": "ConsumedUnit",
    "product/servicecode": "ServiceName",
    "lineItem/UsageAccountId": "SubAccountId",
    "lineItem/ResourceId": "ResourceId",
    "product/region": "RegionId",
    "lineItem/LineItemType": "ChargeCategory",
    "lineItem/CurrencyCode": "Currency",
}


def adapt_aws_cur_data(
    df: pd.DataFrame,
    tenant_id: str = "00000000-0000-0000-0000-000000000000",
    default_currency: str = "USD",
    handle_refunds: str = "include",
) -> pd.DataFrame:
    """Transform AWS CUR DataFrame into validated canonical FOCUS representation."""
    out = pd.DataFrame()

    # 1. Map core columns
    for aws_col, canon_col in AWS_CUR_MAP.items():
        if aws_col in df.columns:
            out[canon_col] = df[aws_col]

    # EffectiveCost fallback
    if "EffectiveCost" not in out.columns and "BilledCost" in out.columns:
        out["EffectiveCost"] = out["BilledCost"]

    # Provider
    out["ProviderName"] = "AWS"

    # ConsumedUnit fallback
    if "ConsumedUnit" not in out.columns:
        out["ConsumedUnit"] = "Hrs"

    # 2. Parse resource tags (columns like 'resourceTags/user:Env' or 'resourceTags/aws:createdBy')
    tag_cols = [c for c in df.columns if c.startswith("resourceTags/")]
    if tag_cols:
        def extract_tags(row: pd.Series) -> str:
            tag_dict = {}
            for tc in tag_cols:
                val = row.get(tc)
                if pd.notna(val) and str(val).strip() != "":
                    # Clean prefix
                    clean_k = tc.replace("resourceTags/user:", "").replace("resourceTags/", "")
                    tag_dict[clean_k] = str(val)
            return json.dumps(tag_dict, sort_keys=True) if tag_dict else "{}"

        out["Tags"] = df[tag_cols].apply(extract_tags, axis=1)
    else:
        out["Tags"] = "{}"

    # ChargeCategory mapping
    if "ChargeCategory" in out.columns:
        category_map = {
            "Usage": "Usage",
            "SavingsPlanCoveredUsage": "Usage",
            "DiscountedUsage": "Usage",
            "Fee": "Purchase",
            "Tax": "Tax",
            "Refund": "Adjustment",
            "Credit": "Credit",
        }
        out["ChargeCategory"] = out["ChargeCategory"].map(
            lambda x: category_map.get(str(x), "Usage")
        )

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
