"""Business severity scoring and tier classification for DriftSense v2.

Computes a composite severity score S in [0, 100] based on:
- Financial dollar impact
- Relative percentage exceedance above expected
- Anomaly duration and persistence streak

Maps continuous score S to user-facing severity labels:
- Info   (S < 25)
- Low    (25 <= S < 50)
- Medium (50 <= S < 75)
- High   (S >= 75)
"""

from __future__ import annotations

import logging
from typing import Literal

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

SeverityTier = Literal["Info", "Low", "Medium", "High"]


class SeverityScorer:
    """Calculates multidimensional anomaly severity scores and tiers."""

    def __init__(
        self,
        weight_dollar: float = 0.45,
        weight_pct: float = 0.30,
        weight_duration: float = 0.25,
        eps: float = 1e-4,
    ) -> None:
        self.weight_dollar = weight_dollar
        self.weight_pct = weight_pct
        self.weight_duration = weight_duration
        self.eps = eps

    def score_single(
        self,
        actual: float,
        expected: float,
        duration_hours: int = 1,
    ) -> tuple[float, SeverityTier]:
        """Compute severity score and tier for a single observation.

        Args:
            actual: Observed spend ($).
            expected: Expected baseline spend ($).
            duration_hours: Consecutive hours the anomaly has persisted.

        Returns:
            tuple[float, SeverityTier]: (score 0-100, tier label)
        """
        dollar_delta = max(0.0, float(actual - expected))
        pct_delta = (dollar_delta / max(float(expected), self.eps)) * 100.0

        # 1. Dollar score (0-100 log/piecewise scaling)
        if dollar_delta <= 5.0:
            dollar_score = (dollar_delta / 5.0) * 20.0
        elif dollar_delta <= 50.0:
            dollar_score = 20.0 + ((dollar_delta - 5.0) / 45.0) * 35.0
        elif dollar_delta <= 250.0:
            dollar_score = 55.0 + ((dollar_delta - 50.0) / 200.0) * 30.0
        else:
            dollar_score = min(100.0, 85.0 + ((dollar_delta - 250.0) / 500.0) * 15.0)

        # 2. Percentage exceedance score (0-100)
        pct_score = min(100.0, pct_delta * 0.5)

        # 3. Duration score (0-100)
        dur_score = min(100.0, duration_hours * 25.0)

        composite = (
            self.weight_dollar * dollar_score
            + self.weight_pct * pct_score
            + self.weight_duration * dur_score
        )
        score = float(np.clip(composite, 0.0, 100.0))

        if score < 25.0:
            tier: SeverityTier = "Info"
        elif score < 50.0:
            tier = "Low"
        elif score < 75.0:
            tier = "Medium"
        else:
            tier = "High"

        return score, tier

    def score_dataframe(
        self,
        df: pd.DataFrame,
        actual_col: str = "EffectiveCost",
        expected_col: str = "EffectiveCost_expected",
        flags_col: str = "is_anomaly_detected",
        service_col: str = "ServiceName",
        time_col: str = "ChargePeriodStart",
    ) -> pd.DataFrame:
        """Add severity_score and severity_tier columns to a DataFrame."""
        df_out = df.sort_values(by=[service_col, time_col]).copy()
        n = len(df_out)
        scores = np.zeros(n, dtype=float)
        tiers: list[str] = ["Info"] * n

        actuals = df_out[actual_col].to_numpy(dtype=float)
        expecteds = df_out[expected_col].to_numpy(dtype=float)
        flags = df_out[flags_col].to_numpy(dtype=int)

        # Track duration streak per service
        streak = 0
        prev_svc = None

        for i, (_, row) in enumerate(df_out.iterrows()):
            svc = str(row[service_col])
            if svc != prev_svc:
                streak = 0
                prev_svc = svc

            if flags[i] == 1:
                streak += 1
                s, t = self.score_single(
                    actual=actuals[i],
                    expected=expecteds[i],
                    duration_hours=streak,
                )
                scores[i] = s
                tiers[i] = t
            else:
                streak = 0
                scores[i] = 0.0
                tiers[i] = "Info"

        df_out["severity_score"] = scores
        df_out["severity_tier"] = tiers
        return df_out


__all__ = ["SeverityScorer", "SeverityTier"]
