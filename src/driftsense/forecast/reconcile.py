"""Hierarchical forecast reconciliation engine for DriftSense v2.

Ensures coherence across aggregation levels:
sum_{s in Services} y_tilde_{s, t} == y_tilde_{Total, t}
Supports:
- bottom_up: Aggregates service-level forecasts up to total account level.
- top_down: Proportions top-level forecast down to service components.
- mint_ols: Optimal projection using structural summing matrix S and OLS/WLS weighting.
"""

from __future__ import annotations

import logging
from typing import Literal

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

ReconcileMethod = Literal["bottom_up", "top_down", "mint_ols"]


class HierarchicalReconciler:
    """Reconciles bottom-level (service) and top-level (total) forecasts."""

    def __init__(
        self,
        method: ReconcileMethod = "bottom_up",
    ) -> None:
        self.method = method
        self.service_shares_: dict[str, float] = {}

    def fit(
        self,
        df_train: pd.DataFrame,
        service_col: str = "ServiceName",
        target_col: str = "EffectiveCost",
    ) -> HierarchicalReconciler:
        """Estimate historical service proportions from training partition."""
        totals = df_train.groupby(service_col)[target_col].sum()
        grand_total = float(totals.sum())
        if grand_total > 0:
            self.service_shares_ = (totals / grand_total).to_dict()
        else:
            n_services = max(1, df_train[service_col].nunique())
            self.service_shares_ = {
                str(s): 1.0 / n_services for s in df_train[service_col].unique()
            }
        return self

    def reconcile(
        self,
        service_forecasts: dict[str, np.ndarray],
        total_forecast: np.ndarray | None = None,
    ) -> tuple[dict[str, np.ndarray], np.ndarray]:
        """Reconcile forecasts across services and total account spend.

        Args:
            service_forecasts: Dict mapping service name to predicted 1D array.
            total_forecast: Optional top-level independent forecast.

        Returns:
            tuple[reconciled_services_dict, reconciled_total_array]
        """
        services = sorted(service_forecasts.keys())
        if not services:
            return {}, np.array([])

        n_steps = len(service_forecasts[services[0]])
        Y_bottom = np.column_stack([service_forecasts[s] for s in services])

        if self.method == "bottom_up":
            # Reconciled total is exact sum of bottom level
            Y_total_rec = np.sum(Y_bottom, axis=1)
            reconciled_services = {s: Y_bottom[:, i] for i, s in enumerate(services)}
            return reconciled_services, Y_total_rec

        if total_forecast is None:
            # Fall back to bottom_up if total_forecast not provided
            Y_total_rec = np.sum(Y_bottom, axis=1)
            reconciled_services = {s: Y_bottom[:, i] for i, s in enumerate(services)}
            return reconciled_services, Y_total_rec

        if self.method == "top_down":
            # Disaggregate total forecast using historical proportions
            reconciled_services = {}
            for s in services:
                share = self.service_shares_.get(s, 1.0 / len(services))
                reconciled_services[s] = np.maximum(0.0, total_forecast * share)
            Y_total_rec = np.sum(np.column_stack(list(reconciled_services.values())), axis=1)
            return reconciled_services, Y_total_rec

        if self.method == "mint_ols":
            # Summing matrix S: top row is ones (1 x m), bottom is identity (m x m)
            # Y_hat = [total_hat, bottom_hat_1, ..., bottom_hat_m]^T
            m = len(services)
            S = np.vstack([np.ones((1, m)), np.eye(m)])  # ((m+1) x m)

            # OLS projection matrix P = (S^T S)^{-1} S^T
            P = np.linalg.inv(S.T @ S) @ S.T  # (m x (m+1))

            reconciled_services = {}
            Y_reconciled_bottom = np.zeros_like(Y_bottom)

            for t in range(n_steps):
                y_hat_t = np.concatenate([[total_forecast[t]], Y_bottom[t, :]])
                y_tilde_t = P @ y_hat_t
                Y_reconciled_bottom[t, :] = np.maximum(0.0, y_tilde_t)

            for i, s in enumerate(services):
                reconciled_services[s] = Y_reconciled_bottom[:, i]

            Y_total_rec = np.sum(Y_reconciled_bottom, axis=1)
            return reconciled_services, Y_total_rec

        raise ValueError(f"Unknown reconciliation method: {self.method}")


__all__ = ["HierarchicalReconciler"]
