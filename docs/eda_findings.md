# DriftSense — Exploratory Data Analysis (EDA) & Data Quality Report

**Run Identifier:** `run_20261019_144959_bac304`  
**Execution Platform:** Google Colab (Linux x86_64, Python 3.13.16, 12.67 GB RAM)  
**Evaluated Dataset:** FOCUS 1.0 Sample Data (10,000 raw billing line items)  
**Temporal Coverage:** `2024-09-01 00:00:00 UTC` to `2024-09-30 23:00:00 UTC` (Full 30-Day September 2024 billing cycle)

> **MANDATORY LEAKAGE DISCLAIMER (G6 Rule):**  
> All statistics, distributions, and patterns documented in this report are computed over the full dataset strictly for descriptive and visual characterization.  
> **No statistics, scalers, normalizers, or parameters from this EDA are permitted to be leaked or reused as feature transformations in subsequent model training or evaluation phases.**

---

### 1. Data Cleaning & Sanitization Audit

Based on the verified audit log [`runs/run_20261019_144959_bac304/cleaning_log.json`](file:///runs/run_20261019_144959_bac304/cleaning_log.json), the cleaning pipeline executed with zero dropped rows and 390 sanitized values:

| Cleaning Metric / Rule | Value | Assessment |
| :--- | :--- | :--- |
| **Initial Records** | 10,000 | Raw FOCUS 1.0 sample dataset |
| **Final Records** | 10,000 | 100% record retention (no data loss) |
| **Exact Duplicates Dropped** | 0 | No identical row collisions found |
| **Missing Services Dropped** | 0 | All records had valid `ServiceName` strings |
| **Missing Timestamps Dropped** | 0 | All records had valid ISO-8601 timestamps |
| **Invalid Timestamps Dropped** | 0 | Zero unparseable date strings |
| **ConsumedQuantity Imputed** | 36 | 36 nulls imputed to `0.0` (fixed-rate / subscription services) |
| **Negative EffectiveCost Handled** | 161 | 161 credit/refund lines segregated into `EffectiveCreditAmount` |
| **Negative BilledCost Handled** | 193 | 193 credit/refund lines segregated into `BilledCreditAmount` |
| **Unit Normalization Changes** | 0 | Units conformed to trimmed string formatting |
| **Total Rows Modified** | 390 | 3.90% of rows required sanitization / credit segregation |

---

### 2. High-Level Dataset & Spend Characteristics

Derived from [`runs/run_20261019_144959_bac304/eda_summary_statistics.json`](file:///runs/run_20261019_144959_bac304/eda_summary_statistics.json):

- **Canonical Grain:** `ServiceName × ChargePeriodStart` at hourly resolution (`1h`).
- **Total Canonical Intervals:** 26,396 service-hour series points.
- **Distinct Cloud Services:** 63 active cloud services across AWS and Azure providers.
- **Gross Invoiced Spend (`BilledCost`):** $281.24 USD.
- **Net Effective Spend (`EffectiveCost`):** $232.83 USD.
- **Segregated Credit Deductions:** $131.47 USD (amortized credits, EDP discounts, and refund vouchers).
- **Zero-Cost Interval Frequency:** **99.38%** across the entire panel.

---

### 3. Service Concentration & Pareto Breakdown

Cloud spending exhibits extreme concentration: the top 3 services represent **85.6%** ($199.26) of total infrastructure expenditure.

| Cloud Service | Total Net Spend ($) | % Total Spend | Hourly Mean ($) | Hourly Max ($) | Zero-Cost % | Skewness |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Amazon Elastic Compute Cloud (EC2)** | $147.00 | 63.13% | $0.2042 | $6.0000 | 88.9% | 3.98 |
| **Azure SQL Database** | $27.47 | 11.80% | $0.0950 | $17.5354 | 98.3% | 13.83 |
| **Virtual Machines (Azure)** | $24.79 | 10.65% | $0.0572 | $5.9000 | 97.2% | 9.81 |
| **Virtual Machine Scale Sets** | $8.95 | 3.84% | $0.0219 | $3.4861 | 98.5% | 12.06 |
| **COMPUTE (Generic)** | $8.00 | 3.44% | $0.0123 | $2.0000 | 99.4% | 12.62 |
| **Amazon RDS** | $4.00 | 1.72% | $0.0056 | $1.0000 | 99.4% | 13.30 |
| **Azure Kubernetes Service (AKS)** | $2.71 | 1.16% | $0.0094 | $2.7101 | 99.7% | 16.91 |
| **Amazon EKS** | $2.00 | 0.86% | $0.0033 | $1.0000 | 99.7% | 17.41 |
| **Remaining 55 Services Combined** | $7.91 | 3.40% | < $0.002 | — | > 99.5% | > 20.0 |

---

### 4. Empirical Visualizations & Behavioral Patterns

#### A. Total Cost Over Time (`eda_01_total_cost_over_time.png`)
- Total spend exhibits pronounced multi-day plateau baselines interrupted by discrete, sharp spending surges.
- Maximum total hourly spend peaked at over $20/hour during mid-month spikes, before returning to a steady-state floor of ~$0.20–$0.50/hour.

#### B. Per-Service Spending Breakdown (`eda_02_service_cost_breakdown.png`)
- Amazon EC2 provides a continuous low-level baseline with periodic step-ups.
- Azure SQL Database exhibits a single high-magnitude isolated impulse spike ($17.54) on 2024-09-18, serving as a classic example of an isolated cost anomaly candidate.

#### C. Cost Distributions & Heavy Tails (`eda_03_cost_distribution.png`)
- Non-zero costs follow an extreme power-law distribution spanning 4 orders of magnitude ($0.0001 to $17.54).
- The log10-transformed distribution displays a bimodal structure: micro-transactions (< $0.01) from networking/storage, and substantive instance-hour costs ($0.10–$5.00).

#### D. Usage vs. Cost Relationships (`eda_04_usage_vs_cost.png`)
- For compute services (EC2, Virtual Machines), `ConsumedQuantity` correlates strongly with cost along discrete linear pricing slopes corresponding to specific instance types (`m5.large`, `t3.medium`).
- Database and storage services demonstrate step-function pricing regimes where storage capacity tier minimums decouple quantity from billed cost.

#### E. Diurnal and Weekly Seasonality (`eda_05_seasonality.png`)
- **Diurnal (Hour-of-Day):** Spend exhibits a diurnal curve peaking between 12:00 UTC and 18:00 UTC (corresponding to peak business hours across US and European operating zones).
- **Day-of-Week:** Weekday spend (Monday–Friday) is significantly higher than weekend spend (Saturday–Sunday), reflecting enterprise batch and operational schedules.

#### F. Zero and Near-Zero Cost Frequency (`eda_06_zero_cost_frequency.png`)
- 55 out of 63 services (87.3%) have zero-cost frequency exceeding 99.0%.
- **Critical Evaluation Implication:** Standard Mean Absolute Percentage Error ($\text{MAPE} = \frac{|Y - \hat{Y}|}{Y}$) is mathematically ill-posed due to near-zero actuals causing division-by-zero explosions.
- **Contract Ratification:** In accordance with Contract 10 and Contract 11, **sMAPE** (Symmetric MAPE) and **WAPE** (Weighted Absolute Percentage Error) are strictly validated as the required primary forecasting error metrics.

#### G. Cross-Service Correlation Matrix (`eda_07_correlation_matrix.png`)
- Compute services (EC2 and Virtual Machines) display weak-to-moderate positive co-movement ($r \approx 0.35$), suggesting shared diurnal demand.
- Database and networking spikes are decoupled from compute baseline variations, indicating independent scaling events.

#### H. Operational Event Track Readiness (`eda_08_event_track_readiness.png`)
- Establishes the temporal boundary for rolling-origin splits:
  - Baseline stable historical reference window: Days 1–18 (60%).
  - Validation & calibration window: Days 19–24 (20%).
  - Locked test / evaluation window: Days 25–30 (20%).
- Demonstrates readiness for controlled synthetic fault injection (deployment spikes, rogue runaway queries, and decoy events) over the calibrated baseline.

---

### 5. Architectural Implications for Modeling (Phase 5–7)

1. **Panel Aggregation Grain:** Hourly canonical grain (`ServiceName × 1h`) captures the sharp impulse spikes (such as the Azure SQL surge) that daily aggregation would smooth out by 24×.
2. **Metric Selection:** WAPE and sMAPE are mandatory; raw MAPE must be gated with a strictly positive epsilon floor ($\epsilon = 0.01$).
3. **Credit Isolation:** Credit memos ($131.47) must remain strictly segregated in `EffectiveCreditAmount` to prevent negative residual distortions in XGBoost and time-series forecasters.
4. **Primary Modeling Focus:** Multi-series panel forecaster should focus on the top 10 dominant cost drivers (accounting for 96.6% of spend), while low-spend intermittent tails can be aggregated into a composite `Other_Services` residual bucket.
