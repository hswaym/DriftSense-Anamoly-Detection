"""Unit tests for Phase 11 dashboard data loaders (app/loaders.py)."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from app.loaders import (
    find_latest_run_for_phase,
    get_default_runs_dir,
    list_available_runs,
    load_ablation_data,
    load_attributions_data,
    load_detections_data,
    load_explainability_data,
    load_pipeline_state,
    load_run_manifest,
)


def test_no_hardcoded_absolute_paths():
    """Verify that loaders module does not use any hardcoded absolute filesystem paths (A11.3)."""
    p = Path("app/loaders.py")
    text = p.read_text(encoding="utf-8")
    assert "C:\\" not in text
    assert "/Users/" not in text
    assert "/home/" not in text
    assert get_default_runs_dir() == Path("runs")


def test_list_available_runs_empty_or_missing(tmp_path):
    """Test loader handles non-existent or empty directories gracefully without errors."""
    missing = tmp_path / "does_not_exist"
    assert list_available_runs(missing) == []

    empty = tmp_path / "empty_dir"
    empty.mkdir()
    assert list_available_runs(empty) == []


def test_load_run_manifest_corrupted(tmp_path):
    """Test corrupted or invalid manifest.json produces clean error dictionary instead of traceback."""
    run_dir = tmp_path / "run_corrupt"
    run_dir.mkdir()
    manifest = run_dir / "manifest.json"
    manifest.write_text("{corrupt json", encoding="utf-8")

    res = load_run_manifest(run_dir)
    assert res["valid"] is False
    assert "error" in res


def test_load_detections_data_missing_and_corrupt(tmp_path):
    """Test detections loader handles missing and corrupted files gracefully."""
    # Missing
    df, err = load_detections_data(tmp_path)
    assert df.empty
    assert err is not None

    # Corrupt
    corrupt_dir = tmp_path / "corrupt_run"
    corrupt_dir.mkdir()
    (corrupt_dir / "val_detections.csv").write_text(
        "invalid,csv\n1,2,3,4,extra", encoding="utf-8"
    )
    df2, _err2 = load_detections_data(corrupt_dir)
    # Pandas parser may either parse with warning or error; must not raise uncaught exception
    assert isinstance(df2, pd.DataFrame)


def test_load_attributions_data_missing(tmp_path):
    """Test attributions loader returns empty DataFrame on missing files."""
    df, err = load_attributions_data(tmp_path)
    assert df.empty
    assert err is not None
    assert "not found" in err.lower()


def test_load_explainability_data_missing(tmp_path):
    """Test explainability loader returns empty structures with message when files missing."""
    df_imp, metrics, narr, msg = load_explainability_data(tmp_path)
    assert df_imp.empty
    assert metrics == {}
    assert narr == ""
    assert msg is not None


def test_load_ablation_data_missing(tmp_path):
    """Test ablation loader returns empty structures with message when files missing."""
    df_sum, metrics, notes, msg = load_ablation_data(tmp_path)
    assert df_sum.empty
    assert metrics == {}
    assert notes == ""
    assert msg is not None


def test_real_workspace_runs_discovery():
    """Verify discovery works against actual repository runs directory if present."""
    runs_dir = Path("runs")
    if runs_dir.is_dir():
        runs = list_available_runs("runs")
        assert len(runs) >= 4

        # Check phase lookup
        p10_run = find_latest_run_for_phase("PHASE_10", "runs")
        assert p10_run is not None
        assert p10_run.is_dir()

        # Check pipeline state
        state = load_pipeline_state("runs")
        assert state["phase_10_run"] is not None
