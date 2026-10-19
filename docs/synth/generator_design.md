# DriftSense — Controlled Synthetic Event & Anomaly Generator Design

## 1. Motivation and Role in DriftSense
Real-world cloud billing datasets (such as FOCUS exports) accurately capture monetary costs and consumed quantities, but almost never contain verified, structured root-cause labels explaining *why* a specific spending surge occurred.

To objectively evaluate whether DriftSense can correctly attribute anomalies to their true operational causes (evaluating Top-1 and Top-3 accuracy), we design a **Controlled Synthetic Event & Anomaly Generator** (`SyntheticInjector`). 

The generator operates by injecting synthetic operational faults and telemetry shifts into real baseline FOCUS billing traces, emitting paired entries into `operational_events` and `anomaly_labels`.

---

## 2. Mathematical Calibration to Real Data Statistics
The generator avoids injecting naive rectangular steps or arbitrary constant offsets. Instead, injections are scaled relative to empirical baseline parameters:
- **Baseline Calibration**: For target service $s$ at hour of week $h$, the injector computes empirical rolling statistics:
  $$\mu_s(h) = \text{mean}(Y_{s, \text{history}}), \quad \sigma_s(h) = \text{std}(Y_{s, \text{history}})$$
- **Multiplier Injections**: Injected cost perturbations $S_t$ scale as a function of the local service variance:
  $$S_t = Y_t \cdot (1 + \alpha) + \beta \cdot \sigma_s(h) + \epsilon_t$$
  where $\alpha \in [0.4, 2.5]$ represents relative scaling and $\beta \in [2.0, 5.0]$ represents sigma deviation.
- **Log-Normal Consumption Scaling**: Resource consumption metrics (`ConsumedQuantity`) are augmented using log-normal random variables to mimic realistic heavy-tailed cloud resource saturation.

---

## 3. Advanced Anomaly Topologies & Scenarios

### A. Decoy Events (Benign Changes Without Cost Impact)
- **Design**: Real cloud environments experience hundreds of benign deployments, routine health checks, and minor configuration tweaks that do not cause financial anomalies.
- **Implementation**: The injector introduces decoy events ($E_{\text{decoy}}$) into `operational_events` where $\Delta Y_t = 0$.
- **Validation Objective**: Evaluates whether the attribution model avoids false positive attributions (e.g., claiming a minor documentation deployment caused an unrelated spend increase).

### B. Confounder Events (Demand Surges Without Deployment)
- **Design**: Legitimate business traffic spikes (e.g. Black Friday or marketing campaigns) cause spend increases driven solely by external demand without any underlying operational defect.
- **Implementation**: Injects proportional increases in both `ConsumedQuantity` (requests/LCU) and `EffectiveCost` alongside a `TRAFFIC_SURGE` event, with zero deployment or configuration events.
- **Validation Objective**: Evaluates whether the system attributes the cost increase to genuine demand rather than falsely indicting engineering operations.

### C. Multi-Cause Cascades
- **Design**: Major cloud incidents often involve compounding factors (e.g. an aggressive autoscaling policy triggered by a memory leak in a new deployment).
- **Implementation**: Paired event injection: a `DEPLOYMENT_DEFECT` event occurs at $t-30\text{m}$, followed by an `AUTOSCALING_OVERPROVISION` event at $t$ as replica counts surge.
- **Output**: Recorded in `anomaly_labels` with `primary_cause = 'DEPLOYMENT_DEFECT'` and `contributing_causes = ['AUTOSCALING_OVERPROVISION']`.

### D. Timing Jitter and Detection Latency
- **Design**: Billing systems experience metering delays, and operational events precede billing record closure.
- **Implementation**: A stochastic delay $\tau \sim \text{Gamma}(k=2, \theta=15\text{ minutes})$ is introduced between the `ts_start` of an operational event and the first elevated billing interval.

### E. Held-Out Cause Mechanisms (Unseen Anomaly Types)
- **Design**: To test whether attribution models overfit to known training faults, specific cause categories (e.g., `ORPHANED_STORAGE_ACCUMULATION`) are withheld from the training partition and evaluated strictly in the test horizon.
- **Validation Objective**: Verifies graceful degradation—the model should assign low confidence or flag the event as an unknown cause rather than making a high-confidence false attribution.

---

## 4. Deterministic Seed Control & Versioned Configurations

To ensure complete scientific reproducibility, the generator is configured via versioned YAML manifests:
```yaml
# configs/scenarios/scenario_v1.yaml
scenario_id: "synthetic_benchmark_v1"
random_seed: 42
injection_rate: 0.05  # Fraction of intervals containing anomalies
scenarios:
  - name: "runaway_autoscaling_after_release"
    service: "Amazon Elastic Compute Cloud"
    primary_cause: "DEPLOYMENT_DEFECT"
    contributing: ["AUTOSCALING_OVERPROVISION"]
    duration_hours: [3, 8]
    cost_multiplier: [1.8, 3.2]
    lead_time_minutes: [10, 45]
  - name: "decoy_routine_deployment"
    service: "Amazon Simple Queue Service"
    is_decoy: true
    event_type: "DEPLOYMENT"
    cost_impact: 0.0
```
- **Seeding**: Uses isolated NumPy `np.random.default_rng(seed)` instances to ensure generation is independent of system execution order.

---

## 5. Output Schema Generation

For every injected scenario, the generator atomically updates two tables:
1. `operational_events`: Writes timestamped operational records with `is_synthetic = TRUE`.
2. `anomaly_labels`: Writes exact ground-truth window intervals $[t_{\text{onset}}, t_{\text{offset}}]$, severity score, and causal taxonomy labels with `is_synthetic = TRUE`.

---

## 6. Real vs. Synthetic Claim Boundaries

To uphold research ethics and publication integrity, the following boundaries are strictly enforced:

### What Synthetic Results CAN Support:
1. **Algorithmic Correctness**: Proves that the attribution ranker and SHAP pipelines have sufficient mathematical capacity to recover a known operational cause when signal is present.
2. **Top-1 / Top-3 Attribution Metrics**: Enables quantitative evaluation of ranking accuracy, precision, and recall against an indisputable ground truth.
3. **Ablation Validity**: Measures performance degradation when operational event features are systematically removed.

### What Synthetic Results CANNOT Support:
1. **Production Reliability Claims**: Synthetic accuracy cannot be cited as proof that the system will detect unlabelled zero-day production cloud outages.
2. **Causal Proof**: Synthetic evaluation validates that the algorithm identified the injected association; it does not prove real-world physical causality.
3. **Billing Generalization**: Results on calibrated synthetic anomalies cannot guarantee identical performance on different CSP billing architectures without recalibration.

**Mandatory Reporting Policy**: All research reports, dashboard views, and Colab artifacts must display real-data unsupervised metrics (residual magnitude, baseline forecasting error) separate from synthetic attribution accuracy scores.
