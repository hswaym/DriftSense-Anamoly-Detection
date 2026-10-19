"""Abstract base interface for DriftSense root-cause attribution models.

Enforces uniform interface across baseline rankers and ML attributors:
- fit(incidents: list[dict] | pd.DataFrame, events: list[dict] | pd.DataFrame, telemetry_df: pd.DataFrame | None = None)
- rank(incident: dict, nearby_events: list[dict], telemetry: dict | None = None) -> list[tuple[str, float]]
- predict_top_k(incidents: list[dict], events: list[dict], telemetry_df: pd.DataFrame | None = None, k: int = 3) -> list[list[str]]
- save(path) -> Path
- load(path) -> BaseAttributor
"""

from __future__ import annotations

import hashlib
import json
import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

import joblib
import pandas as pd

logger = logging.getLogger(__name__)

CANONICAL_TAXONOMY = [
    "DEPLOYMENT_DEFECT",
    "AUTOSCALING_OVERPROVISION",
    "CONFIG_MODIFICATION",
    "EXTERNAL_TRAFFIC_SURGE",
    "ORPHANED_STORAGE_ACCUMULATION",
    "RUNAWAY_BATCH_PROCESS",
]


class BaseAttributor(ABC):
    """Abstract base class for root cause rankers and attribution models."""

    def __init__(
        self,
        name: str,
        taxonomy: list[str] | None = None,
        config: dict[str, Any] | None = None,
        version: str = "1.0.0",
    ) -> None:
        self.name = name
        self.taxonomy = taxonomy or list(CANONICAL_TAXONOMY)
        self.config = config or {}
        self.version = version
        self.is_fitted = False
        self.training_timestamp_utc: str | None = None
        self.config_hash: str = self._compute_config_hash()

    def _compute_config_hash(self) -> str:
        """Compute deterministic SHA256 of model configuration."""
        dumped = json.dumps(
            {"name": self.name, "taxonomy": self.taxonomy, "config": self.config},
            sort_keys=True,
            default=str,
        )
        return hashlib.sha256(dumped.encode("utf-8")).hexdigest()

    @abstractmethod
    def fit(
        self,
        incidents: list[dict[str, Any]] | pd.DataFrame,
        events: list[dict[str, Any]] | pd.DataFrame,
        telemetry_df: pd.DataFrame | None = None,
    ) -> BaseAttributor:
        """Fit attribution model or empirical priors on historical incidents."""
        ...

    @abstractmethod
    def rank(
        self,
        incident: dict[str, Any],
        nearby_events: list[dict[str, Any]],
        telemetry: dict[str, Any] | None = None,
    ) -> list[tuple[str, float]]:
        """Return list of (cause, confidence_score) tuples sorted in descending order."""
        ...

    def predict_top_k(
        self,
        incidents: list[dict[str, Any]] | pd.DataFrame,
        events: list[dict[str, Any]] | pd.DataFrame,
        telemetry_df: pd.DataFrame | None = None,
        k: int = 3,
    ) -> list[list[str]]:
        """Generate top-k predicted causes for each input incident."""
        if isinstance(incidents, pd.DataFrame):
            incident_list = incidents.to_dict(orient="records")
        else:
            incident_list = list(incidents)

        if isinstance(events, pd.DataFrame):
            event_list = events.to_dict(orient="records")
        else:
            event_list = list(events)

        results: list[list[str]] = []
        for inc in incident_list:
            ranked = self.rank(inc, event_list, telemetry=None)
            top_causes = [cause for cause, _ in ranked[:k]]
            results.append(top_causes)

        return results

    def get_metadata(self) -> dict[str, Any]:
        """Return standardized model metadata dictionary."""
        return {
            "attributor_name": self.name,
            "version": self.version,
            "taxonomy": self.taxonomy,
            "config": self.config,
            "config_hash": self.config_hash,
            "is_fitted": self.is_fitted,
            "training_timestamp_utc": self.training_timestamp_utc,
        }

    def save(self, destination: str | Path) -> Path:
        """Serialize attributor model state to disk."""
        if not self.is_fitted:
            raise RuntimeError(f"Cannot save unfitted attributor '{self.name}'.")

        dest = Path(destination)
        if dest.is_dir() or not dest.suffix:
            dest.mkdir(parents=True, exist_ok=True)
            save_path = dest / f"{self.name}.joblib"
        else:
            dest.parent.mkdir(parents=True, exist_ok=True)
            save_path = dest

        payload = {
            "metadata": self.get_metadata(),
            "model_state": self._get_model_state(),
        }
        joblib.dump(payload, save_path)
        logger.info("Saved attributor '%s' to %s", self.name, save_path)
        return save_path

    @classmethod
    def load(cls, source_path: str | Path) -> BaseAttributor:
        """Deserialize attributor from disk."""
        path = Path(source_path)
        if not path.is_file():
            raise FileNotFoundError(f"Attributor file not found: {path}")

        payload = joblib.load(path)
        meta = payload["metadata"]
        instance = cls(
            name=meta["attributor_name"],
            taxonomy=meta.get("taxonomy", CANONICAL_TAXONOMY),
            config=meta["config"],
            version=meta["version"],
        )
        instance.training_timestamp_utc = meta.get("training_timestamp_utc")
        instance.config_hash = meta.get("config_hash", "")
        instance._set_model_state(payload["model_state"])
        instance.is_fitted = True
        return instance

    @abstractmethod
    def _get_model_state(self) -> dict[str, Any]:
        """Extract internal state for serialization."""
        ...

    @abstractmethod
    def _set_model_state(self, state: dict[str, Any]) -> None:
        """Restore internal state from serialization."""
        ...
