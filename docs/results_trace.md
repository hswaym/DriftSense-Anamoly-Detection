# DriftSense — Final Benchmark Results Traceability (Phase 13 & 14)

This document establishes the G1 Truth Rule audit trail for every reported metric in the DriftSense project. All values originate from cryptographically verified run manifests and immutable execution artifacts.

---

## 1. Locked Benchmark Run Provenance

- **Evaluation Partition**: $D_{\text{test}}$ (Days 25–30, `2024-09-25 00:00:00+00:00` to `2024-09-30 23:00:00+00:00` UTC)
- **Total Records Evaluated**: 3,822 hourly service observations
- **Run ID**: `run_20261020_183410_6f5272`
- **Execution Timestamp**: `2026-10-20T18:34:26+00:00`
- **Git Commit**: `2d9a0c384026c97a15ece6b3dcde5e082c5b0e04` (Clean working tree)
- **Python Version**: 3.13.16 on Linux x86_64 (12.67 GB RAM)
- **Protocol Reference**: `docs/final_results_protocol.md` (DEC-016)
- **Manifest Location**: `runs/run_20261020_183410_6f5272/manifest.json`

### Cryptographic Artifact Digest Ledger

| Artifact Path | File Size (Bytes) | Cryptographic SHA-256 Digest |
| :--- | :--- | :--- |
| `final_test_results.json` | 11,988 | `09e6ebdc15c1ff69f349e0751e15e54be917bbadf6943e1192da11837b481495` |
| `test_forecast_and_alerts.csv` | 254,815 | `272a2b063905e490bc8a86c3c2db045490b4accf40ac0d07c79d924c4d358a9c` |
| `test_audit_narratives.md` | 3,396 | `b52b8c9bce4f61de68598e816d220208503eca99c6ee29c1a65b0e4fb915fd40` |
| `test_shap_importance.csv` | 3,289 | `7f13b5dd26105694b5f784831032a62339e7ae5b87ba4b994b7b5f8585d285e3` |

---

## 2. Pillar I: Expected-Cost Forecaster Benchmark Metrics ($D_{\text{test}}$)

All models evaluated strictly on unseen chronological test partition $D_{\text{test}}$. XGBoost champion evaluated across 3 random seeds (`[42, 123, 999]`).

| Model Name | WAPE (%) | MAE ($) | RMSE ($) | MASE | Primary Source Key |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Seasonal Naive ($s=24$)** | 129.18% | $0.0186 | $0.1833 | 1.2381 | `forecast.seasonal_naive` |
| **Moving Average ($w=24$)** | 150.32% | $0.0216 | $0.1760 | 1.4407 | `forecast.moving_average` |
| **Exponential Smoothing ($\alpha=0.25$)** | 144.24% | $0.0208 | $0.1767 | 1.3825 | `forecast.exponential_smoothing` |
| **Champion XGBoost (Seed 42)** | 80.74% | $0.0116 | $0.1362 | 0.7739 | `forecast.xgboost_champion.seed_runs[0]` |
| **Champion XGBoost (Seed 123)** | 84.16% | $0.0121 | $0.1412 | 0.8066 | `forecast.xgboost_champion.seed_runs[1]` |
| **Champion XGBoost (Seed 999)** | 81.19% | $0.0117 | $0.1355 | 0.7782 | `forecast.xgboost_champion.seed_runs[2]` |
| **Champion XGBoost (Mean ± Std)** | **82.03% ± 1.52%** | **$0.0118 ± $0.0002** | **$0.1376 ± $0.0025** | **0.7862 ± 0.0145** | `forecast.xgboost_champion` summary |

*Audit Verification*: MASE of 0.7862 demonstrates a **21.38% reduction in relative error** compared to naive persistence baseline on out-of-sample unseen data.

---

## 3. Pillar II: Anomaly Detection Dual-Track Benchmark Metrics ($D_{\text{test}}$)

Champion Rolling Threshold detector ($w=24\text{h}$, multiplier $k=3.0$).

