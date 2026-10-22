# DriftSense v2 — Traceability Matrix

**Document Version:** 2.0.0  
**Status:** Approved Specification  
**Scope:** Forensic Audit Hypotheses (H1–H7), B2 Defects, User Stories, and Design Requirements Mappings.

---

## 1. Overview & Purpose

This matrix establishes 100% end-to-end traceability between the defects and limitations identified in the DriftSense v1 forensic audit (Section B2 of the Master Prompt Pack) and the binding architectural requirements, design decisions, and verification tests of DriftSense v2.

---

## 2. Forensic Audit (B2 Hypotheses H1–H7) to v2 Architecture Mapping

| Item | v1 Audit Finding (Evidence) | Root Cause in v1 | v2 Architectural Solution | Primary v2 Document | Verification Test Plan |
|---|---|---|---|---|---|
| **H1: Target Leakage** | `BilledCost` was Rank 1 feature with 48.18% SHAP importance predicting `EffectiveCost`. | `feature_cols` included contemporaneous cost column at timestamp $t$. | **Strict Feature Timing:** All contemporaneous cost metrics (`BilledCost`, `ListCost`) are banned from Mode A features. Strict `known_at_prediction_time` flag enforced. | `docs/v2/research_spec.md`, `docs/v2/data_contracts.md` | `tests/test_leakage.py` scanning feature definitions against timestamp $t$. |
| **H2: Usage Conditioning Blind Spot** | Conditioning on `ConsumedQuantity` at time $t$ masked usage runaways ($0\%$ volume detection). | Anomaly defined strictly as cost given current usage, missing volume spikes. | **Decoupled Dual-Mode Forecasting:**<br>• **Mode A (History-Expected):** Detects usage runaways.<br>• **Mode B (Usage-Expected):** Detects rate/price shifts.<br>• **VPM Decomposition:** Separates Volume from Price. | `docs/v2/research_spec.md`, `docs/v2/product_requirements.md` | Pre-registered Hypothesis H-B test suite on synthetic volume vs. rate fault injections. |
| **H3: Circular Attribution Evaluation** | 97.87% Top-1 attribution achieved because candidate event pool contained only the true injected faults. | Attribution pool lacked decoys, confounders, and noise. | **Realistic Event Attribution & Abstention:** Candidate pool includes 3:1 non-injected decoys and concurrent changes. System includes an explicit **Abstention Gate** when evidence is weak. | `docs/v2/research_spec.md`, `docs/v2/data_contracts.md` | Pre-registered Hypothesis H-C test on decoy-injected evaluation runs. |
| **H4: Easy Detection Setting** | Injected faults were large, abrupt step functions with 0.00h detection delay. | Fault generator lacked realistic drift patterns, small magnitudes, and intermittency. | **Scenario Generator v2:** Implements gradual ramp-up drift, subtle margin shifts ($1.25\times$), level shifts, and intermittent spikes across multiple service tiers. | `docs/v2/research_spec.md`, `docs/v2/evaluation_protocol.md` | Benchmarking detection delay and sensitivity across subtle magnitude tiers. |
| **H5: Alert Rate Mischaracterization** | Claimed "FPR 0.16%" was merely an alert rate on unlabeled data with unknown true anomalies. | Alert frequency on unlabeled series was equated to statistical false positive rate. | **Conformal Calibration & Split Tracks:**<br>• Labeled synthetic track reports true FPR/Precision.<br>• Unlabeled track reports "Alert Rate per 1,000 series-hours".<br>• Conformal prediction intervals guarantee nominal coverage. | `docs/v2/evaluation_protocol.md`, `docs/v2/plain_language_glossary.md` | Statistical test of empirical coverage on $D_{\text{val}}$ and fresh holdout. |
| **H6: Dataset Provenance & Discontinuity** | 10,000-row sample mixed providers and discontinuous time chunks. | Reliance on a single unverified sample file without lineage. | **Multi-Source S1–S7 Suite:** Explicit selection of verified FinOps Foundation FOCUS sandboxes, real workload traces (Azure/Alibaba), and documented acquisition scripts. | `docs/v2/data_contracts.md`, `docs/v2/dataset_decision_report.md` | Automated data quality and time-continuity validator in Phase 3. |
| **H7: Unsourced Benchmarks** | "Industry avg FPR ~5–10%" and "Unsupervised Point-F1 ~0.40" were unsourced claims. | Informal marketing metrics included in research summaries. | **Formal Citation Register:** Elimination of all unsourced numbers. Every baseline metric is directly benchmarked or cited with peer-reviewed literature. | `docs/v2/citation_register.md`, `docs/v2/evaluation_protocol.md` | Peer review verification of all cited baselines in Phase 2. |

---

## 3. User Stories (US-1 to US-8) to Requirements & Architecture Traceability

| User Story ID | Persona | Functional Requirement | v2 Architectural Component | Acceptance Criteria |
|---|---|---|---|---|
| **US-1: Rapid Triage** | FinOps Analyst | Instant notification of unexpected spend with dollar impact and confidence score. | Ingestion Pipeline $\rightarrow$ Mode A Detector $\rightarrow$ Notification Service. | Alert delivered within 5 minutes of data ingestion; dollar delta clearly displayed. |
| **US-2: Volume vs. Price Diagnosis** | FinOps Analyst | Ability to immediately distinguish whether spend jumped due to usage or unit price. | Volume-Price-Mix (VPM) Decomposition Engine. | UI displays exact percentage split between Usage Volume and Unit Rate. |
| **US-3: Correlated Event Context** | Engineering Manager | View nearby software deployments and auto-scaling events associated with the anomaly. | Temporal Decay Event Attribution Engine. | Displays top associated changes within $[-6\text{h}, +2\text{h}]$ window with confidence levels. |
| **US-4: Non-Causal Explanation** | FinOps Analyst | Explanations must use responsible correlation language without claiming unproven causality. | Plain-Language Generator + Non-Causal Linter. | 100% pass rate on `tests/test_non_causal_language.py`. |
| **US-5: False Alarm Feedback** | Engineering Manager | Mark alerts as false alarms or expected business events to tune sensitivity. | Feedback API + Suppression Filter. | Muted incidents suppressed in future detection cycles; feedback stored in DB. |
| **US-6: Executive Summary** | CFO / Finance | Weekly digest of total anomalous spend, top recurring culprits, and dollars protected. | Reporting Engine + Executive Summary API. | PDF/Email digest generated showing aggregate unexpected spend. |
| **US-7: Multi-Cloud Ingestion** | Platform Engineer | Ingest standard AWS, Azure, and GCP billing exports without custom schema changes. | Provider Ingestion Adapters (FOCUS Canonical). | Automated parsing and mapping of AWS CUR, Azure Export, and GCP BigQuery billing. |
| **US-8: Zero-Touch Data Isolation** | Platform Engineer | Guarantee that proprietary company billing data is isolated and never leaks across tenants. | PostgreSQL Row Level Security (RLS) + Tenant Context. | Cross-tenant data retrieval queries return 0 rows; multi-tenant security test passes. |

---

## 4. Verification & Validation Summary

Every requirement specified in this matrix is linked to an automated test fixture or pre-registered validation protocol:
1. **Mathematical & Leakage Invariants:** Enforced via local unit and property-based tests (`pytest`).
2. **Scientific Hypotheses (H-A through H-D):** Verified via locked multi-seed Colab evaluation against fresh holdout partition $D_{\text{holdout}}$ in Phase 15.
3. **Enterprise Usability & Accessibility:** Enforced via automated Playwright E2E suites and axe-core accessibility checks in Phase 14.
