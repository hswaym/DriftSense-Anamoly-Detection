"""Dataset validation, schema compliance, and data quality reporting."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from driftsense.data.schemas import FOCUS_CORE_COLUMNS


def validate_dataset(
    data_path: str | Path,
    output_report_path: str | Path | None = None,
    time_col: str = "ChargePeriodStart",
    series_col: str = "ServiceName",
    cost_cols: list[str] | None = None,
    events_path: str | Path | None = None,
) -> dict[str, Any]:
    """Validate FOCUS dataset against quality and integrity standards.

    Checks:
    - Schema compliance and presence of core FOCUS columns
    - Valid UTC timestamp parsing
    - Monotonic chronological order per service series
    - Duplicate detection
    - Non-negative and non-null cost enforcement
    - Unit consistency
    - Missingness breakdown per column
    - Join-key coverage with operational events if supplied

    Emits:
    - Machine-readable data_quality_report.json
    """
    path = Path(data_path)
    if not path.is_file():
        raise FileNotFoundError(f"Dataset file not found for validation: {path}")

    # Load dataframe
    if path.suffix == ".gz" or str(path).endswith(".csv.gz"):
        df = pd.read_csv(path, compression="gzip", low_memory=False)
    else:
        df = pd.read_csv(path, low_memory=False)

    total_rows = len(df)
    total_cols = len(df.columns)
    issues: list[str] = []
    checks: dict[str, Any] = {}

    if cost_cols is None:
        cost_cols = ["EffectiveCost", "BilledCost"]

    # 1. Core column presence check
    missing_core = [col for col in FOCUS_CORE_COLUMNS if col not in df.columns]
    checks["core_columns_present"] = len(missing_core) == 0
    checks["missing_core_columns"] = missing_core
    if missing_core:
        issues.append(f"Missing core FOCUS columns: {missing_core}")

    # 2. Missingness report
    missingness = {}
    for col in df.columns:
        null_count = int(df[col].isna().sum())
        missingness[col] = {
            "null_count": null_count,
            "null_pct": round((null_count / total_rows) * 100, 2)
            if total_rows > 0
            else 0.0,
        }
    checks["missingness_report"] = missingness

    # 3. Duplicate row check
    duplicate_count = int(df.duplicated().sum())
    checks["duplicate_rows_count"] = duplicate_count
    if duplicate_count > 0:
        issues.append(f"Found {duplicate_count} duplicate rows in dataset.")

    # 4. Timestamp parsing and UTC validation
    timestamp_valid = False
    if time_col in df.columns:
        try:
            # Parse timestamps with UTC enforcement
            parsed_ts = pd.to_datetime(df[time_col], utc=True)
            checks["timestamp_parse_utc"] = True
            checks["earliest_timestamp"] = str(parsed_ts.min())
            checks["latest_timestamp"] = str(parsed_ts.max())
            timestamp_valid = True
        except (ValueError, TypeError, pd.errors.ParserError) as e:
            checks["timestamp_parse_utc"] = False
            issues.append(f"Failed to parse '{time_col}' to UTC timestamps: {e}")
    else:
        issues.append(f"Time column '{time_col}' missing from dataset.")

    # 5. Monotonic chronological order per series
    monotonic_order_valid = True
    non_monotonic_services: list[str] = []
    if timestamp_valid and series_col in df.columns:
        temp_df = df.copy()
        temp_df["_dt"] = pd.to_datetime(temp_df[time_col], utc=True)
        for service, group in temp_df.groupby(series_col):
            if not group["_dt"].is_monotonic_increasing:
                monotonic_order_valid = False
                non_monotonic_services.append(str(service))
    checks["monotonic_order_per_series"] = monotonic_order_valid
    checks["non_monotonic_services"] = non_monotonic_services
    if not monotonic_order_valid:
        issues.append(
            f"Series not strictly monotonically increasing for services: {non_monotonic_services[:5]}"
        )

    # 6. Cost metrics validity (non-null, non-negative)
    cost_validity: dict[str, Any] = {}
    for c_col in cost_cols:
        if c_col in df.columns:
            # Coerce to float
            cost_series = pd.to_numeric(df[c_col], errors="coerce")
            null_cost = int(cost_series.isna().sum())
            neg_cost = int((cost_series < 0).sum())
            cost_validity[c_col] = {
                "null_count": null_cost,
                "negative_count": neg_cost,
                "min": float(cost_series.min())
                if not cost_series.isna().all()
                else None,
                "max": float(cost_series.max())
                if not cost_series.isna().all()
                else None,
                "mean": float(cost_series.mean())
                if not cost_series.isna().all()
                else None,
            }
            if null_cost > 0:
                issues.append(
                    f"Cost column '{c_col}' contains {null_cost} null values."
                )
            if neg_cost > 0:
                # In billing, refunds can occur, but must be flagged
                issues.append(
                    f"Cost column '{c_col}' contains {neg_cost} negative values (credits/refunds)."
                )
    checks["cost_validity"] = cost_validity

    # 7. Unit consistency check
    unit_consistency: dict[str, Any] = {}
    if "ConsumedUnit" in df.columns and series_col in df.columns:
        for service, group in df.groupby(series_col):
            distinct_units = [str(u) for u in group["ConsumedUnit"].dropna().unique()]
            unit_consistency[str(service)] = distinct_units
    checks["service_consumed_units"] = unit_consistency

    # 8. Join-key coverage with operational events if provided
    if events_path:
        ev_path = Path(events_path)
        if ev_path.is_file():
            ev_df = pd.read_csv(ev_path)
            if series_col in df.columns and "service_id" in ev_df.columns:
                cost_services = set(df[series_col].dropna().unique())
                event_services = set(ev_df["service_id"].dropna().unique())
                matched = event_services.intersection(cost_services)
                checks["join_key_coverage"] = {
                    "total_event_services": len(event_services),
                    "matched_services": len(matched),
                    "unmatched_event_services": list(event_services - cost_services),
                }

    report = {
        "status": "PASSED" if len(issues) == 0 else "WARNINGS",
        "file": str(path),
        "total_rows": total_rows,
        "total_columns": total_cols,
        "checks": checks,
        "issues": issues,
    }

    if output_report_path:
        out_p = Path(output_report_path)
        out_p.parent.mkdir(parents=True, exist_ok=True)
        with out_p.open("w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)

    return report
