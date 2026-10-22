"""Confounder event and un-correlated anomaly generator.

Models complex real-world operational scenarios:
1. Pure-noise cost anomalies with zero corresponding operational events (e.g. external traffic surge).
2. Major operational changes with zero cost impact (e.g. database schema upgrade).
3. Overlapping concurrent changes across interconnected services (multi-cause attribution challenges).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass
class ConfounderScenario:
    """Record of an un-correlated or confounded event scenario."""
    scenario_type: str  # 'unattributed_surge', 'silent_major_change', 'concurrent_overlap'
    description: str
    affected_services: list[str]
    event_ids: list[str]
    incident_id: str | None = None


class ConfounderGenerator:
    """Generates complex confounders to test abstention and multi-cause disambiguation."""

    def __init__(self, seed: int = 42) -> None:
        self.seed = seed
        self.rng = np.random.default_rng(seed)

    def inject_unattributed_surge(
        self,
        df: pd.DataFrame,
        service_name: str,
        start_index: int,
        duration_hours: int = 4,
        cost_multiplier: float = 1.8,
        cost_col: str = "EffectiveCost",
        quantity_col: str = "ConsumedQuantity",
    ) -> tuple[pd.DataFrame, dict]:
        """Inject a cost and usage surge with ZERO corresponding operational events.

        Tests whether the attribution engine correctly abstains ('Inconclusive Evidence').
        """
        df_out = df.copy()
        svc_indices = df_out[df_out["ServiceName"] == service_name].index.to_numpy()
        if start_index + duration_hours >= len(svc_indices):
            return df_out, {}

        target_indices = [svc_indices[i] for i in range(start_index, start_index + duration_hours)]
        for idx in target_indices:
            df_out.loc[idx, cost_col] = float(df_out.loc[idx, cost_col]) * cost_multiplier
            if quantity_col in df_out.columns:
                df_out.loc[idx, quantity_col] = float(df_out.loc[idx, quantity_col]) * cost_multiplier

        incident_meta = {
            "incident_id": f"unattr_{uuid.uuid4().hex[:8]}",
            "service_name": service_name,
            "scenario_type": "unattributed_surge",
            "description": "Organic viral consumer traffic surge (No operational deployment)",
            "start_time": str(df_out.loc[target_indices[0], "ChargePeriodStart"]),
            "end_time": str(df_out.loc[target_indices[-1], "ChargePeriodEnd"]),
            "duration_hours": duration_hours,
            "cost_multiplier": cost_multiplier,
            "ground_truth_event_id": None,  # Explicitly None
        }
        return df_out, incident_meta

    def generate_silent_major_change_event(
        self,
        service_name: str,
        timestamp: str,
        sub_account_id: str = "acc-prod",
        tenant_id: str = "00000000-0000-0000-0000-000000000000",
    ) -> dict:
        """Generate a major operational deployment that causes ZERO cost variation."""
        return {
            "event_id": f"silent_{uuid.uuid4().hex[:8]}",
            "tenant_id": tenant_id,
            "timestamp": timestamp,
            "service_name": service_name,
            "sub_account_id": sub_account_id,
            "event_type": "major_schema_migration",
            "summary": "Database zero-downtime partition schema migration completed",
            "is_decoy": True,
            "details": {"cost_impact": 0.0, "consequence": "none"},
        }
