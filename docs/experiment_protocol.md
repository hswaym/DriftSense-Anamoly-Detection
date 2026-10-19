# DriftSense Controlled Experiment & Ablation Protocol

**Status**: FROZEN BEFORE EXECUTION  
**Version**: 1.0.0  
**Phase**: PHASE 10 (Controlled Experiments and Ablations)  
**Standard**: FinOps FOCUS 1.0 / 1.3 Specification  
**Target Variable**: `EffectiveCost`  
**Time Horizon**: Hourly aggregation (`1h`), Chronological Validation Partition ($D_{\text{val}}$, Days 16–24)  
**Test Quarantine**: $D_{\text{test}}$ (Days 25–30) is strictly quarantined and excluded from all Phase 10 experiments.

---

## 1. Objective and Scientific Rationale

The objective of Phase 10 is to isolate and quantify the marginal performance contributions of individual feature families, algorithmic architectures, and operational telemetry streams. By holding temporal evaluation windows, test splits, metric formulations, and preprocessing strictly invariant across all experimental arms, we eliminate confounding variables and measure true algorithmic effect sizes with empirical variance ($\text{mean} \pm \text{std}$) across $\ge 3$ random seeds.

---

## 2. Experimental Arms Specification

### Arm 1: Cost-Only Feature Representation
- **Hypothesis**: Historical cost autoregression alone captures baseline diurnal and weekly spend cycles but lacks operational elasticity context.
- **Included Feature Subsets**:
  - Cost Autoregressive Lags: `EffectiveCost_lag_1h`, `EffectiveCost_lag_2h`, `EffectiveCost_lag_3h`, `EffectiveCost_lag_24h`, `EffectiveCost_lag_168h`
  - Cost Rolling Statistics: `EffectiveCost_roll_mean_*`, `EffectiveCost_roll_std_*`, `EffectiveCost_roll_min_*`, `EffectiveCost_roll_max_*` for windows $\tau \in \{3\text{h}, 6\text{h}, 24\text{h}, 168\text{h}\}$
  - Temporal & Calendar Encodings: `hour_of_day`, `day_of_week`, `day_of_month`, `is_weekend`, `sin_hour`, `cos_hour`, `sin_dow`, `cos_dow`
- **Excluded Feature Subsets**:
  - All resource usage metrics (`ConsumedQuantity*`)
  - All operational event telemetry (`event_*`)

### Arm 2: Cost + Usage Feature Representation
- **Hypothesis**: Coupling resource utilization (`ConsumedQuantity`) with billed spend enables the model to distinguish price rate anomalies (e.g. on-demand fallback) from organic workload scaling (e.g. traffic surges).
- **Included Feature Subsets**:
  - All Arm 1 Cost & Calendar Features
  - Resource Usage Lags: `ConsumedQuantity_lag_1h`, `ConsumedQuantity_lag_2h`, `ConsumedQuantity_lag_24h`
  - Resource Usage Rolling Windows: `ConsumedQuantity_roll_mean_6h`, `ConsumedQuantity_roll_mean_24h`, `ConsumedQuantity_roll_std_24h`
  - Unit Cost / Intensity Ratios: `EffectiveCost_to_ConsumedQuantity_ratio`
- **Excluded Feature Subsets**:
  - All operational event telemetry (`event_*`)

### Arm 3: Cost + Usage + Events Feature Representation
- **Hypothesis**: Injecting real-time CI/CD deployments and configuration change events reduces false alarms during scheduled releases and sharpens anomaly onset residuals.
- **Included Feature Subsets**:
  - All Arm 2 Cost, Usage, & Calendar Features
  - Operational Event Signals: Deployment indicators, configuration changes, scheduled maintenance flags within a rolling $k$-hour window.
- **Circularity Caveat (A10.3)**:
  - *Critical Scientific Caution*: On the synthetic injection track, synthetic cost anomalies are co-generated alongside synthetic event logs. Evaluating event features on synthetic data carries inherent circularity (the model can learn to "cheat" by directly keying off injected event timestamps).
  - *Mitigation & Reporting*: Synthetic track metrics for Arm 3 are explicitly flagged with a circularity disclaimer. Real data track metrics evaluate whether background cloud activity logs provide non-trivial predictive signal.

