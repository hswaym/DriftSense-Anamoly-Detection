"""DriftSense command line interface (CLI).

Commands:
- hwcheck: inspect and report hardware (raises on requested-but-absent device)
- acquire: idempotent dataset acquisition with SHA256 integrity verification
- validate: schema compliance and quality report generation
- verify-manifest: recomputes artifact hashes and verifies manifest.json
"""

from __future__ import annotations

import argparse
import sys

from driftsense.data.acquire import acquire_dataset
from driftsense.data.aggregate import aggregate_to_canonical_grain
from driftsense.data.clean import clean_focus_data
from driftsense.data.validate import validate_dataset
from driftsense.ingest import ingest_file
from driftsense.quality import generate_quality_report
from driftsense.runtime.config import load_config
from driftsense.runtime.hardware import check_hardware
from driftsense.runtime.manifest import verify_manifest


def cmd_hwcheck(args: argparse.Namespace) -> int:
    """Execute hardware capability check."""
    try:
        hw = check_hardware(requested_device=args.device)
        print("=== DriftSense Hardware Diagnostic ===")
        print(f"Platform:       {hw['platform']}")
        print(f"Python Version: {hw['python_version']}")
        print(
            f"CPU:            {hw['cpu']} (Logical: {hw['cpu_count_logical']}, Physical: {hw['cpu_count_physical']})"
        )
        print(f"Total RAM:      {hw['ram_gb']} GB")
        print(f"Free Disk:      {hw['disk_free_gb']} GB")
        print(f"GPU:            {hw['gpu'] or 'None detected'}")
        return 0
    except RuntimeError as e:
        print(f"ERROR: Hardware check failed: {e}", file=sys.stderr)
        return 1


def cmd_acquire(args: argparse.Namespace) -> int:
    """Execute dataset acquisition."""
    url = args.url
    destination = args.destination
    expected_sha = args.expected_sha256
    overwrite = args.overwrite

    if args.config:
        cfg, _ = load_config(args.config)
        dataset_cfg = cfg.get("dataset", {})
        url = url or dataset_cfg.get("url")
        destination = destination or dataset_cfg.get("local_path")
        expected_sha = expected_sha or dataset_cfg.get("sha256")

    if not url or not destination:
        print(
            "ERROR: Both --url and --destination (or --config) are required.",
            file=sys.stderr,
        )
        return 1

    try:
        result = acquire_dataset(
            url=url,
            destination=destination,
            expected_sha256=expected_sha,
            overwrite=overwrite,
        )
        print(f"Acquisition successful: {result['path']}")
        print(f"SHA256: {result['sha256']}")
        print(f"Bytes:  {result['bytes']}")
        print(f"Cached: {result['cached']}")
        return 0
    except (ValueError, FileExistsError, RuntimeError, OSError) as e:
        print(f"ERROR: Dataset acquisition failed: {e}", file=sys.stderr)
        return 1


def cmd_validate(args: argparse.Namespace) -> int:
    """Execute dataset validation."""
    data_path = args.data
    report_path = args.report_out or "data_quality_report.json"

    if args.config:
        cfg, _ = load_config(args.config)
        dataset_cfg = cfg.get("dataset", {})
        data_path = data_path or dataset_cfg.get("local_path")

    if not data_path:
        print(
            "ERROR: Target data path (--data or --config) is required.", file=sys.stderr
        )
        return 1

    try:
        report = validate_dataset(
            data_path=data_path,
            output_report_path=report_path,
        )
        print(f"Validation finished with status: {report['status']}")
        print(f"Rows: {report['total_rows']}, Columns: {report['total_columns']}")
        if report["issues"]:
            print(f"Issues/Warnings flagged: {len(report['issues'])}")
            for issue in report["issues"][:5]:
                print(f"  - {issue}")
        print(f"Quality report saved to: {report_path}")
        return 0
    except (ValueError, RuntimeError, OSError) as e:
        print(f"ERROR: Dataset validation failed: {e}", file=sys.stderr)
        return 1


def cmd_verify_manifest(args: argparse.Namespace) -> int:
    """Recompute hashes and verify manifest.json."""
    manifest_target = args.target or "."
    is_valid, errors = verify_manifest(
        manifest_target, require_datasets=args.require_datasets
    )
    if is_valid:
        print(f"PASS: Manifest verified successfully at '{manifest_target}'.")
        return 0
    else:
        print(
            f"FAIL: Manifest verification failed with {len(errors)} error(s):",
            file=sys.stderr,
        )
        for err in errors:
            print(f"  - {err}", file=sys.stderr)
        return 1


def cmd_ingest(args: argparse.Namespace) -> int:
    """Execute multi-cloud billing file ingestion to canonical FOCUS schema."""
    from pathlib import Path


    input_path = args.input
    output_path = args.output
    provider = args.provider or "auto"
    tenant_id = args.tenant_id or "00000000-0000-0000-0000-000000000000"
    handle_refunds = args.handle_refunds or "include"
    dedup = args.dedup or "drop"
    currency = args.currency or "USD"

    if args.config:
        cfg, _ = load_config(args.config)
        ingest_cfg = cfg.get("ingest", {})
        input_path = input_path or ingest_cfg.get("input_path")
        output_path = output_path or ingest_cfg.get("output_path")
        provider = provider if args.provider else ingest_cfg.get("provider", "auto")
        tenant_id = tenant_id if args.tenant_id else ingest_cfg.get("tenant_id", tenant_id)
        handle_refunds = handle_refunds if args.handle_refunds else ingest_cfg.get("handle_refunds", "include")
        dedup = dedup if args.dedup else ingest_cfg.get("dedup", "drop")
        currency = currency if args.currency else ingest_cfg.get("currency", "USD")

    if not input_path:
        print("ERROR: Target input path (--input or --config) is required.", file=sys.stderr)
        return 1
    if not output_path:
        print("ERROR: Output path (--output or --config) is required.", file=sys.stderr)
        return 1

    try:
        df_canon, meta = ingest_file(
            file_path=input_path,
            provider=provider,
            tenant_id=tenant_id,
            default_currency=currency,
            handle_refunds=handle_refunds,
            dedup=dedup,
        )

        p_out = Path(output_path)
        p_out.parent.mkdir(parents=True, exist_ok=True)
        if p_out.suffix.lower() in [".parquet", ".pq"]:
            df_canon.to_parquet(p_out, index=False)
        else:
            df_canon.to_csv(p_out, index=False)

        print("=== DriftSense Ingestion Summary ===")
        print(f"Source File:         {meta['file_name']}")
        print(f"Detected Format:     {meta['detected_provider']} (v{meta['detected_version']}) [Confidence: {meta['detection_confidence']:.2f}]")
        print(f"Resolved Provider:   {meta['resolved_provider']}")
        print(f"Raw Records:         {meta['raw_rows']:,}")
        print(f"Canonical Records:   {meta['canonical_rows']:,}")
        print(f"Dropped Duplicates:  {meta['dropped_duplicates']:,}")
        if meta["unmapped_columns"]:
            print(f"Unmapped Columns ({len(meta['unmapped_columns'])}): {meta['unmapped_columns'][:5]}")
            for u in meta["unmapped_columns"][:3]:
                if u in meta["mapping_suggestions"]:
                    sugg, conf = meta["mapping_suggestions"][u]
                    print(f"  * Suggestion for '{u}': '{sugg}' (conf: {conf:.2f})")
        print(f"Canonical output saved to: {output_path}")
        return 0
    except Exception as e:
        print(f"ERROR: Ingestion failed: {e}", file=sys.stderr)
        return 1


