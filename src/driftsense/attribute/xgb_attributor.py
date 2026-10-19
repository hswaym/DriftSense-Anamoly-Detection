"""Gradient-boosted decision tree multi-class cause attributor for DriftSense."""

from __future__ import annotations

import datetime
import logging
from typing import Any

import numpy as np
import pandas as pd
import xgboost as xgb

from driftsense.attribute.base import BaseAttributor

logger = logging.getLogger(__name__)


class XGBoostAttributor(BaseAttributor):
    """Multi-class XGBoost classifier attributing anomalies to operational causes."""

    def __init__(
        self,
        name: str = "xgb_attributor",
        n_estimators: int = 100,
        max_depth: int = 4,
        learning_rate: float = 0.05,
        lookback_hours: float = 4.0,
        seed: int = 42,
        taxonomy: list[str] | None = None,
        config: dict[str, Any] | None = None,
        version: str = "1.0.0",
    ) -> None:
        cfg = config or {}
        cfg.update(
            {
                "n_estimators": n_estimators,
                "max_depth": max_depth,
                "learning_rate": learning_rate,
                "lookback_hours": lookback_hours,
                "seed": seed,
            }
        )
        super().__init__(name=name, taxonomy=taxonomy, config=cfg, version=version)
        self.n_estimators = n_estimators
        self.max_depth = max_depth
        self.learning_rate = learning_rate
        self.lookback_hours = lookback_hours
        self.seed = seed
        self.class_to_idx_: dict[str, int] = {c: i for i, c in enumerate(self.taxonomy)}
        self.idx_to_class_: dict[int, str] = {i: c for i, c in enumerate(self.taxonomy)}
        self.model_: xgb.XGBClassifier | None = None
        self.feature_names_: list[str] = []

    def _extract_incident_features(
        self,
        incident: dict[str, Any],
        events: list[dict[str, Any]],
        telemetry: dict[str, Any] | None = None,
    ) -> dict[str, float]:
        """Extract multi-modal temporal proximity, count, and telemetry features."""
        onset = pd.to_datetime(incident.get("onset_timestamp"), utc=True)
        target_svc = str(incident.get("service_id", ""))
        severity = float(incident.get("severity_score", 1.0))

        feat: dict[str, float] = {
            "severity_score": severity,
            "onset_hour": float(onset.hour),
            "onset_dayofweek": float(onset.dayofweek),
        }

        # Initialize event delta and count features for each taxonomy class
        for c in self.taxonomy:
            feat[f"min_delta_{c}"] = 999.0
            feat[f"count_2h_{c}"] = 0.0
            feat[f"count_4h_{c}"] = 0.0
            feat[f"svc_match_{c}"] = 0.0

        feat["count_decoy_events"] = 0.0

        for ev in events:
            ev_start = pd.to_datetime(ev.get("ts_start"), utc=True)
            delta_h = (onset - ev_start).total_seconds() / 3600.0

            if 0.0 <= delta_h <= self.lookback_hours:
                ev_type = str(ev.get("event_type", ""))
                meta_str = str(ev.get("metadata_json", ""))

                if "decoy" in meta_str.lower():
                    feat["count_decoy_events"] += 1.0
                    continue

                if ev_type in self.taxonomy:
                    feat[f"min_delta_{ev_type}"] = min(
                        feat[f"min_delta_{ev_type}"], delta_h
                    )

                    if delta_h <= 2.0:
                        feat[f"count_2h_{ev_type}"] += 1.0
                    feat[f"count_4h_{ev_type}"] += 1.0

                    ev_svc = str(ev.get("service_id", ""))
                    if ev_svc and (ev_svc == target_svc):
                        feat[f"svc_match_{ev_type}"] = 1.0

        return feat

    def fit(
        self,
        incidents: list[dict[str, Any]] | pd.DataFrame,
        events: list[dict[str, Any]] | pd.DataFrame,
        telemetry_df: pd.DataFrame | None = None,
    ) -> XGBoostAttributor:
        if isinstance(incidents, pd.DataFrame):
            incident_list = incidents.to_dict(orient="records")
        else:
            incident_list = list(incidents)

        if isinstance(events, pd.DataFrame):
            event_list = events.to_dict(orient="records")
        else:
            event_list = list(events)

        X_rows = []
        y_rows = []

        # Map unique classes present in training set to contiguous indices 0..K-1
        unique_causes = sorted(
            {
                inc.get("primary_cause", "")
                for inc in incident_list
                if inc.get("primary_cause") in self.taxonomy
            }
        )
        self.class_to_idx_ = {c: i for i, c in enumerate(unique_causes)}
        self.idx_to_class_ = {i: c for i, c in enumerate(unique_causes)}

        for inc in incident_list:
            cause = str(inc.get("primary_cause", ""))
            if cause in self.class_to_idx_:
                feat = self._extract_incident_features(inc, event_list)
                X_rows.append(feat)
                y_rows.append(self.class_to_idx_[cause])

        if len(X_rows) == 0:
            raise ValueError(
                "No valid training incidents provided for XGBoostAttributor."
            )

        df_X = pd.DataFrame(X_rows)
        self.feature_names_ = list(df_X.columns)
        X = df_X.to_numpy(dtype=float)
        y = np.array(y_rows, dtype=int)

        self.model_ = xgb.XGBClassifier(
            n_estimators=self.n_estimators,
            max_depth=self.max_depth,
            learning_rate=self.learning_rate,
            random_state=self.seed,
            objective="multi:softprob" if len(unique_causes) > 2 else "binary:logistic",
            eval_metric="mlogloss" if len(unique_causes) > 2 else "logloss",
            tree_method="hist",
            verbosity=0,
        )
        self.model_.fit(X, y)

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
        if not self.is_fitted or self.model_ is None:
            raise RuntimeError(
                f"Attributor '{self.name}' must be fitted before rank()."
            )

        feat = self._extract_incident_features(incident, nearby_events, telemetry)
        row = [feat.get(col, 0.0) for col in self.feature_names_]
        X = np.array([row], dtype=float)

        probs_raw = self.model_.predict_proba(X)[0]
        # Map probabilities into full canonical taxonomy
        scores = {c: 0.0 for c in self.taxonomy}
        if len(self.idx_to_class_) == 2 and len(probs_raw) == 2:
            for i, p in enumerate(probs_raw):
                cause = self.idx_to_class_.get(i)
                if cause:
                    scores[cause] = float(p)
        else:
            for i, p in enumerate(probs_raw):
                cause = self.idx_to_class_.get(i)
                if cause:
                    scores[cause] = float(p)

        results = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
        return results

    def _get_model_state(self) -> dict[str, Any]:
        return {
            "model": self.model_,
            "feature_names": self.feature_names_,
            "class_to_idx": self.class_to_idx_,
            "idx_to_class": self.idx_to_class_,
            "n_estimators": self.n_estimators,
            "max_depth": self.max_depth,
            "learning_rate": self.learning_rate,
            "lookback_hours": self.lookback_hours,
            "seed": self.seed,
        }

    def _set_model_state(self, state: dict[str, Any]) -> None:
        self.model_ = state["model"]
        self.feature_names_ = state["feature_names"]
        self.class_to_idx_ = state["class_to_idx"]
        self.idx_to_class_ = state["idx_to_class"]
        self.n_estimators = state["n_estimators"]
        self.max_depth = state["max_depth"]
        self.learning_rate = state["learning_rate"]
        self.lookback_hours = state["lookback_hours"]
        self.seed = state["seed"]
