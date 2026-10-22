"""Background asynchronous worker daemon for DriftSense (Phase 11).

Can run as an independent background process or container to process queued
heavy inference workloads, data ingestion, and batch evaluation jobs.
"""

from __future__ import annotations

import logging
import signal
import sys
import time
from typing import Any

import pandas as pd

from driftsense.runtime.inference import RuntimeInferenceEngine
from services.api.database import db

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [Worker] %(message)s",
)
logger = logging.getLogger("driftsense-worker")


class AnalysisWorker:
    """Worker polling or queue processor for asynchronous FinOps analysis jobs."""

    def __init__(self, poll_interval_sec: float = 2.0) -> None:
        self.poll_interval_sec = poll_interval_sec
        self._running = True
        self._setup_signals()

    def _setup_signals(self) -> None:
        def _stop(sig: int, frame: Any) -> None:
            logger.info("Received termination signal %s, draining worker...", sig)
            self._running = False

        try:
            signal.signal(signal.SIGINT, _stop)
            signal.signal(signal.SIGTERM, _stop)
        except (ValueError, AttributeError):
            # Not supported in certain non-main threads or platforms
            pass

    def run_job(self, analysis_id: str, tenant_id: str) -> bool:
        """Execute a single analysis job synchronously."""
        analysis = db.get_analysis(analysis_id, tenant_id)
        if not analysis:
            logger.error("Analysis %s not found for tenant %s", analysis_id, tenant_id)
            return False

        upload_id = analysis["upload_id"]
        upload_rec = db.get_upload(upload_id, tenant_id)
        if not upload_rec:
            logger.error("Upload %s not found for analysis %s", upload_id, analysis_id)
            db.update_analysis_status(
                analysis_id,
                status="FAILED",
                progress_pct=100,
                error_message="Referenced upload file missing",
            )
            return False

        logger.info("Starting processing for analysis %s (tenant: %s)", analysis_id, tenant_id)
        try:
            db.update_analysis_status(analysis_id, status="RUNNING", progress_pct=10)
            df_raw = pd.read_csv(upload_rec["file_path"], low_memory=False)

            events = db.get_events(tenant_id)
            db.update_analysis_status(analysis_id, status="RUNNING", progress_pct=30)

            engine = RuntimeInferenceEngine(min_materiality_dollars=10.0)
            res = engine.run_pipeline(
                raw_df=df_raw,
                analysis_id=analysis_id,
                tenant_id=tenant_id,
                events=events,
                column_mapping=upload_rec.get("column_mapping", {}),
            )

            db.update_analysis_status(analysis_id, status="RUNNING", progress_pct=80)

            anom_dicts = [a.to_dict() for a in res.anomalies]
            db.store_anomalies(tenant_id=tenant_id, analysis_id=analysis_id, anomalies=anom_dicts)

            db.update_analysis_status(
                analysis_id,
                status="COMPLETED",
                progress_pct=100,
                results=res.to_dict(),
            )
            logger.info(
                "Successfully completed analysis %s: detected %d anomalies",
                analysis_id,
                len(anom_dicts),
            )
            return True
        except Exception as e:
            logger.exception("Analysis job %s failed: %s", analysis_id, e)
            db.update_analysis_status(
                analysis_id,
                status="FAILED",
                progress_pct=100,
                error_message=str(e),
            )
            return False

    def poll_and_run(self) -> None:
        """Main daemon loop."""
        logger.info("DriftSense Worker started. Polling for pending jobs...")
        while self._running:
            # Check for any PENDING analysis across tenants in db
            found_job = False
            with db._lock:
                for a_id, a_rec in list(db.analyses.items()):
                    if a_rec.get("status") == "PENDING":
                        t_id = a_rec["tenant_id"]
                        found_job = True
                        break

            if found_job:
                self.run_job(a_id, t_id)
            else:
                time.sleep(self.poll_interval_sec)

        logger.info("DriftSense Worker gracefully stopped.")


def main() -> None:
    worker = AnalysisWorker()
    worker.poll_and_run()


if __name__ == "__main__":
    main()
