# DriftSense v2 — Data Contracts & Schema Specification

**Document Version:** 2.0.0  
**Status:** Approved Specification  
**Scope:** Canonical Ingestion Contracts, Provider Adapters, Event & Label Schemas, and Tenant Isolation Model.

---

## 1. Executive Overview & Design Principles

DriftSense v2 strictly enforces contract-driven ingestion and feature isolation to eliminate the data leakage and schema instability identified during the v1 audit.

### Core Architectural Rules:
1. **Canonical Schema Alignment:** All multi-cloud billing inputs must transform into the FinOps Open Cost and Usage Specification (FOCUS™) standard (supporting versions 1.0, 1.1, 1.2, 1.3, and 1.4 draft).
2. **Strict Time Isolation:** Feature engineering pipelines must enforce `known_at_prediction_time` validation. Billed cost and contemporaneous cost metrics are banned from prediction feature sets.
3. **Physical Label Segregation:** Ground truth labels and incident markers are stored in dedicated schema tables that are never accessible to inference or training feature queries.
4. **Tenant Isolation:** Every record in the database is strictly bound to a cryptographic `tenant_id` foreign key with Row Level Security (RLS).

---

## 2. Canonical FOCUS Schema (Version 1.0–1.4 Compatible)

All incoming billing data is validated and parsed into the canonical `BillingRecord` relational table.

| Canonical Column Name | Data Type | Nullable | Unit / Format | Description & Validation Rules |
|---|---|---|---|---|
| `record_id` | UUID | No | String UUIDv4 | Unique primary key generated upon ingestion. |
| `tenant_id` | UUID | No | String UUIDv4 | Multi-tenant namespace identifier. |
| `ProviderName` | VARCHAR(64) | No | Text | `AWS`, `Azure`, `GCP`, `OCI`, or `FinOps-Sandbox`. |
| `BillingPeriodStart` | TIMESTAMP | No | UTC ISO-8601 | Start of cloud provider billing cycle. |
| `BillingPeriodEnd` | TIMESTAMP | No | UTC ISO-8601 | End of cloud provider billing cycle. |
| `ChargePeriodStart` | TIMESTAMP | No | UTC ISO-8601 | Start of measured hourly or sub-hourly charge window. |
| `ChargePeriodEnd` | TIMESTAMP | No | UTC ISO-8601 | End of measured charge window. Must be $> \text{ChargePeriodStart}$. |
| `BilledCost` | DECIMAL(18,6) | No | Account Currency | Invoiced charge including tax, credits, and amortizations. |
| `EffectiveCost` | DECIMAL(18,6) | No | Account Currency | Amortized post-discount actual spend. Primary analysis metric. |
| `ListCost` | DECIMAL(18,6) | Yes | Account Currency | Undiscounted list/retail price for the usage. |
| `ContractedCost` | DECIMAL(18,6) | Yes | Account Currency | Negotiated contract price before commitment discounts. |
| `ConsumedQuantity` | DECIMAL(18,6) | No | Dimensionless/Unit | Quantity of physical service usage consumed. |
| `ConsumedUnit` | VARCHAR(64) | No | Text | Unit descriptor (e.g., `Hrs`, `GB-Mo`, `Requests`, `vCPU-Hours`). |
| `PricingQuantity` | DECIMAL(18,6) | Yes | Dimensionless/Unit | Quantity multiplied by unit price to yield cost. |
| `PricingUnit` | VARCHAR(64) | Yes | Text | Billing unit of pricing model. |
| `ServiceName` | VARCHAR(128) | No | Text | Normalized service taxonomy (e.g., `AmazonEC2`, `Virtual Machines`). |
| `ServiceCategory` | VARCHAR(64) | Yes | Text | High-level taxonomy (`Compute`, `Storage`, `Networking`, `Database`). |
| `SubAccountId` | VARCHAR(128) | No | Text | Cloud account ID (AWS Account ID, Azure Subscription ID, GCP Project ID). |
| `SubAccountName` | VARCHAR(256) | Yes | Text | Human-readable account or project name. |
| `ResourceId` | VARCHAR(512) | Yes | Text | Fully-qualified ARN, Resource URI, or Instance ID. |
| `RegionId` | VARCHAR(64) | Yes | Text | Normalized geographical region code (e.g., `us-east-1`, `westeurope`). |
| `AvailabilityZone` | VARCHAR(64) | Yes | Text | Specific zone identifier if applicable. |
| `ChargeCategory` | VARCHAR(64) | No | Enum | `Usage`, `Purchase`, `Adjustment`, `Tax`, `Credit`. |
| `ChargeClass` | VARCHAR(64) | Yes | Enum | `On-Demand`, `Commitment-Discounted`, `Spot`, `Preemptible`. |
| `CommitmentDiscountCategory` | VARCHAR(64) | Yes | Enum | `SavingsPlan`, `ReservedInstance`, `CommittedUseDiscount`, `None`. |
| `Tags` | JSONB | Yes | Key-Value Pairs | Resource metadata tags (e.g., `{"Environment": "Prod", "Owner": "DataEng"}`). |

