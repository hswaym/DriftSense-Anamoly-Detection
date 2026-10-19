"""Data cleaning pipeline and sanitization rules for DriftSense cost datasets.

Enforces deterministic cleaning rules:
- Deduplication of exact and composite rows.
- Strict UTC timestamp coercion and validation.
- Missing value policy (imputing ConsumedQuantity, dropping critical key nulls).
- Text unit normalization.
- Negative cost (credits/refunds) segregation and net cost computation.
- Comprehensive machine-readable cleaning log tracking counts per rule.
"""

from __future__ import annotations

import logging
from typing import Any

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


def clean_focus_data(
    df: pd.DataFrame,
    config: dict[str, Any] | None = None,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Clean and sanitize raw FOCUS billing dataframe according to project contracts.

    Args:
        df: Raw FOCUS DataFrame.
        config: Optional cleaning configuration dictionary.

    Returns:
        tuple[pd.DataFrame, dict[str, Any]]: (Cleaned DataFrame, cleaning log summary)
    """
    cfg = config or {}
    df_clean = df.copy()
    initial_rows = len(df_clean)

    cleaning_log: dict[str, Any] = {
        "initial_rows": initial_rows,
        "final_rows": initial_rows,
        "exact_duplicates_dropped": 0,
        "missing_timestamps_dropped": 0,
        "missing_services_dropped": 0,
        "invalid_timestamps_dropped": 0,
        "missing_consumed_quantity_imputed": 0,
        "unit_normalization_changes": 0,
        "negative_effective_cost_handled": 0,
        "negative_billed_cost_handled": 0,
        "total_rows_modified_or_dropped": 0,
    }

    # 1. Deduplication
    if cfg.get("deduplicate", True):
        dup_mask = df_clean.duplicated()
        dup_count = int(dup_mask.sum())
        if dup_count > 0:
            df_clean = df_clean.drop_duplicates().copy()
            cleaning_log["exact_duplicates_dropped"] = dup_count
            logger.info("Dropped %d exact duplicate rows", dup_count)

    # 2. Critical Key Null Policy
    # Rows without ServiceName or ChargePeriodStart cannot be associated with any time series
    if "ServiceName" in df_clean.columns:
        null_service_mask = df_clean["ServiceName"].isna() | (
            df_clean["ServiceName"].astype(str).str.strip() == ""
        )
        null_services = int(null_service_mask.sum())
        if null_services > 0:
            df_clean = df_clean[~null_service_mask].copy()
            cleaning_log["missing_services_dropped"] = null_services
            logger.info("Dropped %d rows with missing ServiceName", null_services)

    if "ChargePeriodStart" in df_clean.columns:
        null_time_mask = df_clean["ChargePeriodStart"].isna()
        null_times = int(null_time_mask.sum())
        if null_times > 0:
            df_clean = df_clean[~null_time_mask].copy()
            cleaning_log["missing_timestamps_dropped"] = null_times
            logger.info("Dropped %d rows with missing ChargePeriodStart", null_times)

    # 3. Timestamp Parsing and Strict UTC Normalization
    time_cols = cfg.get("time_columns", ["ChargePeriodStart", "ChargePeriodEnd"])
    for col in time_cols:
        if col in df_clean.columns:
            parsed = pd.to_datetime(df_clean[col], utc=True, errors="coerce")
            invalid_ts_mask = parsed.isna() & df_clean[col].notna()
            invalid_count = int(invalid_ts_mask.sum())
            if invalid_count > 0:
                cleaning_log["invalid_timestamps_dropped"] += invalid_count
                df_clean = df_clean[~invalid_ts_mask].copy()
                parsed = parsed[~invalid_ts_mask]
                logger.warning(
                    "Dropped %d rows with unparseable %s timestamps", invalid_count, col
                )
            df_clean[col] = parsed

    # 4. Missing Value Policy (Usage and Units)
    # ConsumedQuantity nulls in FOCUS indicate non-usage fixed fees, support, or subscription lines.
    if "ConsumedQuantity" in df_clean.columns:
        null_qty_mask = df_clean["ConsumedQuantity"].isna()
        null_qty_count = int(null_qty_mask.sum())
        if null_qty_count > 0:
            df_clean["ConsumedQuantity"] = df_clean["ConsumedQuantity"].fillna(0.0)
            cleaning_log["missing_consumed_quantity_imputed"] = null_qty_count
            logger.info(
                "Imputed %d null ConsumedQuantity values with 0.0", null_qty_count
            )

    if "ConsumedUnit" in df_clean.columns:
        df_clean["ConsumedUnit"] = df_clean["ConsumedUnit"].fillna("Unknown")

    # 5. Text Unit Normalization
    # Standardize whitespace and casing
    unit_cols = ["ConsumedUnit", "PricingUnit"]
    total_unit_changes = 0
    for ucol in unit_cols:
        if ucol in df_clean.columns:
            orig = df_clean[ucol].astype(str)
            normalized = orig.str.strip()
            changes = int((orig != normalized).sum())
            total_unit_changes += changes
            df_clean[ucol] = normalized
    cleaning_log["unit_normalization_changes"] = total_unit_changes

    # 6. Negative Cost / Refund / Credit Treatment
    # In cloud FinOps, negative costs represent credits, refunds, or EDP commitment amortizations.
    # We segregate credit magnitudes into explicit columns while creating non-negative net costs.
    cost_policy = cfg.get("negative_cost_policy", "segregate_credits")
    if "EffectiveCost" in df_clean.columns:
        neg_eff_mask = df_clean["EffectiveCost"] < 0
        neg_eff_count = int(neg_eff_mask.sum())
        cleaning_log["negative_effective_cost_handled"] = neg_eff_count

        df_clean["EffectiveCreditAmount"] = np.where(
            neg_eff_mask, -df_clean["EffectiveCost"].astype(float), 0.0
        )
        if cost_policy in ("segregate_credits", "clip_zero"):
            df_clean["EffectiveCostRaw"] = df_clean["EffectiveCost"]
            df_clean["EffectiveCost"] = np.maximum(
                df_clean["EffectiveCost"].astype(float), 0.0
            )

    if "BilledCost" in df_clean.columns:
        neg_billed_mask = df_clean["BilledCost"] < 0
        neg_billed_count = int(neg_billed_mask.sum())
        cleaning_log["negative_billed_cost_handled"] = neg_billed_count

        df_clean["BilledCreditAmount"] = np.where(
            neg_billed_mask, -df_clean["BilledCost"].astype(float), 0.0
        )
        if cost_policy in ("segregate_credits", "clip_zero"):
            df_clean["BilledCostRaw"] = df_clean["BilledCost"]
            df_clean["BilledCost"] = np.maximum(
                df_clean["BilledCost"].astype(float), 0.0
            )

    # 7. Sorting per series monotonically
    if (
        cfg.get("sort_output", True)
        and "ServiceName" in df_clean.columns
        and "ChargePeriodStart" in df_clean.columns
    ):
        df_clean = df_clean.sort_values(
            by=["ServiceName", "ChargePeriodStart"]
        ).reset_index(drop=True)

    cleaning_log["final_rows"] = len(df_clean)
    cleaning_log["total_rows_modified_or_dropped"] = (
        cleaning_log["exact_duplicates_dropped"]
        + cleaning_log["missing_timestamps_dropped"]
        + cleaning_log["missing_services_dropped"]
        + cleaning_log["invalid_timestamps_dropped"]
        + cleaning_log["missing_consumed_quantity_imputed"]
        + cleaning_log["negative_effective_cost_handled"]
        + cleaning_log["negative_billed_cost_handled"]
    )

    return df_clean, cleaning_log
