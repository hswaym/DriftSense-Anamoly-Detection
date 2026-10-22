# DriftSense v2 — Architectural & Research Decision Log (D1–D8)

**Document Version:** 2.0.0  
**Status:** Approved Architectural Baseline  
**Date:** 2026-10-21

This document formally records the architectural decisions D1 through D8 that govern the transition from DriftSense v1 (research prototype) to DriftSense v2 (enterprise-grade data product).

---

## Decision D1: Rule G3 Amendment (In-App Training vs. Colab)

* **Context:** In DriftSense v1, Rule G3 strictly forbade in-app model training to preserve reproducibility. However, enterprise product users require uploading billing files and receiving calibrated anomaly scores without executing manual notebook pipelines.
* **Options Considered:**
  1. *Maintain strict Rule G3:* Require all model fitting to occur manually in Google Colab notebooks. (Unusable for product end-users).
  2. *Full in-app heavy training:* Train deep neural nets and multi-seed models directly inside the web server process. (Prone to web process timeouts and memory crashes).
  3. *Tiered execution policy (Adopted):*
     * **Research Training:** Heavy multi-seed training, baseline ablations, and large-scale experiments remain strictly Colab-driven via `driftsense` CLI commands.
     * **Product Runtime:** Light CPU-only per-tenant fitting (conformal quantile calibrations, Ridge/LightGBM inference) runs asynchronously inside background workers with strict timeout budgets ($\le 120$s).
* **Outcome:** **ACCEPTED (Tiered Execution Policy).**
* **Consequences:** Rule G3 is formally amended for product-runtime background workers while preserving zero-trust Colab discipline for research artifacts.

---

## Decision D2: Target Application Technology Stack

* **Context:** DriftSense v1 used Streamlit for its interactive dashboard. Streamlit is suitable for research demonstrations but lacks responsive state management, role-based access control, sub-second client transitions, and enterprise design aesthetics.
* **Options Considered:**
  1. *Retain Streamlit only.*
  2. *Rewrite everything in pure Django or Flask templates.*
  3. *Decoupled Modern Stack (Adopted):*
     * **Backend:** FastAPI (Python 3.11) with Pydantic v2 data validation, SQLModel/PostgreSQL with Row Level Security, Celery/Redis for background jobs.
     * **Frontend:** Next.js 14 (App Router) + TypeScript + Tailwind CSS / Vanilla CSS + Shadcn/UI for accessible, modern UI.
     * **Research Console:** Streamlit preserved in `app/` as a frozen research inspection console.
* **Outcome:** **ACCEPTED (Decoupled Next.js + FastAPI).**
* **Consequences:** Clear boundary between statistical backend logic and rich accessible user presentation.

---

## Decision D3: Deployment Target & Infrastructure Architecture

* **Context:** DriftSense must be verifiable by academic evaluators and runnable in diverse enterprise environments without mandatory multi-cloud cloud bills.
* **Options Considered:**
  1. *Kubernetes (EKS/GKE) cluster manifests only.* (High operational overhead for evaluators).
  2. *Single monolithic script.* (No background worker or multi-tenant database).
  3. *Local Docker Compose (Adopted):* Multi-container composition (`web`, `api`, `worker`, `db`, `redis`) with one-line startup (`docker compose up --build`).
* **Outcome:** **ACCEPTED (Docker Compose with Production Container Images).**
* **Consequences:** Evaluators can inspect and run the entire product locally in under 3 minutes.

---

## Decision D4: Real Billing Data Access & Sourcing Strategy

* **Context:** High-fidelity real cloud billing data containing documented, un-redacted production outages is rarely public due to corporate confidentiality.
* **Options Considered:**
  1. *Request confidential enterprise customer data.* (Blocked by NDA and compliance).
  2. *Rely purely on synthetic datasets.* (Fails realism and external validity).
  3. *Hybrid S1–S7 Suite (Adopted):*
     * **S1:** Real anonymized FinOps Foundation FOCUS sandbox datasets (AWS/GCP/OCI).
     * **S3/S4:** Real production workload traces (Azure VM traces / Alibaba) priced against public provider rate cards.
     * **S7:** Configurable synthetic scenarios with injected faults and realistic decoys for controlled benchmark validation.
* **Outcome:** **ACCEPTED (Hybrid Suite).**
* **Consequences:** Avoids dependency on proprietary customer data while ensuring realistic multi-tenant data dynamics.

---

## Decision D5: Supported Billing Provider Scope

* **Context:** Enterprises use heterogeneous cloud providers with disparate billing export schemas.
* **Options Considered:**
  1. *AWS only.*
  2. *Provider-specific custom tables for every vendor.*
  3. *FOCUS as Canonical Layer with Vendor Adapters (Adopted):*
     * Support FOCUS 1.0 through 1.4 specifications.
     * Dedicated ingestion adapters for AWS CUR 2.0, Azure Cost Management Export, and GCP BigQuery Billing Export.
* **Outcome:** **ACCEPTED (FOCUS Canonical + Provider Adapters).**
* **Consequences:** New cloud providers can be onboarded simply by implementing a single FOCUS translation adapter.

---

## Decision D6: Fresh Holdout Quarantine Strategy

* **Context:** In DriftSense v1, test partition $D_{\text{test}}$ was evaluated during development (DEC-016), contaminating it for subsequent tuning.
* **Options Considered:**
  1. *Re-use v1 test partition with new seeds.* (Partial contamination remains).
  2. *Cross-validation without holdout.* (Vulnerable to hyperparameter over-fitting).
  3. *Strictly Quarantined Fresh Holdout (Adopted):*
     * Holdout partition $D_{\text{holdout}}$ is generated from completely unobserved date ranges, fresh multi-cloud sources, and new fault generator seeds.
     * Evaluated strictly once in Phase 15.
     * Manifest enforce `"holdout_touched": false` for all intermediate runs.
* **Outcome:** **ACCEPTED (Fresh Quarantined Holdout).**
* **Consequences:** True out-of-sample statistical validity for all final research claims.

---

## Decision D7: Authentication & Multi-Tenant Authorization Model

* **Context:** Enterprise SaaS deployment requires strict tenant isolation and corporate SSO readiness.
* **Options Considered:**
  1. *Single-user mode without auth.* (Unsuitable for enterprise deployment).
  2. *Complex proprietary LDAP implementation.* (High setup friction).
  3. *OIDC-ready JWT Architecture (Adopted):*
     * Stateless JWT bearer tokens with standard claims (`sub`, `tenant_id`, `roles`).
     * Included zero-configuration local developer mode (`demo-tenant`) for instant testing.
     * Database-level Row Level Security (RLS) enforcing `tenant_id` on every query.
* **Outcome:** **ACCEPTED (OIDC JWT + Dev Mode + DB RLS).**
* **Consequences:** Instant evaluator setup with seamless enterprise SSO integration path.

---

## Decision D8: Primary Evaluation Audience & Scope Alignment

* **Context:** DriftSense serves two distinct audiences: academic evaluators assessing methodological rigor, and FinOps practitioners evaluating business utility.
* **Options Considered:**
  1. *Optimize exclusively for academic data science benchmark.* (Loses business value).
  2. *Build an executive BI dashboard with heuristic rules.* (Loses research rigor).
  3. *Dual-Track Design (Adopted):*
     * Methodological track with formal pre-registration, conformal prediction, and zero-trust audit trails.
     * Enterprise product track with plain-language interfaces, actionable alert triage, and progressive disclosure toggles.
* **Outcome:** **ACCEPTED (Dual-Track Research & Product Alignment).**
* **Consequences:** Satisfies high-rigor research review while delivering immediate executive usability.
