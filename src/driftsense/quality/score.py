"""Deterministic data quality scoring engine (0–100) with plain-language rationales."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pandas as pd

from driftsense.quality.validators import (
    check_currency_consistency,
    check_duplicates,
    check_missing_days,
    check_negative_costs,
    check_timestamp_gaps,
    check_unit_conflicts,
    check_untagged_share,
)


@dataclass
class QualityDeduction:
    """Single quality score deduction."""
    category: str
    points_deducted: float
    plain_language_reason: str
    actionable_fix: str
    metrics: dict[str, Any] = field(default_factory=dict)


@dataclass
class QualityScoreResult:
    """Result of dataset quality assessment."""
    score: float  # 0.0 to 100.0
    grade: str   # 'A' (>=90), 'B' (>=75), 'C' (>=60), 'D' (>=40), 'F' (<40)
    total_deductions: float
    deductions: list[QualityDeduction]
    total_rows: int
    summary: str


def calculate_quality_score(df: pd.DataFrame) -> QualityScoreResult:
    """Compute deterministic data quality score (0–100) with plain-language explanations.

    Deductions:
    - Duplicates: up to -15 points (proportional to dup ratio * 1.5).
    - Missing days: up to -20 points (-2 points per missing day).
    - Untagged share: up to -15 points (untagged_ratio * 15).
    - Unit conflicts: up to -20 points (-10 points per service with conflicting units).
    - Negative costs: up to -10 points (negative_ratio * 100).
    - Multi-currency: -15 points if multiple currencies present.
    - Timestamp gaps: up to -10 points (-2 points per irregular gap).
    """
    total_rows = len(df)
    if total_rows == 0:
        return QualityScoreResult(
            score=0.0,
            grade="F",
            total_deductions=100.0,
            deductions=[
                QualityDeduction(
                    category="empty_dataset",
                    points_deducted=100.0,
                    plain_language_reason="Dataset contains 0 rows.",
                    actionable_fix="Upload a non-empty cloud billing export.",
                )
            ],
            total_rows=0,
            summary="Empty dataset. Quality score is 0.",
        )

    deductions: list[QualityDeduction] = []

    # 1. Duplicates
    dup_res = check_duplicates(df)
    dup_count = dup_res["duplicate_count"]
    dup_ratio = dup_res["duplicate_ratio"]
    if dup_count > 0:
        pts = round(min(15.0, dup_ratio * 100.0 * 1.5), 1)
        deductions.append(
            QualityDeduction(
                category="duplicates",
                points_deducted=pts,
                plain_language_reason=f"{dup_count} duplicate billing rows detected ({round(dup_ratio * 100, 1)}% of dataset).",
                actionable_fix="Enable deduplication during ingestion (--dedup drop) or verify source export job uniqueness.",
                metrics=dup_res,
            )
        )

    # 2. Missing Days
    miss_res = check_missing_days(df)
    missing_days = miss_res["missing_days_count"]
    if missing_days > 0:
        pts = round(min(20.0, missing_days * 2.0), 1)
        deductions.append(
            QualityDeduction(
                category="missing_days",
                points_deducted=pts,
                plain_language_reason=f"{missing_days} calendar days are completely missing from the billing history span.",
                actionable_fix="Backfill missing billing export days or review provider export schedule.",
                metrics=miss_res,
            )
        )

    # 3. Untagged Share
    tag_res = check_untagged_share(df)
    untagged_ratio = tag_res["untagged_ratio"]
    if untagged_ratio > 0.05:  # Tolerate up to 5% untagged without penalty
        pts = round(min(15.0, untagged_ratio * 15.0), 1)
        deductions.append(
            QualityDeduction(
                category="untagged_share",
                points_deducted=pts,
                plain_language_reason=f"{round(untagged_ratio * 100, 1)}% of cloud billing records lack cost allocation tags.",
                actionable_fix="Enforce organizational tagging policies on active infrastructure resources.",
                metrics=tag_res,
            )
        )

    # 4. Unit Conflicts
    unit_res = check_unit_conflicts(df)
    conflicts_count = unit_res["conflicting_services_count"]
    if conflicts_count > 0:
        pts = round(min(20.0, conflicts_count * 10.0), 1)
        deductions.append(
            QualityDeduction(
                category="unit_conflicts",
                points_deducted=pts,
                plain_language_reason=f"{conflicts_count} services report conflicting usage units across billing periods.",
                actionable_fix="Standardize unit descriptors or split the service across discrete usage types.",
                metrics=unit_res,
            )
        )

    # 5. Negative Costs
    neg_res = check_negative_costs(df)
    neg_count = neg_res["negative_count"]
    neg_ratio = neg_res["negative_ratio"]
    if neg_count > 0:
        pts = round(min(10.0, neg_ratio * 100.0 * 1.0), 1)
        deductions.append(
            QualityDeduction(
                category="negative_costs",
                points_deducted=pts,
                plain_language_reason=f"{neg_count} records contain negative cost adjustments or refunds (total: ${abs(neg_res['total_negative_sum'])}).",
                actionable_fix="Configure refund handling to 'exclude' or 'zero_clamp' in the ingestion configuration.",
                metrics=neg_res,
            )
        )

    # 6. Currency Consistency
    curr_res = check_currency_consistency(df)
    if curr_res["is_multi_currency"]:
        deductions.append(
            QualityDeduction(
                category="multi_currency",
                points_deducted=15.0,
                plain_language_reason=f"Multiple billing currencies detected ({curr_res['currencies']}). Single currency required.",
                actionable_fix="Convert all costs into a single reporting currency before model training.",
                metrics=curr_res,
            )
        )

    # 7. Timestamp Gaps
    gap_res = check_timestamp_gaps(df)
    gap_count = gap_res["gap_count"]
    if gap_count > 0:
        pts = round(min(10.0, gap_count * 2.0), 1)
        deductions.append(
            QualityDeduction(
                category="timestamp_gaps",
                points_deducted=pts,
                plain_language_reason=f"{gap_count} irregular timestamp gaps (>1h) detected within service series.",
                actionable_fix="Apply canonical hourly grain aggregation with zero-imputation policy.",
                metrics=gap_res,
            )
        )

    total_deducted = round(sum(d.points_deducted for d in deductions), 1)
    final_score = round(max(0.0, 100.0 - total_deducted), 1)

    if final_score >= 90.0:
        grade = "A"
    elif final_score >= 75.0:
        grade = "B"
    elif final_score >= 60.0:
        grade = "C"
    elif final_score >= 40.0:
        grade = "D"
    else:
        grade = "F"

    summary = (
        f"Data Quality Score: {final_score}/100 (Grade: {grade}). "
        f"Total deductions: -{total_deducted} across {len(deductions)} categories."
    )

    return QualityScoreResult(
        score=final_score,
        grade=grade,
        total_deductions=total_deducted,
        deductions=deductions,
        total_rows=total_rows,
        summary=summary,
    )
