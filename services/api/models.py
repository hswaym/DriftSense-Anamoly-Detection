"""Pydantic schemas for DriftSense v2 API (Phase 11)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class UploadMetadata(BaseModel):
    """Metadata response for an uploaded file."""

    upload_id: str
    tenant_id: str
    filename: str
    file_size_bytes: int
    detected_provider: str  # "FOCUS", "AWS_CUR", "AZURE", "GCP", "UNKNOWN"
    row_count_estimate: int
    column_names: list[str]
    suggested_mapping: dict[str, str]


class ColumnMappingUpdateRequest(BaseModel):
    """User confirmed or edited column mapping."""

    column_mapping: dict[str, str] = Field(
        ...,
        description="Map from raw uploaded column names to canonical FOCUS 1.0 names",
    )


class DataQualityReport(BaseModel):
    """Data health score and diagnostic findings on uploaded file."""

    upload_id: str
    health_score: float  # [0.0, 100.0]
    total_rows: int
    missing_timestamp_count: int
    negative_cost_count: int
    null_service_count: int
    duplicate_rows_count: int
    findings: list[str]


class AnalysisCreateRequest(BaseModel):
    """Request to initiate background analysis."""

    upload_id: str
    min_materiality_dollars: float = Field(
        default=10.0, description="Minimum deviation ($) to flag as actionable anomaly"
    )
    sensitivity: str = Field(
        default="Balanced", description="'Low', 'Balanced', or 'High'"
    )


class AnalysisStatusResponse(BaseModel):
    """Status and progress of an analysis run."""

    analysis_id: str
    tenant_id: str
    upload_id: str
    status: str  # "PENDING", "RUNNING", "COMPLETED", "FAILED"
    progress_pct: int
    created_at_utc: str
    completed_at_utc: str | None = None
    error_message: str | None = None


class AnalysisOverviewResponse(BaseModel):
    """Executive summary metrics for a completed analysis."""

    analysis_id: str
    tenant_id: str
    total_spend: float
    expected_spend: float
    dollars_at_risk: float
    total_anomalies: int
    critical_anomalies_count: int
    high_anomalies_count: int
    top_moving_services: list[dict[str, Any]]


class AnomalySummary(BaseModel):
    """Brief summary of a detected anomaly for the inbox view."""

    anomaly_id: str
    analysis_id: str
    service_name: str
    timestamp: str
    actual_cost: float
    expected_cost: float
    deviation_cost: float
    percentage_deviation: float
    severity: str
    top_cause: str
    confidence_tier: str
    status: str
    user_feedback: str | None = None


class AnomalyDetailResponse(AnomalySummary):
    """Full detail view of an anomaly including plain-language narrative and evidence."""

    narrative_markdown: str
    evidence_refs: list[str]
    feedback_notes: str | None = None


class AnomalyFeedbackRequest(BaseModel):
    """User feedback on an anomaly alert."""

    feedback: str = Field(
        ...,
        description="One of 'USEFUL', 'NOT_AN_ISSUE', or 'PLANNED'",
    )
    notes: str | None = Field(
        default=None, description="Optional engineering/accounting notes"
    )


class EventCreateRequest(BaseModel):
    """Operational change event."""

    event_id: str
    service_id: str
    timestamp: str
    event_type: str
    summary: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)