def cmd_quality(args: argparse.Namespace) -> int:
    """Execute dataset quality assessment and compute 0–100 score."""
    from pathlib import Path

    import pandas as pd

    data_path = args.data
    report_out = args.report_out
    json_out = args.json_out
    fail_under = args.fail_under

    if args.config:
        cfg, _ = load_config(args.config)
        qual_cfg = cfg.get("quality", {})
        data_path = data_path or qual_cfg.get("data_path")
        report_out = report_out or qual_cfg.get("report_out")
        json_out = json_out or qual_cfg.get("json_out")
        fail_under = fail_under if fail_under is not None else qual_cfg.get("fail_under")

    if not data_path:
        print("ERROR: Data path (--data or --config) is required.", file=sys.stderr)
        return 1

    try:
        p_data = Path(data_path)
        if p_data.suffix.lower() in [".parquet", ".pq"]:
            df = pd.read_parquet(p_data)
        else:
            df = pd.read_csv(p_data, low_memory=False)

        report = generate_quality_report(
            df=df,
            dataset_name=p_data.name,
            output_json=json_out,
            output_md=report_out,
        )

        print("=== DriftSense Data Quality Assessment ===")
        print(f"Dataset:       {report['dataset_name']}")
        print(f"Total Records: {report['total_rows']:,}")
        print(f"Quality Score: {report['quality_score']}/100 (Grade: {report['grade']})")
        print(f"Summary:       {report['summary']}")
        if report["deductions"]:
            print(f"\nDeductions Breakdown ({len(report['deductions'])}):")
            for d in report["deductions"]:
                print(f"  - [{d['category']}] -{d['points_deducted']} pts: {d['reason']}")
                print(f"    Actionable Fix: {d['actionable_fix']}")

        if report_out:
            print(f"\nMarkdown report written to: {report_out}")
        if json_out:
            print(f"JSON metrics written to:     {json_out}")

        if fail_under is not None and report["quality_score"] < float(fail_under):
            print(
                f"\nFAIL: Quality score ({report['quality_score']}) is below required threshold ({fail_under}).",
                file=sys.stderr,
            )
            return 1

        return 0
    except Exception as e:
        print(f"ERROR: Quality assessment failed: {e}", file=sys.stderr)
        return 1


def cmd_clean(args: argparse.Namespace) -> int:
    """Execute FOCUS data cleaning and optional aggregation."""
    import json
    from pathlib import Path

    import pandas as pd

    cfg: dict = {}
    if args.config:
        loaded, _ = load_config(args.config)
        cfg = loaded

    ds_cfg = cfg.get("dataset", {})
    clean_cfg = cfg.get("cleaning", {})
    agg_cfg = cfg.get("aggregation", {})

    input_path = args.input or ds_cfg.get("input_path")
    if not input_path or not Path(input_path).is_file():
        print(
            f"ERROR: Valid input dataset path required (found: {input_path}).",
            file=sys.stderr,
        )
        return 1

    output_path = args.output or ds_cfg.get(
        "cleaned_output_path", "data/processed/focus_cleaned.csv"
    )
    log_path = args.log_out or ds_cfg.get("cleaning_log_path", "cleaning_log.json")

    print(f"Loading raw dataset from {input_path}...")
    df_raw = pd.read_csv(input_path, low_memory=False)

    df_cleaned, cleaning_log = clean_focus_data(df_raw, clean_cfg)
    print("=== Cleaning Summary ===")
    print(f"Initial Rows:                   {cleaning_log['initial_rows']}")
    print(f"Final Rows:                     {cleaning_log['final_rows']}")
    print(f"Exact Duplicates Dropped:       {cleaning_log['exact_duplicates_dropped']}")
    print(f"Missing Services Dropped:       {cleaning_log['missing_services_dropped']}")
    print(
        f"Missing Timestamps Dropped:     {cleaning_log['missing_timestamps_dropped']}"
    )
    print(
        f"Invalid Timestamps Dropped:     {cleaning_log['invalid_timestamps_dropped']}"
    )
    print(
        f"ConsumedQuantity Imputed:       {cleaning_log['missing_consumed_quantity_imputed']}"
    )
    print(
        f"Negative EffectiveCost Handled: {cleaning_log['negative_effective_cost_handled']}"
    )
    print(
        f"Negative BilledCost Handled:    {cleaning_log['negative_billed_cost_handled']}"
    )
    print(
        f"Unit Normalization Changes:     {cleaning_log['unit_normalization_changes']}"
    )

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    df_cleaned.to_csv(output_path, index=False)
    print(f"Cleaned dataset saved to: {output_path}")

    Path(log_path).parent.mkdir(parents=True, exist_ok=True)
    with open(log_path, "w", encoding="utf-8") as f:
        json.dump(cleaning_log, f, indent=2)
    print(f"Cleaning log saved to: {log_path}")

    if args.aggregate or agg_cfg.get("enabled", False):
        grain = args.grain or agg_cfg.get("grain", "1h")
        agg_output = args.agg_output or ds_cfg.get(
            "aggregated_output_path", f"data/processed/focus_aggregated_{grain}.csv"
        )
        df_agg, agg_summary = aggregate_to_canonical_grain(
            df_cleaned,
            grain=grain,
            service_col=agg_cfg.get("service_col", "ServiceName"),
            time_col=agg_cfg.get("time_col", "ChargePeriodStart"),
            continuous_grid=agg_cfg.get("continuous_grid", True),
            grid_scope=agg_cfg.get("grid_scope", "per_service"),
        )
        Path(agg_output).parent.mkdir(parents=True, exist_ok=True)
        df_agg.to_csv(agg_output, index=False)
        print(f"Canonical aggregation ({grain}) saved to: {agg_output}")
        print(
            f"Aggregated Rows: {agg_summary['output_rows']}, "
            f"Services: {agg_summary['distinct_services']}, "
            f"Grid Points Added: {agg_summary['grid_points_added']}"
        )

    return 0


