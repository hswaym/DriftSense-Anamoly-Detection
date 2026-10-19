"""Empirical class-prior frequency attribution baseline for DriftSense."""

from __future__ import annotations

import datetime
from collections import Counter
from typing import Any

import pandas as pd

from driftsense.attribute.base import BaseAttributor


class ClassPriorAttributor(BaseAttributor):
    """Class-prior frequency attribution baseline ranker.

    Ranks root-causes deterministically by their marginal historical frequency in the training set.
    """

    def __init__(
        self,
        name: str = "prior_baseline",
        taxonomy: list[str] | None = None,
        config: dict[str, Any] | None = None,
        version: str = "1.0.0",
    ) -> None:
        super().__init__(name=name, taxonomy=taxonomy, config=config, version=version)
        self.class_frequencies_: dict[str, float] = {}
        self.sorted_priors_: list[tuple[str, float]] = []

    def fit(
        self,
        incidents: list[dict[str, Any]] | pd.DataFrame,
        events: list[dict[str, Any]] | pd.DataFrame,
        telemetry_df: pd.DataFrame | None = None,
    ) -> ClassPriorAttributor:
        if isinstance(incidents, pd.DataFrame):
            causes = incidents["primary_cause"].tolist()
        else:
            causes = [str(inc.get("primary_cause", "")) for inc in incidents]

        total = max(1, len(causes))
        counts = Counter(causes)
        self.class_frequencies_ = {}
        for c in self.taxonomy:
            self.class_frequencies_[c] = float(counts.get(c, 0) / total)

        self.sorted_priors_ = sorted(
            self.class_frequencies_.items(), key=lambda kv: kv[1], reverse=True
        )

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

        return list(self.sorted_priors_)

    def _get_model_state(self) -> dict[str, Any]:
        return {
            "class_frequencies": self.class_frequencies_,
            "sorted_priors": self.sorted_priors_,
        }

    def _set_model_state(self, state: dict[str, Any]) -> None:
        self.class_frequencies_ = state["class_frequencies"]
        self.sorted_priors_ = state["sorted_priors"]