---

## 3. Provider Adapter Specifications

Each provider exporter parses heterogeneous raw schema lines and maps them into canonical FOCUS fields.

### 3.1 AWS Cost and Usage Report (CUR 2.0 / Data Exports)
* **Source Format:** Parquet or Gzip CSV delivered to S3.
* **Mappings:**
  * `identity/LineItemId` $\rightarrow$ `record_id`
  * `lineItem/LineItemType` $\rightarrow$ `ChargeCategory` (Mapped to `Usage`, `SavingsPlanCoveredUsage`, etc.)
  * `lineItem/UsageStartDate` $\rightarrow$ `ChargePeriodStart`
  * `lineItem/UsageEndDate` $\rightarrow$ `ChargePeriodEnd`
  * `lineItem/UnblendedCost` $\rightarrow$ `BilledCost`
  * `lineItem/NetUnblendedCost` $\rightarrow$ `EffectiveCost` (amortized with Savings Plans / RIs)
  * `lineItem/UsageAmount` $\rightarrow$ `ConsumedQuantity`
  * `pricing/unit` $\rightarrow$ `ConsumedUnit`
  * `product/servicecode` $\rightarrow$ `ServiceName`
  * `lineItem/UsageAccountId` $\rightarrow$ `SubAccountId`
  * `lineItem/ResourceId` $\rightarrow$ `ResourceId`
  * `product/region` $\rightarrow$ `RegionId`
  * `resourceTags/user:*` $\rightarrow$ `Tags`

### 3.2 Azure Cost Management Export
* **Source Format:** Gzip CSV or Parquet export from Azure Blob Storage.
* **Mappings:**
  * `CostInBillingCurrency` $\rightarrow$ `BilledCost`
  * `EffectivePrice * Quantity` or `CostInBillingCurrency` $\rightarrow$ `EffectiveCost`
  * `UsageQuantity` $\rightarrow$ `ConsumedQuantity`
  * `UnitOfMeasure` $\rightarrow$ `ConsumedUnit`
  * `Date` / `BillingPeriodStartDate` $\rightarrow$ `ChargePeriodStart`
  * `MeterCategory` $\rightarrow$ `ServiceName`
  * `SubscriptionId` $\rightarrow$ `SubAccountId`
  * `SubscriptionName` $\rightarrow$ `SubAccountName`
  * `ResourceId` $\rightarrow$ `ResourceId`
  * `ResourceLocation` $\rightarrow$ `RegionId`
  * `Tags` (parsed JSON string) $\rightarrow$ `Tags`

### 3.3 GCP Cloud Billing Export (BigQuery)
* **Source Format:** Direct BigQuery dataset export or JSON/Parquet extract.
* **Mappings:**
  * `cost` $\rightarrow$ `BilledCost`
  * `cost + credits.amount` $\rightarrow$ `EffectiveCost`
  * `usage.amount` $\rightarrow$ `ConsumedQuantity`
  * `usage.unit` $\rightarrow$ `ConsumedUnit`
  * `usage_start_time` $\rightarrow$ `ChargePeriodStart`
  * `usage_end_time` $\rightarrow$ `ChargePeriodEnd`
  * `service.description` $\rightarrow$ `ServiceName`
  * `project.id` $\rightarrow$ `SubAccountId`
  * `project.name` $\rightarrow$ `SubAccountName`
  * `labels` (array of STRUCT) $\rightarrow$ `Tags`
  * `location.region` $\rightarrow$ `RegionId`

