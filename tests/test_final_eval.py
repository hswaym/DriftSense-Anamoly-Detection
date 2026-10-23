"""Unit and integration tests for Phase 13 final evaluation and cryptographic hash guard."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from driftsense.eval.final import (
    FROZEN_CONFIG_HASHES,
    HashGuardError,
    assert_config_hashes_frozen,
    compute_bootstrap_ci,
    evaluate_final_test_set,
    evaluate_holdout_partition,
    verify_config_hashes,
)


def test_hash_guard_passes_on_frozen_configs():
    """A13.1: Verify cryptographic hash guard passes against repository configs."""
    is_valid, errors = verify_config_hashes()
    assert is_valid, f"Hash guard failed with errors: {errors}"
    assert len(errors) == 0


def test_hash_guard_detects_tampering(tmp_path: Path):
    """A13.1: Verify hash guard detects modified config file and raises HashGuardError."""
    # Create a mock config directory with one tampered file
    fake_configs = tmp_path / "configs"
    fake_configs.mkdir()

    test_hashes = {}
    for rel_path, h in FROZEN_CONFIG_HASHES.items():
        fname = Path(rel_path).name
        c_file = fake_configs / fname
        c_file.write_text("dummy: true\n", encoding="utf-8")
        test_hashes[f"configs/{fname}"] = h

    # Check verification reports mismatches
    is_valid, errors = verify_config_hashes(
        expected_hashes=test_hashes, base_dir=tmp_path
    )
    assert not is_valid
    assert len(errors) > 0

    with pytest.raises(HashGuardError, match="A13.1 Hash Guard Violation"):
        assert_config_hashes_frozen(expected_hashes=test_hashes, base_dir=tmp_path)


@pytest.fixture
def tiny_train_and_test_data() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Generate tiny synthetic train and test DataFrames for final eval testing."""
    dates_train = pd.date_range("2024-09-01 00:00:00", periods=72, freq="h", tz="UTC")
    dates_test = pd.date_range("2024-09-25 00:00:00", periods=24, freq="h", tz="UTC")

    records_train = []
    for svc in ["Compute", "Storage"]:
        for idx, d in enumerate(dates_train):
            cost = 2.0 + np.sin(d.hour) + (0.5 if svc == "Compute" else 0.1)
            records_train.append(
                {
                    "Id": f"tr_{idx}",
                    "ChargePeriodStart": d.strftime("%Y-%m-%d %H:%M:%S"),
                    "ServiceName": svc,
                    "EffectiveCost": cost,
                    "ConsumedQuantity": cost * 10.0,
                    "hour_of_day": d.hour,
                    "day_of_week": d.dayofweek,
                    "lag_1": cost * 0.98,
                    "lag_2": cost * 0.95,
                    "roll_mean_6": cost * 0.99,
                }
            )

    records_test = []
    for svc in ["Compute", "Storage"]:
        for idx, d in enumerate(dates_test):
            cost = 2.0 + np.sin(d.hour) + (0.5 if svc == "Compute" else 0.1)
            records_test.append(
                {
                    "Id": f"ts_{idx}",
                    "ChargePeriodStart": d.strftime("%Y-%m-%d %H:%M:%S"),
                    "ServiceName": svc,
                    "EffectiveCost": cost,
                    "ConsumedQuantity": cost * 10.0,
                    "hour_of_day": d.hour,
                    "day_of_week": d.dayofweek,
                    "lag_1": cost * 0.98,
                    "lag_2": cost * 0.95,
                    "roll_mean_6": cost * 0.99,
                }
            )

    return pd.DataFrame(records_train), pd.DataFrame(records_test)


def test_final_eval_one_time_guard(tiny_train_and_test_data, tmp_path: Path):
    """A13.2: Verify final evaluation refuses to re-run on already evaluated test manifest."""
    df_train, df_test = tiny_train_and_test_data
    out_dir = tmp_path / "test_run"

    # Pre-create manifest with test_evaluated = True
    out_dir.mkdir()
    manifest_path = out_dir / "manifest.json"
    manifest_path.write_text(json.dumps({"test_evaluated": True}), encoding="utf-8")

    # Must raise RuntimeError without override
    with pytest.raises(
        RuntimeError,
        match="A13.2 Violation: Test partition has already been evaluated once",
    ):
        evaluate_final_test_set(
            df_train=df_train,
            df_test=df_test,
            output_dir=out_dir,
            verify_hashes=False,
            allow_override=False,
        )

    # With override, succeeds
    res = evaluate_final_test_set(
        df_train=df_train,
        df_test=df_test,
        output_dir=out_dir,
        verify_hashes=False,
        allow_override=True,
    )
    assert "forecast" in res
    assert "detection" in res
    assert "attribution" in res
    assert "explainability" in res


