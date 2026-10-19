"""Abstract base interface for DriftSense anomaly detectors.

Enforces uniform interface across statistical and ML anomaly detection models:
- fit(df_train, residual_col, feature_cols=None) -> BaseAnomalyDetector
- score(df) -> np.ndarray (continuous anomaly score, higher = more anomalous)
- predict(df, threshold=None) -> np.ndarray (binary 0 or 1 labels)
- save(path) -> Path
- load(path) -> BaseAnomalyDetector
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


class BaseAnomalyDetector(ABC):
    """Abstract base class for residual and telemetry anomaly detectors."""

    def __init__(
        self,
        name: str,
        threshold: float = 3.0,
        config: dict[str, Any] | None = None,
        version: str = "1.0.0",
    ) -> None:
        self.name = name
        self.threshold = threshold
        self.config = config or {}
        self.version = version
        self.is_fitted = False
        self.residual_col = "residual"
        self.service_col = "ServiceName"
        self.time_col = "ChargePeriodStart"
        self.feature_cols_: list[str] = []
        self.training_timestamp_utc: str | None = None
        self.config_hash: str = self._compute_config_hash()

    def _compute_config_hash(self) -> str:
        """Compute deterministic SHA256 of detector configuration."""
        dumped = json.dumps(self.config, sort_keys=True, default=str)
        return hashlib.sha256(dumped.encode("utf-8")).hexdigest()

    @abstractmethod
    def fit(
        self,
        df_train: pd.DataFrame,
        residual_col: str = "residual",
        service_col: str = "ServiceName",
        time_col: str = "ChargePeriodStart",
        feature_cols: list[str] | None = None,
    ) -> BaseAnomalyDetector:
        """Fit detector baselines or distributions on training residuals."""
        ...

    @abstractmethod
    def score(self, df: pd.DataFrame) -> np.ndarray:
        """Compute continuous anomaly score (higher = more anomalous)."""
        ...

    def predict(self, df: pd.DataFrame, threshold: float | None = None) -> np.ndarray:
        """Generate binary anomaly flags (1 = anomaly, 0 = normal)."""
        thresh = threshold if threshold is not None else self.threshold
        scores = self.score(df)
        return (scores >= thresh).astype(int)

    def get_metadata(self) -> dict[str, Any]:
        """Return standardized model metadata dictionary."""
        return {
            "detector_name": self.name,
            "version": self.version,
            "threshold": self.threshold,
            "config": self.config,
            "config_hash": self.config_hash,
            "is_fitted": self.is_fitted,
            "residual_col": self.residual_col,
            "service_col": self.service_col,
            "time_col": self.time_col,
            "feature_cols": self.feature_cols_,
            "training_timestamp_utc": self.training_timestamp_utc,
        }

    def save(self, destination: str | Path) -> Path:
        """Serialize detector state and metadata to disk."""
        if not self.is_fitted:
            raise RuntimeError(f"Cannot save unfitted detector '{self.name}'.")

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
        logger.info("Saved detector '%s' to %s", self.name, save_path)
        return save_path

    @classmethod
    def load(cls, source_path: str | Path) -> BaseAnomalyDetector:
        """Deserialize detector from disk."""
        path = Path(source_path)
        if not path.is_file():
            raise FileNotFoundError(f"Detector checkpoint not found: {path}")

        payload = joblib.load(path)
        meta = payload["metadata"]
        instance = cls(
            name=meta["detector_name"],
            threshold=meta.get("threshold", 3.0),
            config=meta["config"],
            version=meta["version"],
        )
        instance.residual_col = meta.get("residual_col", "residual")
        instance.service_col = meta.get("service_col", "ServiceName")
        instance.time_col = meta.get("time_col", "ChargePeriodStart")
        instance.feature_cols_ = meta.get("feature_cols", [])
        instance.training_timestamp_utc = meta.get("training_timestamp_utc")
        instance.config_hash = meta.get("config_hash", "")
        instance._set_model_state(payload["model_state"])
        instance.is_fitted = True
        return instance

    @abstractmethod
    def _get_model_state(self) -> dict[str, Any]:
        """Extract detector internal state for serialization."""
        ...

    @abstractmethod
    def _set_model_state(self, state: dict[str, Any]) -> None:
        """Restore detector internal state from serialization."""
        ...