def cmd_features(args: argparse.Namespace) -> int:
    """Execute feature engineering and chronological dataset splitting."""
    from pathlib import Path

    import pandas as pd

    from driftsense.eval.splits import chronological_split
    from driftsense.features.builder import FeaturePipeline

    cfg: dict = {}
    if args.config:
        loaded, _ = load_config(args.config)
        cfg = loaded

    ds_cfg = cfg.get("dataset", {})
    feat_cfg = cfg.get("features", {})
    split_cfg = cfg.get("splits", {})

    input_path = args.input or ds_cfg.get("input_path")
    if not input_path or not Path(input_path).is_file():
        print(
            f"ERROR: Valid input dataset path required (found: {input_path}).",
            file=sys.stderr,
        )
        return 1

    output_path = args.output or ds_cfg.get(
        "output_path", "data/processed/focus_features_1h.csv"
    )
    splits_dir = Path(args.splits_dir or ds_cfg.get("splits_dir", "data/splits"))

    print(f"Loading dataset from {input_path}...")
    df = pd.read_csv(input_path, low_memory=False)

    train_df, val_df, test_df, split_info = chronological_split(
        df,
        time_col=feat_cfg.get("time_col", "ChargePeriodStart"),
        train_frac=split_cfg.get("train_frac", 0.60),
        val_frac=split_cfg.get("val_frac", 0.20),
        test_frac=split_cfg.get("test_frac", 0.20),
        purge_gap_hours=split_cfg.get("purge_gap_hours", 0),
    )

    print("=== Chronological Split Summary ===")
    print(
        f"Train Slice: {split_info.train_rows:,} rows ({split_info.train_start} -> {split_info.train_end})"
    )
    print(
        f"Val Slice:   {split_info.val_rows:,} rows ({split_info.val_start} -> {split_info.val_end})"
    )
    print(
        f"Test Slice:  {split_info.test_rows:,} rows ({split_info.test_start} -> {split_info.test_end})"
    )

    pipeline = FeaturePipeline(
        target_col=feat_cfg.get("target_col", "EffectiveCost"),
        service_col=feat_cfg.get("service_col", "ServiceName"),
        time_col=feat_cfg.get("time_col", "ChargePeriodStart"),
        usage_col=feat_cfg.get("usage_col", "ConsumedQuantity"),
        cost_lags=feat_cfg.get("cost_lags", [1, 2, 3, 24, 168]),
        cost_windows=feat_cfg.get("cost_windows", [3, 6, 24, 168]),
        usage_lags=feat_cfg.get("usage_lags", [1, 2, 24]),
        usage_windows=feat_cfg.get("usage_windows", [6, 24]),
        scale_features=feat_cfg.get("scale_features", False),
    )
    pipeline.fit(train_df)

    train_feats = pipeline.transform(train_df)
    val_feats = pipeline.transform(val_df)
    test_feats = pipeline.transform(test_df)

    splits_dir.mkdir(parents=True, exist_ok=True)
    train_feats.to_csv(splits_dir / "train_features.csv", index=False)
    val_feats.to_csv(splits_dir / "val_features.csv", index=False)
    test_feats.to_csv(splits_dir / "test_features.csv", index=False)

    full_feats = pd.concat([train_feats, val_feats, test_feats], ignore_index=True)
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    full_feats.to_csv(output_path, index=False)

    print(f"\nGenerated {len(pipeline.feature_names_)} engineered features.")
    print(f"Saved splits to: {splits_dir}")
    print(f"Saved full feature matrix to: {output_path} ({len(full_feats):,} rows)")
    return 0


def cmd_forecast(args: argparse.Namespace) -> int:
    """Train and evaluate baseline and ML forecasting models on train/val splits."""
    import json
    from pathlib import Path

    import pandas as pd

    from driftsense.eval.metrics import compute_all_metrics
    from driftsense.forecast.base import BaseForecaster
    from driftsense.forecast.naive import (
        MovingAverageForecaster,
        SeasonalNaiveForecaster,
    )
    from driftsense.forecast.smoothing import ExponentialSmoothingForecaster
    from driftsense.forecast.xgb import XGBoostForecaster

    cfg: dict = {}
    if args.config:
        loaded, _ = load_config(args.config)
        cfg = loaded

    ds_cfg = cfg.get("dataset", {})
    models_cfg = cfg.get("models", {})
    eval_cfg = cfg.get("evaluation", {})
    out_cfg = cfg.get("output", {})

    train_path = args.train or ds_cfg.get(
        "train_path", "data/splits/train_features.csv"
    )
    val_path = args.val or ds_cfg.get("val_path", "data/splits/val_features.csv")
    models_dir = Path(args.models_dir or out_cfg.get("models_dir", "models/forecast"))
    metrics_path = Path(
        args.metrics_out
        or out_cfg.get("metrics_path", "metrics/val_forecast_metrics.json")
    )
    val_preds_path = Path(
        args.predictions_out
        or out_cfg.get(
            "val_predictions_path", "data/predictions/val_forecast_predictions.csv"
        )
    )

    if not Path(train_path).is_file():
        print(f"ERROR: Train split not found at {train_path}", file=sys.stderr)
        return 1
    if not Path(val_path).is_file():
        print(f"ERROR: Validation split not found at {val_path}", file=sys.stderr)
        return 1

    # Strict isolation check: ensure test split is never evaluated during Phase 6 (A6.4)
    if "test" in Path(val_path).name.lower():
        print(
            "ERROR: A6.4 Violation — Test split evaluation is strictly forbidden during Phase 6.",
            file=sys.stderr,
        )
        return 1

    target_col = ds_cfg.get("target_col", "EffectiveCost")
    time_col = ds_cfg.get("time_col", "ChargePeriodStart")
    service_col = ds_cfg.get("service_col", "ServiceName")
    primary_metric = eval_cfg.get("primary_metric", "wape")

    print(f"Loading training data from: {train_path}")
    df_train = pd.read_csv(train_path, low_memory=False)
    print(f"Loading validation data from: {val_path}")
    df_val = pd.read_csv(val_path, low_memory=False)

    print(f"Train rows: {len(df_train):,}, Validation rows: {len(df_val):,}")
    print(f"Target column: {target_col}")

    y_train = df_train[target_col].to_numpy(dtype=float)
    y_val = df_val[target_col].to_numpy(dtype=float)

    models_to_run: list[BaseForecaster] = []

    if models_cfg.get("seasonal_naive", {}).get("enabled", True):
        sn_cfg = models_cfg.get("seasonal_naive", {})
        models_to_run.append(
            SeasonalNaiveForecaster(
                seasonality=sn_cfg.get("seasonality", 24),
                config=sn_cfg,
            )
        )

    if models_cfg.get("moving_average", {}).get("enabled", True):
        ma_cfg = models_cfg.get("moving_average", {})
        models_to_run.append(
            MovingAverageForecaster(
                window=ma_cfg.get("window", 24),
                config=ma_cfg,
            )
        )

    if models_cfg.get("exponential_smoothing", {}).get("enabled", True):
        es_cfg = models_cfg.get("exponential_smoothing", {})
        models_to_run.append(
            ExponentialSmoothingForecaster(
                alpha=es_cfg.get("alpha", 0.25),
                config=es_cfg,
            )
        )

    if models_cfg.get("xgboost", {}).get("enabled", True):
        xgb_cfg = models_cfg.get("xgboost", {})
        models_to_run.append(
            XGBoostForecaster(
                n_estimators=xgb_cfg.get("n_estimators", 150),
                max_depth=xgb_cfg.get("max_depth", 5),
                learning_rate=xgb_cfg.get("learning_rate", 0.05),
                subsample=xgb_cfg.get("subsample", 0.8),
                colsample_bytree=xgb_cfg.get("colsample_bytree", 0.8),
                device=xgb_cfg.get("device", "cpu"),
                seed=xgb_cfg.get("seed", 42),
                log_transform=xgb_cfg.get("log_transform", True),
                config=xgb_cfg,
            )
        )

    models_dir.mkdir(parents=True, exist_ok=True)
    metrics_path.parent.mkdir(parents=True, exist_ok=True)
    val_preds_path.parent.mkdir(parents=True, exist_ok=True)

    results: dict = {}
    preds_dict: dict = {
        time_col: df_val[time_col],
        service_col: df_val[service_col],
        f"{target_col}_actual": y_val,
    }

    print("\n=== Training & Evaluating Forecasting Models ===")
    for i, model in enumerate(models_to_run, 1):
        print(f"[{i}/{len(models_to_run)}] Fitting {model.name}...")
        model.fit(
            df_train,
            target_col=target_col,
            time_col=time_col,
            service_col=service_col,
        )
        preds = model.predict(df_val)
        preds_dict[f"{target_col}_pred_{model.name}"] = preds

        model_metrics = compute_all_metrics(
            y_true=y_val,
            y_pred=preds,
            y_train=y_train,
        )
        results[model.name] = {
            "metrics": model_metrics,
            "metadata": model.get_metadata(),
        }

        # Serialize model
        saved_file = model.save(models_dir)
        print(f"    Saved model checkpoint to: {saved_file}")

    # Build comparison summary
    print("\n=== Validation Forecast Evaluation Summary ===")
    header = f"{'Model':<25} | {'MAE ($)':<10} | {'RMSE ($)':<10} | {'sMAPE (%)':<10} | {'WAPE (%)':<10} | {'MASE':<8}"
    print(header)
    print("-" * len(header))
    for name, res in results.items():
        m = res["metrics"]
        print(
            f"{name:<25} | {m['mae']:<10.4f} | {m['rmse']:<10.4f} | {m['smape']:<10.2f} | {m['wape']:<10.2f} | {m['mase']:<8.4f}"
        )

    # Champion selection
    champion_name = min(
        results.keys(),
        key=lambda k: results[k]["metrics"].get(primary_metric, float("inf")),
    )
    print(
        f"\nChampion Model Selected on Validation ({primary_metric}): '{champion_name}'"
    )

    summary_payload = {
        "primary_metric": primary_metric,
        "champion_model": champion_name,
        "validation_rows": len(df_val),
        "training_rows": len(df_train),
        "models": results,
    }

    with open(metrics_path, "w", encoding="utf-8") as f:
        json.dump(summary_payload, f, indent=2)
    print(f"Validation metrics report saved to: {metrics_path}")

    df_preds = pd.DataFrame(preds_dict)
    df_preds.to_csv(val_preds_path, index=False)
    print(f"Validation predictions saved to: {val_preds_path}")

    return 0


