# DriftSense — Data Dictionary Draft

This data dictionary defines the canonical schema, types, descriptions, nullability constraints, and validation rules for datasets in DriftSense:
1. **FOCUS Cost and Usage Table** (Ingested billing data)
2. **Operational Events Table** (Aligned operational context)
3. **Anomaly Labels Table** (Attribution ground truth)

---

## 1. FOCUS Cost and Usage Dataset (`focus_cost_and_usage`)

Standardized schema conforming to FinOps Open Cost & Usage Specification (FOCUS) v1.0/1.3.

| Column Name | Physical Data Type | Logical Type | Nullable? | Example Value | Description & Business Meaning |
|---|---|---|---|---|---|
| `Id` | `BIGINT` | Identifier | No | `11472` | Unique row identifier within the export partition. |
| `ProviderName` | `VARCHAR(32)` | Dimension | No | `"AWS"` | Cloud Service Provider (CSP) delivering the service. |
| `BillingAccountId` | `VARCHAR(64)` | Dimension | No | `"1234567890123"` | Identifier for the root billing entity or master account. |
| `BillingAccountName` | `VARCHAR(128)`| Dimension | Yes | `"SunBird"` | Human-readable name for the billing account. |
| `SubAccountId` | `VARCHAR(64)` | Dimension | No | `"51738928782"` | Scoped account, project, or subscription consuming the resource. |
| `SubAccountName` | `VARCHAR(128)`| Dimension | Yes | `"Atlas Nimbus"` | Human-readable sub-account / project designation. |
| `InvoiceIssuerName` | `VARCHAR(128)`| Dimension | Yes | `"Amazon Web Services, Inc."` | Entity issuing the formal financial invoice. |
| `BillingPeriodStart` | `TIMESTAMP` | Temporal | No | `2024-09-01T00:00:00Z` | Start of the overall billing cycle (UTC). |
| `BillingPeriodEnd` | `TIMESTAMP` | Temporal | No | `2024-10-01T00:00:00Z` | End of the overall billing cycle (UTC). |
| `ChargePeriodStart` | `TIMESTAMP` | Temporal | No | `2024-09-18T22:00:00Z` | Start of the specific rated interval (UTC). **Primary time index**. |
| `ChargePeriodEnd` | `TIMESTAMP` | Temporal | No | `2024-09-18T23:00:00Z` | End of the specific rated interval (UTC). |
| `BillingCurrency` | `VARCHAR(3)` | Dimension | No | `"USD"` | ISO 4217 currency code for invoiced amounts. |
| `ChargeCategory` | `VARCHAR(64)` | Dimension | No | `"Usage"` | Category: `Usage`, `Purchase`, `Tax`, `Credit`, `Refund`. |
| `ChargeFrequency` | `VARCHAR(64)` | Dimension | Yes | `"Usage-Based"` | Frequency of charge: `Usage-Based`, `One-Time`, `Recurring`. |
| `ChargeDescription` | `TEXT` | Metadata | Yes | `"$0.40 per million SQS standard requests"` | Descriptive description of the applied tariff. |
| `ServiceCategory` | `VARCHAR(64)` | Dimension | Yes | `"Compute"`, `"Networking"` | High-level categorization of the service domain. |
| `ServiceName` | `VARCHAR(128)`| Dimension | No | `"Amazon Elastic Compute Cloud"` | Specific cloud service delivering the capability. |
| `RegionId` | `VARCHAR(32)` | Dimension | Yes | `"us-west-2"`, `"ap-south-1"` | Canonical identifier of geographic cloud region. |
| `RegionName` | `VARCHAR(128)`| Dimension | Yes | `"US West (Oregon)"` | Descriptive name of geographic location. |
| `AvailabilityZone` | `VARCHAR(32)` | Dimension | Yes | `"us-west-2a"`, `NULL` | Specific cloud datacenter cluster zone. |
| `ResourceId` | `VARCHAR(256)`| Dimension | Yes | `"arn:aws:sqs:...:my-queue"` | Cloud resource ARN, instance id, or URI. |
| `ConsumedQuantity` | `DECIMAL(24,12)`| Metric | No | `2.000000000000` | Raw amount of the resource consumed. |
| `ConsumedUnit` | `VARCHAR(64)` | Dimension | Yes | `"Requests"`, `"LCU-Hours"`, `"GB"` | Unit of measurement for consumption. |
| `PricingQuantity` | `DECIMAL(24,12)`| Metric | Yes | `2.000000000000` | Quantity multiplied by unit price to compute cost. |
| `PricingUnit` | `VARCHAR(64)` | Dimension | Yes | `"Requests"`, `"Hours"` | Unit applied on the CSP rate card. |
| `BilledCost` | `DECIMAL(18,8)`| Metric | No | `0.00000080` | Invoiced undiscounted cost. |
| `EffectiveCost` | `DECIMAL(18,8)`| Metric | No | `0.00000000` | Net cost after amortizing discounts and credits. **Target metric**. |
| `ListCost` | `DECIMAL(18,8)`| Metric | Yes | `0.00000080` | Baseline cost calculated at standard public list prices. |
| `ContractedCost` | `DECIMAL(18,8)`| Metric | Yes | `0.00000000` | Cost based on negotiated contracted enterprise rates. |
| `ListUnitPrice` | `DECIMAL(18,8)`| Metric | Yes | `0.00000040` | Published list price per unit. |
| `ContractedUnitPrice` | `DECIMAL(18,8)`| Metric | Yes | `0.00000000` | Enterprise negotiated price per unit. |
| `SkuId` | `VARCHAR(64)` | Dimension | Yes | `"G95FST5FTYV3JSRX"` | Stock Keeping Unit identifier in CSP catalog. |
| `Tags` | `JSON / TEXT` | Metadata | Yes | `{"env": "prod", "app": "core"}` | User-defined resource metadata tags. |

