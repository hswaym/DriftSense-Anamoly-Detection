# DriftSense — Technical Contracts Specification

This document establishes binding engineering contracts for data schemas, temporal grains, partitioning semantics, and evaluation metrics. In accordance with Phase 1 governance, fields pending empirical dataset inspection or architect ratification are explicitly identified as **`OPEN ITEM: Awaiting Architect / Dataset Confirmation in Phase 2`**.

---

### Contract 1: Canonical Grain
- **Baseline Definition**: `service_id × timestamp`
- **Temporal Resolution**: Daily aggregation (`1D`) as primary baseline; hourly (`1H`) as secondary telemetry resolution if raw data fidelity permits.
- **Architect Decision**: `OPEN ITEM: Awaiting Architect / Dataset Confirmation in Phase 2 (Recommended: Service × Day)`

---

### Contract 2: Cost Column
- **Baseline Definition**: Cost metrics adhere to FOCUS 1.3 column naming:
  - `BilledCost`: Gross undiscounted cost as invoiced.
  - `EffectiveCost`: Net cost reflecting amortized commitments, discounts, and credits.
- **Primary Target Metric**: `EffectiveCost` (reflects true economic impact of cloud consumption).
- **Architect Decision**: `OPEN ITEM: Awaiting Architect / Dataset Confirmation in Phase 2 (Recommended: EffectiveCost with fallback to BilledCost)`

---

### Contract 3: Timezone Semantics
- **Specification**: **`UTC` (Universal Coordinated Time)** strictly enforced.
- **Rule**: All timestamps ingested from cloud billing or telemetry traces must be parsed with explicit timezone awareness and normalized to UTC (`ISO 8601` format: `YYYY-MM-DDTHH:MM:SSZ`).
- **Architect Decision**: **VERIFIED / ACCEPTED** (`UTC`)

---

### Contract 4: Currency Handling
- **Baseline Specification**: Single-currency normalization.
- **Dimension**: `BillingCurrency` (e.g., `USD`, `INR`, `EUR`).
- **Rule**: If raw data contains multi-currency billing lines, amounts must be converted to a designated base currency using historical daily exchange rates or analyzed in currency-homogenous partitions.
- **Architect Decision**: `OPEN ITEM: Awaiting Architect / Dataset Confirmation in Phase 2 (Recommended: Retain native single currency, e.g., USD or INR without dynamic FX volatility)`

---

### Contract 5: Event Table Schema
- **Specification**: Relational schema capturing operational changes:
  ```sql
  CREATE TABLE operational_events (
      event_id       VARCHAR(64) PRIMARY KEY,
      ts_start       TIMESTAMP NOT NULL,      -- UTC timestamp of event onset
      ts_end         TIMESTAMP NOT NULL,      -- UTC timestamp of event completion
      service_id     VARCHAR(128) NOT NULL,   -- Target cloud service / resource
      event_type     VARCHAR(64) NOT NULL,    -- DEPLOYMENT, SCALING, CONFIG_CHANGE, TRAFFIC, BATCH
      event_source   VARCHAR(64) NOT NULL,    -- GitHub, K8s, Terraform, CloudWatch, Synthetic
      is_synthetic   BOOLEAN NOT NULL,        -- TRUE if generated via fault injection
      metadata_json  TEXT                     -- Arbitrary key-value payload (e.g. replica count, commit SHA)
  );
  ```
- **Architect Decision**: `OPEN ITEM: Awaiting Architect / Dataset Confirmation in Phase 2 (Recommended: Schema above adopted)`

---

### Contract 6: Label Table Schema (Attribution Ground Truth)
- **Specification**: Decoupled ground truth table for validated or injected anomalies:
  ```sql
  CREATE TABLE anomaly_labels (
      label_id          VARCHAR(64) PRIMARY KEY,
      service_id        VARCHAR(128) NOT NULL,
      onset_timestamp   TIMESTAMP NOT NULL,     -- UTC timestamp when anomaly began
      offset_timestamp  TIMESTAMP NOT NULL,     -- UTC timestamp when anomaly normalized
      primary_cause     VARCHAR(64) NOT NULL,    -- Canonical taxonomy term
      contributing_causes TEXT,                 -- Comma-separated or JSON list of secondary causes
      is_synthetic      BOOLEAN NOT NULL,       -- TRUE if injected fault; FALSE if real verified incident
      severity_score    FLOAT,                  -- Relative magnitude ($ or % deviation)
      verification_src  VARCHAR(128)            -- 'SyntheticInjector_v1', 'PostMortem_Audit'
  );
  ```
- **Rule**: The label table is strictly quarantined from model input features; it is queried exclusively by evaluation harnesses.
- **Architect Decision**: `OPEN ITEM: Awaiting Architect / Dataset Confirmation in Phase 2`

