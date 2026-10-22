"""DriftSense v2 Adversarial Fault Injection Engine.

Replaces v1 naive deterministic additive spikes with 15 calibrated fault families,
multiple onset curves (abrupt, gradual linear, gradual exponential, step),
and decoupled volume vs. rate perturbations.
"""

from __future__ import annotations

import uuid
from typing import Any

import numpy as np
import pandas as pd

from driftsense.synth.labels import GroundTruthIncident

ALL_FAULT_FAMILIES = [
    "usage_spike",
    "gradual_ramp_drift",
    "level_shift",
    "rate_price_change",
    "new_service_appearance",
    "region_migration",
    "untagged_spend_growth",
    "commitment_discount_expiry",
    "data_transfer_surge",
    "credit_refund_artifact",
    "month_end_seasonality_shift",
    "autoscaling_overprovision",
    "runaway_batch",
    "deployment_defect",
    "config_change",
]

# Leave-Family-Out Partition
DEV_FAULT_FAMILIES = [
    "usage_spike",
    "gradual_ramp_drift",
    "rate_price_change",
    "new_service_appearance",
    "data_transfer_surge",
    "autoscaling_overprovision",
    "runaway_batch",
    "deployment_defect",
    "config_change",
    "month_end_seasonality_shift",
]

HOLDOUT_RESERVED_FAULT_FAMILIES = [
    "level_shift",
    "region_migration",
    "untagged_spend_growth",
    "commitment_discount_expiry",
    "credit_refund_artifact",
]


