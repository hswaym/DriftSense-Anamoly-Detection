"""TreeSHAP explainer wrapper for DriftSense forecasting and attribution models.

Implements local and dataset-level feature attribution using SHAP (TreeExplainer)
with strict additivity verification:
    f(x) = phi_0 + sum_j phi_j(x)
where phi_0 is the baseline/expected model output and phi_j is the attribution of feature j.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd
import shap

logger = logging.getLogger(__name__)


@dataclass
class InstanceExplanation:
    """Structured feature attribution report for a single prediction point."""

    prediction_id: str
    base_value: float
    model_output: float
    feature_values: dict[str, Any]
    attribution_values: dict[str, float]
    top_positive_drivers: list[tuple[str, float]]
    top_negative_drivers: list[tuple[str, float]]
    additivity_error: float
    additivity_verified: bool

    def to_dict(self) -> dict[str, Any]:
        """Convert explanation to JSON-serializable dictionary."""
        return {
            "prediction_id": self.prediction_id,
            "base_value": float(self.base_value),
            "model_output": float(self.model_output),
            "feature_values": {
                k: float(v)
                if isinstance(v, (np.floating, float, int, np.integer))
                else str(v)
                for k, v in self.feature_values.items()
            },
            "attribution_values": {
                k: float(v) for k, v in self.attribution_values.items()
            },
            "top_positive_drivers": [
                (k, float(v)) for k, v in self.top_positive_drivers
            ],
            "top_negative_drivers": [
                (k, float(v)) for k, v in self.top_negative_drivers
            ],
            "additivity_error": float(self.additivity_error),
            "additivity_verified": bool(self.additivity_verified),
        }


class TreeSHAPExplainer:
    """Wrapper around shap.TreeExplainer providing strict additivity and formatting."""

    def __init__(
        self,
        model: Any,
        feature_names: list[str] | None = None,
        atol: float = 1e-3,
    ) -> None:
        """Initialize TreeSHAPExplainer.

        Args:
            model: Tree-based model (e.g. XGBoostForecaster, xgb.Booster, or XGBClassifier).
            feature_names: Ordered feature names corresponding to model inputs.
            atol: Maximum absolute error allowed for the SHAP additivity invariant.
        """
        self.atol = atol
        self.feature_names = feature_names

        # Extract native tree model if wrapped inside DriftSense classes
        if hasattr(model, "model_") and model.model_ is not None:
            self.raw_model = model.model_
            if self.feature_names is None and hasattr(model, "feature_names_"):
                self.feature_names = model.feature_names_
        elif hasattr(model, "model") and model.model is not None:
            self.raw_model = model.model
            if self.feature_names is None and hasattr(model, "feature_names"):
                self.feature_names = model.feature_names
        else:
            self.raw_model = model

        logger.info("Initializing shap.TreeExplainer on underlying tree model...")
        self.explainer = shap.TreeExplainer(self.raw_model)

        # Determine expected/base value
        expected = self.explainer.expected_value
        if isinstance(expected, np.ndarray):
            if expected.ndim == 0:
                self.expected_value = float(expected.item())
            else:
                self.expected_value = [float(v) for v in expected.ravel()]
        else:
            self.expected_value = float(expected)

    def _prepare_features(
        self, X: pd.DataFrame | np.ndarray
    ) -> tuple[np.ndarray, list[str]]:
        """Normalize input features to numpy array and extract column names."""
        if isinstance(X, pd.DataFrame):
            cols = self.feature_names or list(X.columns)
            X_mat = (
                X[cols].to_numpy(dtype=float)
                if self.feature_names
                else X.to_numpy(dtype=float)
            )
            feature_names = cols
        else:
            X_mat = np.asarray(X, dtype=float)
            feature_names = self.feature_names or [
                f"feature_{i}" for i in range(X_mat.shape[1])
            ]
        return X_mat, feature_names

    def explain(
        self,
        X: pd.DataFrame | np.ndarray,
        check_additivity: bool = True,
    ) -> np.ndarray:
        """Compute raw SHAP values for dataset X.

        Args:
            X: Input feature matrix or DataFrame.
            check_additivity: If True, asserts SHAP additivity invariant.

        Returns:
            np.ndarray of SHAP values matching X's shape.
        """
        X_mat, _ = self._prepare_features(X)
        shap_vals = self.explainer.shap_values(X_mat)

        if check_additivity:
            self.verify_additivity(X_mat, shap_vals)

        return shap_vals

    def verify_additivity(
        self,
        X: np.ndarray,
        shap_values: np.ndarray,
        atol: float | None = None,
    ) -> bool:
        """Verify the additivity property: sum(shap_values, axis=1) + base_value == model_output.

        Raises:
            AssertionError: If any instance exceeds tolerance.
        """
        tolerance = atol if atol is not None else self.atol

        # For XGBoost regressors or single-output models
        if isinstance(self.expected_value, (float, int)) or (
            isinstance(self.expected_value, (list, np.ndarray))
            and len(self.expected_value) == 1
        ):
            base_val = (
                float(self.expected_value[0])
                if isinstance(self.expected_value, (list, np.ndarray))
                else float(self.expected_value)
            )
            reconstructed = np.sum(shap_values, axis=1) + base_val

            # Obtain model predictions in margin space
            if hasattr(self.raw_model, "predict"):
                preds = self.raw_model.predict(X)
            else:
                preds = reconstructed

            diff = np.abs(reconstructed - preds)
            max_err = float(np.max(diff))
            if max_err > tolerance:
                raise AssertionError(
                    f"A9.1 Additivity Check Failed: Max discrepancy {max_err:.6f} exceeds tolerance {tolerance:.6f}"
                )
            return True

        # Multi-class output (shap_values is 3D or list of 2D)
        if isinstance(shap_values, list):
            for class_idx, (s_class, base_v) in enumerate(
                zip(shap_values, self.expected_value)
            ):
                reconstructed = np.sum(s_class, axis=1) + base_v
                if hasattr(self.raw_model, "predict_proba"):
                    preds = self.raw_model.predict_proba(X)[:, class_idx]
                else:
                    preds = reconstructed
                diff = np.abs(reconstructed - preds)
                max_err = float(np.max(diff))
                if max_err > tolerance:
                    raise AssertionError(
                        f"A9.1 Multi-class Additivity Failed (class {class_idx}): Max error {max_err:.6f} > {tolerance:.6f}"
                    )
        return True

    def explain_instance(
        self,
        row: pd.Series | dict | np.ndarray,
        prediction_id: str = "pred_0",
        top_k: int = 5,
    ) -> InstanceExplanation:
        """Compute structured attribution explanation for a single prediction point.

        Args:
            row: Single observation features.
            prediction_id: Unique identifier for the prediction.
            top_k: Number of positive and negative drivers to extract.

        Returns:
            InstanceExplanation object.
        """
        if isinstance(row, dict):
            row_df = pd.DataFrame([row])
            X_mat, feat_names = self._prepare_features(row_df)
            feat_vals = row
        elif isinstance(row, pd.Series):
            row_df = pd.DataFrame([row])
            X_mat, feat_names = self._prepare_features(row_df)
            feat_vals = row.to_dict()
        else:
            X_mat = np.atleast_2d(row)
            feat_names = self.feature_names or [
                f"feat_{i}" for i in range(X_mat.shape[1])
            ]
            feat_vals = {
                feat_names[i]: float(X_mat[0, i]) for i in range(len(feat_names))
            }

        shap_vals = self.explainer.shap_values(X_mat)
        if isinstance(shap_vals, list):
            # If multi-class, use the highest probability class
            vals = shap_vals[0][0]
            base_val = (
                float(self.expected_value[0])
                if isinstance(self.expected_value, (list, np.ndarray))
                else float(self.expected_value)
            )
        elif shap_vals.ndim == 3:
            vals = shap_vals[0, :, 0]
            base_val = (
                float(self.expected_value[0])
                if isinstance(self.expected_value, (list, np.ndarray))
                else float(self.expected_value)
            )
        else:
            vals = shap_vals[0]
            base_val = (
                float(self.expected_value[0])
                if isinstance(self.expected_value, (list, np.ndarray))
                else float(self.expected_value)
            )

        # Map to dict
        attr_dict = {feat_names[i]: float(vals[i]) for i in range(len(feat_names))}

        # Calculate model output and additivity
        reconstructed = base_val + sum(vals)
        if hasattr(self.raw_model, "predict"):
            pred_out = float(self.raw_model.predict(X_mat)[0])
        else:
            pred_out = float(reconstructed)

        err = float(abs(reconstructed - pred_out))
        verified = err <= self.atol

        # Rank positive and negative drivers
        sorted_drivers = sorted(attr_dict.items(), key=lambda kv: kv[1], reverse=True)
        pos_drivers = [(k, v) for k, v in sorted_drivers if v > 0][:top_k]
        neg_drivers = [
            (k, v) for k, v in sorted(attr_dict.items(), key=lambda kv: kv[1]) if v < 0
        ][:top_k]

        return InstanceExplanation(
            prediction_id=prediction_id,
            base_value=base_val,
            model_output=pred_out,
            feature_values=feat_vals,
            attribution_values=attr_dict,
            top_positive_drivers=pos_drivers,
            top_negative_drivers=neg_drivers,
            additivity_error=err,
            additivity_verified=verified,
        )
