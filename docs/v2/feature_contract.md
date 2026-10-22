# DriftSense v2 — Feature Contract & Anti-Leakage Specification

**Status:** APPROVED (Phase 5 Binding Contract)  
**Version:** 2.0.0  
**Audit Protocol Compliance:** Rule C6 (Anti-Leakage Protocol), Phase 5 Acceptance Criteria A5.1 & A5.2  
**Governing Hypotheses:** Audit H1 (Eliminate contemporaneous cost leakage) & Audit H2 (Explicit Mode A vs Mode B forecasting semantics)

---

## 1. Principles & Anti-Leakage Invariants

DriftSense v2 enforces a strict mathematical and operational boundary between historical observations, contemporaneous operational telemetry, and target variables:

1. **Rule C6 Target Isolation Invariant:**
   Under no circumstances may a contemporaneous cost column (`BilledCost`, `ListCost`, `ContractedCost`, or unadjusted raw equivalents) at timestamp $t$ be admitted into the feature set for predicting `EffectiveCost` at timestamp $t$. Any model predicting cost from contemporaneous cost suffers from near-duplicate target leakage.
2. **Forecasting Paradigm Segregation:**
   - **Mode A (History-Expected):** Predicts expected spend purely given historical series trajectory ($\le t-1$), calendar schedule, and known operational events ($ts_{\text{start}} \le t$). Contemporaneous resource usage is **strictly excluded**. Alerts flag **usage-driven spikes and volume anomalies**.
   - **Mode B (Usage-Expected):** Conditions the cost expectation on contemporaneous resource usage (`ConsumedQuantity` at timestamp $t$). Alerts flag **rate, pricing, commitment-expiration, and unit efficiency anomalies**.
3. **Strictly Left-Closed Windows:**
   All autoregressive lags reference $t - k$ ($k \ge 1$). All rolling statistics apply a `shift(1)` before window aggregation, guaranteeing that observations at timestamp $t$ do not influence rolling statistics for row $t$.
4. **Causal Event Timing:**
   Operational events are evaluated strictly on $ts_{\text{start}} \le t$. Future events ($ts_{\text{start}} > t$) exert 0.0 influence on feature vectors at $t$.
5. **Label Isolation:**
   Ground truth anomaly manifests (`is_anomaly`, `incident_id`, `fault_family`, `true_cause`, `severity_score`, etc.) are segregated into external sidecar JSON files and raise immediate `ValueError` if introduced into the feature pipeline.

---

## 2. Complete Feature Inventory (100% Coverage)

