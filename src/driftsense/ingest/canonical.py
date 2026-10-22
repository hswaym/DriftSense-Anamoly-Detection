"""Canonical FOCUS-aligned data schema definitions and data contracts.

Enforces standardized multi-cloud billing representations for DriftSense v2.
"""

from __future__ import annotations

import json
from typing import Any

import pandas as pd

CANONICAL_COLUMNS: list[str] = [
    "record_id",
    "tenant_id",
    "ProviderName",
    "ChargePeriodStart",
    "ChargePeriodEnd",
    "BilledCost",
    "EffectiveCost",
    "ListCost",
    "ContractedCost",
    "ConsumedQuantity",
    "ConsumedUnit",
    "PricingQuantity",
    "PricingUnit",
    "ServiceName",
    "ServiceCategory",
    "SubAccountId",
    "SubAccountName",
    "ResourceId",
    "RegionId",
    "ChargeCategory",
    "ChargeClass",
    "CommitmentDiscountCategory",
    "Currency",
    "Tags",
]

REQUIRED_CANONICAL_COLUMNS: list[str] = [
    "record_id",
    "tenant_id",
    "ProviderName",
    "ChargePeriodStart",
    "ChargePeriodEnd",
    "BilledCost",
    "EffectiveCost",
    "ConsumedQuantity",
    "ConsumedUnit",
    "ServiceName",
    "SubAccountId",
    "ChargeCategory",
    "Currency",
]


def enforce_canonical_types(
    df: pd.DataFrame,
    tenant_id: str = "00000000-0000-0000-0000-000000000000",
    default_currency: str = "USD",
) -> pd.DataFrame:
    """Normalize and enforce canonical types and invariants on DataFrame."""
    out = df.copy()

    # 1. Ensure required columns exist
    if "record_id" not in out.columns or out["record_id"].isnull().all():
        out["record_id"] = [f"rec_{i:08d}" for i in range(len(out))]
    if "tenant_id" not in out.columns:
        out["tenant_id"] = tenant_id

    # 2. Datetime normalization (UTC ISO-8601)
    for dt_col in ["ChargePeriodStart", "ChargePeriodEnd"]:
        if dt_col in out.columns:
            out[dt_col] = pd.to_datetime(out[dt_col], utc=True, errors="coerce")
            if out[dt_col].isnull().any():
                invalid_count = out[dt_col].isnull().sum()
                raise ValueError(
                    f"Column '{dt_col}' contains {invalid_count} unparseable datetime entries. UTC timestamps required."
                )

    # Invariant: ChargePeriodEnd > ChargePeriodStart
    if "ChargePeriodStart" in out.columns and "ChargePeriodEnd" in out.columns:
        invalid_intervals = out["ChargePeriodEnd"] <= out["ChargePeriodStart"]
        if invalid_intervals.any():
            # If equal, default end to start + 1h
            out.loc[invalid_intervals, "ChargePeriodEnd"] = out.loc[
                invalid_intervals, "ChargePeriodStart"
            ] + pd.Timedelta(hours=1)

    # 3. Numeric columns
    num_cols = [
        "BilledCost",
        "EffectiveCost",
        "ListCost",
        "ContractedCost",
        "ConsumedQuantity",
        "PricingQuantity",
    ]
    for n_col in num_cols:
        if n_col in out.columns:
            out[n_col] = pd.to_numeric(out[n_col], errors="coerce").fillna(0.0)

    # 4. String / Categorical columns
    str_cols = [
        "record_id",
        "tenant_id",
        "ProviderName",
        "ServiceName",
        "ServiceCategory",
        "SubAccountId",
        "SubAccountName",
        "ResourceId",
        "RegionId",
        "ChargeCategory",
        "ChargeClass",
        "CommitmentDiscountCategory",
        "ConsumedUnit",
        "PricingUnit",
    ]
    for s_col in str_cols:
        if s_col in out.columns:
            out[s_col] = out[s_col].astype(str).replace({"nan": "", "None": ""})
        else:
            out[s_col] = ""

    # 5. Currency enforcement
    if "Currency" not in out.columns or out["Currency"].isnull().all():
        out["Currency"] = default_currency
    else:
        out["Currency"] = out["Currency"].astype(str).str.strip().str.upper()
        unique_currencies = set(out["Currency"].unique()) - {"", "NAN"}
        if len(unique_currencies) > 1:
            raise ValueError(
                f"Multi-currency billing detected: {sorted(unique_currencies)}. "
                "DriftSense v2 strictly enforces single-currency datasets per tenant."
            )
        if len(unique_currencies) == 1:
            out["Currency"] = next(iter(unique_currencies))

    # 6. Tags column JSON normalization
    if "Tags" not in out.columns:
        out["Tags"] = "{}"
    else:
        out["Tags"] = out["Tags"].apply(normalize_tags_json)

    # 7. Select canonical columns only (preserve order)
    present_canon = [c for c in CANONICAL_COLUMNS if c in out.columns]
    return out[present_canon]


def normalize_tags_json(val: Any) -> str:
    """Normalize raw tags input into a valid JSON string."""
    if pd.isna(val) or val is None or val == "" or str(val).strip() in ("{}", "nan", "None"):
        return "{}"
    if isinstance(val, dict):
        return json.dumps(val, sort_keys=True)
    if isinstance(val, str):
        val_str = val.strip()
        if val_str.startswith("{") and val_str.endswith("}"):
            try:
                parsed = json.loads(val_str)
                if isinstance(parsed, dict):
                    return json.dumps(parsed, sort_keys=True)
            except (json.JSONDecodeError, ValueError):
                return "{}"
        # If key=value format (e.g. AWS user:Env=Prod | user:App=API)
        if "=" in val_str:
            items = {}
            for token in val_str.replace(";", "|").replace(",", "|").split("|"):
                if "=" in token:
                    k, v = token.split("=", 1)
                    items[k.strip()] = v.strip()
            if items:
                return json.dumps(items, sort_keys=True)
    return "{}"
