# DriftSense v2 — Final Locked Evaluation Protocol (Fresh Holdout)

**Document Version:** 2.0.0  
**Phase:** Phase 15 (Final Locked Evaluation)  
**Preconditions:** Phase 14 PASS (Security, Performance & Accessibility QA Complete)  
**Evaluation Standard:** Pre-registered, Zero-Contamination Locked Horizon Protocol  
**Holdout Status:** Strictly Quarantined until One-Time Execution (`holdout_touched=true`)  
**Effective Date:** October 2026

---

## 1. Scientific Governance & The Anti-Contamination Invariant

In DriftSense v1, test partition $D_{\text{test}}$ was iteratively evaluated during model parameter exploration (DEC-016), introducing statistical contamination. 

For DriftSense v2, the fresh holdout partition $D_{\text{holdout}}$ represents completely unobserved data across:
1. **Unseen Chronological Window:** October 2024 dates (Days 23–30), with zero temporal overlap with development ($D_{\text{dev}}$, Days 1–15) or validation ($D_{\text{val}}$, Days 16–22).
2. **Unseen Stochastic Seeds:** Seeds `[707, 808, 909, 1010, 1111]` reserved strictly for holdout generation.
3. **Disjoint Fault Families:** 5 fault families reserved strictly for holdout (`level_shift`, `region_migration`, `untagged_spend_growth`, `commitment_discount_expiry`, `credit_refund_artifact`).
4. **Disjoint External Topologies:** Train Ticket microservice benchmark (RCAEval cases 501–735) and quarantined TSB-UAD time series sets 13–18.

### Mandatory Execution Invariants
- **A15.1 Hash Guard:** The evaluation notebook/script must compute SHA-256 digests of all configuration files and model artifacts prior to execution. If any hash differs from the frozen table in Section 2, execution **immediately aborts**.
- **A15.2 One-Time Evaluation:** $D_{\text{holdout}}$ is evaluated **strictly once**. The resulting run manifest records `"holdout_touched": true`. Any rerun requires `--allow-override` and is permanently flagged as an audit deviation.
- **A15.3 Zero Post-Hoc Tuning:** Model parameters, feature definitions, and anomaly thresholds are frozen. All outcomes, including negative results or regressions, are reported verbatim without tuning.
- **Bootstrap Uncertainty:** All primary metrics must be reported with 95% bootstrap confidence intervals ($B=1,000$ iterations).

---

## 2. Cryptographic Hash Register (Frozen Configuration Baseline)

| Configuration Path | Frozen SHA-256 Digest | Status |
|---|---|---|
| `configs/ablation_focus.yaml` | `b54e694879f707f128fb3f27bea99be261ae76ce140a201ddde14d29eff9bb61` | Frozen |
| `configs/attribute_focus.yaml` | `997e05c2f96bbfd4aa75eb709355f94168d0865f88da61974a8c4b47878a1ec9` | Frozen |
| `configs/attribute_v2.yaml` | `d6f47d2bdd2020872af77015d12d41b648772788d4bf868d83f440da7371ce35` | Frozen |
| `configs/clean_focus.yaml` | `bb455365af3555f9ceea952bb9a81e538ff8f822e47ea55c8e7f2710dcf85758` | Frozen |
| `configs/data_focus.yaml` | `83de4997d41c0e13bac504e00d55e53782471493be3093b03064093c8a5c814c` | Frozen |
| `configs/detect_focus.yaml` | `908afbff06e7b7f34f26d78b64d0aa12bbeda815f454962216cc3ea889e516c4` | Frozen |
| `configs/detect_v2.yaml` | `458f83cb4745d11add466f04bbb73a0194a6ecf7fb5de2eb42b73f0448750cbe` | Frozen |
| `configs/explain_focus.yaml` | `2ea422840f82d2c7dd03e94b2f5140c0981d3407bffa8730329838dd996fa400` | Frozen |
| `configs/features_focus.yaml` | `0b81fb782ba4e134ba476e65c3817cbb48546f6a9bf6e69363d6212ac2ef078b` | Frozen |
| `configs/forecast_focus.yaml` | `4bbaa59ce0eb76e2f2f2269d58bc16f7552b1b05fa13a3a154de74bd159b288f` | Frozen |
| `configs/forecast_v2.yaml` | `392d3f1f53e088879689c5beb4619377fe9ce82192208e6a513f47767f9da342` | Frozen |
| `configs/ingest_aws.yaml` | `1564d6a1de88fb462c0b04bdaae2ca487788b14d5c55a9856dabeec0161332b1` | Frozen |
| `configs/ingest_azure.yaml` | `30577751c98d5a9ffa4788dff55eb4ba90f093de7b3d01066a02e99e10d9e280` | Frozen |
| `configs/ingest_focus.yaml` | `da10f64a38f45a740495bdadbb6360f5e2f4dc7c1589ce20c88a9169b60486b5` | Frozen |
| `configs/ingest_gcp.yaml` | `1fd9e30964fc9fbacfaffe8971337b7b6a9596e4b212f1f383a355a6ce31bda6` | Frozen |
| `configs/synth_dev.yaml` | `47dfda7e769bae5ef124c4367d529b436bafbd98dafad3f7b690588ebb595876` | Frozen |
| `configs/synth_holdout.yaml` | `cf35d117146cf7ec1db61c8a49da66a3039dcb3baeec608a5eefa182f08930a8` | Frozen |