### Track A: Real Clean Track (Operational Alert Fatigue Audit)

| Metric | Measured Value | Evaluation Target | Audit Verification |
| :--- | :--- | :--- | :--- |
| **Total Clean Evaluation Hours** | 3,822 hours | All records in $D_{\text{test}}$ | Verified in `detection.clean_track.total_clean_points` |
| **False Alarms Triggered** | 6 alarms | Minimum possible | Verified in `detection.clean_track.false_alarms` |
| **Overall False Positive Rate (FPR)** | **0.16%** (0.00157) | $\le 1.0\%$ | Verified in `detection.clean_track.fpr_overall` |
| **Weekday False Positive Rate** | **0.15%** (0.00155) | $\le 1.0\%$ | Verified in `detection.clean_track.fpr_weekday` |
| **Weekend False Positive Rate** | **0.16%** (0.00162) | $\le 1.0\%$ | Verified in `detection.clean_track.fpr_weekend` |

### Track B: Synthetic Ground Truth Track (Detection Sensitivity Audit)

Evaluated against 47 injected operational anomaly episodes spanning 5 fault types:

| Metric | Measured Value | Primary Source Key |
| :--- | :--- | :--- |
| **Point Precision** | 96.03% (0.9603) | `detection.synthetic_track.point_precision` |
| **Point Recall** | 63.68% (0.6368) | `detection.synthetic_track.point_recall` |
| **Point F1-Score** | **0.7658** | `detection.synthetic_track.point_f1` |
| **Event Precision** | 90.00% (0.9000) | `detection.synthetic_track.event_precision` |
| **Event Recall** | **95.74%** (45 / 47 events) | `detection.synthetic_track.event_recall` |
| **Event F1-Score** | **0.9278** | `detection.synthetic_track.event_f1` |
| **Mean Detection Delay** | **0.00 hours** | `detection.synthetic_track.mean_delay_hours` |

---

## 4. Pillar III: Root-Cause Attribution Engine Benchmark Metrics ($D_{\text{test}}$)

Evaluated across 47 ground-truth incidents occurring during the test horizon:

| Attribution Method | Top-1 Accuracy (%) | Top-2 Accuracy (%) | Top-3 Accuracy (%) | MRR | Source Key |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Random Baseline** | 4.26% | 23.40% | 42.55% | 0.3099 | `attribution.baseline_random` |
| **Class Prior Baseline** | 27.66% | 53.19% | 76.60% | 0.4908 | `attribution.baseline_prior` |
| **Champion Temporal Correlation** | **97.87%** (46/47) | **100.0%** (47/47) | **100.0%** (47/47) | **0.9894** | `attribution.champion_correlation` |

---

## 5. Pillar IV: Explainability & Governance Verification ($D_{\text{test}}$)

- **TreeSHAP Additivity Invariant**: $\sum \phi_i(x) + \phi_0 = f(x)$ verified on 3,822 test predictions. Max absolute summation discrepancy $< 0.002$ (clearing strict additivity).
- **Top 5 Global Feature Drivers**:
  1. `BilledCost`: 48.18% relative importance ($\text{mean}\|\text{SHAP}\| = 0.00941$)
  2. `ConsumedQuantity`: 8.46% relative importance ($\text{mean}\|\text{SHAP}\| = 0.00165$)
  3. `day_of_month`: 3.71% relative importance ($\text{mean}\|\text{SHAP}\| = 0.00072$)
  4. `EffectiveCost_roll_mean_168h`: 3.70% relative importance ($\text{mean}\|\text{SHAP}\| = 0.00072$)
  5. `EffectiveCost_roll_max_24h`: 3.12% relative importance ($\text{mean}\|\text{SHAP}\| = 0.00061$)
- **Non-Causal Language Compliance**: 100% of generated executive audit narratives pass `validate_non_causal_text()` assertion check. Zero prohibited causal verbs ("caused", "triggered", "resulted from") present in output narratives.