| Feature Name | Formula | Lookback Window | Includes Current Row? | Known at Prediction Time? | Source Column | Mode | Data Type / Bounds | Description |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `billing_cycle_day` | `((day - start) % days_in_month) + 1` | Current row | Yes | Yes | `ChargePeriodStart` | Both | Integer $[1, 31]$ | Day index within billing cycle |
| `day_of_month` | `dt.day` | Current row | Yes | Yes | `ChargePeriodStart` | Both | Integer $[1, 31]$ | Gregorian day of month |
| `day_of_week` | `dt.dayofweek` | Current row | Yes | Yes | `ChargePeriodStart` | Both | Integer $[0, 6]$ | Day of week ($0=\text{Monday}, 6=\text{Sunday}$) |
| `days_until_month_end` | `days_in_month - dt.day` | Current row | Yes | Yes | `ChargePeriodStart` | Both | Integer $[0, 30]$ | Days remaining until month-end boundary |
| `hour_of_day` | `dt.hour` | Current row | Yes | Yes | `ChargePeriodStart` | Both | Integer $[0, 23]$ | UTC hour of day |
| `is_month_end` | `1 if dt.day == days_in_month else 0` | Current row | Yes | Yes | `ChargePeriodStart` | Both | Binary $\{0, 1\}$ | Indicator of final day of billing month |
| `is_weekend` | `1 if dt.dayofweek >= 5 else 0` | Current row | Yes | Yes | `ChargePeriodStart` | Both | Binary $\{0, 1\}$ | Weekend binary indicator |
| `sin_hour` | $\sin(2\pi \cdot \text{hour} / 24)$ | Current row | Yes | Yes | `ChargePeriodStart` | Both | Float $[-1.0, 1.0]$ | Trigonometric continuous diurnal cycle |
| `cos_hour` | $\cos(2\pi \cdot \text{hour} / 24)$ | Current row | Yes | Yes | `ChargePeriodStart` | Both | Float $[-1.0, 1.0]$ | Trigonometric continuous diurnal cycle |
| `sin_dow` | $\sin(2\pi \cdot \text{dow} / 7)$ | Current row | Yes | Yes | `ChargePeriodStart` | Both | Float $[-1.0, 1.0]$ | Trigonometric continuous weekly cycle |
| `cos_dow` | $\cos(2\pi \cdot \text{dow} / 7)$ | Current row | Yes | Yes | `ChargePeriodStart` | Both | Float $[-1.0, 1.0]$ | Trigonometric continuous weekly cycle |
| `EffectiveCost_lag_1` | $\text{Cost}(t - 1)$ | $1\text{h}$ | No | Yes | `EffectiveCost` | Both | Float $[0, \infty)$ | 1-step historical spend lag |
| `EffectiveCost_lag_2` | $\text{Cost}(t - 2)$ | $2\text{h}$ | No | Yes | `EffectiveCost` | Both | Float $[0, \infty)$ | 2-step historical spend lag |
| `EffectiveCost_lag_3` | $\text{Cost}(t - 3)$ | $3\text{h}$ | No | Yes | `EffectiveCost` | Both | Float $[0, \infty)$ | 3-step historical spend lag |
| `EffectiveCost_lag_24` | $\text{Cost}(t - 24)$ | $24\text{h}$ | No | Yes | `EffectiveCost` | Both | Float $[0, \infty)$ | 24-step (diurnal) historical spend lag |
| `EffectiveCost_lag_168` | $\text{Cost}(t - 168)$ | $168\text{h}$ | No | Yes | `EffectiveCost` | Both | Float $[0, \infty)$ | 168-step (weekly) historical spend lag |
| `EffectiveCost_roll_mean_3h` | $\text{mean}(\text{Cost}[t-3, t-1])$ | $3\text{h}$ | No | Yes | `EffectiveCost` | Both | Float $[0, \infty)$ | 3-hour shifted rolling average spend |
| `EffectiveCost_roll_std_3h` | $\text{std}(\text{Cost}[t-3, t-1])$ | $3\text{h}$ | No | Yes | `EffectiveCost` | Both | Float $[0, \infty)$ | 3-hour shifted rolling volatility |
| `EffectiveCost_roll_max_3h` | $\max(\text{Cost}[t-3, t-1])$ | $3\text{h}$ | No | Yes | `EffectiveCost` | Both | Float $[0, \infty)$ | 3-hour shifted rolling peak spend |
| `EffectiveCost_roll_mean_6h` | $\text{mean}(\text{Cost}[t-6, t-1])$ | $6\text{h}$ | No | Yes | `EffectiveCost` | Both | Float $[0, \infty)$ | 6-hour shifted rolling average spend |
| `EffectiveCost_roll_std_6h` | $\text{std}(\text{Cost}[t-6, t-1])$ | $6\text{h}$ | No | Yes | `EffectiveCost` | Both | Float $[0, \infty)$ | 6-hour shifted rolling volatility |
| `EffectiveCost_roll_max_6h` | $\max(\text{Cost}[t-6, t-1])$ | $6\text{h}$ | No | Yes | `EffectiveCost` | Both | Float $[0, \infty)$ | 6-hour shifted rolling peak spend |
| `EffectiveCost_roll_mean_24h` | $\text{mean}(\text{Cost}[t-24, t-1])$ | $24\text{h}$ | No | Yes | `EffectiveCost` | Both | Float $[0, \infty)$ | 24-hour shifted rolling average spend |
| `EffectiveCost_roll_std_24h` | $\text{std}(\text{Cost}[t-24, t-1])$ | $24\text{h}$ | No | Yes | `EffectiveCost` | Both | Float $[0, \infty)$ | 24-hour shifted rolling volatility |
| `EffectiveCost_roll_max_24h` | $\max(\text{Cost}[t-24, t-1])$ | $24\text{h}$ | No | Yes | `EffectiveCost` | Both | Float $[0, \infty)$ | 24-hour shifted rolling peak spend |
| `EffectiveCost_roll_mean_168h` | $\text{mean}(\text{Cost}[t-168, t-1])$ | $168\text{h}$ | No | Yes | `EffectiveCost` | Both | Float $[0, \infty)$ | 168-hour shifted rolling average spend |
| `EffectiveCost_roll_std_168h` | $\text{std}(\text{Cost}[t-168, t-1])$ | $168\text{h}$ | No | Yes | `EffectiveCost` | Both | Float $[0, \infty)$ | 168-hour shifted rolling volatility |
| `EffectiveCost_roll_max_168h` | $\max(\text{Cost}[t-168, t-1])$ | $168\text{h}$ | No | Yes | `EffectiveCost` | Both | Float $[0, \infty)$ | 168-hour shifted rolling peak spend |
| `EffectiveCost_diff_1h` | $\text{Cost}(t-1) - \text{Cost}(t-2)$ | $2\text{h}$ | No | Yes | `EffectiveCost` | Both | Float $(-\infty, \infty)$ | 1-hour historical cost delta velocity |
| `EffectiveCost_diff_24h` | $\text{Cost}(t-1) - \text{Cost}(t-24)$ | $24\text{h}$ | No | Yes | `EffectiveCost` | Both | Float $(-\infty, \infty)$ | 24-hour historical seasonal delta |
| `is_zero_spend_lag1` | $1 \text{ if } \text{Cost}(t-1) \le 10^{-6} \text{ else } 0$ | $1\text{h}$ | No | Yes | `EffectiveCost` | Both | Binary $\{0, 1\}$ | Zero-spend sparsity indicator at $t-1$ |
| `zero_spend_streak_hours` | Consecutive zero-spend steps up to $t-1$ | Variable | No | Yes | `EffectiveCost` | Both | Float $[0, \infty)$ | Duration of idle streak prior to step $t$ |
| `total_spend_lag1` | $\sum_{s} \text{Cost}_{s}(t-1)$ | $1\text{h}$ | No | Yes | `EffectiveCost` | Both | Float $[0, \infty)$ | Account-wide total spend at $t-1$ |
| `service_spend_share_lag1` | $\text{Cost}_{svc}(t-1) / (\text{total\_spend\_lag1} + \epsilon)$ | $1\text{h}$ | No | Yes | `EffectiveCost` | Both | Float $[0.0, 1.0]$ | Proportion of account spend by service |
| `ConsumedQuantity_lag_1` | $\text{Usage}(t-1)$ | $1\text{h}$ | No | Yes | `ConsumedQuantity` | Both | Float $[0, \infty)$ | Historical usage volume at $t-1$ |
| `ConsumedQuantity_lag_2` | $\text{Usage}(t-2)$ | $2\text{h}$ | No | Yes | `ConsumedQuantity` | Both | Float $[0, \infty)$ | Historical usage volume at $t-2$ |
| `ConsumedQuantity_lag_24` | $\text{Usage}(t-24)$ | $24\text{h}$ | No | Yes | `ConsumedQuantity` | Both | Float $[0, \infty)$ | Diurnal historical usage volume |
| `ConsumedQuantity_diff_1h` | $\text{Usage}(t-1) - \text{Usage}(t-2)$ | $2\text{h}$ | No | Yes | `ConsumedQuantity` | Both | Float $(-\infty, \infty)$ | 1-hour usage volume delta |
| `ConsumedQuantity_diff_24h` | $\text{Usage}(t-1) - \text{Usage}(t-24)$ | $24\text{h}$ | No | Yes | `ConsumedQuantity` | Both | Float $(-\infty, \infty)$ | 24-hour seasonal usage volume delta |
| `ConsumedQuantity_growth_pct_1h` | $(\text{Usage}(t-1) - \text{Usage}(t-2)) / (|\text{Usage}(t-2)| + \epsilon)$ | $2\text{h}$ | No | Yes | `ConsumedQuantity` | Both | Float $(-\infty, \infty)$ | 1-hour percentage change in usage |
| `ConsumedQuantity_growth_pct_24h` | $(\text{Usage}(t-1) - \text{Usage}(t-24)) / (|\text{Usage}(t-24)| + \epsilon)$ | $24\text{h}$ | No | Yes | `ConsumedQuantity` | Both | Float $(-\infty, \infty)$ | 24-hour percentage change in usage |
| `ConsumedQuantity_roll_mean_6h` | $\text{mean}(\text{Usage}[t-6, t-1])$ | $6\text{h}$ | No | Yes | `ConsumedQuantity` | Both | Float $[0, \infty)$ | 6-hour shifted rolling average usage |
| `ConsumedQuantity_roll_std_6h` | $\text{std}(\text{Usage}[t-6, t-1])$ | $6\text{h}$ | No | Yes | `ConsumedQuantity` | Both | Float $[0, \infty)$ | 6-hour shifted rolling usage volatility |
| `ConsumedQuantity_roll_mean_24h` | $\text{mean}(\text{Usage}[t-24, t-1])$ | $24\text{h}$ | No | Yes | `ConsumedQuantity` | Both | Float $[0, \infty)$ | 24-hour shifted rolling average usage |
| `ConsumedQuantity_roll_std_24h` | $\text{std}(\text{Usage}[t-24, t-1])$ | $24\text{h}$ | No | Yes | `ConsumedQuantity` | Both | Float $[0, \infty)$ | 24-hour shifted rolling usage volatility |
| `ConsumedQuantity_contemporaneous` | $\text{Usage}(t)$ | Current row | Yes | Yes (Mode B only) | `ConsumedQuantity` | Mode B | Float $[0, \infty)$ | Contemporaneous resource usage at $t$ |
| `event_active_deployment` | $1 \text{ if deployment active at } t \text{ else } 0$ | Current row | Yes | Yes | `operational_events` | Both | Binary $\{0, 1\}$ | Deployment event active at timestamp $t$ |
| `event_active_scaling` | $1 \text{ if scaling active at } t \text{ else } 0$ | Current row | Yes | Yes | `operational_events` | Both | Binary $\{0, 1\}$ | Autoscaling event active at timestamp $t$ |
| `event_active_config_change` | $1 \text{ if config change active at } t \text{ else } 0$ | Current row | Yes | Yes | `operational_events` | Both | Binary $\{0, 1\}$ | Configuration event active at timestamp $t$ |
| `event_active_traffic` | $1 \text{ if traffic shift active at } t \text{ else } 0$ | Current row | Yes | Yes | `operational_events` | Both | Binary $\{0, 1\}$ | Traffic shift event active at timestamp $t$ |
| `event_active_batch` | $1 \text{ if batch run active at } t \text{ else } 0$ | Current row | Yes | Yes | `operational_events` | Both | Binary $\{0, 1\}$ | Batch workload active at timestamp $t$ |
| `hours_since_last_event` | $t - \max(ts_{\text{start}} \le t)$ | Variable | Yes | Yes | `operational_events` | Both | Float $[0, 720.0]$ | Elapsed hours since most recent event |
| `recent_event_count_24h` | $\sum 1 \text{ for } ts_{\text{start}} \in [t-24\text{h}, t]$ | $24\text{h}$ | Yes | Yes | `operational_events` | Both | Integer $[0, \infty)$ | Count of event starts in trailing 24 hours |

