"""Events router for DriftSense API (Phase 11)."""

from __future__ import annotations

import io
from typing import Any

import pandas as pd
from fastapi import APIRouter, Depends, File, UploadFile, status

from services.api.database import db
from services.api.models import EventCreateRequest
from services.api.security import get_current_tenant_id, sanitize_filename, validate_upload_content

router = APIRouter(prefix="/events", tags=["Operational Events"])


@router.post("", status_code=status.HTTP_201_CREATED)
def create_operational_event(
    event: EventCreateRequest,
    tenant_id: str = Depends(get_current_tenant_id),
):
    """Register a single operational change event."""
    db.add_events(tenant_id=tenant_id, events=[event.model_dump()])
    return {"status": "SUCCESS", "event_id": event.event_id}


@router.post("/upload", status_code=status.HTTP_201_CREATED)
async def upload_events_csv(
    file: UploadFile = File(...),
    tenant_id: str = Depends(get_current_tenant_id),
):
    """Upload bulk operational change events via CSV."""
    clean_name = sanitize_filename(file.filename or "events.csv")
    content = await file.read()
    validate_upload_content(content, clean_name)

    df_events = pd.read_csv(io.BytesIO(content))
    events_list = df_events.to_dict(orient="records")
    db.add_events(tenant_id=tenant_id, events=events_list)

    return {"status": "SUCCESS", "events_imported": len(events_list)}


@router.get("")
def list_operational_events(
    tenant_id: str = Depends(get_current_tenant_id),
):
    """List operational change events for current tenant."""
    events = db.get_events(tenant_id)
    return {"tenant_id": tenant_id, "total_events": len(events), "events": events}
