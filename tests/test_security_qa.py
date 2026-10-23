"""Security QA, Tenant Isolation, and Upload Abuse Test Suite for DriftSense v2 (Phase 14).

Verifies STRIDE threat model mitigations:
1. Security Headers: Enforces defense-in-depth headers on all API responses.
2. Rate Limiting: Sliding-window burst mitigation with HTTP 429 and Retry-After headers.
3. Tenant Isolation & Header Fuzzing: Rejection of path traversal, SQLi tokens, oversized headers.
4. Upload Abuse Rejection: Magic-byte inspection, file size bounds, traversal filenames.
5. Cross-Tenant Data Isolation: Strict isolation between distinct tenant namespaces.
6. CSV Formula Injection Neutralization: Escaping DDE formula triggers (=, +, -, @, \\t, \\r).
"""

from __future__ import annotations

import io
import pytest
from fastapi.testclient import TestClient

from services.api.database import db
from services.api.main import app
from services.api.security import (
    MAX_TENANT_ID_LENGTH,
    MAX_UPLOAD_SIZE_BYTES,
    InMemoryRateLimiter,
    rate_limiter,
    sanitize_csv_cell,
    sanitize_filename,
)

client = TestClient(app)


@pytest.fixture(autouse=True)
def reset_state():
    """Clear database and rate limiter records before each test."""
    with db._lock:
        db.uploads.clear()
        db.analyses.clear()
        db.anomalies.clear()
        db.events.clear()
    rate_limiter.reset()


def test_enterprise_security_headers():
    """Verify all defense-in-depth security headers are present on API responses."""
    res = client.get("/health")
    assert res.status_code == 200

    headers = res.headers
    assert headers.get("X-Content-Type-Options") == "nosniff"
    assert headers.get("X-Frame-Options") == "DENY"
    assert headers.get("X-XSS-Protection") == "1; mode=block"
    assert "max-age=" in headers.get("Strict-Transport-Security", "")
    assert headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"
    assert "default-src 'self'" in headers.get("Content-Security-Policy", "")
    assert "frame-ancestors 'none'" in headers.get("Content-Security-Policy", "")
    assert "geolocation=()" in headers.get("Permissions-Policy", "")


def test_rate_limiting_enforcement():
    """Verify rate limiter blocks burst requests exceeding thresholds with HTTP 429."""
    test_limiter = InMemoryRateLimiter(max_requests=3, window_seconds=10)

    # Key test
    allowed1, _ = test_limiter.check("ip_test:tenant_a")
    allowed2, _ = test_limiter.check("ip_test:tenant_a")
    allowed3, _ = test_limiter.check("ip_test:tenant_a")
    allowed4, retry_after = test_limiter.check("ip_test:tenant_a")

    assert allowed1 is True
    assert allowed2 is True
    assert allowed3 is True
    assert allowed4 is False
    assert retry_after > 0

    # Test via API middleware with temporary tight threshold
    orig_max = rate_limiter.max_requests
    try:
        rate_limiter.max_requests = 2
        r1 = client.get("/anomalies", headers={"X-Tenant-ID": "tenant_flood"})
        assert r1.status_code in (200, 404)

        r2 = client.get("/anomalies", headers={"X-Tenant-ID": "tenant_flood"})
        assert r2.status_code in (200, 404)

        r3 = client.get("/anomalies", headers={"X-Tenant-ID": "tenant_flood"})
        assert r3.status_code == 429
        assert "Rate limit exceeded" in r3.json()["detail"]
        assert "Retry-After" in r3.headers

        # Health endpoint should be exempt from rate limiting
        r_health = client.get("/health")
        assert r_health.status_code == 200
    finally:
        rate_limiter.max_requests = orig_max
        rate_limiter.reset()


@pytest.mark.parametrize(
    "malicious_tenant",
    [
        "../../etc/passwd",
        "..\\..\\windows\\system32",
        "../../../",
        "   ",
        "!!!@@@###$$$",
        "A" * (MAX_TENANT_ID_LENGTH + 10),  # Oversized header
    ],
)
def test_tenant_id_fuzzing_and_rejection(malicious_tenant: str):
    """Verify malformed, traversal, or oversized tenant identifiers are rejected with HTTP 400."""
    res = client.get("/anomalies", headers={"X-Tenant-ID": malicious_tenant})
    assert res.status_code == 400
    detail = res.json()["detail"]
    assert "Invalid X-Tenant-ID" in detail or "exceeds maximum length" in detail


