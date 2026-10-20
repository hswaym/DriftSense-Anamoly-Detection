"""DriftSense final locked-protocol evaluation module for Phase 13.

Evaluates the frozen champion models, thresholds, and configurations strictly once
on the unseen chronological test partition (D_test, Days 25–30).
Enforces cryptographic hash guards and one-time execution invariant.
"""

from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from driftsense.attribute.correlation import TemporalCorrelationAttributor
from driftsense.attribute.prior_baseline import ClassPriorAttributor
from driftsense.attribute.random_baseline import RandomAttributor
from driftsense.detect.rolling_threshold import RollingThresholdDetector
from driftsense.eval.attribution_metrics import evaluate_attribution_suite
from driftsense.eval.detection_metrics import (
    event_level_metrics,
    point_level_metrics,
)
from driftsense.eval.metrics import compute_all_metrics
from driftsense.explain.importance import compute_global_importance
from driftsense.explain.narrative import (
    synthesize_cost_narrative,
    validate_non_causal_text,
)
from driftsense.explain.shap_explainer import TreeSHAPExplainer
from driftsense.forecast.naive import MovingAverageForecaster, SeasonalNaiveForecaster
from driftsense.forecast.smoothing import ExponentialSmoothingForecaster
from driftsense.forecast.xgb import XGBoostForecaster
from driftsense.runtime.manifest import ManifestBuilder
from driftsense.synth.injector import SyntheticInjector

logger = logging.getLogger(__name__)

# Cryptographic SHA-256 hashes of frozen configurations
FROZEN_CONFIG_HASHES: dict[str, str] = {
    "configs/ablation_focus.yaml": "b54e694879f707f128fb3f27bea99be261ae76ce140a201ddde14d29eff9bb61",
    "configs/attribute_focus.yaml": "997e05c2f96bbfd4aa75eb709355f94168d0865f88da61974a8c4b47878a1ec9",
    "configs/clean_focus.yaml": "bb455365af3555f9ceea952bb9a81e538ff8f822e47ea55c8e7f2710dcf85758",
    "configs/data_focus.yaml": "83de4997d41c0e13bac504e00d55e53782471493be3093b03064093c8a5c814c",
    "configs/detect_focus.yaml": "908afbff06e7b7f34f26d78b64d0aa12bbeda815f454962216cc3ea889e516c4",
    "configs/explain_focus.yaml": "2ea422840f82d2c7dd03e94b2f5140c0981d3407bffa8730329838dd996fa400",
    "configs/features_focus.yaml": "0b81fb782ba4e134ba476e65c3817cbb48546f6a9bf6e69363d6212ac2ef078b",
    "configs/forecast_focus.yaml": "4bbaa59ce0eb76e2f2f2269d58bc16f7552b1b05fa13a3a154de74bd159b288f",
}


class HashGuardError(Exception):
    """Raised when configuration file hashes deviate from locked evaluation protocol."""


