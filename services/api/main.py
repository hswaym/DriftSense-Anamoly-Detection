"""Main FastAPI application for DriftSense v2 (Phase 11).

Exposes high-performance FinOps Anomaly Detection, Attribution, and Plain-Language
Briefing APIs with tenant isolation, rate limiting readiness, and full OpenAPI documentation.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from services.api.routes.admin import router as admin_router
from services.api.routes.analyses import router as analyses_router
from services.api.routes.anomalies import router as anomalies_router
from services.api.routes.events import router as events_router
from services.api.routes.reports import router as reports_router
from services.api.routes.uploads import router as uploads_router
from services.api.security import rate_limiter


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Enforces enterprise defense-in-depth security headers on all HTTP responses."""

    async def dispatch(self, request: Request, call_next):
        response: Response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Content-Security-Policy"] = "default-src 'self'; frame-ancestors 'none';"
        response.headers["Permissions-Policy"] = "geolocation=(), camera=(), microphone=()"
        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Protects against burst floods and denial-of-service abuse via sliding-window tracker."""

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if path in ("/health", "/docs", "/redoc", "/openapi.json"):
            return await call_next(request)

        client_host = request.client.host if request.client else "127.0.0.1"
        tenant_id = request.headers.get("X-Tenant-ID", "anonymous")
        key = f"{client_host}:{tenant_id}"

        allowed, retry_after = rate_limiter.check(key)
        if not allowed:
            return JSONResponse(
                status_code=429,
                content={
                    "detail": "Rate limit exceeded. Please retry after specified duration.",
                    "retry_after_seconds": retry_after,
                },
                headers={"Retry-After": str(retry_after)},
            )
        return await call_next(request)


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

# Enterprise Security Headers and Rate Limiting
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(RateLimitMiddleware)

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