---

## 3. Forbidden Column Specification

The following columns are **strictly forbidden** from the feature matrix `self.feature_names_`:

1. **Contemporaneous Cost Columns:**
   - `EffectiveCost` (Prediction target)
   - `BilledCost` (Contemporaneous invoice duplicate; leaks 48% SHAP in v1)
   - `ListCost`, `ContractedCost` (Contemporaneous pricing duplicates)
   - `EffectiveCostRaw`, `BilledCostRaw`, `ListCostRaw`, `ContractedCostRaw`
2. **Ground Truth Anomaly Labels:**
   - `is_anomaly`, `incident_id`, `fault_family`, `true_cause`, `is_synthetic`, `is_decoy`
   - `label_id`, `primary_cause`, `contributing_causes`, `severity_score`, `onset_timestamp`, `offset_timestamp`, `verification_src`
3. **Contemporaneous Usage in Mode A:**
   - `ConsumedQuantity` (Contemporaneous raw usage is forbidden in Mode A)

---

## 4. Hierarchy and Grain Aggregation

1. **Supported Grains:**
   - `"1h"`: Standard hourly interval (ChargePeriodStart timestamp preserved).
   - `"1d"`: Daily roll-up truncated to `dt.floor("D")` UTC, with cost and usage summed across 24 hourly periods.
2. **Reconciliation Hierarchy:**
   - Level 0: Account / Total spend (`total_spend_lag1`)
   - Level 1: SubAccount / Business Unit
   - Level 2: Service (`ServiceName`)
   - Level 3: Region (`RegionId`)
