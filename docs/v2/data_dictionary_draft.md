# DriftSense v2 — Data Dictionary & Attribute Catalog (Draft)

**Document Version:** 2.0.0  
**Phase:** Phase 2 (Dataset Program — Verify and Select)  
**Status:** Approved Draft Catalog  
**Scope:** Canonical FOCUS billing fields, provider source columns (AWS, Azure, GCP), telemetry trace metrics (S3/S4), event attributes, and derived feature definitions.

---

## 1. Canonical FOCUS Billing Attributes (S1 & S4 Suite)

| Column Name | Physical Type | Logical Type | Nullable | Value Constraints | Provider Source Mapping | Feature Pipeline Role |
|---|---|---|---|---|---|---|
| `record_id` | UUID | Primary Key | No | UUIDv4 format | Synthetic / Ingestion UUID | Indexing & Audit Log |
| `tenant_id` | UUID | Foreign Key | No | UUIDv4 format | Ingestion Context | RLS Security Isolation |
| `ProviderName` | VARCHAR(64) | Categorical | No | In `['AWS','Azure','GCP','OCI']` | `ProviderName` / System | Filter Dimension |
| `ChargePeriodStart` | TIMESTAMP | Datetime (UTC)| No | Valid ISO-8601 UTC | AWS `UsageStartDate`, Azure `Date` | Time Axis / Index |
| `ChargePeriodEnd` | TIMESTAMP | Datetime (UTC)| No | $> \text{ChargePeriodStart}$ | AWS `UsageEndDate` | Interval Duration |
| `BilledCost` | NUMERIC(18,6)| Currency ($) | No | $\ge 0.0$ | AWS `UnblendedCost`, Azure `CostInBillingCurrency` | Financial Accounting (**Banned from Mode A features**) |
| `EffectiveCost` | NUMERIC(18,6)| Currency ($) | No | $\ge 0.0$ | AWS `NetUnblendedCost`, GCP `cost + credits` | **Primary Prediction Target** ($Y_t$) |
| `ListCost` | NUMERIC(18,6)| Currency ($) | Yes | $\ge 0.0$ | AWS `ListCost`, Azure `ListPrice * Qty`| Discount Analysis |
| `ConsumedQuantity`| NUMERIC(18,6)| Quantity | No | $\ge 0.0$ | AWS `UsageAmount`, Azure `UsageQuantity` | Usage Volume (**Mode B feature only; lagged in Mode A**) |
| `ConsumedUnit` | VARCHAR(64) | Unit Label | No | Text string | AWS `pricing/unit`, Azure `UnitOfMeasure`| Normalization Dimension |
| `ServiceName` | VARCHAR(128)| Categorical | No | Text string | AWS `product/servicecode`, Azure `MeterCategory` | Primary Series Partition |
| `SubAccountId` | VARCHAR(128)| Categorical | No | Account ID | AWS `UsageAccountId`, Azure `SubscriptionId` | Sub-Account Partition |
| `ResourceId` | VARCHAR(512)| Categorical | Yes | ARN / URI string | AWS `resourceId`, Azure `ResourceId` | Entity Drill-Down |
| `RegionId` | VARCHAR(64) | Categorical | Yes | Standard Region | AWS `product/region`, Azure `ResourceLocation` | Geographical Feature |
| `ChargeCategory` | VARCHAR(64) | Enum | No | `Usage`,`Purchase`,`Adjustment`| Inferred from line item type | Scope Filter |
| `Tags` | JSONB | Key-Value | Yes | JSON Object | `resourceTags/user:*`, Azure `Tags` | Attribution Context |

---

## 2. Workload Telemetry Trace Attributes (S3 & S4 Suite)

| Field Name | Type | Unit | Range / Constraints | Description |
|---|---|---|---|---|
| `vm_id` | VARCHAR(64) | Identifier | Alphanumeric | Anonymized unique virtual machine identifier. |
| `timestamp` | TIMESTAMP | ISO-8601 UTC | Multi-week series | 5-minute telemetry timestamp aggregated to 1-hour. |
| `avg_cpu` | FLOAT | Percentage | $[0.0, 100.0]$ | Average CPU utilization over the measurement window. |
| `max_cpu` | FLOAT | Percentage | $[0.0, 100.0]$ | Peak CPU utilization over the measurement window. |
| `mem_assigned` | FLOAT | Gigabytes | $\ge 0.5$ | RAM capacity allocated to the instance. |
| `assigned_vcpu`| INTEGER | Count | $1, 2, 4, 8, 16, 32, 64$| Number of virtual CPU cores provisioned. |
| `derived_unit_rate`| FLOAT | $/vCPU-Hour | $[0.015, 0.450]$ | Public rate-card price applied during S4 tele-pricing. |

