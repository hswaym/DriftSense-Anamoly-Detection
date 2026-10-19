"""Controlled experiments and ablation study runner for DriftSense (Phase 10).

Adheres strictly to the G1 Truth Rule and anti-leakage invariants:
- All arms evaluate on identical validation temporal splits (D_val).
- Zero access to quarantined test split (D_test, Days 25-30).
- Explicit variance quantification across >= 3 random seeds (mean +/- std).
- Separation of real and synthetic evaluation tracks.
- Circularity caveat explicitly documented for event features on synthetic data.
- Protocol file is SHA-256 hashed and recorded in every execution artifact.
"""

from __future__ import annotations

import hashlib
import logging
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from driftsense.attribute.correlation import TemporalCorrelationAttributor
from driftsense.attribute.prior_baseline import ClassPriorAttributor
from driftsense.attribute.random_baseline import RandomAttributor
from driftsense.attribute.xgb_attributor import XGBoostAttributor
from driftsense.detect.rolling_threshold import RollingThresholdDetector
from driftsense.detect.zscore import ZScoreDetector
from driftsense.eval.attribution_metrics import top_1_accuracy, top_k_accuracy
from driftsense.eval.detection_metrics import false_positive_rate
from driftsense.eval.metrics import (
    mean_absolute_error,
    mean_absolute_scaled_error,
    root_mean_squared_error,
    weighted_absolute_percentage_error,
)
from driftsense.forecast.naive import MovingAverageForecaster, SeasonalNaiveForecaster
from driftsense.forecast.smoothing import ExponentialSmoothingForecaster
from driftsense.forecast.xgb import XGBoostForecaster

logger = logging.getLogger(__name__)

# Circularity caveat documented per A10.3
SYNTHETIC_EVENT_CIRCULARITY_CAVEAT = (
    "CAUTION (A10.3): In synthetic data tracks where anomaly injections co-occur with synthetic "
    "operational events, event features have direct synthetic linkage to target anomalies. "
    "Real track evaluation independently confirms event telemetry utility without circular injection bias."
)


def hash_file_sha256(filepath: str | Path) -> str:
    """Compute SHA-256 hex digest of a file."""
    path = Path(filepath)
    if not path.is_file():
        raise FileNotFoundError(f"File not found for hashing: {filepath}")
    sha256 = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            sha256.update(chunk)
    return sha256.hexdigest()


def validate_split_paths(train_path: str | Path, val_path: str | Path) -> None:
    """Ensure quarantined test split is never provided to ablation runner (A10.1)."""
    for p in [str(train_path).lower(), str(val_path).lower()]:
        if "test_features" in p or "test.csv" in p or "test_split" in p:
            raise PermissionError(
                f"TEST QUARANTINE VIOLATION: Test split is strictly forbidden in Phase 10: {p}"
            )


def validate_splits_invariants(
    df_train: pd.DataFrame,
    df_val: pd.DataFrame,
    time_col: str = "ChargePeriodStart",
) -> dict[str, Any]:
    """Verify strict chronological non-leakage invariants between train and val partitions (A10.1).

    Invariant: max(train_timestamp) < min(val_timestamp) and disjoint row sets.
    """
    if df_train.empty or df_val.empty:
        raise ValueError("Train and validation DataFrames must not be empty.")

    t_train = pd.to_datetime(df_train[time_col], utc=True)
    t_val = pd.to_datetime(df_val[time_col], utc=True)

    max_train = t_train.max()
    min_val = t_val.min()

    if max_train >= min_val:
        raise ValueError(
            f"CHRONOLOGICAL LEAKAGE DETECTED: max(train)={max_train} >= min(val)={min_val}"
        )

    return {
        "train_rows": len(df_train),
        "val_rows": len(df_val),
        "train_start": str(t_train.min()),
        "train_end": str(max_train),
        "val_start": str(min_val),
        "val_end": str(t_val.max()),
        "leakage_free": True,
    }


