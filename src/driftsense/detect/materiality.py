"""Business materiality filtering for DriftSense v2.

Suppresses economically immaterial alerts (e.g., micro-spikes from $0.01 to $0.05)
by enforcing minimum dollar impact and minimum percentage exceedance over expectation.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class MaterialityThresholds:
    """Configurable thresholds for economic materiality."""

    min_dollar_exceedance: float = 10.0  # Minimum dollar amount above expected
    min_pct_exceedance: float = 15.0     # Minimum percentage above expected (%)


class MaterialityFilter:
    """Filters candidate anomaly flags against business materiality criteria."""

    def __init__(
        self,
        min_dollar_exceedance: float = 10.0,
        min_pct_exceedance: float = 15.0,
        eps: float = 1e-4,
    ) -> None:
        self.min_dollar_exceedance = min_dollar_exceedance
        self.min_pct_exceedance = min_pct_exceedance
        self.eps = eps

    def apply(
        self,
        raw_flags: np.ndarray,
        actuals: np.ndarray,
        expecteds: np.ndarray,
    ) -> np.ndarray:
        """Filter raw boolean flags, suppressing immaterial spikes.

        An alert is retained if and only if:
        1. raw_flags == 1 (statistical exceedance triggered)
        2. (actual - expected) >= min_dollar_exceedance
        3. (actual - expected) / max(expected, eps) * 100 >= min_pct_exceedance

        Args:
            raw_flags: Binary or boolean indicator array of raw detections.
            actuals: Array of observed actual costs.
            expecteds: Array of expected / baseline costs.

        Returns:
            np.ndarray: Filtered binary array (0 or 1).
        """
        flags = np.asarray(raw_flags, dtype=int)
        y_act = np.asarray(actuals, dtype=float)
        y_exp = np.asarray(expecteds, dtype=float)

        dollar_delta = y_act - y_exp
        pct_delta = (dollar_delta / np.maximum(y_exp, self.eps)) * 100.0

        is_material_dollar = dollar_delta >= self.min_dollar_exceedance
        is_material_pct = pct_delta >= self.min_pct_exceedance

        filtered = flags & is_material_dollar & is_material_pct
        return filtered.astype(int)


__all__ = ["MaterialityFilter", "MaterialityThresholds"]
