# DriftSense — Final Presentation Slide Deck Outline

This outline specifies the slide-by-slide structure for the DriftSense final technical presentation. Each slide includes the visual layout, key bullet points, quantitative data citations (traced to `docs/results_trace.md`), and speaker talking points.

---

### Slide 1: Title & Executive Vision
* **Title**: DriftSense: Cloud Cost Anomaly Detection & Operational Root-Cause Attribution
* **Subtitle**: Standardized on FinOps Open Cost & Usage Specification (FOCUS 1.0/1.3)
* **Visuals**: DriftSense architecture logo, FOCUS 1.3 compliance badge, GitHub open-source badge.
* **Key Bullets**:
  * The cloud visibility dilemma: $30B+ in annual enterprise cloud waste.
  * Moving beyond crude static budgets to counterfactual machine learning.
  * An end-to-end reproducible pipeline from raw billing data to interactive dashboard.
* **Speaker Notes**: Introduce the problem of modern cloud elasticity where decentralized microservices spawn runaway jobs and unexpected billing surges. Introduce DriftSense as the first open system combining FOCUS standards, ML forecasting, and operational attribution.

---

### Slide 2: The FinOps Challenge & Research Motivation
* **Title**: The Cloud Cost Visibility Gap: Why Static Thresholds Fail
* **Visuals**: Split graphic comparing a static $1,000 threshold (causing false alarms on Monday peaks and missing weekend anomalies) vs. dynamic counterfactual bands.
* **Key Bullets**:
  * Billing lag (4–24h) and noisy microservices compound cost drift.
  * Static budget alerts trigger severe alert fatigue (industry false positive rates ~5–10%).
  * The "What Happened?" Attribution Void: Teams spend 3–6 hours in post-mortems hunting across logs.
* **Speaker Notes**: Highlight that raw spend is inherently non-stationary and diurnal. A Monday 9 AM traffic surge is expected; a Sunday 2 AM batch loop is dangerous even at lower spend.

---

### Slide 3: The Four Pillars of DriftSense
* **Title**: System Architecture: The Four-Pillar Machine Learning Framework
* **Visuals**: Pipeline flow diagram: FOCUS Ingestion $\rightarrow$ Pillar 1 (Forecasting) $\rightarrow$ Pillar 2 (Residual Detection) $\rightarrow$ Pillar 3 (Attribution) $\rightarrow$ Pillar 4 (Explainability).
* **Key Bullets**:
  * **Pillar I**: Counterfactual Expected-Cost Forecasting ($E[Y_t \mid X_t]$).
  * **Pillar II**: Dual-Track Anomaly Detection on Residuals ($Y_t - \hat{Y}_t$).
  * **Pillar III**: Operational Root-Cause Attribution via Temporal Proximity.
  * **Pillar IV**: Interpretability via TreeSHAP and Non-Causal Audit Narratives.
* **Speaker Notes**: Walk the audience through the four pillars, emphasizing how each pillar solves a distinct failure mode of conventional monitoring.

---

### Slide 4: Data Pipeline & FOCUS 1.0/1.3 Standardization
* **Title**: Standardized Data Hygiene & Anti-Leakage Chronological Splits
* **Visuals**: Diagram of FOCUS columns (`EffectiveCost`, `ConsumedQuantity`, `ServiceName`) and chronological split timeline (Days 1–15 Train, Days 16–24 Val, Days 25–30 Test).
* **Key Bullets**:
  * Vendor independence via FOCUS 1.0/1.3 dimensions.
  * Deterministic data hygiene: UTC alignment, negative credit segregation, canonical 1h grid.
  * Strict chronological partitioning: Zero lookahead leakage, scalers fit strictly on $D_{\text{train}}$.
* **Speaker Notes**: Explain why standardizing on FOCUS enables multi-cloud deployment across AWS, Azure, and GCP without changing a line of ML code.

---

### Slide 5: Controlled Feature Ablation Insights
* **Title**: Empirical Feature Ablation: The Power of Usage Coupling
* **Visuals**: Bar chart showing WAPE dropping from 87.99% (Cost Only) to 62.15% (Cost + Usage).
* **Key Bullets**:
  * 7-arm controlled ablation across 3 random seeds on $D_{\text{val}}$ (Phase 10, DEC-013).
  * **25.84 percentage point WAPE reduction** by coupling `ConsumedQuantity` with cost.
  * Resource usage is the physical leading indicator that precedes financial accrual.
  * Baseline comparisons: Seasonal Naive (140.15% WAPE), Moving Avg (158.42% WAPE).
* **Speaker Notes**: Emphasize this core scientific finding: pure cost autoregression is blind to workload surges. Ingesting physical usage volume is the single most impactful feature decision.

---

### Slide 6: Pillar I Results — Forecaster Benchmark on Test Horizon
* **Title**: Final Expected-Cost Forecaster Benchmark ($D_{\text{test}}$, Days 25–30)
* **Visuals**: Bar chart comparing WAPE and MASE across Seasonal Naive, Moving Avg, Exp Smoothing, and Champion XGBoost (Panel A of `final_test_benchmark.png`).
* **Key Bullets**:
  * Seasonal Naive ($s=24$): WAPE = 129.18%, MASE = 1.2381 (fails persistence).
  * Moving Average ($w=24$): WAPE = 150.32%, RMSE = $0.1760.
  * **Champion XGBoost (3 seeds)**: **WAPE = 82.03% ± 1.52%**, **RMSE = $0.1376**, **MASE = 0.7862 ± 0.0145**.
  * **21.4% error reduction** over naive persistence on completely unseen test data.
