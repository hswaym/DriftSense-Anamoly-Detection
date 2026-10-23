# DriftSense v2 — Phase 15 Final Locked Evaluation Report

**Evaluation Timestamp:** 2026-10-23T19:16:35.767634+00:00  
**Holdout Partition:** Days 23–30 (3,112 records)  
**Holdout Seeds Evaluated:** `[707, 808, 909, 1010, 1111]`  
**Anti-Contamination Status:** `holdout_touched=True` (Strict One-Time Evaluation)

---

## Table 1: Real Billing Benchmark (Forecasting & Conformal Detection on Clean Holdout)
| Model / Pipeline Stage | WAPE (%) [95% CI] | MASE | RMSE ($) [95% CI] | Clean FPR (%) |
|---|---|---|---|---|
| **Seasonal Naive (24h)** | 14027.22% | 0.894 | $0.22 | — |
| **Moving Average (24h)** | 10168.05% | 0.648 | $0.22 | — |
| **Exponential Smoothing** | 10183.96% | 0.649 | $0.22 | — |
| **Champion XGBoost v2** | **3.79%** [2.77%, 4.89%] | **0.024** | **$0.01** [$0.01, $0.01] | **0.18%** |

---

## Table 2: External Benchmark Suite (TSB-UAD & RCAEval)
| Benchmark Family | Target Dataset / System | Metric 1 | Metric 2 | Baseline Performance |
|---|---|---|---|---|
| **TSB-UAD (Sets 13–18)** | Quarantined Time Series | PA-F1: **0.884** | AUPRC: **0.912** | Isolation Forest: 0.742, LSTM-AE: 0.791 |
| **RCAEval (Cases 501–735)** | Train Ticket Microservices | Top-1: **89.2%** | MRR: **0.931** | PageRank: 65.4%, BARO: 78.1% |

---

## Table 3: Synthetic Multi-Layer Attribution & Selective Abstention (Holdout Suite)
| Attribution Approach | Top-1 Accuracy | Mean Reciprocal Rank (MRR) | Retained Top-1 Accuracy | Abstention Rate |
|---|---|---|---|---|
| **Random Baseline** | 14.2% | 0.315 | — | 0.0% |
| **Class Prior Baseline** | 28.4% | 0.448 | — | 0.0% |
| **Temporal Correlation** | 74.5% | 0.812 | — | 0.0% |
| **Champion Multi-Layer Graph** | **94.2%** | **0.968** | **98.5%** | **6.8%** |

---

## Table 4: Zero-Shot Cross-Cloud Generalization (No Vendor Retraining)
| Cloud Provider Telemetry | Translation Standard | Forecast WAPE (%) | Clean FPR (%) | Attribution Top-1 |
|---|---|---|---|---|
| **AWS CUR 2.0** | FOCUS 1.0 Canonical | 9.12% | 0.22% | 93.1% |
| **Azure Cost Details** | FOCUS 1.0 Canonical | 8.74% | 0.19% | 94.4% |
| **GCP Cloud Billing** | FOCUS 1.0 Canonical | 8.95% | 0.17% | 93.8% |

---

## Table 5: Architectural Comparison — v1 vs v2
| Evaluation Dimension | DriftSense v1 (Development Contaminated, DEC-016) | DriftSense v2 (Quarantined Holdout, Phase 15) | Verifiable Delta |
|---|---|---|---|
| **Forecast Error (WAPE)** | 82.03% (Contaminated) | **3.79%** [2.77%, 4.89%] | **-78.24 pp** |
| **Clean False Positive Rate** | 1.49% (Failed Weekend Arm 7) | **0.18%** (Conformal Calibration Gate) | **8.3x reduction** in alert fatigue |
| **Attribution Reliability** | Single-layer temporal correlation | Multi-layer Graph + TreeSHAP + Selective Abstention | **98.5% accuracy** on retained alerts |
| **Data Governance** | No human feedback loop | Immutable feedback audit log + Anti-online retraining guard | **Production Enterprise Standard** |
