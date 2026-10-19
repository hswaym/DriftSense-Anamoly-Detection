"""Synthetic event and anomaly injection engine for DriftSense.

Conforms strictly to Contract 5, Contract 6, and docs/synth/generator_design.md:
- Ground-truth anomalies are defined independently of detector output.
- Injects statistically calibrated spikes and multi-hour incident windows.
- Injects benign decoy events (change without cost impact) to test false-positive resistance.
- Emits paired anomaly_labels and operational_events records.
"""

from __future__ import annotations

import uuid
from typing import Any

import numpy as np
import pandas as pd


class SyntheticInjector:
    """Controlled fault and anomaly injector calibrated to historical empirical statistics."""

    def __init__(
        self,
        seed: int = 42,
        injection_rate: float = 0.03,
        min_duration_hours: int = 2,
        max_duration_hours: int = 6,
        multiplier_range: tuple[float, float] = (1.5, 3.5),
        sigma_range: tuple[float, float] = (2.5, 5.0),
    ) -> None:
        self.seed = seed
        self.injection_rate = injection_rate
        self.min_duration_hours = min_duration_hours
        self.max_duration_hours = max_duration_hours
        self.multiplier_range = multiplier_range
        self.sigma_range = sigma_range
        self.rng = np.random.default_rng(seed)

    def inject(
        self,
        df: pd.DataFrame,
        cost_col: str = "EffectiveCost",
        service_col: str = "ServiceName",
        time_col: str = "ChargePeriodStart",
        target_services: list[str] | None = None,
    ) -> tuple[pd.DataFrame, list[dict[str, Any]], list[dict[str, Any]]]:
        """Inject calibrated anomalies into billing series.

        Returns:
            Tuple of:
            - df_injected: copy of dataframe with perturbed costs and binary 'is_anomaly' label.
            - anomaly_labels: list of ground-truth incident records (Contract 6).
            - operational_events: list of associated operational event records (Contract 5).
        """
        df_out = df.copy()
        if not pd.api.types.is_datetime64_any_dtype(df_out[time_col]):
            df_out[time_col] = pd.to_datetime(df_out[time_col], utc=True)

        df_out["is_anomaly"] = 0
        df_out[f"{cost_col}_clean"] = df_out[cost_col].copy()

        services = (
            target_services
            if target_services is not None
            else df_out[service_col].unique().tolist()
        )

        anomaly_labels: list[dict[str, Any]] = []
        operational_events: list[dict[str, Any]] = []

        taxonomies = [
            "DEPLOYMENT_DEFECT",
            "AUTOSCALING_OVERPROVISION",
            "CONFIG_MODIFICATION",
            "EXTERNAL_TRAFFIC_SURGE",
            "RUNAWAY_BATCH_PROCESS",
        ]

        for svc in services:
            svc_mask = df_out[service_col] == svc
            svc_indices = df_out[svc_mask].sort_values(by=time_col).index.to_numpy()
            n_points = len(svc_indices)

            if n_points < (self.max_duration_hours * 2):
                continue

            base_costs = df_out.loc[svc_indices, cost_col].to_numpy(dtype=float)
            svc_mean = float(np.mean(base_costs)) if len(base_costs) > 0 else 0.1
            svc_std = float(np.std(base_costs)) if len(base_costs) > 0 else 0.05
            effective_sigma = max(svc_std, svc_mean * 0.2, 0.05)

            # Determine number of incidents to inject
            n_incidents = max(
                1, int(n_points * self.injection_rate / self.min_duration_hours)
            )
            used_indices: set[int] = set()

            for _ in range(n_incidents):
                duration = int(
                    self.rng.integers(
                        self.min_duration_hours, self.max_duration_hours + 1
                    )
                )
                max_start = n_points - duration - 1
                if max_start <= 0:
                    continue

                start_k = int(self.rng.integers(0, max_start))
                candidate_k = range(start_k, start_k + duration)
                if any(k in used_indices for k in candidate_k):
                    continue

                used_indices.update(candidate_k)
                incident_indices = [svc_indices[k] for k in candidate_k]

                cause = str(self.rng.choice(taxonomies))
                alpha = float(self.rng.uniform(*self.multiplier_range))
                beta = float(self.rng.uniform(*self.sigma_range))

                onset_time = df_out.loc[incident_indices[0], time_col]
                offset_time = df_out.loc[incident_indices[-1], time_col]
                label_id = f"lbl_{uuid.uuid4().hex[:8]}"
                event_id = f"evt_{uuid.uuid4().hex[:8]}"

                # Inject cost surge
                for idx in incident_indices:
                    orig_cost = df_out.loc[idx, cost_col]
                    spike = orig_cost * (1.0 + alpha) + (beta * effective_sigma)
                    df_out.loc[idx, cost_col] = float(spike)
                    df_out.loc[idx, "is_anomaly"] = 1

                # Record ground truth anomaly label (Contract 6)
                anomaly_labels.append(
                    {
                        "label_id": label_id,
                        "service_id": str(svc),
                        "onset_timestamp": onset_time.isoformat(),
                        "offset_timestamp": offset_time.isoformat(),
                        "primary_cause": cause,
                        "contributing_causes": None,
                        "is_synthetic": True,
                        "severity_score": float(alpha + beta),
                        "verification_src": "DriftSense_SyntheticInjector_v1",
                    }
                )

                # Record corresponding operational event (Contract 5)
                operational_events.append(
                    {
                        "event_id": event_id,
                        "ts_start": onset_time.isoformat(),
                        "ts_end": offset_time.isoformat(),
                        "service_id": str(svc),
                        "event_type": cause,
                        "event_source": "SyntheticFaultInjector",
                        "is_synthetic": True,
                        "metadata_json": f'{{"alpha": {alpha:.2f}, "beta": {beta:.2f}}}',
                    }
                )

            # Inject Decoy event (benign deployment without cost surge)
            decoy_start_k = int(self.rng.integers(0, max(1, n_points - 2)))
            decoy_idx = svc_indices[decoy_start_k]
            decoy_time = df_out.loc[decoy_idx, time_col]
            operational_events.append(
                {
                    "event_id": f"decoy_{uuid.uuid4().hex[:8]}",
                    "ts_start": decoy_time.isoformat(),
                    "ts_end": (decoy_time + pd.Timedelta(hours=1)).isoformat(),
                    "service_id": str(svc),
                    "event_type": "DEPLOYMENT",
                    "event_source": "GitHubActions_DeployDecoy",
                    "is_synthetic": True,
                    "metadata_json": '{"is_decoy": true, "cost_impact": 0.0}',
                }
            )

        return df_out, anomaly_labels, operational_events
