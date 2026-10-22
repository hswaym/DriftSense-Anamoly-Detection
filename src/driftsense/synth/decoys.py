"""Decoy operational event generation engine.

Generates realistic benign change events (deployments, autoscaling, scheduled maintenance)
that have ZERO cost impact, establishing a candidate pool ratio of >= 3:1 decoys-to-faults
to test false-positive resistance and eliminate circular attribution.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass
class DecoyEvent:
    """Benign operational change with zero cost or usage impact."""
    event_id: str
    tenant_id: str
    timestamp: str  # ISO-8601 UTC
    service_name: str
    sub_account_id: str
    event_type: str
    summary: str
    is_decoy: bool = True
    jitter_minutes: int = 0
    details: dict | None = None


DECOY_EVENT_TYPES = [
    ("routine_maintenance_decoy", "Scheduled weekly OS patch and log rotation"),
    ("canary_deployment_decoy", "Automated canary deployment (Zero error rate, passed validation)"),
    ("config_sync_decoy", "Terraform state sync (No infrastructure resources modified)"),
    ("scheduled_backup_decoy", "Automated EBS snapshot and RDS automated backup completed"),
    ("autoscaling_health_decoy", "Routine health probe replacement of 1 healthy instance"),
    ("dependency_upgrade_decoy", "Minor security patch dependency bump deployed cleanly"),
]


class DecoyGenerator:
    """Generates non-injected benign decoy events with timestamp jitter."""

    def __init__(
        self,
        seed: int = 42,
        decoy_to_fault_ratio: float = 3.0,
        jitter_min_minutes: int = -45,
        jitter_max_minutes: int = 45,
    ) -> None:
        self.seed = seed
        self.decoy_to_fault_ratio = decoy_to_fault_ratio
        self.jitter_min = jitter_min_minutes
        self.jitter_max = jitter_max_minutes
        self.rng = np.random.default_rng(seed)

    def generate_decoys_for_timeline(
        self,
        time_series: pd.Series,
        service_names: list[str],
        sub_account_ids: list[str],
        n_faults: int,
        tenant_id: str = "00000000-0000-0000-0000-000000000000",
    ) -> list[DecoyEvent]:
        """Generate non-injected decoy events across the time window."""
        target_decoys = max(3, int(np.ceil(n_faults * self.decoy_to_fault_ratio)))
        dts = pd.to_datetime(time_series, utc=True).dropna().sort_values().to_numpy()

        if len(dts) == 0:
            return []

        min_time = pd.Timestamp(dts[0])
        max_time = pd.Timestamp(dts[-1])
        total_seconds = int((max_time - min_time).total_seconds())
        if total_seconds <= 3600:
            total_seconds = 86400

        decoys: list[DecoyEvent] = []

        for _ in range(target_decoys):
            # Pick random baseline timestamp
            offset_sec = int(self.rng.integers(0, total_seconds))
            base_time = min_time + pd.Timedelta(seconds=offset_sec)

            # Apply temporal jitter
            jitter = int(self.rng.integers(self.jitter_min, self.jitter_max + 1))
            event_time = base_time + pd.Timedelta(minutes=jitter)

            # Pick service and type
            svc = str(self.rng.choice(service_names))
            sub_acc = str(self.rng.choice(sub_account_ids)) if sub_account_ids else "acc-default"
            etype, summary = DECOY_EVENT_TYPES[int(self.rng.integers(0, len(DECOY_EVENT_TYPES)))]

            decoy = DecoyEvent(
                event_id=f"decoy_{uuid.uuid4().hex[:8]}",
                tenant_id=tenant_id,
                timestamp=event_time.isoformat(),
                service_name=svc,
                sub_account_id=sub_acc,
                event_type=etype,
                summary=summary,
                is_decoy=True,
                jitter_minutes=jitter,
                details={"cost_impact": 0.0, "is_benign": True},
            )
            decoys.append(decoy)

        return decoys
