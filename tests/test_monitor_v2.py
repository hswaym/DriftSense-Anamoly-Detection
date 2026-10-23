"""Comprehensive unit and integration tests for DriftSense Monitoring & Governance (Phase 13).

Validates Acceptance Criteria:
- A13.1: Feedback API and metrics calculation with strict segregation from synthetic data.
- A13.2: Drift monitors with synthetic schema and volume distribution shifts.
- A13.3: Model registry integrity and SHA-256 fingerprinting.
- A13.4: Anti-online-retraining invariant enforcement in production.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from driftsense.monitor.alert_volume import AlertVolumeMonitor
from driftsense.monitor.data_drift import SchemaDriftMonitor, VolumeDriftMonitor
from driftsense.monitor.feedback_metrics import compute_feedback_metrics
from driftsense.monitor.feedback_store import FeedbackRecord, FeedbackStore
from driftsense.monitor.registry import ModelRegistry
from services.api.main import app

client = TestClient(app)


def test_feedback_store_and_segregation(tmp_path):
    """A13.1 Verify feedback store operations and human vs synthetic segregation."""
    store = FeedbackStore(storage_dir=tmp_path)

    # 1. Reject synthetic flag on human feedback record
    with pytest.raises(ValueError, match="Segregation invariant violation"):
        FeedbackRecord(
            feedback_id="fb_bad",
            anomaly_id="anom_1",
            analysis_id="anl_1",
            tenant_id="tenant_1",
            service_name="AmazonEC2",
            severity="Critical",
            timestamp_alert="2026-03-14T03:00:00Z",
            timestamp_feedback="2026-03-14T03:30:00Z",
            feedback_label="USEFUL",
            is_synthetic=True,
        )

    # 2. Record valid human feedback
    r1 = store.record_feedback(
        anomaly_id="anom_1",
        analysis_id="anl_1",
        tenant_id="t1",
        service_name="AmazonEC2",
        severity="Critical",
        timestamp_alert="2026-03-14T03:00:00Z",
        feedback_label="USEFUL",
        timestamp_feedback="2026-03-14T03:15:00Z",  # 900 seconds
    )
    assert not r1.is_synthetic
    assert r1.time_to_acknowledge_seconds == 900.0

    r2 = store.record_feedback(
        anomaly_id="anom_2",
        analysis_id="anl_1",
        tenant_id="t1",
        service_name="AmazonRDS",
        severity="High",
        timestamp_alert="2026-03-14T04:00:00Z",
        feedback_label="NOT_AN_ISSUE",
        timestamp_feedback="2026-03-14T04:10:00Z",  # 600 seconds
    )

    r3 = store.record_feedback(
        anomaly_id="anom_3",
        analysis_id="anl_1",
        tenant_id="t1",
        service_name="AmazonS3",
        severity="Medium",
        timestamp_alert="2026-03-14T05:00:00Z",
        feedback_label="PLANNED",
        timestamp_feedback="2026-03-14T05:05:00Z",  # 300 seconds
    )

    records = store.get_records(tenant_id="t1")
    assert len(records) == 3

    # 3. Compute metrics
    report = compute_feedback_metrics(records)
    assert report.total_feedback_count == 3
    assert report.usefulness_rate_pct == round(100.0 / 3.0, 1)  # 33.3%
    assert report.dismissal_rate_pct == round(100.0 / 3.0, 1)  # 33.3%
    assert report.planned_rate_pct == round(100.0 / 3.0, 1)  # 33.3%
    assert report.median_acknowledge_latency_seconds == 600.0
    assert report.dismissal_rate_by_severity["High"] == 100.0
    assert report.dismissal_rate_by_severity["Critical"] == 0.0


def test_schema_drift_monitor():
    """A13.2 Verify schema drift detector against FOCUS 1.0."""
    monitor = SchemaDriftMonitor()

    # Valid DataFrame
    df_valid = pd.DataFrame({
        "ChargePeriodStart": ["2026-03-01T00:00:00Z"],
        "ServiceName": ["AmazonEC2"],
        "EffectiveCost": [100.50],
        "BilledCost": [100.50],
        "UsageQuantity": [10],
    })
    rep_valid = monitor.inspect_schema(df_valid)
    assert not rep_valid.is_drift_detected
    assert rep_valid.risk_level == "Low"

    # Missing required column
    df_missing = pd.DataFrame({
        "ServiceName": ["AmazonEC2"],
        "EffectiveCost": [100.50],
    })
    rep_missing = monitor.inspect_schema(df_missing)
    assert rep_missing.is_drift_detected
    assert "ChargePeriodStart" in rep_missing.missing_required_columns
    assert rep_missing.risk_level == "High"


def test_volume_and_distribution_drift_monitor():
    """A13.2 Verify volume and statistical cost distribution shift detection."""
    monitor = VolumeDriftMonitor(volume_shift_threshold=0.40, ks_alpha=0.01)

    baseline = np.random.normal(loc=100.0, scale=10.0, size=300)
    # Similar distribution
    current_normal = np.random.normal(loc=101.0, scale=10.0, size=300)
    rep_normal = monitor.inspect_volume(current_normal, baseline)
    assert not rep_normal.is_drift_detected

    # Shifted distribution
    current_drifted = np.random.normal(loc=180.0, scale=30.0, size=300)
    rep_drifted = monitor.inspect_volume(current_drifted, baseline)
    assert rep_drifted.is_drift_detected
    assert rep_drifted.is_distribution_drift
    assert rep_drifted.ks_pvalue < 0.01


def test_alert_volume_and_fatigue_monitor():
    """A13.2 Verify alert fatigue and alert volume storm detection."""
    monitor = AlertVolumeMonitor(alert_fatigue_multiplier=3.0, min_critical_spike_count=10)

    # Normal rate
    rep_normal = monitor.inspect_alert_volume(current_window_count=6, historical_window_counts=[5, 6, 7, 5])
    assert not rep_normal.is_alert_storm_detected
    assert rep_normal.risk_level == "Normal"

    # Storm rate (4x surge)
    rep_storm = monitor.inspect_alert_volume(current_window_count=24, historical_window_counts=[5, 6, 7, 5])
    assert rep_storm.is_alert_storm_detected
    assert rep_storm.risk_level == "Critical_Alert_Storm"
    assert "Alert Fatigue Warning" in (rep_storm.actionable_warning or "")


def test_model_registry_integrity_and_anti_retraining_guard(tmp_path):
    """A13.3 & A13.4 Verify model registry integrity and anti-online-retraining invariant."""
    reg = ModelRegistry(registry_path=tmp_path / "registry.json")
    assert reg.verify_integrity()
    assert "forecaster_xgb_champion" in reg.models

    card = reg.models["forecaster_xgb_champion"]
    assert card.allow_online_retraining is False
    assert len(card.sha256_hash) == 64

    # A13.4: Rejects unauthorized online retraining attempts
    with pytest.raises(RuntimeError, match="A13.4 Invariant Violation"):
        reg.guard_against_online_retraining(allow_explicit_flag=False)

    # Allowed only with explicit offline authorization flag
    reg.guard_against_online_retraining(allow_explicit_flag=True)


def test_admin_governance_api_endpoints():
    """A13.1 & A13.4 Test admin monitoring and governance endpoints."""
    headers = {"X-Tenant-ID": "tenant_gov_test"}

    # 1. Summary before feedback
    res_sum = client.get("/admin/feedback/summary", headers=headers)
    assert res_sum.status_code == 200
    assert "usefulness_rate_pct" in res_sum.json()

    # 2. Drift status
    res_drift = client.get("/admin/drift/status", headers=headers)
    assert res_drift.status_code == 200
    assert "alert_volume_monitor" in res_drift.json()

    # 3. Model registry
    res_reg = client.get("/admin/models/registry", headers=headers)
    assert res_reg.status_code == 200
    data = res_reg.json()
    assert data["status"] == "FROZEN_REPRODUCIBLE"
    assert data["registry_integrity_valid"] is True
    assert "forecaster_xgb_champion" in data["models"]

    # 4. Attempt unauthorized online retrain -> 403 Forbidden (A13.4)
    res_retrain = client.post("/admin/retrain/attempt?allow_explicit_flag=false", headers=headers)
    assert res_retrain.status_code == 403
    assert "Automatic online retraining in production is strictly forbidden" in res_retrain.json()["detail"]