---

### Contract 7: Split Specification (Chronological Partitioning)
- **Strategy**: Rolling-origin chronological splits without future lookahead.
- **Partitions**:
  - **Train Partition**: Historical baseline window ($t_0 \to t_{\text{train}}$), minimum 60% of temporal range.
  - **Validation Partition**: Hyperparameter tuning and threshold calibration ($t_{\text{train}} \to t_{\text{val}}$), typically 20%.
  - **Test Partition**: Strictly locked evaluation window ($t_{\text{val}} \to t_{\text{test}}$), remaining 20%.
- **Horizon**: Multi-step horizon $H \in \{1, 7\}$ days ahead.
- **Rule**: Transformers and scalers are `.fit()` strictly on $D_{\text{train}}$ and only `.transform()` on subsequent partitions.
- **Architect Decision**: `OPEN ITEM: Awaiting Architect / Dataset Confirmation in Phase 2`

---

### Contract 8: Prediction-Timestamp Semantics
- **Rule**: For a forecast generated for interval $[t, t+1)$, all input features (lags, rolling aggregates, event counts) must have timestamps $< t$.
- **Formula**:
  $$\hat{Y}_{t} = f(X_{< t})$$
- **Boundary**: Rolling windows must be strictly left-closed: `rolling(window, closed='left')` or `shift(1)`.
- **Architect Decision**: **VERIFIED / ACCEPTED**

---

### Contract 9: Anomaly Definition (Independent of Model Output)
- **Objective Anomaly Definition**: An observed spending event $Y_t$ is defined as an empirical anomaly if and only if:
  1. **Ground-Truth Label**: An active entry exists in `anomaly_labels` covering interval $t$, OR
  2. **Statistical Deviation**: The residual deviation $|Y_t - \mu_{\text{baseline}}| > k \cdot \sigma_{\text{baseline}}$ where $k \ge 3.0$ over a verified stable historical reference window.
- **Independence Principle**: Model prediction residuals $R_t = |Y_t - \hat{Y}_t|$ represent the *model's detector output*, never the ground-truth definition itself.
- **Architect Decision**: `OPEN ITEM: Awaiting Architect / Dataset Confirmation in Phase 2`

---

### Contract 10: Cause Taxonomy
- **Standardized Multi-Class Cause Hierarchy**:
  1. `DEPLOYMENT_DEFECT`: Cost spike triggered by code release, resource leak, or unoptimized query introduced in deployment.
  2. `AUTOSCALING_OVERPROVISION`: Uncapped horizontal or vertical scaling due to aggressive scaling policies or unmanaged load.
  3. `CONFIG_MODIFICATION`: Manual or automated tier upgrade (e.g. upgrading database from `db.m5.large` to `db.m5.16xlarge`).
  4. `EXTERNAL_TRAFFIC_SURGE`: Genuine legitimate or DDoS request spike driving consumption.
  5. `ORPHANED_STORAGE_ACCUMULATION`: Unattached EBS volumes, unpruned snapshots, or rapid S3 bucket expansion without lifecycle policy.
  6. `RUNAWAY_BATCH_PROCESS`: Hung, looped, or unoptimized ETL/ML training jobs executing past scheduled windows.
- **Architect Decision**: `OPEN ITEM: Awaiting Architect / Dataset Confirmation in Phase 2`

---

### Contract 11: Evaluation Metrics
- **Forecasting Residual Metrics**:
  - $\text{MAE} = \frac{1}{N} \sum_{t=1}^N |Y_t - \hat{Y}_t|$
  - $\text{RMSE} = \sqrt{\frac{1}{N} \sum_{t=1}^N (Y_t - \hat{Y}_t)^2}$
  - **MAPE Alternative**: Weighted Absolute Percentage Error (WAPE) / Symmetric MAPE (sMAPE) with numerical safeguard $\epsilon = 10^{-6}$:
    $$\text{WAPE} = \frac{\sum |Y_t - \hat{Y}_t|}{\sum Y_t}, \quad \text{sMAPE} = \frac{100\%}{N} \sum \frac{2 |Y_t - \hat{Y}_t|}{|Y_t| + |\hat{Y}_t| + \epsilon}$$
- **Anomaly Detection Metrics**:
  - Precision, Recall, $F_1 = 2 \cdot \frac{P \cdot R}{P + R}$, False Positive Rate (FPR).
- **Attribution Accuracy Metrics**:
  - **Top-1 Accuracy**: Fraction of detected anomalies where the true cause matches rank-1 predicted cause.
  - **Top-3 Accuracy**: Fraction of detected anomalies where the true cause appears in the top-3 predicted causes.
- **Architect Decision**: `OPEN ITEM: Awaiting Architect / Dataset Confirmation in Phase 2 (sMAPE & WAPE adopted)`
