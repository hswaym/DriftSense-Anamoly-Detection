"""Temporal proximity decay kernel for operational change events.

Implements Layer 2 of DriftSense attribution:
- Matches operational events (deployments, autoscaling rules, config changes, maintenance)
  to detected cost incidents.
- Evaluates temporal proximity using configurable half-life decay.
- Rewards exact service and regional matches while down-weighting cross-service events.
- Produces inspectable EvidenceItem records for auditability.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from typing import Any

import pandas as pd

from driftsense.attribute.evidence import EvidenceItem

logger = logging.getLogger(__name__)

EVENT_TYPE_TO_CAUSE = {
    "DEPLOYMENT": "DEPLOYMENT_DEFECT",
    "RELEASE": "DEPLOYMENT_DEFECT",
    "AUTOSCALING_RULE_CHANGE": "AUTOSCALING_OVERPROVISION",
    "AUTOSCALING": "AUTOSCALING_OVERPROVISION",
    "CONFIG_CHANGE": "CONFIG_MODIFICATION",
    "SECURITY_GROUP_UPDATE": "CONFIG_MODIFICATION",
    "MARKETING_CAMPAIGN": "EXTERNAL_TRAFFIC_SURGE",
    "TRAFFIC_SURGE": "EXTERNAL_TRAFFIC_SURGE",
    "CRON_SCHEDULE_UPDATE": "RUNAWAY_BATCH_PROCESS",
    "BATCH_JOB": "RUNAWAY_BATCH_PROCESS",
    "STORAGE_LIFECYCLE_POLICY_DISABLE": "ORPHANED_STORAGE_ACCUMULATION",
    "BACKUP_RETENTION_CHANGE": "ORPHANED_STORAGE_ACCUMULATION",
}


@dataclass
class EventKernelConfig:
    """Configuration for event proximity matching."""

    lookback_hours: float = 24.0
    half_life_hours: float = 6.0
    service_match_multiplier: float = 2.5
    global_multiplier: float = 1.0
    unmatched_multiplier: float = 0.2
    grace_period_hours: float = 0.5  # Accommodates clock skew/logging delay
    kernel_type: str = "exponential"  # "exponential" or "gaussian"


class EventEvidenceMatcher:
    """Matches operational events to an incident and calculates proximity decay scores."""

    def __init__(self, config: EventKernelConfig | None = None) -> None:
        self.config = config or EventKernelConfig()

    def _compute_kernel_weight(self, delta_hours: float) -> float:
        """Calculate temporal proximity decay weight.

        delta_hours is (t_incident - t_event).
        Positive delta means event happened before the incident.
        """
        # If event happened in the future beyond grace period, weight is 0
        if delta_hours < -self.config.grace_period_hours:
            return 0.0

        effective_delta = max(0.0, delta_hours)
        if effective_delta > self.config.lookback_hours:
            return 0.0

        if self.config.kernel_type == "gaussian":
            sigma = self.config.half_life_hours
            return float(math.exp(-0.5 * (effective_delta / max(1e-3, sigma)) ** 2))
        else:
            # Exponential half-life decay: 2^(-delta / tau)
            tau = max(1e-3, self.config.half_life_hours)
            return float(math.pow(2.0, -effective_delta / tau))

    def match_events(
        self,
        incident_time: str | pd.Timestamp,
        incident_service: str | None,
        events: list[dict[str, Any]],
    ) -> tuple[dict[str, float], list[EvidenceItem]]:
        """Evaluate proximity of events to the given incident.

        Returns:
            Tuple of:
            - Dict mapping cause category -> aggregated evidence score
            - List of supporting EvidenceItem objects sorted by relevance
        """
        inc_ts = pd.to_datetime(incident_time, utc=True)
        cause_scores: dict[str, float] = {}
        evidence_items: list[EvidenceItem] = []

        for ev in events:
            ev_ts_raw = ev.get("timestamp") or ev.get("event_time") or ev.get("Time")
            if not ev_ts_raw:
                continue

            ev_ts = pd.to_datetime(ev_ts_raw, utc=True)
            delta_hours = (inc_ts - ev_ts).total_seconds() / 3600.0

            kernel_weight = self._compute_kernel_weight(delta_hours)
            if kernel_weight <= 1e-4:
                continue

            ev_service = ev.get("service") or ev.get("ServiceName")
            ev_type = str(ev.get("event_type", "UNKNOWN")).upper()
            mapped_cause = ev.get("mapped_cause") or EVENT_TYPE_TO_CAUSE.get(ev_type, "UNKNOWN")

            # Scope matching
            if incident_service and ev_service:
                if str(incident_service).lower() == str(ev_service).lower():
                    match_mult = self.config.service_match_multiplier
                    match_status = "EXACT_SERVICE_MATCH"
                else:
                    match_mult = self.config.unmatched_multiplier
                    match_status = "CROSS_SERVICE"
            else:
                match_mult = self.config.global_multiplier
                match_status = "GLOBAL_SCOPE"

            # Event confidence or prior weight (decoys may have is_decoy=True)
            is_decoy = bool(ev.get("is_decoy", False))
            decoy_mult = 0.05 if is_decoy else 1.0

            total_event_weight = kernel_weight * match_mult * decoy_mult
            if mapped_cause != "UNKNOWN":
                cause_scores[mapped_cause] = cause_scores.get(mapped_cause, 0.0) + total_event_weight

            ev_id = str(ev.get("event_id", f"ev_{ev_type}_{int(delta_hours)}h"))
            evidence_items.append(
                EvidenceItem(
                    evidence_type="EVENT_PROXIMITY",
                    dimension="OperationalEvent",
                    key=ev_id,
                    dollar_impact=0.0,
                    percentage_share=float(kernel_weight),
                    time_overlap_hours=float(delta_hours),
                    details={
                        "event_type": ev_type,
                        "event_service": ev_service,
                        "match_status": match_status,
                        "kernel_weight": kernel_weight,
                        "total_event_weight": total_event_weight,
                        "is_decoy": is_decoy,
                        "mapped_cause": mapped_cause,
                    },
                )
            )

        # Sort evidence items by kernel weight descending
        evidence_items.sort(key=lambda e: e.percentage_share, reverse=True)
        return cause_scores, evidence_items
