# DriftSense v1 Forensic Audit Report (Phase 0)

**Date of Audit:** 2026-10-21  
**Audit Scope:** DriftSense v1 baseline (`origin/main`, commit `ffd11c7`, frozen run `run_20261020_183410_6f5272`)  
**Auditor:** Antigravity (Implementation Agent) under `DriftSense_V2_Master_Prompt_Pack.md` protocol  
**Reviewer:** Claude (Architectural Reviewer)  

---

## 1. Executive Summary of Audit Findings

The Phase 0 forensic audit evaluated the seven critical hypotheses (H1–H7) raised by Claude in Part B2 of the v2 Master Prompt Pack against the executed code, datasets, manifests, and test runs of DriftSense v1.

| Hypothesis ID | Target Problem Area | Forensic Verdict | Core Evidence & Severity |
| :--- | :--- | :--- | :--- |
| **H1** | **Target Leakage via Contemporaneous Cost** | **CONFIRMED** | `BilledCost` (contemporaneous cost at hour $t$) is unlagged in `FeaturePipeline.feature_names_`. In the TreeSHAP importance table, `BilledCost` accounts for **48.18% relative importance** (Rank 1 driver) when predicting `EffectiveCost`. High severity. |
| **H2** | **Narrow Counterfactual Semantics** | **CONFIRMED** | `ConsumedQuantity` at hour $t$ is included unlagged in the feature matrix. Conditioning on actual usage volume means the model predicts high cost when usage surges, keeping residuals $e_t = Y_t - \hat{Y}_t$ small. v1 flags rate/efficiency deviations, but misses volume-driven surges. |
| **H3** | **Circular Attribution Candidate Pool** | **CONFIRMED** | Candidate operational events in the test evaluation pool consist exclusively of injected faults. Zero non-injected decoy events exist in the candidate pool. The 97.87% Top-1 accuracy largely measures identifying the nearest same-service injected event within a 6h window. |
| **H4** | **Abrupt Large-Magnitude Fault Injections** | **CONFIRMED** | Injected faults in narratives show cost spikes of +330% to +515% (e.g. $4.00 vs $0.65). These large, abrupt step injections explain the high event precision (90%), event recall (95.74%), and 0.00h detection delay. Gradual low-magnitude drift (<10%) was not evaluated. |
| **H5** | **Alert Rate on Presumed-Normal Series ("FPR")** | **CONFIRMED** | The clean track False Positive Rate (0.16%, 6 alarms / 3,822 hours) was computed on real unlabelled data, implicitly assuming real data contains zero anomalies. Without external ground truth on the real split, this metric represents an alert rate on presumed-normal data, not a verified FPR. |
| **H6** | **Dataset Topology & Zero-Imputation** | **CONFIRMED** | `focus_sample_10000.csv` contains 10,000 raw lines across 27 distinct AWS services. Aggregating to 1h canonical grain zero-imputes missing hours per service across the full 30-day timeline (144 hours $\times$ 26.54 active services $\approx$ 3,822 test records in $D_{\text{test}}$). |
| **H7** | **Unsourced External Benchmark Claims** | **CONFIRMED** | Citations such as "industry avg FPR ~5–10%" and "unsupervised Point-F1 ~0.40" in executive summaries lack specific DOI or paper references. |

---

## 2. Detailed Hypothesis Findings & Execution Evidence

### Hypothesis 1: Target Leakage in Feature Engineering
- **Claude's Hypothesis:** Top SHAP driver for forecasting `EffectiveCost` is `BilledCost` (48.18%). A contemporaneous, near-duplicate cost column used as a feature would inflate accuracy and contradict the stated rule that features exclude timestamp $t$.
- **Verdict:** **CONFIRMED**
- **Forensic Evidence:**
  - Inspection of `src/driftsense/features/builder.py` lines 128–143 reveals:
    ```python
    exclude_cols = {
        self.target_col,            # "EffectiveCost"
        f"{self.target_col}Raw",
        self.service_col,
        self.time_col,
        "ChargePeriodEnd",
        "Id",
        "Tags",
    }
    numeric_cols = [c for c in df_raw_feats.columns if c not in exclude_cols and pd.api.types.is_numeric_dtype(df_raw_feats[c])]
    ```
  - `BilledCost` is NOT excluded. As a result, `BilledCost` at timestamp $t$ was automatically added to `feature_names_`.
  - The frozen run artifact `runs/run_20261020_183410_6f5272/test_shap_importance.csv` confirms:
    - Rank 1: `BilledCost`, $\text{mean}\|\text{SHAP}\| = 0.00941$, **48.18% relative importance**.
  - **Impact:** The forecaster was partially learning the contemporaneous identity between cash billing (`BilledCost`) and amortized spend (`EffectiveCost`), artificially deflating forecasting error.
  - **v2 Remedy:** Exclude all contemporaneous cost-derived columns from the feature contract (Rule C6).

---

### Hypothesis 2: Counterfactual Semantics & Anomaly Definition
- **Claude's Hypothesis:** Conditioning on `ConsumedQuantity` at time $t$ means usage-driven spikes are "explained" and NOT flagged. v1 detects cost that is unexpected *given usage* (rate anomalies), whereas users asking "why did my bill jump?" mostly mean usage jumps.
- **Verdict:** **CONFIRMED**
- **Forensic Evidence:**
  - `ConsumedQuantity` at timestamp $t$ is included unlagged in `FeaturePipeline.feature_names_` alongside lag and rolling features (`ConsumedQuantity_lag_1`, `roll_mean_24h`, etc.).
  - When `ConsumedQuantity` jumps 5x, the forecaster predicts a commensurate cost jump.
  - Consequently, the counterfactual residual $e_t = Y_t - \hat{Y}_t$ remains near zero, failing to flag the volume surge as a cost anomaly.
  - **v2 Remedy:** Implement two explicit, decoupled forecasting modes (Phase 5):
    - **Mode A (History-Expected):** Conditions purely on past cost, calendar cycles, and planned commitments (no contemporaneous usage). Flags volume surges.
    - **Mode B (Usage-Expected):** Conditions on contemporaneous usage volume. Flags rate/pricing/efficiency spikes.

