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
    is_valid, errors = verify_manifest(manifest_target)
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
    p_vm.set_defaults(func=cmd_verify_manifest)

    parsed = parser.parse_args(argv)
    return parsed.func(parsed)


if __name__ == "__main__":
    sys.exit(main())
