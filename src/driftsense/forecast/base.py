"""Abstract base interface for DriftSense forecasting models.

Enforces uniform interface across all baseline and ML forecasters:
- fit(df_train, target_col, time_col, service_col)
- predict(df) -> np.ndarray
- save(path) -> Path
- load(path) -> BaseForecaster
All models serialize model metadata, configuration hash, and version.
"""

from __future__ import annotations

import hashlib
import json
import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class BaseForecaster(ABC):
    """Abstract base class for expected-cost forecasting models."""

    def __init__(
        self,
        name: str,
        config: dict[str, Any] | None = None,
        version: str = "1.0.0",
    ) -> None:
        self.name = name
        self.config = config or {}
        self.version = version
        self.is_fitted = False
        self.target_col = "EffectiveCost"
        self.service_col = "ServiceName"
        self.time_col = "ChargePeriodStart"
        self.training_timestamp_utc: str | None = None
        self.config_hash: str = self._compute_config_hash()

    def _compute_config_hash(self) -> str:
        """Compute deterministic SHA256 of model configuration."""
        dumped = json.dumps(self.config, sort_keys=True, default=str)
        return hashlib.sha256(dumped.encode("utf-8")).hexdigest()

    @abstractmethod
    def fit(
        self,
        df_train: pd.DataFrame,
        target_col: str = "EffectiveCost",
        time_col: str = "ChargePeriodStart",
        service_col: str = "ServiceName",
        feature_cols: list[str] | None = None,
    ) -> BaseForecaster:
        """Fit model on historical training partition."""
        ...

    @abstractmethod
    def predict(self, df: pd.DataFrame) -> np.ndarray:
        """Generate point forecasts for input records."""
        ...

    def get_metadata(self) -> dict[str, Any]:
        """Return standardized model metadata dictionary."""
        return {
            "model_name": self.name,
            "version": self.version,
            "config": self.config,
            "config_hash": self.config_hash,
            "is_fitted": self.is_fitted,
            "target_col": self.target_col,
            "service_col": self.service_col,
            "time_col": self.time_col,
            "training_timestamp_utc": self.training_timestamp_utc,
        }

    def save(self, destination: str | Path) -> Path:
        """Serialize model weights and metadata to disk."""
        if not self.is_fitted:
            raise RuntimeError(f"Cannot save unfitted model '{self.name}'.")

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
        logger.info("Saved model '%s' to %s", self.name, save_path)
        return save_path

    @classmethod
    def load(cls, source_path: str | Path) -> BaseForecaster:
        """Deserialize model from disk."""
        path = Path(source_path)
        if not path.is_file():
            raise FileNotFoundError(f"Model file not found: {path}")

        payload = joblib.load(path)
        meta = payload["metadata"]
        instance = cls(
            name=meta["model_name"], config=meta["config"], version=meta["version"]
        )
        instance.target_col = meta.get("target_col", "EffectiveCost")
        instance.service_col = meta.get("service_col", "ServiceName")
        instance.time_col = meta.get("time_col", "ChargePeriodStart")
        instance.training_timestamp_utc = meta.get("training_timestamp_utc")
        instance.config_hash = meta.get("config_hash", "")
        instance._set_model_state(payload["model_state"])
        instance.is_fitted = True
        return instance

    @abstractmethod
    def _get_model_state(self) -> dict[str, Any]:
        """Extract model parameters and weights for serialization."""
        ...

    @abstractmethod
    def _set_model_state(self, state: dict[str, Any]) -> None:
        """Restore model parameters and weights from serialization."""
        ...
