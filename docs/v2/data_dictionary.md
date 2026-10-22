# DriftSense v2 — Production Data Dictionary & Ingestion Specification

**Document Version:** 2.0.0  
**Phase:** Phase 3 (Data Layer v2 — Ingestion, Schema Mapping, Quality Score)  
**Status:** Approved Production Specification  

---

## 1. Overview & Invariant Contracts

The DriftSense v2 Data Layer normalizes heterogeneous multi-cloud billing formats into the canonical FOCUS™ (FinOps Open Cost and Usage Specification) schema.

### Core Data Invariants:
1. **Single Reporting Currency:** All records in an ingested dataset must share a single currency (default: `USD`). Multi-currency files are rejected or flagged with a 15-point quality deduction.
2. **Strict Time Localization:** All timestamps (`ChargePeriodStart`, `ChargePeriodEnd`) are parsed and normalized to UTC ISO-8601.
3. **Temporal Ordering:** `ChargePeriodEnd > ChargePeriodStart` is strictly enforced.
4. **Target Leakage Prohibition:** Features observed at time $t$ are flagged with `known_at_prediction_time: yes/no`. Contemporaneous cost metrics (`BilledCost`, `ListCost`) are prohibited as prediction features.

---

## 2. Canonical Column Specification

| Column Name | Physical Type | Mandatory | Nullable | Default | Description |
|---|---|---|---|---|---|
| `record_id` | VARCHAR(64) | **Yes** | No | Auto-generated UUID | Unique row identifier for tracing. |
| `tenant_id` | VARCHAR(64) | **Yes** | No | Tenant UUID | Multi-tenant isolation namespace. |
| `ProviderName` | VARCHAR(32) | **Yes** | No | Inferred | Cloud provider (`AWS`, `Azure`, `GCP`, `FOCUS`). |
| `ChargePeriodStart` | TIMESTAMP | **Yes** | No | None | UTC start timestamp of the billing charge interval. |
| `ChargePeriodEnd` | TIMESTAMP | **Yes** | No | Start + 1h | UTC end timestamp of the billing charge interval. |
| `BilledCost` | NUMERIC(18,6) | **Yes** | No | 0.0 | Invoiced charge including taxes and adjustments. |
| `EffectiveCost` | NUMERIC(18,6) | **Yes** | No | `BilledCost` | Post-discount amortized spend (Primary prediction target). |
| `ListCost` | NUMERIC(18,6) | No | Yes | 0.0 | Undiscounted list price for retail benchmark. |
| `ContractedCost` | NUMERIC(18,6) | No | Yes | 0.0 | Negotiated contract price before commitment discounts. |
| `ConsumedQuantity` | NUMERIC(18,6) | **Yes** | No | 0.0 | Quantity of infrastructure usage consumed. |
| `ConsumedUnit` | VARCHAR(64) | **Yes** | No | `Units` | Measurement unit descriptor (e.g. `Hrs`, `GB-Mo`). |
| `PricingQuantity` | NUMERIC(18,6) | No | Yes | 0.0 | Pricing unit multiplier. |
| `PricingUnit` | VARCHAR(64) | No | Yes | None | Pricing rate card unit descriptor. |
| `ServiceName` | VARCHAR(128) | **Yes** | No | `UnknownService`| Normalized service identifier (e.g. `AmazonEC2`). |
| `ServiceCategory` | VARCHAR(64) | No | Yes | None | High-level taxonomy (`Compute`, `Storage`, etc.). |
| `SubAccountId` | VARCHAR(128) | **Yes** | No | `default_account`| Cloud account ID, subscription, or project ID. |
| `SubAccountName` | VARCHAR(256) | No | Yes | None | Human-readable account or project name. |
| `ResourceId` | VARCHAR(512) | No | Yes | None | Unique instance ARN, URI, or identifier. |
| `RegionId` | VARCHAR(64) | No | Yes | `global` | Normalized geographic region code. |
| `ChargeCategory` | VARCHAR(64) | **Yes** | No | `Usage` | `Usage`, `Purchase`, `Adjustment`, `Tax`, `Credit`. |
| `ChargeClass` | VARCHAR(64) | No | Yes | `On-Demand` | Pricing class (`On-Demand`, `Spot`, etc.). |
| `CommitmentDiscountCategory` | VARCHAR(64) | No | Yes | None | `SavingsPlan`, `ReservedInstance`, etc. |
| `Currency` | VARCHAR(8) | **Yes** | No | `USD` | Single ISO-4217 currency code. |
| `Tags` | JSONB / TEXT | **Yes** | No | `{}` | Normalized JSON object of resource tags. |

---

## 3. Provider Adapter Mapping Catalog

