# DriftSense FinOps Dashboard Documentation

**Version:** 1.0.0  
**Phase:** PHASE 11 (Interactive FinOps Dashboard)  
**Standard:** FinOps FOCUS 1.0 / 1.3 Specification  
**Architecture:** Streamlit + Python 3 (Pure Artifact Consumer)

---

## 1. Overview and Design Principles

The DriftSense Dashboard is an interactive executive visualization application for exploring cloud cost forecasts, residual anomalies, root-cause attribution rankings, TreeSHAP explainability drivers, and controlled scientific ablations.

### Architectural Invariants:
1. **Zero In-App Training**: The dashboard never trains models, runs pipelines, or modifies datasets. It reads strictly verified artifacts from `runs/`.
2. **Resilient Data Loading**: All artifact loaders in `app/loaders.py` handle missing, empty, or corrupt files gracefully with informative UI banners rather than tracebacks.
3. **Strict Non-Causal Terminology**: Consistent with FinOps Foundation audit standards, all causal claims are phrased in terms of statistical association:
   - "Likely associated causes" instead of "Root causes" or "Definite causes".
   - Scores labelled "Model evidence" instead of "Causality score" or "Proof".
4. **No Hardcoded Absolute Paths (A11.3)**: All file resolution uses relative paths anchored at the repository root.
5. **No GPU Required**: Runs smoothly on any standard CPU workstation or server.

---

## 2. Views and Capabilities

### 🏢 Executive Overview (`app/views/overview.py`)
- High-level KPIs: Total Observed Spend, Expected Cost Baseline, Anomaly Impact Delta ($), and Anomaly Alert Frequency.
- Service Contribution Breakdown: Aggregated spend distribution across cloud services.
- Cryptographic Provenance Matrix: Run IDs, verification status, and commit hashes for Phases 6 through 10.
- Top Operational Incidents Portfolio.

### 📈 Time-Series & Anomaly Explorer (`app/views/forecast_anomalies.py`)
- Service-level time-series visualization comparing Observed Actual Spend vs. Expected Cost Baseline.
- Residual tracking $e(t) = y(t) - \hat{y}(t)$ alongside champion Dynamic Rolling Threshold control limits ($w=24\text{h}, k=3.0\sigma$).
- Detailed tabular view of anomaly excursions with cost impact deltas.

### 🔍 Root-Cause Attribution (`app/views/attribution.py`)
- Incident-by-incident investigation of validation cost anomalies.
- Side-by-side comparison of model evidence:
  - *Temporal Precedence Champion*: Exponential decay across preceding operational events.
  - *Multi-Modal XGBoost Ranker*: Joint telemetry jumps and event metadata.
  - *Empirical Class Prior Baseline*: Static historical frequencies.
- Audit evidence notes confirming rejection of concurrent benign decoy deployments.

### 💡 TreeSHAP Explainability (`app/views/explainability.py`)
- Global feature importance ranking (TreeSHAP Mean $|Attribution|$ and relative %).
- Invariant verification badges:
  - Additivity Check (A9.1): Mathematical reconstruction $f(x) = \phi_0 + \sum \phi_j(x)$.
  - Seed Rank Stability: Mean Spearman $\rho = 0.9044$ across 3 random seeds.
  - Non-Causal Wording Audit (A9.2): 100% compliant phrasing.
- Executive audit narratives detailing statistical drivers and coincident operational events.

### 🔬 Controlled Ablations (`app/views/ablations.py`)
- Comparative performance table across all 7 experimental arms with empirical variance ($\text{mean} \pm \text{std}$) across 3 seeds (`[42, 123, 999]`).
- Visual bar chart comparing validation WAPE.
- Marginal lift breakdown:
  - Usage features (`ConsumedQuantity`): 25.84 percentage point WAPE reduction.
  - Champion XGBoost: 55.7% error reduction over Seasonal Naive baseline.
  - False Positive Robustness across peak and off-peak business regimes ($\text{FPR} \le 0.14\%$).
- Protocol hash verification (`b3d6945e90c46d76310241a2168c7e9e8e8e506589d17e4cb878d547e47dfe7e`).
- Explicit A10.3 circularity caveat disclosure.

---

## 3. How to Launch Locally

To start the dashboard locally:
```bash
streamlit run app/main.py
```
Or with custom port:
```bash
streamlit run app/main.py --server.port 8501
```