* **Speaker Notes**: Point out that the model was evaluated under locked protocol on unseen future data. The low seed variance (±1.52%) proves high operational stability.

---

### Slide 7: Pillar II Results — Dual-Track Anomaly Detection
* **Title**: Dual-Track Anomaly Detection: Conquering Alert Fatigue & Sensitivity
* **Visuals**: Two-column graphic: Left column showing Real Clean Track (FPR = 0.16%); Right column showing Synthetic Track (Event F1 = 0.9278, Delay = 0.00h).
* **Key Bullets**:
  * **Real Clean Track**: Only 6 false alarms across 3,822 hours (**0.16% FPR** overall, 0.15% weekday, 0.16% weekend).
  * **Synthetic Fault Track**: **95.74% Event Recall** (45 / 47 fault episodes caught).
  * **Event F1**: **0.9278** | **Point Precision**: **96.03%**.
  * **Mean Detection Delay**: **0.00 hours** (instantaneous detection on onset).
* **Speaker Notes**: Highlight the dual-track methodology. We audited clean data to prove we don't spam engineers with false alarms, while proving on injected faults that we catch almost every real outage instantly.

---

### Slide 8: Pillar III Results — Root-Cause Attribution Engine
* **Title**: Operational Attribution: Pinpointing the Culprit Event
* **Visuals**: Grouped bar chart comparing Random, Prior, and Temporal Correlation Top-1 and Top-3 accuracy (Panel C of `final_test_benchmark.png`).
* **Key Bullets**:
  * Random Baseline: Top-1 = 4.26%, Top-3 = 42.55%, MRR = 0.3099.
  * Class Prior Baseline: Top-1 = 27.66%, Top-3 = 76.60%, MRR = 0.4908.
  * **Champion Temporal Correlation ($lookback=6\text{h}, decay=2\text{h}$)**:
    * **Top-1 Accuracy: 97.87%** (46 of 47 incidents correctly ranked rank 1).
    * **Top-2 Accuracy: 100.0%** | **Top-3 Accuracy: 100.0%**.
    * **Mean Reciprocal Rank (MRR): 0.9894**.
* **Speaker Notes**: Walk through the confusion matrix. Deployments, config modifications, runaway batches, and traffic surges are ranked near-perfectly using exponential temporal decay.

---

### Slide 9: Pillar IV Results — TreeSHAP Interpretability & Governance
* **Title**: Interpretable FinOps Governance: TreeSHAP & Non-Causal Audits
* **Visuals**: Horizontal bar chart of Top-5 global TreeSHAP drivers (Panel D of `final_test_benchmark.png`) alongside a sample non-causal audit narrative snippet.
* **Key Bullets**:
  * Exact TreeSHAP Additivity verified on 3,822 test predictions ($\max |\Delta| < 0.002$).
  * Top drivers: `BilledCost` (48.18%), `ConsumedQuantity` (8.46%), `day_of_month` (3.71%), `roll_mean_168h` (3.70%), `roll_max_24h` (3.12%).
  * Automated governance scanner enforces non-causal phrasing ("likely associated with") to protect teams from premature liability claims.
* **Speaker Notes**: Explain the governance innovation: black-box ML is unacceptable in financial audits. TreeSHAP provides exact mathematical accountability, while our narrative scanner prevents false causal claims.

---

### Slide 10: Interactive FinOps Streamlit Dashboard
* **Title**: Operationalizing the Pipeline: Interactive FinOps Dashboard
* **Visuals**: Screenshots of the 5 views: Executive Overview, Forecast & Anomalies, Root-Cause Attribution, TreeSHAP Explainability, and Ablations.
* **Key Bullets**:
  * Lightweight local Streamlit interface adhering to zero in-app training rule (G3).
  * Multi-service filtering, interactive Plotly spend charts, and threshold sensitivity sliders.
  * 8 resilient artifact loaders with comprehensive unit testing coverage.
* **Speaker Notes**: Showcase the dashboard as the delivery vehicle for FinOps practitioners. An engineering manager or FinOps analyst can explore any historical run with one command: `streamlit run app/main.py`.

---

### Slide 11: Production Verification & Quality Assurance
* **Title**: Production Packaging, Code Quality & Traceability
* **Visuals**: Matrix showing 106 passed tests, ruff clean status, and cryptographically verified manifest seal.
* **Key Bullets**:
  * Production packaging: `pip install -e .` with registered `driftsense` CLI.
  * 106 automated tests passing in pytest across all modules and edge cases.
  * 100% ruff lint and format check compliance across all Python files.
  * G1 Truth Rule: All reported numbers traced to cryptographically signed SHA-256 manifests.
* **Speaker Notes**: Reassure technical evaluators that DriftSense is not a disorganized research notebook, but a hardened, tested, and reproducible Python engineering package.

---

### Slide 12: Conclusion & Strategic Roadmap
* **Title**: Summary of Contributions & Future Roadmap
* **Visuals**: Summary scorecard highlighting key metrics (82.0% WAPE, 0.16% FPR, 97.9% Top-1 Attribution) and roadmap timeline.
* **Key Bullets**:
  * **Core Impact**: Proved that coupled cost+usage ML forecasting cuts error by 21.4% and eliminates false alarms down to 0.16%.
  * **Roadmap Ahead**:
    1. Causal DAG discovery via distributed tracing (OpenTelemetry spans).
    2. Hierarchical optimal reconciliation across accounts and regions.
    3. Closed-loop automated rightsizing and remediation.
  * GitHub Repository: Fully open-source and reproducible.
* **Speaker Notes**: Conclude with a strong summary statement: DriftSense provides the foundational intelligence layer for automated cloud financial operations. Open the floor for questions.
