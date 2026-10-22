"""Scenario orchestration engine for DriftSense v2.

Coordinates calibrated fault injection, decoy event generation, and confounder synthesis.
Produces strictly segregated outputs:
1. Canonical billing records (contains zero ground-truth labels).
2. Candidate operational events (fault triggers + >=3:1 decoys + confounders).
3. Ground-truth incident annotations (quarantined).
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from driftsense.synth.calibrate import calibrate_from_dataframe
from driftsense.synth.confounders import ConfounderGenerator
from driftsense.synth.decoys import DecoyGenerator
from driftsense.synth.injector import (
    DEV_FAULT_FAMILIES,
    HOLDOUT_RESERVED_FAULT_FAMILIES,
    CalibratedFaultInjector,
)
from driftsense.synth.labels import (
    GroundTruthIncident,
    labels_to_dataframe,
    verify_label_isolation,
)


class ScenarioOrchestrator:
    """Orchestrates comprehensive benchmark scenario synthesis."""

    def __init__(
        self,
        seed: int = 42,
        is_holdout: bool = False,
        decoy_to_fault_ratio: float = 3.0,
        min_faults_per_service: int = 1,
        max_faults_per_service: int = 3,
    ) -> None:
        self.seed = seed
        self.is_holdout = is_holdout
        self.decoy_ratio = decoy_to_fault_ratio
        self.min_faults = min_faults_per_service
        self.max_faults = max_faults_per_service

        # Enforce Leave-Family-Out Partitioning
        if is_holdout:
            self.allowed_families = HOLDOUT_RESERVED_FAULT_FAMILIES
        else:
            self.allowed_families = DEV_FAULT_FAMILIES

        self.injector = CalibratedFaultInjector(
            seed=seed,
            allowed_fault_families=self.allowed_families,
        )
        self.decoy_gen = DecoyGenerator(
            seed=seed + 1000,
            decoy_to_fault_ratio=decoy_to_fault_ratio,
        )
        self.confounder_gen = ConfounderGenerator(seed=seed + 2000)

    def generate_scenario(
        self,
        df_clean: pd.DataFrame,
        scenario_name: str = "benchmark_scenario",
        time_col: str = "ChargePeriodStart",
        service_col: str = "ServiceName",
        cost_col: str = "EffectiveCost",
        quantity_col: str = "ConsumedQuantity",
    ) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict[str, Any]]:
        """Generate end-to-end benchmark dataset with faults, decoys, and labels.

        Returns:
            tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict]:
            1. df_injected (Canonical billing records, NO labels)
            2. df_events (Candidate operational events: faults + decoys + confounders)
            3. df_labels (Segregated ground-truth labels)
            4. scenario_manifest (Summary dictionary)
        """
        df_injected = df_clean.copy()
        services = df_clean[service_col].unique().tolist()
        sub_accounts = df_clean["SubAccountId"].unique().tolist() if "SubAccountId" in df_clean.columns else ["acc-default"]

        ground_truth_labels: list[GroundTruthIncident] = []
        candidate_events: list[dict[str, Any]] = []

        # 1. Calibrate empirical baseline
        calibrate_from_dataframe(df_clean, source_name=scenario_name)

        # 2. Inject faults per service
        for s_idx, service in enumerate(services):
            s_mask = df_injected[service_col] == service
            n_rows = s_mask.sum()
            if n_rows < 15:
                continue

            n_faults = self.injector.rng.integers(self.min_faults, self.max_faults + 1)
            used_starts: set[int] = set()

            for _ in range(n_faults):
                duration = int(self.injector.rng.integers(self.injector.min_duration, self.injector.max_duration + 1))
                max_start = max(1, n_rows - duration - 1)
                start_i = int(self.injector.rng.integers(0, max_start))

                if any(abs(start_i - us) < duration for us in used_starts):
                    continue
                used_starts.add(start_i)

                family = str(self.injector.rng.choice(self.allowed_families))
                mag = float(self.injector.rng.uniform(*self.injector.magnitude_range))
                onset = str(self.injector.rng.choice(["abrupt", "gradual_linear", "step"]))

                df_injected, label, event = self.injector.inject_incident(
                    df=df_injected,
                    service_name=service,
                    start_idx=start_i,
                    duration_hours=duration,
                    fault_family=family,
                    magnitude=mag,
                    onset_shape=onset,
                    cost_col=cost_col,
                    quantity_col=quantity_col,
                    time_col=time_col,
                )
                ground_truth_labels.append(label)
                candidate_events.append(event)

        # 3. Generate Decoys (>= 3:1 ratio)
        decoys = self.decoy_gen.generate_decoys_for_timeline(
            time_series=df_injected[time_col],
            service_names=services,
            sub_account_ids=sub_accounts,
            n_faults=len(ground_truth_labels),
        )
        for d in decoys:
            candidate_events.append({
                "event_id": d.event_id,
                "tenant_id": d.tenant_id,
                "timestamp": d.timestamp,
                "service_name": d.service_name,
                "sub_account_id": d.sub_account_id,
                "event_type": d.event_type,
                "summary": d.summary,
                "is_decoy": True,
                "details": d.details or {},
            })

        # 4. Generate Silent Major Change Confounder
        if services:
            silent_event = self.confounder_gen.generate_silent_major_change_event(
                service_name=services[0],
                timestamp=str(df_injected.iloc[min(5, len(df_injected) - 1)][time_col]),
            )
            candidate_events.append(silent_event)

        # 5. Format DataFrames
        df_events = pd.DataFrame(candidate_events)
        df_labels = labels_to_dataframe(ground_truth_labels)

        # 6. Verify Label Isolation (Invariant C6)
        verify_label_isolation(list(df_injected.columns))

        manifest = {
            "scenario_name": scenario_name,
            "is_holdout": self.is_holdout,
            "seed": self.seed,
            "allowed_families": self.allowed_families,
            "total_faults_injected": len(ground_truth_labels),
            "total_events_generated": len(candidate_events),
            "decoy_events_count": len(decoys) + 1,
            "decoy_to_fault_ratio": round(len(candidate_events) / max(1, len(ground_truth_labels)), 2),
            "clean_records": len(df_clean),
            "injected_records": len(df_injected),
        }

        return df_injected, df_events, df_labels, manifest
