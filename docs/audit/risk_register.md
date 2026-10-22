# DriftSense v2 — Risk Register (Phase 0 Audit)

This risk register tracks all identified methodological, architectural, and evaluation vulnerabilities from the v1 forensic audit, establishing mitigation plans for v2.

---

| Risk ID | Vulnerability / Concern | Affected v1 Area | Severity | Impact on Credibility | v2 Mitigation & Target Phase |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **RSK-01** | **Contemporaneous Target Leakage** | `FeaturePipeline` (`BilledCost` at $t$) | **HIGH** | Forecaster partially memorizes contemporaneous billing line items, deflating WAPE. | Enforce strict Rule C6: exclude all contemporaneous cost columns from feature space. (Phase 5) |
| **RSK-02** | **Usage-Conditioning Blind Spot** | Counterfactual residual definition ($e_t = Y_t - \hat{Y}_t$) | **HIGH** | Forecaster absorbs volume spikes; usage-driven bill surges are NOT flagged as anomalies. | Implement two decoupled modes: Mode A (History-Expected) and Mode B (Usage-Expected). (Phase 1, Phase 5) |
| **RSK-03** | **Attribution Candidate Circularity** | Event candidate pool in attribution evaluation | **HIGH** | 97.87% Top-1 accuracy is an artifact of having only true faults in candidate pool. | Inject calibrated decoy events, confounders, and evaluate with leave-family-out. (Phase 4, Phase 8) |
| **RSK-04** | **Step-Only Anomaly Injection** | Synthetic fault generator (`injector.py`) | **MEDIUM** | Models not evaluated on subtle (<10%) or slow ramps/drifts; metrics over-optimistic. | Implement continuous magnitude distributions and ramp/drift shapes. (Phase 4, Phase 7) |
| **RSK-05** | **Misleading "FPR" Terminology** | Real clean track evaluation | **MEDIUM** | Real data is unlabelled; organic anomalies may be counted as "false alarms". | Rename metric to "Alert Rate on Presumed-Normal Data". (Phase 1, Phase 7) |
| **RSK-06** | **Test Partition Exhaustion** | Chronological test split ($D_{\text{test}}$, Days 25–30) | **HIGH** | $D_{\text{test}}$ was evaluated once (DEC-016). Cannot be reused for v2 tuning without leakage. | Pre-register a fresh, untouched holdout suite for v2. (Phase 1, Phase 2, Phase 15) |
| **RSK-07** | **Unsourced Benchmark Citations** | Literature review & executive reports | **LOW** | Contextual numbers lack formal bibliographic references. | Build `docs/v2/citation_register.md` with $\ge 15$ verified DOIs. (Phase 2, Phase 16) |
| **RSK-08** | **Zero In-App Training Rule Conflict** | Rule G3 vs customer CSV upload | **MEDIUM** | Enterprise customers cannot analyze custom uploads if training is banned in product. | Adopt Decision D1: permit light CPU per-tenant inference and fitting in worker. (Phase 1, Phase 11) |
