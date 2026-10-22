# DriftSense v2 — Product Requirements Document (PRD)

## 1. Executive Vision & Objectives
DriftSense v2 is an enterprise-grade Cloud Financial Operations (FinOps) platform that empowers engineering and finance teams to detect, understand, and remediate unexpected cloud spending without alert fatigue or technical obscurity.

Unlike v1—which operated strictly as an offline research prototype on a single pre-processed dataset—DriftSense v2 is designed as an interactive, multi-tenant product that ingests arbitrary cloud billing exports (FOCUS, AWS CUR, Azure, GCP), automatically validates data quality, and presents actionable insights in plain, non-academic language.

---

## 2. Target Personas & Jobs-to-be-Done (JTBD)

### Persona 1: Sarah — The FinOps Analyst / Cloud Economist
* **Role:** Centralized financial controller responsible for tracking cloud unit economics, forecasting monthly budgets, and identifying wasted spend across engineering departments.
* **Pain Points:** Spends 15+ hours per week manually joining AWS and Datadog CSVs in Excel; overwhelmed by hundreds of uninformative provider budget alerts; cannot tell whether a cost increase was planned business growth or an engineering mistake.
* **Job-to-be-Done:** *"When our monthly cloud bill fluctuates, I want to immediately see whether the change is driven by resource consumption volume or unit price changes, so that I can hold engineering teams accountable without false alarms."*

### Persona 2: Alex — The Engineering Manager / Tech Lead
* **Role:** Leads a microservice engineering squad deploying code daily to Kubernetes and cloud serverless infrastructure.
* **Pain Points:** Silences automated cost alerts because 90% are false alarms triggered by normal business traffic; fears incident post-mortems where cost spikes are unfairly blamed on his team's code deployments.
* **Job-to-be-Done:** *"When my team's cloud spend spikes abnormally, I want a concise alert that points to the exact service, timestamp, and coincident deployment with supporting evidence, so that we can remediate the issue within 30 minutes without reading raw billing logs."*

### Persona 3: Marcus — The Chief Financial Officer (CFO) / VP of Finance
* **Role:** Executive responsible for corporate operating margins and investor cloud expenditure guidance.
* **Pain Points:** Surprised by unexpected cloud invoices at month-end; lacks confidence in static 80% budget alerts; requires auditable, compliant financial governance.
* **Job-to-be-Done:** *"At any point in the billing cycle, I want an executive-level summary of dollars-at-risk and forecast variance, so that our board updates have accurate margin forecasts."*

### Persona 4: Elena — The Platform / SRE Engineer
* **Role:** Manages shared cloud infrastructure, CI/CD pipelines, and cloud provider relationships.
* **Pain Points:** Cloud bills lack resource tags; unallocated shared infrastructure (e.g. NAT gateways, idle clusters) creates orphan spend; provider billing APIs export differing formats.
* **Job-to-be-Done:** *"When I upload a multi-cloud billing export, I want the system to automatically score its data quality and flag missing tags or orphaned resources, so that we can enforce tagging hygiene."*

---

## 3. Epics & User Stories with Acceptance Tests

### Epic 1: Multi-Provider Ingestion & Data Health
* **US-1.1 (Format Auto-Detection):** As a FinOps Analyst, I want to drag and drop an AWS CUR, Azure Cost Export, GCP Billing Export, or FOCUS CSV, so that the system automatically detects the schema without manual configuration.
  * *Acceptance Test:* Uploading standard sample exports from AWS, Azure, GCP, and FOCUS 1.0–1.4 must detect provider with $\ge 99\%$ accuracy; unknown columns must provide interactive mapping suggestions.
* **US-1.2 (Data Health Score):** As a Platform Engineer, I want an immediate Data Health Score (0–100) with plain-English reasons for deduction (e.g., "12 days have no data", "18% untagged spend"), so that I can fix ingestion gaps before analysis.
  * *Acceptance Test:* Uploading a file with missing days or negative adjustments displays clear remediation steps with hand-computed deterministic scoring.

### Epic 2: Dual-Mode Anomaly Intelligence
* **US-2.1 (History-Expected Anomaly Alerts - Mode A):** As an Engineering Manager, I want alerts when spend exceeds what was expected based on historical patterns alone, so that runaway compute loops and organic viral traffic are flagged immediately.
  * *Acceptance Test:* An abrupt 3x usage spike must trigger a High-severity alert with zero false alarms during normal cyclical peaks.
* **US-2.2 (Usage-Expected Rate Anomalies - Mode B):** As a FinOps Analyst, I want alerts when cost exceeds expectations *given* measured usage, so that misconfigured pricing tiers or expired commitments are caught even if total usage didn't surge.
  * *Acceptance Test:* An instance type upgrade causing cost per vCPU-hour to double must be flagged even when total workload remains flat.

### Epic 3: Probabilistic Attribution & Root-Cause Evidence
* **US-3.1 (Culprit Change Ranking):** As an on-call Engineer, I want unusual spend incidents to rank coincident operational changes (deployments, autoscaling loops, config edits) with a confidence level (High / Medium / Low) and supporting data points.
  * *Acceptance Test:* When a known deployment coincides with an incident within 2 hours, it must rank #1 with supporting timestamp overlap evidence.
* **US-3.2 (Abstention on Weak Evidence):** As an on-call Engineer, I want the system to state "Not enough evidence" when no operational change matches the spike, rather than guessing a false culprit.
  * *Acceptance Test:* Injecting pure synthetic noise must trigger an "Abstention" output with zero false event attributions.

### Epic 4: Plain-Language Audits & Governance
* **US-4.1 (Non-Causal Audit Post-Mortem):** As an Engineering Lead, I want one-click executive incident summaries written without blame-assigning causal verbs ("caused by"), so that post-mortems remain blameless and evidence-driven.
  * *Acceptance Test:* Automated grep scan of 100% of generated narratives must contain 0 occurrences of "caused by", "triggered by", or "resulted from".
* **US-4.2 (Expert Details Toggle):** As a Data Scientist or Auditor, I want an "Expert Details" toggle that reveals mathematical TreeSHAP additivity, model hashes, and residual plots without confusing non-technical users.
  * *Acceptance Test:* Default view shows zero mathematical jargon; toggling "Expert Details" exposes full technical provenance.

---

## 4. Product Success Metrics (KPIs)

| Metric | Target (v2 Launch) | Measurement Method |
| :--- | :--- | :--- |
| **Time-to-First-Insight** | $< 60$ seconds | Elapsed time from file drop to Overview screen render on 100k-row file |
| **Alert Actionability Rate** | $\ge 80\%$ | Percentage of alerts marked "Useful" or "Investigating" by users |
| **Alert Volume Fatigue Limit** | $\le 5$ alerts / service / month | Total volume of triggered alerts across normal operational periods |
| **False Positive Rate on Clean Data** | $\le 0.5\%$ | Verified alert rate on certified normal cloud billing periods |
| **Root-Cause Top-3 Accuracy** | $\ge 90\%$ | Correct identification of true operational trigger in top 3 suggestions |
| **Accessibility Compliance** | WCAG 2.1 AA | Zero critical issues flagged by automated accessibility scanners (axe-core) |
