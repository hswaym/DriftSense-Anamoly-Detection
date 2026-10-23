# DriftSense v2 — Production Operations Runbook & Disaster Recovery Guide

**Document Version:** 2.0.0  
**Target Environment:** Production Cloud (Kubernetes, AWS ECS, or Docker Compose)  
**Classification:** Enterprise SRE & FinOps Operations  
**Audience:** Site Reliability Engineers (SRE), Platform Engineers, FinOps Operators  
**Last Verified:** October 2026 (Phase 14 Enterprise Readiness)

---

## 1. System Topology & Architecture

DriftSense v2 operates as an isolated, multi-tenant cloud FinOps platform composed of four primary runtime components:

```
                  [ Public Ingress / HTTPS TLS 1.3 ]
                                │
                    ┌───────────┴───────────┐
                    ▼                       ▼
          [ FastAPI API Service ]    [ Modern Web UI ]
          (Port 8000, 3+ replicas)   (Static / CDN / Port 3000)
                    │                       
         ┌──────────┼──────────────────────┐
         ▼          ▼                      ▼
  [ PostgreSQL 16 ] [ Redis 7 Queue ] [ Local / S3 Storage ]
  (RLS Enabled)     (Job Broker)      (Encrypted at Rest)
                    │
                    ▼
         [ Celery Worker Pool ]
         (CPU-Optimized Inference)
```

### Component Roles & Resiliency
| Component | Docker Container Name | Scaling Target | Healthcheck Probe |
|---|---|---|---|
| **API Gateway** | `driftsense-api` | Horizontal (HPA 3-10 pods) | `GET /health` (HTTP 200) |
| **Inference Worker** | `driftsense-worker` | Queue-Depth Autoscale (2-8 pods) | `celery inspect ping` |
| **Relational Store** | `driftsense-db` | Primary + Standby Replica | `pg_isready -U postgres` |
| **Task Queue** | `driftsense-redis` | Redis Sentinel / Cluster | `redis-cli ping` |

---

## 2. Environment Variables & Configuration Reference

Store all production configuration in a secure secrets vault (e.g., AWS Secrets Manager, HashiCorp Vault) and inject as container environment variables:

| Variable Name | Default / Example | Description & Security Constraint |
|---|---|---|
| `DATABASE_URL` | `postgresql://user:pass@db:5432/driftsense` | Connection URI with connection pooling parameters. |
| `REDIS_URL` | `redis://redis:6379/0` | Broker URL for Celery async task queue. |
| `DRIFTSENSE_DATA_DIR` | `/var/lib/driftsense/data/uploads` | Path to persistent storage volume for telemetry uploads. |
| `DRIFTSENSE_FEEDBACK_DIR` | `/var/lib/driftsense/data/feedback` | Path to immutable append-only human feedback logs. |
| `DRIFTSENSE_MODELS_DIR` | `/var/lib/driftsense/models` | Path to frozen model artifacts and registry. |
| `DRIFTSENSE_RATE_LIMIT_MAX` | `120` | Maximum allowable requests per sliding window. |
| `DRIFTSENSE_RATE_LIMIT_WINDOW` | `60` | Duration of rate limiting window in seconds. |
| `ALLOW_OFFLINE_RETRAINING` | `0` | Must remain `0` in production to enforce Invariant A13.4. |
| `CORS_ORIGINS` | `https://finops.enterprise.internal` | Strict FQDN of authorized web UI origins. |

---

## 3. Backup, Snapshot, and Disaster Recovery (DR)

### Recovery Objectives
- **Recovery Point Objective (RPO):** $\le 1\text{ hour}$ (Continuous WAL archiving + Hourly snapshots).
- **Recovery Time Objective (RTO):** $\le 15\text{ minutes}$ (Automated container provisioning).

### Automated Backup Procedure
Run via cron daemon or Kubernetes CronJob every 6 hours:

```bash
#!/usr/bin/env bash
set -euo pipefail

BACKUP_TIMESTAMP=$(date -u +"%Y%m%d_%H%M%SZ")
BACKUP_DIR="/mnt/driftsense_backups/${BACKUP_TIMESTAMP}"
mkdir -p "${BACKUP_DIR}"

echo "[INFO] Commencing database dump..."
docker exec -t driftsense-db pg_dump -U driftsense -d driftsense -Fc -f "/tmp/db_${BACKUP_TIMESTAMP}.dump"
docker cp "driftsense-db:/tmp/db_${BACKUP_TIMESTAMP}.dump" "${BACKUP_DIR}/"

echo "[INFO] Archiving telemetry and feedback volumes..."
tar -czf "${BACKUP_DIR}/feedback_events.tar.gz" -C "/var/lib/driftsense/data" feedback
tar -czf "${BACKUP_DIR}/model_registry.tar.gz" -C "/var/lib/driftsense" models

echo "[INFO] Computing SHA-256 integrity checksums..."
sha256sum "${BACKUP_DIR}"/* > "${BACKUP_DIR}/manifest.sha256"

echo "[INFO] Syncing to offsite immutable cloud vault..."
aws s3 sync "${BACKUP_DIR}" "s3://corp-finops-dr-backups/driftsense/${BACKUP_TIMESTAMP}/" --sse aws:kms

echo "[SUCCESS] Backup completed: ${BACKUP_TIMESTAMP}"
```