---

## 2. Operational Events Dataset (`operational_events`)

Relational schema capturing infrastructure and operational changes aligned by timestamp and service.

| Column Name | Physical Data Type | Logical Type | Nullable? | Example Value | Description & Business Meaning |
|---|---|---|---|---|---|
| `event_id` | `VARCHAR(64)` | Identifier | No | `"evt_deploy_8841"` | Unique operational event identifier. |
| `ts_start` | `TIMESTAMP` | Temporal | No | `2024-09-18T21:45:00Z` | Start timestamp of event onset (UTC). |
| `ts_end` | `TIMESTAMP` | Temporal | No | `2024-09-18T22:05:00Z` | Completion or stabilization timestamp (UTC). |
| `service_id` | `VARCHAR(128)`| Dimension | No | `"Amazon Elastic Compute Cloud"` | Target cloud service affected by the operation. |
| `event_type` | `VARCHAR(64)` | Dimension | No | `"DEPLOYMENT"` | Taxonomy: `DEPLOYMENT`, `SCALING`, `CONFIG_CHANGE`, `TRAFFIC`, `STORAGE`, `BATCH`. |
| `event_source` | `VARCHAR(64)` | Dimension | No | `"GitHub Actions"` | System generating event: `GitHub`, `Kubernetes`, `Terraform`, `SyntheticInjector`. |
| `is_synthetic` | `BOOLEAN` | Indicator | No | `TRUE` | Explicit flag: `TRUE` for injected test faults, `FALSE` for production logs. |
| `metadata_json` | `JSON / TEXT` | Metadata | Yes | `{"commit": "a1b2c", "replicas": 12}` | Payload parameters (e.g. replica count delta, machine type changes). |

---

## 3. Anomaly Labels Dataset (`anomaly_labels`)

Quarantined ground-truth table for evaluating anomaly detection and cause attribution accuracy.

| Column Name | Physical Data Type | Logical Type | Nullable? | Example Value | Description & Business Meaning |
|---|---|---|---|---|---|
| `label_id` | `VARCHAR(64)` | Identifier | No | `"lbl_anom_042"` | Unique ground truth incident label identifier. |
| `service_id` | `VARCHAR(128)`| Dimension | No | `"Amazon Elastic Compute Cloud"` | Service impacted by the cost spike. |
| `onset_timestamp` | `TIMESTAMP` | Temporal | No | `2024-09-18T22:00:00Z` | Timestamp when unexpected cost increase initiated (UTC). |
| `offset_timestamp` | `TIMESTAMP` | Temporal | No | `2024-09-19T06:00:00Z` | Timestamp when spend normalized back to expected baseline (UTC). |
| `primary_cause` | `VARCHAR(64)` | Dimension | No | `"AUTOSCALING_OVERPROVISION"` | Ground-truth root cause term from canonical taxonomy. |
| `contributing_causes` | `JSON / TEXT`| Dimension | Yes | `["TRAFFIC_SURGE"]` | Secondary contributing factor identifiers. |
| `is_synthetic` | `BOOLEAN` | Indicator | No | `TRUE` | `TRUE` if generated via synthetic fault injector; `FALSE` if empirical incident. |
| `severity_score` | `FLOAT` | Metric | Yes | `3.42` | Residual magnitude: standard deviations or spend multiplier above expected baseline. |
| `verification_src` | `VARCHAR(128)`| Metadata | No | `"SyntheticInjector_v1.0"` | Verification authority or post-mortem incident reference. |
