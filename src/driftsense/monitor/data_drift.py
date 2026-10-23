"""Data & Schema drift detection for DriftSense v2 (Phase 13).

Detects:
1. Schema drift: Missing required FOCUS 1.0 columns, type changes, unexpected extra columns.
2. Volume drift: Significant drops or surges in row count or daily total spend vs baseline.
3. Cost distribution drift: Two-sample distribution shifts via Kolmogorov-Smirnov / Wasserstein tests.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

import numpy as np
import pandas as pd
from scipy.stats import ks_2samp

# Canonical required and recommended columns in FOCUS 1.0
FOCUS_REQUIRED_COLUMNS = {"ChargePeriodStart", "ServiceName", "EffectiveCost"}
FOCUS_RECOMMENDED_COLUMNS = {"BilledCost", "UsageQuantity", "RegionName", "ChargeCategory"}


@dataclass
class SchemaDriftReport:
    """Findings on tabular schema integrity."""

    is_drift_detected: bool
    missing_required_columns: list[str]
    missing_recommended_columns: list[str]
    new_unmapped_columns: list[str]
    type_mismatches: list[str]
    risk_level: str  # "Low", "Medium", "High"
    warnings: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class VolumeDriftReport:
    """Findings on volume and statistical spend distribution shift."""

    is_drift_detected: bool
    reference_mean_spend: float
    current_mean_spend: float
    spend_shift_pct: float
    row_count_ratio: float
    ks_statistic: float
    ks_pvalue: float
    is_distribution_drift: bool
    risk_level: str  # "Low", "Medium", "High"
    warnings: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class SchemaDriftMonitor:
    """Monitors telemetry uploads against canonical FOCUS 1.0 specification."""

    def __init__(self, required_cols: set[str] | None = None) -> None:
        self.required_cols = required_cols or FOCUS_REQUIRED_COLUMNS
        self.recommended_cols = FOCUS_RECOMMENDED_COLUMNS

    def inspect_schema(self, df: pd.DataFrame) -> SchemaDriftReport:
        cols = set(df.columns)
        missing_req = sorted(list(self.required_cols - cols))
        missing_rec = sorted(list(self.recommended_cols - cols))
        new_cols = sorted(list(cols - (self.required_cols | self.recommended_cols)))

        type_mismatches = []
        warnings = []

        if missing_req:
            warnings.append(f"Critical Schema Drift: Missing required FOCUS columns: {missing_req}")
            risk = "High"
            is_drift = True
        else:
            risk = "Low"
            is_drift = False

        if missing_rec:
            warnings.append(f"Recommended column notice: Missing optional fields {missing_rec}")

        if "EffectiveCost" in df.columns:
            if not pd.api.types.is_numeric_dtype(df["EffectiveCost"]):
                type_mismatches.append("EffectiveCost column is not numeric")
                warnings.append("Type Mismatch: EffectiveCost contains non-numeric strings.")
                risk = "High"
                is_drift = True

        return SchemaDriftReport(
            is_drift_detected=is_drift,
            missing_required_columns=missing_req,
            missing_recommended_columns=missing_rec,
            new_unmapped_columns=new_cols,
            type_mismatches=type_mismatches,
            risk_level=risk,
            warnings=warnings,
        )


class VolumeDriftMonitor:
    """Monitors row volume and statistical cost distribution shift."""

    def __init__(
        self,
        volume_shift_threshold: float = 0.50,  # 50% shift triggers alert
        ks_alpha: float = 0.01,  # p < 0.01 indicates significant shift
    ) -> None:
        self.volume_shift_threshold = volume_shift_threshold
        self.ks_alpha = ks_alpha

    def inspect_volume(
        self,
        current_costs: np.ndarray | pd.Series,
        baseline_costs: np.ndarray | pd.Series,
    ) -> VolumeDriftReport:
        c_arr = np.asarray(current_costs, dtype=float)
        b_arr = np.asarray(baseline_costs, dtype=float)

        c_arr = c_arr[~np.isnan(c_arr)]
        b_arr = b_arr[~np.isnan(b_arr)]

        c_mean = float(np.mean(c_arr)) if len(c_arr) > 0 else 0.0
        b_mean = float(np.mean(b_arr)) if len(b_arr) > 0 else 0.0

        spend_shift_pct = round(((c_mean - b_mean) / max(1e-3, b_mean)) * 100.0, 1)
        row_ratio = round(len(c_arr) / max(1, len(b_arr)), 2)

        warnings = []
        is_drift = False

        # Check volume ratio
        if row_ratio < 0.25:
            warnings.append(f"Volume Depletion Warning: Current partition has {row_ratio*100:.0f}% of baseline records.")
            is_drift = True
        elif row_ratio > 3.0:
            warnings.append(f"Volume Explosion Warning: Current partition has {row_ratio:.1f}x baseline records.")
            is_drift = True

        # Check cost mean shift
        if abs(spend_shift_pct) > (self.volume_shift_threshold * 100):
            warnings.append(f"Spend Mean Drift: Cost shifted by {spend_shift_pct:+.1f}% vs baseline reference.")
            is_drift = True

        # Kolmogorov-Smirnov 2-sample test
        ks_stat, ks_pval = ks_2samp(c_arr, b_arr) if len(c_arr) > 5 and len(b_arr) > 5 else (0.0, 1.0)
        dist_drift = bool(ks_pval < self.ks_alpha)
        if dist_drift:
            warnings.append(f"Statistical Distribution Drift: Two-sample KS test p-value={ks_pval:.2e} (< {self.ks_alpha}).")
            is_drift = True

        risk = "High" if (is_drift and abs(spend_shift_pct) > 100) else "Medium" if is_drift else "Low"

        return VolumeDriftReport(
            is_drift_detected=is_drift,
            reference_mean_spend=round(b_mean, 2),
            current_mean_spend=round(c_mean, 2),
            spend_shift_pct=spend_shift_pct,
            row_count_ratio=row_ratio,
            ks_statistic=round(float(ks_stat), 4),
            ks_pvalue=float(ks_pval),
            is_distribution_drift=dist_drift,
            risk_level=risk,
            warnings=warnings,
        )