---

### Hypothesis 3: Circular Attribution Evaluation
- **Claude's Hypothesis:** Candidate events are the injected events. 97.87% Top-1 largely measures "nearest same-service injected event within 6h". No decoys, confounders, multi-cause, or held-out fault families exist.
- **Verdict:** **CONFIRMED**
- **Forensic Evidence:**
  - In `src/driftsense/synth/injector.py`, event logs are generated strictly alongside injected anomaly faults (`events` list).
  - In `src/driftsense/eval/final.py` lines 410–425, `events_pool` consists of the ground-truth injected events. No decoy events (events with zero cost impact) or unannounced background events were inserted.
  - The temporal correlation attributor scores candidate events based on time distance:
    $$S(E_i) = \mathbb{I}_{(\text{service}_i = \text{service})} \cdot \exp(-\Delta t / 2.885\text{h})$$
  - In a sparse event setting where only true faults exist, the nearest same-service event is almost always the true injected fault.
  - **v2 Remedy:** Introduce calibrated scenarios with decoy events, confounders, multi-cause incidents, and leave-family-out evaluation (Phase 4 & Phase 8).

---

### Hypothesis 4: Injected Fault Magnitudes & Detection Difficulty
- **Claude's Hypothesis:** Deterministic injected faults and 0.00h delay suggest large, abrupt magnitudes. Gradual drift, small-magnitude (<10%), level-shift, and rate-change faults are not evaluated.
- **Verdict:** **CONFIRMED**
- **Forensic Evidence:**
  - Audit of executive audit narratives in `final_test_results.json` and `test_audit_narratives.md` reveals sample deviations:
    - Incident 1: Observed `$4.00` vs expected `$0.65` (+515.4% jump, ratio 6.15x).
    - Incident 2: Observed `$4.00` vs expected `$0.86` (+362.5% jump, ratio 4.65x).
    - Incident 3: Observed `$4.00` vs expected `$0.93` (+330.2% jump, ratio 4.30x).
  - These massive 4x–6x spikes are trivially separable by a 3-sigma rolling threshold detector, explaining the 0.00h delay and 95.74% event recall.
  - **v2 Remedy:** Introduce parametric fault generators drawing from continuous magnitude distributions, including subtle anomalies (<10% increase), slow linear/exponential ramps, and level shifts (Phase 4).

---

### Hypothesis 5: Alert Rate on Presumed-Normal Data vs "FPR"
- **Claude's Hypothesis:** "FPR 0.16%" is an alert rate on unlabeled data. Real data may contain true anomalies, so it is not a true false positive rate. Also depends on zero-imputation and series sparsity.
- **Verdict:** **CONFIRMED**
- **Forensic Evidence:**
  - In `src/driftsense/eval/final.py` lines 275–285, `clean_alerts` are generated by running the detector on untouched real billing data `df_test_res`.
  - The FPR is calculated as:
    ```python
    fpr_overall = float(np.mean(clean_alerts))  # 6 alerts / 3,822 hours = 0.00157 (0.16%)
    ```
  - Because real data was not manually audited or labeled by humans, any of those 6 alerts might represent actual cloud billing anomalies present in the sample data.
  - Labeling this metric as "False Positive Rate" assumes ground truth $y_{\text{true}} = 0$ for all real records.
  - **v2 Remedy:** Renaming this metric to "Alert Rate on Presumed-Normal Data" (Phase 7).

---

### Hypothesis 6: Dataset Topology, Small Sample & Continuity
- **Claude's Hypothesis:** 10,000 rows, 30 days. If `focus_sample_10000.csv` merges multiple providers or services, rows may mix periods. 3,822 test records over 6 days implies parallel series.
- **Verdict:** **CONFIRMED**
- **Forensic Evidence:**
  - `focus_sample_10000.csv` contains 10,000 raw billing entries across 27 distinct AWS services.
  - When resampled to 1-hour canonical intervals via `aggregate_to_canonical_grain()`, missing hours for each service are zero-imputed.
  - Across the 6-day test window ($D_{\text{test}}$, 144 hours), 26.54 active services on average produce:
    $$144 \text{ hours} \times 26.54 \text{ services} = 3,822 \text{ records}$$
  - The series exhibits high sparsity: zero-cost entries account for a significant fraction of hourly service slots.
  - **v2 Remedy:** Multi-dataset program evaluating continuous high-volume telemetry and multi-cloud adapters (Phase 2 & Phase 3).

---

### Hypothesis 7: Unsourced Benchmark Numbers
- **Claude's Hypothesis:** "Industry avg FPR ~5–10%" and "Unsupervised Point-F1 ~0.40" have no source citations.
- **Verdict:** **CONFIRMED**
- **Forensic Evidence:**
  - Automated scanning located occurrences of "Industry avg" and "Unsupervised" in `docs/report/01_executive_summary.md` line 25 and `docs/presentation_outline.md`.
  - These values were used as representative contextual baselines from industry whitepapers, but lack formal bibliographic DOIs or specific literature citations.
  - **v2 Remedy:** Establish a rigorous citation register (`docs/v2/citation_register.md`) with $\ge 15$ verified papers (Phase 2).
