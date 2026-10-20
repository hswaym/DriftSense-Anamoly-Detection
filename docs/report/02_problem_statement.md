# DriftSense — Final Report: Chapter 2. Problem Statement & Research Motivation

## 2.1 The Cloud Cost Visibility Gap

Enterprise cloud migration has transitioned organizations from predictable, capitalized IT expenses (CapEx) to dynamic, operational expenditures (OpEx). Under modern microservice architectures, serverless computing, and dynamic container orchestration (e.g., Kubernetes, Amazon ECS), thousands of autonomous services continuously provision, scale, and de-provision cloud resources.

While this elasticity drives agility, it creates severe FinOps challenges:
1. **Decentralized Provisioning**: Developers and continuous integration/continuous deployment (CI/CD) pipelines spawn cloud infrastructure without central financial gatekeeping.
2. **Delayed Ingestion & Billing Lag**: Cloud service providers (AWS, Azure, Google Cloud) finalize billing data with latency ranging from 4 to 24 hours. Undetected runaway jobs can accrue thousands of dollars before human operators notice.
3. **Complex Multi-Cloud Schemas**: Inconsistent column names, differing tax/credit representations, and incompatible unit scales across cloud vendors make unified monitoring labor-intensive and prone to data corruption.

---

## 2.2 Shortcomings of Existing Industry Approaches

Current industry approaches to cloud cost management predominantly rely on two flawed paradigms:

### Paradigm A: Static Thresholds & Budget Alerts
Cloud providers natively provide budget alerts that trigger when monthly spend crosses a fixed percentage (e.g., "80% of $10,000 budget reached").
* **Limitation**: These alerts trigger long after anomalies occur and fail to detect short-term micro-spikes (e.g., a $500/hr spike that subsides before exhausting the monthly threshold).
* **Alert Fatigue**: Fixed dollar thresholds fail during high-traffic operational peaks (Black Friday, product launches), generating false alarms that engineering teams routinely silence or ignore.

### Paradigm B: Naive Statistical Outlier Detection on Raw Spend
Many monitoring tools apply standard 3-sigma or percentile thresholds directly to raw hourly cost.
* **Limitation**: Normal business operations exhibit pronounced diurnal (day vs. night) and weekly (weekday vs. weekend) cycles.
* **Failure Mode**: A Monday morning ramp in traffic looks like a catastrophic anomaly to a raw-spend threshold detector, while an anomalous weekend background process operating at moderate cost goes undetected.

### Paradigm C: The "What Happened?" Attribution Void
Even when an anomaly is flagged, existing cost management platforms provide no operational context. The on-call engineer is left asking: *Was this caused by a bad deployment, an autoscaling runaway, or organic customer traffic?* Investigating this requires manual log hunting across DataDog, CloudWatch, and GitHub deployments, with mean time to resolution (MTTR) often exceeding 3 to 6 hours.

---

## 2.3 Research Questions and Project Scope

DriftSense was engineered to resolve these gaps through rigorous data science:

* **RQ1 (Forecasting)**: Can gradient boosted decision trees leveraging joint cost and resource consumption features significantly outperform seasonal statistical baselines on hourly cloud spend?
* **RQ2 (Detection)**: Does thresholding on counterfactual residuals ($Y_t - \hat{Y}_t$) maintain an operational false positive rate $\le 1.0\%$ across weekday and weekend regimes while detecting $\ge 90\%$ of true operational fault episodes?
* **RQ3 (Attribution)**: Can temporal proximity correlation between billing spikes and operational telemetry accurately rank the true triggering event in the Top-1 and Top-3 recommendations without complex causal graph inference?
* **RQ4 (Explainability & Governance)**: Can model decisions be explained with exact mathematical additivity (TreeSHAP) while maintaining strict non-causal language to prevent unwarranted engineering liability?