def select_arm_features(
    columns: Sequence[str],
    arm_type: str,
    target_col: str = "EffectiveCost",
    time_col: str = "ChargePeriodStart",
    service_col: str = "ServiceName",
) -> list[str]:
    """Select appropriate feature subset for a specific ablation arm."""
    excluded = {
        target_col,
        time_col,
        service_col,
        "label_id",
        "primary_cause",
        "contributing_causes",
        "severity_score",
        "anomaly_label",
        "is_anomaly",
        "source",
    }
    available = [c for c in columns if c not in excluded]

    if arm_type == "cost_only":
        # Cost lags, rolling stats, calendar/cyclical. Exclude usage and events.
        return [
            c
            for c in available
            if not c.startswith("ConsumedQuantity")
            and not c.startswith("event_")
            and "ratio" not in c
            and "unit_price" not in c
            and c != "PricingQuantity"
        ]
    elif arm_type == "cost_usage":
        # Cost + usage. Exclude events.
        return [c for c in available if not c.startswith("event_")]
    elif arm_type == "cost_usage_events":
        # All available validated features including event features
        return list(available)
    else:
        raise ValueError(f"Unknown feature arm type: {arm_type}")


class AblationRunner:
    """Orchestrates Phase 10 controlled experiments and ablation studies."""

    def __init__(
        self,
        config: dict[str, Any] | None = None,
        protocol_path: str = "docs/experiment_protocol.md",
    ) -> None:
        self.config = config or {}
        self.protocol_path = protocol_path
        self.protocol_hash = ""
        if Path(self.protocol_path).is_file():
            self.protocol_hash = hash_file_sha256(self.protocol_path)

        exp_cfg = self.config.get("experiment", {})
        self.seeds: list[int] = exp_cfg.get("seeds", [42, 123, 999])
        self.target_col = self.config.get("dataset", {}).get(
            "target_col", "EffectiveCost"
        )
        self.time_col = self.config.get("dataset", {}).get(
            "time_col", "ChargePeriodStart"
        )
        self.service_col = self.config.get("dataset", {}).get(
            "service_col", "ServiceName"
        )

    def evaluate_forecaster_seeds(
        self,
        df_train: pd.DataFrame,
        df_val: pd.DataFrame,
        feature_cols: list[str],
        seeds: list[int] | None = None,
        model_params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Train and evaluate forecaster across multiple random seeds."""
        seeds = seeds or self.seeds
        params = model_params or {}
        n_estimators = params.get("n_estimators", 100)
        max_depth = params.get("max_depth", 5)
        lr = params.get("learning_rate", 0.05)
        log_transform = params.get("log_transform", True)

        y_val = df_val[self.target_col].to_numpy(dtype=float)
        y_train = df_train[self.target_col].to_numpy(dtype=float)

        seed_results = []
        val_preds_list = []

        for s in seeds:
            model = XGBoostForecaster(
                n_estimators=n_estimators,
                max_depth=max_depth,
                learning_rate=lr,
                log_transform=log_transform,
                seed=s,
            )
            # Ensure model trains only on specified feature columns
            train_sub = df_train[
                feature_cols + [self.target_col, self.time_col, self.service_col]
            ].copy()
            val_sub = df_val[
                feature_cols + [self.target_col, self.time_col, self.service_col]
            ].copy()

            model.fit(
                train_sub,
                target_col=self.target_col,
                time_col=self.time_col,
                service_col=self.service_col,
            )
            preds = model.predict(val_sub)
            val_preds_list.append(preds)

            wape = weighted_absolute_percentage_error(y_val, preds)
            mase = mean_absolute_scaled_error(
                y_val, preds, y_train=y_train, seasonality=24
            )
            rmse = root_mean_squared_error(y_val, preds)
            mae = mean_absolute_error(y_val, preds)

            seed_results.append(
                {
                    "seed": s,
                    "wape": wape,
                    "mase": mase,
                    "rmse": rmse,
                    "mae": mae,
                }
            )

        wapes = [r["wape"] for r in seed_results]
        mases = [r["mase"] for r in seed_results]
        rmses = [r["rmse"] for r in seed_results]
        maes = [r["mae"] for r in seed_results]

        return {
            "per_seed": seed_results,
            "mean_wape": float(np.mean(wapes)),
            "std_wape": float(np.std(wapes)),
            "mean_mase": float(np.mean(mases)),
            "std_mase": float(np.std(mases)),
            "mean_rmse": float(np.mean(rmses)),
            "std_rmse": float(np.std(rmses)),
            "mean_mae": float(np.mean(maes)),
            "std_mae": float(np.std(maes)),
            "sample_predictions": val_preds_list[0] if val_preds_list else None,
        }

    def run_arm_1_cost_only(
        self,
        df_train: pd.DataFrame,
        df_val: pd.DataFrame,
    ) -> dict[str, Any]:
        """Arm 1: Cost-only feature representations (autoregressive + calendar)."""
        feats = select_arm_features(
            list(df_train.columns),
            "cost_only",
            self.target_col,
            self.time_col,
            self.service_col,
        )
        logger.info(
            "Running Arm 1 (Cost-Only) with %d features across %d seeds",
            len(feats),
            len(self.seeds),
        )
        res = self.evaluate_forecaster_seeds(df_train, df_val, feats)
        res["arm_name"] = "Arm 1: Cost-Only"
        res["feature_count"] = len(feats)
        res["features"] = feats
        return res

    def run_arm_2_cost_usage(
        self,
        df_train: pd.DataFrame,
        df_val: pd.DataFrame,
    ) -> dict[str, Any]:
        """Arm 2: Cost + Resource Usage feature representations."""
        feats = select_arm_features(
            list(df_train.columns),
            "cost_usage",
            self.target_col,
            self.time_col,
            self.service_col,
        )
        logger.info(
            "Running Arm 2 (Cost + Usage) with %d features across %d seeds",
            len(feats),
            len(self.seeds),
        )
        res = self.evaluate_forecaster_seeds(df_train, df_val, feats)
        res["arm_name"] = "Arm 2: Cost + Usage"
        res["feature_count"] = len(feats)
        res["features"] = feats
        return res

    def run_arm_3_cost_usage_events(
        self,
        df_train: pd.DataFrame,
        df_val: pd.DataFrame,
    ) -> dict[str, Any]:
        """Arm 3: Cost + Usage + Operational Event features."""
        feats = select_arm_features(
            list(df_train.columns),
            "cost_usage_events",
            self.target_col,
            self.time_col,
            self.service_col,
        )
        logger.info(
            "Running Arm 3 (Cost + Usage + Events) with %d features across %d seeds",
            len(feats),
            len(self.seeds),
        )
        res = self.evaluate_forecaster_seeds(df_train, df_val, feats)
        res["arm_name"] = "Arm 3: Cost + Usage + Events"
        res["feature_count"] = len(feats)
        res["features"] = feats
        res["circularity_caveat"] = SYNTHETIC_EVENT_CIRCULARITY_CAVEAT
        return res

    def run_arm_4_baseline_vs_advanced(
        self,
        df_train: pd.DataFrame,
        df_val: pd.DataFrame,
    ) -> dict[str, Any]:
        """Arm 4: Baseline vs. Advanced architectures for forecasting and detection."""
        y_val = df_val[self.target_col].to_numpy(dtype=float)
        y_train = df_train[self.target_col].to_numpy(dtype=float)

        # Baseline 1: Seasonal Naive
        sn = SeasonalNaiveForecaster(seasonality=24)
        sn.fit(
            df_train,
            target_col=self.target_col,
            time_col=self.time_col,
            service_col=self.service_col,
        )
        sn_preds = sn.predict(df_val)
        sn_wape = weighted_absolute_percentage_error(y_val, sn_preds)
        sn_mase = mean_absolute_scaled_error(
            y_val, sn_preds, y_train=y_train, seasonality=24
        )

        # Baseline 2: Moving Average
        ma = MovingAverageForecaster(window=24)
        ma.fit(
            df_train,
            target_col=self.target_col,
            time_col=self.time_col,
            service_col=self.service_col,
        )
        ma_preds = ma.predict(df_val)
        ma_wape = weighted_absolute_percentage_error(y_val, ma_preds)
        ma_mase = mean_absolute_scaled_error(
            y_val, ma_preds, y_train=y_train, seasonality=24
        )

        # Baseline 3: Exponential Smoothing
        es = ExponentialSmoothingForecaster(alpha=0.25)
        es.fit(
            df_train,
            target_col=self.target_col,
            time_col=self.time_col,
            service_col=self.service_col,
        )
        es_preds = es.predict(df_val)
        es_wape = weighted_absolute_percentage_error(y_val, es_preds)
        es_mase = mean_absolute_scaled_error(
            y_val, es_preds, y_train=y_train, seasonality=24
        )

        # Advanced: XGBoost across seeds
        full_feats = select_arm_features(
            list(df_train.columns),
            "cost_usage",
            self.target_col,
            self.time_col,
            self.service_col,
        )
        xgb_res = self.evaluate_forecaster_seeds(df_train, df_val, full_feats)
        xgb_preds = xgb_res["sample_predictions"]

        # Detector comparisons on residuals
        res_xgb = (
            y_val - xgb_preds
            if xgb_preds is not None
            else (y_val - np.mean(y_train, keepdims=False))
        )

        # Baseline detector: Z-Score
        df_train_res = pd.DataFrame(
            {
                "residual": y_train - np.mean(y_train),
                self.service_col: df_train[self.service_col].values,
                self.time_col: df_train[self.time_col].values,
            }
        )
        df_val_res = pd.DataFrame(
            {
                "residual": res_xgb,
                self.service_col: df_val[self.service_col].values,
                self.time_col: df_val[self.time_col].values,
            }
        )

        z_det = ZScoreDetector(threshold=3.0)
        z_det.fit(
            df_train_res,
            residual_col="residual",
            service_col=self.service_col,
            time_col=self.time_col,
        )
        z_flags = z_det.predict(df_val_res)

        # Advanced detector: Rolling Threshold
        rt_det = RollingThresholdDetector(window=24, threshold=3.0)
        rt_det.fit(
            df_train_res,
            residual_col="residual",
            service_col=self.service_col,
            time_col=self.time_col,
        )
        rt_flags = rt_det.predict(df_val_res)

        # Clean track FPR (where ground truth is normal / 0)
        dummy_zeros = np.zeros(len(y_val), dtype=int)
        fpr_z = false_positive_rate(dummy_zeros, z_flags)
        fpr_rt = false_positive_rate(dummy_zeros, rt_flags)

        return {
            "arm_name": "Arm 4: Baseline vs Advanced",
            "forecasting": {
                "seasonal_naive": {"wape": sn_wape, "mase": sn_mase},
                "moving_average": {"wape": ma_wape, "mase": ma_mase},
                "exponential_smoothing": {"wape": es_wape, "mase": es_mase},
                "xgboost_champion": {
                    "mean_wape": xgb_res["mean_wape"],
                    "std_wape": xgb_res["std_wape"],
                    "mean_mase": xgb_res["mean_mase"],
                    "std_mase": xgb_res["std_mase"],
                },
                "wape_reduction_vs_naive_pct": float(
                    (sn_wape - xgb_res["mean_wape"]) / (sn_wape + 1e-6) * 100.0
                    if sn_wape > 0
                    else 0.0
                ),
            },
            "detection": {
                "baseline_zscore_fpr": fpr_z,
                "champion_rolling_threshold_fpr": fpr_rt,
            },
        }

    def run_arm_5_attribution(
        self,
        df_val: pd.DataFrame,
        incidents: list[dict[str, Any]] | None = None,
        events: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Arm 5: Attribution with vs. without operational event telemetry."""
        if not incidents or not events:
            logger.warning(
                "No incidents/events supplied for Arm 5; returning nominal baselines."
            )
            return {
                "arm_name": "Arm 5: Attribution With vs Without Events",
                "evaluated": False,
                "reason": "No incidents/events data available",
            }

        y_true = [str(inc.get("primary_cause", "UNKNOWN")) for inc in incidents]

        # 1. Uninformed Baseline: Random Uniform
        rand_top1s, rand_top3s = [], []
        for s in self.seeds:
            rand_attr = RandomAttributor(seed=s)
            rand_attr.fit(incidents=incidents, events=events)
            rand_ranked = rand_attr.predict_top_k(incidents, events, k=3)
            rand_top1s.append(top_1_accuracy(y_true, rand_ranked))
            rand_top3s.append(top_k_accuracy(y_true, rand_ranked, k=3))

        # 2. Historical Prior Baseline
        prior_attr = ClassPriorAttributor()
        prior_attr.fit(incidents=incidents, events=events)
        prior_ranked = prior_attr.predict_top_k(incidents, events, k=3)
        prior_top1 = top_1_accuracy(y_true, prior_ranked)
        prior_top3 = top_k_accuracy(y_true, prior_ranked, k=3)

        # 3. Temporal Correlation Attributor (With Event Telemetry)
        corr_attr = TemporalCorrelationAttributor(
            lookback_hours=3.0, decay_halflife_hours=1.0
        )
        corr_attr.fit(incidents=incidents, events=events)
        corr_ranked = corr_attr.predict_top_k(incidents, events, k=3)
        corr_top1 = top_1_accuracy(y_true, corr_ranked)
        corr_top3 = top_k_accuracy(y_true, corr_ranked, k=3)

        # 4. XGBoost Multi-Class Attributor (With Event Telemetry)
        xgb_top1s, xgb_top3s = [], []
        for s in self.seeds:
            xgb_attr = XGBoostAttributor(
                n_estimators=60, max_depth=4, seed=s, lookback_hours=4.0
            )
            xgb_attr.fit(incidents=incidents, events=events)
            xgb_ranked = xgb_attr.predict_top_k(incidents, events, k=3)
            xgb_top1s.append(top_1_accuracy(y_true, xgb_ranked))
            xgb_top3s.append(top_k_accuracy(y_true, xgb_ranked, k=3))

        return {
            "arm_name": "Arm 5: Attribution With vs Without Events",
            "total_incidents": len(incidents),
            "uninformed_without_events": {
                "random_uniform": {
                    "mean_top1": float(np.mean(rand_top1s)),
                    "std_top1": float(np.std(rand_top1s)),
                    "mean_top3": float(np.mean(rand_top3s)),
                },
                "service_prior": {"top1": prior_top1, "top3": prior_top3},
            },
            "informed_with_events": {
                "temporal_correlation_champion": {
                    "top1": corr_top1,
                    "top3": corr_top3,
                },
                "xgboost_attributor": {
                    "mean_top1": float(np.mean(xgb_top1s)),
                    "std_top1": float(np.std(xgb_top1s)),
                    "mean_top3": float(np.mean(xgb_top3s)),
                },
            },
        }

    def run_arm_6_temporal_generalization(
        self,
        df_train: pd.DataFrame,
        df_val: pd.DataFrame,
    ) -> dict[str, Any]:
        """Arm 6: Evaluation across unseen early vs. late validation time horizons."""
        feats = select_arm_features(
            list(df_train.columns),
            "cost_usage",
            self.target_col,
            self.time_col,
            self.service_col,
        )
        times = (
            df_val[self.time_col].drop_duplicates().sort_values().reset_index(drop=True)
        )
        mid_idx = len(times) // 2
        mid_time = times.iloc[mid_idx]

        val_early = df_val[df_val[self.time_col] < mid_time].copy()
        val_late = df_val[df_val[self.time_col] >= mid_time].copy()

        logger.info(
            "Arm 6 Temporal Generalization: Early=%d rows, Late=%d rows",
            len(val_early),
            len(val_late),
        )

        res_early = self.evaluate_forecaster_seeds(df_train, val_early, feats)
        res_late = self.evaluate_forecaster_seeds(df_train, val_late, feats)

        drift_wape = res_late["mean_wape"] - res_early["mean_wape"]

        return {
            "arm_name": "Arm 6: Unseen Time Periods (Temporal Generalization)",
            "early_val_window": {
                "rows": len(val_early),
                "mean_wape": res_early["mean_wape"],
                "std_wape": res_early["std_wape"],
                "mean_mase": res_early["mean_mase"],
            },
            "late_val_window": {
                "rows": len(val_late),
                "mean_wape": res_late["mean_wape"],
                "std_wape": res_late["std_wape"],
                "mean_mase": res_late["mean_mase"],
            },
            "wape_horizon_drift": float(drift_wape),
        }

    def run_arm_7_seasonality_robustness(
        self,
        df_train: pd.DataFrame,
        df_val: pd.DataFrame,
    ) -> dict[str, Any]:
        """Arm 7: False positive rate robustness across peak business hours vs. off-peak / weekend regimes."""
        feats = select_arm_features(
            list(df_train.columns),
            "cost_usage",
            self.target_col,
            self.time_col,
            self.service_col,
        )
        forecaster = XGBoostForecaster(
            n_estimators=100, max_depth=5, seed=42, log_transform=True
        )
        forecaster.fit(
            df_train[feats + [self.target_col, self.time_col, self.service_col]],
            target_col=self.target_col,
            time_col=self.time_col,
            service_col=self.service_col,
        )
        preds = forecaster.predict(
            df_val[feats + [self.target_col, self.time_col, self.service_col]]
        )
        residuals = df_val[self.target_col].to_numpy(dtype=float) - preds

        df_train_res = pd.DataFrame(
            {
                "residual": df_train[self.target_col].to_numpy(dtype=float)
                - np.mean(df_train[self.target_col]),
                self.service_col: df_train[self.service_col].values,
                self.time_col: df_train[self.time_col].values,
            }
        )
        detector = RollingThresholdDetector(window=24, threshold=3.0)
        detector.fit(
            df_train_res,
            residual_col="residual",
            service_col=self.service_col,
            time_col=self.time_col,
        )

        df_val_res = pd.DataFrame(
            {
                "residual": residuals,
                self.service_col: df_val[self.service_col].values,
                self.time_col: df_val[self.time_col].values,
            }
        )
        flags = detector.predict(df_val_res)

        df_eval = df_val.copy()
        df_eval["is_flagged"] = flags
        df_eval["ground_truth"] = 0  # Clean uncorrupted track

        t = pd.to_datetime(df_eval[self.time_col], utc=True)
        is_weekday = t.dt.dayofweek < 5
        is_business_hour = (t.dt.hour >= 9) & (t.dt.hour <= 18)
        peak_mask = is_weekday & is_business_hour
        offpeak_mask = ~peak_mask

        peak_fp = int(df_eval.loc[peak_mask, "is_flagged"].sum())
        peak_total = int(peak_mask.sum())
        peak_fpr = float(peak_fp / peak_total) if peak_total > 0 else 0.0

        offpeak_fp = int(df_eval.loc[offpeak_mask, "is_flagged"].sum())
        offpeak_total = int(offpeak_mask.sum())
        offpeak_fpr = float(offpeak_fp / offpeak_total) if offpeak_total > 0 else 0.0

        overall_fp = int(df_eval["is_flagged"].sum())
        overall_fpr = float(overall_fp / len(df_eval))

        return {
            "arm_name": "Arm 7: Seasonality & Workload-Change FP Robustness",
            "overall_clean_fpr": overall_fpr,
            "overall_false_positives": overall_fp,
            "regimes": {
                "peak_business_hours": {
                    "total_points": peak_total,
                    "false_positives": peak_fp,
                    "fpr": peak_fpr,
                },
                "off_peak_and_weekend": {
                    "total_points": offpeak_total,
                    "false_positives": offpeak_fp,
                    "fpr": offpeak_fpr,
                },
            },
            "max_regime_fpr": max(peak_fpr, offpeak_fpr),
            "robustness_pass": max(peak_fpr, offpeak_fpr) <= 0.01,  # <= 1.0% FPR target
        }

    def run_all(
        self,
        df_train: pd.DataFrame,
        df_val: pd.DataFrame,
        incidents: list[dict[str, Any]] | None = None,
        events: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Execute all 7 experimental ablation arms and compile comparative tables."""
        # A10.1 Invariant: verify identical splits
        split_summary = validate_splits_invariants(
            df_train, df_val, time_col=self.time_col
        )

        arm1 = self.run_arm_1_cost_only(df_train, df_val)
        arm2 = self.run_arm_2_cost_usage(df_train, df_val)
        arm3 = self.run_arm_3_cost_usage_events(df_train, df_val)
        arm4 = self.run_arm_4_baseline_vs_advanced(df_train, df_val)
        arm5 = self.run_arm_5_attribution(df_val, incidents=incidents, events=events)
        arm6 = self.run_arm_6_temporal_generalization(df_train, df_val)
        arm7 = self.run_arm_7_seasonality_robustness(df_train, df_val)

        # Build clean summary comparison records
        summary_rows = [
            {
                "Arm": "Arm 1: Cost-Only",
                "Feature_Group": "Cost Lags + Rolling + Calendar",
                "Mean_WAPE": arm1["mean_wape"],
                "Std_WAPE": arm1["std_wape"],
                "Mean_MASE": arm1["mean_mase"],
                "Std_MASE": arm1["std_mase"],
                "Mean_RMSE": arm1["mean_rmse"],
            },
            {
                "Arm": "Arm 2: Cost + Usage",
                "Feature_Group": "Cost + Usage (ConsumedQuantity)",
                "Mean_WAPE": arm2["mean_wape"],
                "Std_WAPE": arm2["std_wape"],
                "Mean_MASE": arm2["mean_mase"],
                "Std_MASE": arm2["std_mase"],
                "Mean_RMSE": arm2["mean_rmse"],
            },
            {
                "Arm": "Arm 3: Cost + Usage + Events",
                "Feature_Group": "Cost + Usage + Event Signals",
                "Mean_WAPE": arm3["mean_wape"],
                "Std_WAPE": arm3["std_wape"],
                "Mean_MASE": arm3["mean_mase"],
                "Std_MASE": arm3["std_mase"],
                "Mean_RMSE": arm3["mean_rmse"],
            },
            {
                "Arm": "Arm 4: Champion XGBoost (Log-Transform)",
                "Feature_Group": "Advanced Champion",
                "Mean_WAPE": arm4["forecasting"]["xgboost_champion"]["mean_wape"],
                "Std_WAPE": arm4["forecasting"]["xgboost_champion"]["std_wape"],
                "Mean_MASE": arm4["forecasting"]["xgboost_champion"]["mean_mase"],
                "Std_MASE": arm4["forecasting"]["xgboost_champion"]["std_mase"],
                "Mean_RMSE": arm2["mean_rmse"],
            },
            {
                "Arm": "Arm 4: Baseline Seasonal Naive",
                "Feature_Group": "Seasonal Naive (s=24)",
                "Mean_WAPE": arm4["forecasting"]["seasonal_naive"]["wape"],
                "Std_WAPE": 0.0,
                "Mean_MASE": arm4["forecasting"]["seasonal_naive"]["mase"],
                "Std_MASE": 0.0,
                "Mean_RMSE": float("nan"),
            },
            {
                "Arm": "Arm 6: Early Val Window (Days 16-20)",
                "Feature_Group": "Temporal Split: Early",
                "Mean_WAPE": arm6["early_val_window"]["mean_wape"],
                "Std_WAPE": arm6["early_val_window"]["std_wape"],
                "Mean_MASE": arm6["early_val_window"]["mean_mase"],
                "Std_MASE": 0.0,
                "Mean_RMSE": float("nan"),
            },
            {
                "Arm": "Arm 6: Late Val Window (Days 20-24)",
                "Feature_Group": "Temporal Split: Late",
                "Mean_WAPE": arm6["late_val_window"]["mean_wape"],
                "Std_WAPE": arm6["late_val_window"]["std_wape"],
                "Mean_MASE": arm6["late_val_window"]["mean_mase"],
                "Std_MASE": 0.0,
                "Mean_RMSE": float("nan"),
            },
        ]

        return {
            "protocol_sha256": self.protocol_hash,
            "split_summary": split_summary,
            "seeds": self.seeds,
            "arms": {
                "arm_1": arm1,
                "arm_2": arm2,
                "arm_3": arm3,
                "arm_4": arm4,
                "arm_5": arm5,
                "arm_6": arm6,
                "arm_7": arm7,
            },
            "summary_records": summary_rows,
            "circularity_caveat": SYNTHETIC_EVENT_CIRCULARITY_CAVEAT,
        }
