"""Thread-safe metadata storage and repository for DriftSense API (Phase 11).

Provides tenant-scoped persistence for:
- Upload records & saved files
- Column mappings
- Analysis job status & progress
- Anomaly records & user feedback
- Operational events
"""

from __future__ import annotations

import datetime
import os
import threading
from pathlib import Path
from typing import Any

BASE_STORAGE_DIR = Path(os.environ.get("DRIFTSENSE_DATA_DIR", "data/uploads"))


class Database:
    """In-memory thread-safe tenant repository with disk storage backing."""

    def __init__(self, storage_dir: Path | None = None) -> None:
        self.storage_dir = storage_dir or BASE_STORAGE_DIR
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

        # Primary tables keyed by ID:
        # {upload_id: {tenant_id, ...}}
        self.uploads: dict[str, dict[str, Any]] = {}
        # {analysis_id: {tenant_id, ...}}
        self.analyses: dict[str, dict[str, Any]] = {}
        # {anomaly_id: {tenant_id, analysis_id, ...}}
        self.anomalies: dict[str, dict[str, Any]] = {}
        # {tenant_id: [event_dicts]}
        self.events: dict[str, list[dict[str, Any]]] = {}

    def get_tenant_storage_path(self, tenant_id: str) -> Path:
        p = self.storage_dir / tenant_id
        p.mkdir(parents=True, exist_ok=True)
        return p

    def save_upload(
        self,
        upload_id: str,
        tenant_id: str,
        filename: str,
        file_bytes: bytes,
        detected_provider: str,
        column_names: list[str],
        suggested_mapping: dict[str, str],
        row_count: int,
    ) -> dict[str, Any]:
        tenant_dir = self.get_tenant_storage_path(tenant_id)
        file_path = tenant_dir / f"{upload_id}_{filename}"
        file_path.write_bytes(file_bytes)

        record = {
            "upload_id": upload_id,
            "tenant_id": tenant_id,
            "filename": filename,
            "file_path": str(file_path),
            "file_size_bytes": len(file_bytes),
            "detected_provider": detected_provider,
            "column_names": column_names,
            "column_mapping": suggested_mapping,
            "row_count_estimate": row_count,
            "created_at_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        }
        with self._lock:
            self.uploads[upload_id] = record
        return record

    def get_upload(self, upload_id: str, tenant_id: str) -> dict[str, Any] | None:
        with self._lock:
            record = self.uploads.get(upload_id)
            if record and record["tenant_id"] == tenant_id:
                return dict(record)
        return None

    def update_column_mapping(
        self, upload_id: str, tenant_id: str, mapping: dict[str, str]
    ) -> bool:
        with self._lock:
            record = self.uploads.get(upload_id)
            if record and record["tenant_id"] == tenant_id:
                record["column_mapping"] = mapping
                return True
        return False

    def delete_upload(self, upload_id: str, tenant_id: str) -> bool:
        with self._lock:
            record = self.uploads.get(upload_id)
            if record and record["tenant_id"] == tenant_id:
                # Remove file from disk
                try:
                    Path(record["file_path"]).unlink(missing_ok=True)
                except Exception:
                    pass
                del self.uploads[upload_id]
                return True
        return False

    def create_analysis(
        self,
        analysis_id: str,
        tenant_id: str,
        upload_id: str,
    ) -> dict[str, Any]:
        record = {
            "analysis_id": analysis_id,
            "tenant_id": tenant_id,
            "upload_id": upload_id,
            "status": "PENDING",
            "progress_pct": 0,
            "created_at_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "completed_at_utc": None,
            "error_message": None,
            "results": None,
        }
        with self._lock:
            self.analyses[analysis_id] = record
        return record

    def update_analysis_status(
        self,
        analysis_id: str,
        status: str,
        progress_pct: int = 0,
        results: dict[str, Any] | None = None,
        error_message: str | None = None,
    ) -> None:
        with self._lock:
            record = self.analyses.get(analysis_id)
            if record:
                record["status"] = status
                record["progress_pct"] = progress_pct
                if results:
                    record["results"] = results
                if error_message:
                    record["error_message"] = error_message
                if status in ("COMPLETED", "FAILED"):
                    record["completed_at_utc"] = datetime.datetime.now(
                        datetime.timezone.utc
                    ).isoformat()

    def get_analysis(self, analysis_id: str, tenant_id: str) -> dict[str, Any] | None:
        with self._lock:
            record = self.analyses.get(analysis_id)
            if record and record["tenant_id"] == tenant_id:
                return dict(record)
        return None

    def store_anomalies(
        self,
        tenant_id: str,
        analysis_id: str,
        anomalies: list[dict[str, Any]],
    ) -> None:
        with self._lock:
            for anom in anomalies:
                anom_id = anom["anomaly_id"]
                full_rec = dict(anom)
                full_rec["tenant_id"] = tenant_id
                full_rec["analysis_id"] = analysis_id
                self.anomalies[anom_id] = full_rec

    def get_anomalies_for_tenant(
        self,
        tenant_id: str,
        analysis_id: str | None = None,
        severity: str | None = None,
        service: str | None = None,
    ) -> list[dict[str, Any]]:
        with self._lock:
            res = []
            for anom in self.anomalies.values():
                if anom["tenant_id"] != tenant_id:
                    continue
                if analysis_id and anom["analysis_id"] != analysis_id:
                    continue
                if severity and anom["severity"].lower() != severity.lower():
                    continue
                if service and anom["service_name"].lower() != service.lower():
                    continue
                res.append(dict(anom))
            # Sort by deviation descending
            res.sort(key=lambda x: x["deviation_cost"], reverse=True)
            return res

    def get_anomaly(self, anomaly_id: str, tenant_id: str) -> dict[str, Any] | None:
        with self._lock:
            anom = self.anomalies.get(anomaly_id)
            if anom and anom["tenant_id"] == tenant_id:
                return dict(anom)
        return None

    def update_anomaly_feedback(
        self,
        anomaly_id: str,
        tenant_id: str,
        feedback: str,
        notes: str | None = None,
    ) -> bool:
        with self._lock:
            anom = self.anomalies.get(anomaly_id)
            if anom and anom["tenant_id"] == tenant_id:
                anom["user_feedback"] = feedback
                anom["feedback_notes"] = notes
                anom["status"] = "Resolved" if feedback == "PLANNED" else "Investigating"
                return True
        return False

    def add_events(self, tenant_id: str, events: list[dict[str, Any]]) -> None:
        with self._lock:
            if tenant_id not in self.events:
                self.events[tenant_id] = []
            self.events[tenant_id].extend(events)

    def get_events(self, tenant_id: str) -> list[dict[str, Any]]:
        with self._lock:
            return list(self.events.get(tenant_id, []))


# Global singleton instance
db = Database()
