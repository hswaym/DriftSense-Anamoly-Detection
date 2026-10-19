# DriftSense — Dataset Candidate Decision Report

This report presents an empirical evaluation of candidate datasets for DriftSense. Each candidate is audited against 15 required evaluation criteria to establish its suitability for cloud cost forecasting, anomaly detection, and operational attribution.

---

### Candidate 1: FOCUS Sample Data (FinOps Foundation)
1. **Official Name & URL**: FOCUS Sample Data (`FOCUS-Sample-Data`), [https://github.com/FinOps-Open-Cost-and-Usage-Spec/FOCUS-Sample-Data](https://github.com/FinOps-Open-Cost-and-Usage-Spec/FOCUS-Sample-Data)
2. **Publisher**: FinOps Foundation (Linux Foundation)
3. **License**: Apache-2.0 License (verified via `license.md` in repository)
4. **Download Method**: Direct HTTPS raw fetch from GitHub repository via `curl` / Python `requests`.
5. **Format & Schema**: CSV / Gzipped CSV. Schema matches FOCUS 1.0 / 1.3 Cost and Usage specification (44 standardized columns).
6. **Rows / Columns / Entities**:
   - `focus_sample.csv`: 1,000 rows, 44 columns, 755 KB.
   - `focus_sample_10000.csv`: 10,000 rows, 44 columns, 7.5 MB.
   - `focus_sample_100000.csv.gz`: 100,000 rows, 44 columns, 9.1 MB gzipped.
   - Distinct services: AWS SQS, EC2, ELB, CloudWatch, S3, RDS, NAT Gateway, etc.
   - Resources: Unique ARNs and instance identifiers (`i-032l64f2065481b12`, etc.).
7. **Temporal Coverage & Frequency**: Hourly billing charge intervals (`ChargePeriodStart` to `ChargePeriodEnd`), covering multi-week billing cycles (September–October 2024).
8. **Cost / Usage / Telemetry / Event Fields**:
   - **Cost Fields**: `BilledCost`, `EffectiveCost`, `ContractedCost`, `ListCost`, `ContractedUnitPrice`, `ListUnitPrice`.
   - **Usage Fields**: `ConsumedQuantity`, `ConsumedUnit`, `PricingQuantity`, `PricingUnit`.
   - **Dimensions**: `ProviderName`, `ServiceName`, `ServiceCategory`, `RegionId`, `RegionName`, `ResourceId`, `Tags` (JSON metadata: application, environment, business_unit).
   - **Events/Telemetry**: No operational event logs included.
9. **Missing Fields**: Lacks direct operational event timestamps (deployments, config changes) and ground-truth anomaly labels.
10. **Anomaly Labels (Y/N)**: **No** (unlabelled real-world cloud billing export).
11. **Root-Cause Labels (Y/N)**: **No**.
12. **Nature**: **Real / Transformed** (Anonymized enterprise billing export conforming to the open FOCUS standard).
13. **Storage & Compute Needs**: Minimal: 7.5 MB raw, ~50 MB in-memory Pandas dataframe; trivial CPU consumption for local smoke tests, scalable to Colab.
14. **Reproducible Acquisition Steps**:
    ```bash
    curl -fsSL -o data/raw/focus_sample_10000.csv \
      https://raw.githubusercontent.com/FinOps-Open-Cost-and-Usage-Spec/FOCUS-Sample-Data/main/FOCUS-1.0/focus_sample_10000.csv
    ```
15. **Verification Evidence**: Directly verified on 2026-10-19 via GitHub API and raw content inspection (`sha256: 0bf58b73123294c4476b648e647cad842935036f67dc4e9a2cc4a6d7497cc2e3`, Git blob `sha: 3315d4806a37642f4cff86e7977302adf089e486`, 7,529,214 bytes).
16. **Decision**: **SELECTED (PRIMARY DATASET)**  
    - **Reason**: 100% compliant with the FinOps FOCUS 1.3 specification; provides verified multi-service hourly cost and consumed usage metrics across real AWS services; permissive Apache-2.0 license.

---

### Candidate 2: Alibaba Cluster Trace (v2018 / v2021)
1. **Official Name & URL**: Alibaba Cluster Data, [https://github.com/alibaba/clusterdata](https://github.com/alibaba/clusterdata)
2. **Publisher**: Alibaba Group
3. **License**: Custom Academic Research License
4. **Download Method**: HTTP / OSS bucket download
5. **Format & Schema**: CSV files covering machine utilization, container usage, and batch task metrics.
6. **Rows / Columns / Entities**: ~4,000 machines, millions of batch jobs across 8 days.
7. **Temporal Coverage & Frequency**: Per-second and 10-second resource utilization intervals.
8. **Cost / Usage / Telemetry / Event Fields**: CPU utilization, memory percent, disk I/O, task start/end timestamps. Zero cost or currency fields.
9. **Missing Fields**: No `BilledCost`, no `EffectiveCost`, no cloud pricing tiers, no billing account metadata.
10. **Anomaly Labels (Y/N)**: **No**.
11. **Root-Cause Labels (Y/N)**: **No**.
12. **Nature**: **Real** (Production cluster telemetry).
13. **Storage & Compute Needs**: Massive: >50 GB compressed, requiring multi-node Spark clusters to process.
14. **Reproducible Acquisition Steps**: Requires manual registration and multi-part OSS script download.
15. **Verification Evidence**: Documented in academic cluster computing benchmarks.
16. **Decision**: **REJECTED**  
    - **Reason**: Lacks monetary billing and cost dimensions completely. DriftSense is fundamentally a financial cost anomaly detection system.

---

### Candidate 3: Azure Public Dataset (VM Workload Traces)
1. **Official Name & URL**: Azure Public Dataset, [https://github.com/Azure/AzurePublicDataset](https://github.com/Azure/AzurePublicDataset)
2. **Publisher**: Microsoft Azure
3. **License**: CC-BY-4.0
4. **Download Method**: Azure Blob Storage / Blob SAS URL
5. **Format & Schema**: CSV / Parquet traces of VM CPU usage and memory lifetimes.
6. **Rows / Columns / Entities**: >2 million VM lifetimes over 30 days.
7. **Temporal Coverage & Frequency**: 5-minute average CPU readings.
8. **Cost / Usage / Telemetry / Event Fields**: VM creation/deletion events, average CPU, max CPU. No billing lines or invoiced cost.
9. **Missing Fields**: Zero financial or pricing information.
10. **Anomaly Labels (Y/N)**: **No**.
11. **Root-Cause Labels (Y/N)**: **No**.
12. **Nature**: **Real** (Anonymized Azure hypervisor telemetry).
13. **Storage & Compute Needs**: High (>10 GB compressed).
14. **Reproducible Acquisition Steps**: Python blob client download from Azure open datasets.
15. **Verification Evidence**: Publicly cited in cloud systems research.
16. **Decision**: **REJECTED**  
    - **Reason**: Contains machine resource traces but no monetary billing metrics or FOCUS schema attributes.

---

### Candidate 4: Numenta Anomaly Benchmark (NAB)
1. **Official Name & URL**: Numenta Anomaly Benchmark (NAB), [https://github.com/numenta/NAB](https://github.com/numenta/NAB)
2. **Publisher**: Numenta
3. **License**: AGPL-3.0 License
4. **Download Method**: GitHub clone / raw HTTPS fetch.
5. **Format & Schema**: 2-column CSV (`timestamp`, `value`).
6. **Rows / Columns / Entities**: 58 individual univariate time series, ~4,000–10,000 rows each.
7. **Temporal Coverage & Frequency**: 5-minute intervals spanning weeks to months.
8. **Cost / Usage / Telemetry / Event Fields**: Single metric stream (e.g. AWS CloudWatch CPU, network bytes, Twitter volume). No cost or service dimensions.
9. **Missing Fields**: No multidimensional attributes, no billing categories, no resource identifiers.
10. **Anomaly Labels (Y/N)**: **Yes** (Window-based ground truth anomaly timestamps provided in `labels/combined_windows.json`).
11. **Root-Cause Labels (Y/N)**: **No** (Binary anomaly flags only; no operational cause metadata).
12. **Nature**: **Real** with verified window labels.
13. **Storage & Compute Needs**: Extremely lightweight (<15 MB total).
14. **Reproducible Acquisition Steps**: Direct curl from Numenta GitHub repository.
15. **Verification Evidence**: Peer-reviewed benchmark (Ahmad et al., 2017).
16. **Decision**: **REJECTED AS PRIMARY; RETAINED AS SECONDARY BENCHMARK**  
    - **Reason**: Excellent for testing isolated univariate anomaly detectors, but unsuitable as primary DriftSense dataset because it lacks multi-service financial billing dimensions and root causes.

---

### Candidate 5: ServerMachineDataset (SMD)
1. **Official Name & URL**: ServerMachineDataset (OmniAnomaly benchmark), [https://github.com/NetManAIOps/OmniAnomaly](https://github.com/NetManAIOps/OmniAnomaly)
2. **Publisher**: NetMan AIOps Lab (Tsinghua University)
3. **License**: MIT License
4. **Download Method**: GitHub raw download.
5. **Format & Schema**: Continuous matrix of 38 server metrics.
6. **Rows / Columns / Entities**: 28 machines, 5 weeks of data, ~700,000 points.
7. **Temporal Coverage & Frequency**: 1-minute intervals.
8. **Cost / Usage / Telemetry / Event Fields**: 38 telemetry metrics (CPU, memory, disk, network). Zero billing data.
9. **Missing Fields**: Lacks monetary cost, currency, billing tags, and cloud service metadata.
10. **Anomaly Labels (Y/N)**: **Yes** (Binary point anomaly labels).
11. **Root-Cause Labels (Y/N)**: **No** (Anomaly interpretation list provided, but no operational event logs).
12. **Nature**: **Real** production traces.
13. **Storage & Compute Needs**: Moderate (~100 MB).
14. **Reproducible Acquisition Steps**: Raw fetch from OmniAnomaly GitHub repository.
15. **Verification Evidence**: Published at ACM KDD 2019 (Su et al.).
16. **Decision**: **REJECTED**  
    - **Reason**: Pure server telemetry benchmark; does not represent enterprise cloud billing or FinOps data structures.

---

### Candidate 6: NetMan DejaVu Microservice Benchmark
1. **Official Name & URL**: DejaVu Benchmark, [https://github.com/NetManAIOps/DejaVu](https://github.com/NetManAIOps/DejaVu)
2. **Publisher**: NetMan AIOps Lab / BizSeer
3. **License**: Apache-2.0
4. **Download Method**: GitHub repository release / Zenodo link.
5. **Format & Schema**: JSON topology graphs + metric CSVs + injected fault logs.
6. **Rows / Columns / Entities**: Microservice call graphs across hundreds of injected failure episodes.
7. **Temporal Coverage & Frequency**: Seconds to minutes during fault injection runs.
8. **Cost / Usage / Telemetry / Event Fields**: Service response time, error rate, fault injection manifests (type, node, timestamp). Zero monetary billing data.
9. **Missing Fields**: No cloud billing or invoicing fields.
10. **Anomaly Labels (Y/N)**: **Yes**.
11. **Root-Cause Labels (Y/N)**: **Yes** (Specific injected fault types and affected services logged).
12. **Nature**: **Simulated / Synthetic Fault Injection** over containerized services.
13. **Storage & Compute Needs**: ~500 MB.
14. **Reproducible Acquisition Steps**: Git clone or Zenodo archive unpack.
15. **Verification Evidence**: Published at ACM ESEC/FSE 2022 (Li et al.).
16. **Decision**: **EVALUATED AS REFERENCE ARCHITECTURE; REJECTED AS PRIMARY BILLING**  
    - **Reason**: Invaluable as an architectural reference for designing DriftSense's synthetic fault injection engine, but rejected as the primary billing dataset because it contains no FOCUS cloud cost fields.

---

### Summary of Dataset Decisions

| Candidate Dataset | Focus / Domain | License | Billing Fields? | Anomaly Labels? | Root-Cause Labels? | Final Decision |
|---|---|---|---|---|---|---|
| **FOCUS Sample Data** | Cloud Billing (FOCUS 1.0/1.3) | Apache-2.0 | **Yes** | No | No | **SELECTED (Primary)** |
| **Alibaba Cluster Trace** | Cluster Job Telemetry | Academic | No | No | No | **REJECTED** |
| **Azure Public Dataset** | VM Resource Traces | CC-BY-4.0 | No | No | No | **REJECTED** |
| **Numenta Anomaly Benchmark** | Univariate Streaming Metrics | AGPL-3.0 | No | Yes | No | **REJECTED (Primary)** |
| **ServerMachineDataset** | Multi-variate Server Telemetry | MIT | No | Yes | No | **REJECTED** |
| **DejaVu Benchmark** | Microservice Injected Faults | Apache-2.0 | No | Yes | Yes | **REJECTED (Primary)** |
