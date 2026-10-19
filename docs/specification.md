# DriftSense — Technical Specification

## 1. Project Overview & Objectives
**DriftSense** is an explainable Data Science and Machine Learning framework for cloud cost anomaly detection and operational root-cause attribution. Moving beyond binary threshold alerting ("your bill is unusually high"), DriftSense answers three operational questions:
1. **What was expected?** (Counterfactual / baseline expected cost forecasting)
2. **What actually happened?** (Quantitative anomaly detection and deviation estimation)
3. **Why did the cost increase?** (Multi-source operational event alignment, feature attribution, and explainable AI)

### Core Research Question
*Can a machine-learning system combining time-series forecasting, anomaly detection, and explainable cause attribution identify and explain unexpected cloud-cost increases more effectively than traditional statistical threshold methods?*

### Formal Scope & Non-Claims
As established in the research foundation:
- **Correlation $\neq$ Causation**: Feature importance and correlation do not constitute mathematical causal proof. Attributions are ranked probabilistic evidence.
- **Controlled Synthetic Ground Truth**: Where real cloud telemetry lacks ground-truth cause labels, controlled synthetic fault injection is utilized and explicitly segregated from real data.
- **Research Prototype**: The system is designed as an experimentally evaluated data science research prototype, benchmarked on standardized cloud billing specifications.

---

## 2. Architecture & System Pipeline

The end-to-end pipeline consists of sequential, decoupled stages:
```
[Cloud Cost Data (FOCUS 1.3)] + [Operational Telemetry & Injected Events]
                             │
                             ▼
              [Stage 3: Data Cleaning & Harmonization]
                             │
                             ▼
              [Stage 4: Exploratory Data Analysis]
                             │
                             ▼
              [Stage 5: Feature Engineering (Lags, Windows, Events)]
                             │
                             ▼
              [Stage 6: Counterfactual Expected-Cost Forecasting]
                             │
                             ▼
              [Stage 7: Anomaly Detection (Deviation Scoring)]
                             │
                             ▼
              [Stage 8: Cause Attribution & Operational Alignment]
                             │
                             ▼
              [Stage 9: Explainable AI (SHAP & Feature Attributions)]
                             │
                             ▼
          [Stage 10: Model Comparison & Ablation Suite]
                             │
                             ▼
          [Stage 11: Interactive Streamlit Dashboard]
```

---

## 3. Data Specification & Integration

### Primary Ingestion: FinOps Open Cost and Usage Specification (FOCUS)
- **Standard**: FOCUS 1.3 Cost and Usage specification.
- **Key Dimensions**: `ProviderName`, `ServiceName`, `SubAccountId` / `BillingAccountId`, `RegionId`, `ResourceId`, `ChargeCategory`.
- **Key Metrics**: `BilledCost`, `EffectiveCost`, `PricingQuantity`, `ConsumedQuantity`, `PricingUnit`.
- **Intervals**: Standardized UTC timestamps aggregated to canonical grain.

### Secondary Ingestion: Operational Events & Telemetry
To bridge the dataset gap between billing spikes and operational triggers:
- **Event Dimensions**: `event_id`, `timestamp_start`, `timestamp_end`, `service_id`, `event_type`, `event_source`, `metadata`.
- **Event Taxonomies**:
  1. `DEPLOYMENT`: Code deployments, container revisions, CI/CD pipeline triggers.
  2. `SCALING`: Horizontal autoscaling, replica set increases, cluster expansions.
  3. `CONFIG_CHANGE`: Instance resizing, tier upgrades, provisioned IOPS modifications.
  4. `TRAFFIC_SURGE`: Request spikes, ingress/egress anomalies, query volume changes.
  5. `STORAGE_GROWTH`: Unattached volume retention, snapshot accumulation, bucket expansion.
  6. `BACKGROUND_BATCH`: Unscheduled batch jobs, re-indexing, ETL runaway tasks.

---

## 4. Modeling & Algorithmic Framework

### Stage 6: Expected Cost Forecasting
- **Goal**: Model expected baseline spend $E_t$ at time $t$ had normal operating conditions persisted.
- **Candidate Models**:
  - Naive baseline (Moving Average, Historical Mean / Exponential Smoothing)
  - Statistical time-series: ARIMA / SARIMA
  - Machine Learning regression: Gradient Boosted Trees (XGBoost / LightGBM)
  - Deep Learning (Optional / Phase-dependent): LSTM / GRU if dataset depth warrants.

### Stage 7: Anomaly Detection
- **Goal**: Quantify residual deviation $R_t = |Y_t - E_t|$ and classify anomalies $A_t \in \{0, 1\}$.
- **Candidate Detectors**:
  - Statistical thresholding: Dynamic Z-score, rolling median absolute deviation (MAD).
  - Unsupervised Machine Learning: Isolation Forest, One-Class SVM.

### Stage 8 & 9: Cause Attribution & Explainability
- **Goal**: Rank probable causes and generate human-interpretable explanations.
- **Attribution Engine**: Temporal proximity alignment, multi-variate feature correlation, and ranked anomaly scoring.
- **Explainability**: SHAP (SHapley Additive exPlanations) values quantifying marginal contributions of event indicators, usage metrics, and temporal lags.

---

## 5. Evaluation Protocol & Metrics

### 1. Forecasting Metrics
- Mean Absolute Error (MAE)
- Root Mean Squared Error (RMSE)
- Symmetric Mean Absolute Percentage Error (sMAPE) / Weighted Absolute Percentage Error (WAPE) *(chosen over standard MAPE to prevent zero-cost division instability)*.

### 2. Anomaly Detection Metrics
- Precision, Recall, F1-Score
- False Positive Rate (FPR)
- Point-adjusted event-level Precision/Recall.

### 3. Attribution Metrics
- Top-1 Cause Accuracy
- Top-3 Cause Accuracy
- Attribution Precision, Recall, F1.

### 4. Ablation & Contribution Experiments
- Cost-only features vs. Cost + Usage features.
- Cost + Usage vs. Cost + Usage + Operational Events.
- Impact of removing deployment/event indicators on root-cause accuracy.

---

## 6. Visualization & Interface (Streamlit)
- **Time-Series Overview**: Actual vs. Expected spend across selected grain.
- **Anomaly Inspection**: Highlighted anomaly windows with residual magnitude.
- **Root-Cause Attribution Panel**: Top-3 ranked operational events aligned by timestamp.
- **Explainability Plotting**: SHAP force/waterfall plots decomposing cost drivers.
