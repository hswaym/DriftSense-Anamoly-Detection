"""Anomalies router for DriftSense API (Phase 11)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from services.api.database import db
from services.api.models import (
    AnomalyDetailResponse,
    AnomalyFeedbackRequest,
    AnomalySummary,
)
from services.api.security import get_current_tenant_id

router = APIRouter(prefix="/anomalies", tags=["Anomalies"])


@router.get("", response_model=list[AnomalySummary])
def list_anomalies(
    analysis_id: str | None = Query(default=None),
    severity: str | None = Query(default=None),
    service: str | None = Query(default=None),
    tenant_id: str = Depends(get_current_tenant_id),
):
    """List detected anomalies with optional severity and service filters."""
    anomalies = db.get_anomalies_for_tenant(
        tenant_id=tenant_id,
        analysis_id=analysis_id,
        severity=severity,
        service=service,
    )
    return [
        AnomalySummary(
            anomaly_id=a["anomaly_id"],
            analysis_id=a.get("analysis_id", ""),
            service_name=a["service_name"],
            timestamp=a["timestamp"],
            actual_cost=a["actual_cost"],
            expected_cost=a["expected_cost"],
            deviation_cost=a["deviation_cost"],
            percentage_deviation=a["percentage_deviation"],
            severity=a["severity"],
            top_cause=a["top_cause"],
            confidence_tier=a["confidence_tier"],
            status=a.get("status", "New"),
            user_feedback=a.get("user_feedback"),
        )
        for a in anomalies
    ]


@router.get("/{anomaly_id}", response_model=AnomalyDetailResponse)
def get_anomaly_detail(
    anomaly_id: str,
    tenant_id: str = Depends(get_current_tenant_id),
):
    """Get complete anomaly briefing with plain-language narrative and evidence refs."""
    anom = db.get_anomaly(anomaly_id, tenant_id)
    if not anom:
        raise HTTPException(status_code=404, detail="Anomaly not found.")

    return AnomalyDetailResponse(
        anomaly_id=anom["anomaly_id"],
        analysis_id=anom.get("analysis_id", ""),
        service_name=anom["service_name"],
        timestamp=anom["timestamp"],
        actual_cost=anom["actual_cost"],
        expected_cost=anom["expected_cost"],
        deviation_cost=anom["deviation_cost"],
        percentage_deviation=anom["percentage_deviation"],
        severity=anom["severity"],
        top_cause=anom["top_cause"],
        confidence_tier=anom["confidence_tier"],
        status=anom.get("status", "New"),
        user_feedback=anom.get("user_feedback"),
        narrative_markdown=anom.get("narrative_markdown", ""),
        evidence_refs=anom.get("evidence_refs", []),
        feedback_notes=anom.get("feedback_notes"),
    )


@router.post("/{anomaly_id}/feedback")
def submit_anomaly_feedback(
    anomaly_id: str,
    body: AnomalyFeedbackRequest,
    tenant_id: str = Depends(get_current_tenant_id),
):
    """Submit human engineer / finance feedback on an anomaly alert."""
    allowed = {"USEFUL", "NOT_AN_ISSUE", "PLANNED"}
    upper_fb = body.feedback.upper()
    if upper_fb not in allowed:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid feedback '{body.feedback}'. Must be one of {allowed}",
        )

    anom = db.get_anomaly(anomaly_id, tenant_id)
    if not anom:
        raise HTTPException(status_code=404, detail="Anomaly not found.")

    success = db.update_anomaly_feedback(
        anomaly_id=anomaly_id,
        tenant_id=tenant_id,
        feedback=upper_fb,
        notes=body.notes,
    )
    if not success:
        raise HTTPException(status_code=404, detail="Anomaly not found.")

    from driftsense.monitor.feedback_store import feedback_store
    feedback_store.record_feedback(
        anomaly_id=anomaly_id,
        analysis_id=anom.get("analysis_id", "anl_unknown"),
        tenant_id=tenant_id,
        service_name=anom.get("service_name", "UNKNOWN"),
        severity=anom.get("severity", "Medium"),
        timestamp_alert=anom.get("timestamp", ""),
        feedback_label=upper_fb,
        notes=body.notes,
    )

    return {
        "status": "SUCCESS",
        "anomaly_id": anomaly_id,
        "user_feedback": upper_fb,
        "notes": body.notes,
    }