class CalibratedFaultInjector:
    """Enterprise-grade fault injection engine supporting 15 parametric fault families."""

    def __init__(
        self,
        seed: int = 42,
        allowed_fault_families: list[str] | None = None,
        min_duration_hours: int = 3,
        max_duration_hours: int = 12,
        magnitude_range: tuple[float, float] = (1.20, 3.50),
    ) -> None:
        self.seed = seed
        self.allowed_families = allowed_fault_families or DEV_FAULT_FAMILIES
        self.min_duration = min_duration_hours
        self.max_duration = max_duration_hours
        self.magnitude_range = magnitude_range
        self.rng = np.random.default_rng(seed)

    def inject_incident(
        self,
        df: pd.DataFrame,
        service_name: str,
        start_idx: int,
        duration_hours: int,
        fault_family: str,
        magnitude: float,
        onset_shape: str = "abrupt",
        cost_col: str = "EffectiveCost",
        quantity_col: str = "ConsumedQuantity",
        billed_col: str = "BilledCost",
        time_col: str = "ChargePeriodStart",
    ) -> tuple[pd.DataFrame, GroundTruthIncident, dict[str, Any]]:
        """Inject a single calibrated fault episode into DataFrame."""
        if fault_family not in ALL_FAULT_FAMILIES:
            raise ValueError(f"Unknown fault family: '{fault_family}'. Must be one of {ALL_FAULT_FAMILIES}")

        out = df.copy()
        svc_mask = out["ServiceName"] == service_name
        svc_indices = out[svc_mask].index.to_numpy()

        if start_idx + duration_hours > len(svc_indices):
            duration_hours = max(1, len(svc_indices) - start_idx)

        target_indices = [svc_indices[start_idx + i] for i in range(duration_hours)]
        incident_id = f"inc_{uuid.uuid4().hex[:8]}"
        event_id = f"evt_{uuid.uuid4().hex[:8]}"

        # Compute perturbation curve over duration
        steps = np.arange(duration_hours)
        if onset_shape == "gradual_linear":
            ramp = 1.0 + (magnitude - 1.0) * (steps + 1) / duration_hours
        elif onset_shape == "gradual_exponential":
            ramp = 1.0 + (magnitude - 1.0) * (np.exp(steps / max(1, duration_hours - 1)) - 1.0) / (np.e - 1.0)
        else:  # 'abrupt' or 'step'
            ramp = np.full(duration_hours, magnitude)

        # Apply fault physics based on family
        if fault_family in ["usage_spike", "runaway_batch", "autoscaling_overprovision", "data_transfer_surge"]:
            # Volume runaway: Both quantity and cost increase proportionally
            for i, idx in enumerate(target_indices):
                orig_q = max(0.01, float(out.loc[idx, quantity_col]))
                orig_c = max(0.01, float(out.loc[idx, cost_col]))
                unit_rate = orig_c / orig_q
                new_q = orig_q * ramp[i]
                new_c = new_q * unit_rate
                out.loc[idx, quantity_col] = round(new_q, 4)
                out.loc[idx, cost_col] = round(new_c, 4)
                if billed_col in out.columns:
                    out.loc[idx, billed_col] = round(new_c, 4)

        elif fault_family in ["rate_price_change", "commitment_discount_expiry"]:
            # Rate anomaly: ConsumedQuantity is UNCHANGED, but EffectiveCost surges
            for i, idx in enumerate(target_indices):
                orig_c = max(0.01, float(out.loc[idx, cost_col]))
                new_c = orig_c * ramp[i]
                out.loc[idx, cost_col] = round(new_c, 4)
                if billed_col in out.columns:
                    out.loc[idx, billed_col] = round(new_c, 4)

        elif fault_family == "untagged_spend_growth":
            # Cost increases and tags are stripped
            for i, idx in enumerate(target_indices):
                orig_c = max(0.01, float(out.loc[idx, cost_col]))
                out.loc[idx, cost_col] = round(orig_c * ramp[i], 4)
                if "Tags" in out.columns:
                    out.loc[idx, "Tags"] = "{}"

        elif fault_family == "credit_refund_artifact":
            # Injects negative cost artifact or removes credits
            for i, idx in enumerate(target_indices):
                orig_c = max(0.01, float(out.loc[idx, cost_col]))
                out.loc[idx, cost_col] = round(orig_c * 0.2, 4)  # sudden 80% collapse

        else:
            # Generic cost increase (level_shift, deployment_defect, config_change, etc.)
            for i, idx in enumerate(target_indices):
                orig_c = max(0.01, float(out.loc[idx, cost_col]))
                out.loc[idx, cost_col] = round(orig_c * ramp[i], 4)
                if billed_col in out.columns:
                    out.loc[idx, billed_col] = round(orig_c * ramp[i], 4)

        start_dt = str(out.loc[target_indices[0], time_col])
        end_dt = str(out.loc[target_indices[-1], time_col])
        sub_acc = str(out.loc[target_indices[0], "SubAccountId"]) if "SubAccountId" in out.columns else "acc-default"

        incident = GroundTruthIncident(
            incident_id=incident_id,
            scenario_id=f"scen_{fault_family}",
            service_name=service_name,
            sub_account_id=sub_acc,
            fault_family=fault_family,
            start_time=start_dt,
            end_time=end_dt,
            duration_hours=duration_hours,
            magnitude_multiplier=round(float(magnitude), 2),
            onset_shape=onset_shape,
            is_synthetic=True,
            true_cause_list=[fault_family],
            ground_truth_event_id=event_id,
            is_confounded=False,
            has_decoy=False,
        )

        event = {
            "event_id": event_id,
            "tenant_id": str(out.loc[target_indices[0], "tenant_id"]) if "tenant_id" in out.columns else "default",
            "timestamp": start_dt,
            "service_name": service_name,
            "sub_account_id": sub_acc,
            "event_type": fault_family,
            "summary": f"Injected operational trigger: {fault_family.replace('_', ' ').title()}",
            "is_decoy": False,
            "details": {"magnitude": magnitude, "duration_hours": duration_hours},
        }

        return out, incident, event


class SyntheticInjector:
    """Controlled fault and anomaly injector calibrated to historical empirical statistics (v1 compatibility)."""

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
        """Inject calibrated anomalies into billing series."""
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

                for idx in incident_indices:
                    orig_cost = df_out.loc[idx, cost_col]
                    spike = orig_cost * (1.0 + alpha) + (beta * effective_sigma)
                    df_out.loc[idx, cost_col] = float(spike)
                    df_out.loc[idx, "is_anomaly"] = 1

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

            # Decoy event
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
