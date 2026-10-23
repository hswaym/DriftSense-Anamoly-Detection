# DriftSense v2 — Comprehensive STRIDE Security Threat Model

**Document Version:** 2.0.0  
**Classification:** Enterprise Security Baseline  
**Evaluation Standard:** STRIDE (Spoofing, Tampering, Repudiation, Information Disclosure, Denial of Service, Elevation of Privilege)  
**Target Systems:** FastAPI Backend Service (`services/api/`), Background Inference Worker (`services/worker/`), React Modern Web UI (`frontend/`), and PostgreSQL Data Layer.  
**Verification Date:** October 2026  
**Status:** APPROVED & VERIFIED (Phase 14 Gate)

---

## 1. System Scope & Architecture Overview

DriftSense v2 processes sensitive enterprise multi-cloud billing logs (FOCUS 1.0, AWS CUR, Azure Cost Details, GCP Cloud Billing), deployment and change events, and executive financial summaries.

```
+-------------------------------------------------------------------------------+
|                             Public Client Tier                                |
|  [ Modern Web UI (React/Vite) ]               [ Enterprise FinOps Analyst ]   |
+-------------------------------------------------------------------------------+
                                     │
                             (HTTPS / TLS 1.3)
                                     ▼
══════════════════════════════════════════════════════════════════ [ TRUST BOUNDARY 1 ]
+-------------------------------------------------------------------------------+
|                       Ingress & Reverse Proxy Layer                           |
|  - TLS Termination & HSTS Enforcement                                         |
|  - Edge Security Headers (CSP, X-Frame-Options, HSTS, Nosniff)                 |
+-------------------------------------------------------------------------------+
                                     │
                             (HTTP / Internal)
                                     ▼
══════════════════════════════════════════════════════════════════ [ TRUST BOUNDARY 2 ]
+-------------------------------------------------------------------------------+
|                     DriftSense FastAPI Application Core                       |
|  - RateLimitingMiddleware (Sliding-window request flood protection)           |
|  - SecurityHeadersMiddleware (Defense-in-depth response headers)              |
|  - Tenant Context Resolution (Strict Regex ^[a-zA-Z0-9_\-]+$)                 |
|  - Magic-Byte & Executable Upload Inspector (Rejects PE, ELF, Mach-O, ZIP)    |
|  - CSV DDE Formula Sanitization Filter                                        |
+-------------------------------------------------------------------------------+
                  │                                            │
        (Job Dispatch / IPC)                           (SQL / Async Engine)
                  ▼                                            ▼
══════════════════════════════════════════════════════════════════ [ TRUST BOUNDARY 3 ]
+----------------------------------+          +----------------------------------+
|    Background Inference Worker   |          |  PostgreSQL / Disk Storage Layer |
|  - Conformal Prediction Engine   |          |  - Tenant-Scoped Directory Trees |
|  - Multi-Layer Attribution Graph |          |  - Row-Level Security Scoping    |
|  - Anti-Online-Retraining Guard  |          |  - Encrypted Volume at Rest      |
+----------------------------------+          +----------------------------------+
```

---

## 2. Trust Boundaries

1. **Trust Boundary 1 (Client to Ingress):**
   - Untrusted internet traffic crossing into the enterprise perimeter.
   - Primary risks: Man-in-the-Middle (MitM), eavesdropping, packet tampering.
   - Controls: TLS 1.3 mandatory; `Strict-Transport-Security: max-age=31536000; includeSubDomains`.

2. **Trust Boundary 2 (Ingress to FastAPI Application):**
   - Public HTTP payload crossing into application business logic.
   - Primary risks: Broken Object-Level Authorization (BOLA), tenant spoofing, CSV formula injection, rate abuse / DoS, malicious binary upload.
   - Controls: `RateLimitMiddleware`, strict tenant header validation, magic byte filtering, input schema validation via Pydantic.

3. **Trust Boundary 3 (Application to Storage & Inference Workers):**
   - Application service interacting with persistence stores and compute engines.
   - Primary risks: Path traversal during disk storage, cross-tenant file collision, unauthorized online retraining.
   - Controls: Base storage directory path validation, tenant-isolated subdirectories (`data/uploads/<tenant_id>/`), anti-online-retraining runtime assertions.

---

## 3. STRIDE Threat Analysis & Mitigation Matrix

