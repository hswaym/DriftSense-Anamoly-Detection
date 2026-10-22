"""Data quality validators for cloud billing series."""

from __future__ import annotations

from typing import Any

import pandas as pd


def check_duplicates(
    df: pd.DataFrame,
    subset: list[str] | None = None,
) -> dict[str, Any]:
    """Check for duplicate rows based on canonical key."""
    if df.empty:
        return {"duplicate_count": 0, "duplicate_ratio": 0.0, "total_rows": 0}

    keys = subset or [
        c for c in ["ChargePeriodStart", "ServiceName", "ResourceId", "SubAccountId"]
        if c in df.columns
    ]
    if not keys:
        keys = list(df.columns)

    df.duplicated(subset=keys, keep=False)
    dup_count = int(df.duplicated(subset=keys, keep="first").sum())
    total_rows = len(df)
    ratio = round(dup_count / total_rows, 4) if total_rows > 0 else 0.0

    return {
        "duplicate_count": dup_count,
        "duplicate_ratio": ratio,
        "total_rows": total_rows,
        "checked_keys": keys,
    }


def check_missing_days(df: pd.DataFrame, date_col: str = "ChargePeriodStart") -> dict[str, Any]:
    """Check for missing calendar days in the chronological time span."""
    if df.empty or date_col not in df.columns:
        return {"missing_days_count": 0, "expected_days": 0, "observed_days": 0, "missing_dates": []}

    dts = pd.to_datetime(df[date_col], utc=True, errors="coerce").dropna()
    if dts.empty:
        return {"missing_days_count": 0, "expected_days": 0, "observed_days": 0, "missing_dates": []}

    min_date = dts.min().floor("D")
    max_date = dts.max().floor("D")
    expected_range = pd.date_range(min_date, max_date, freq="D", tz="UTC")
    expected_days_count = len(expected_range)

    observed_days = set(dts.dt.floor("D").unique())
    missing = sorted(set(expected_range) - observed_days)
    missing_strs = [d.strftime("%Y-%m-%d") for d in missing]

    return {
        "missing_days_count": len(missing),
        "expected_days": expected_days_count,
        "observed_days": len(observed_days),
        "min_date": min_date.strftime("%Y-%m-%d"),
        "max_date": max_date.strftime("%Y-%m-%d"),
        "missing_dates": missing_strs,
    }


def check_untagged_share(df: pd.DataFrame, tags_col: str = "Tags") -> dict[str, Any]:
    """Check the proportion of records lacking resource tags."""
    if df.empty or tags_col not in df.columns:
        return {"untagged_count": 0, "untagged_ratio": 0.0, "tagged_ratio": 1.0}

    total = len(df)
    def is_empty_tags(val: Any) -> bool:
        if pd.isna(val) or val is None:
            return True
        s = str(val).strip()
        return s in ("", "{}", "nan", "None", "[]")

    untagged_count = int(df[tags_col].apply(is_empty_tags).sum())
    untagged_ratio = round(untagged_count / total, 4) if total > 0 else 0.0

    return {
        "untagged_count": untagged_count,
        "untagged_ratio": untagged_ratio,
        "tagged_ratio": round(1.0 - untagged_ratio, 4),
        "total_rows": total,
    }


def check_unit_conflicts(
    df: pd.DataFrame,
    service_col: str = "ServiceName",
    unit_col: str = "ConsumedUnit",
) -> dict[str, Any]:
    """Check whether any service has conflicting or multiple usage units."""
    if df.empty or service_col not in df.columns or unit_col not in df.columns:
        return {"conflicting_services_count": 0, "conflicts": {}}

    conflicts: dict[str, list[str]] = {}
    grouped = df.groupby(service_col)[unit_col].unique()

    for service, units in grouped.items():
        clean_units = [str(u).strip() for u in units if pd.notna(u) and str(u).strip() != ""]
        clean_unique = sorted(set(clean_units))
        if len(clean_unique) > 1:
            conflicts[str(service)] = clean_unique

    return {
        "conflicting_services_count": len(conflicts),
        "conflicts": conflicts,
    }


def check_negative_costs(
    df: pd.DataFrame,
    cost_col: str = "EffectiveCost",
) -> dict[str, Any]:
    """Check for negative cost values representing refunds or credit adjustments."""
    if df.empty or cost_col not in df.columns:
        return {"negative_count": 0, "negative_ratio": 0.0, "total_negative_sum": 0.0}

    costs = pd.to_numeric(df[cost_col], errors="coerce").fillna(0.0)
    neg_mask = costs < 0
    neg_count = int(neg_mask.sum())
    total = len(df)
    ratio = round(neg_count / total, 4) if total > 0 else 0.0
    neg_sum = round(float(costs[neg_mask].sum()), 2)

    return {
        "negative_count": neg_count,
        "negative_ratio": ratio,
        "total_negative_sum": neg_sum,
        "total_rows": total,
    }


def check_currency_consistency(
    df: pd.DataFrame,
    currency_col: str = "Currency",
) -> dict[str, Any]:
    """Check for presence of multiple currencies."""
    if df.empty or currency_col not in df.columns:
        return {"is_multi_currency": False, "currencies": ["USD"]}

    clean_curr = (
        df[currency_col].dropna().astype(str).str.strip().str.upper().replace({"": "USD"})
    )
    unique_currencies = sorted(set(clean_curr.unique()) - {"NAN"})

    is_multi = len(unique_currencies) > 1
    return {
        "is_multi_currency": is_multi,
        "currency_count": len(unique_currencies),
        "currencies": unique_currencies,
    }


def check_timestamp_gaps(
    df: pd.DataFrame,
    time_col: str = "ChargePeriodStart",
    service_col: str = "ServiceName",
) -> dict[str, Any]:
    """Check for irregular timestamp intervals or temporal gaps (>1h) per service."""
    if df.empty or time_col not in df.columns or service_col not in df.columns:
        return {"gap_count": 0, "services_with_gaps": []}

    gap_count = 0
    services_with_gaps: list[str] = []

    for s_name, group in df.groupby(service_col):
        dts = pd.to_datetime(group[time_col], utc=True, errors="coerce").dropna().sort_values()
        if len(dts) < 2:
            continue
        diffs = dts.diff().dropna()
        # Any gap > 1 hour and 15 mins (allowing slight clock jitter)
        large_gaps = (diffs > pd.Timedelta(hours=1, minutes=15)).sum()
        if large_gaps > 0:
            gap_count += int(large_gaps)
            services_with_gaps.append(str(s_name))

    return {
        "gap_count": gap_count,
        "services_with_gaps": sorted(set(services_with_gaps)),
    }
