"""Temporal-precedence correlation attribution ranker for DriftSense."""

from __future__ import annotations

import datetime
from typing import Any

import numpy as np
import pandas as pd

from driftsense.attribute.base import BaseAttributor


class TemporalCorrelationAttributor(BaseAttributor):
    """Heuristic attribution ranker based on temporal proximity and service affinity."""

    def __init__(
        self,
        name: str = "correlation",
        lookback_hours: float = 3.0,
        decay_halflife_hours: float = 1.0,
        service_match_multiplier: float = 2.0,
        taxonomy: list[str] | None = None,
        config: dict[str, Any] | None = None,
        version: str = "1.0.0",
    ) -> None:
        cfg = config or {}
        cfg.update(
            {
                "lookback_hours": lookback_hours,
                "decay_halflife_hours": decay_halflife_hours,
                "service_match_multiplier": service_match_multiplier,
            }
        )
        super().__init__(name=name, taxonomy=taxonomy, config=cfg, version=version)
        self.lookback_hours = lookback_hours
        self.decay_halflife_hours = decay_halflife_hours
        self.service_match_multiplier = service_match_multiplier
        self.priors_: dict[str, float] = {}

    def fit(
        self,
        incidents: list[dict[str, Any]] | pd.DataFrame,
        events: list[dict[str, Any]] | pd.DataFrame,
        telemetry_df: pd.DataFrame | None = None,
    ) -> TemporalCorrelationAttributor:
        # Fit fallback marginal priors
        if isinstance(incidents, pd.DataFrame):
            causes = incidents["primary_cause"].tolist()
        else:
            causes = [str(inc.get("primary_cause", "")) for inc in incidents]

        total = max(1, len(causes))
        self.priors_ = {c: float(causes.count(c) / total) for c in self.taxonomy}

        self.is_fitted = True
        self.training_timestamp_utc = datetime.datetime.now(
            datetime.timezone.utc
        ).isoformat()
        return self

    def rank(
        self,
        incident: dict[str, Any],
        nearby_events: list[dict[str, Any]],
        telemetry: dict[str, Any] | None = None,
    ) -> list[tuple[str, float]]:
        if not self.is_fitted:
            raise RuntimeError(
                f"Attributor '{self.name}' must be fitted before rank()."
            )

        onset = pd.to_datetime(incident.get("onset_timestamp"), utc=True)
        target_svc = str(incident.get("service_id", ""))

        scores = {c: self.priors_.get(c, 0.001) for c in self.taxonomy}

        for ev in nearby_events:
            ev_start = pd.to_datetime(ev.get("ts_start"), utc=True)
            delta_hours = (onset - ev_start).total_seconds() / 3600.0

            # Causal window: event must precede or coincide with onset
            if 0.0 <= delta_hours <= self.lookback_hours:
                ev_type = str(ev.get("event_type", ""))
                if ev_type in scores:
                    # Ignore decoy events
                    meta_str = str(ev.get("metadata_json", ""))
                    if "decoy" in meta_str.lower():
                        continue

                    # Exponential decay weighting
                    w = np.exp(-delta_hours / self.decay_halflife_hours)

                    # Service affinity bonus
                    ev_svc = str(ev.get("service_id", ""))
                    if ev_svc and (ev_svc == target_svc):
                        w *= self.service_match_multiplier

                    scores[ev_type] += float(w)

        sorted_causes = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
        return sorted_causes

    def _get_model_state(self) -> dict[str, Any]:
        return {
            "lookback_hours": self.lookback_hours,
            "decay_halflife_hours": self.decay_halflife_hours,
            "service_match_multiplier": self.service_match_multiplier,
            "priors": self.priors_,
        }

    def _set_model_state(self, state: dict[str, Any]) -> None:
        self.lookback_hours = state["lookback_hours"]
        self.decay_halflife_hours = state["decay_halflife_hours"]
        self.service_match_multiplier = state["service_match_multiplier"]
        self.priors_ = state["priors"]
