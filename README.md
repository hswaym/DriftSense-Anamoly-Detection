# DriftSense

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![FinOps FOCUS](https://img.shields.io/badge/FOCUS-1.0%2F1.3-orange.svg)](https://focus.finops.org/)

**Explainable Machine Learning for Cloud Cost Anomaly Detection & Operational Root-Cause Attribution**

---

## Overview

**DriftSense** is an open-source, research-grade FinOps machine learning framework conforming to the FinOps Foundation FOCUS (FinOps Cost and Usage Specification) 1.0/1.3 standard. Moving beyond traditional binary alerts ("your cloud bill is unusually high"), DriftSense systematically answers three core operational questions:

1. **What was expected?** — Multi-service counterfactual expected-cost forecasting using gradient-boosted regression trees (XGBoost / LightGBM) incorporating autoregressive lags and resource usage (`ConsumedQuantity`).
2. **What actually happened?** — Dynamic residual anomaly scoring with rolling adaptive thresholds separating expected diurnal/seasonal patterns from genuine cost anomalies.
3. **Why did it happen?** — Operational event alignment and TreeSHAP feature attributions, delivering mathematically additive explanations ($|f(x) - \mathbb{E}[f(x)] - \sum \phi_i| \le 10^{-3}$) and non-causal executive audit narratives.

---

## Architecture & System Pipeline

```
[Raw Billing (FOCUS 1.0/1.3) + Telemetry]
                   │
                   ▼
       [Data Cleaning & Harmonization]
                   │
                   ▼
  [Feature Engineering (Lags, Windows, Events)]
                   │
                   ▼
  [Expected-Cost Forecasting (XGBoost/LightGBM)]
                   │
                   ▼
    [Residual Anomaly Detection (Adaptive)]
                   │
                   ▼
   [Operational Root-Cause Attribution]
                   │
                   ▼
 [Explainability (TreeSHAP & Audit Narratives)]
                   │
                   ▼
    [Interactive FinOps Streamlit Dashboard]
```

---

## Installation

### Prerequisites
- Python 3.10 or higher
- Git

### Quickstart
```bash
git clone https://github.com/hswaym/DriftSense-Anamoly-Detection.git
cd DriftSense-Anamoly-Detection

# Create and activate a virtual environment
python -m venv .venv
# Linux/macOS:
source .venv/bin/activate
# Windows:
.venv\Scripts\activate

# Install editable package with ML dependencies
pip install -e ".[ml,dev]"
```

---

## CLI Usage

DriftSense provides a unified, deterministic CLI pipeline:

```bash
# Check environment and accelerator status
driftsense hwcheck

# Idempotently acquire and validate raw dataset
driftsense acquire --config configs/dataset.yaml
driftsense validate --config configs/dataset.yaml

# Clean raw data to canonical hourly grain
driftsense clean --config configs/dataset.yaml

# Engineer temporal, usage, and operational features
driftsense features --config configs/features.yaml

# Run counterfactual forecasting
driftsense forecast --config configs/models.yaml

# Run anomaly detection
driftsense detect --config configs/models.yaml

# Run operational root-cause attribution
driftsense attribute --config configs/models.yaml

# Generate TreeSHAP feature explanations and narratives
driftsense explain --config configs/models.yaml

# Cryptographically verify run manifest
driftsense verify-manifest --manifest runs/<run_id>/manifest.json
```

---

## Interactive FinOps Dashboard

DriftSense includes an interactive, zero-in-app-training Streamlit dashboard:

```bash
streamlit run app/main.py
```

The dashboard includes:
- **🏢 Executive Overview**: Total spend, anomaly delta, service breakdown, and run provenance.
- **📈 Expected vs. Actual Cost**: Multi-service forecasting with anomaly threshold bands.
- **🔍 Root-Cause Attribution**: Ranked operational drivers with strictly non-causal evidence.
- **🧠 TreeSHAP Explainability**: Global driver importance and executive audit narratives.
- **🧪 Scientific Ablations**: 7-arm comparative evaluation across random seeds.

---

## Research Invariants & Non-Causal Framing

1. **Correlation $\neq$ Causation**: In accordance with scientific integrity guidelines, all attribution rankings represent probabilistic model evidence rather than mathematical causal proof.
2. **Strict Test Partition Quarantine**: The evaluation test set ($D_{\text{test}}$, Days 25–30) is quarantined and evaluated strictly once under locked protocol.
3. **Controlled Synthetic Injection**: Synthetic cost anomalies and operational events are isolated to ensure uncorrupted baseline evaluation.

---

## Repository Structure

```
DriftSense-Anamoly-Detection/
├── app/                  # Streamlit FinOps Dashboard
├── configs/              # Canonical pipeline and experiment YAML configs
├── data/                 # Raw, processed, and synthetic datasets
├── docs/                 # Specifications, contracts, and decision logs
├── notebooks/            # Deterministic notebook templates and generated .ipynb
├── runs/                 # Cryptographically verified execution runs and manifests
├── scripts/              # Build, compilation, and utility scripts
├── src/driftsense/       # Core framework source code
│   ├── data/             # Ingestion, validation, and cleaning
│   ├── features/         # Temporal and operational feature pipelines
│   ├── models/           # Forecasters, anomaly detectors, and attribution
│   ├── explain/          # TreeSHAP explainer and narrative generators
│   └── runtime/          # Manifest, hashing, and execution tracing
└── tests/                # Automated pytest unit and integration test suite
```

---

## License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.