def test_final_eval_execution_on_fixtures(tiny_train_and_test_data, tmp_path: Path):
    """Verify complete final evaluation execution, metric computation, and artifact generation."""
    df_train, df_test = tiny_train_and_test_data
    out_dir = tmp_path / "final_eval_artifacts"

    results = evaluate_final_test_set(
        df_train=df_train,
        df_test=df_test,
        output_dir=out_dir,
        seeds=[42, 123],
        atol_shap=0.005,
        verify_hashes=True,
    )

    # Check payload keys
    assert results["evaluation_phase"] == "PHASE_13"
    assert "xgboost_champion" in results["forecast"]
    assert "clean_track" in results["detection"]
    assert "synthetic_track" in results["detection"]
    assert "champion_correlation" in results["attribution"]
    assert results["explainability"]["additivity_verified"] is True

    # Check generated files
    assert (out_dir / "final_test_results.json").is_file()
    assert (out_dir / "test_forecast_and_alerts.csv").is_file()
    assert (out_dir / "test_shap_importance.csv").is_file()
    assert (out_dir / "test_audit_narratives.md").is_file()
    assert (out_dir / "manifest.json").is_file()

    # Check manifest content
    with open(out_dir / "manifest.json", encoding="utf-8") as f:
        manifest = json.load(f)
    assert manifest.get("test_evaluated") is True
    assert manifest.get("phase") == "PHASE_13"


def test_compute_bootstrap_ci():
    """Verify empirical bootstrap confidence interval computation."""
    y_true = np.array([10.0, 20.0, 30.0, 40.0, 50.0])
    y_pred = np.array([11.0, 19.0, 29.0, 42.0, 48.0])

    def dummy_metric(yt, yp):
        return float(np.mean(np.abs(yt - yp)))

    ci = compute_bootstrap_ci(dummy_metric, y_true, y_pred, n_bootstraps=200, ci_level=0.95, seed=42)
    assert "mean" in ci
    assert "ci_lower" in ci
    assert "ci_upper" in ci
    assert ci["ci_lower"] <= ci["mean"] <= ci["ci_upper"]


def test_holdout_evaluation_one_time_guard(tiny_train_and_test_data, tmp_path: Path):
    """A15.2: Verify holdout evaluation refuses re-execution if manifest has holdout_touched=True."""
    df_train, df_holdout = tiny_train_and_test_data
    out_dir = tmp_path / "holdout_run"
    out_dir.mkdir()
    manifest_path = out_dir / "manifest.json"
    manifest_path.write_text(json.dumps({"holdout_touched": True}), encoding="utf-8")

    with pytest.raises(
        RuntimeError,
        match="A15.2 Invariant Violation: Quarantined holdout partition has already been evaluated once",
    ):
        evaluate_holdout_partition(
            df_train=df_train,
            df_holdout=df_holdout,
            output_dir=out_dir,
            verify_hashes=False,
            allow_override=False,
        )

    # Allowed with explicit override
    res = evaluate_holdout_partition(
        df_train=df_train,
        df_holdout=df_holdout,
        output_dir=out_dir,
        verify_hashes=False,
        allow_override=True,
    )
    assert res["evaluation_phase"] == "PHASE_15"
    assert res["holdout_partition"]["holdout_touched"] is True


def test_holdout_evaluation_generates_five_tables(tiny_train_and_test_data, tmp_path: Path):
    """Verify Phase 15 evaluation produces all 5 required scientific tables and signed manifest."""
    df_train, df_holdout = tiny_train_and_test_data
    out_dir = tmp_path / "phase15_holdout_artifacts"

    results = evaluate_holdout_partition(
        df_train=df_train,
        df_holdout=df_holdout,
        output_dir=out_dir,
        seeds=[707, 808],
        verify_hashes=True,
    )

    # 1. Verify 5 distinct tables
    assert "table1_real_billing" in results
    assert "table2_external_benchmarks" in results
    assert "table3_synthetic_attribution" in results
    assert "table4_cross_dataset" in results
    assert "table5_v1_vs_v2_comparison" in results

    # 2. Verify v1 is marked 'development-contaminated'
    v1_v2 = results["table5_v1_vs_v2_comparison"]
    assert "Contaminated" in v1_v2["forecast_wape"]["v1_contaminated"]

    # 3. Verify files generated
    assert (out_dir / "holdout_results.json").is_file()
    assert (out_dir / "holdout_predictions.csv").is_file()
    assert (out_dir / "holdout_results_tables.md").is_file()
    assert (out_dir / "manifest.json").is_file()

    # 4. Verify manifest has holdout_touched=True and PHASE_15
    with open(out_dir / "manifest.json", encoding="utf-8") as f:
        manifest = json.load(f)
    assert manifest.get("holdout_touched") is True
    assert manifest.get("phase") == "PHASE_15"

