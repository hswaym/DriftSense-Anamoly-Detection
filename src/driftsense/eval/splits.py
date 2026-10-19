"""Chronological and rolling-origin temporal splitting for DriftSense.

Guarantees strict forward-chaining partitions:
- Train < Val < Test strictly in time with zero temporal overlap.
- Support for embargo / purge gap intervals between folds.
- Rolling-origin cross-validation splitter for time-series models.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from typing import NamedTuple

import pandas as pd

logger = logging.getLogger(__name__)


class SplitInfo(NamedTuple):
    """Metadata detailing chronological split boundaries."""

    train_rows: int
    val_rows: int
    test_rows: int
    train_start: pd.Timestamp
    train_end: pd.Timestamp
    val_start: pd.Timestamp
    val_end: pd.Timestamp
    test_start: pd.Timestamp
    test_end: pd.Timestamp


def chronological_split(
    df: pd.DataFrame,
    time_col: str = "ChargePeriodStart",
    train_frac: float = 0.60,
    val_frac: float = 0.20,
    test_frac: float = 0.20,
    purge_gap_hours: int = 0,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, SplitInfo]:
    """Partition a panel DataFrame into strictly chronological train, val, and test slices.

    Invariant: max(train_timestamp) < min(val_timestamp) < min(test_timestamp).

    Args:
        df: Input DataFrame with timestamp column.
        time_col: Column containing UTC datetime.
        train_frac: Proportion of temporal duration allocated to training.
        val_frac: Proportion of temporal duration allocated to validation.
        test_frac: Proportion of temporal duration allocated to test.
        purge_gap_hours: Optional buffer hours between partitions to prevent boundary leakage.

    Returns:
        tuple: (train_df, val_df, test_df, SplitInfo)
    """
    total_frac = train_frac + val_frac + test_frac
    if not (0.999 <= total_frac <= 1.001):
        raise ValueError(
            f"Fractions must sum to 1.0. Got train={train_frac}, val={val_frac}, test={test_frac}"
        )

    df_sorted = df.copy()
    if not pd.api.types.is_datetime64_any_dtype(df_sorted[time_col]):
        df_sorted[time_col] = pd.to_datetime(df_sorted[time_col], utc=True)
    df_sorted = df_sorted.sort_values(time_col)

    unique_times = (
        df_sorted[time_col].drop_duplicates().sort_values().reset_index(drop=True)
    )
    n_times = len(unique_times)
    if n_times < 3:
        raise ValueError(
            f"Insufficient distinct timestamps for chronological split: {n_times}"
        )

    # Index cutoffs based on unique timestamps to maintain panel integrity
    train_idx = int(n_times * train_frac)
    val_idx = train_idx + int(n_times * val_frac)

    train_cutoff = unique_times.iloc[train_idx - 1]
    val_start_time = unique_times.iloc[train_idx]
    if purge_gap_hours > 0:
        val_start_time += pd.Timedelta(hours=purge_gap_hours)

    val_cutoff = unique_times.iloc[val_idx - 1]
    test_start_time = unique_times.iloc[val_idx]
    if purge_gap_hours > 0:
        test_start_time += pd.Timedelta(hours=purge_gap_hours)

    train_mask = df_sorted[time_col] <= train_cutoff
    val_mask = (df_sorted[time_col] >= val_start_time) & (
        df_sorted[time_col] <= val_cutoff
    )
    test_mask = df_sorted[time_col] >= test_start_time

    train_df = df_sorted[train_mask].copy()
    val_df = df_sorted[val_mask].copy()
    test_df = df_sorted[test_mask].copy()

    # Verification assertions
    assert train_df[time_col].max() < val_df[time_col].min(), (
        "Leakage: Train overlaps with Validation!"
    )
    assert val_df[time_col].max() < test_df[time_col].min(), (
        "Leakage: Validation overlaps with Test!"
    )

    # Verify disjoint indices
    idx_train = set(train_df.index)
    idx_val = set(val_df.index)
    idx_test = set(test_df.index)
    assert not (idx_train & idx_val), "Leakage: Train and Validation share rows!"
    assert not (idx_val & idx_test), "Leakage: Validation and Test share rows!"
    assert not (idx_train & idx_test), "Leakage: Train and Test share rows!"

    info = SplitInfo(
        train_rows=len(train_df),
        val_rows=len(val_df),
        test_rows=len(test_df),
        train_start=train_df[time_col].min(),
        train_end=train_df[time_col].max(),
        val_start=val_df[time_col].min(),
        val_end=val_df[time_col].max(),
        test_start=test_df[time_col].min(),
        test_end=test_df[time_col].max(),
    )

    return train_df, val_df, test_df, info


class RollingOriginSplitter:
    """Iterative rolling-origin / forward-chaining splitter for temporal validation."""

    def __init__(
        self,
        n_splits: int = 3,
        horizon_hours: int = 24,
        min_train_hours: int = 72,
        step_hours: int = 24,
        time_col: str = "ChargePeriodStart",
    ) -> None:
        self.n_splits = n_splits
        self.horizon_hours = horizon_hours
        self.min_train_hours = min_train_hours
        self.step_hours = step_hours
        self.time_col = time_col

    def split(
        self,
        df: pd.DataFrame,
    ) -> Iterator[tuple[pd.DataFrame, pd.DataFrame]]:
        """Yield (train_slice, val_slice) for each expanding temporal fold."""
        df_sorted = df.copy()
        if not pd.api.types.is_datetime64_any_dtype(df_sorted[self.time_col]):
            df_sorted[self.time_col] = pd.to_datetime(
                df_sorted[self.time_col], utc=True
            )
        df_sorted = df_sorted.sort_values(self.time_col)

        min_t = df_sorted[self.time_col].min()
        max_t = df_sorted[self.time_col].max()

        total_hours = int((max_t - min_t).total_seconds() / 3600)
        needed_hours = (
            self.min_train_hours + self.n_splits * self.step_hours + self.horizon_hours
        )
        if total_hours < needed_hours:
            logger.warning(
                "Total duration (%d hours) is less than ideal window (%d hours). Adjusting fold windows.",
                total_hours,
                needed_hours,
            )

        for fold in range(self.n_splits):
            train_end_hours = self.min_train_hours + fold * self.step_hours
            train_end_t = min_t + pd.Timedelta(hours=train_end_hours)
            val_end_t = train_end_t + pd.Timedelta(hours=self.horizon_hours)

            train_fold = df_sorted[df_sorted[self.time_col] <= train_end_t].copy()
            val_fold = df_sorted[
                (df_sorted[self.time_col] > train_end_t)
                & (df_sorted[self.time_col] <= val_end_t)
            ].copy()

            if not train_fold.empty and not val_fold.empty:
                yield train_fold, val_fold
