"""Artifact and telemetry loaders for the DriftSense FinOps Dashboard (Phase 11).

Strictly adheres to Phase 11 invariants:
- Reads exported artifacts only. No model training or pipeline execution.
- Handles missing, empty, or corrupt files gracefully with user-facing error messages, never unhandled tracebacks.
- Never uses hardcoded absolute paths (A11.3).
- Uses non-causal terminology: "likely associated causes", scores labelled "model evidence".
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import pandas as pd

logger = logging.getLogger(__name__)


def get_default_runs_dir() -> Path:
    """Return relative path to runs directory without hardcoded absolute paths (A11.3)."""
    return Path("runs")


def list_available_runs(runs_dir: str | Path = "runs") -> list[dict[str, Any]]:
    """Scan the runs directory and extract metadata for all verified runs."""
    base_dir = Path(runs_dir)
    if not base_dir.is_dir():
        logger.warning("Runs directory does not exist: %s", base_dir)
        return []

    runs = []
    for p in sorted(base_dir.iterdir(), reverse=True):
        if not p.is_dir() or p.name.startswith("."):
            continue

        manifest_path = p / "manifest.json"
        manifest_data: dict[str, Any] = {}
        if manifest_path.is_file():
            try:
                with open(manifest_path, "r", encoding="utf-8") as f:
                    manifest_data = json.load(f)
            except Exception as e:
                logger.warning("Failed to parse manifest at %s: %e", manifest_path, e)

        phase = manifest_data.get("phase", "UNKNOWN")
        stage = manifest_data.get("stage", "unknown")
        timestamp = manifest_data.get(
            "finished_utc", manifest_data.get("started_utc", "")
        )
        commit = manifest_data.get("git_commit", "unknown")[:7]

        # Inventory available files
        files = [f.name for f in p.glob("*") if f.is_file()]

        runs.append(
            {
                "run_id": p.name,
                "path": str(p),
                "phase": phase,
                "stage": stage,
                "timestamp": timestamp,
                "git_commit": commit,
                "manifest_present": bool(manifest_data),
                "files": files,
            }
        )

    return runs


def find_latest_run_for_phase(phase: str, runs_dir: str | Path = "runs") -> Path | None:
    """Locate the most recent run directory corresponding to a specific phase."""
    runs = list_available_runs(runs_dir)
    for r in runs:
        if r["phase"] == phase:
            return Path(r["path"])
    return None


def load_run_manifest(run_dir: str | Path) -> dict[str, Any]:
    """Safely load manifest.json from a run directory."""
    path = Path(run_dir) / "manifest.json"
    if not path.is_file():
        return {"error": f"Manifest not found in '{run_dir}'", "valid": False}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            data["valid"] = True
            return data
    except Exception as e:
        logger.error("Error reading manifest %s: %s", path, e)
        return {"error": f"Corrupt manifest.json: {e}", "valid": False}


def load_detections_data(
    run_dir: str | Path | None = None,
) -> tuple[pd.DataFrame, str | None]:
    """Safely load anomaly detection predictions."""
    target_dir: Path | None = (
        Path(run_dir) if run_dir else find_latest_run_for_phase("PHASE_7")
    )
    if target_dir is None:
        target_dir = find_latest_run_for_phase("PHASE_8")
    if target_dir is None:
        return (
            pd.DataFrame(),
            "No Phase 7 or Phase 8 detection runs available in runs/.",
        )

    path = target_dir / "val_detections.csv"
    if not path.is_file():
        return pd.DataFrame(), f"Detections file not found at '{path}'."

    try:
        df = pd.read_csv(path, low_memory=False)
        if df.empty:
            return df, f"Detections file at '{path}' is empty."
        if "ChargePeriodStart" in df.columns:
            df["ChargePeriodStart"] = pd.to_datetime(df["ChargePeriodStart"], utc=True)
        return df, None
    except Exception as e:
        logger.error("Failed to read detections from %s: %s", path, e)
        return pd.DataFrame(), f"Corrupt detections file at '{path}': {e}"


def load_attributions_data(
    run_dir: str | Path | None = None,
) -> tuple[pd.DataFrame, str | None]:
    """Safely load root-cause attribution predictions."""
    target_dir: Path | None = (
        Path(run_dir) if run_dir else find_latest_run_for_phase("PHASE_8")
    )
    if target_dir is None:
        return pd.DataFrame(), "No Phase 8 attribution runs available in runs/."

    path = target_dir / "val_attributions.csv"
    if not path.is_file():
        return pd.DataFrame(), f"Attributions file not found at '{path}'."

    try:
        df = pd.read_csv(path, low_memory=False)
        if df.empty:
            return df, f"Attributions file at '{path}' is empty."
        if "start_timestamp" in df.columns:
            df["start_timestamp"] = pd.to_datetime(df["start_timestamp"], utc=True)
        return df, None
    except Exception as e:
        logger.error("Failed to read attributions from %s: %s", path, e)
        return pd.DataFrame(), f"Corrupt attributions file at '{path}': {e}"


def load_explainability_data(
    run_dir: str | Path | None = None,
) -> tuple[pd.DataFrame, dict[str, Any], str, str | None]:
    """Safely load global feature importance, metrics, and narrative markdown."""
    target_dir: Path | None = (
        Path(run_dir) if run_dir else find_latest_run_for_phase("PHASE_9")
    )
    if target_dir is None:
        return (
            pd.DataFrame(),
            {},
            "",
            "No Phase 9 explainability runs available in runs/.",
        )

    imp_path = target_dir / "global_feature_importance.csv"
    metrics_path = target_dir / "val_explain_metrics.json"
    narr_path = target_dir / "val_narratives.md"

    df_imp = pd.DataFrame()
    metrics: dict[str, Any] = {}
    narratives = ""

    msg = None
    if imp_path.is_file():
        try:
            df_imp = pd.read_csv(imp_path)
        except Exception as e:
            logger.warning("Error reading %s: %s", imp_path, e)

    if metrics_path.is_file():
        try:
            with open(metrics_path, "r", encoding="utf-8") as f:
                metrics = json.load(f)
        except Exception as e:
            logger.warning("Error reading %s: %s", metrics_path, e)

    if narr_path.is_file():
        try:
            narratives = narr_path.read_text(encoding="utf-8")
        except Exception as e:
            logger.warning("Error reading %s: %s", narr_path, e)

    if df_imp.empty and not metrics and not narratives:
        msg = f"No explainability artifacts could be loaded from '{target_dir}'."

    return df_imp, metrics, narratives, msg


def load_ablation_data(
    run_dir: str | Path | None = None,
) -> tuple[pd.DataFrame, dict[str, Any], str, str | None]:
    """Safely load ablation summary table, metrics, and scientific notes."""
    target_dir: Path | None = (
        Path(run_dir) if run_dir else find_latest_run_for_phase("PHASE_10")
    )
    if target_dir is None:
        return (
            pd.DataFrame(),
            {},
            "",
            "No Phase 10 controlled experiments runs available in runs/.",
        )

    summary_path = target_dir / "ablation_summary.csv"
    metrics_path = target_dir / "ablation_metrics.json"
    notes_path = target_dir / "protocol_notes.md"

    df_summary = pd.DataFrame()
    metrics: dict[str, Any] = {}
    notes = ""

    msg = None
    if summary_path.is_file():
        try:
            df_summary = pd.read_csv(summary_path)
        except Exception as e:
            logger.warning("Error reading %s: %s", summary_path, e)

    if metrics_path.is_file():
        try:
            with open(metrics_path, "r", encoding="utf-8") as f:
                metrics = json.load(f)
        except Exception as e:
            logger.warning("Error reading %s: %s", metrics_path, e)

    if notes_path.is_file():
        try:
            notes = notes_path.read_text(encoding="utf-8")
        except Exception as e:
            logger.warning("Error reading %s: %s", notes_path, e)

    if df_summary.empty and not metrics:
        msg = f"No ablation artifacts could be loaded from '{target_dir}'."

    return df_summary, metrics, notes, msg


def load_pipeline_state(runs_dir: str | Path = "runs") -> dict[str, Any]:
    """Assemble verified latest artifacts across all completed phases into a single state bundle."""
    return {
        "runs": list_available_runs(runs_dir),
        "phase_6_run": find_latest_run_for_phase("PHASE_6", runs_dir),
        "phase_7_run": find_latest_run_for_phase("PHASE_7", runs_dir),
        "phase_8_run": find_latest_run_for_phase("PHASE_8", runs_dir),
        "phase_9_run": find_latest_run_for_phase("PHASE_9", runs_dir),
        "phase_10_run": find_latest_run_for_phase("PHASE_10", runs_dir),
    }
