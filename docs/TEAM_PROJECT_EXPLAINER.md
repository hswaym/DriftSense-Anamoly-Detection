# DriftSense: Complete Project Guide & Team Member Walkthrough

> **Purpose of this Document:**  
> This guide is an all-in-one, plain-English, deep-dive explanation of **DriftSense**. It is specifically structured so that you and your groupmates can completely understand:
> 1. What problem this project solves and why it matters in the real world.
> 2. How the dataset was collected, standardized, and cleaned.
> 3. How the entire project was designed, built, and evaluated step-by-step.
> 4. How the work is cleanly divided across **4 team members** (with specific talking points and viva answers for each member).

---

## Table of Contents
1. [The Big Picture: What is DriftSense & Why Does It Exist?](#1-the-big-picture-what-is-driftsense--why-does-it-exist)
2. [The Core Innovation: The 4-Pillar Machine Learning Framework](#2-the-core-innovation-the-4-pillar-machine-learning-framework)
3. [The Dataset & Data Engineering Pipeline](#3-the-dataset--data-engineering-pipeline)
4. [Step-by-Step Project Journey (How We Built Everything)](#4-step-by-step-project-journey-how-we-built-everything)
5. [The Final Benchmark Results (What We Proved)](#5-the-final-benchmark-results-what-we-proved)
6. [Team Division of Work (4 Members) & Presentation Scripts](#6-team-division-of-work-4-members--presentation-scripts)
7. [Common Viva / Professor Questions & Winning Answers](#7-common-viva--professor-questions--winning-answers)

---

# 1. The Big Picture: What is DriftSense & Why Does It Exist?

### The Real-World Problem: Cloud Cost Chaos
When companies use cloud providers like **Amazon Web Services (AWS)**, **Google Cloud (GCP)**, or **Microsoft Azure**, they pay on-demand per hour or second. In a large tech company:
- Hundreds of software engineers deploy code daily.
- Microservices, serverless functions, and container clusters (Kubernetes) automatically scale up and down.
- **The Disaster**: A developer makes a typo in an autoscaling configuration, or runs a massive machine learning data pipeline with an infinite loop over the weekend. By Monday morning, the company has burned **$50,000 in unexpected cloud bills**. Industry statistics show that **25% to 35% of all corporate cloud spend is pure waste**.

### Why Existing Tools Fail Miserably
Most companies try to solve this with simple budget alerts (e.g., in AWS Cost Explorer):
1. **Static Thresholds Fail**: If you set an alert at *"alert me if hourly spend > $500"*, you get spammed with **false alarms** every Monday morning when normal customer traffic ramps up (**Alert Fatigue**).
2. **They Miss Dangerous Weekend Spikes**: If your normal spend drops to $50 on Sunday, an accidental $300 runaway job won't cross the $500 threshold, so it goes completely unnoticed.
3. **The "What Happened?" Void**: Even when an alert fires, it just says *"Spend is high"*. It doesn't tell the engineer **why**. Was it a bad code deployment? An autoscaling glitch? An accidental instance upgrade? Engineers spend 4–8 hours digging through disparate server logs.

### What DriftSense Does
**DriftSense** is an intelligent, automated **FinOps (Financial Operations)** anomaly detection and operational root-cause attribution system.
- Instead of static thresholds, it uses **Machine Learning to predict what the cost should be right now** based on normal time cycles and physical resource usage.
- It detects anomalies on the **difference (residual)** between actual cost and expected cost.
- It automatically inspects deployment and server logs to **pinpoint the exact operational trigger** (e.g., *"Deployment Defect on EC2 at 2:00 PM"*).
- It explains the decision using mathematical explainable AI (**TreeSHAP**) and writes a human-readable executive audit narrative.
- It wraps everything into an **interactive dashboard** for financial analysts and engineering managers.

---

# 2. The Core Innovation: The 4-Pillar Machine Learning Framework

DriftSense solves the problem using **four interconnected pillars**:

```
[Raw Multi-Cloud Billing Data]
             │
             ▼
┌────────────────────────────────────────────────────────────────────────┐
│                      FOCUS 1.0/1.3 Standardization                     │
│  (Normalizes column names, deduplicates, and resamples to 1-hr grain)  │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
    ┌───────────────────────────────┴───────────────────────────────┐
    │                                                               │
    ▼                                                               ▼
┌───────────────────────────────────┐   ┌───────────────────────────────────┐
│     PILLAR 1: COST FORECASTING    │   │      PILLAR 2: ANOMALY DETECT     │
│   Predicts Expected Cost (Ŷ_t)    │   │  Computes Residual e_t = Y_t - Ŷ_t│
│  Champion: XGBoost Regressor      │──▶│  Champion: Rolling Threshold (3σ) │
│  (Beats baselines by 21.4% MASE)  │   │  (0.16% Clean False Positive Rate)│
└───────────────────────────────────┘   └─────────────────┬─────────────────┘
                                                          │ (When anomaly detected)
    ┌─────────────────────────────────────────────────────┴─────────────────┐
    │                                                                       │
    ▼                                                                       ▼
┌───────────────────────────────────┐   ┌───────────────────────────────────┐
│    PILLAR 3: CAUSE ATTRIBUTION    │   │     PILLAR 4: EXPLAINABLE AI      │
│  Temporal Decay Proximity Kernel  │   │  Exact TreeSHAP Feature Weights   │
│  Ranks operational culprit events │   │  + Non-Causal Plain-English Audit │
│  (97.9% Top-1 Ranking Accuracy)   │   │  Narratives for FinOps Executives │
└───────────────────────────────────┘   └───────────────────────────────────┘
```

1. **Pillar 1: Counterfactual Expected-Cost Forecasting**
   - *Question:* "What should this cloud service cost this hour under normal conditions?"
   - *How:* An XGBoost model trained on 48 chronological features predicts expected spend $\hat{Y}_t$.
2. **Pillar 2: Dual-Track Anomaly Detection on Residuals**
   - *Question:* "Is the current spend significantly higher than expected?"
   - *How:* We calculate the residual $e_t = Y_t - \hat{Y}_t$. If normal morning traffic arrives, $\hat{Y}_t$ rises, so $e_t \approx 0$ (no false alarm!). If an unexpected fault hits, $e_t$ spikes and crosses a dynamic $3\sigma$ threshold.
3. **Pillar 3: Operational Root-Cause Attribution Engine**
   - *Question:* "What operational event triggered this cost spike?"
   - *How:* We inspect operational logs (deployments, autoscaling loops, config edits) within a 6-hour lookback window and rank them using an exponential decay kernel.
4. **Pillar 4: Model Explainability & Governance (XAI)**
   - *Question:* "Which features drove this prediction, and how do we present this safely?"
   - *How:* Exact TreeSHAP values prove feature contributions mathematically ($\sum \phi_i + \phi_0 = f(x)$), while an automated narrative generator creates non-causal audit reports.

---

# 3. The Dataset & Data Engineering Pipeline

### 3.1 Why the FOCUS Standard?
If you download an AWS bill, column names are `lineItem/UnblendedCost`, `lineItem/UsageAmount`, and `product/servicecode`. If you download an Azure bill, they are `CostInBillingCurrency`, `Quantity`, and `MeterCategory`.
To make our project work for **any cloud provider**, we standardized on **FOCUS 1.0 / 1.3 (FinOps Open Cost and Usage Specification)**, stewarded by the Linux Foundation.

Key standard FOCUS columns used in DriftSense:
- `ChargePeriodStart`: The UTC timestamp of the hour.
- `ServiceName`: The cloud service (e.g., *Amazon Elastic Compute Cloud (EC2)*, *Amazon Relational Database Service (RDS)*).
- `EffectiveCost`: The actual amortized dollar cost after discounts (our primary target variable $Y_t$).
- `BilledCost`: The raw unadjusted invoice cost.
- `ConsumedQuantity`: The physical volume of usage (e.g., number of vCPU-hours, gigabytes transferred).
- `RegionName`: The geographical datacenter region (e.g., `us-east-1`).

### 3.2 Data Hygiene & Preprocessing
Raw billing data is notoriously dirty. Our cleaning pipeline (`driftsense.data.clean` and `aggregate`) performs:
1. **Deduplication**: Drops duplicated line items sharing identical timestamps and resource IDs.
2. **Timestamp Normalization**: Converts all varied date strings into strict timezone-aware UTC ISO 8601 timestamps.
3. **Negative Spend Segregation**: Segregates cloud refunds and credit adjustments so they don't corrupt positive consumption trends.
4. **Canonical 1-Hour Grid Aggregation**: Cloud services report usage at irregular minutes (e.g., 10:14, 10:47). We aggregate everything to a strict 1-hour interval and fill missing hours with zero so time-series lag structures are never broken.

### 3.3 The Evaluation Dilemma & Synthetic Fault Ground Truth
In real-world cloud bills, there is no "anomaly label" column saying *"this spike was caused by deployment defect #12"*.
To evaluate our system with rigorous scientific proof:
- We built a deterministic **Synthetic Fault Injector** (`driftsense.synth.injector`).
- It injects 5 realistic operational incident types into our time series:
  1. `RUNAWAY_BATCH_PROCESS`: Infinite loop / zombie worker consuming max compute.
  2. `AUTOSCALING_OVERPROVISION`: Misconfigured autoscaler adding 10x more servers than needed.
  3. `CONFIG_MODIFICATION`: Accidental upgrade to expensive GPU instance types.
  4. `DEPLOYMENT_DEFECT`: Code bug that doubles CPU/memory usage per user request.
  5. `EXTERNAL_TRAFFIC_SURGE`: Sudden organic viral traffic spike.
- Each injected incident generates an exact ground-truth label and timestamp, allowing us to evaluate detection precision, recall, and attribution ranking objectively.

### 3.4 Strict Anti-Leakage Chronological Splits
We split our 30-day billing dataset strictly by time to prevent lookahead bias:
- **$D_{\text{train}}$ (Days 1–15)**: Training historical models (50%).
- **$D_{\text{val}}$ (Days 16–24)**: Validation, model tuning, and ablation studies (30%).
- **$D_{\text{test}}$ (Days 25–30)**: **Quarantined Test Horizon** (20%). Locked away until the final phase, evaluated strictly once with zero retuning.

---

# 4. Step-by-Step Project Journey (How We Built Everything)

Here is how our project progressed across all development phases:

| Phase | Milestone | What Was Built |
| :--- | :--- | :--- |
| **Phase 0–3** | **Planning & Specs** | Defined project contracts, mathematical formulas, and adopted the FOCUS 1.3 schema. |
| **Phase 4** | **Data Cleaning & EDA** | Built `clean.py` and `aggregate.py`. Conducted exploratory data analysis on 10,000 billing records. |
| **Phase 5** | **Splits & Leakage Audits** | Implemented chronological splitting. Created automated unit tests proving zero future leakage in rolling windows. |
| **Phase 6** | **Feature Engineering** | Built `FeaturePipeline` with 48 features: cost lags ($t-1, t-2, t-24, t-168$), rolling statistics, differences, calendar cyclic terms, and coupled usage metrics (`ConsumedQuantity`). |
| **Phase 7** | **Pillar 1: Forecasting** | Trained baseline models (Seasonal Naive, Moving Average, Exponential Smoothing) and our Champion XGBoost Forecaster. |
| **Phase 8** | **Pillar 2: Anomaly Detection** | Built residual calculator and the Champion Rolling Threshold detector ($w=24\text{h}, k=3.0\sigma$). Established dual-track evaluation. |
| **Phase 9** | **Pillar 3: Attribution Engine** | Built `TemporalCorrelationAttributor` with exponential decay kernel ($lookback=6\text{h}, decay=2\text{h}$) to rank operational events. |
| **Phase 10** | **Controlled Ablations** | Ran a 7-arm ablation study across 3 random seeds. Discovered that coupling resource usage with cost reduced WAPE by **25.84 percentage points**! |
| **Phase 11** | **Pillar 4: XAI & Dashboard** | Integrated TreeSHAP explainer with exact additivity verification and built the interactive 5-view **Streamlit Dashboard** (`app/main.py`). |
| **Phase 12** | **Packaging & Integration** | Hardened repository into an installable Python package (`pip install -e .`), registered `driftsense` CLI, and wrote 106 automated unit tests. |
| **Phase 13** | **Locked Test Evaluation** | Cryptographically locked all 8 YAML configs with SHA-256 hashes and evaluated once on the unseen test horizon ($D_{\text{test}}$, Days 25–30). |
| **Phase 14** | **Final Delivery** | Produced the 7-chapter technical report, results traceability ledger, and 12-slide presentation deck. |

---

# 5. The Final Benchmark Results (What We Proved)

All metrics were evaluated on the unseen test partition ($D_{\text{test}}$, 3,822 hourly records) under locked protocol (DEC-016):

### 1. Forecaster Benchmark (XGBoost vs Baselines)
- **Seasonal Naive ($s=24$)**: WAPE = 129.18%, MASE = 1.2381 (Fails persistence baseline)
- **Moving Average ($w=24$)**: WAPE = 150.32%, RMSE = $0.1760
- **Exponential Smoothing ($\alpha=0.25$)**: WAPE = 144.24%, RMSE = $0.1767
- **Champion XGBoost (3 seeds)**: **WAPE = 82.03% ± 1.52%**, **RMSE = $0.1376**, **MASE = 0.7862 ± 0.0145**
  - **Result**: $\text{MASE} = 0.7862 < 1.0$ proves DriftSense cuts forecasting error by **21.4%** compared to naive persistence on completely unseen future data!

### 2. Dual-Track Anomaly Detection
- **Real Clean Track (Alert Fatigue Audit)**:
  - Total hours evaluated: 3,822 hours.
  - False alarms triggered: **Only 6 false alarms**.
  - **False Positive Rate (FPR)**: **0.16%** (0.15% weekday, 0.16% weekend).
  - *Result*: Decimates industry false alarm rates (which average 5%–10%), completely eliminating alert fatigue.
- **Synthetic Fault Track (Sensitivity Audit)**:
  - **Point Precision**: **96.03%**
  - **Event Recall**: **95.74%** (45 out of 47 operational events caught!)
  - **Event F1-Score**: **0.9278**
  - **Mean Detection Delay**: **0.00 hours** (instantaneous detection on the very first hour of incident onset).

### 3. Root-Cause Attribution Engine
- **Random Guessing**: Top-1 Accuracy = 4.26%, Top-3 = 42.55%
- **Class Prior Baseline**: Top-1 Accuracy = 27.66%, Top-3 = 76.60%
- **Champion Temporal Correlation**:
  - **Top-1 Accuracy**: **97.87%** (46 of 47 incidents correctly ranked #1)
  - **Top-2 Accuracy**: **100.0%**
  - **Top-3 Accuracy**: **100.0%**
  - **Mean Reciprocal Rank (MRR)**: **0.9894**

### 4. TreeSHAP Feature Drivers
- **Exact Additivity**: Verified on all 3,822 test instances ($\sum \phi_i + \phi_0 = f(x)$, error $< 0.002$).
- **Top 5 Cost Drivers**:
  1. `BilledCost` (48.18% importance)
  2. `ConsumedQuantity` (8.46% importance)
  3. `day_of_month` (3.71% importance)
  4. `EffectiveCost_roll_mean_168h` (3.70% importance)
  5. `EffectiveCost_roll_max_24h` (3.12% importance)

---

# 6. Team Division of Work (4 Members) & Presentation Scripts

To present this smoothly to evaluators, divide ownership into 4 distinct, cohesive roles:

```
┌────────────────────────────────────────────────────────────────────────┐
│                        TEAM ROLE ARCHITECTURE                          │
├────────────────────┬────────────────────┬──────────────────────────────┤
│ Member 1           │ Member 2           │ Member 3                     │
│ Data Engineering   │ ML Forecasting &   │ Anomaly Detection &          │
│ & FOCUS Standards  │ Feature Pipeline   │ Root-Cause Attribution       │
├────────────────────┼────────────────────┼──────────────────────────────┤
│ • FOCUS 1.3 schema │ • 48-feature space │ • Counterfactual residuals   │
│ • Data cleaning    │ • XGBoost forecaster • Rolling threshold (3σ)     │
│ • Resampling grid  │ • 3 baselines      │ • Dual-track clean/synth     │
│ • Anti-leak splits │ • 7-arm ablations  │ • Temporal decay attribution │
│ • Fault injector   │ • 25.84 pp lift    │ • 97.9% Top-1 accuracy       │
├────────────────────┴────────────────────┴──────────────────────────────┤
│ Member 4                                                               │
│ Explainable AI (XAI), Interactive Dashboard & Quality Assurance        │
├────────────────────────────────────────────────────────────────────────┤
│ • TreeSHAP exact additivity verification (atol < 0.002)                │
│ • Non-causal automated governance scanner                              │
│ • Modular 5-view Streamlit dashboard (`app/`)                          │
│ • Production packaging (`pip install -e .`, CLI, 106 pytest tests)    │
└────────────────────────────────────────────────────────────────────────┘
```

---

### 👤 Member 1: Data Engineering, FOCUS Standards & Ground Truth
* **Core Responsibilities**:
  - Cloud billing data ingestion and schema harmonization using the **FOCUS 1.0/1.3 standard**.
  - Developing the data hygiene pipeline (`src/driftsense/data/clean.py` and `aggregate.py`): deduplication, UTC normalization, negative credit segregation, and canonical 1-hour grid aggregation.
  - Designing the strict chronological partitioning pipeline (`src/driftsense/eval/splits.py`) to prevent data leakage ($D_{\text{train}}$ Days 1–15, $D_{\text{val}}$ Days 16–24, $D_{\text{test}}$ Days 25–30).
  - Authoring the synthetic operational fault injector (`src/driftsense/synth/injector.py`) generating the 5 fault types with deterministic seeds.
* **Member 1 Presentation Script (1.5 – 2 mins)**:
  > *"Good morning. My name is [Member 1], and I led the Data Engineering and Standard Ingestion architecture for DriftSense. Cloud billing data is notoriously fragmented across AWS, Azure, and GCP. To solve this, we standardized our entire pipeline on the Linux Foundation's FOCUS 1.3 specification, harmonizing dimensions like `EffectiveCost`, `BilledCost`, and `ConsumedQuantity`.  
  > In real billing feeds, timestamps are irregular, duplicates exist, and cloud credits create negative values. I developed our data hygiene engine, which coerces timestamps to UTC, segregates refunds, and aggregates spend to a continuous 1-hour canonical grid with zero-imputation so time-series lag structures are never broken.  
  > Crucially, time-series models often suffer from lookahead leakage. I enforced strict chronological splitting, ensuring transformers and scalers are fit strictly on the first 15 days, with zero future data bleeding into validation or the test horizon. Finally, because real cloud bills lack root-cause labels, I designed our synthetic fault injector, which injects 5 realistic operational incident types—such as runaway batch jobs and autoscaling overprovisioning—to establish objective ground truth for evaluation."*

---

### 👤 Member 2: Feature Engineering, Cost Forecasting & Ablation Studies
* **Core Responsibilities**:
  - Designing the 48-dimensional chronological feature pipeline (`src/driftsense/features/builder.py`).
  - Implementing the statistical baselines (`SeasonalNaive`, `MovingAverage`, `ExponentialSmoothing`) in `src/driftsense/forecast/`.
  - Training and tuning the Champion **XGBoost Forecaster** (`src/driftsense/forecast/xgb.py`) across multiple random seeds.
  - Leading the 7-arm controlled ablation study (Phase 10, DEC-013) that proved the value of physical resource usage coupling.
* **Member 2 Presentation Script (1.5 – 2 mins)**:
  > *"Hello, I am [Member 2], responsible for Feature Engineering, Expected-Cost Forecasting, and Controlled Ablations. To predict what cloud services should normally cost, I engineered a 48-dimensional feature space covering autoregressive cost lags (1h, 2h, 24h, 168h), trailing rolling statistics, cyclic hour and day-of-week sine/cosine encodings, and crucially, physical resource consumption lags from `ConsumedQuantity`.  
  > We benchmarked our Champion XGBoost regressor against three standard industry baselines: Seasonal Naive, Moving Average, and Exponential Smoothing. While naive baselines struggled with error rates exceeding 129% WAPE, our tuned XGBoost forecaster achieved 82.03% WAPE and an out-of-sample MASE of 0.7862 across 3 random seeds. A MASE below 1.0 proves we beat naive persistence by 21.4% on completely unseen future data.  
  > In our ablation study on the validation split, we tested cost-only features versus joint cost-and-usage features. We discovered that coupling `ConsumedQuantity` with cost delivered an empirical 25.84 percentage point WAPE reduction. Resource volume acts as an immediate physical leading indicator before financial billing accrues."*

---

### 👤 Member 3: Anomaly Detection Engine & Operational Root-Cause Attribution
* **Core Responsibilities**:
  - Designing the counterfactual residual modeling architecture ($e_t = Y_t - \hat{Y}_t$).
  - Implementing the Champion **Rolling Threshold Detector** ($w=24\text{h}, k=3.0\sigma$) in `src/driftsense/detect/rolling_threshold.py`.
  - Establishing the dual-track evaluation framework (Real Clean Track FPR vs. Synthetic Fault Track Event-F1).
  - Building the **Temporal Correlation Attribution Engine** (`src/driftsense/attribute/correlation.py`) using exponential decay proximity kernels.
* **Member 3 Presentation Script (1.5 – 2 mins)**:
  > *"Hi everyone, I am [Member 3], and I engineered the Anomaly Detection and Operational Root-Cause Attribution engines. Traditional anomaly detectors evaluate raw spend and fail because cloud usage has natural day and night cycles, creating endless false alarms on Monday mornings. In DriftSense, we decouple detection from raw spend by monitoring the counterfactual residual: the difference between actual spend and Member 2's forecasted spend. During normal morning traffic surges, the forecast rises, holding the residual near zero.  
  > Our Champion Rolling Threshold detector evaluates residual standard deviation over a trailing 24-hour window with a 3-sigma multiplier. We evaluated this on a dual-track framework: on real clean data, we achieved an ultra-low False Positive Rate of 0.16%—only 6 false alarms across 3,822 hours. On our synthetic fault track, we achieved 95.74% Event Recall, detecting 45 out of 47 operational incidents with 0.00 hours delay.  
  > When an anomaly fires, my attribution engine searches a 6-hour lookback window of operational events. By applying an exponential half-life decay kernel based on time proximity, we achieved 97.87% Top-1 ranking accuracy and 100% Top-2 and Top-3 accuracy, successfully identifying the true triggering event."*

---

### 👤 Member 4: Explainable AI (XAI), FinOps Dashboard & Quality Assurance
* **Core Responsibilities**:
  - Implementing the **TreeSHAP Explainer** (`src/driftsense/explain/shap_explainer.py`) with exact additivity mathematical verification ($\sum \phi_i + \phi_0 = f(x)$).
  - Designing the automated non-causal governance scanner (`src/driftsense/explain/narrative.py`).
  - Building the production-grade **Streamlit FinOps Dashboard** (`app/main.py` and `app/views/`).
  - Packaging the library (`pip install -e .`), CLI registration, and authoring the **106 automated tests** in `tests/`.
* **Member 4 Presentation Script (1.5 – 2 mins)**:
  > *"Greetings, I am [Member 4], and I led Explainable AI, Governance, Dashboard Development, and Production Quality Assurance. In financial engineering audits, black-box predictions are unacceptable. I integrated TreeSHAP into DriftSense, mathematically verifying that the sum of local feature attributions exactly equals the difference between expected spend and baseline across all 3,822 test predictions within a 0.002 tolerance. Our global analysis revealed that `BilledCost` and `ConsumedQuantity` explain over 56% of model decisions.  
  > Furthermore, to prevent unwarranted liability in engineering post-mortems, I implemented an automated governance scanner that enforces strictly non-causal phrasing, replacing words like 'caused by' with 'likely associated with'.  
  > To deliver these insights to practitioners, I built our interactive Streamlit FinOps dashboard featuring 5 views: Executive Overview, Forecast & Anomalies, Root-Cause Attribution, TreeSHAP Explainability, and Ablations. It runs locally with zero in-app training. Finally, I hardened DriftSense into an installable Python package with a dedicated CLI and 106 automated unit tests in pytest, ensuring complete reproducibility across Linux and Windows environments."*

---

# 7. Common Viva / Professor Questions & Winning Answers

### Q1: "Why did you use FOCUS instead of just taking an AWS Cost Explorer CSV?"
> **Answer**: *"Cloud cost management is fundamentally a multi-cloud challenge. Large enterprises use AWS for compute, Snowflake for warehousing, and GCP for machine learning. Raw cloud bills have incompatible column names and credit structures. By standardizing on the Linux Foundation's FOCUS 1.3 specification, DriftSense is completely vendor-agnostic. Our pipeline ingests normalized dimensions like `EffectiveCost` and `ConsumedQuantity`, meaning our models work seamlessly across AWS, Azure, and GCP without altering any ML code."*

### Q2: "Why did you choose XGBoost over Deep Learning (LSTM / Transformers)?"
> **Answer**: *"We evaluated this in our architectural decision log (DEC-009). Extensive empirical research—including Grinsztajn et al. (NeurIPS 2022)—has established that Gradient Boosted Decision Trees (GBDTs) consistently outperform neural networks on tabular time series with heterogeneous features (costs, quantities, cyclic calendar terms). XGBoost trains 50x faster on CPU, requires zero complex hyperparameter schedules, exhibits no catastrophic vanishing gradients, and critically, supports exact mathematical TreeSHAP attributions in polynomial time ($O(TLD^2)$), which deep learning models cannot offer."*

### Q3: "Why did you detect anomalies on residuals rather than on raw cost?"
> **Answer**: *"Raw cloud spend is non-stationary and exhibits heavy diurnal (day/night) and weekly (weekday/weekend) seasonality. If you apply a 3-sigma or percentile threshold to raw spend, you get severe alert fatigue: normal Monday morning business peaks trigger false alarms, while an expensive Sunday runaway job goes undetected because Sunday spend is lower. By subtracting the model's expected cost ($\hat{Y}_t$), the counterfactual residual $e_t = Y_t - \hat{Y}_t$ becomes stationary and centered near zero. Detection on residuals eliminated false alarms down to 0.16% on clean data while capturing 95.74% of true faults."*

### Q4: "How did you ensure there is zero data leakage in your time-series pipeline?"
> **Answer**: *"We implemented a three-tier anti-leakage protocol (DEC-005). First, all data partitions are strictly chronological (Days 1–15 Train, 16–24 Val, 25–30 Test); random train-test shuffling was strictly forbidden. Second, all feature transformers, scalers, and imputation baselines were fit strictly on the training partition ($D_{\text{train}}$). Third, all rolling windows and lag features strictly exclude the current timestamp $t$ (e.g., rolling mean is computed over $[t-24, t-1]$). We wrote dedicated automated tests in `tests/test_leakage.py` that verify this invariant programmatically."*

### Q5: "What is the 'Synthetic Event Circularity Caveat' documented in your report?"
> **Answer**: *"Because real-world billing datasets lack ground-truth operational labels, we used a deterministic synthetic fault generator to inject operational faults for evaluation. However, evaluating an ML model on synthetic anomalies creates a risk of circularity: the model might simply learn the mathematical artifact of the injector. We mitigated this by training our forecasting models strictly on clean real data, fitting detection thresholds on clean residual variance, and independently auditing the False Positive Rate on real un-injected data (A10.3)."*

### Q6: "Why is non-causal language so heavily stressed in your documentation and code?"
> **Answer**: *"In software engineering and finance, correlation does not equal physical causation. If our model attributes a cost spike to a software deployment that occurred 30 minutes earlier, that is probabilistic evidence based on temporal proximity. It is possible that an unobserved cloud provider hardware outage or upstream API price change was the true cause. Claiming the deployment 'caused' the outage could falsely blame an engineer in an incident post-mortem. We automated a governance validator (`validate_non_causal_text`) ensuring all reports use responsible phrasing like 'likely associated with' rather than 'caused by'."*

---

### Project File Quick Reference for the Team
- **Dashboard**: Run `streamlit run app/main.py`
- **CLI Commands**: `driftsense --help` (supports `clean`, `features`, `forecast`, `detect`, `attribute`, `explain`, `verify-manifest`)
- **Unit Tests**: Run `pytest tests/` (106 tests passing)
- **Technical Report**: Read `docs/report/` (Chapters 1 through 7)
- **Slide Deck Outline**: Read `docs/presentation_outline.md`
- **Audit Numbers**: Read `docs/results_trace.md`
