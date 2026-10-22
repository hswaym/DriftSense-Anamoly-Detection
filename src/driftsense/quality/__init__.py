"""Data quality evaluation module for DriftSense v2."""

from __future__ import annotations

from driftsense.quality.report import generate_quality_report
from driftsense.quality.score import (
    QualityDeduction,
    QualityScoreResult,
    calculate_quality_score,
)
from driftsense.quality.validators import (
    check_currency_consistency,
    check_duplicates,
    check_missing_days,
    check_negative_costs,
    check_timestamp_gaps,
    check_unit_conflicts,
    check_untagged_share,
)

__all__ = [
    "QualityDeduction",
    "QualityScoreResult",
    "calculate_quality_score",
    "check_currency_consistency",
    "check_duplicates",
    "check_missing_days",
    "check_negative_costs",
    "check_timestamp_gaps",
    "check_unit_conflicts",
    "check_untagged_share",
    "generate_quality_report",
]