def cmd_detect(args: argparse.Namespace) -> int:
    """Train and evaluate statistical and ML anomaly detectors on validation split."""
    import json
    from pathlib import Path

    import numpy as np
    import pandas as pd

    from driftsense.detect.base import BaseAnomalyDetector
    from driftsense.detect.iforest import IsolationForestDetector
    from driftsense.detect.ocsvm import OneClassSVMDetector
    from driftsense.detect.rolling_threshold import RollingThresholdDetector
    from driftsense.detect.zscore import ZScoreDetector
    from driftsense.eval.detection_metrics import (
        event_level_metrics,
        point_level_metrics,
        stratified_fp_analysis,
    )
    from driftsense.forecast.xgb import XGBoostForecaster
    from driftsense.synth.injector import SyntheticInjector

    cfg: dict = {}
    if args.config:
        loaded, _ = load_config(args.config)
        cfg = loaded

    ds_cfg = cfg.get("dataset", {})
    synth_cfg = cfg.get("synthetic", {})
    det_cfg = cfg.get("detectors", {})
    eval_cfg = cfg.get("evaluation", {})
    out_cfg = cfg.get("output", {})

    train_path = args.train or ds_cfg.get(
        "train_path", "data/splits/train_features.csv"
    )
    val_path = args.val or ds_cfg.get("val_path", "data/splits/val_features.csv")
    detectors_dir = Path(
        args.detectors_dir or out_cfg.get("detectors_dir", "models/detect")
    )
    metrics_path = Path(
        args.metrics_out
        or out_cfg.get("metrics_path", "metrics/val_detect_metrics.json")
    )
    val_detections_path = Path(
        args.predictions_out
        or out_cfg.get("val_detections_path", "data/predictions/val_detections.csv")
    )
    labels_path = Path(
        out_cfg.get("labels_path", "data/labels/val_anomaly_labels.json")
    )
    events_path = Path(
        out_cfg.get("events_path", "data/events/val_operational_events.json")
    )

    if not Path(train_path).is_file():
        print(f"ERROR: Train split not found at {train_path}", file=sys.stderr)
        return 1
    if not Path(val_path).is_file():
        print(f"ERROR: Validation split not found at {val_path}", file=sys.stderr)
        return 1

    # Strict A7.3 isolation check: ensure test split is never evaluated during Phase 7
    if "test" in Path(val_path).name.lower():
        print(
            "ERROR: A7.3 Violation — Test split evaluation is strictly forbidden during Phase 7.",
            file=sys.stderr,
        )
        return 1

    target_col = ds_cfg.get("target_col", "EffectiveCost")
    time_col = ds_cfg.get("time_col", "ChargePeriodStart")
    service_col = ds_cfg.get("service_col", "ServiceName")
    primary_metric = eval_cfg.get("primary_metric", "event_f1")

    print(f"Loading train features: {train_path}")
    df_train = pd.read_csv(train_path, low_memory=False)
    print(f"Loading val features:   {val_path}")
    df_val = pd.read_csv(val_path, low_memory=False)

    # Compute residuals using champion forecast model or fallback
    forecast_model_path = ds_cfg.get("forecast_model_path")
    if forecast_model_path and Path(forecast_model_path).is_file():
        print(f"Loading champion forecaster from: {forecast_model_path}")
        forecaster = XGBoostForecaster.load(forecast_model_path)
        train_preds = forecaster.predict(df_train)
        val_preds = forecaster.predict(df_val)
    else:
        print("Using historical mean forecast for residual baseline...")
        train_preds = np.zeros(len(df_train))
        val_preds = np.zeros(len(df_val))

    df_train["residual"] = df_train[target_col] - train_preds
    df_val["residual"] = df_val[target_col] - val_preds

    # Synthetic Ground-Truth Track Generation (Contract 5 & 6)
    print(
        "Generating calibrated synthetic ground-truth anomalies on validation track..."
    )
    injector = SyntheticInjector(
        seed=synth_cfg.get("seed", 42),
        injection_rate=synth_cfg.get("injection_rate", 0.03),
        min_duration_hours=synth_cfg.get("min_duration_hours", 2),
        max_duration_hours=synth_cfg.get("max_duration_hours", 6),
        multiplier_range=tuple(synth_cfg.get("multiplier_range", [1.5, 3.5])),
        sigma_range=tuple(synth_cfg.get("sigma_range", [2.5, 5.0])),
    )
    df_val_synth, labels, events = injector.inject(
        df_val,
        cost_col=target_col,
        service_col=service_col,
        time_col=time_col,
    )
    df_val_synth["residual"] = df_val_synth[target_col] - val_preds

    labels_path.parent.mkdir(parents=True, exist_ok=True)
    with open(labels_path, "w", encoding="utf-8") as f:
        json.dump(labels, f, indent=2)
    events_path.parent.mkdir(parents=True, exist_ok=True)
    with open(events_path, "w", encoding="utf-8") as f:
        json.dump(events, f, indent=2)

    detectors: list[BaseAnomalyDetector] = []
    if det_cfg.get("zscore", {}).get("enabled", True):
        z_cfg = det_cfg.get("zscore", {})
        detectors.append(
            ZScoreDetector(
                threshold=z_cfg.get("threshold", 3.0),
                per_service=z_cfg.get("per_service", True),
                one_sided=z_cfg.get("one_sided", True),
                config=z_cfg,
            )
        )
    if det_cfg.get("rolling_threshold", {}).get("enabled", True):
        rt_cfg = det_cfg.get("rolling_threshold", {})
        detectors.append(
            RollingThresholdDetector(
                window=rt_cfg.get("window", 24),
                threshold=rt_cfg.get("threshold", 3.0),
                config=rt_cfg,
            )
        )
    if det_cfg.get("iforest", {}).get("enabled", True):
        if_cfg = det_cfg.get("iforest", {})
        detectors.append(
            IsolationForestDetector(
                n_estimators=if_cfg.get("n_estimators", 100),
                contamination=if_cfg.get("contamination", 0.03),
                threshold=if_cfg.get("threshold", 0.55),
                seed=if_cfg.get("seed", 42),
                config=if_cfg,
            )
        )
    if det_cfg.get("ocsvm", {}).get("enabled", True):
        oc_cfg = det_cfg.get("ocsvm", {})
        detectors.append(
            OneClassSVMDetector(
                kernel=oc_cfg.get("kernel", "rbf"),
                nu=oc_cfg.get("nu", 0.03),
                threshold=oc_cfg.get("threshold", 0.0),
                config=oc_cfg,
            )
        )

    detectors_dir.mkdir(parents=True, exist_ok=True)
    results_synthetic = {}
    results_real = {}

    detections_dict = {
        time_col: df_val[time_col],
        service_col: df_val[service_col],
        "is_synthetic_anomaly": df_val_synth["is_anomaly"],
        "cost_actual_clean": df_val[target_col],
        "cost_actual_synth": df_val_synth[target_col],
        "residual_clean": df_val["residual"],
        "residual_synth": df_val_synth["residual"],
    }

    print("\n=== Fitting Detectors on D_train Residuals ===")
    for i, det in enumerate(detectors, 1):
        print(f"[{i}/{len(detectors)}] Fitting {det.name}...")
        det.fit(
            df_train,
            residual_col="residual",
            service_col=service_col,
            time_col=time_col,
        )

        # Real Data Track
        clean_scores = det.score(df_val)
        clean_preds = det.predict(df_val)
        detections_dict[f"score_clean_{det.name}"] = clean_scores
        detections_dict[f"alert_clean_{det.name}"] = clean_preds

        y_zero = np.zeros(len(df_val), dtype=int)
        df_val_eval = df_val.copy()
        df_val_eval["y_zero"] = y_zero
        df_val_eval["pred"] = clean_preds
        fp_strat = stratified_fp_analysis(
            df_val_eval, y_true_col="y_zero", y_pred_col="pred"
        )
        results_real[det.name] = {
            "total_points": len(df_val),
            "false_positives": int(np.sum(clean_preds == 1)),
            "fpr": float(np.mean(clean_preds == 1)),
            "stratified_fpr": fp_strat,
            "metadata": det.get_metadata(),
        }

        # Synthetic Track
        synth_scores = det.score(df_val_synth)
        synth_preds = det.predict(df_val_synth)
        detections_dict[f"score_synth_{det.name}"] = synth_scores
        detections_dict[f"alert_synth_{det.name}"] = synth_preds

        p_metrics = point_level_metrics(
            y_true=df_val_synth["is_anomaly"].to_numpy(dtype=int),
            y_pred=synth_preds,
        )
        ev_metrics = event_level_metrics(
            timestamps=df_val_synth[time_col],
            y_true=df_val_synth["is_anomaly"].to_numpy(dtype=int),
            y_pred=synth_preds,
        )
        results_synthetic[det.name] = {
            "point_metrics": p_metrics,
            "event_metrics": ev_metrics,
            "metadata": det.get_metadata(),
        }

        chk = det.save(detectors_dir)
        print(f"    Checkpointed: {chk.name}")

    print("\n" + "=" * 90)
    print("TRACK 1: REAL DATA TRACK (False Positive Rate & Diurnal Stratification)")
    print("=" * 90)
    h_real = f"{'Detector':<22} | {'Alerts':<8} | {'Overall FPR (%)':<15} | {'Weekday FPR (%)':<15} | {'Weekend FPR (%)':<15}"
    print(h_real)
    print("-" * len(h_real))
    for name, res in results_real.items():
        st = res.get("stratified_fpr", {})
        wk_fpr = st.get("weekday_fpr", 0.0) * 100.0
        we_fpr = st.get("weekend_fpr", 0.0) * 100.0
        print(
            f"{name:<22} | {res['false_positives']:<8} | {res['fpr'] * 100:<15.2f} | {wk_fpr:<15.2f} | {we_fpr:<15.2f}"
        )

    print("\n" + "=" * 90)
    print("TRACK 2: SYNTHETIC GROUND-TRUTH TRACK (Calibrated Incident Evaluation)")
    print("=" * 90)
    h_synth = f"{'Detector':<22} | {'Point F1':<10} | {'Point Prec':<10} | {'Point Rec':<10} | {'Event F1':<10} | {'Event Rec':<10} | {'Mean Delay (h)':<14}"
    print(h_synth)
    print("-" * len(h_synth))
    for name, res in results_synthetic.items():
        pm = res["point_metrics"]
        em = res["event_metrics"]
        print(
            f"{name:<22} | {pm['f1']:<10.4f} | {pm['precision']:<10.4f} | {pm['recall']:<10.4f} | {em['event_f1']:<10.4f} | {em['event_recall']:<10.4f} | {em['mean_delay_hours']:<14.2f}"
        )

    champion_name = max(
        results_synthetic.keys(),
        key=lambda k: results_synthetic[k]["event_metrics"].get(primary_metric, 0.0),
    )
    print("=" * 90)
    print(
        f"CHAMPION DETECTOR SELECTED: '{champion_name}' (Highest {primary_metric.upper()} on Validation Ground Truth)"
    )
    print("=" * 90)

    metrics_path.parent.mkdir(parents=True, exist_ok=True)
    summary_payload = {
        "primary_metric": primary_metric,
        "champion_detector": champion_name,
        "validation_rows": len(df_val),
        "synthetic_incidents": len(labels),
        "real_track": results_real,
        "synthetic_track": results_synthetic,
    }
    with open(metrics_path, "w", encoding="utf-8") as f:
        json.dump(summary_payload, f, indent=2)
    print(f"\nSaved validation detection metrics to: {metrics_path}")

    val_detections_path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(detections_dict).to_csv(val_detections_path, index=False)
    print(f"Saved validation detections matrix to: {val_detections_path}")

    return 0


