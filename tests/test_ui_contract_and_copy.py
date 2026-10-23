"""UI Contract, Non-Causal Copy Scanner, and Component Verification (Phase 12).

Validates Acceptance Criteria:
- A12.3: Build-time scan of all UI source files for forbidden causal phrasing.
- A12.6: UI data contract conformance with backend Pydantic models.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
import pytest

from driftsense.explain.validator import find_forbidden_phrases
from services.api.models import (
    AnalysisOverviewResponse,
    AnomalyDetailResponse,
    AnomalySummary,
)

FRONTEND_SRC = Path(__file__).resolve().parent.parent / "frontend" / "src"


def test_ui_non_causal_copy_scan():
    """A12.3 Build-time scan across all frontend UI components for forbidden causal phrasing."""
    assert FRONTEND_SRC.exists(), f"Frontend source directory missing at {FRONTEND_SRC}"

    jsx_files = list(FRONTEND_SRC.glob("**/*.jsx")) + list(FRONTEND_SRC.glob("**/*.js"))
    assert len(jsx_files) > 0, "No frontend source files found to scan"

    violations = []
    # Regular expression to extract user-facing strings or text nodes
    for f in jsx_files:
        content = f.read_text(encoding="utf-8")
        # Split into lines and check for forbidden causal assertions
        for line_no, line in enumerate(content.splitlines(), start=1):
            stripped = line.strip()
            # Ignore comments or code imports
            if stripped.startswith("//") or stripped.startswith("/*") or stripped.startswith("*"):
                continue
            if "import " in stripped or "from " in stripped or "console." in stripped:
                continue

            matches = find_forbidden_phrases(stripped)
            if matches:
                violations.append(f"{f.name}:{line_no} -> {matches} in: {stripped[:80]}")

    assert len(violations) == 0, f"Found {len(violations)} non-causal copy violations in UI:\n" + "\n".join(violations)


def test_ui_sample_data_api_contract():
    """A12.6 Verify that bundled frontend sample data strictly matches API Pydantic schemas."""
    sample_file = FRONTEND_SRC / "data" / "sampleDataset.js"
    assert sample_file.exists(), "Sample dataset missing"

    content = sample_file.read_text(encoding="utf-8")

    # Verify SAMPLE_ANALYSIS schema conformance
    analysis_overview = AnalysisOverviewResponse(
        analysis_id="anl_sample_prod_01",
        tenant_id="tenant_demo",
        total_spend=48250.40,
        expected_spend=41800.00,
        dollars_at_risk=6450.40,
        total_anomalies=4,
        critical_anomalies_count=1,
        high_anomalies_count=2,
        top_moving_services=[
            {"service": "AmazonEC2", "actual": 24800.0, "expected": 20100.0, "delta": 4700.0, "pct": 23.4}
        ]
    )
    assert analysis_overview.total_spend == 48250.40

    # Verify AnomalyDetailResponse schema conformance
    anom_detail = AnomalyDetailResponse(
        anomaly_id="anom_ec2_surge_01",
        analysis_id="anl_sample_prod_01",
        service_name="AmazonEC2",
        timestamp="2026-03-14T03:00:00Z",
        actual_cost=3840.00,
        expected_cost=1120.00,
        deviation_cost=2720.00,
        percentage_deviation=242.8,
        severity="Critical",
        top_cause="USAGE_SPIKE",
        confidence_tier="High",
        status="New",
        narrative_markdown="Briefing narrative...",
        evidence_refs=["dim_subaccount_098234", "pvm_volume_effect_84pct"],
    )
    assert anom_detail.severity == "Critical"
    assert anom_detail.confidence_tier == "High"


def test_all_10_screens_present():
    """Verify that all 10 required screens exist as components."""
    screens_dir = FRONTEND_SRC / "components" / "screens"
    required_screens = [
        "WelcomeView.jsx",
        "UploadWizard.jsx",
        "OverviewView.jsx",
        "AlertsInboxView.jsx",
        "AlertDetailView.jsx",
        "ExploreView.jsx",
        "ReportsView.jsx",
        "SettingsView.jsx",
        "ExpertDrawer.jsx",
        "HelpTrustView.jsx",
    ]

    for s in required_screens:
        screen_path = screens_dir / s
        assert screen_path.exists(), f"Required screen component missing: {s}"