### Arm 4: Baseline vs. Advanced Architectures
- **Hypothesis**: Non-linear gradient boosted ensembles with log-transform target handling substantially outperform linear and heuristic time-series baselines.
- **Forecasting Comparison**:
  - Baselines: Seasonal Naive ($s=24$), Moving Average ($w=24$), Exponential Smoothing ($\alpha=0.25$)
  - Advanced Champion: XGBoost Forecaster with `log1p` target transformation, `n_estimators=150`, `max_depth=5`, `learning_rate=0.05`
- **Anomaly Detection Comparison**:
  - Baseline: Static Z-Score Residual Detector ($k=3.0\sigma$)
  - Advanced Champion: Rolling Dynamic Quantile/Threshold Detector ($w=24\text{h}$, dynamic band multiplier)

### Arm 5: Root-Cause Attribution With vs. Without Event Information
- **Hypothesis**: Temporal correlation with operational deployment logs provides high-precision root-cause identification, whereas uninformed static priors fail under concurrent multi-service background noise.
- **Attribution Comparison**:
  - Uninformed Baseline: Random Uniform Guessing & Historical Service Frequency Prior
  - Advanced Attribution: Temporal Correlation Attributor with exponential decay ($\lambda=1\text{h}$) and multi-modal XGBoost incident ranker.
- **Metrics**: Top-1 Accuracy, Top-2 Accuracy, Top-3 Accuracy on 27 validation incident scenarios.

### Arm 6: Temporal Generalization on Unseen Time Periods
- **Hypothesis**: Model forecast accuracy degrades gracefully across expanding forward horizons rather than experiencing catastrophic concept drift.
- **Evaluation Design**:
  - Split $D_{\text{val}}$ chronologically into:
    - Early Validation Window ($D_{\text{val, early}}$: Days 16–20)
    - Late Validation Window ($D_{\text{val, late}}$: Days 20–24)
  - Train on $D_{\text{train}}$ (Days 1–15) only; evaluate WAPE, MASE, and residual calibration across both unseen temporal segments.

### Arm 7: Seasonality and Workload-Change False Positive Robustness
- **Hypothesis**: The champion anomaly detector maintains a low false positive rate ($\text{FPR} \le 1.0\%$) across both high-load business hours (diurnal peaks) and low-load periods (off-peak / weekends), preventing alert fatigue.
- **Evaluation Subgroups**:
  - Peak Business Hours: Monday–Friday 09:00–18:00 UTC
  - Off-Peak / Weekend Hours: Saturdays, Sundays, and night windows (00:00–06:00 UTC)
  - Metrics: Subgroup FPR and False Positive count on clean, uncorrupted validation data.

---

## 3. Strict Experimental Invariants and Controls

1. **Identical Partitions**: All arms use the exact same training split ($D_{\text{train}}$, 14,949 rows) and validation split ($D_{\text{val}}$, 4,983 rows).
2. **Zero Test Contamination**: Test set ($D_{\text{test}}$, Days 25–30) is never accessed or referenced.
3. **Random Seed Variance**: All stochastic runs are repeated across $S = 3$ predefined seeds: $\{42, 123, 999\}$. Results report $\mu \pm \sigma$.
4. **Primary Metrics**:
   - Forecasting: $\text{WAPE} = \frac{\sum |y - \hat{y}|}{\sum y}$, $\text{MASE} = \frac{\text{MAE}}{\text{MAE}_{\text{naive}}}$, $\text{RMSE} = \sqrt{\frac{1}{N}\sum(y - \hat{y})^2}$
   - Anomaly Detection: $\text{FPR} = \frac{\text{FP}}{\text{FP} + \text{TN}}$ on uncorrupted validation data; $\text{Event-F1}$, Precision, Recall on synthetic track.
   - Root-Cause Attribution: Top-1, Top-2, Top-3 Accuracy.
5. **Cryptographic Provenance**: This document's SHA-256 hash is computed before execution and recorded in `manifest.json`.
