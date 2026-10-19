"""One-Class Support Vector Machine (OC-SVM) anomaly detector for DriftSense."""

from __future__ import annotations

import datetime
from typing import Any

import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler
from sklearn.svm import OneClassSVM

from driftsense.detect.base import BaseAnomalyDetector


class OneClassSVMDetector(BaseAnomalyDetector):
    """Non-linear boundary One-Class SVM detector on residual and telemetry vectors."""

    def __init__(
        self,
        name: str = "ocsvm",
        kernel: str = "rbf",
        nu: float = 0.05,
        gamma: str | float = "scale",
        threshold: float = 0.0,
        config: dict[str, Any] | None = None,
        version: str = "1.0.0",
    ) -> None:
        cfg = config or {}
        cfg.update(
            {
                "kernel": kernel,
                "nu": nu,
                "gamma": gamma,
                "threshold": threshold,
            }
        )
        super().__init__(name=name, threshold=threshold, config=cfg, version=version)
        self.kernel = kernel
        self.nu = nu
        self.gamma = gamma
        self.scaler_: StandardScaler = StandardScaler()
        self.model_: OneClassSVM | None = None

    def _prepare_features(self, df: pd.DataFrame, residual_col: str) -> pd.DataFrame:
        """Extract numeric features suitable for kernel boundary estimation."""
        res = df[residual_col].to_numpy(dtype=float)
        feats: dict[str, Any] = {
            "residual": res,
            "abs_residual": np.abs(res),
        }
        if "ConsumedQuantity" in df.columns:
            feats["ConsumedQuantity"] = df["ConsumedQuantity"].to_numpy(dtype=float)
        if "hour_of_day" in df.columns:
            feats["hour_of_day"] = df["hour_of_day"].to_numpy(dtype=float)

        return pd.DataFrame(feats).fillna(0.0)

    def fit(
        self,
        df_train: pd.DataFrame,
        residual_col: str = "residual",
        service_col: str = "ServiceName",
        time_col: str = "ChargePeriodStart",
        feature_cols: list[str] | None = None,
    ) -> OneClassSVMDetector:
        self.residual_col = residual_col
        self.service_col = service_col
        self.time_col = time_col

        X_train = (
            df_train[feature_cols].fillna(0.0)
            if feature_cols is not None
            else self._prepare_features(df_train, residual_col)
        )
        self.feature_cols_ = list(X_train.columns)

        X_scaled = self.scaler_.fit_transform(X_train)
        self.model_ = OneClassSVM(
            kernel=self.kernel,
            nu=self.nu,
            gamma=self.gamma,
        )
        self.model_.fit(X_scaled)

        self.is_fitted = True
        self.training_timestamp_utc = datetime.datetime.now(
            datetime.timezone.utc
        ).isoformat()
        return self

    def score(self, df: pd.DataFrame) -> np.ndarray:
        if not self.is_fitted or self.model_ is None:
            raise RuntimeError(f"Detector '{self.name}' must be fitted before score().")

        if self.feature_cols_:
            X = (
                df.reindex(columns=self.feature_cols_, fill_value=0.0)
                if all(c in df.columns for c in self.feature_cols_)
                else self._prepare_features(df, self.residual_col).reindex(
                    columns=self.feature_cols_, fill_value=0.0
                )
            )
        else:
            X = self._prepare_features(df, self.residual_col)

        X_scaled = self.scaler_.transform(X)
        # decision_function returns positive for inliers, negative for outliers.
        # Invert so higher positive score = more anomalous.
        raw_dist = self.model_.decision_function(X_scaled)
        return -raw_dist

    def _get_model_state(self) -> dict[str, Any]:
        return {
            "model": self.model_,
            "scaler": self.scaler_,
            "feature_cols": self.feature_cols_,
            "kernel": self.kernel,
            "nu": self.nu,
            "gamma": self.gamma,
        }

    def _set_model_state(self, state: dict[str, Any]) -> None:
        self.model_ = state["model"]
        self.scaler_ = state["scaler"]
        self.feature_cols_ = state["feature_cols"]
        self.kernel = state["kernel"]
        self.nu = state["nu"]
        self.gamma = state["gamma"]