---

## 3. Required Pre-Registered Evaluation Tables

The evaluation produces five separate tables to eliminate confounding between synthetic and real-world billing data:

### Table 1: Real Billing Holdout Evaluation (Forecast & Anomaly Detection)
Evaluated on un-injected, clean multi-cloud telemetry over chronological Days 23–30:
- **Forecast Models:** Seasonal Naive, Moving Average, Exponential Smoothing, Champion XGBoost, LightGBM.
- **Forecast Metrics:** WAPE (%), MASE, RMSE ($), $R^2$ with 95% bootstrap CIs.
- **Anomaly Detection:** Clean False Positive Rate (FPR) at nominal $\alpha = 0.05$ threshold.

### Table 2: External Benchmark Suite (TSB-UAD & RCAEval)
Evaluated on disjoint external benchmarks:
- **TSB-UAD (Sets 13–18):** Point-Adjusted F1, Area Under the Precision-Recall Curve (AUPRC).
- **RCAEval (Train Ticket Microservices, Cases 501–735):** Top-1 Accuracy, Top-3 Accuracy, Mean Reciprocal Rank (MRR).

### Table 3: Synthetic Attribution & Selective Abstention (S7 Holdout Suite)
Evaluated across holdout seeds `[707, 808, 909, 1010, 1111]`:
- **Attribution Baselines:** Random baseline, Class-prior baseline, Temporal correlation, Champion Multi-Layer Attributor.
- **Metrics:** Top-1 Accuracy, Mean Reciprocal Rank (MRR), Mean Time to Attributed Incident (MTTA).
- **Selective Abstention:** Abstention Rate (%), Retained Accuracy (%), Risk-Coverage Curve.

### Table 4: Cross-Dataset & Cross-Cloud Generalization
Zero-shot transfer across distinct cloud provider schemas without retraining:
- AWS CUR 2.0 $\rightarrow$ FOCUS Canonical $\rightarrow$ DriftSense v2
- Azure Cost Details $\rightarrow$ FOCUS Canonical $\rightarrow$ DriftSense v2
- GCP Cloud Billing $\rightarrow$ FOCUS Canonical $\rightarrow$ DriftSense v2

### Table 5: v1 vs v2 Benchmark Comparison
Direct architectural head-to-head. All v1 figures are explicitly labeled as **"development-contaminated"** per DEC-016:
- Forecast WAPE reduction (pp)
- Clean FPR reduction (ratio)
- Attribution Top-1 Accuracy improvement
- Conformal Coverage Gap ($|1 - \alpha - \text{Coverage}|$)

---

## 4. Verification & Audit Trail

The final evaluation manifest must be stored at `runs/run_phase15_holdout/manifest.json` and include:
- Git commit hash at start of execution
- Python and dependency version fingerprint
- Hardware processor and RAM details
- Frozen configuration file digests
- Final artifact SHA-256 hashes
- Marker: `"holdout_touched": true`
