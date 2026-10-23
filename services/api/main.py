"""Main FastAPI application for DriftSense v2 (Phase 11).

Exposes high-performance FinOps Anomaly Detection, Attribution, and Plain-Language
Briefing APIs with tenant isolation, rate limiting readiness, and full OpenAPI documentation.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from services.api.routes.admin import router as admin_router
from services.api.routes.analyses import router as analyses_router
from services.api.routes.anomalies import router as anomalies_router
from services.api.routes.events import router as events_router
from services.api.routes.reports import router as reports_router
from services.api.routes.uploads import router as uploads_router

app = FastAPI(
    title="DriftSense Cloud FinOps Anomaly Detection API",
    description=(
        "Production backend service for multi-cloud FinOps anomaly detection, "
        "root-cause attribution, plain-language executive narratives, and human feedback loops."
    ),
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

# Cross-Origin Resource Sharing (CORS) for Next.js / Web UI
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount functional API routers
app.include_router(uploads_router)
app.include_router(analyses_router)
app.include_router(anomalies_router)
app.include_router(events_router)
app.include_router(reports_router)
app.include_router(admin_router)


@app.get("/health", tags=["Health"])
def health_check() -> dict[str, str]:
    """Basic health check and service readiness endpoint."""
    return {
        "status": "healthy",
        "service": "driftsense-api",
        "version": "2.0.0",
    }


@app.get("/", tags=["Root"])
def root_info() -> dict[str, str]:
    """Root metadata and documentation navigator."""
    return {
        "name": "DriftSense API",
        "version": "2.0.0",
        "documentation": "/docs",
        "status": "operational",
    }
