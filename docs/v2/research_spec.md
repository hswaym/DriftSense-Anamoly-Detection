# DriftSense v2 — Research Specification & Scientific Methodology

## 1. Revised Problem Statement (Post-Audit v1 Learnings)

The Phase 0 forensic audit demonstrated that while DriftSense v1 established a disciplined chronological evaluation harness, it suffered from three foundational scientific vulnerabilities:
1. **Contemporaneous Target Leakage (H1):** `BilledCost` at timestamp $t$ was included as an unlagged feature, allowing the forecaster to memorize a near-identical cost column rather than truly anticipating future spend from historical dynamics.
2. **Narrow Counterfactual Conditioning (H2):** Conditioning the primary forecaster on contemporaneous usage (`ConsumedQuantity` at $t$) caused the model to predict high cost when usage surged, masking volume-driven runaways and flagging only unit-rate or pricing-tier anomalies.
3. **Attribution Candidate Circularity (H3 & H4):** The attribution engine was evaluated against a candidate pool consisting exclusively of large, abrupt step-injected faults without decoys, confounders, or gradual drift.

**DriftSense v2** addresses these flaws through a revised, mathematically sound research architecture.

---

## 2. Decoupled Forecasting Paradigms: Mode A vs. Mode B

To satisfy both operational engineering needs (catching volume runaways) and financial accounting needs (catching rate/pricing drift), DriftSense v2 introduces two formally decoupled forecasting modes:

```
[Raw Billing & Usage Telemetry]
                │
        ┌───────┴───────┐
        ▼               ▼
┌──────────────┐ ┌──────────────┐
│    MODE A    │ │    MODE B    │
│History-Expect│ │Usage-Expected│
└───────┬──────┘ └──────┬───────┘
        │               │
        ▼               ▼
[Flags Volume   [Flags Rate/
 & Workload      Efficiency
 Surges]         Anomalies]
```

### 2.1 Mode A: History-Expected Forecaster ($\hat{Y}_{s,t}^{(A)}$)
* **Question Answered:** *"Given historical spend, day-of-week, hour-of-day, and known planned commitments, what should this service cost at hour $t$?"*
* **Information Set ($\mathcal{F}_{t-1}^{(A)}$):**
  - Autoregressive cost lags: $Y_{s,t-1}, Y_{s,t-2}, Y_{s,t-24}, Y_{s,t-168}$.
  - Trailing rolling cost statistics over $[t-w, t-1]$.
  - Calendar cyclical encodings (hour sine/cosine, day-of-week sine/cosine, month-end).
  - Known scheduled commitments / reservation baselines.
  - **STRICT PROHIBITION:** Zero contemporaneous usage (`ConsumedQuantity` at $t$) and zero contemporaneous cost (`BilledCost` at $t$).
* **Operational Role:** Detects total spend spikes, runaway batch jobs, autoscaling loops, and sudden viral traffic surges.

### 2.2 Mode B: Usage-Expected Forecaster ($\hat{Y}_{s,t}^{(B)}$)
* **Question Answered:** *"Given the exact physical compute/storage volume consumed at hour $t$, what should this service cost at hour $t$?"*
* **Information Set ($\mathcal{F}_{t}^{(B)}$):**
  - All features from Mode A ($\mathcal{F}_{t-1}^{(A)}$).
  - Contemporaneous physical usage volume: $Q_{s,t}$ (`ConsumedQuantity` at hour $t$).
  - Historical unit rate lags: $R_{s,t-1} = Y_{s,t-1} / Q_{s,t-1}$.
  - **STRICT PROHIBITION:** Zero contemporaneous cost columns (`BilledCost` at $t$ remains strictly forbidden).
* **Operational Role:** Detects unit-rate inflation, accidental instance-tier upgrades, discount/credit expirations, and architectural memory leaks that inflate price per unit of useful work.

---

## 3. Mathematical Volume-Price-Mix Driver Decomposition

To explain cost gaps without relying solely on black-box heuristics, DriftSense v2 incorporates an exact, deterministic **Volume-Price-Mix (VPM) Decomposition**.

### 3.1 Mathematical Formulation
For any service $s$, let:
- $Q_0, Q_1$ denote baseline expected volume and actual observed volume.
- $R_0, R_1$ denote baseline expected effective unit rate and actual observed unit rate, where $R = \text{EffectiveCost} / \text{ConsumedQuantity}$.

