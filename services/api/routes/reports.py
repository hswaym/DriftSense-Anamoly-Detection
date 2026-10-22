"""Reports and export router for DriftSense API (Phase 11).

Provides CSV and JSON report exports with strict CSV-injection sanitization
and tenant isolation.
"""

from __future__ import annotations

import csv
import io
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Response

from services.api.database import db
from services.api.security import get_current_tenant_id, sanitize_csv_cell

router = APIRouter(prefix="/reports", tags=["Reports"])


@router.get("/{analysis_id}/export.csv")
@router.get("/{analysis_id}.csv")
def export_analysis_csv(
    analysis_id: str,
    tenant_id: str = Depends(get_current_tenant_id),
):
    """Export detected anomalies for an analysis as a sanitized CSV file.
    
    Guards against formula injection by prefixing '=', '+', '-', '@' with a single quote.
    """
    analysis = db.get_analysis(analysis_id, tenant_id)
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found.")

    anomalies = db.get_anomalies_for_tenant(tenant_id=tenant_id, analysis_id=analysis_id)

    output = io.StringIO()
    fieldnames = [
        "anomaly_id",
        "analysis_id",
        "service_name",
        "timestamp",
        "actual_cost",
        "expected_cost",
        "deviation_cost",
        "percentage_deviation",
        "severity",
        "top_cause",
        "confidence_tier",
        "status",
        "user_feedback",
        "feedback_notes",
    ]

    writer = csv.DictWriter(output, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()

    for a in anomalies:
        row: dict[str, Any] = {
            "anomaly_id": sanitize_csv_cell(a.get("anomaly_id", "")),
            "analysis_id": sanitize_csv_cell(analysis_id),
            "service_name": sanitize_csv_cell(a.get("service_name", "")),
            "timestamp": sanitize_csv_cell(a.get("timestamp", "")),
            "actual_cost": f"{float(a.get('actual_cost', 0.0)):.2f}",
            "expected_cost": f"{float(a.get('expected_cost', 0.0)):.2f}",
            "deviation_cost": f"{float(a.get('deviation_cost', 0.0)):.2f}",
            "percentage_deviation": f"{float(a.get('percentage_deviation', 0.0)):.1f}",
            "severity": sanitize_csv_cell(a.get("severity", "")),
            "top_cause": sanitize_csv_cell(a.get("top_cause", "")),
            "confidence_tier": sanitize_csv_cell(a.get("confidence_tier", "")),
            "status": sanitize_csv_cell(a.get("status", "New")),
            "user_feedback": sanitize_csv_cell(a.get("user_feedback", "")),
            "feedback_notes": sanitize_csv_cell(a.get("feedback_notes", "")),
        }
        writer.writerow(row)

    csv_content = output.getvalue()
    filename = f"driftsense_report_{analysis_id}.csv"

    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "no-cache",
        },
    )


@router.get("/{analysis_id}/export.json")
def export_analysis_json(
    analysis_id: str,
    tenant_id: str = Depends(get_current_tenant_id),
):
    """Export complete audit trail and anomalies as JSON."""
    analysis = db.get_analysis(analysis_id, tenant_id)
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found.")

    anomalies = db.get_anomalies_for_tenant(tenant_id=tenant_id, analysis_id=analysis_id)
    events = db.get_events(tenant_id=tenant_id)

    return {
        "analysis_id": analysis_id,
        "tenant_id": tenant_id,
        "status": analysis.get("status"),
        "created_at_utc": analysis.get("created_at_utc"),
        "completed_at_utc": analysis.get("completed_at_utc"),
        "results_overview": analysis.get("results"),
        "anomalies_count": len(anomalies),
        "anomalies": anomalies,
        "operational_events": events,
    }