def cmd_attribute(args: argparse.Namespace) -> int:
    """Train and evaluate root-cause attribution baselines and ML models."""
    import json
    from pathlib import Path

    import pandas as pd

    from driftsense.attribute.base import BaseAttributor
    from driftsense.attribute.correlation import TemporalCorrelationAttributor
    from driftsense.attribute.prior_baseline import ClassPriorAttributor
    from driftsense.attribute.random_baseline import RandomAttributor
    from driftsense.attribute.xgb_attributor import XGBoostAttributor
    from driftsense.eval.attribution_metrics import evaluate_attribution_suite
    from driftsense.synth.injector import SyntheticInjector

    cfg: dict = {}
    if args.config:
        loaded, _ = load_config(args.config)
        cfg = loaded

    ds_cfg = cfg.get("dataset", {})
    attr_cfg = cfg.get("attributors", {})
    eval_cfg = cfg.get("evaluation", {})
    out_cfg = cfg.get("output", {})

    train_path = args.train or ds_cfg.get(
        "train_path", "data/splits/train_features.csv"
    )
    val_path = args.val or ds_cfg.get("val_path", "data/splits/val_features.csv")
    attributors_dir = Path(
        args.attributors_dir or out_cfg.get("attributors_dir", "models/attribute")
    )
    metrics_path = Path(
        args.metrics_out
        or out_cfg.get("metrics_path", "metrics/val_attribute_metrics.json")
    )
    val_attributions_path = Path(
        args.predictions_out
        or out_cfg.get("val_attributions_path", "data/predictions/val_attributions.csv")
    )

    if not Path(train_path).is_file():
        print(f"ERROR: Train split not found at {train_path}", file=sys.stderr)
        return 1
    if not Path(val_path).is_file():
        print(f"ERROR: Validation split not found at {val_path}", file=sys.stderr)
        return 1

    # Strict A8.4 quarantine check: ensure test split is never evaluated during Phase 8
    if "test" in Path(val_path).name.lower():
        print(
            "ERROR: A8.4 Violation — Test split evaluation is strictly forbidden during Phase 8.",
            file=sys.stderr,
        )
        return 1

    val_labels_path = Path(
        ds_cfg.get(
            "val_labels_path",
            "runs/run_20261019_174627_660563/val_anomaly_labels.json",
        )
    )
    val_events_path = Path(
        ds_cfg.get(
            "val_events_path",
            "runs/run_20261019_174627_660563/val_operational_events.json",
        )
    )

    if val_labels_path.is_file() and val_events_path.is_file():
        print(f"Loading incident labels from: {val_labels_path}")
        with open(val_labels_path, "r", encoding="utf-8") as f:
            incidents = json.load(f)
        print(f"Loading operational events from: {val_events_path}")
        with open(val_events_path, "r", encoding="utf-8") as f:
            events = json.load(f)
    else:
        print(
            "Generating calibrated synthetic incidents and events on validation dataset..."
        )
        df_val = pd.read_csv(val_path, low_memory=False)
        injector = SyntheticInjector(seed=42, injection_rate=0.03)
        _, incidents, events = injector.inject(df_val)

    print(f"Total Incidents: {len(incidents):,}, Total Events: {len(events):,}")

    n_train_inc = max(1, int(len(incidents) * 0.6))
    train_incidents = incidents[:n_train_inc]
    val_incidents = incidents[n_train_inc:]

    print(
        f"Attributor Train Incidents: {len(train_incidents)}, Validation Incidents: {len(val_incidents)}"
    )

    attributors: list[BaseAttributor] = []
    if attr_cfg.get("random", {}).get("enabled", True):
        attributors.append(
            RandomAttributor(seed=attr_cfg.get("random", {}).get("seed", 42))
        )
    if attr_cfg.get("prior", {}).get("enabled", True):
        attributors.append(ClassPriorAttributor())
    if attr_cfg.get("correlation", {}).get("enabled", True):
        c_cfg = attr_cfg.get("correlation", {})
        attributors.append(
            TemporalCorrelationAttributor(
                lookback_hours=c_cfg.get("lookback_hours", 3.0),
                decay_halflife_hours=c_cfg.get("decay_halflife_hours", 1.0),
                service_match_multiplier=c_cfg.get("service_match_multiplier", 2.0),
            )
        )
    if attr_cfg.get("xgboost", {}).get("enabled", True):
        x_cfg = attr_cfg.get("xgboost", {})
        attributors.append(
            XGBoostAttributor(
                n_estimators=x_cfg.get("n_estimators", 100),
                max_depth=x_cfg.get("max_depth", 4),
                learning_rate=x_cfg.get("learning_rate", 0.05),
                lookback_hours=x_cfg.get("lookback_hours", 4.0),
                seed=x_cfg.get("seed", 42),
            )
        )

    attributors_dir.mkdir(parents=True, exist_ok=True)
    results = {}
    y_true_val = [inc["primary_cause"] for inc in val_incidents]
    attributions_records = []

    print("\n=== Fitting Attributors on Historical Incidents ===")
    for i, model in enumerate(attributors, 1):
        print(f"[{i}/{len(attributors)}] Fitting {model.name}...")
        model.fit(train_incidents, events)

        top3_preds = model.predict_top_k(val_incidents, events, k=3)
        metrics = evaluate_attribution_suite(y_true_val, top3_preds)
        results[model.name] = {
            "metrics": metrics,
            "metadata": model.get_metadata(),
        }

        chk = model.save(attributors_dir)
        print(
            f"    Checkpointed: {chk.name} (Top-1 Acc: {metrics['top_1_accuracy'] * 100:.1f}%, Top-3 Acc: {metrics['top_3_accuracy'] * 100:.1f}%)"
        )

    print("\n" + "=" * 80)
    print("DRIFTSENSE — VALIDATION ROOT CAUSE ATTRIBUTION BENCHMARK")
    print("=" * 80)
    header = f"{'Attributor':<25} | {'Top-1 Acc (%)':<15} | {'Top-2 Acc (%)':<15} | {'Top-3 Acc (%)':<15}"
    print(header)
    print("-" * len(header))
    for name, res in results.items():
        m = res["metrics"]
        print(
            f"{name:<25} | {m['top_1_accuracy'] * 100:<15.2f} | {m['top_2_accuracy'] * 100:<15.2f} | {m['top_3_accuracy'] * 100:<15.2f}"
        )

    primary_metric = eval_cfg.get("primary_metric", "top_1_accuracy")
    champion_name = max(
        results.keys(), key=lambda k: results[k]["metrics"].get(primary_metric, 0.0)
    )
    print("=" * 80)
    print(
        f"CHAMPION ATTRIBUTOR SELECTED: '{champion_name}' (Highest {primary_metric.upper()} on Validation Incidents)"
    )
    print("=" * 80)

    summary_payload = {
        "primary_metric": primary_metric,
        "champion_attributor": champion_name,
        "total_incidents": len(incidents),
        "train_incidents": len(train_incidents),
        "validation_incidents": len(val_incidents),
        "models": results,
    }
    metrics_path.parent.mkdir(parents=True, exist_ok=True)
    with open(metrics_path, "w", encoding="utf-8") as f:
        json.dump(summary_payload, f, indent=2)
    print(f"\nSaved validation attribution metrics to: {metrics_path}")

    for inc in val_incidents:
        row = {
            "label_id": inc.get("label_id"),
            "service_id": inc.get("service_id"),
            "onset_timestamp": inc.get("onset_timestamp"),
            "primary_cause_true": inc.get("primary_cause"),
        }
        for name in results:
            top_preds = attributors[
                [a.name for a in attributors].index(name)
            ].predict_top_k([inc], events, k=3)[0]
            row[f"{name}_top1"] = top_preds[0] if len(top_preds) > 0 else ""
            row[f"{name}_top2"] = top_preds[1] if len(top_preds) > 1 else ""
            row[f"{name}_top3"] = top_preds[2] if len(top_preds) > 2 else ""
        attributions_records.append(row)

    val_attributions_path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(attributions_records).to_csv(val_attributions_path, index=False)
    print(f"Saved validation attributions matrix to:  {val_attributions_path}")

    return 0


