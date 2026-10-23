"""Uploads router for DriftSense API (Phase 11)."""

from __future__ import annotations

import io
import uuid

import pandas as pd
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status

from services.api.database import db
from services.api.models import (
    ColumnMappingUpdateRequest,
    DataQualityReport,
    UploadMetadata,
)
from services.api.security import (
    get_current_tenant_id,
    sanitize_filename,
    validate_upload_content,
)

router = APIRouter(prefix="/uploads", tags=["Uploads"])

PROVIDER_SIGNATURES = {
    "FOCUS": {"ChargePeriodStart", "BilledCost", "EffectiveCost", "ServiceName"},
    "AWS_CUR": {"lineItem/UsageStartDate", "lineItem/UnblendedCost", "lineItem/ProductCode"},
    "AZURE": {"date", "costInBillingCurrency", "meterCategory"},
    "GCP": {"usage_start_time", "cost", "service.description"},
}


def detect_provider(columns: list[str]) -> tuple[str, dict[str, str]]:
    col_set = set(columns)
    for prov, sig in PROVIDER_SIGNATURES.items():
        if sig.issubset(col_set):
            return prov, {c: c for c in columns}

    # Best-effort heuristic mapping to FOCUS
    mapping: dict[str, str] = {}
    lower_map = {c.lower(): c for c in columns}

    # Time col
    for candidate in ["chargeperiodstart", "usagestartdate", "date", "time", "timestamp"]:
        if candidate in lower_map:
            mapping[lower_map[candidate]] = "ChargePeriodStart"
            break

    # Cost col
    for candidate in ["effectivecost", "billedcost", "cost", "unblendedcost", "amount"]:
        if candidate in lower_map:
            mapping[lower_map[candidate]] = "EffectiveCost"
            break

    # Service col
    for candidate in ["servicename", "service", "productcode", "metercategory", "lineitem/productcode"]:
        if candidate in lower_map:
            mapping[lower_map[candidate]] = "ServiceName"
            break

    # Quantity col
    for candidate in ["consumedquantity", "usagequantity", "quantity", "usage_amount"]:
        if candidate in lower_map:
            mapping[lower_map[candidate]] = "ConsumedQuantity"
            break

    detected = "FOCUS" if "ChargePeriodStart" in mapping.values() else "CUSTOM"
    return detected, mapping


@router.post("", response_model=UploadMetadata, status_code=status.HTTP_201_CREATED)
async def upload_billing_file(
    file: UploadFile = File(...),
    tenant_id: str = Depends(get_current_tenant_id),
):
    """Upload a billing telemetry file with magic-byte and format verification."""
    clean_name = sanitize_filename(file.filename or "upload.csv")
    content = await file.read()

    # Security check (size & magic bytes)
    validate_upload_content(content, clean_name)

    # Read schema
    try:
        if clean_name.endswith(".parquet"):
            df_sample = pd.read_parquet(io.BytesIO(content))
        else:
            df_sample = pd.read_csv(io.BytesIO(content), nrows=500, low_memory=False)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unable to parse upload file as valid tabular data: {e}",
        ) from e

    cols = list(df_sample.columns)
    detected_prov, suggested_map = detect_provider(cols)
    upload_id = f"upl_{uuid.uuid4().hex[:10]}"

    record = db.save_upload(
        upload_id=upload_id,
        tenant_id=tenant_id,
        filename=clean_name,
        file_bytes=content,
        detected_provider=detected_prov,
        column_names=cols,
        suggested_mapping=suggested_map,
        row_count=len(df_sample),
    )

    return UploadMetadata(
        upload_id=record["upload_id"],
        tenant_id=tenant_id,
        filename=clean_name,
        file_size_bytes=record["file_size_bytes"],
        detected_provider=detected_prov,
        row_count_estimate=record["row_count_estimate"],
        column_names=cols,
        suggested_mapping=suggested_map,
    )


@router.get("", response_model=list[UploadMetadata])
def list_uploads(
    tenant_id: str = Depends(get_current_tenant_id),
):
    """List all uploads scoped to authenticated tenant."""
    records = db.list_uploads_for_tenant(tenant_id)
    return [
        UploadMetadata(
            upload_id=rec["upload_id"],
            tenant_id=tenant_id,
            filename=rec["filename"],
            file_size_bytes=rec["file_size_bytes"],
            detected_provider=rec["detected_provider"],
            row_count_estimate=rec["row_count_estimate"],
            column_names=rec["column_names"],
            suggested_mapping=rec.get("column_mapping", {}),
        )
        for rec in records
    ]


