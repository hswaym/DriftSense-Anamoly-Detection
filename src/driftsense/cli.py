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

    parsed = parser.parse_args(argv)
    return parsed.func(parsed)


if __name__ == "__main__":
    sys.exit(main())