### 3.1 AWS Cost and Usage Report (CUR 2.0)
* `lineItem/UsageStartDate` $\rightarrow$ `ChargePeriodStart`
* `lineItem/UsageEndDate` $\rightarrow$ `ChargePeriodEnd`
* `lineItem/UnblendedCost` $\rightarrow$ `BilledCost`
* `lineItem/NetUnblendedCost` $\rightarrow$ `EffectiveCost`
* `lineItem/UsageAmount` $\rightarrow$ `ConsumedQuantity`
* `pricing/unit` $\rightarrow$ `ConsumedUnit`
* `product/servicecode` $\rightarrow$ `ServiceName`
* `lineItem/UsageAccountId` $\rightarrow$ `SubAccountId`
* `lineItem/ResourceId` $\rightarrow$ `ResourceId`
* `product/region` $\rightarrow$ `RegionId`
* `lineItem/LineItemType` $\rightarrow$ `ChargeCategory`
* `resourceTags/user:*` $\rightarrow$ Parsed into `Tags` JSON dictionary.

### 3.2 Microsoft Azure Cost Management Export
* `Date` / `BillingPeriodStartDate` $\rightarrow$ `ChargePeriodStart`
* `CostInBillingCurrency` $\rightarrow$ `BilledCost` and `EffectiveCost`
* `UsageQuantity` $\rightarrow$ `ConsumedQuantity`
* `UnitOfMeasure` $\rightarrow$ `ConsumedUnit`
* `MeterCategory` $\rightarrow$ `ServiceName`
* `SubscriptionId` $\rightarrow$ `SubAccountId`
* `SubscriptionName` $\rightarrow$ `SubAccountName`
* `ResourceId` $\rightarrow$ `ResourceId`
* `ResourceLocation` $\rightarrow$ `RegionId`
* `ChargeType` $\rightarrow$ `ChargeCategory`
* `Tags` $\rightarrow$ Sanitized JSON dictionary.

### 3.3 Google Cloud Billing Export (BigQuery)
* `cost` $\rightarrow$ `BilledCost`
* `cost + credits.amount` $\rightarrow$ `EffectiveCost`
* `usage_start_time` $\rightarrow$ `ChargePeriodStart`
* `usage_end_time` $\rightarrow$ `ChargePeriodEnd`
* `usage.amount` $\rightarrow$ `ConsumedQuantity`
* `usage.unit` $\rightarrow$ `ConsumedUnit`
* `service.description` $\rightarrow$ `ServiceName`
* `project.id` $\rightarrow$ `SubAccountId`
* `project.name` $\rightarrow$ `SubAccountName`
* `location.region` $\rightarrow$ `RegionId`
* `labels` $\rightarrow$ Parsed into `Tags` JSON dictionary.

---

## 4. Data Quality Score Mathematical Model (0–100)

$$\text{Quality Score} = \max\left(0, 100 - \sum_{i=1}^{7} D_i\right)$$

| Deduction Category ($D_i$) | Parameter Condition | Penalty Formula | Maximum Deduction | Plain-Language Rationale |
|---|---|---|---|---|
| **$D_1$: Duplicate Records** | `dup_count > 0` | $\min(15.0, \text{ratio} \times 150)$ | 15.0 pts | Redundant rows corrupt hourly sums. |
| **$D_2$: Missing Calendar Days** | `missing_days > 0` | $\min(20.0, \text{days} \times 2.0)$ | 20.0 pts | Discontinuous time span prevents lag modeling. |
| **$D_3$: Untagged Share** | `untagged_ratio > 0.05` | $\min(15.0, \text{ratio} \times 15.0)$ | 15.0 pts | Missing cost allocation tags hampers attribution. |
| **$D_4$: Unit Conflicts** | `conflict_services > 0` | $\min(20.0, \text{count} \times 10.0)$ | 20.0 pts | Inconsistent units break quantity aggregation. |
| **$D_5$: Negative Adjustments**| `negative_count > 0` | $\min(10.0, \text{ratio} \times 100.0)$ | 10.0 pts | Negative credits distort forecast baselines. |
| **$D_6$: Multi-Currency** | `currency_count > 1` | Flat 15.0 pts | 15.0 pts | Currency mixtures produce invalid totals. |
| **$D_7$: Timestamp Gaps** | `gap_count > 0` | $\min(10.0, \text{gaps} \times 2.0)$ | 10.0 pts | Irregular step intervals undermine lag features. |

### Letter Grade Scale:
* **Grade A:** $90.0 \le \text{Score} \le 100.0$ (Production Certified)
* **Grade B:** $75.0 \le \text{Score} < 90.0$ (High Quality, minor hygiene needed)
* **Grade C:** $60.0 \le \text{Score} < 75.0$ (Acceptable for research, backfill suggested)
* **Grade D:** $40.0 \le \text{Score} < 60.0$ (Poor quality, deduplication/cleaning required)
* **Grade F:** $\text{Score} < 40.0$ (Rejected: Severe data defects)
