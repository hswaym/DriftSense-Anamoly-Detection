# DriftSense — Final Report: Chapter 1. Executive Summary

## 1.1 Project Overview and Strategic Mission

Modern enterprise cloud spending is notoriously volatile, decentralized, and difficult to manage. Engineering teams deploy infrastructure continuously, leading to unexpected billing spikes, runaway batch jobs, misconfigurations, and sudden autoscaling storms. According to industry FinOps benchmarks, between 25% and 35% of overall enterprise cloud expenditure is wasted through idle capacity or undetected operational anomalies.

**DriftSense** is an open-source, production-grade cloud cost anomaly detection and operational root-cause attribution system built specifically around the **FinOps Open Cost & Usage Specification (FOCUS) v1.0 / v1.3**. Rather than relying on simplistic static thresholds or naive percentage alerts that trigger severe alert fatigue, DriftSense decomposes cloud billing into a four-pillar statistical and machine-learning framework:

1. **Counterfactual Expected-Cost Forecasting**: Establishing dynamic, seasonal baselines ($E[Y_t \mid X_t]$) for each cloud service using Gradient Boosted Decision Trees (XGBoost) trained on chronological usage and cost signals.
2. **Dual-Track Anomaly Detection**: Identifying true cost deviations through counterfactual residuals ($Y_t - \hat{Y}_t$) evaluated via rolling statistical thresholds, eliminating seasonal false alarms while guaranteeing high detection sensitivity.
3. **Probabilistic Root-Cause Attribution**: Correlating anomalous billing spikes with timestamped operational telemetry (deployments, autoscaling loops, config changes) using temporal decay kernels to rank likely operational drivers.
4. **Interpretable FinOps Governance (XAI)**: Providing mathematically additive TreeSHAP feature attributions alongside non-causal natural language audit narratives designed for FinOps practitioners and engineering leads.

---

## 1.2 Summary of Final Locked Test Horizon Findings

Under a strictly locked evaluation protocol (Phase 13, DEC-016), DriftSense was evaluated once on an unseen future test partition ($D_{\text{test}}$, Days 25–30, 3,822 hourly service observations) using cryptographically frozen configurations.

### Key Benchmark Achievements

| Benchmark Dimension | Baseline Metric | DriftSense Champion Performance | Verified Impact / Lift |
| :--- | :--- | :--- | :--- |
| **Forecasting Accuracy** | Seasonal Naive WAPE: `129.18%` | **XGBoost WAPE: 82.03% ± 1.52%** | **47.15 pp WAPE reduction**; MASE = 0.7862 (21.4% better than persistence) |
| **Alert Fatigue (Clean Track)** | Industry avg FPR: `~5.0%–10.0%` | **Rolling Threshold FPR: 0.16%** | Only 6 false alarms across 3,822 hours (0.15% weekday, 0.16% weekend) |
| **Anomaly Sensitivity (Fault Track)** | Unsupervised Point-F1: `~0.30–0.50` | **Event-F1: 0.9278 (Recall: 95.74%)** | **45 out of 47 operational events detected** with **0.00 hours detection delay** |
| **Root-Cause Attribution** | Class Prior Top-1: `27.66%` | **Temporal Correlation Top-1: 97.87%** | **46/47 incidents correctly attributed** (100.0% Top-2 & Top-3; MRR = 0.9894) |
| **Explainability Integrity** | Heuristic feature importances | **Exact TreeSHAP Additivity** | $\sum \phi_i + \phi_0 = f(x)$ verified ($\|\Delta\| < 0.002$); 100% non-causal compliance |

---

## 1.3 Key Architectural Innovations

1. **FOCUS 1.0/1.3 Standardization**: Native ingestion of canonical FinOps dimensions (`EffectiveCost`, `BilledCost`, `ConsumedQuantity`, `ServiceName`, `RegionName`), insulating the system from cloud provider schema lock-in.
2. **Coupled Cost + Usage Feature Engineering**: Incorporating resource consumption metrics (`ConsumedQuantity`) into cost autoregression yielded an empirical **25.84 percentage point WAPE reduction** over cost-only models.
3. **Decoupled Counterfactual Residuals**: Evaluating detection on residuals ($Y_t - \hat{Y}_t$) rather than raw cost completely eliminated false positives caused by expected diurnal and weekly seasonality.
4. **Temporal Proximity Attribution**: Operational root causes are scored using half-life exponential decay kernels ($lookback=6\text{h}, decay=2\text{h}$), outperforming static classification baselines by over 70 percentage points in Top-1 accuracy.
5. **Strict Governance & Anti-Leakage Protocol**: Full cryptographic reproducibility enforced via SHA-256 manifests, strict chronological partitioning, and formal non-causal phrasing guardrails.
