"""Alert volume and fatigue monitoring for DriftSense v2 (Phase 13).

Tracks alert generation rates across hours/days to detect alert storms,
false-alarm avalanches, and alert fatigue before engineers become overwhelmed.
"""

from __future__ import annotations

import statistics
from dataclasses import asdict, dataclass, field
from typing import Any, Sequence


@dataclass
class AlertVolumeReport:
    """Findings on alert rate dynamics."""

    is_alert_storm_detected: bool
    current_alert_count: int
    baseline_alert_rate: float
    surge_multiplier: float
    risk_level: str  # "Normal", "Elevated", "Critical_Alert_Storm"
    actionable_warning: str | None
    recommendations: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class AlertVolumeMonitor:
    """Monitors alert generation velocity and flags alert fatigue."""

    def __init__(
        self,
        alert_fatigue_multiplier: float = 3.0,
        min_critical_spike_count: int = 10,
    ) -> None:
        self.alert_fatigue_multiplier = alert_fatigue_multiplier
        self.min_critical_spike_count = min_critical_spike_count

    def inspect_alert_volume(
        self,
        current_window_count: int,
        historical_window_counts: Sequence[int],
    ) -> AlertVolumeReport:
        if not historical_window_counts:
            baseline = max(1.0, float(current_window_count))
        else:
            baseline = max(1.0, float(statistics.mean(historical_window_counts)))

        surge_mult = round(current_window_count / baseline, 2)
        is_storm = (
            surge_mult >= self.alert_fatigue_multiplier
            and current_window_count >= self.min_critical_spike_count
        )

        recommendations = []
        if is_storm:
            risk = "Critical_Alert_Storm"
            warning = (
                f"Alert Fatigue Warning: Alert rate surged by {surge_mult}x "
                f"({current_window_count} alerts vs. {baseline:.1f} baseline). "
                "Possible widespread infrastructure event or threshold collapse."
            )
            recommendations.append("Inspect if an operational cloud provider outage occurred.")
            recommendations.append("Check if a low-baseline off-peak collapse occurred across multiple services.")
            recommendations.append("Temporarily activate high materiality suppression ($50 delta threshold).")
        elif surge_mult >= 1.75:
            risk = "Elevated"
            warning = f"Elevated alert volume detected ({surge_mult}x baseline rate)."
            recommendations.append("Monitor engineering triage queue for response latency.")
        else:
            risk = "Normal"
            warning = None

        return AlertVolumeReport(
            is_alert_storm_detected=is_storm,
            current_alert_count=current_window_count,
            baseline_alert_rate=round(baseline, 1),
            surge_multiplier=surge_mult,
            risk_level=risk,
            actionable_warning=warning,
            recommendations=recommendations,
        )