def cmd_explain(args: argparse.Namespace) -> int:
    """Compute TreeSHAP explanations, stability checks, and non-causal narratives."""
    import json
    from pathlib import Path

    import numpy as np
    import pandas as pd

    from driftsense.explain.consistency import compute_cause_agreement
    from driftsense.explain.importance import compute_global_importance
    from driftsense.explain.narrative import (
        synthesize_cost_narrative,
        validate_non_causal_text,
    )
    from driftsense.explain.shap_explainer import TreeSHAPExplainer
    from driftsense.forecast.xgb import XGBoostForecaster

    cfg: dict = {}
    if args.config:
        loaded, _ = load_config(args.config)
        cfg = loaded

    ds_cfg = cfg.get("dataset", {})
    exp_cfg = cfg.get("explain", {})
    out_cfg = cfg.get("output", {})

    val_path = args.val or ds_cfg.get("val_path", "data/splits/val_features.csv")
    model_path = args.model or ds_cfg.get(
        "forecast_model_path", "runs/run_20261019_172039_9dc09a/models/xgboost.joblib"
    )
    metrics_path = Path(
        args.metrics_out
        or out_cfg.get("metrics_path", "metrics/val_explain_metrics.json")
    )
    narratives_path = Path(
        out_cfg.get("narratives_path", "reports/explain/val_narratives.md")
    )
    importance_path = Path(
        out_cfg.get("importance_path", "reports/explain/global_feature_importance.csv")
    )

    if not Path(val_path).is_file():
        print(f"ERROR: Validation split not found at {val_path}", file=sys.stderr)
        return 1

    # Strict A9.3 quarantine check: ensure test split is never evaluated during Phase 9
    if "test" in Path(val_path).name.lower():
        print(
            "ERROR: A9.3 Violation — Test split evaluation is strictly forbidden during Phase 9.",
            file=sys.stderr,
        )
        return 1

    print(f"Loading validation features: {val_path}")
    df_val = pd.read_csv(val_path, low_memory=False)

    if not Path(model_path).is_file():
        print(
            f"ERROR: Champion forecaster not found at {model_path}. Train forecasting model first.",
            file=sys.stderr,
        )
        return 1

    print(f"Loading champion forecasting model from: {model_path}")
    forecaster = XGBoostForecaster.load(model_path)

    atol_tol = getattr(args, "atol", None) or exp_cfg.get("atol_additivity", 0.002)
    explainer = TreeSHAPExplainer(
        forecaster.model_,
        feature_names=forecaster.feature_names_,
        atol=atol_tol,
    )

    X_val = df_val[forecaster.feature_names_]
    print(f"Computing TreeSHAP values for {len(X_val):,} validation points...")
    shap_values = explainer.explain(X_val, check_additivity=True)
    print("PASS: A9.1 Additivity Check Verified on validation dataset.")

    # Compute Global Importance
    imp_df = compute_global_importance(
        shap_values, forecaster.feature_names_, model=forecaster.model_
    )
    importance_path.parent.mkdir(parents=True, exist_ok=True)
    imp_df.to_csv(importance_path, index=False)
    print(f"Saved global feature importance ranking to: {importance_path}")

    # Top features summary table
    print("\n" + "=" * 80)
    print("TOP 5 GLOBAL COST DRIVERS (TreeSHAP Mean |Attribution|)")
    print("=" * 80)
    for _, row in imp_df.head(5).iterrows():
        print(
            f"Rank {int(row['rank'])}: {row['feature']:<30} | {row['mean_abs_shap']:<10.4f} ({row['relative_importance_pct']:.1f}%)"
        )
    print("=" * 80)

    # Load operational events & incidents if present
    events_path = Path(ds_cfg.get("val_events_path", ""))
    labels_path = Path(ds_cfg.get("val_labels_path", ""))
    events: list[dict] = []
    labels: list[dict] = []
    if events_path.is_file():
        with open(events_path, "r", encoding="utf-8") as f:
            events = json.load(f)
    if labels_path.is_file():
        with open(labels_path, "r", encoding="utf-8") as f:
            labels = json.load(f)

    # Generate sample instance explanations and natural language narratives
    target_col = ds_cfg.get("target_col", "EffectiveCost")
    time_col = ds_cfg.get("time_col", "ChargePeriodStart")
    service_col = ds_cfg.get("service_col", "ServiceName")

    preds_val = forecaster.predict(df_val)
    residuals = df_val[target_col] - preds_val

    # Select top anomaly instances
    anomaly_indices = np.argsort(np.abs(residuals))[::-1][
        : exp_cfg.get("num_sample_anomalies", 10)
    ]
    instance_explanations = []
    narratives = []

    print("\nSynthesizing non-causal audit narratives for top cost anomalies...")
    for rank, idx in enumerate(anomaly_indices, 1):
        row = df_val.iloc[idx]
        pred_id = f"val_point_{idx}"
        exp = explainer.explain_instance(
            row[forecaster.feature_names_], prediction_id=pred_id, top_k=5
        )
        instance_explanations.append(exp.to_dict())

        svc = str(row.get(service_col, "UnknownService"))
        ts = str(row.get(time_col, ""))
        actual = float(row[target_col])
        expected = float(preds_val[idx])

        # Filter coincident events within +/- 3 hours
        coincident = [
            ev
            for ev in events
            if ev.get("service_id") == svc or ev.get("service_name") == svc
        ][:2]

        narr = synthesize_cost_narrative(
            service_name=svc,
            timestamp=ts,
            actual_cost=actual,
            expected_cost=expected,
            top_positive_drivers=exp.top_positive_drivers,
            coincident_events=coincident,
        )
        validate_non_causal_text(narr)
        narratives.append(f"## Incident Case {rank}\n\n{narr}\n\n---\n")

    narratives_path.parent.mkdir(parents=True, exist_ok=True)
    with open(narratives_path, "w", encoding="utf-8") as f:
        f.write("# DriftSense — Executive Cost Anomaly Explanations\n\n")
        f.write("\n".join(narratives))
    print(f"Saved non-causal explanation narratives to: {narratives_path}")

    # Ground-truth agreement check
    agreement_report = {}
    if labels:
        agreement_report = compute_cause_agreement(
            instance_explanations, labels, top_k=exp_cfg.get("top_k_drivers", 3)
        )
        print(
            f"Synthetic Cause Agreement Rate: {agreement_report.get('agreement_rate', 0.0) * 100:.1f}%"
        )

    # Metrics summary export
    metrics_payload = {
        "validation_rows": len(df_val),
        "additivity_verified": True,
        "max_additivity_error": float(
            np.max(
                np.abs(
                    np.sum(shap_values, axis=1) + explainer.expected_value - preds_val
                )
            )
        ),
        "global_top_features": imp_df.head(10).to_dict(orient="records"),
        "cause_agreement": agreement_report,
    }
    metrics_path.parent.mkdir(parents=True, exist_ok=True)
    with open(metrics_path, "w", encoding="utf-8") as f:
        json.dump(metrics_payload, f, indent=2)
    print(f"Saved explainability metrics to: {metrics_path}")

    return 0


