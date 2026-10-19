# DriftSense — Project Risk Register

This register identifies, assesses, and outlines mitigations for technical, methodological, and environmental risks across the DriftSense project lifecycle.

---

### Risk Assessment Matrix
- **Severity**: Critical / High / Medium / Low
- **Likelihood**: High / Medium / Low

| Risk ID | Category | Risk Description | Severity | Likelihood | Impact on Project | Mitigation Strategy | Owner | Status |
|---|---|---|---|---|---|---|---|---|
| **RSK-01** | Methodological | **Conflating Correlation with Causation**: High SHAP value or temporal coincidence interpreted as conclusive causal proof of spend spike. | High | High | Overconfident/erroneous root-cause diagnosis in reports and alerts. | Explicitly disclaimer that attribution outputs are ranked probabilistic associations; enforce causal verification language in docstrings and UI. | Antigravity / Claude | OPEN |
| **RSK-02** | Data Integrity | **Synthetic Label Overfitting**: Anomaly attribution model memorizes synthetic injection artifacts rather than realistic billing dynamics. | High | Medium | Inflated benchmark accuracy that fails on real unlabelled billing traces. | Report real-data unsupervised metrics separately from synthetic-data attribution accuracy; introduce noise and varied injection topologies. | Antigravity | OPEN |
| **RSK-03** | Data Engineering | **Evaluation Data Leakage**: Future timestamps, rolling aggregates, or target variables leaking into feature transformers. | Critical | Medium | Artificially high forecasting performance ($R^2 \approx 1.0$) that collapses in forward testing. | Strict chronological splits; feature transformations fit strictly on train splits; rolling windows formally assert `closed='left'` (exclude row $t$). | Antigravity | MITIGATING |
| **RSK-04** | Environment | **Local vs. Colab Python ABI Discrepancy**: Local environment runs Python 3.13.2; Google Colab runs Python 3.10/3.11 with Linux glibc. | Medium | High | Pickled models, compiled C-extensions (LightGBM/XGBoost), or dependencies fail when transferred between platforms. | Package dependencies strictly pinned via `requirements-colab.txt`; code authored for Python $\ge 3.10$ without 3.13-only syntax; serialized artifacts use portable JSON/SafeTensors/ONNX where applicable. | Antigravity | OPEN |
| **RSK-05** | Computational | **Colab Disconnections & Resource Limits**: Colab timeout or GPU/RAM OOM during long hyperparameter optimization runs. | Medium | High | Interrupted experiments and loss of uncommitted run progress. | Stateless training script architecture with `--resume` checkpoints; intermediate artifacts persisted to Google Drive; all runs emit self-contained `manifest.json`. | Antigravity | OPEN |
| **RSK-06** | Data Quality | **Zero-Spend Division in Percentage Metrics**: Traditional MAPE evaluates to $\infty$ or undefined when cloud service cost is 0.00. | Medium | High | Broken evaluation pipelines and invalid comparison tables. | Replace raw MAPE with Symmetric MAPE (sMAPE) or Weighted Absolute Percentage Error (WAPE), with epsilon safeguards ($\epsilon = 10^{-6}$). | Antigravity | MITIGATING |
| **RSK-07** | Operational | **Repository Contamination**: Accidental commit of credentials, cloud API keys, large raw datasets, or IDE artifacts. | High | Low | Security exposure and bloated git history exceeding GitHub limits. | Comprehensive `.gitignore` created in Phase 1; automated secret-scanning before git staging; large datasets downloaded at runtime or mounted via Drive. | Antigravity | MITIGATING |
| **RSK-08** | Governance | **Unverified Dataset Assumptions**: Ingesting datasets with unverified licenses, incompatible schemas, or non-representative grains. | High | Medium | Wasted engineering effort on unusable raw traces. | Mandatory Phase 2 literature and dataset validation gate; explicit schema mapping against FOCUS 1.3 before model development. | Claude / Antigravity | OPEN |