### Complete Disaster Recovery Restoration Procedure
In the event of total datacenter or cluster loss:

1. **Provision Infrastructure:** Deploy baseline storage volumes and launch `docker compose up -d db redis`.
2. **Download Verified Backup Snapshot:**
   ```bash
   aws s3 sync "s3://corp-finops-dr-backups/driftsense/<SNAPSHOT_ID>/" /tmp/restore/
   cd /tmp/restore && sha256sum -c manifest.sha256
   ```
3. **Restore Database:**
   ```bash
   docker cp "/tmp/restore/db_<SNAPSHOT_ID>.dump" driftsense-db:/tmp/restore.dump
   docker exec -t driftsense-db pg_restore -U driftsense -d driftsense -c --if-exists /tmp/restore.dump
   ```
4. **Restore Model Registry & Human Feedback Logs:**
   ```bash
   tar -xzf /tmp/restore/feedback_events.tar.gz -C /var/lib/driftsense/data/
   tar -xzf /tmp/restore/model_registry.tar.gz -C /var/lib/driftsense/
   ```
5. **Start Application Services & Verify:**
   ```bash
   docker compose up -d api worker frontend
   curl -f http://localhost:8000/health
   curl -f http://localhost:8000/admin/registry
   ```

---

## 4. Incident Response & Troubleshooting Playbooks

### Playbook A: High Memory Usage / Worker OOM
- **Symptoms:** Container exit code 137; Prometheus alert `DriftSenseWorkerMemorySaturation > 85%`.
- **Root Cause:** A tenant uploaded a billing CSV with an extreme number of unaggregated micro-transactions (>5M rows) without pre-filtering.
- **Triage Steps:**
  1. Inspect active task payload:
     ```bash
     docker logs driftsense-worker --tail 200 | grep "Analyzing upload"
     ```
  2. Verify upload file size:
     ```bash
     ls -lh /var/lib/driftsense/data/uploads/
     ```
  3. Mitigation: The engine automatically downsamples or streams chunks in `chunked_io.py`. If worker memory exceeds host limits, scale worker container limit in `docker-compose.yml` to `mem_limit: 4g`.

### Playbook B: Elevated Rate Limiting (HTTP 429 Storms)
- **Symptoms:** Client reports `HTTP 429: Rate limit exceeded` during batch automation or scheduled CI/CD telemetry uploads.
- **Triage Steps:**
  1. Inspect caller IP and Tenant ID in API logs:
     ```bash
     docker logs driftsense-api --tail 100 | grep "429"
     ```
  2. If the request volume is legitimate enterprise telemetry ingestion, temporarily adjust the sliding-window threshold:
     ```bash
     export DRIFTSENSE_RATE_LIMIT_MAX=300
     docker compose restart api
     ```

### Playbook C: Database Connection Pool Exhaustion
- **Symptoms:** API logs report `psycopg2.OperationalError: FATAL: remaining connection slots are reserved for non-replication superuser connections`.
- **Triage Steps:**
  1. Check open connections:
     ```bash
     docker exec -it driftsense-db psql -U driftsense -c "SELECT count(*), state FROM pg_stat_activity GROUP BY state;"
     ```
  2. Ensure connection pooling is active with `max_overflow=10` and `pool_size=20`. Restart API replicas sequentially if leaked connections remain idle.

### Playbook D: Schema or Volume Drift Detected
- **Symptoms:** Alert in `/admin/drift` endpoint indicates `schema_drift=true` or `volume_drift=true`.
- **Triage Steps:**
  1. Check provider schema differences:
     ```bash
     curl -s http://localhost:8000/admin/drift | jq .
     ```
  2. If the cloud vendor added new metadata columns, update the column mapping table in `/uploads/{upload_id}/mapping`. Invariant A13.4 forbids automatic online retraining; any model adjustment must occur through offline Colab re-validation gates.

---

## 5. Zero-Downtime Deployment & Rollback Protocol

1. **Deploy New Version:**
   ```bash
   git pull origin v2-enterprise
   docker compose build api worker
   docker compose up -d --no-deps --scale api=2 --no-recreate api
   sleep 10
   docker compose up -d --no-deps api
   ```
2. **Verify Deployment Health:**
   ```bash
   curl -f http://localhost:8000/health
   uv run pytest tests/test_api_service.py
   ```
3. **Emergency Rollback:**
   ```bash
   git checkout <PREVIOUS_COMMIT_TAG>
   docker compose build api worker
   docker compose up -d
   ```
