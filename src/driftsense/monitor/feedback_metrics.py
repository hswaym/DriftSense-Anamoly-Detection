"""Feedback metrics computation for DriftSense v2 (Phase 13).

Calculates alert usefulness rate, dismissal rate by severity, and time-to-acknowledge.
"""

from __future__ import annotations

import statistics
from dataclasses import asdict, dataclass, field
from typing import Sequence

from driftsense.monitor.feedback_store import FeedbackRecord


@dataclass
class FeedbackMetricsReport:
    """Aggregated operational feedback metrics."""

    total_feedback_count: int
    useful_count: int
    dismissed_count: int
    planned_count: int
    usefulness_rate_pct: float
    dismissal_rate_pct: float
    planned_rate_pct: float
    dismissal_rate_by_severity: dict[str, float]
    mean_acknowledge_latency_seconds: float
    median_acknowledge_latency_seconds: float
    p90_acknowledge_latency_seconds: float
    executive_summary: str

    def to_dict(self) -> dict:
        return asdict(self)


def compute_feedback_metrics(records: Sequence[FeedbackRecord]) -> FeedbackMetricsReport:
    """Compute precision, usefulness, dismissal rates, and acknowledge latencies."""
    total = len(records)
    if total == 0:
        return FeedbackMetricsReport(
            total_feedback_count=0,
            useful_count=0,
            dismissed_count=0,
            planned_count=0,
            usefulness_rate_pct=0.0,
            dismissal_rate_pct=0.0,
            planned_rate_pct=0.0,
            dismissal_rate_by_severity={"Critical": 0.0, "High": 0.0, "Medium": 0.0, "Low": 0.0},
            mean_acknowledge_latency_seconds=0.0,
            median_acknowledge_latency_seconds=0.0,
            p90_acknowledge_latency_seconds=0.0,
            executive_summary="Zero user feedback submissions recorded to date.",
        )

    useful = sum(1 for r in records if r.feedback_label == "USEFUL")
    dismissed = sum(1 for r in records if r.feedback_label == "NOT_AN_ISSUE")
    planned = sum(1 for r in records if r.feedback_label == "PLANNED")

    usefulness_rate = round((useful / total) * 100.0, 1)
    dismissal_rate = round((dismissed / total) * 100.0, 1)
    planned_rate = round((planned / total) * 100.0, 1)

    # Dismissal by severity
    severity_totals: dict[str, int] = {}
    severity_dismissed: dict[str, int] = {}
    for r in records:
        sev = r.severity.capitalize()
        severity_totals[sev] = severity_totals.get(sev, 0) + 1
        if r.feedback_label == "NOT_AN_ISSUE":
            severity_dismissed[sev] = severity_dismissed.get(sev, 0) + 1

    dismissal_by_sev: dict[str, float] = {}
    for sev in ["Critical", "High", "Medium", "Low"]:
        n = severity_totals.get(sev, 0)
        d = severity_dismissed.get(sev, 0)
        dismissal_by_sev[sev] = round((d / n * 100.0), 1) if n > 0 else 0.0

    # Latencies
    latencies = [max(0.0, r.time_to_acknowledge_seconds) for r in records]
    mean_lat = round(statistics.mean(latencies), 1)
    median_lat = round(statistics.median(latencies), 1)
    latencies_sorted = sorted(latencies)
    p90_idx = int(0.9 * len(latencies_sorted))
    p90_lat = round(latencies_sorted[min(p90_idx, len(latencies_sorted) - 1)], 1)

    # Executive summary
    summary = (
        f"Analyzed {total} alerts with user feedback. Usefulness rate is {usefulness_rate}% "
        f"({useful}/{total}), dismissal rate is {dismissal_rate}% ({dismissed}/{total}), "
        f"and planned maintenance rate is {planned_rate}% ({planned}/{total}). "
        f"Median acknowledgment time is {median_lat} seconds."
    )

    return FeedbackMetricsReport(
        total_feedback_count=total,
        useful_count=useful,
        dismissed_count=dismissed,
        planned_count=planned,
        usefulness_rate_pct=usefulness_rate,
        dismissal_rate_pct=dismissal_rate,
        planned_rate_pct=planned_rate,
        dismissal_rate_by_severity=dismissal_by_sev,
        mean_acknowledge_latency_seconds=mean_lat,
        median_acknowledge_latency_seconds=median_lat,
        p90_acknowledge_latency_seconds=p90_lat,
        executive_summary=summary,
    )