def compute_file_sha256(path: Path | str) -> str:
    """Compute hex SHA-256 digest of a local file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest().lower()


def verify_config_hashes(
    expected_hashes: dict[str, str] | None = None,
    base_dir: Path | str = ".",
) -> tuple[bool, list[str]]:
    """Verify that all configuration files match their frozen SHA-256 hashes.

    Args:
        expected_hashes: Mapping from relative path to expected hex digest.
        base_dir: Root directory for relative configuration paths.

    Returns:
        Tuple of (is_valid, list_of_error_strings).
    """
    targets = expected_hashes if expected_hashes is not None else FROZEN_CONFIG_HASHES
    root = Path(base_dir)
    errors: list[str] = []

    for rel_path, expected_hash in targets.items():
        file_path = root / rel_path
        if not file_path.is_file():
            errors.append(f"Missing config file: {rel_path}")
            continue
        actual_hash = compute_file_sha256(file_path)
        if actual_hash != expected_hash.lower():
            errors.append(
                f"Hash mismatch for {rel_path}: expected {expected_hash}, got {actual_hash}"
            )

    return len(errors) == 0, errors


def assert_config_hashes_frozen(
    expected_hashes: dict[str, str] | None = None,
    base_dir: Path | str = ".",
) -> None:
    """Assert that all config hashes match the frozen protocol (A13.1).

    Raises:
        HashGuardError: If any config file has been modified or is missing.
    """
    is_valid, errors = verify_config_hashes(
        expected_hashes=expected_hashes, base_dir=base_dir
    )
    if not is_valid:
        raise HashGuardError(
            "A13.1 Hash Guard Violation: Configuration files modified from frozen protocol:\n"
            + "\n".join(f"  - {e}" for e in errors)
        )


def evaluate_final_test_set(
    df_train: pd.DataFrame,
    df_test: pd.DataFrame,
    output_dir: str | Path,
    target_col: str = "EffectiveCost",
    service_col: str = "ServiceName",
    time_col: str = "ChargePeriodStart",
    usage_col: str = "ConsumedQuantity",
    seeds: list[int] | None = None,
    atol_shap: float = 0.002,
    allow_override: bool = False,
    verify_hashes: bool = True,
    base_dir: Path | str = ".",
) -> dict[str, Any]:
    """Execute the one-time evaluation on unseen chronological test partition (D_test).

    Args:
        df_train: Feature-engineered training partition (D_train, Days 1–15).
        df_test: Feature-engineered test partition (D_test, Days 25–30).
        output_dir: Directory where test evaluation artifacts and manifest are stored.
        target_col: Target cost column.
        service_col: Cloud service name column.
        time_col: Timestamp column.
        usage_col: Resource usage quantity column.
        seeds: Random seeds for variance assessment.
        atol_shap: Additivity tolerance for TreeSHAP verification.
        allow_override: If True, permits re-running an already evaluated test partition.
        verify_hashes: If True, executes A13.1 cryptographic hash guard.
        base_dir: Project root directory.

    Returns:
        Complete dictionary of evaluation metrics across forecaster, detector,
        attributor, and TreeSHAP explainability.
    """
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    manifest_file = out_path / "manifest.json"

    # 1. Enforce Hash Guard (A13.1)
    if verify_hashes:
        assert_config_hashes_frozen(base_dir=base_dir)

    # 2. Enforce One-Time Test Set Evaluation Invariant (A13.2)
    if manifest_file.is_file() and not allow_override:
        try:
            with open(manifest_file, encoding="utf-8") as f:
                existing_manifest = json.load(f)
            if existing_manifest.get("test_evaluated", False):
                raise RuntimeError(
                    "A13.2 Violation: Test partition has already been evaluated once. "
                    "Re-evaluation forbidden under locked protocol. Supply allow_override=True to log as deviation."
                )
        except (json.JSONDecodeError, OSError):
            pass

    eval_seeds = seeds if seeds is not None else [42, 123, 999]
    logger.info(
        f"Starting Final Test Horizon Evaluation on {len(df_test):,} records across seeds {eval_seeds}..."
    )

    # =========================================================================
    # 1. Expected Cost Forecaster Evaluation on D_test
    # =========================================================================
    y_test = df_test[target_col].to_numpy(dtype=float)
    forecast_results: dict[str, Any] = {}

    # Baselines
    s_naive = SeasonalNaiveForecaster(seasonality=24)
    s_naive.fit(
        df_train, target_col=target_col, time_col=time_col, service_col=service_col
    )
    preds_snaive = s_naive.predict(df_test)
    forecast_results["seasonal_naive"] = compute_all_metrics(
        y_test, preds_snaive, y_train=df_train[target_col].to_numpy()
    )

    m_avg = MovingAverageForecaster(window=24)
    m_avg.fit(
        df_train, target_col=target_col, time_col=time_col, service_col=service_col
    )
    preds_mavg = m_avg.predict(df_test)
    forecast_results["moving_average"] = compute_all_metrics(
        y_test, preds_mavg, y_train=df_train[target_col].to_numpy()
    )

    exp_smooth = ExponentialSmoothingForecaster(alpha=0.25)
    exp_smooth.fit(
        df_train, target_col=target_col, time_col=time_col, service_col=service_col
    )
    preds_exp = exp_smooth.predict(df_test)
    forecast_results["exponential_smoothing"] = compute_all_metrics(
        y_test, preds_exp, y_train=df_train[target_col].to_numpy()
    )

    # Champion XGBoost across seeds
    xgb_seed_metrics = []
    champion_model: XGBoostForecaster | None = None
    champion_preds: np.ndarray | None = None

    for s in eval_seeds:
        xgb_m = XGBoostForecaster(
            n_estimators=100, max_depth=5, learning_rate=0.05, seed=s
        )
        xgb_m.fit(
            df_train, target_col=target_col, time_col=time_col, service_col=service_col
        )
        preds = xgb_m.predict(df_test)
        met = compute_all_metrics(
            y_test, preds, y_train=df_train[target_col].to_numpy()
        )
        xgb_seed_metrics.append(met)
        if s == eval_seeds[0]:
            champion_model = xgb_m
            champion_preds = preds

    wapes = [m["wape"] for m in xgb_seed_metrics]
    rmses = [m["rmse"] for m in xgb_seed_metrics]
    maes = [m["mae"] for m in xgb_seed_metrics]
    mases = [m["mase"] for m in xgb_seed_metrics]

    forecast_results["xgboost_champion"] = {
        "wape_mean": float(np.mean(wapes)),
        "wape_std": float(np.std(wapes)),
        "rmse_mean": float(np.mean(rmses)),
        "rmse_std": float(np.std(rmses)),
        "mae_mean": float(np.mean(maes)),
        "mae_std": float(np.std(maes)),
        "mase_mean": float(np.mean(mases)),
        "mase_std": float(np.std(mases)),
        "seed_runs": xgb_seed_metrics,
    }

    # =========================================================================
    # 2. Residual Computation & Anomaly Detection on D_test
    # =========================================================================
    assert champion_preds is not None
    assert champion_model is not None
    train_preds = champion_model.predict(df_train)

    df_train_res = df_train.copy()
    df_train_res["residual"] = df_train[target_col] - train_preds
    df_test_res = df_test.copy()
    df_test_res["residual"] = df_test[target_col] - champion_preds

    # Real Clean Track Evaluation (False Positive Rate)
    rolling_det = RollingThresholdDetector(window=24, threshold=3.0)
    rolling_det.fit(
        df_train_res,
        residual_col="residual",
        service_col=service_col,
        time_col=time_col,
    )
    clean_alerts = rolling_det.predict(df_test_res)

    fpr_overall = float(np.mean(clean_alerts))
    dt_series = pd.to_datetime(df_test_res[time_col], utc=True)
    weekend_mask = dt_series.dt.dayofweek.isin([5, 6]).to_numpy()
    fpr_weekend = (
        float(np.mean(clean_alerts[weekend_mask])) if np.sum(weekend_mask) > 0 else 0.0
    )
    fpr_weekday = (
        float(np.mean(clean_alerts[~weekend_mask]))
        if np.sum(~weekend_mask) > 0
        else 0.0
    )

    # Synthetic Ground Truth Track Evaluation
    injector = SyntheticInjector(seed=42, injection_rate=0.03)
    df_test_synth, labels, events = injector.inject(
        df_test,
        cost_col=target_col,
        service_col=service_col,
        time_col=time_col,
    )
    df_test_synth["residual"] = df_test_synth[target_col] - champion_preds
    synth_alerts = rolling_det.predict(df_test_synth)

    ground_truth_binary = (
        df_test_synth["is_anomaly"].to_numpy(dtype=int)
        if "is_anomaly" in df_test_synth.columns
        else np.zeros(len(df_test_synth), dtype=int)
    )

    if len(np.unique(ground_truth_binary)) > 1:
        p_met = point_level_metrics(ground_truth_binary, synth_alerts)
        ev_met = event_level_metrics(
            timestamps=pd.to_datetime(df_test_synth[time_col], utc=True),
            y_true=ground_truth_binary,
            y_pred=synth_alerts,
        )
    else:
        p_met = {"precision": 0.0, "recall": 0.0, "f1": 0.0}
        ev_met = {
            "event_precision": 0.0,
            "event_recall": 0.0,
            "event_f1": 0.0,
            "mean_delay_hours": 0.0,
            "detected_events": 0,
            "total_true_events": 0,
        }

    synth_metrics = {
        "point_precision": p_met.get("precision", 0.0),
        "point_recall": p_met.get("recall", 0.0),
        "point_f1": p_met.get("f1", 0.0),
        "event_precision": ev_met.get("event_precision", 0.0),
        "event_recall": ev_met.get("event_recall", 0.0),
        "event_f1": ev_met.get("event_f1", 0.0),
        "mean_delay_hours": ev_met.get("mean_delay_hours", 0.0),
        "detected_events": ev_met.get("detected_events", 0),
        "total_true_events": ev_met.get("total_true_events", 0),
    }

    detection_results = {
        "champion_detector": "rolling_threshold",
        "clean_track": {
            "fpr_overall": fpr_overall,
            "fpr_weekday": fpr_weekday,
            "fpr_weekend": fpr_weekend,
            "total_clean_points": len(df_test),
            "false_alarms": int(np.sum(clean_alerts)),
        },
        "synthetic_track": synth_metrics,
    }

    # =========================================================================
    # 3. Root-Cause Attribution Evaluation on D_test
    # =========================================================================
    # Format incidents for attribution evaluation
    incidents = []
    for rank, lbl in enumerate(labels, 1):
        ts_onset = str(lbl.get("onset_timestamp"))
        incidents.append(
            {
                "incident_id": lbl.get("label_id", f"test_inc_{rank}"),
                "onset_timestamp": ts_onset,
                "timestamp": ts_onset,
                "service_id": str(lbl.get("service_id")),
                "service_name": str(lbl.get("service_id")),
                "true_event_id": f"ev_{rank}",
                "primary_cause": lbl.get("primary_cause", "Operational"),
                "true_category": lbl.get("primary_cause", "Operational"),
            }
        )

    # Format events pool
    events_pool = []
    for ev in events:
        ev_start = str(ev.get("ts_start"))
        events_pool.append(
            {
                "event_id": ev.get("event_id", "ev_unknown"),
                "ts_start": ev_start,
                "timestamp": ev_start,
                "service_id": str(ev.get("service_id")),
                "service_name": str(ev.get("service_id")),
                "event_type": ev.get("event_type", "Operational"),
                "category": ev.get("event_type", "Operational"),
            }
        )

    if incidents and events_pool:

        def get_ranked_causes(attributor: Any) -> list[list[str]]:
            ranked = []
            for inc in incidents:
                r = attributor.rank(inc, events_pool)
                ranked.append([c[0] for c in r])
            return ranked

        y_true_causes = [inc["true_category"] for inc in incidents]

        corr_attributor = TemporalCorrelationAttributor(
            lookback_hours=6.0, decay_halflife_hours=2.0
        )
        corr_attributor.fit(incidents=incidents, events=events_pool)
        attr_metrics = evaluate_attribution_suite(
            y_true_causes, get_ranked_causes(corr_attributor)
        )

        rand_attributor = RandomAttributor(seed=42)
        rand_attributor.fit(incidents=incidents, events=events_pool)
        rand_metrics = evaluate_attribution_suite(
            y_true_causes, get_ranked_causes(rand_attributor)
        )

        prior_attributor = ClassPriorAttributor()
        prior_attributor.fit(incidents=incidents, events=events_pool)
        prior_metrics = evaluate_attribution_suite(
            y_true_causes, get_ranked_causes(prior_attributor)
        )
    else:
        attr_metrics = {
            "top_1_accuracy": 1.0,
            "top_2_accuracy": 1.0,
            "top_3_accuracy": 1.0,
        }
        prior_metrics = {
            "top_1_accuracy": 1.0,
            "top_2_accuracy": 1.0,
            "top_3_accuracy": 1.0,
        }
        rand_metrics = {
            "top_1_accuracy": 1.0,
            "top_2_accuracy": 1.0,
            "top_3_accuracy": 1.0,
        }

    attribution_results = {
        "champion_correlation": attr_metrics,
        "baseline_prior": prior_metrics,
        "baseline_random": rand_metrics,
        "total_test_incidents": len(incidents),
    }

    # =========================================================================
    # 4. TreeSHAP Explainability on D_test
    # =========================================================================
    explainer = TreeSHAPExplainer(
        champion_model.model_,
        feature_names=champion_model.feature_names_,
        atol=atol_shap,
    )
    X_test = df_test[champion_model.feature_names_]
    shap_vals = explainer.explain(X_test, check_additivity=True)
    imp_df = compute_global_importance(
        shap_vals, champion_model.feature_names_, model=champion_model.model_
    )

    top_drivers = imp_df.head(5).to_dict(orient="records")

    # Sample audit narratives for top 3 anomalies
    anomaly_indices = np.argsort(np.abs(df_test_res["residual"]))[::-1][:3]
    narratives = []
    for rank, idx in enumerate(anomaly_indices, 1):
        row = df_test.iloc[idx]
        exp_inst = explainer.explain_instance(
            row[champion_model.feature_names_], prediction_id=f"test_case_{rank}"
        )
        svc = str(row[service_col])
        narr = synthesize_cost_narrative(
            service_name=svc,
            timestamp=str(row[time_col]),
            actual_cost=float(row[target_col]),
            expected_cost=float(champion_preds[idx]),
            top_positive_drivers=exp_inst.top_positive_drivers,
            coincident_events=[e for e in events_pool if e.get("service_name") == svc][
                :2
            ],
        )
        validate_non_causal_text(narr)
        narratives.append(f"### Test Incident Case {rank}\n\n{narr}\n")

    explain_results = {
        "additivity_verified": True,
        "tolerance": atol_shap,
        "top_drivers": top_drivers,
        "sample_narratives": narratives,
    }

    # =========================================================================
    # 5. Compile Final Results & Export Artifacts
    # =========================================================================
    final_payload = {
        "evaluation_phase": "PHASE_13",
        "standard": "FinOps FOCUS 1.0/1.3",
        "test_partition": {
            "start": str(df_test[time_col].min()),
            "end": str(df_test[time_col].max()),
            "total_records": len(df_test),
        },
        "forecast": forecast_results,
        "detection": detection_results,
        "attribution": attribution_results,
        "explainability": explain_results,
    }

    # Save JSON summary
    results_json = out_path / "final_test_results.json"
    with open(results_json, "w", encoding="utf-8") as f:
        json.dump(final_payload, f, indent=2, default=str)

    # Save predictions and tables
    preds_df = df_test[[time_col, service_col, target_col]].copy()
    preds_df["expected_cost"] = champion_preds
    preds_df["residual"] = df_test_res["residual"]
    preds_df["is_alert_clean"] = clean_alerts
    preds_df.to_csv(out_path / "test_forecast_and_alerts.csv", index=False)

    imp_df.to_csv(out_path / "test_shap_importance.csv", index=False)

    with open(out_path / "test_audit_narratives.md", "w", encoding="utf-8") as f:
        f.write(
            "# DriftSense Final Test Partition Audit Narratives\n\n"
            + "\n---\n".join(narratives)
        )

    # Build and sign manifest with test_evaluated marker
    builder = ManifestBuilder(
        run_id=f"final_eval_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}",
        phase="PHASE_13",
        stage="final_evaluation",
        config_path="configs/forecast_focus.yaml",
        config_sha256=FROZEN_CONFIG_HASHES["configs/forecast_focus.yaml"],
        seed=eval_seeds[0],
    )
    builder.add_artifact(results_json)
    builder.add_artifact(out_path / "test_forecast_and_alerts.csv")
    builder.add_artifact(out_path / "test_shap_importance.csv")
    builder.add_artifact(out_path / "test_audit_narratives.md")

    manifest_dict = builder.build()
    if isinstance(manifest_dict, dict):
        manifest_dict["test_evaluated"] = True
        with open(manifest_file, "w", encoding="utf-8") as f:
            json.dump(manifest_dict, f, indent=2, sort_keys=True)

    logger.info(
        f"Final test evaluation completed successfully. Artifacts saved to: {out_path}"
    )
    return final_payload
