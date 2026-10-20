# DriftSense — Final Report: Chapter 3. Data Ingestion, Hygiene & FOCUS Standard

## 3.1 The FinOps Open Cost & Usage Specification (FOCUS)

To eliminate vendor lock-in and establish cross-cloud compatibility, DriftSense adopts the **FinOps Open Cost & Usage Specification (FOCUS) v1.0 / v1.3** as its foundational data schema.

FOCUS is an industry-standard open specification stewarded by the FinOps Foundation (Linux Foundation), establishing clear column semantics, types, and relationships for cloud billing data.

### Standard FOCUS Dimensions Utilized in DriftSense

| FOCUS Column Name | Data Type | Description | Role in DriftSense Pipeline |
| :--- | :--- | :--- | :--- |
| `ChargePeriodStart` | UTC Timestamp | Start of the billing consumption window | Primary chronological time index ($t$) |
| `ChargePeriodEnd` | UTC Timestamp | End of the billing consumption window | Window validation & boundary checking |
| `ServiceName` | Categorical String | Normalized provider service (e.g. `Amazon Elastic Compute Cloud`) | Partition key & service filtering dimension |
| `EffectiveCost` | Float64 ($) | Amortized post-discount actual spend | **Primary target variable ($Y_t$)** |
| `BilledCost` | Float64 ($) | Cash-basis undiscounted invoice cost | Explanatory feature & cost variance driver |
| `ConsumedQuantity` | Float64 | Measured volume of resource consumption | **Primary operational usage feature** |
| `ConsumedUnit` | Categorical String | Measurement unit (e.g., `Hours`, `GB-Mo`) | Unit normalization & validation |
| `PricingUnit` | Categorical String | Pricing denominator unit | Pricing tier verification |
| `RegionName` | Categorical String | Deployment geographic region | Geographic slice analysis |

---

## 3.2 Data Hygiene and Standardization Pipeline

Raw cloud billing data frequently contains irregularities that degrade statistical models if unaddressed. DriftSense implements a deterministic data hygiene module (`src/driftsense/data/clean.py` and `aggregate.py`) enforcing:

1. **Deduplication**: Identification and purging of duplicate billing records sharing identical `(ChargePeriodStart, ServiceName, ResourceId, ChargeCategory)`.
2. **UTC Timestamp Alignment**: Coercion of diverse string date formats into timezone-aware ISO 8601 UTC timestamps, flagging records with start dates after end dates.
3. **Canonical 1-Hour Aggregation**: Raw records are grouped and summed to a strict 1-hour grain per service. Missing hourly intervals are reindexed onto a continuous hourly grid with zero-imputation to prevent discontinuous lag structures.
4. **Negative Spend Segregation**: Credits, refunds, and adjustments (negative `EffectiveCost`) are segregated from consumption spend and logged separately, ensuring cost modeling reflects true infrastructure consumption.

---

## 3.3 Strict Chronological Partitioning ($D_{\text{train}}, D_{\text{val}}, D_{\text{test}}$)

To eliminate lookahead bias and evaluation leakage, DriftSense rejects random shuffling in favor of strict chronological splitting:

```
[ Day 1 ------------------- Day 15 ] [ Day 16 -------- Day 24 ] [ Day 25 -------- Day 30 ]
           D_train (50%)                      D_val (30%)                    D_test (20%)
   2024-09-01 00:00 - 2024-09-15        2024-09-16 - 2024-09-24        2024-09-25 - 2024-09-30
     Historical Training Split             Model Selection Split          Quarantined Test Horizon
```

### Anti-Leakage Protocol (DEC-005, A10.1)
* **Feature Transformer Bounds**: All scalers, mean encoders, and lag aggregators are fit strictly on $D_{\text{train}}$. No statistics from $D_{\text{val}}$ or $D_{\text{test}}$ are ever computed prior to inference.
* **Lag Formulation**: Rolling windows and difference metrics strictly exclude the current observation $t$ (e.g., rolling mean spans $[t-24, t-1]$).
* **Quarantined Test Horizon**: The test split $D_{\text{test}}$ was locked in storage until Phase 13 and evaluated exactly once under cryptographic hash guards.

---

## 3.4 Operational Telemetry & Synthetic Fault Injection

Real cloud billing traces rarely provide verified, objective labels explaining the exact root cause behind cost spikes. To provide a rigorous benchmark ground truth, DriftSense combines real/FOCUS billing traces with a deterministic synthetic fault generator (`src/driftsense/synth/injector.py`).

The generator injects 5 realistic operational incident types:

1. **`RUNAWAY_BATCH_PROCESS`**: Unbounded compute loops causing continuous, sustained spend elevation.
2. **`AUTOSCALING_OVERPROVISION`**: Flawed threshold policies causing oscillating or excess server provisioning.
3. **`CONFIG_MODIFICATION`**: Accidental instance-type upgrades or parameter changes altering baseline cost.
4. **`DEPLOYMENT_DEFECT`**: Software regressions that inflate memory or CPU consumption per request.
5. **`EXTERNAL_TRAFFIC_SURGE`**: Organic high-volume traffic events requiring infrastructure scale.

Each injected fault generates an exact ground-truth record with onset timestamp, duration, affected service, magnitude, and operational fault label, enabling rigorous event-level detection and attribution scoring.