def test_cross_tenant_isolation_enforcement():
    """Ensure Tenant Attacker cannot access, list, or download Tenant Victim resources."""
    # Seed Tenant Victim upload
    victim_upload = {
        "upload_id": "upl_victim_999",
        "tenant_id": "tenant_victim",
        "filename": "victim_spend.csv",
        "file_path": "data/uploads/victim_spend.csv",
        "file_size_bytes": 1024,
        "detected_provider": "FOCUS",
        "column_names": ["ChargePeriodStart", "BilledCost"],
        "column_mapping": {},
        "row_count_estimate": 500,
        "created_at_utc": "2026-03-01T00:00:00Z",
    }
    with db._lock:
        db.uploads["upl_victim_999"] = victim_upload

    # 1. Attacker attempts to list uploads
    attacker_list = client.get("/uploads", headers={"X-Tenant-ID": "tenant_attacker"})
    assert attacker_list.status_code == 200
    assert len(attacker_list.json()) == 0

    # 2. Attacker attempts direct access to victim upload
    attacker_get = client.get("/uploads/upl_victim_999", headers={"X-Tenant-ID": "tenant_attacker"})
    assert attacker_get.status_code == 404

    # 3. Victim access succeeds
    victim_get = client.get("/uploads/upl_victim_999", headers={"X-Tenant-ID": "tenant_victim"})
    assert victim_get.status_code == 200
    assert victim_get.json()["upload_id"] == "upl_victim_999"


def test_filename_traversal_sanitization():
    """Verify filename sanitizer strips relative paths, directory separators, and control characters."""
    assert sanitize_filename("../../../../etc/passwd.csv") == "passwd.csv"
    assert sanitize_filename("..\\..\\windows\\system32\\cmd.exe.csv") == "cmd.exe.csv"
    assert sanitize_filename("normal_file.parquet") == "normal_file.parquet"
    assert sanitize_filename("test space;name.csv") == "test_space_name.csv"

    # Completely illegal or hidden filenames get randomized fallback
    fallback = sanitize_filename(".hidden")
    assert fallback.startswith("upload_")
    assert fallback.endswith(".csv")


@pytest.mark.parametrize(
    "bad_bytes,label",
    [
        (b"MZ\x90\x00\x03\x00\x00\x00", "Windows PE Executable"),
        (b"\x7fELF\x02\x01\x01\x00", "Linux ELF Binary"),
        (b"\xca\xfe\xba\xbe\x00\x00\x00", "Java Class / Mach-O"),
        (b"\xfe\xed\xfa\xce\x00\x00\x00", "Mach-O Binary"),
        (b"PK\x03\x04\x14\x00\x08\x00", "ZIP Archive / Zip Bomb"),
    ],
)
def test_upload_abuse_executable_magic_rejection(bad_bytes: bytes, label: str):
    """Verify executables and archives disguised as CSV files are strictly rejected."""
    file_payload = bad_bytes + b",col2,col3\n1,2,3\n"
    res = client.post(
        "/uploads",
        files={"file": ("disguised.csv", file_payload, "text/csv")},
        headers={"X-Tenant-ID": "tenant_safe"},
    )
    assert res.status_code == 400, f"Failed to reject {label}"
    assert "Executable or archive magic bytes detected" in res.json()["detail"]


def test_upload_abuse_oversized_payload_rejection():
    """Verify oversized payloads exceeding MAX_UPLOAD_SIZE_BYTES trigger HTTP 413."""
    oversized = b"A" * (MAX_UPLOAD_SIZE_BYTES + 1024)
    res = client.post(
        "/uploads",
        files={"file": ("oversized.csv", oversized, "text/csv")},
        headers={"X-Tenant-ID": "tenant_safe"},
    )
    assert res.status_code == 413
    assert "Upload exceeds maximum allowable size" in res.json()["detail"]


@pytest.mark.parametrize(
    "raw_input,expected_sanitized",
    [
        ("=cmd|'/C calc'!A0", "'=cmd|'/C calc'!A0"),
        ("+12345", "'+12345"),
        ("-12345", "'-12345"),
        ("@SUM(A1:A10)", "'@SUM(A1:A10)"),
        ("\tTabbedCell", "'\tTabbedCell"),
        ("\rCarriageReturn", "'\rCarriageReturn"),
        ("StandardText", "StandardText"),
        ("AmazonEC2", "AmazonEC2"),
        (123.45, "123.45"),
        (None, ""),
    ],
)
def test_csv_formula_injection_sanitization(raw_input, expected_sanitized):
    """Verify formula injection prefixes are safely escaped with single quote."""
    assert sanitize_csv_cell(raw_input) == expected_sanitized
