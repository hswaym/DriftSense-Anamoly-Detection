"""Temporal persistence rules for DriftSense v2.

Implements k-of-n windowed persistence to suppress transient single-hour
flukes and confirm genuine sustained anomalies per service series.
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class PersistenceRule:
    """Enforces k-of-n rolling persistence rule per service series."""

    def __init__(
        self,
        k: int = 2,
        n: int = 3,
    ) -> None:
        """Initialize persistence rule.

        Args:
            k: Minimum number of positive triggers required within window (e.g. 2).
            n: Length of lookback window (e.g. 3).
        """
        if k < 1 or n < 1:
            raise ValueError(f"k and n must be >= 1. Got k={k}, n={n}")
        if k > n:
            raise ValueError(f"k cannot exceed n. Got k={k}, n={n}")
        self.k = k
        self.n = n

    def apply(
        self,
        df: pd.DataFrame,
        raw_flags: np.ndarray,
        service_col: str = "ServiceName",
        time_col: str = "ChargePeriodStart",
    ) -> np.ndarray:
        """Apply k-of-n persistence filter grouped by service and ordered by time.

        Args:
            df: DataFrame containing service and timestamp columns.
            raw_flags: Binary or boolean trigger array corresponding to df rows.
            service_col: Column identifying service series.
            time_col: Column identifying chronological order.

        Returns:
            np.ndarray: Binary array (0 or 1) indicating confirmed persistent anomalies.
        """
        df_work = df.copy()
        df_work["_raw_flag"] = np.asarray(raw_flags, dtype=int)
        df_work["_orig_idx"] = np.arange(len(df_work))

        df_sorted = df_work.sort_values(by=[service_col, time_col]).copy()

        # Rolling sum of positive flags over window n per service
        # Shift(0) includes current row t and preceding n-1 steps
        rolling_counts = (
            df_sorted.groupby(service_col)["_raw_flag"]
            .rolling(window=self.n, min_periods=1)
            .sum()
            .reset_index(level=0, drop=True)
        )

        persistent = (rolling_counts >= self.k).astype(int)
        df_sorted["_persistent"] = persistent

        # Re-sort to original input order
        df_restored = df_sorted.sort_values(by="_orig_idx")
        return df_restored["_persistent"].to_numpy(dtype=int)


__all__ = ["PersistenceRule"]
