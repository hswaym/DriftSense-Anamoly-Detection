"""Feedback store and schema for DriftSense v2 (Phase 13).

Provides isolated storage for human engineering and accounting feedback on anomaly alerts.
Ensures human feedback remains completely segregated from synthetic benchmarks (A13.1).
"""

from __future__ import annotations

import datetime
import json
import os
import threading
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

VALID_FEEDBACK_LABELS = {"USEFUL", "NOT_AN_ISSUE", "PLANNED"}
DEFAULT_FEEDBACK_DIR = Path(os.environ.get("DRIFTSENSE_FEEDBACK_DIR", "data/feedback"))


@dataclass
class FeedbackRecord:
    """Individual human feedback record for an anomaly detection alert."""

    feedback_id: str
    anomaly_id: str
    analysis_id: str
    tenant_id: str
    service_name: str
    severity: str
    timestamp_alert: str
    timestamp_feedback: str
    feedback_label: str  # "USEFUL", "NOT_AN_ISSUE", "PLANNED"
    notes: str | None = None
    time_to_acknowledge_seconds: float = 0.0
    is_synthetic: bool = False  # Strict segregation marker (A13.1)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.feedback_label not in VALID_FEEDBACK_LABELS:
            raise ValueError(
                f"Invalid feedback label '{self.feedback_label}'. "
                f"Must be one of {VALID_FEEDBACK_LABELS}"
            )
        if self.is_synthetic:
            raise ValueError(
                "Segregation invariant violation: FeedbackRecord must never be flagged as synthetic."
            )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> FeedbackRecord:
        d = dict(data)
        d.pop("is_synthetic", None)  # Always enforce False
        return cls(is_synthetic=False, **d)


class FeedbackStore:
    """Thread-safe persistent store for alert feedback records."""

    def __init__(self, storage_dir: Path | None = None) -> None:
        self.storage_dir = storage_dir or DEFAULT_FEEDBACK_DIR
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.log_file = self.storage_dir / "feedback_log.jsonl"
        self._lock = threading.Lock()
        self._records: dict[str, FeedbackRecord] = {}
        self._load_existing()

    def _load_existing(self) -> None:
        if not self.log_file.exists():
            return
        with open(self.log_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    rec = FeedbackRecord.from_dict(data)
                    self._records[rec.feedback_id] = rec
                except Exception:
                    continue

    def record_feedback(
        self,
        anomaly_id: str,
        analysis_id: str,
        tenant_id: str,
        service_name: str,
        severity: str,
        timestamp_alert: str,
        feedback_label: str,
        notes: str | None = None,
        timestamp_feedback: str | None = None,
    ) -> FeedbackRecord:
        """Create and persist a new human feedback record."""
        ts_fb = timestamp_feedback or datetime.datetime.now(datetime.timezone.utc).isoformat()

        # Compute acknowledge latency
        ack_seconds = 0.0
        try:
            t0 = datetime.datetime.fromisoformat(timestamp_alert.replace("Z", "+00:00"))
            t1 = datetime.datetime.fromisoformat(ts_fb.replace("Z", "+00:00"))
            ack_seconds = max(0.0, (t1 - t0).total_seconds())
        except Exception:
            pass

        fb_id = f"fb_{uuid.uuid4().hex[:12]}"
        rec = FeedbackRecord(
            feedback_id=fb_id,
            anomaly_id=anomaly_id,
            analysis_id=analysis_id,
            tenant_id=tenant_id,
            service_name=service_name,
            severity=severity,
            timestamp_alert=timestamp_alert,
            timestamp_feedback=ts_fb,
            feedback_label=feedback_label.upper(),
            notes=notes,
            time_to_acknowledge_seconds=round(ack_seconds, 1),
            is_synthetic=False,
        )

        with self._lock:
            self._records[fb_id] = rec
            # Append to persistent JSON lines log
            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(rec.to_dict()) + "\n")

        return rec

    def get_records(
        self,
        tenant_id: str | None = None,
        service_name: str | None = None,
        severity: str | None = None,
    ) -> list[FeedbackRecord]:
        """Query stored feedback records with optional filters."""
        with self._lock:
            records = list(self._records.values())

        filtered = []
        for r in records:
            if tenant_id and r.tenant_id != tenant_id:
                continue
            if service_name and r.service_name.lower() != service_name.lower():
                continue
            if severity and r.severity.lower() != severity.lower():
                continue
            filtered.append(r)
        return filtered

    def clear(self) -> None:
        """Clear memory and storage for testing."""
        with self._lock:
            self._records.clear()
            if self.log_file.exists():
                self.log_file.unlink(missing_ok=True)


# Global singleton instance
feedback_store = FeedbackStore()