---

## 3. Operational Event Attributes (Attribution Candidate Pool)

| Field Name | Type | Nullable | Format / Enum | Description |
|---|---|---|---|---|
| `event_id` | UUID | No | UUIDv4 | Unique primary key for the operational change event. |
| `tenant_id` | UUID | No | UUIDv4 | Tenant namespace identifier. |
| `timestamp` | TIMESTAMP | No | ISO-8601 UTC | Timestamp when the deployment, scaling, or config occurred ($t_e$). |
| `service_name` | VARCHAR(128) | No | Matches `ServiceName` | Affected cloud microservice or infrastructure component. |
| `sub_account_id`| VARCHAR(128) | Yes | Account ID string | Specific target cloud account or project. |
| `event_type` | VARCHAR(64) | No | Enum | `deployment`, `autoscaling`, `config_change`, `migration`, `decoy_maintenance`. |
| `summary` | VARCHAR(256) | No | Text string | Human-readable change log description. |
| `is_decoy` | BOOLEAN | No | True / False | Research benchmark flag: true if injected as an un-correlated background decoy event. |

---

## 4. Ground Truth Fault Annotation Attributes (Segregated Labels)

| Field Name | Type | Range / Constraints | Description |
|---|---|---|---|
| `incident_id` | UUID | UUIDv4 | Unique incident record. |
| `start_time` | TIMESTAMP | ISO-8601 UTC | True start of anomalous behavior ($t_{\text{start}}$). |
| `end_time` | TIMESTAMP | $> \text{start_time}$ | True resolution of anomalous behavior ($t_{\text{end}}$). |
| `fault_family` | VARCHAR(64) | Enum | `volume_runaway`, `rate_spike`, `zombie_resource`, `misconfiguration`, `concurrency_leak`. |
| `magnitude_multiplier` | FLOAT | $\ge 1.10$ | Multiplier applied to baseline expected spend (e.g., $1.25\times$, $2.00\times$). |
| `target_service` | VARCHAR(128) | Valid `ServiceName` | Cloud service targeted by the anomaly injector. |
| `ground_truth_event_id`| UUID | UUIDv4 | Foreign key referencing the true causal event (if not un-attributed noise). |

---

## 5. Derived Feature Store Definitions (Leakage-Isolated)

To prevent target leakage (Forensic Audit Hypothesis H1 & H2), derived features adhere strictly to time and mode boundaries:

| Feature Variable Name | Mathematical Definition | Mode A (History) | Mode B (Usage) | Timing Isolation Rule |
|---|---|---|---|---|
| `cost_lag_1h` | $Y_{t-1}$ | **Included** | **Included** | Lag $\ge 1\text{h}$; observed strictly before $t$. |
| `cost_lag_24h` | $Y_{t-24}$ | **Included** | **Included** | Seasonal daily lag ($24\text{h}$ prior). |
| `cost_lag_168h` | $Y_{t-168}$ | **Included** | **Included** | Weekly seasonal lag ($7\times 24\text{h}$ prior). |
| `cost_rolling_mean_24h`| $\frac{1}{24}\sum_{i=1}^{24} Y_{t-i}$ | **Included** | **Included** | Trailing 24-hour mean excluding current point $t$. |
| `cost_rolling_std_24h` | $\sigma(Y_{t-24:t-1})$ | **Included** | **Included** | Trailing 24-hour volatility excluding point $t$. |
| `usage_contemporaneous`| $Q_t$ | **EXCLUDED** | **Included** | Present at $t$. **Strictly forbidden in Mode A.** |
| `usage_lag_1h` | $Q_{t-1}$ | **Included** | **Included** | Lagged consumption ($1\text{h}$ prior). |
| `unit_rate_trailing` | $\frac{\sum Y_{t-24:t-1}}{\sum Q_{t-24:t-1}}$ | **Included** | **Included** | Historical average price per unit consumed. |
| `hour_of_day` | $\text{hour}(t) \in [0, 23]$ | **Included** | **Included** | Cyclical sine/cosine transformation. |
| `day_of_week` | $\text{day}(t) \in [0, 6]$ | **Included** | **Included** | Calendar dimension known a priori. |
| `is_weekend` | $\mathbb{I}(\text{day} \in [5,6])$ | **Included** | **Included** | Binary indicator known a priori. |
| `billed_cost_t` | $B_t$ | **FORBIDDEN** | **FORBIDDEN** | **Zero-tolerance leakage invariant in all models.** |
