"""Rolling threshold anomaly detector for DriftSense v2.

Re-exports RollingThresholdDetector for consistent module taxonomy.
"""

from __future__ import annotations

from driftsense.detect.rolling_threshold import RollingThresholdDetector

__all__ = ["RollingThresholdDetector"]
