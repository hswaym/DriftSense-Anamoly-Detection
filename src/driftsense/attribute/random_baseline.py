"""Uniform random attribution baseline for DriftSense."""

from __future__ import annotations

import datetime
from typing import Any

import numpy as np
import pandas as pd

from driftsense.attribute.base import BaseAttributor


class RandomAttributor(BaseAttributor):
    """Uniform random attribution baseline ranker."""

    def __init__(
        self,
        name: str = "random_baseline",
        seed: int = 42,
        taxonomy: list[str] | None = None,
        config: dict[str, Any] | None = None,
        version: str = "1.0.0",
    ) -> None:
        cfg = config or {}
        cfg["seed"] = seed
        super().__init__(name=name, taxonomy=taxonomy, config=cfg, version=version)
        self.seed = seed
        self.rng = np.random.default_rng(seed)

    def fit(
        self,
        incidents: list[dict[str, Any]] | pd.DataFrame,
        events: list[dict[str, Any]] | pd.DataFrame,
        telemetry_df: pd.DataFrame | None = None,
    ) -> RandomAttributor:
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

        inc_key = str(incident.get("label_id", incident.get("onset_timestamp", "0")))
        incident_seed = (abs(hash(inc_key)) + self.seed) % (2**31 - 1)
        rng = np.random.default_rng(incident_seed)

        shuffled = list(self.taxonomy)
        rng.shuffle(shuffled)
        n = len(shuffled)
        return [(cause, float(1.0 - i / n)) for i, cause in enumerate(shuffled)]

    def _get_model_state(self) -> dict[str, Any]:
        return {"seed": self.seed}

    def _set_model_state(self, state: dict[str, Any]) -> None:
        self.seed = state["seed"]
        self.rng = np.random.default_rng(self.seed)
