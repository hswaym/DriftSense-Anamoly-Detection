# DriftSense v2 — Security Threat Model Outline

**Document Version:** 2.0.0  
**Status:** Approved Security Baseline  
**Methodology:** STRIDE (Spoofing, Tampering, Repudiation, Information Disclosure, Denial of Service, Elevation of Privilege)  
**Target Architecture:** Multi-Tenant Web API, Background Ingestion Worker, and PostgreSQL Storage Layer.

---

## 1. System Scope & Trust Boundaries

The DriftSense v2 architecture handles sensitive multi-cloud enterprise billing logs and deployment metadata.

```
[ External Client / Browser ] 
        │
   (HTTPS / TLS 1.3)
        ▼
[ API Gateway / Reverse Proxy ] ────────── (Trust Boundary 1)
        │
   (JWT with tenant_id)
        ▼
[ FastAPI Application Core ] ───────────── (Trust Boundary 2)
   ┌────┴──────────────────────────┐
   ▼                               ▼
[ Redis / Celery Workers ]   [ PostgreSQL (RLS Enabled) ] ── (Trust Boundary 3)
   │
[ S3 / Object Storage (Encrypted at Rest) ]
```

---

## 2. Threat Analysis Matrix (STRIDE)

| Threat ID | Threat Category | Threat Description | Attack Vector | Potential Impact | Mitigation Strategy in DriftSense v2 |
|---|---|---|---|---|---|
| **T-01** | Information Disclosure | **Cross-Tenant Data Leakage** | Malicious user crafts an API request specifying another tenant's `incident_id` or query filter. | Exposure of proprietary cloud infrastructure, spend figures, and vendor agreements. | **Mandatory DB-Level RLS:** PostgreSQL Row Level Security enforces `WHERE tenant_id = current_setting('app.current_tenant_id')` on all queries. JWT validation binds context at entry. |
| **T-02** | Denial of Service | **Decompression & Resource Bomb (Zip Bomb)** | Attacker uploads highly compressed multi-gigabyte gzip/zip billing archive. | Worker memory exhaustion, disk fill-up, worker crash, denial of service for other tenants. | **Streaming Chunk Limits:** Strict upload size limit ($250\text{ MB}$ raw, $50\text{ MB}$ compressed). Decompression streams through an uncompressed byte counter with immediate abort if ratio exceeds $10:1$ or size exceeds threshold. |
| **T-03** | Tampering | **Formula / CSV Injection in Exports** | Billing record tag or resource description contains spreadsheet formula (e.g. `=cmd|' /C calc'!A0`). | Remote code execution on analyst workstation when opening exported CSV/Excel incident report. | **Sanitization Filter:** Automated prefix escaping on all CSV exporter fields. Any cell beginning with `=`, `+`, `-`, `@`, `\t`, or `\r` is prepended with a single quote `'` and sanitized. |
| **T-04** | Tampering / Repudiation | **Adversarial Baseline Poisoning** | Attacker slowly inflates historical billing entries over weeks to artificially widen conformal bounds. | Suppresses anomaly detection on future intentional data exfiltration or crypto-mining attacks. | **Robust Robustness & Rolling Trimming:** Forecast models employ median-based rolling aggregations and Huber loss / robust scalers that limit the influence of high-magnitude leverage points. |
| **T-05** | Elevation of Privilege | **Broken Object-Level Authorization (BOLA)** | User with `Analyst` role attempts to alter tenant sensitivity thresholds or delete audit logs. | Unauthorized sensitivity changes or destruction of incident history. | **Role-Based Access Control (RBAC):** Strictly enforced permission scopes (`read:incidents`, `write:feedback`, `admin:config`) validated at FastAPI router dependencies. |
| **T-06** | Information Disclosure | **Model Inversion / Topology Extraction** | Attacker queries attribution API with synthetic anomalies to reverse-engineer proprietary cloud topology. | Exposure of internal service names, deployment schedules, and infrastructure architecture. | **Rate Limiting & Masked Exports:** API rate limiting (60 requests/min per API key). Research and diagnostic SHAP features mask internal identifiers unless user possesses `admin:security` permissions. |
| **T-07** | Spoofing | **Unauthenticated Event Ingestion** | Attacker injects fraudulent deployment events into the operational event stream. | Skews attribution scoring toward false decoy events, masking real intrusions. | **HMAC Webhook Verification:** All CI/CD and deployment webhook ingestion endpoints require cryptographic HMAC-SHA256 signature verification matching shared secrets. |

---

## 3. Data Protection & Cryptographic Controls

1. **Data in Transit:** TLS 1.3 mandatory on all external connections; internal service-to-service communication within Docker/VPC isolated by private virtual network.
2. **Data at Rest:** 
   * Database storage volumes encrypted using AES-256 (PostgreSQL transparent data encryption / encrypted EBS).
   * Sensitive API keys, cloud provider credentials, and OAuth tokens stored hashed using Argon2id or encrypted using envelope encryption with dedicated master key.
3. **Audit Logging & Immutability:** All incident feedback, sensitivity threshold changes, and user access records are written to an append-only audit table with cryptographic hash chaining to detect tampering.

---

## 4. Security Verification Plan (Phase 14 Gate)

Before any public release, the security architecture must pass:
* **Automated SAST & Secret Scanning:** Clean scan with zero high/critical vulnerabilities.
* **DAST API Security Suite:** OWASP Top 10 automated test run validating BOLA, input sanitization, and auth boundaries.
* **Multi-Tenant Penetration Fixture:** Automated unit tests attempting cross-tenant injection and RLS bypass must reliably exit with HTTP 403 / 404.