The total cost deviation $\Delta C = Y_1 - Y_0 = Q_1 R_1 - Q_0 R_0$ is decomposed into exact, non-overlapping identities:
$$\Delta C = \underbrace{(Q_1 - Q_0) R_0}_{\text{Volume Effect}} + \underbrace{(R_1 - R_0) Q_0}_{\text{Price/Rate Effect}} + \underbrace{(Q_1 - Q_0)(R_1 - R_0)}_{\text{Interaction / Mix Effect}}$$

### 3.2 Exact Numerical Verification
The decomposition engine verifies that:
$$\left| \Delta C - (\text{Volume Effect} + \text{Price Effect} + \text{Mix Effect}) \right| < 10^{-6}$$
* If $\text{Volume Effect} \gg \text{Price Effect}$, the incident is driven by workload demand.
* If $\text{Price Effect} \gg \text{Volume Effect}$, the incident is driven by pricing tier or architectural inefficiency.

---

## 4. Model-Independent Anomaly Definition

In DriftSense v2, an anomaly is defined as a statistically significant, economically material excursion from an expected counterfactual baseline.

### 4.1 Statistical Residual Significance
Let $e_{s,t} = Y_{s,t} - \hat{Y}_{s,t}$ denote the counterfactual residual. Using split-conformal prediction bands calibrated on validation data at significance level $\alpha = 0.05$:
$$\text{IsSignificant}(t) \iff e_{s,t} \notin [-\hat{q}_{1-\alpha/2}, +\hat{q}_{1-\alpha/2}]$$

### 4.2 Economic Materiality Gate
To prevent operational alert fatigue on micro-services spending pennies, an alert is raised if and only if it clears both statistical significance and an **Economic Materiality Filter**:
$$\text{IsAnomaly}(t) = \text{IsSignificant}(t) \land \left( |e_{s,t}| \ge \Delta_{\min} \right) \land \left( \frac{|e_{s,t}|}{\hat{Y}_{s,t}} \ge \delta_{\min} \right)$$
where default parameters are:
- $\Delta_{\min} = \$5.00$ (minimum absolute dollar impact).
- $\delta_{\min} = 20\%$ (minimum relative percentage excursion).

---

## 5. Revised Operational Cause Taxonomy v2

DriftSense v2 expands beyond simple fault injection into a comprehensive, realistic taxonomy including decoys, unobserved causes, and planned events:

```
┌────────────────────────────────────────────────────────────────────────┐
│                      OPERATIONAL CAUSE TAXONOMY v2                     │
├────────────────────┬────────────────────┬──────────────────────────────┤
│ 1. Workload Faults │ 2. Config Faults   │ 3. Pricing & Contract Faults │
├────────────────────┼────────────────────┼──────────────────────────────┤
│ • RUNAWAY_BATCH    │ • CONFIG_MOD       │ • COMMITMENT_EXPIRATION      │
│ • AUTOSCALE_LOOP   │ • REGION_MIGRATE   │ • RATE_TIER_SHIFT            │
│ • DEPLOY_DEFECT    │ • UNTAGGED_GROWTH  │ • DISCOUNT_DROP              │
├────────────────────┴────────────────────┴──────────────────────────────┤
│ 4. Benign & Confounder Categories (Crucial for Evaluation Rigor)        │
├────────────────────────────────────────────────────────────────────────┤
│ • EXTERNAL_TRAFFIC_SURGE (Organic business peak — non-fault)           │
│ • DECOY_EVENT (Operational change with zero billing impact)            │
│ • UNKNOWN_CAUSE (Cost anomaly with no matching event — triggers abstain)│
│ • PLANNED_MAINTENANCE (Pre-announced change — suppressed)              │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 6. Scientific Metrics & Claim Support Ledger

Every reported metric in v2 must be explicitly bounded by the claim it supports:

| Scientific Track | Metric Reported | Claim Supported | Claim Forbidden |
| :--- | :--- | :--- | :--- |
| **Real Presumed-Normal** | Alert Rate per 1k hrs | Measure of alert volume during standard operations | Cannot claim "0% False Positive Rate" without human labels |
| **Calibrated Synthetic** | Event Recall & Precision | Detector sensitivity across diverse fault shapes | Cannot claim production outage mastery |
| **Confounder / Decoy** | Abstention Accuracy & Top-1 | Robustness against false attribution triggers | Cannot claim physical causation |
| **Conformal Bands** | Empirical Coverage vs Nominal | Calibrated uncertainty bounds | Cannot claim deterministic bounds |