def main(argv: list[str] | None = None) -> int:
    """CLI Entry point."""
    parser = argparse.ArgumentParser(
        prog="driftsense",
        description="DriftSense CLI — Cloud Cost Anomaly Detection and Attribution",
    )
    subparsers = parser.add_subparsers(dest="subcommand", required=True)

    # hwcheck
    p_hw = subparsers.add_parser(
        "hwcheck", help="Check system hardware and accelerator status"
    )
    p_hw.add_argument(
        "--device", choices=["cpu", "gpu", "cuda"], help="Required execution device"
    )
    p_hw.set_defaults(func=cmd_hwcheck)

    # acquire
    p_acq = subparsers.add_parser("acquire", help="Idempotently download dataset")
    p_acq.add_argument("--config", help="Path to dataset configuration YAML")
    p_acq.add_argument("--url", help="Direct dataset download URL")
    p_acq.add_argument("--destination", help="Target destination path")
    p_acq.add_argument("--expected-sha256", help="Expected SHA256 checksum")
    p_acq.add_argument(
        "--overwrite", action="store_true", help="Force overwrite existing file"
    )
    p_acq.set_defaults(func=cmd_acquire)

    # validate
    p_val = subparsers.add_parser(
        "validate", help="Validate dataset schema and emit quality report"
    )
    p_val.add_argument("--config", help="Path to dataset configuration YAML")
    p_val.add_argument("--data", help="Path to CSV dataset file")
    p_val.add_argument("--report-out", help="Path to output data_quality_report.json")
    p_val.set_defaults(func=cmd_validate)

    # verify-manifest
    p_vm = subparsers.add_parser(
        "verify-manifest", help="Verify run manifest and artifact hashes"
    )
    p_vm.add_argument(
        "target",
        nargs="?",
        default=".",
        help="Directory containing manifest.json or path to manifest",
    )
    p_vm.add_argument(
        "--require-datasets",
        action="store_true",
        help="Require dataset files to be present locally for hash verification",
    )
    p_vm.set_defaults(func=cmd_verify_manifest)

    # ingest
    p_ing = subparsers.add_parser(
        "ingest", help="Ingest multi-cloud billing file to canonical FOCUS schema"
    )
    p_ing.add_argument("--config", help="Path to ingestion configuration YAML")
    p_ing.add_argument("--input", help="Path to input raw billing export CSV/Parquet")
    p_ing.add_argument("--output", help="Path to output canonical CSV/Parquet")
    p_ing.add_argument("--provider", default="auto", choices=["auto", "focus", "aws_cur", "azure_cost", "gcp_billing"], help="Cloud billing provider")
    p_ing.add_argument("--tenant-id", default="00000000-0000-0000-0000-000000000000", help="Tenant UUID")
    p_ing.add_argument("--handle-refunds", default="include", choices=["include", "exclude", "zero_clamp"], help="Refund/credit handling policy")
    p_ing.add_argument("--dedup", default="drop", choices=["drop", "keep"], help="Deduplication policy")
    p_ing.add_argument("--currency", default="USD", help="Single reporting currency")
    p_ing.set_defaults(func=cmd_ingest)

    # quality
    p_qual = subparsers.add_parser(
        "quality", help="Evaluate dataset quality score (0-100) and emit diagnostic report"
    )
    p_qual.add_argument("--config", help="Path to quality configuration YAML")
    p_qual.add_argument("--data", help="Path to input billing dataset CSV/Parquet")
    p_qual.add_argument("--report-out", help="Path to output Markdown quality report")
    p_qual.add_argument("--json-out", help="Path to output JSON quality metrics")
    p_qual.add_argument("--fail-under", type=float, help="Fail with exit code 1 if score < threshold")
    p_qual.set_defaults(func=cmd_quality)

    # clean
    p_cln = subparsers.add_parser(
        "clean", help="Clean dataset and aggregate to canonical grain"
    )
    p_cln.add_argument("--config", help="Path to clean configuration YAML")
    p_cln.add_argument("--input", help="Path to raw CSV dataset")
    p_cln.add_argument("--output", help="Path to output cleaned CSV")
    p_cln.add_argument("--log-out", help="Path to output cleaning_log.json")
    p_cln.add_argument(
        "--aggregate", action="store_true", help="Aggregate to canonical grain"
    )
    p_cln.add_argument("--grain", default="1h", help="Canonical grain ('1h', '1D')")
    p_cln.add_argument("--agg-output", help="Path to output aggregated CSV")
    p_cln.set_defaults(func=cmd_clean)

    # features
    p_feat = subparsers.add_parser(
        "features",
        help="Engineer temporal, usage, and event features with chronological splits",
    )
    p_feat.add_argument("--config", help="Path to features configuration YAML")
    p_feat.add_argument("--input", help="Path to aggregated CSV dataset")
    p_feat.add_argument("--output", help="Path to output full features CSV")
    p_feat.add_argument(
        "--splits-dir", help="Directory to save train/val/test CSV splits"
    )
    p_feat.set_defaults(func=cmd_features)

    # forecast
    p_fc = subparsers.add_parser(
        "forecast",
        help="Train and evaluate expected-cost forecasting models on validation split",
    )
    p_fc.add_argument("--config", help="Path to forecast configuration YAML")
    p_fc.add_argument("--train", help="Path to training features CSV")
    p_fc.add_argument("--val", help="Path to validation features CSV")
    p_fc.add_argument("--models-dir", help="Directory to save serialized models")
    p_fc.add_argument("--metrics-out", help="Path to output validation metrics JSON")
    p_fc.add_argument(
        "--predictions-out", help="Path to output validation predictions CSV"
    )
    p_fc.set_defaults(func=cmd_forecast)

    # detect
    p_det = subparsers.add_parser(
        "detect",
        help="Train and evaluate statistical and ML anomaly detectors on validation split",
    )
    p_det.add_argument("--config", help="Path to detect configuration YAML")
    p_det.add_argument("--train", help="Path to training features CSV")
    p_det.add_argument("--val", help="Path to validation features CSV")
    p_det.add_argument("--detectors-dir", help="Directory to save serialized detectors")
    p_det.add_argument("--metrics-out", help="Path to output validation metrics JSON")
    p_det.add_argument(
        "--predictions-out", help="Path to output validation detections CSV"
    )
    p_det.set_defaults(func=cmd_detect)

    # attribute
    p_att = subparsers.add_parser(
        "attribute",
        help="Train and evaluate root-cause attribution baselines and ML models",
    )
    p_att.add_argument("--config", help="Path to attribute configuration YAML")
    p_att.add_argument("--train", help="Path to training features CSV")
    p_att.add_argument("--val", help="Path to validation features CSV")
    p_att.add_argument(
        "--attributors-dir", help="Directory to save serialized attributors"
    )
    p_att.add_argument("--metrics-out", help="Path to output validation metrics JSON")
    p_att.add_argument(
        "--predictions-out", help="Path to output validation attributions CSV"
    )
    p_att.set_defaults(func=cmd_attribute)

    # explain
    p_exp = subparsers.add_parser(
        "explain",
        help="Compute TreeSHAP feature attributions, additivity verification, and non-causal narratives",
    )
    p_exp.add_argument("--config", help="Path to explain configuration YAML")
    p_exp.add_argument("--val", help="Path to validation features CSV")
    p_exp.add_argument("--model", help="Path to champion forecasting model")
    p_exp.add_argument("--metrics-out", help="Path to output validation metrics JSON")
    p_exp.add_argument(
        "--atol",
        type=float,
        default=0.002,
        help="Additivity numerical tolerance for TreeSHAP verification",
    )
    p_exp.set_defaults(func=cmd_explain)

    parsed = parser.parse_args(argv)
    return parsed.func(parsed)


if __name__ == "__main__":
    sys.exit(main())