@router.get("/{upload_id}", response_model=UploadMetadata)
def get_upload_metadata(
    upload_id: str,
    tenant_id: str = Depends(get_current_tenant_id),
):
    """Retrieve metadata for an existing upload."""
    rec = db.get_upload(upload_id, tenant_id)
    if not rec:
        raise HTTPException(status_code=404, detail="Upload not found.")
    return UploadMetadata(
        upload_id=rec["upload_id"],
        tenant_id=tenant_id,
        filename=rec["filename"],
        file_size_bytes=rec["file_size_bytes"],
        detected_provider=rec["detected_provider"],
        row_count_estimate=rec["row_count_estimate"],
        column_names=rec["column_names"],
        suggested_mapping=rec.get("column_mapping", {}),
    )


@router.get("/{upload_id}/mapping")
def get_column_mapping(
    upload_id: str,
    tenant_id: str = Depends(get_current_tenant_id),
):
    """Get active column mapping for an upload."""
    rec = db.get_upload(upload_id, tenant_id)
    if not rec:
        raise HTTPException(status_code=404, detail="Upload not found.")
    return {"upload_id": upload_id, "column_mapping": rec.get("column_mapping", {})}


@router.put("/{upload_id}/mapping")
def update_column_mapping(
    upload_id: str,
    body: ColumnMappingUpdateRequest,
    tenant_id: str = Depends(get_current_tenant_id),
):
    """Update column mapping for an upload."""
    success = db.update_column_mapping(upload_id, tenant_id, body.column_mapping)
    if not success:
        raise HTTPException(status_code=404, detail="Upload not found.")
    return {"status": "SUCCESS", "upload_id": upload_id, "column_mapping": body.column_mapping}


@router.get("/{upload_id}/health", response_model=DataQualityReport)
@router.get("/{upload_id}/quality", response_model=DataQualityReport)
def get_data_quality_report(
    upload_id: str,
    tenant_id: str = Depends(get_current_tenant_id),
):
    """Compute data health score and diagnostics."""
    rec = db.get_upload(upload_id, tenant_id)
    if not rec:
        raise HTTPException(status_code=404, detail="Upload not found.")

    try:
        df = pd.read_csv(rec["file_path"], low_memory=False)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read file: {e}") from e

    mapping = rec.get("column_mapping", {})
    if mapping:
        df = df.rename(columns=mapping)

    total_rows = len(df)
    missing_ts = int(df["ChargePeriodStart"].isna().sum()) if "ChargePeriodStart" in df.columns else total_rows
    negative_cost = int((df["EffectiveCost"] < 0).sum()) if "EffectiveCost" in df.columns else 0
    null_service = int(df["ServiceName"].isna().sum()) if "ServiceName" in df.columns else total_rows
    duplicate_rows = int(df.duplicated().sum())

    score = 100.0
    findings = []

    if missing_ts > 0:
        pct_missing = (missing_ts / max(1, total_rows)) * 100.0
        score -= min(35.0, pct_missing)
        findings.append(f"{missing_ts:,} rows ({pct_missing:.1f}%) have missing or unparseable timestamps.")

    if null_service > 0:
        pct_null = (null_service / max(1, total_rows)) * 100.0
        score -= min(25.0, pct_null)
        findings.append(f"{null_service:,} rows ({pct_null:.1f}%) have unassigned ServiceName values.")

    if negative_cost > 0:
        score -= min(15.0, negative_cost * 2.0)
        findings.append(f"{negative_cost:,} rows contain negative costs (possible credit adjustments).")

    if duplicate_rows > 0:
        score -= min(15.0, duplicate_rows * 1.5)
        findings.append(f"{duplicate_rows:,} duplicate rows detected.")

    if not findings:
        findings.append("All data quality checks passed with zero integrity defects.")

    return DataQualityReport(
        upload_id=upload_id,
        health_score=round(max(0.0, score), 1),
        total_rows=total_rows,
        missing_timestamp_count=missing_ts,
        negative_cost_count=negative_cost,
        null_service_count=null_service,
        duplicate_rows_count=duplicate_rows,
        findings=findings,
    )


@router.delete("/{upload_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_upload_data(
    upload_id: str,
    tenant_id: str = Depends(get_current_tenant_id),
):
    """Hard delete uploaded dataset and associated records for privacy/retention compliance."""
    success = db.delete_upload(upload_id, tenant_id)
    if not success:
        raise HTTPException(status_code=404, detail="Upload not found.")
