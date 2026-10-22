# DriftSense v2 — Evaluation Protocol & Pre-Registration

**Protocol Version:** 2.0.0-LOCKED  
**Pre-Registration Date:** 2026-10-21  
**Status:** Pre-Registered (Binding)  

---

## 1. Partition Roles & Fresh Holdout Rule

To prevent the data contamination identified in v1 (where $D_{\text{test}}$ was spent in DEC-016), DriftSense v2 strictly partitions all research datasets into three disjoint splits:

```
[ Development Split (D_dev) ] [ Validation Split (D_val) ] [ Fresh Untouched Holdout (D_holdout) ]
           50%                             25%                                    25%
  Historical Fitting & EDA      Model Selection & Tuning           One-Time Phase 15 Evaluation Only
```

### 1.1 Fresh Holdout Rule (Mandatory Invariant)
* **$D_{\text{holdout}}$ is strictly quarantined:** It was NEVER evaluated in DriftSense v1 (Phases 0–14).
* It consists of **new chronological periods, fresh multi-cloud sources, and unobserved synthetic fault generator seeds**.
* **Zero-Touch Enforcement:** No code, model, or threshold may be fit, tuned, or inspected on $D_{\text{holdout}}$ prior to Phase 15. Every intermediate run manifest must verify:
  ```json
  "holdout_touched": false
  ```
* In Phase 15, $D_{\text{holdout}}$ is evaluated **strictly once**. Post-hoc parameter adjustments after observing holdout metrics are strictly forbidden.

---

## 2. Pre-Registered Hypotheses for v2

The v2 research program pre-registers four binding scientific hypotheses:

### Hypothesis H-A (Leakage Remediation & True Forecaster Baseline)
* **Hypothesis:** When contemporaneous `BilledCost` and unlagged `ConsumedQuantity` are removed from Mode A, the forecaster WAPE will increase relative to v1 (confirming that v1's 82% WAPE was deflated by contemporaneous leakage), but Mode A will significantly outperform Seasonal Naive persistence by $\ge 15\%$ on MASE ($\text{MASE} \le 0.85$).

### Hypothesis H-B (Decoupled Volume vs. Rate Anomaly Detection)
* **Hypothesis:** Mode A will achieve $\ge 90\%$ Event Recall on workload volume runaways (where Mode B's recall drops to $< 50\%$), whereas Mode B will achieve $\ge 90\%$ Event Recall on unit-rate price jumps (where Mode A's recall is slower or requires higher threshold bounds).

### Hypothesis H-C (Attribution Robustness under Decoys & Confounders)
* **Hypothesis:** When the candidate pool is populated with non-injected decoy events and confounders (ratio 3:1 decoys to faults), the temporal decay attribution engine combined with the abstention gate will maintain $\ge 80\%$ Top-1 accuracy while successfully abstaining on $\ge 90\%$ of pure-noise incidents.

### Hypothesis H-D (Conformal Uncertainty Calibration)
* **Hypothesis:** Split-conformal prediction intervals calibrated at nominal coverage $1 - \alpha = 0.90$ on $D_{\text{val}}$ will demonstrate empirical coverage between $88.0\%$ and $92.0\%$ on the unseen holdout partition, providing statistically valid sensitivity boundaries.

---

## 3. Evaluation Metrics & Statistical Testing Standards

### 3.1 Forecasting Metrics
* **Weighted Absolute Percentage Error (WAPE):**
  $$\text{WAPE} = \frac{\sum_{t} |Y_t - \hat{Y}_t|}{\sum_{t} Y_t}$$
* **Mean Absolute Scaled Error (MASE):** Relative to 24h seasonal naive benchmark.
* **Empirical Interval Coverage & Mean Interval Width (conformal evaluation).**

### 3.2 Anomaly Detection Metrics
* **Point-Level:** Precision, Recall, F1-Score, PR-AUC.
* **Event-Level:** Event Precision, Event Recall (requiring detection within duration window $[t_{\text{start}}, t_{\text{end}}]$), Detection Delay (hours from onset to first alert).
* **Alert Burden:** Alerts per 1,000 series-hours and alerts per $10,000 of spend on presumed-normal data.

### 3.3 Attribution Metrics
* **Top-1 Accuracy, Top-3 Accuracy, and Mean Reciprocal Rank (MRR).**
* **Abstention Accuracy:** Percentage of low-evidence or pure-noise cases correctly assigned to the "Not enough evidence" class.

### 3.4 Multi-Seed & Bootstrap Confidence Intervals
* All experiments must be evaluated across **$\ge 10$ distinct random seeds** (`[42, 101, 202, 303, 404, 505, 606, 707, 808, 909]`).
* All final metrics must be reported with **mean $\pm$ standard deviation** and **95% empirical bootstrap confidence intervals** (1,000 resamples).

---

## 4. Formal Protocol Stop Criteria
An evaluation run will be halted and marked **FAILED** if:
1. Any feature column in Mode A has timestamp $t \ge t_{\text{prediction}}$.
2. Any configuration file's SHA-256 hash differs from its frozen protocol digest.
3. The manifest records `"holdout_touched": true` prior to Phase 15.
4. An automated scan detects any forbidden causal phrasing in generated narratives.

---

## 5. Protocol Verification Digest
- **Document Canonical SHA-256:** `2b4ab6a1c36fd4d4f47a7ad5e513f64e4511e0ce64dd66b9c2d009b2482abdd0`
