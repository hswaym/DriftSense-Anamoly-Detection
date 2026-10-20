# DriftSense — Final Report: Chapter 5. Experimental Results & Ablation Analysis

This chapter details the quantitative empirical findings from the controlled validation ablations (Phase 10) and the final benchmark evaluation on the locked test partition ($D_{\text{test}}$, Days 25–30, 3,822 records, Run `run_20261020_183410_6f5272`, DEC-016).

---

## 5.1 Controlled Feature Ablation Study (Phase 10, DEC-013)

Before evaluating on the locked test partition, a 7-arm controlled ablation experiment was conducted on the validation split ($D_{\text{val}}$, Days 16–24) across 3 random seeds (`[42, 123, 999]`) to quantify the exact contribution of each feature family.

### Validation Partition Ablation Summary

| Arm ID | Feature Configuration | WAPE Mean ± Std (%) | MAE ($) | MASE | Key Finding / Lift |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Arm 1** | Baseline Cost Only (Lags + Rolls) | 87.99% ± 0.00% | $0.0152 | 0.5113 | Autoregressive baseline |
| **Arm 2** | **Cost + Usage (`ConsumedQuantity`)** | **62.15% ± 0.00%** | **$0.0107** | **0.3612** | **+25.84 pp WAPE reduction** |
| **Arm 3** | Cost + Usage + Calendar Terms | 62.15% ± 0.00% | $0.0107 | 0.3612 | Calendar captured by lags |
| **Arm 4** | Cost + Usage + Full Event Indicators | 62.08% ± 0.00% | $0.0107 | 0.3608 | Modest lift; circularity caveat |
| **Arm 5** | Seasonal Naive Baseline | 140.15% ± 0.00% | $0.0242 | 0.8145 | Naive persistence reference |
| **Arm 6** | Moving Average Baseline | 158.42% ± 0.00% | $0.0273 | 0.9207 | Simple smoothing reference |
| **Arm 7** | Exponential Smoothing Baseline | 149.33% ± 0.00% | $0.0258 | 0.8679 | Exponential moving average |

> **Key Finding (Usage Coupling)**: Coupling resource consumption (`ConsumedQuantity`) with cost autoregression drove a **25.84 percentage point WAPE reduction** (from 87.99% down to 62.15%). Resource volume acts as an immediate physical precursor to billing accrual.

---

## 5.2 Final Benchmark Evaluation on Locked Test Horizon ($D_{\text{test}}$)

Under the locked evaluation protocol (A13.1–A13.3, DEC-016), the complete DriftSense pipeline was evaluated on the unseen test horizon ($D_{\text{test}}$, 2024-09-25 00:00:00 to 2024-09-30 23:00:00 UTC).

### 5.2.1 Forecaster Benchmark Results

| Model | WAPE (%) | MAE ($) | RMSE ($) | MASE | Outcome |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Seasonal Naive ($s=24$)** | 129.18% | $0.0186 | $0.1833 | 1.2381 | Fails persistence test ($\text{MASE} > 1$) |
| **Moving Average ($w=24$)** | 150.32% | $0.0216 | $0.1760 | 1.4407 | Significant lag distortion |
| **Exponential Smoothing ($\alpha=0.25$)** | 144.24% | $0.0208 | $0.1767 | 1.3825 | Oversmoothes abrupt peaks |
| **Champion XGBoost (3 seeds)** | **82.03% ± 1.52%** | **$0.0118 ± $0.0002** | **$0.1376 ± $0.0025** | **0.7862 ± 0.0145** | **Beats persistence by 21.4%** |

* Seed-level variance: Seed 42 = 80.74% WAPE, Seed 123 = 84.16% WAPE, Seed 999 = 81.19% WAPE. The low standard deviation (1.52%) confirms model stability across random initializations.

---

### 5.2.2 Dual-Track Anomaly Detection Results

#### Real Clean Track (False Positive Rate Audit)
* **Total Clean Evaluation Hours**: 3,822 hours
* **False Alarms Triggered**: 6 alerts
* **Overall FPR**: **0.16%** (0.00157)
* **Weekday FPR**: **0.15%** (5 alarms / 3,235 hours)
* **Weekend FPR**: **0.16%** (1 alarm / 587 hours)
* *Significance*: Completely clears the operational constraint ($\le 1.0\%$), guaranteeing that engineering teams will not experience alarm fatigue during routine operations.

#### Synthetic Ground Truth Track (Sensitivity & Timeliness Audit)
Evaluated across 47 ground-truth fault injection episodes:
* **Point-Level Precision**: **96.03%**
* **Point-Level Recall**: **63.68%**
* **Point-Level F1**: **0.7658**
* **Event-Level Precision**: **90.00%**
* **Event-Level Recall**: **95.74%** (45 out of 47 operational events successfully detected)
* **Event-Level F1**: **0.9278**
* **Mean Detection Delay**: **0.00 hours** (instantaneous alert triggered on the first hour of fault onset)

---

### 5.2.3 Root-Cause Attribution Engine Benchmark Results

Evaluated across 47 ground-truth operational incidents occurring during $D_{\text{test}}$:

| Method | Top-1 Accuracy | Top-2 Accuracy | Top-3 Accuracy | Mean Reciprocal Rank (MRR) |
| :--- | :--- | :--- | :--- | :--- |
| **Random Baseline** | 4.26% (2/47) | 23.40% (11/47) | 42.55% (20/47) | 0.3099 |
| **Class Prior Baseline** | 27.66% (13/47) | 53.19% (25/47) | 76.60% (36/47) | 0.4908 |
| **Champion Temporal Correlation** | **97.87%** (46/47) | **100.0%** (47/47) | **100.0%** (47/47) | **0.9894** |

#### Confusion Matrix Breakdown for Temporal Correlation
* `AUTOSCALING_OVERPROVISION`: 2/3 correct (66.7% recall; 1 misclassified as `DEPLOYMENT_DEFECT`)
* `CONFIG_MODIFICATION`: 11/11 correct (100.0% recall)
* `DEPLOYMENT_DEFECT`: 13/13 correct (100.0% recall)
* `EXTERNAL_TRAFFIC_SURGE`: 12/12 correct (100.0% recall)
* `RUNAWAY_BATCH_PROCESS`: 8/8 correct (100.0% recall)

---

### 5.2.4 Explainability & TreeSHAP Cost Drivers

TreeSHAP additivity verification passed across all 3,822 test instances ($\max |\Delta| < 0.002$).

#### Top-5 Global Feature Drivers on Test Horizon
1. **`BilledCost`**: 48.18% relative importance ($\text{mean}\|\text{SHAP}\| = 0.00941$) — Primary unadjusted billing baseline.
2. **`ConsumedQuantity`**: 8.46% relative importance ($\text{mean}\|\text{SHAP}\| = 0.00165$) — Resource volume multiplier.
3. **`day_of_month`**: 3.71% relative importance ($\text{mean}\|\text{SHAP}\| = 0.00072$) — Monthly cycle baseline.
4. **`EffectiveCost_roll_mean_168h`**: 3.70% relative importance ($\text{mean}\|\text{SHAP}\| = 0.00072$) — Weekly baseline spend.
5. **`EffectiveCost_roll_max_24h`**: 3.12% relative importance ($\text{mean}\|\text{SHAP}\| = 0.00061$) — Trailing peak capacity.

Cumulative importance of the top-5 features accounts for **67.16%** of total forecaster decision weight.