---

## 4. Operational Event Contract

Candidate operational events are ingested from CI/CD, orchestrators, and cloud audit logs to enable evidence-backed attribution.

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "OperationalEvent",
  "type": "object",
  "required": [
    "event_id",
    "tenant_id",
    "timestamp",
    "service_name",
    "event_type",
    "summary"
  ],
  "properties": {
    "event_id": { "type": "string", "format": "uuid" },
    "tenant_id": { "type": "string", "format": "uuid" },
    "timestamp": { "type": "string", "format": "date-time" },
    "service_name": { "type": "string" },
    "sub_account_id": { "type": "string" },
    "resource_id": { "type": "string" },
    "region_id": { "type": "string" },
    "event_type": {
      "type": "string",
      "enum": [
        "deployment",
        "autoscaling_policy_change",
        "infrastructure_migration",
        "instance_type_change",
        "configuration_change",
        "pricing_model_change",
        "routine_maintenance_decoy",
        "scheduled_job_decoy"
      ]
    },
    "summary": { "type": "string", "maxLength": 256 },
    "details": { "type": "object" },
    "is_decoy": {
      "type": "boolean",
      "description": "Internal research flag: true if injected as an un-correlated background decoy event."
    }
  }
}
```

---

## 5. Ground Truth Label Contract (Research & Validation Split Only)

To prevent circularity and target leakage, ground truth fault annotations are stored strictly outside the production feature tables.

| Field Name | Type | Description |
|---|---|---|
| `incident_id` | UUID | Unique identifier of the ground truth fault incident. |
| `tenant_id` | UUID | Tenant namespace. |
| `service_name` | VARCHAR(128) | Affected service. |
| `sub_account_id` | VARCHAR(128) | Affected account. |
| `start_time` | TIMESTAMP | True onset timestamp of the fault ($t_{\text{start}}$). |
| `end_time` | TIMESTAMP | True resolution timestamp of the fault ($t_{\text{end}}$). |
| `fault_family` | ENUM | `volume_runaway`, `rate_spike`, `zombie_resource`, `misconfiguration`, `concurrency_leak`. |
| `injected_magnitude` | DECIMAL(8,2) | Relative multiple of expected spend (e.g., $2.5\times$). |
| `ground_truth_event_id`| UUID | Reference to the true generating event (if causal link exists). |
| `is_confounded` | BOOLEAN | True if multiple overlapping events occurred simultaneously. |

---

## 6. Multi-Tenant Architecture & Data Retention Model

### 6.1 Multi-Tenant Isolation
* **Logical & Storage Isolation:** All database relations enforce PostgreSQL Row Level Security (RLS) indexed on `tenant_id`. Every API query context requires an authenticated `tenant_id` claim parsed from the verified JWT.
* **Worker Queue Isolation:** Background inference tasks run with tenant-specific memory allocations and sandboxed scratch volumes. Cross-tenant memory sharing is prohibited.

### 6.2 Data Retention Policy
1. **Raw Ingestion Files (S3/GCS):** Retained for **90 days** in hot storage, transitioned to cold glacier storage for **365 days**, then purged unless compliance override is active.
2. **Normalized Hourly Feature Store:** Aggregated hourly features (`EffectiveCost`, `ConsumedQuantity`, rolling statistics) retained for **18 months** to support multi-season model training.
3. **Detected Incidents & Attribution History:** Retained **indefinitely** in the tenant audit log until tenant deletion.
4. **Right-to-be-Forgotten Protocol:** A tenant deletion request triggers a cryptographic purge of all database rows, cached feature files, model checkpoints, and audit entries matching `tenant_id` within 24 hours.
