"""Execution manifest builder and verification according to G5 specification."""

from __future__ import annotations

import datetime
import importlib.metadata
import json
import platform
import subprocess
from pathlib import Path
from typing import Any

from driftsense.runtime.config import compute_file_sha256
from driftsense.runtime.hardware import check_hardware


def get_git_info() -> tuple[str, bool]:
    """Retrieve current git commit SHA and dirty working tree status."""
    try:
        commit = (
            subprocess.check_output(
                ["git", "rev-parse", "HEAD"], stderr=subprocess.DEVNULL
            )
            .decode("utf-8")
            .strip()
        )
        status = (
            subprocess.check_output(
                ["git", "status", "--porcelain"], stderr=subprocess.DEVNULL
            )
            .decode("utf-8")
            .strip()
        )
        return commit, len(status) > 0
    except (subprocess.SubprocessError, FileNotFoundError, OSError):
        return "unknown", False


def get_installed_packages(package_names: list[str] | None = None) -> dict[str, str]:
    """Collect versions of key packages."""
    if package_names is None:
        package_names = [
            "pandas",
            "numpy",
            "scikit-learn",
            "xgboost",
            "lightgbm",
            "shap",
            "pyyaml",
            "requests",
            "pydantic",
            "psutil",
        ]
    pkgs = {}
    for name in package_names:
        try:
            pkgs[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            pass
    return pkgs


class ManifestBuilder:
    """Builder for constructing G5-compliant run manifests."""

    def __init__(
        self,
        run_id: str,
        phase: str,
        stage: str,
        config_path: str,
        config_sha256: str,
        seed: int,
        dataset_ids: list[str] | None = None,
    ) -> None:
        self.run_id = run_id
        self.phase = phase
        self.stage = stage
        self.config_path = config_path
        self.config_sha256 = config_sha256
        self.seed = seed
        self.dataset_ids = dataset_ids or []
        self.dataset_sha256: dict[str, str] = {}
        self.artifacts: list[dict[str, Any]] = []
        self.metrics_files: list[str] = []
        self.started_utc = datetime.datetime.now(datetime.timezone.utc).isoformat()
        self.hardware = check_hardware()
        self.git_commit, self.git_dirty = get_git_info()

    def register_dataset_file(self, file_path: str | Path) -> str:
        """Register a dataset file, computing its SHA256 checksum."""
        path = Path(file_path)
        sha = compute_file_sha256(path)
        self.dataset_sha256[path.as_posix()] = sha
        return sha

    def add_artifact(self, file_path: str | Path) -> dict[str, Any]:
        """Record an output artifact with sha256 checksum and byte size."""
        path = Path(file_path)
        if not path.is_file():
            raise FileNotFoundError(f"Artifact does not exist: {path}")
        sha = compute_file_sha256(path)
        size_bytes = path.stat().st_size
        entry = {
            "path": path.as_posix(),
            "sha256": sha,
            "bytes": size_bytes,
        }
        self.artifacts.append(entry)
        return entry

    def add_metrics_file(self, file_path: str | Path) -> None:
        """Register a metrics file."""
        path = Path(file_path)
        self.add_artifact(path)
        self.metrics_files.append(path.as_posix())

    def build(self) -> dict[str, Any]:
        """Finalize manifest dictionary."""
        finished_utc = datetime.datetime.now(datetime.timezone.utc).isoformat()
        return {
            "run_id": self.run_id,
            "phase": self.phase,
            "stage": self.stage,
            "git_commit": self.git_commit,
            "git_dirty": self.git_dirty,
            "config_path": str(self.config_path),
            "config_sha256": self.config_sha256,
            "seed": self.seed,
            "python": platform.python_version(),
            "packages": get_installed_packages(),
            "hardware": {
                "cpu": self.hardware.get("cpu"),
                "gpu": self.hardware.get("gpu"),
                "ram_gb": self.hardware.get("ram_gb"),
            },
            "dataset_ids": self.dataset_ids,
            "dataset_sha256": self.dataset_sha256,
            "started_utc": self.started_utc,
            "finished_utc": finished_utc,
            "artifacts": self.artifacts,
            "metrics_files": self.metrics_files,
        }

    def save(self, destination: str | Path) -> Path:
        """Save finalized manifest JSON to target file or directory."""
        dest = Path(destination)
        if dest.is_dir() or not dest.suffix:
            dest.mkdir(parents=True, exist_ok=True)
            output_file = dest / "manifest.json"
        else:
            dest.parent.mkdir(parents=True, exist_ok=True)
            output_file = dest

        data = self.build()
        with output_file.open("w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, sort_keys=True)
        return output_file


def verify_manifest(manifest_path_or_dir: str | Path) -> tuple[bool, list[str]]:
    """Recomputes every hash and verifies artifacts in manifest.json.

    Returns:
        tuple[bool, list[str]]: (is_valid, list of error messages)
    """
    path = Path(manifest_path_or_dir)
    if path.is_dir():
        manifest_file = path / "manifest.json"
    else:
        manifest_file = path

    if not manifest_file.is_file():
        return False, [f"Manifest file not found: {manifest_file}"]

    try:
        with manifest_file.open("r", encoding="utf-8") as f:
            manifest = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        return False, [f"Failed to parse manifest JSON: {e}"]

    errors: list[str] = []

    # 1. Verify artifacts
    artifacts = manifest.get("artifacts", [])
    for art in artifacts:
        art_path_str = art.get("path")
        expected_sha = art.get("sha256")
        expected_bytes = art.get("bytes")

        if not art_path_str:
            errors.append("Artifact entry missing 'path' property.")
            continue

        art_path = Path(art_path_str)
        # Check direct path or path relative to manifest parent
        if not art_path.is_file():
            rel_path = manifest_file.parent / art_path.name
            if rel_path.is_file():
                art_path = rel_path
            else:
                errors.append(f"Artifact file not found: {art_path_str}")
                continue

        actual_bytes = art_path.stat().st_size
        if expected_bytes is not None and actual_bytes != expected_bytes:
            errors.append(
                f"Artifact size mismatch for {art_path}: expected {expected_bytes}, got {actual_bytes}"
            )

        actual_sha = compute_file_sha256(art_path)
        if expected_sha and actual_sha != expected_sha:
            errors.append(
                f"Artifact hash mismatch for {art_path}: expected {expected_sha}, got {actual_sha}"
            )

    # 2. Verify dataset hashes if recorded
    dataset_hashes = manifest.get("dataset_sha256", {})
    for ds_path_str, expected_ds_sha in dataset_hashes.items():
        ds_path = Path(ds_path_str)
        if not ds_path.is_file():
            rel_path = manifest_file.parent / ds_path.name
            if rel_path.is_file():
                ds_path = rel_path
            else:
                errors.append(
                    f"Dataset file recorded in manifest not found: {ds_path_str}"
                )
                continue

        actual_ds_sha = compute_file_sha256(ds_path)
        if actual_ds_sha != expected_ds_sha:
            errors.append(
                f"Dataset hash mismatch for {ds_path}: expected {expected_ds_sha}, got {actual_ds_sha}"
            )

    return len(errors) == 0, errors