| Threat ID | Category | Threat Scenario | Attack Vector & Impact | DriftSense v2 Mitigation Strategy | Verification Status |
|---|---|---|---|---|---|
| **T-01** | Information Disclosure | **Cross-Tenant Data Exfiltration** | Attacker crafts an API query requesting another tenant's `upload_id`, `analysis_id`, or `anomaly_id`. | Mandatory Tenant Scoping on all database queries (`db.get_upload`, `db.get_anomalies_for_tenant`). Requests without matching tenant return `404 Not Found`. | **VERIFIED** (`test_cross_tenant_isolation_enforcement`) |
| **T-02** | Denial of Service | **Decompression & Resource Bomb** | Attacker uploads an archive or multi-gigabyte disguised payload to exhaust worker memory. | Hard upload ceiling ($50\text{ MB}$), file extension allowlist (`.csv`, `.parquet`), and magic-byte inspection blocking ZIP/JAR archives. | **VERIFIED** (`test_upload_abuse_oversized_payload_rejection`, `test_upload_abuse_executable_magic_rejection`) |
| **T-03** | Tampering | **Formula / CSV Injection (DDE)** | Malicious service name or tag contains spreadsheet formula (e.g. `=cmd\|'/C calc'!A0`). | Automated prefix neutralization via `sanitize_csv_cell`. Any cell starting with `=`, `+`, `-`, `@`, `\t`, or `\r` is escaped with a leading single quote `'`. | **VERIFIED** (`test_csv_formula_injection_sanitization`) |
| **T-04** | Tampering / Repudiation | **Baseline Poisoning & Drift Corruption** | Adversary injects fabricated spending records over time to widen anomaly prediction bands. | Robust Rolling Median baselines with Huber quantile estimation; model registry version freezing; strict prohibition of unauthenticated feedback. | **VERIFIED** (A13.4 Anti-Online Retraining Invariant) |
| **T-05** | Elevation of Privilege | **Tenant Header Manipulation / Traversal** | Attacker injects path traversal sequences (e.g. `../../etc/passwd`) or SQLi tokens in `X-Tenant-ID`. | Strict alphanumeric validation: regex `^[a-zA-Z0-9_\-]+$` with a 64-character maximum length limit; invalid inputs rejected with `HTTP 400`. | **VERIFIED** (`test_tenant_id_fuzzing_and_rejection`) |
| **T-06** | Denial of Service | **API Flooding & Brute-Force Abuse** | Distributed client attempts rapid requests to exhaust API thread pools or inference resources. | Integrated `RateLimitMiddleware` with thread-safe sliding window tracking; throttles excess requests with `HTTP 429` and `Retry-After` headers. | **VERIFIED** (`test_rate_limiting_enforcement`) |
| **T-07** | Spoofing | **Unauthenticated Change Event Ingestion** | Attacker injects fraudulent deployment events to manipulate attribution scoring. | Operational event ingestion requires authenticated tenant context; foreign service keys are rejected with validation errors. | **VERIFIED** (`test_event_registration`) |
| **T-08** | Information Disclosure | **Host Header Injection & Clickjacking** | Attacker embeds the DriftSense UI inside an iframe to capture credentials or financial data. | Enforced HTTP headers: `X-Frame-Options: DENY`, `Content-Security-Policy: frame-ancestors 'none'`, `X-Content-Type-Options: nosniff`. | **VERIFIED** (`test_enterprise_security_headers`) |
| **T-09** | Tampering | **Path Traversal in Upload Filenames** | Attacker specifies `../../../../etc/shadow` as the uploaded filename to overwrite host system files. | `sanitize_filename` uses `Path(filename).name` and strips non-alphanumeric characters, falling back to secure random hashes if empty or hidden. | **VERIFIED** (`test_filename_traversal_sanitization`) |
| **T-10** | Tampering | **Online Retraining in Production** | Accidental or malicious invocation of model training endpoints modifying production weights. | Invariant A13.4 enforced: `guard_against_online_retraining()` explicitly throws `RuntimeError` and returns `HTTP 403 Forbidden` unless explicit offline flag is set. | **VERIFIED** (`test_anti_online_retraining_invariant`) |

---

## 4. Cryptographic Controls & Data Protection

1. **Data in Transit:**
   - External traffic terminated via TLS 1.3 with AES-256-GCM cipher suites.
   - Internal microservice traffic isolated within dedicated Docker bridge networks.

2. **Data at Rest:**
   - Database volumes encrypted at rest via storage volume encryption (AES-256).
   - Tenant isolation enforced both logically (database query predicates) and physically on disk (`data/uploads/<tenant_id>/`).

3. **Audit Trail & Integrity:**
   - Every human feedback action and model registry transition is timestamped and recorded in immutable append-only JSON stores (`data/feedback/feedback_events.jsonl`).
   - Ground truth segregation enforced: synthetic benchmarks are strictly quarantined and prohibited from human feedback storage.

---

## 5. Residual Risk Assessment & Acceptance Matrix

| Risk ID | Residual Risk Description | Inherent Likelihood | Inherent Severity | Residual Severity | Accepted Risk Justification & Operational Safeguards |
|---|---|---|---|---|---|
| **RR-01** | Development In-Memory Database Mode | Low | Medium | **Low** | In standalone dev/test mode, an in-memory repository with thread locking is used. In production deployment, PostgreSQL with Row-Level Security (RLS) is specified per `docker-compose.yml`. |
| **RR-02** | Local Client-Side Dataset Storage in Demo Mode | Very Low | Low | **Low** | Demo datasets bundled in the frontend are sanitized synthetic data (`frontend/src/data/sampleDataset.js`) with zero PII or real infrastructure credentials. |
| **RR-03** | Upstream Dependency CVEs (e.g. transitive scientific libraries) | Medium | Medium | **Low** | Dependencies audited via `pip-audit` and `npm audit`; all critical packages pinned in lockfiles; standard policy prohibits automatic major version upgrades without validation. |

---

## 6. Verification Summary

All 10 threat scenarios outlined in this STRIDE model have been subjected to automated unit and integration tests in `tests/test_security_qa.py` and `tests/test_api_service.py`. Zero unresolved high or critical vulnerabilities exist.
