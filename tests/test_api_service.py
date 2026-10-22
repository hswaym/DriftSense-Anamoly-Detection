"""Comprehensive integration tests for DriftSense FastAPI service (Phase 11).

Tests:
1. Health check & Root endpoints
2. Multi-tenant isolation (Tenant A vs Tenant B access controls)
3. Upload safety & Magic-byte executable rejection
4. Upload -> Mapping -> Background Analysis -> Anomaly Detection -> Detail Briefing -> Feedback
5. CSV Export sanitization (Formula Injection Protection)
6. Operational Event registration
"""

from __future__ import annotations

import io
import pytest
from fastapi.testclient import TestClient

from services.api.database import db
from services.api.main import app

client = TestClient(app)

_sample_lines = [
    "ChargePeriodStart,ServiceName,BilledCost,EffectiveCost,UsageQuantity,RegionName,ChargeCategory"
]
for h in range(30):
    day = 1 + (h // 24)
    hr = h % 24
    _sample_lines.append(
        f"2026-03-{day:02d}T{hr:02d}:00:00Z,AmazonEC2,100.00,100.00,50,us-east-1,Usage"
    )
    _sample_lines.append(
        f"2026-03-{day:02d}T{hr:02d}:00:00Z,AmazonS3,40.00,40.00,200,us-east-1,Usage"
    )
# Massive spike on AmazonEC2
_sample_lines.append(
    "2026-03-02T07:00:00Z,AmazonEC2,1850.00,1850.00,1200,us-east-1,Usage"
)
SAMPLE_CSV = "\n".join(_sample_lines) + "\n"

_inj_lines = [
    "ChargePeriodStart,ServiceName,BilledCost,EffectiveCost,UsageQuantity,RegionName,ChargeCategory"
]
for h in range(30):
    day = 1 + (h // 24)
    hr = h % 24
    _inj_lines.append(
        f"2026-03-{day:02d}T{hr:02d}:00:00Z,AmazonEC2,100.00,100.00,50,us-east-1,Usage"
    )
# Injection spike
_inj_lines.append(
    "2026-03-02T07:00:00Z,=cmd|'/C calc'!A0,1950.00,1950.00,1200,us-east-1,Usage"
)
CSV_WITH_INJECTION = "\n".join(_inj_lines) + "\n"


@pytest.fixture(autouse=True)
def clean_database():
    """Reset database between tests."""
    with db._lock:
        db.uploads.clear()
        db.analyses.clear()
        db.anomalies.clear()
        db.events.clear()


def test_health_and_root():
    """Test health check and root endpoints."""
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json()["status"] == "healthy"

    res_root = client.get("/")
    assert res_root.status_code == 200
    assert res_root.json()["status"] == "operational"


def test_upload_safety_and_magic_byte_rejection():
    """Verify executable magic bytes and invalid extensions are strictly rejected."""
    headers = {"X-Tenant-ID": "tenant_alpha"}

    # 1. Reject invalid file extension
    bad_ext_res = client.post(
        "/uploads",
        files={"file": ("malicious.exe", b"MZDummyPayload", "application/octet-stream")},
        headers=headers,
    )
    assert bad_ext_res.status_code == 400
    assert "Unsupported file format" in bad_ext_res.json()["detail"]

    # 2. Reject executable disguised as CSV (Magic byte MZ)
    fake_csv_res = client.post(
        "/uploads",
        files={"file": ("fake.csv", b"MZ\x90\x00\x03\x00\x00\x00", "text/csv")},
        headers=headers,
    )
    assert fake_csv_res.status_code == 400
    assert "Executable or archive magic bytes detected" in fake_csv_res.json()["detail"]

    # 3. Reject ELF binary disguised as CSV
    fake_elf_res = client.post(
        "/uploads",
        files={"file": ("fake_linux.csv", b"\x7fELF\x02\x01\x01\x00", "text/csv")},
        headers=headers,
    )
    assert fake_elf_res.status_code == 400
    assert "Executable or archive magic bytes detected" in fake_elf_res.json()["detail"]


def test_tenant_isolation():
    """Ensure Tenant A cannot see, modify, or delete Tenant B's uploads or data."""
    headers_a = {"X-Tenant-ID": "tenant_alpha"}
    headers_b = {"X-Tenant-ID": "tenant_beta"}

    # Tenant Alpha uploads data
    res_up = client.post(
        "/uploads",
        files={"file": ("billing.csv", SAMPLE_CSV.encode("utf-8"), "text/csv")},
        headers=headers_a,
    )
    assert res_up.status_code == 201
    upload_id = res_up.json()["upload_id"]

    # Tenant Beta attempts to view Alpha's upload -> 404
    res_get_b = client.get(f"/uploads/{upload_id}", headers=headers_b)
    assert res_get_b.status_code == 404

    # Tenant Beta attempts to update mapping for Alpha's upload -> 404
    res_map_b = client.put(
        f"/uploads/{upload_id}/mapping",
        json={"column_mapping": {"BilledCost": "BilledCost"}},
        headers=headers_b,
    )
    assert res_map_b.status_code == 404

    # Tenant Beta attempts to delete Alpha's upload -> 404
    res_del_b = client.delete(f"/uploads/{upload_id}", headers=headers_b)
    assert res_del_b.status_code == 404

    # Tenant Alpha can access their own upload
    res_get_a = client.get(f"/uploads/{upload_id}", headers=headers_a)
    assert res_get_a.status_code == 200
    assert res_get_a.json()["upload_id"] == upload_id


def test_full_analysis_and_feedback_lifecycle():
    """Test full upload -> quality check -> analysis -> anomalies -> feedback workflow."""
    headers = {"X-Tenant-ID": "tenant_test"}

    # 1. Upload CSV
    res_up = client.post(
        "/uploads",
        files={"file": ("cloud_spend.csv", SAMPLE_CSV.encode("utf-8"), "text/csv")},
        headers=headers,
    )
    assert res_up.status_code == 201
    data = res_up.json()
    upload_id = data["upload_id"]
    assert data["detected_provider"] == "FOCUS"
    assert data["row_count_estimate"] >= 30

    # 2. Check Data Health Report
    res_health = client.get(f"/uploads/{upload_id}/health", headers=headers)
    assert res_health.status_code == 200
    health_data = res_health.json()
    assert health_data["health_score"] >= 90.0

    # 3. Add Operational Change Event
    res_evt = client.post(
        "/events",
        json={
            "event_id": "evt_deploy_1",
            "event_type": "DEPLOYMENT",
            "service_id": "AmazonEC2",
            "timestamp": "2026-03-01T02:30:00Z",
            "summary": "Production compute autoscaling fleet scale-up",
            "details": {},
        },
        headers=headers,
    )
    assert res_evt.status_code == 201

    # 4. Trigger Analysis
    res_anl = client.post(
        "/analyses",
        json={"upload_id": upload_id, "min_materiality_dollars": 10.0, "sensitivity": "Balanced"},
        headers=headers,
    )
    assert res_anl.status_code == 202
    analysis_id = res_anl.json()["analysis_id"]

    # 5. Check status (in TestClient background tasks execute synchronously)
    res_status = client.get(f"/analyses/{analysis_id}", headers=headers)
    assert res_status.status_code == 200
    status_data = res_status.json()
    assert status_data["status"] == "COMPLETED"
    assert status_data["progress_pct"] == 100

    # 6. Check Analysis Overview
    res_overview = client.get(f"/analyses/{analysis_id}/overview", headers=headers)
    assert res_overview.status_code == 200
    overview_data = res_overview.json()
    assert overview_data["total_spend"] > 0
    assert overview_data["total_anomalies"] >= 1

    # 7. List Anomalies
    res_anoms = client.get(f"/anomalies?analysis_id={analysis_id}", headers=headers)
    assert res_anoms.status_code == 200
    anom_list = res_anoms.json()
    assert len(anom_list) >= 1
    target_anom = anom_list[0]
    anom_id = target_anom["anomaly_id"]

    # 8. Get Anomaly Detail with Plain-Language Narrative
    res_det = client.get(f"/anomalies/{anom_id}", headers=headers)
    assert res_det.status_code == 200
    det_data = res_det.json()
    assert len(det_data["narrative_markdown"]) > 0
    assert "evidence_refs" in det_data

    # 9. Submit User Feedback
    res_fb = client.post(
        f"/anomalies/{anom_id}/feedback",
        json={"feedback": "USEFUL", "notes": "Confirmed unplanned surge in worker instances."},
        headers=headers,
    )
    assert res_fb.status_code == 200
    assert res_fb.json()["user_feedback"] == "USEFUL"

    # Verify updated anomaly detail
    res_det_updated = client.get(f"/anomalies/{anom_id}", headers=headers)
    assert res_det_updated.json()["user_feedback"] == "USEFUL"
    assert res_det_updated.json()["status"] == "Investigating"


def test_csv_injection_protection_in_reports():
    """Verify exported CSV sanitizes dangerous characters (=, +, -, @) to neutralize formula injection."""
    headers = {"X-Tenant-ID": "tenant_sec_test"}

    # Upload CSV with malicious formula injection attempts
    res_up = client.post(
        "/uploads",
        files={"file": ("injected.csv", CSV_WITH_INJECTION.encode("utf-8"), "text/csv")},
        headers=headers,
    )
    assert res_up.status_code == 201
    upload_id = res_up.json()["upload_id"]

    # Run analysis
    res_anl = client.post(
        "/analyses",
        json={"upload_id": upload_id, "min_materiality_dollars": 10.0},
        headers=headers,
    )
    analysis_id = res_anl.json()["analysis_id"]

    # Export CSV report
    res_csv = client.get(f"/reports/{analysis_id}.csv", headers=headers)
    assert res_csv.status_code == 200
    csv_text = res_csv.text

    # Verify any cell that started with '=' or '+' has been escaped with a leading single quote
    for line in csv_text.splitlines():
        cells = line.split(",")
        for c in cells:
            clean_cell = c.strip('"')
            # If cell original began with formula trigger, must now begin with single quote
            if "cmd|" in clean_cell:
                assert clean_cell.startswith("'=" or "'+")
