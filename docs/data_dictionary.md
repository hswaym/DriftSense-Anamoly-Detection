# DriftSense — Final Data Dictionary

This document specifies the authoritative schema, field types, nullability rules, and validation constraints for the ingested **FOCUS Cost and Usage** dataset, as observed from the official FinOps Foundation repository and validated by `driftsense.data.validate`.

---

## 1. FOCUS Cost and Usage Dataset Specification (44 Columns)

| Column Name | Physical Type | Logical Role | Nullable? | Validation & Business Constraints |
|---|---|---|---|---|
| `Id` | `BIGINT` | Identifier | No | Row identifier; unique across partitioned exports. |
| `ProviderName` | `VARCHAR(32)` | Dimension | No | Cloud Service Provider (e.g. `"AWS"`). |
| `BillingAccountId` | `VARCHAR(64)` | Dimension | No | Root billing account or organization master ID. |
| `BillingAccountName` | `VARCHAR(128)` | Dimension | Yes | Descriptive account name. |
| `SubAccountId` | `VARCHAR(64)` | Dimension | No | Scoped project or account consuming the resource. |
| `SubAccountName` | `VARCHAR(128)` | Dimension | Yes | Descriptive project designation. |
| `InvoiceIssuerName` | `VARCHAR(128)` | Dimension | Yes | Financial billing entity. |
| `BillingPeriodStart` | `TIMESTAMP (UTC)` | Temporal | No | Master billing month cycle start (UTC). |
| `BillingPeriodEnd` | `TIMESTAMP (UTC)` | Temporal | No | Master billing month cycle end (UTC). |
| `ChargePeriodStart` | `TIMESTAMP (UTC)` | Temporal | No | Start of the rated interval (UTC). **Primary series timestamp**. |
| `ChargePeriodEnd` | `TIMESTAMP (UTC)` | Temporal | No | End of the rated interval (UTC). |
| `BillingCurrency` | `VARCHAR(3)` | Dimension | No | ISO 4217 currency code (e.g. `"USD"`). |
| `ChargeCategory` | `VARCHAR(64)` | Dimension | No | Standard category (`"Usage"`, `"Purchase"`, `"Tax"`, `"Credit"`). |
| `ChargeClass` | `VARCHAR(64)` | Dimension | Yes | Correction or adjustment class. |
| `ChargeDescription` | `TEXT` | Metadata | Yes | Textual line-item description. |
| `ChargeFrequency` | `VARCHAR(64)` | Dimension | Yes | Billing frequency (`"Usage-Based"`, `"One-Time"`). |
| `ServiceCategory` | `VARCHAR(64)` | Dimension | Yes | Category (`"Compute"`, `"Networking"`, `"Integration"`, etc.). |
| `ServiceName` | `VARCHAR(128)` | Dimension | No | Service name (`"Amazon Elastic Compute Cloud"`, etc.). **Series key**. |
| `RegionId` | `VARCHAR(32)` | Dimension | Yes | Cloud region identifier (`"us-west-2"`, etc.). |
| `RegionName` | `VARCHAR(128)` | Dimension | Yes | Location name (`"US West (Oregon)"`). |
| `AvailabilityZone` | `VARCHAR(32)` | Dimension | Yes | Datacenter cluster zone (`"us-west-2a"`, etc.). |
| `ResourceId` | `VARCHAR(256)` | Dimension | Yes | Unique resource ARN or identifier. |
| `ConsumedQuantity` | `FLOAT64` | Metric | No | Raw quantity of resource consumed. Non-negative. |
| `ConsumedUnit` | `VARCHAR(64)` | Dimension | Yes | Metric unit (`"Requests"`, `"LCU-Hours"`, `"GB"`). |
| `PricingQuantity` | `FLOAT64` | Metric | Yes | Quantity rated on the tariff schedule. |
| `PricingUnit` | `VARCHAR(64)` | Dimension | Yes | Unit corresponding to CSP list price. |
| `BilledCost` | `FLOAT64` | Metric | No | Undiscounted cost invoiced. Non-negative (except refunds). |
| `EffectiveCost` | `FLOAT64` | Metric | No | Net cost after amortized savings and credits. **Target prediction metric**. |
| `ListCost` | `FLOAT64` | Metric | Yes | List price cost. |
| `ContractedCost` | `FLOAT64` | Metric | Yes | Negotiated contract cost. |
| `ListUnitPrice` | `FLOAT64` | Metric | Yes | Public rate card unit price. |
| `ContractedUnitPrice` | `FLOAT64` | Metric | Yes | Negotiated enterprise unit price. |
| `SkuId` | `VARCHAR(64)` | Dimension | Yes | CSP catalog SKU identifier. |
| `Tags` | `JSON / TEXT` | Metadata | Yes | User tags (JSON: `{"application": "...", "environment": "..."}`). |

---

## 2. Core Modeling Views & Granularity
- **Canonical Series Identifier**: `ServiceName`
- **Canonical Temporal Grain**: Hourly charge intervals (`ChargePeriodStart` in UTC).
- **Primary Numerical Target**: `EffectiveCost`
- **Secondary Usage Predictor**: `ConsumedQuantity` (standardized by `ConsumedUnit`).
