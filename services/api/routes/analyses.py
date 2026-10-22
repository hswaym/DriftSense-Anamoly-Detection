"""Analyses router for DriftSense API (Phase 11)."""

from __future__ import annotations

import threading
import uuid
from typing import Any

import pandas as pd
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status

from driftsense.runtime.inference import RuntimeInferenceEngine
from services.api.database import db
from services.api.models import (
    AnalysisCreateRequest,
    AnalysisOverviewResponse,
    AnalysisStatusResponse,
)
from services.api.security import get_current_tenant_id

router = APIRouter(prefix="/analyses", tags=["Analyses"])


def _run_background_inference(
    analysis_id: str,
    tenant_id: str,
    file_path: str,
    column_mapping: dict[str, str],
    min_materiality_dollars: float,
) -> None:
    try:
        db.update_analysis_status(analysis_id, status="RUNNING", progress_pct=10)
        df_raw = pd.read_csv(file_path, low_memory=False)

        events = db.get_events(tenant_id)
        db.update_analysis_status(analysis_id, status="RUNNING", progress_pct=30)

        engine = RuntimeInferenceEngine(
            min_materiality_dollars=min_materiality_dollars,
        )

        res = engine.run_pipeline(
            raw_df=df_raw,
            analysis_id=analysis_id,
            tenant_id=tenant_id,
            events=events,
            column_mapping=column_mapping,
        )

        db.update_analysis_status(analysis_id, status="RUNNING", progress_pct=80)

        # Store anomalies
        anom_dicts = [a.to_dict() for a in res.anomalies]
        db.store_anomalies(tenant_id=tenant_id, analysis_id=analysis_id, anomalies=anom_dicts)

        db.update_analysis_status(
            analysis_id,
            status="COMPLETED",
            progress_pct=100,
            results=res.to_dict(),
        )
    except Exception as e:
        db.update_analysis_status(
            analysis_id,
            status="FAILED",
            progress_pct=100,
            error_message=str(e),
        )


@router.post("", response_model=AnalysisStatusResponse, status_code=status.HTTP_202_ACCEPTED)
def start_analysis_job(
    body: AnalysisCreateRequest,
    background_tasks: BackgroundTasks,
    tenant_id: str = Depends(get_current_tenant_id),
):
    """Trigger background anomaly detection & root-cause attribution analysis."""
    upload_rec = db.get_upload(body.upload_id, tenant_id)
    if not upload_rec:
        raise HTTPException(status_code=404, detail="Upload not found or access denied.")

    analysis_id = f"anl_{uuid.uuid4().hex[:10]}"
    rec = db.create_analysis(analysis_id=analysis_id, tenant_id=tenant_id, upload_id=body.upload_id)

    # Launch asynchronously
    background_tasks.add_task(
        _run_background_inference,
        analysis_id=analysis_id,
        tenant_id=tenant_id,
        file_path=upload_rec["file_path"],
        column_mapping=upload_rec.get("column_mapping", {}),
        min_materiality_dollars=body.min_materiality_dollars,
    )

    return AnalysisStatusResponse(
        analysis_id=rec["analysis_id"],
        tenant_id=tenant_id,
        upload_id=body.upload_id,
        status=rec["status"],
        progress_pct=rec["progress_pct"],
        created_at_utc=rec["created_at_utc"],
    )


@router.get("/{analysis_id}", response_model=AnalysisStatusResponse)
def get_analysis_status(
    analysis_id: str,
    tenant_id: str = Depends(get_current_tenant_id),
):
    """Poll status and progress of an ongoing or completed analysis."""
    rec = db.get_analysis(analysis_id, tenant_id)
    if not rec:
        raise HTTPException(status_code=404, detail="Analysis not found.")
    return AnalysisStatusResponse(
        analysis_id=rec["analysis_id"],
        tenant_id=tenant_id,
        upload_id=rec["upload_id"],
        status=rec["status"],
        progress_pct=rec["progress_pct"],
        created_at_utc=rec["created_at_utc"],
        completed_at_utc=rec.get("completed_at_utc"),
        error_message=rec.get("error_message"),
    )


@router.get("/{analysis_id}/overview", response_model=AnalysisOverviewResponse)
def get_analysis_overview(
    analysis_id: str,
    tenant_id: str = Depends(get_current_tenant_id),
):
    """Get high-level executive dashboard metrics for a completed analysis."""
    rec = db.get_analysis(analysis_id, tenant_id)
    if not rec:
        raise HTTPException(status_code=404, detail="Analysis not found.")

    if rec["status"] != "COMPLETED":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Analysis is currently in state '{rec['status']}'. Overview available only after completion.",
        )

    res = rec.get("results", {})
    anomalies = res.get("anomalies", [])

    crit_cnt = sum(1 for a in anomalies if a.get("severity") == "Critical")
    high_cnt = sum(1 for a in anomalies if a.get("severity") == "High")

    # Aggregate top moving services by total deviation
    svc_map: dict[str, float] = {}
    for a in anomalies:
        svc = a.get("service_name", "Unknown")
        svc_map[svc] = svc_map.get(svc, 0.0) + float(a.get("deviation_cost", 0.0))

    top_services = [
        {"service_name": s, "total_deviation_cost": round(c, 2)}
        for s, c in sorted(svc_map.items(), key=lambda x: x[1], reverse=True)[:5]
    ]

    return AnalysisOverviewResponse(
        analysis_id=analysis_id,
        tenant_id=tenant_id,
        total_spend=res.get("total_spend", 0.0),
        expected_spend=res.get("expected_spend", 0.0),
        dollars_at_risk=res.get("dollars_at_risk", 0.0),
        total_anomalies=res.get("total_anomalies", 0),
        critical_anomalies_count=crit_cnt,
        high_anomalies_count=high_cnt,
        top_moving_services=top_services,
    )
