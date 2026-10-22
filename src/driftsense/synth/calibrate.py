"""Empirical calibration engine for synthetic scenario generation.

Estimates noise distributions, seasonality multipliers, and sparsity from real billing sources
(S1/S3/S4) to ensure synthetic scenarios reflect genuine cloud dynamics.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
import pandas as pd


@dataclass
class ServiceCalibrationStats:
    """Empirical time series statistics for a single cloud service."""
    service_name: str
    mean_cost: float
    std_cost: float
    p25_cost: float
    p50_cost: float
    p75_cost: float
    p95_cost: float
    zero_cost_ratio: float
    mean_quantity: float
    std_quantity: float
    hourly_diurnal_factors: list[float]  # 24 normalized hourly multipliers
    noise_sigma: float


@dataclass
class CalibrationProfile:
    """Full empirical calibration profile for scenario generation."""
    profile_id: str
    source_dataset: str
    sample_rows: int
    services: dict[str, ServiceCalibrationStats]
    global_mean_cost: float
    global_std_cost: float
    global_zero_ratio: float


def calibrate_from_dataframe(
    df: pd.DataFrame,
    source_name: str = "RealBillingSource",
    cost_col: str = "EffectiveCost",
    quantity_col: str = "ConsumedQuantity",
    service_col: str = "ServiceName",
    time_col: str = "ChargePeriodStart",
) -> CalibrationProfile:
    """Extract empirical parameters from real billing records."""
    if df.empty:
        raise ValueError("Cannot calibrate from an empty DataFrame.")

    pd.to_datetime(df[time_col], utc=True, errors="coerce")
    costs = pd.to_numeric(df[cost_col], errors="coerce").fillna(0.0)
    pd.to_numeric(df.get(quantity_col, 0.0), errors="coerce").fillna(0.0)

    services_stats: dict[str, ServiceCalibrationStats] = {}

    for s_name, group in df.groupby(service_col):
        s_costs = pd.to_numeric(group[cost_col], errors="coerce").fillna(0.0).to_numpy()
        s_quantities = pd.to_numeric(group.get(quantity_col, 0.0), errors="coerce").fillna(0.0).to_numpy()
        s_dts = pd.to_datetime(group[time_col], utc=True, errors="coerce")

        if len(s_costs) == 0:
            continue

        mean_c = float(np.mean(s_costs))
        std_c = float(np.std(s_costs))
        zero_ratio = float(np.mean(s_costs <= 0.0))

        # Hourly diurnal profile (24 hours)
        diurnal = [1.0] * 24
        if len(s_dts.dropna()) > 0 and mean_c > 0:
            hours = s_dts.dt.hour
            hourly_means = [float(s_costs[hours == h].mean()) if (hours == h).any() else mean_c for h in range(24)]
            mean_hm = np.mean(hourly_means) or 1.0
            diurnal = [round(float(hm / mean_hm), 4) for hm in hourly_means]

        # Residual noise estimation (relative to diurnal mean)
        noise_sigma = max(0.01, std_c * 0.3)

        services_stats[str(s_name)] = ServiceCalibrationStats(
            service_name=str(s_name),
            mean_cost=round(mean_c, 4),
            std_cost=round(std_c, 4),
            p25_cost=round(float(np.percentile(s_costs, 25)), 4),
            p50_cost=round(float(np.percentile(s_costs, 50)), 4),
            p75_cost=round(float(np.percentile(s_costs, 75)), 4),
            p95_cost=round(float(np.percentile(s_costs, 95)), 4),
            zero_cost_ratio=round(zero_ratio, 4),
            mean_quantity=round(float(np.mean(s_quantities)), 4),
            std_quantity=round(float(np.std(s_quantities)), 4),
            hourly_diurnal_factors=diurnal,
            noise_sigma=round(noise_sigma, 4),
        )

    return CalibrationProfile(
        profile_id="calib_v2_empirical",
        source_dataset=source_name,
        sample_rows=len(df),
        services=services_stats,
        global_mean_cost=round(float(np.mean(costs)), 4),
        global_std_cost=round(float(np.std(costs)), 4),
        global_zero_ratio=round(float(np.mean(costs <= 0.0)), 4),
    )


def save_calibration_profile(profile: CalibrationProfile, path: str | Path) -> None:
    """Serialize calibration profile to JSON."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(asdict(profile), indent=2), encoding="utf-8")


def load_calibration_profile(path: str | Path) -> CalibrationProfile:
    """Load calibration profile from JSON."""
    p = Path(path)
    data = json.loads(p.read_text(encoding="utf-8"))
    services = {
        k: ServiceCalibrationStats(**v) for k, v in data.get("services", {}).items()
    }
    data["services"] = services
    return CalibrationProfile(**data)
