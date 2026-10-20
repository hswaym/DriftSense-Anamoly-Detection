# DriftSense Final Evaluation Protocol (Locked Test Horizon)

**Status**: **FROZEN & LOCKED BEFORE EXECUTION**  
**Version**: 1.0.0  
**Phase**: PHASE 13 (Final Evaluation under Locked Protocol)  
**Standard**: FinOps FOCUS 1.0 / 1.3 Specification  
**Target Variable**: `EffectiveCost`  
**Temporal Partition**: Unseen Chronological Test Partition ($D_{\text{test}}$, Days 25–30, 2024-09-25 00:00:00 to 2024-09-30 23:00:00 UTC)  
**Execution Guarantee**: The test partition is evaluated **strictly once**. Zero re-tuning, parameter search, or threshold calibration is permitted after viewing test partition results.

---

## 1. Objective & Non-Claims

The objective of Phase 13 is to benchmark the generalization capabilities of the frozen DriftSense pipeline on completely unseen future data ($D_{\text{test}}$, Days 25–30).

### Invariants & Non-Claims:
1. **Unseen Horizon**: All feature normalizers, lag structures, forecast models, anomaly thresholds, and attribution engines were fit exclusively on training data ($D_{\text{train}}$, Days 1–15) and tuned on validation data ($D_{\text{val}}$, Days 16–24).
2. **Correlation $\neq$ Causation**: Attributions represent ranked probabilistic model evidence derived from timestamp alignment and gradient importance, not mathematical causal proof.
3. **Synthetic Ground Truth Disclaimers**: Synthetic incidents on $D_{\text{test}}$ represent controlled fault injection for repeatable benchmarking and do not claim to mirror real-world production incident distributions.
4. **No Re-tuning Policy**: All results on $D_{\text{test}}$—including potential performance regressions or negative results—are reported as-is without post-hoc modifications.

---

## 2. Cryptographic Configuration Hash Registry

Execution of Phase 13 requires cryptographic verification of all pipeline configurations against these frozen SHA-256 hashes:

| Configuration File | Frozen SHA-256 Digest |
|---|---|
| `configs/data_focus.yaml` | `83de4997d41c0e13bac504e00d55e53782471493be3093b03064093c8a5c814c` |
| `configs/clean_focus.yaml` | `bb455365af3555f9ceea952bb9a81e538ff8f822e47ea55c8e7f2710dcf85758` |
| `configs/features_focus.yaml` | `0b81fb782ba4e134ba476e65c3817cbb48546f6a9bf6e69363d6212ac2ef078b` |
| `configs/forecast_focus.yaml` | `4bbaa59ce0eb76e2f2f2269d58bc16f7552b1b05fa13a3a154de74bd159b288f` |
| `configs/detect_focus.yaml` | `908afbff06e7b7f34f26d78b64d0aa12bbeda815f454962216cc3ea889e516c4` |
| `configs/attribute_focus.yaml` | `997e05c2f96bbfd4aa75eb709355f94168d0865f88da61974a8c4b47878a1ec9` |
| `configs/explain_focus.yaml` | `2ea422840f82d2c7dd03e94b2f5140c0981d3407bffa8730329838dd996fa400` |
| `configs/ablation_focus.yaml` | `b54e694879f707f128fb3f27bea99be261ae76ce140a201ddde14d29eff9bb61` |

Any deviation in file hash triggers immediate abort via `A13.1 HashGuardError`.

---

## 3. Frozen Champion Models and Threshold Specifications

The models evaluated on $D_{\text{test}}$ are frozen from Phases 6–10:

### 3.1 Expected Cost Forecaster
- **Champion Architecture**: XGBoost Regressor (`XGBoostForecaster`)
- **Hyperparameters**: `n_estimators=100`, `max_depth=5`, `learning_rate=0.05`, `subsample=0.8`, `colsample_bytree=0.8`
- **Target Handling**: `log1p(EffectiveCost)` with inverse exponential reconstruction
- **Feature Set**: 48 features (Cost lags 1, 2, 3, 24, 168h; rolling statistics 3, 6, 24, 168h; ConsumedQuantity lags & rolling; calendar trigonometric encodings)
- **Primary Metric**: Weighted Absolute Percentage Error (WAPE) and MASE ($m=24$)

### 3.2 Anomaly Detector
- **Champion Architecture**: Rolling Adaptive Threshold Detector (`RollingThresholdDetector`)
- **Hyperparameters**: `window_size=24h`, `multiplier=3.0`, `min_periods=12`, dynamic quantile clipping
- **Dual-Track Evaluation**:
  - **Real Track ($D_{\text{test}}$ Clean)**: Evaluates False Positive Rate (FPR), Diurnal FPR (Peak vs Off-Peak), and Day-of-Week FPR. Target: Overall $\text{FPR} \le 1.0\%$.
  - **Synthetic Track ($D_{\text{test}}$ Injected)**: Evaluates Event-F1, Event-Precision, Event-Recall, Point-F1, and Mean Detection Delay (hours) under calibrated incident injection.

### 3.3 Root-Cause Attributor
- **Champion Architecture**: Temporal Correlation Attributor (`TemporalCorrelationAttributor`)
- **Hyperparameters**: Decay half-life $\lambda = 2.0\text{h}$, candidate search window $\pm 6\text{h}$
- **Evaluation Benchmark**: Top-1 Accuracy, Top-2 Accuracy, and Top-3 Accuracy against injected operational ground-truth incidents.

### 3.4 Model Explainability
- **Engine**: TreeSHAP Explainer (`TreeSHAPExplainer`)
- **Additivity Tolerance**: $\le 2.0 \times 10^{-3}$ ($|f(x) - \mathbb{E}[f(x)] - \sum \phi_i|$)
- **Audit Deliverable**: Top-5 Global Driver importance ranking and natural language audit narratives adhering strictly to non-causal phrasing.

---

## 4. One-Time Execution Invariant

To preserve scientific validity:
- The evaluation runner checks for existing test manifests. If `test_evaluated: true` is present, further execution is blocked unless an explicit override flag is supplied.
- All evaluation metrics, confusion matrices, and narratives are recorded directly to `runs/<run_id>/final_test_results.json` and cryptographically signed in `manifest.json`.
