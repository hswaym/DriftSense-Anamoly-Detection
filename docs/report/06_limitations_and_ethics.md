# DriftSense — Final Report: Chapter 6. Limitations, Ethics & Governance

Academic rigor and engineering integrity require transparent documentation of assumptions, synthetic caveats, and ethical boundaries.

---

## 6.1 Epistemic Boundary: Correlation vs. Causation

The most critical operational caveat in DriftSense is the fundamental distinction between statistical correlation and physical causation.

1. **Statistical Association Only**: The root-cause attribution engine ranks operational events based on temporal proximity kernels and service colocation. A high attribution score indicates strong temporal correlation, not definitive physical causation.
2. **Confounding Variables**: Unobserved external factors—such as underlying cloud provider hypervisor faults, unannounced API price shifts, or hidden third-party upstream dependencies—may coincide with an internal deployment without being caused by it.
3. **Automated Guardrails**: All natural language audit narratives are systematically validated by `validate_non_causal_text()`, ensuring that no automated report ever claims an event "caused" or "triggered" an anomaly. Human engineering validation remains an indispensable requirement.

---

## 6.2 Synthetic Event Circularity Caveat (A10.3)

To benchmark detection sensitivity and attribution accuracy, DriftSense relies on controlled synthetic fault injection (`driftsense.synth.injector`).

* **Circularity Risk**: When machine learning models are evaluated against synthetic anomalies generated via explicit mathematical rules (e.g., multiplier steps or exponential ramps), there is a latent risk that feature engineering exploits synthetic artifacts that do not exist in real production outages.
* **Mitigation Protocol**:
  1. The forecasting model ($\hat{Y}_t$) was trained strictly on clean historical billing data without synthetic faults.
  2. The detection threshold was fit on clean residual variance, preserving genuine out-of-distribution detection capability.
  3. Real clean track FPR was audited independently on untouched billing data, confirming that low false alarm rates are genuine and uninfluenced by synthetic assumptions.

---

## 6.3 Billing Ingestion Latency & Real-Time Limitations

1. **Vendor Ingestion Delay**: Cloud billing APIs (AWS Cost Explorer, Azure Cost Management, GCP BigQuery Billing Export) do not emit true real-time streaming data. Billing records typically settle with a latency of 4 to 24 hours.
2. **Operational Scope**: DriftSense is designed as an hourly near-line FinOps auditing and rapid detection system. It does not replace real-time operating system metrics (e.g., Prometheus 15-second CPU metrics) for immediate infrastructure auto-remediation.
3. **Unit Cost Volatility**: For serverless architectures with millions of ephemeral micro-invocations, sub-hour cost fluctuations may exhibit high variance that requires grouping to 1-hour canonical grains.

---

## 6.4 Ethical & Organizational Governance

1. **Blameless Post-Mortem Culture**: Automated attribution must not be used punitively against individual software engineers who authored commits coincident with cost spikes. DriftSense explicitly frames attribution as system-level telemetry to accelerate blameless remediation.
2. **Data Privacy & Multi-Tenancy**: The FOCUS standard normalizes data to resource IDs and service categories, ensuring that proprietary payload data, customer personally identifiable information (PII), and application database contents are never ingested by the cost modeling engine.
