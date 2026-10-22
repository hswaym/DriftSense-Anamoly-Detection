# DriftSense v2 — Enterprise Polish Program: Master Prompt Pack (Phase 0 → 17)

Single reference file. One phase at a time. Claude = architect/reviewer. Antigravity = implementer. Colab = research training.

---

# PART A — HOW TO USE

1. Paste **Part C (Global Preamble)** at the start of every Antigravity session.
2. Paste exactly ONE phase block from Part D.
3. Antigravity stops at the end of its phase and returns the Standard Final Report (C7).
4. Bring the report to Claude. Claude returns PASS / CONDITIONAL PASS / FAIL / BLOCKED.
5. You send `go <phase>` only after PASS (or accepted CONDITIONAL PASS).
6. `<<FILL>>` marks values Claude completes after reviewing the previous phase. Do not run a block with unfilled `<<FILL>>` fields.
7. Nothing in this file is a verified result. Dataset names, URLs, and metrics are candidates or claims-under-audit until a phase verifies them with executed evidence.

---

# PART B — ENGINEERING AUDIT OF v1 (Claude's critical read)

Source: the "Context for Claude Code" document. Every item below is a **hypothesis to test in Phase 0**, not a confirmed defect. Section 6 of that document (file structure) is empty, so repo paths are UNKNOWN.

## B1. What v1 claims (UNVERIFIED in this chat)
106 passing tests; 4-pillar pipeline; run `run_20261020_183410_6f5272`; WAPE 82.03%, Event-F1 0.9278, Top-1 attribution 97.87%, FPR 0.16%, TreeSHAP additivity.

## B2. Suspected problems (ranked by threat to credibility)

1. **Possible target leakage.** Top SHAP driver for forecasting `EffectiveCost` is `BilledCost` (48.18%). A contemporaneous, near-duplicate cost column used as a feature would inflate accuracy and contradict the stated rule that features exclude timestamp t. Test: list the exact 48 features and their timing.
2. **Counterfactual semantics are narrower than the product promise.** Conditioning on `ConsumedQuantity` at time t means usage-driven spikes are "explained" and NOT flagged. v1 detects cost that is unexpected *given usage* (rate/price/efficiency anomalies). Users asking "why did my bill jump?" mostly mean usage jumps. v2 needs two explicit modes: (a) expected given history (flags usage spikes), (b) expected given usage (flags rate anomalies), and a decomposition that separates volume from price.
3. **Circular attribution evaluation.** Candidate events are the injected events. 97.87% Top-1 largely measures "nearest same-service injected event within 6h". No decoys, confounders, multi-cause, or held-out fault families are mentioned. The reported number cannot support a real-world claim.
4. **Easy detection setting.** Deterministic injected faults and 0.00h delay suggest large, abrupt magnitudes. Gradual drift, small-magnitude, level-shift, and rate-change faults are not described.
5. **"FPR 0.16%" is an alert rate on unlabeled data.** Real data may contain true anomalies, so it is not a false positive rate. Also depends on zero-imputation and series sparsity.
6. **Forecast accuracy is modest in absolute terms.** WAPE 82% and MASE 0.786. The "47 pp lift" is against a weak baseline (WAPE 129%). Acceptable as research, misleading as a product trust claim.
7. **Test partition is spent.** D_test was evaluated once (DEC-016). Any v2 change informed by those numbers contaminates it. v2 needs a fresh, pre-registered holdout.
8. **Dataset is small and of uncertain provenance.** 10,000 rows, 30 days. The FinOps Foundation publishes an anonymized FOCUS sandbox that merges real AWS/GCP/OCI data with Microsoft toolkit sample data (per finops.org). If `focus_sample_10000.csv` derives from it, rows may mix providers and periods, which undermines continuous hourly series. Treat "real AWS hourly series" as UNVERIFIED. Also 3,822 test records over 6 days implies many parallel series; verify.
9. **Unsourced benchmark rows.** "Industry avg FPR ~5–10%" and "Unsupervised Point-F1 ~0.40" have no source. Remove or source them.
10. **Rule G3 (no in-app training) conflicts with the product goal** (companies upload data and get answers). Needs a deliberate amendment (Decision D1).
11. **FOCUS version drift.** The document says v1.0/v1.3. The FOCUS site lists provider exports mostly at v1.2, some v1.0 or v1.3, and a v1.4 spec page exists. Ingestion must handle multiple versions.
12. **106 passing tests** unverified here.

## B3. What to keep
Chronological split discipline; manifests with hashes; non-causal language validator; TreeSHAP additivity checks; zero-trust metric reporting; dual real/synthetic tracks. These are strengths. v2 builds on them.

## B4. v2 principles
- Honest metrics beat impressive metrics. Report negative results.
- The product must say "likely associated with", show confidence, and show evidence.
- A non-scientist can act on every screen. Scientific detail lives behind an "Expert details" toggle.
- No claim in the UI that the research cannot support.

---

# PART C — GLOBAL PREAMBLE (paste with every phase)

## C1. Role and truth rules
You are Antigravity, implementation agent for DriftSense v2. Claude is architect and reviewer. You do not redefine scope, skip phases, or approve your own work.
- Inspect the repo before editing. Every path you cite comes from observed evidence.
- Never claim a command passed unless you ran it and the output shows it. Never claim a dataset was acquired, a model trained, a Colab notebook run, a UI tested, or a number measured without execution evidence.
- Label every report statement VERIFIED (with evidence) or UNKNOWN.
- Never invent files, data, results, citations, DOIs.
- If ambiguous or a command is not permitted: STOP and ask.
- Work only on the authorized phase.

## C2. Git and safety
- `git status` before any change. Protect unrelated user changes.
- v1 is frozen: do not modify `runs/run_20261020_183410_6f5272/` or v1 manifests. Work on the branch named in Phase 0.
- Never reset, clean, force-push, stash, delete, or overwrite protected files without explicit authorization. No commit or push unless the phase says so.
- No credentials, tokens, private URLs, or customer data in files, notebooks, logs, screenshots, or test fixtures.
- No hardcoded machine paths.

## C3. Execution policy (amended per Decision D1, pending approval)
- **Local:** edit code; `pytest`; `ruff`; `pip install -e .` in a venv; frontend `npm`/`pnpm` build and test; `docker compose` in phases that allow it; tiny-fixture runs.
- **Colab:** all research training, large downloads, full-data EDA, full experiments, ablations, final evaluation. You write the code and notebook; you do NOT run them or claim they ran. Report `AWAITING COLAB RUN` and stop.
- **Product runtime (Phases 11+):** inference and light CPU-only per-tenant fitting inside the backend worker is permitted with a hard time budget. Heavy or research training remains Colab-only.
- Never silently switch device or method. Fail loudly.

## C4. Colab notebook standard
Notebooks are generated by `scripts/build_notebooks.py` from templates, never hand-edited, and contain no logic (they call the `driftsense` CLI).
Cell order: (1) setup: clone repo at pinned SHA, `pip install -e .` plus pinned `requirements-colab.txt`, secrets only from Colab Secrets; (2) `driftsense hwcheck`, error if requested device absent; (3) mount Drive, create `<DRIVE_ROOT>/driftsense_v2/runs/<run_id>/`; (4) data validation, abort on failure; (5) run stage with `--config --seed --resume`; (6) evaluation; (7) export artifacts and `manifest.json`, print sha256s.
Header states runtime type, estimated runtime, RAM, disk, expected outputs. Cells are rerun-safe.

## C5. Manifest schema (`manifest.json`)
`run_id, phase, stage, git_commit, git_dirty, config_path, config_sha256, protocol_sha256, seed, python, packages{}, hardware{cpu,gpu,ram_gb}, dataset_ids[], dataset_sha256{}, started_utc, finished_utc, artifacts[{path,sha256,bytes}], metrics_files[], split_roles{train,val,holdout}, holdout_touched(bool)`.
`driftsense verify-manifest <dir>` recomputes all hashes; must exit 0.

## C6. Mandatory leakage and validation rules
- Split chronologically before fitting any transform, encoder, scaler, or learned feature. Fit on train only.
- Rolling windows exclude the current row unless it is the prediction target; windows are documented.
- Any feature observed at time t (contemporaneous) must be labelled `known_at_prediction_time: yes/no` in the feature contract. Cost-derived contemporaneous columns (e.g. `BilledCost` when predicting `EffectiveCost`) are forbidden as features unless Claude explicitly approves with justification.
- Labels live in a separate table; never model inputs.
- Tune thresholds and select models on validation only. The v2 holdout is touched once, in Phase 15.
- Real and synthetic tracks reported separately and labelled.
- Correlation, importance, SHAP are never described as causal proof. The non-causal validator applies to ALL user-facing strings (backend narratives and frontend copy).

## C7. Standard Final Report
1. Phase ID; status COMPLETE / BLOCKED / AWAITING COLAB RUN
2. Summary of changes
3. Exact files created / modified / deleted
4. Exact commands run, exit codes, relevant output
5. Tests run and results
6. Dataset or artifact changes with sha256
7. Acceptance criteria, each PASS/FAIL with evidence
8. Known defects and risks
9. UNKNOWNs
10. Evidence needed from the user
11. Proposed next phase (do NOT start it)
Then stop.

## C8. Standing forbidden actions (every phase)
Editing v1 frozen artifacts; touching the v2 holdout before Phase 15; fabricating results; copying customer data into the repo; weakening a test to make it pass; disabling the leakage or non-causal validators; commits/pushes without authorization.

## C9. Standing stop conditions
Missing required input; a needed command not permitted; a test requires modifying frozen artifacts; a licence blocks use; a Colab result is needed to proceed.

---

# PART D — PHASES

Phase index:
0 Baseline freeze and forensic audit
1 Product and research specification v2
2 Dataset program (verify and select)
3 Data layer v2 (ingestion, schema mapping, quality score)
4 Scenario generator v2 (realistic faults, decoys, confounders)
5 Feature and leakage re-engineering
6 Forecasting v2 (intervals, grains)
7 Detection v2 (alerts, materiality, benchmarks)
8 Attribution v2 (driver decomposition, events, abstention)
9 Explainability and trust layer
10 Experiments and ablations (locked protocol)
11 Backend service (API, tenants, jobs, security)
12 Product UI for non-scientists
13 Feedback loop and monitoring
14 Security, performance, accessibility QA
15 Final locked evaluation (fresh holdout)
16 Documentation, report, demo
17 Final audit and release

---

## PHASE 0 — BASELINE FREEZE AND FORENSIC AUDIT — READY

**Repo path:** `<<USER_FILLS_IN_REPO_PATH>>`

**Objective:** establish verified repo state, reproduce v1, and test every hypothesis in B2. Protect v1.

**Steps**
1. Report OS, shell, Python, Node (if present), git version, repo path.
2. Git: `git status`, `git branch -a`, `git log --oneline -n 30`, `git remote -v`. Report dirty files.
3. Full tree (depth 4, ignore `.git`, `node_modules`, `__pycache__`, `.venv`). Sizes of files >1 MB.
4. Inventory: `pyproject.toml`, requirements, `configs/`, `src/`, `app/`, `tests/`, `notebooks/`, `runs/`, `docs/`, `data/`. Every module: path, lines, public API, imports, TODOs, hardcoded paths.
5. Run `pytest` and `ruff check` locally (if approved). Paste pass/fail counts and exit codes. State whether 106 tests passed.
6. Locate run `run_20261020_183410_6f5272`. Run the verify-manifest equivalent (or recompute hashes) and report mismatches.
7. **Hypothesis tests (read-only analysis scripts under `docs/audit/scripts/`, no change to src):**
   - H1: print the exact 48 features; flag any cost-derived contemporaneous column (`BilledCost`, etc.) and any column observed at t; report the SHAP table source.
   - H2: confirm the forecast target and whether `ConsumedQuantity` at t is a feature; describe in plain words what "anomaly" means in v1.
   - H3: list how candidate events are generated for attribution; state whether non-injected (decoy) events exist; count events per type in D_test.
   - H4: injected fault magnitudes (min/median/max multiple of expected cost) and durations.
   - H5: how "clean track" is determined; how many hourly series exist; fraction of zero-imputed hours; how 3,822 test records arise.
   - H6: dataset row counts per `ProviderName`, `BillingPeriodStart`, `ServiceName`; number of distinct `ChargePeriodStart` days; continuity per series.
   - H7: where "industry avg" and "unsupervised ~0.40" numbers originate in code or docs.
8. Colab-readiness and secret scan (paths only, never contents).

**Create:** `docs/audit/v1_forensic_audit.md` (each hypothesis: CONFIRMED / REFUTED / INCONCLUSIVE with evidence), `docs/audit/repo_inventory.md`, `docs/audit/risk_register.md`, `docs/audit/scripts/*.py`.

**Permitted commands:** read-only git; `ls/tree/cat/head/wc/find`; `python --version`; `pip list`; `pytest`; `ruff check`; running the audit scripts on existing local data. **User must approve** `pip install -e .` if the venv is not ready.

**Forbidden:** modifying `src/`, `app/`, `tests/`, `configs/`; touching `runs/`; downloads; commits.

**Acceptance criteria**
- A0.1 Environment and git state reported with command evidence.
- A0.2 `pytest`/`ruff` results pasted.
- A0.3 Manifest hash check result reported.
- A0.4 H1–H7 each have a verdict with evidence.
- A0.5 `git status` shows only new files under `docs/audit/`.
- A0.6 Recommended branch name for v2 work (default `v2-enterprise`), NOT created.

---

## PHASE 1 — PRODUCT AND RESEARCH SPECIFICATION v2 — TEMPLATE

**Preconditions:** Phase 0 PASS. `<<FILL: audit verdicts H1–H7>>`.

**Objective:** binding v2 specification. Docs only.

**Create:**
- `docs/v2/product_requirements.md`: personas (FinOps analyst, engineering manager, finance/CFO, platform engineer), jobs-to-be-done, user stories with acceptance tests, success metrics (time-to-first-insight, % alerts acted on, alert volume per week).
- `docs/v2/research_spec.md`: revised problem statement, two forecasting modes (history-expected vs usage-expected), volume/price/mix decomposition definition, anomaly definition independent of models, cause taxonomy v2, metrics, claims each track supports.
- `docs/v2/evaluation_protocol.md`: dev/val/holdout roles, fresh holdout rule (holdout never seen in v1 or Phases 0–14), pre-registered hypotheses, metrics and statistical tests, bootstrap CIs, seeds, stop criteria. Protocol hash recorded.
- `docs/v2/data_contracts.md`: canonical schema (FOCUS-based) plus provider adapters, event schema, label schema, tenant/data-retention model.
- `docs/v2/ux_principles.md` and `docs/v2/plain_language_glossary.md` (see Glossary below).
- `docs/v2/decision_log.md` (D1–D8 with outcomes), `docs/v2/traceability_matrix.md`, `docs/v2/threat_model_outline.md`.

**Plain-language glossary (minimum mapping):**
| Technical | User-facing |
|---|---|
| Residual | Gap between expected and actual spend |
| Anomaly | Unusual spend |
| Z-score / threshold | Sensitivity setting (Low / Balanced / High) |
| SHAP value | What pushed spend up or down |
| Attribution score | How strongly the evidence points to this reason |
| Counterfactual forecast | What we expected you to spend |
| FPR / precision | How often alerts are worth your time |
| Event | Change (deployment, scaling, config) |
Rule: no UI string uses "caused by", "triggered by", "resulted from".

**Requirements:** every v1 B2 finding maps to a v2 design decision or an explicit open item. Decisions D1–D8 are recorded with the user's answers; unanswered ones remain OPEN.

**Acceptance:** A1.1 all documents exist; A1.2 each B2 item traced; A1.3 protocol complete and hashed; A1.4 only `docs/v2/` changed.

**Forbidden:** code changes; inventing decisions the user has not made.

---

## PHASE 2 — DATASET PROGRAM — TEMPLATE

**Preconditions:** Phase 1 PASS. Web access required; if unavailable, BLOCKED.

**Objective:** verify and select a dataset **suite** (no single "perfect" dataset exists). Documentation and tiny samples only.

**Suite roles:**
- **S1 Real billing (FOCUS):** FinOps Foundation FOCUS sandbox/sample data (anonymized real AWS/GCP/OCI plus Microsoft toolkit sample, per finops.org). Verify license, size, schema, version, billing periods, whether series are continuous.
- **S2 Provider-format samples:** AWS CUR / Data Exports, Azure cost export, GCP billing export sample files, FOCUS converters (verify).
- **S3 Real workload telemetry:** Azure public datasets (VM traces, Functions), Google cluster traces, Alibaba cluster traces, Bitbrains (all UNVERIFIED candidates). Purpose: realistic usage patterns.
- **S4 Semi-synthetic cost-from-usage:** price real telemetry using public provider price lists to produce realistic billing with known usage. Verify price-list licence and reproducibility.
- **S5 Anomaly benchmarks:** NAB, TSB-UAD, SMD, others verified in-phase. Purpose: validate detectors independent of our own injector.
- **S6 Root-cause benchmarks:** microservice fault-injection datasets with root-cause labels (e.g. RCAEval-style). Verify.
- **S7 Own synthetic scenarios** from Phase 4.

**Create:** `docs/v2/dataset_decision_report.md` (per candidate: official name/URL, publisher, licence, download method, format and schema, rows/columns/time coverage/frequency, cost/usage/telemetry/event fields, missing fields, anomaly labels, root-cause labels, real/transformed/simulated/synthetic, size, reproducible acquisition steps, verification evidence with fetch date, decision and reason); `docs/v2/citation_register.md` (≥15 verified papers: FinOps, cloud cost forecasting, time-series anomaly detection incl. evaluation pitfalls, AIOps/RCA, conformal prediction, XAI, FOCUS); `docs/v2/data_dictionary_draft.md`; `docs/v2/holdout_plan.md` (which sources/periods/seeds form the untouched holdout).

**Acceptance:** A2.1 every candidate has all fields or UNKNOWN; A2.2 selected sources have licence, schema, acquisition steps; A2.3 ≥15 papers verified or marked UNVERIFIED and excluded; A2.4 holdout plan disjoint from dev/val sources; A2.5 claims each source supports stated; A2.6 no downloads beyond licence-permitted small samples.

**Stop:** if no acceptable real cost source exists beyond the v1 sample, report the blocker and the fallback (S4 plus S7 with explicit limitations).

---

## PHASE 3 — DATA LAYER v2 — TEMPLATE

**Preconditions:** Phase 2 PASS. `<<FILL: selected sources, schemas, licences>>`.

**Objective:** robust ingestion for arbitrary company uploads and research datasets.

**Create / modify (adjust to Phase 0 inventory):**
- `src/driftsense/ingest/{detect_format,adapters_focus,adapters_aws_cur,adapters_azure,adapters_gcp,mapping,canonical}.py`
- `src/driftsense/quality/{validators,score,report}.py`
- `src/driftsense/data/{acquire,chunked_io}.py`
- CLI: `driftsense ingest`, `driftsense quality`, `driftsense verify-manifest`, `driftsense hwcheck`
- `configs/ingest_*.yaml`, `docs/v2/data_dictionary.md`, tests with ≤100-row fixtures per provider, notebook template `01_acquire_validate`.

**Requirements**
- Auto-detect provider and FOCUS version (1.0–1.3+); unknown columns routed to a **mapping suggestion** (column → canonical field with confidence), never silently dropped.
- Canonical fields minimum: charge period start/end (UTC), service, sub-account, region, resource id (optional), usage quantity and unit, billed cost, effective cost, list/contracted cost if present, charge category, tags (parsed), currency.
- Currency: single-currency enforced; multi-currency flagged.
- **Data quality score (0–100) with plain-language reasons** (missing days, duplicate rows, negative adjustments, untagged share, timestamp gaps, unit conflicts) and actionable fixes.
- Chunked reads for files up to `<<FILL: e.g. 1M rows>>` within a memory budget; encoding/delimiter detection; size and row limits enforced with clear errors.
- Refund/credit handling, deduplication keys, zero-imputation policy documented and toggled by config; imputed counts reported.
- No customer data in fixtures.

**Permitted:** `pytest`, `ruff`, notebook generation, fixtures. **Forbidden:** full downloads locally.

**Acceptance:** A3.1 adapter tests per provider pass; A3.2 malformed-file tests (bad encoding, mixed timezones, missing columns, duplicate headers) produce clear errors; A3.3 quality score unit tests with hand-computed cases; A3.4 deterministic notebook build; A3.5 **Colab run** on selected sources, manifest verified. Status `AWAITING COLAB RUN` (notebook `01_acquire_validate`).

---

## PHASE 4 — SCENARIO GENERATOR v2 — TEMPLATE

**Preconditions:** Phase 3 PASS.

**Objective:** replace easy deterministic injection with calibrated, adversarial scenarios.

**Create / modify:** `src/driftsense/synth/{calibrate,scenarios,injector,decoys,confounders,labels}.py`, `configs/synth_*.yaml`, `docs/v2/generator_design.md`, tests, notebook `02_synth`.

**Fault families (each with parametric magnitude, duration, onset shape):** usage spike; gradual ramp/drift; level shift; rate/price change; new service appearance; region migration; untagged spend growth; commitment/discount expiry; data-transfer surge; credit/refund artifact; month-end/seasonality shift; autoscaling over-provision; runaway batch; deployment defect; config change.

**Requirements**
- Calibrate noise, seasonality, and sparsity from real sources (S1/S3/S4); record calibration stats in the manifest.
- Magnitudes drawn from distributions including small (<10% of expected), moderate, large. Onsets include abrupt and gradual.
- **Decoy events** (no cost effect), **confounders** (usage up without any event; event without cost change), **multi-cause** anomalies, **unknown-cause** anomalies, benign planned changes.
- Event timestamps carry jitter and missing-event rates.
- Label table separate from features; every row `is_synthetic=true` with scenario id, fault family, true cause list, onset, offset, magnitude.
- Fault families partitioned: some reserved for validation, others reserved ONLY for the holdout (leave-family-out).
- Seeded and versioned; regenerable in Colab.

**Acceptance:** A4.1 injector tests: onset, magnitude, duration match config; A4.2 decoy/confounder tests: decoys have zero injected effect; A4.3 label isolation test; A4.4 holdout-reserved families never appear in dev configs (test); A4.5 **Colab run** manifest verified. Status `AWAITING COLAB RUN`.

---

## PHASE 5 — FEATURE AND LEAKAGE RE-ENGINEERING — TEMPLATE

**Preconditions:** Phases 0 and 4 PASS. `<<FILL: H1/H2 verdicts, grain decision>>`.

**Objective:** a leak-free feature contract supporting two forecasting modes.

**Create / modify:** `src/driftsense/features/{calendar,autoregressive,usage,events,hierarchy,builder}.py`, `docs/v2/feature_contract.md` (name, formula, window, includes-current-row, `known_at_prediction_time`, source, mode A/B), tests.

**Requirements**
- **Mode A (history-expected):** autoregressive cost, calendar, known planned events/commitments. No contemporaneous usage. Flags usage-driven spikes.
- **Mode B (usage-expected):** adds contemporaneous usage with explicit documentation that it detects rate/efficiency anomalies.
- Remove contemporaneous cost-derived columns (per C6) unless Claude approves.
- Grains: hourly and daily; per service, per sub-account, total. Hierarchy keys for reconciliation.
- Calendar: hour, weekday, month-end, billing-cycle day, holidays optional.
- Explicit handling of sparse/zero-inflated series.

**Mandatory tests:** perturbation (future data changes do not alter past features); fit-on-train-only; label isolation; event timing; split ordering; feature-contract completeness (every produced column is documented); forbidden-column test.

**Acceptance:** A5.1 all leakage tests pass with pasted output; A5.2 contract covers 100% of features; A5.3 **Colab run** builds features on full data; row counts reconcile with Phase 3. Status `AWAITING COLAB RUN`.

---

## PHASE 6 — FORECASTING v2 — TEMPLATE

**Preconditions:** Phase 5 PASS.

**Objective:** accurate expected-cost forecasts with calibrated uncertainty.

**Create / modify:** `src/driftsense/forecast/{baselines,ets,sarima,boosted,quantile,conformal,reconcile}.py`, `src/driftsense/eval/forecast_metrics.py`, configs, tests, notebook `04_forecast`.

**Requirements**
- Models: seasonal-naive, moving average, ETS, SARIMA (only where seasonality evidence supports), gradient-boosted trees (XGBoost/LightGBM) with count/zero-inflated-appropriate objective (e.g. Tweedie), optional global model across series. LSTM only if Claude approves `<<FILL>>`.
- **Prediction intervals** by quantile regression and/or split-conformal calibrated on validation. Report empirical coverage versus nominal.
- Metrics: MAE, RMSE, WAPE, sMAPE, MASE, pinball loss, interval coverage and width; MAPE only where actuals ≠ 0, with explicit zero handling.
- Rolling-origin evaluation on validation; per-service breakdown; sparse-series analysis.
- Select models on validation only. **No holdout predictions.** Save models with config hash.

**Acceptance:** A6.1 metric tests with hand-computed cases incl. zeros; A6.2 interface tests; A6.3 coverage test on synthetic data with known noise; A6.4 **Colab run** validation tables, coverage plots, manifest verified; A6.5 manifest `holdout_touched=false`. Status `AWAITING COLAB RUN`.

---

## PHASE 7 — DETECTION v2 — TEMPLATE

**Preconditions:** Phase 6 PASS. `<<FILL: selected forecasters>>`.

**Objective:** fewer, better alerts with business materiality.

**Create / modify:** `src/driftsense/detect/{interval,zscore,rolling,iforest,changepoint,persistence,materiality,severity}.py`, `src/driftsense/eval/detection_metrics.py`, configs, tests, notebook `05_detect`.

**Requirements**
- Primary detector: **forecast-interval exceedance** (conformal band) with persistence rule (e.g. k of n periods) and **materiality filter** (minimum dollars and minimum percent of expected, configurable).
- Baselines: static threshold, Z-score, rolling threshold (v1 champion), Isolation Forest, One-Class SVM. Level-shift detector (change-point) for sustained shifts.
- **Severity score** = f(dollar impact, duration, persistence, confidence). Output severity label: Info / Low / Medium / High.
- **Sensitivity presets** (Low / Balanced / High) mapped to documented parameters.
- Metrics: point and event precision/recall/F1, PR-AUC, detection delay, **alerts per week** and alerts per $1k of spend, false alarms on clean/seasonal periods (reported as "alert rate on presumed-normal data", NOT as FPR unless labelled).
- Run detectors on external benchmarks (S5) to validate beyond own injector; report separately.
- Thresholds tuned on validation only.

**Acceptance:** A7.1 metric tests with hand-computed event/delay cases; A7.2 materiality/persistence unit tests; A7.3 **Colab run** validation tables (own synthetic, S5 benchmarks, real presumed-normal), manifest verified; A7.4 holdout untouched. Status `AWAITING COLAB RUN`.

---

## PHASE 8 — ATTRIBUTION v2 — TEMPLATE

**Preconditions:** Phase 7 PASS. `<<FILL: taxonomy, event availability policy>>`.

**Objective:** useful reasons even when the company uploads billing only.

**Create / modify:** `src/driftsense/attribute/{decompose,price_volume_mix,dimension_rank,events_kernel,ranker,abstain,evidence}.py`, `src/driftsense/eval/attribution_metrics.py`, configs, tests, notebook `06_attribute`.

**Layers**
1. **Driver decomposition (always available):** split the cost gap by service, sub-account, region, usage type, tag using an additive method (e.g. contribution ranking with Shapley or Adtributor-style surprise). Separate **volume**, **rate/price**, and **mix** effects: ΔCost = Δquantity×base rate + Δrate×new quantity (+ mix), with the identity checked numerically.
2. **Event evidence (optional upload):** proximity decay kernel over deployments/scaling/config events; service-matched; half-life configurable.
3. **Learned ranker (optional):** gradient-boosted ranker over layer 1+2 evidence, trained on synthetic labels only.
4. **Abstention:** output "Not enough evidence" when top evidence is weak or ambiguous. Calibrated confidence (reliability curve) mapped to High / Medium / Low labels.
5. **Evidence objects:** each reason lists supporting data points (service, dollar share, time overlap).

**Evaluation:** baselines random, class-prior, single-dimension largest-share, kernel-only, full. Metrics Top-1, Top-3, MRR, per-class F1, abstention precision/coverage, calibration error. Scenarios include decoys, confounders, multi-cause, unknown, held-out fault families. External RCA benchmark (S6) reported separately. State plainly that synthetic ground truth is not production ground truth.

**Acceptance:** A8.1 decomposition identity test (parts sum to total within tolerance); A8.2 metric tests; A8.3 abstention test on pure-noise cases; A8.4 label-isolation test; A8.5 **Colab run** validation tables, confusion matrices, calibration plots, manifest verified. Status `AWAITING COLAB RUN`.

---

## PHASE 9 — EXPLAINABILITY AND TRUST LAYER — TEMPLATE

**Preconditions:** Phase 8 PASS.

**Objective:** explanations a finance manager can read and an engineer can audit.

**Create / modify:** `src/driftsense/explain/{shap_layer,plain_language,narrative_templates,confidence,validator,faithfulness}.py`, tests, notebook `07_explain`.

**Requirements**
- Keep TreeSHAP additivity checks; move SHAP behind "Expert details".
- **Plain-language narrative** per anomaly: what happened (dollar and percent versus expected), where (top contributing service/account/region), when, likely reasons with confidence label, suggested next checks (generic, non-prescriptive), what we are not sure about.
- Narrative templates versioned; extended non-causal validator applied to every template and rendered output; test greps for forbidden verbs ("caused by", "triggered by", "resulted from", "due to" when asserting certainty).
- Confidence labels derived from calibrated scores, never from raw SHAP.
- Faithfulness checks: narrative numbers equal underlying artifact numbers (automated); stability of top drivers across seeds.
- Every explanation record has `prediction_id`, model id, evidence refs.

**Acceptance:** A9.1 additivity test; A9.2 narrative-number consistency test; A9.3 validator test over all templates; A9.4 readability check (documented rule, e.g. no unexplained technical term from the glossary list in the default view); A9.5 **Colab run** (stability tables) manifest verified. Status `AWAITING COLAB RUN`.

---

## PHASE 10 — EXPERIMENTS AND ABLATIONS (LOCKED PROTOCOL) — TEMPLATE

**Preconditions:** Phases 6–9 PASS. Protocol frozen: `<<FILL: protocol hash>>`.

**Objective:** comparable, variance-aware evidence on validation data.

**Create / modify:** `src/driftsense/eval/ablation.py`, configs, tests, notebook `08_ablation`.

**Arms:** cost-only; +usage; +events; Mode A vs Mode B; baselines vs advanced; interval vs rolling threshold; with/without materiality filter; attribution layers 1 / 1+2 / 1+2+3; leave-fault-family-out; cross-dataset generalization (train on source X, evaluate on source Y); robustness to missing data, noise, and event-log gaps; sensitivity presets.

**Requirements:** identical windows and metrics across arms; ≥`<<FILL: 10>>` seeds; mean ± std and bootstrap CIs; paired tests where appropriate; real and synthetic tables separate; documented caveat that event features on synthetic data are partially circular and that decoy/confounder arms are the fair test.

**Acceptance:** A10.1 arms share identical splits (test); A10.2 protocol hash in every manifest; A10.3 **Colab run** tables/plots with variance, manifest verified; A10.4 holdout untouched. Status `AWAITING COLAB RUN`.

---

## PHASE 11 — BACKEND SERVICE — TEMPLATE

**Preconditions:** Phases 3–9 PASS; Decisions D1, D2, D7 answered. `<<FILL: stack decision>>`.

**Objective:** multi-tenant API that runs the pipeline on uploaded data.

**Default stack (change only per D2):** FastAPI, Pydantic, Postgres (metadata) plus Parquet on object storage (data), background worker (RQ/Celery or equivalent), Docker Compose.

**Create / modify:** `services/api/…`, `services/worker/…`, `src/driftsense/runtime/inference.py` (loads exported models; per-tenant CPU-only light fit with time budget), OpenAPI spec, `docker-compose.yml`, `.env.example`, tests.

**Endpoints (minimum):** `POST /uploads` (chunked, size-limited), `GET /uploads/{id}/mapping` and `PUT` (confirm column mapping), `GET /uploads/{id}/quality`, `POST /analyses`, `GET /analyses/{id}` (status/progress), `GET /analyses/{id}/overview`, `/anomalies`, `/anomalies/{id}` (detail, evidence, narrative), `POST /anomalies/{id}/feedback`, `POST /events` (optional change events CSV/webhook), `GET /reports/{id}.pdf|csv`, `DELETE /uploads/{id}` (hard delete).

**Requirements**
- Auth: JWT/OIDC-ready; local dev mode with seeded demo user, never default credentials in production config.
- Tenant isolation: every query scoped by tenant id; isolation tests.
- Upload safety: extension and magic-byte checks, size/row limits, CSV-injection-safe exports, decompression-bomb guard, no execution of uploaded content.
- Privacy: encryption at rest where supported, configurable retention, account-id masking option, audit log, delete-on-request, no customer data in logs.
- Jobs: idempotent, resumable, progress reporting, per-job time and memory budget, clear failure messages in plain language.
- Reproducibility: every analysis stores model version, config hash, data hash, protocol version.
- The API never trains research-grade models; it loads exported artifacts.

**Acceptance:** A11.1 `pytest` including tenant-isolation and malicious-upload tests; A11.2 OpenAPI generated; A11.3 `docker compose up` end-to-end on a fixture upload (log evidence); A11.4 no secrets in repo; A11.5 analysis on a 100k-row fixture completes within `<<FILL: budget>>` (timing evidence).

---

## PHASE 12 — PRODUCT UI FOR NON-SCIENTISTS — TEMPLATE

**Preconditions:** Phase 11 PASS. `<<FILL: UI stack, brand name/colors if any>>`.

**Objective:** a UI an engineering manager or finance lead trusts and uses without data-science knowledge.

**Default stack:** Next.js (React + TypeScript), Tailwind, a charting library with accessible defaults, Playwright for E2E. Streamlit app stays as a frozen "research console".

**Information architecture and screens**
1. **Welcome:** one sentence value proposition; "Try with sample data" and "Upload your bill".
2. **Upload wizard (3 steps):** drop file → we detect provider/format → confirm column mapping with plain-language labels → **data health score** with fixable issues ("12 days have no data"). Optional step: add change events.
3. **Overview:** this period's spend vs what we expected, dollars at risk, number of unusual-spend alerts by severity, top services moving, "What needs attention first".
4. **Alerts inbox:** list sorted by dollar impact; severity chips; status (New / Investigating / Expected / Resolved); filters (service, account, region, severity, date); bulk actions.
5. **Alert detail:** headline in one sentence; chart of actual vs expected band with the unusual period highlighted; "Where it happened" (top contributors); "Likely reasons" with High/Medium/Low confidence and the evidence behind each; "What to check next"; "How sure are we?" panel; feedback buttons (This was useful / Not an issue / It was planned) with optional note.
6. **Explore:** drill by service/account/region/tag with plain tooltips.
7. **Reports:** download PDF/CSV; weekly digest settings (email/Slack webhook).
8. **Settings:** sensitivity (Low/Balanced/High), minimum dollar materiality, budgets, data retention, delete my data.
9. **Expert details toggle:** reveals expected-given-usage vs history mode, residual plots, SHAP charts, model/version/config hashes, metrics versus benchmark. Off by default.
10. **Help and trust page:** how it works in plain words, what it can and cannot tell you, validation summary with honest numbers and limitations, data handling policy.

**Requirements**
- Copy follows the glossary and non-causal rules; a build-time test scans all UI strings for forbidden phrasing.
- Never display a metric the research does not support; benchmark claims link to the verified results page.
- Empty, loading, error, partial-data, and "not enough evidence" states for every screen.
- Responsive; WCAG 2.1 AA contrast, keyboard navigation, screen-reader labels, non-color-only status.
- Charts: readable axis labels in dollars, units, time zone shown; timestamps in UTC with a local toggle.
- Performance: first meaningful paint and chart rendering budgets `<<FILL>>`; large tables virtualized.
- Demo mode loads a bundled sample dataset with a clear "sample data" banner.

**Acceptance:** A12.1 unit and component tests pass; A12.2 Playwright E2E: upload → mapping → analysis → alert detail → feedback; A12.3 forbidden-phrase scan passes; A12.4 accessibility audit tool report (e.g. axe) with zero critical issues; A12.5 screenshots or recordings supplied by the user for visual review; A12.6 UI shows only values returned by the API (contract test).

---

## PHASE 13 — FEEDBACK LOOP AND MONITORING — TEMPLATE

**Preconditions:** Phase 12 PASS.

**Objective:** learn from user feedback safely; detect model decay.

**Create / modify:** feedback store and schema, `src/driftsense/monitor/{data_drift,alert_volume,feedback_metrics}.py`, admin page, tests, notebook `09_feedback_eval` (offline re-evaluation).

**Requirements**
- Feedback becomes a labelled dataset (`useful / not issue / planned`) kept separate from synthetic labels.
- Metrics: alert usefulness rate, dismissal rate by severity, time-to-acknowledge.
- Drift monitors: schema drift, volume drift, alert-volume spikes; plain-language admin warnings.
- **No automatic online retraining.** Retraining is an explicit Colab workflow with a model-card update and validation gate.
- Model cards and version registry (`models/registry.json` with hashes).

**Acceptance:** A13.1 feedback API tests; A13.2 drift monitor tests with synthetic drift; A13.3 registry integrity test; A13.4 no code path retrains in production without an explicit flag.

---

## PHASE 14 — SECURITY, PERFORMANCE, ACCESSIBILITY QA — TEMPLATE

**Preconditions:** Phases 11–13 PASS.

**Objective:** enterprise readiness checks with evidence.

**Tasks / create:** `docs/v2/threat_model.md` (STRIDE-style), dependency vulnerability scan (`pip-audit`, `npm audit`; report only, do not auto-upgrade), secret scan, SAST (e.g. bandit/semgrep if approved), tenant-isolation fuzz tests, upload-abuse tests, rate limiting, security headers, load test (documented tool) on 1M-row fixture, memory profile, backup/restore note, `docs/v2/ops_runbook.md`, Docker image build, clean-checkout install.

**Acceptance:** A14.1 scan outputs attached with triaged findings; A14.2 zero critical unresolved findings or explicit accepted-risk entries; A14.3 load-test numbers recorded with hardware description; A14.4 clean-checkout `pytest` + frontend tests + `docker compose up` all exit 0; A14.5 accessibility report attached.

---

## PHASE 15 — FINAL LOCKED EVALUATION (FRESH HOLDOUT) — TEMPLATE

**Preconditions:** Phase 14 PASS. Frozen config and model hashes: `<<FILL>>`. Holdout sources/seeds per `docs/v2/holdout_plan.md` never used before.

**Objective:** one-time evaluation of v2.

**Create:** notebook `10_final_eval`, `src/driftsense/eval/final.py`, `docs/v2/final_results_protocol.md`.

**Requirements**
- Notebook aborts if any config, model, or protocol hash differs from frozen values.
- Holdout evaluated exactly once; manifest `holdout_touched=true` marker; a rerun needs explicit user override and is logged as a deviation.
- Report all pre-registered metrics, including negative results, with bootstrap CIs. Separate tables: real billing (forecast/detect only), external benchmarks, synthetic attribution, cross-dataset, and v1 vs v2 comparison (v1 numbers labelled "development-contaminated").
- No post-hoc tuning.

**Acceptance:** A15.1 hash guard test passes locally; A15.2 **Colab run** results and manifest verified; A15.3 no code or model changes between Phase 14 and 15 (hash evidence). Status `AWAITING COLAB RUN`.

---

## PHASE 16 — DOCUMENTATION, REPORT, DEMO — TEMPLATE

**Preconditions:** Phase 15 PASS.

**Create:** research report (introduction, verified literature review, methodology, datasets and provenance, experiments, results, explainability, limitations, ethics/licensing, reproducibility, conclusion); `docs/v2/results_trace.md` (every number → artifact → manifest → sha256); user guide with screenshots supplied by the user; admin/deploy guide; API reference; model cards; demo script (5-minute narrative using sample data); presentation outline; FAQ ("Can I trust this?", "What data do you keep?", "What can't it tell me?").

**Requirements:** no number without a trace entry; no UI or marketing claim beyond Phase 15 evidence; contribution framed as an evaluated pipeline and decomposition/abstention design, not novelty of individual techniques; state that synthetic labels are not production ground truth.

**Acceptance:** A16.1 every number traced; A16.2 every citation verified; A16.3 limitations cover synthetic circularity, small real data, provider generalization, correlation vs causation; A16.4 documented steps reproduce from a clean checkout.

---

## PHASE 17 — FINAL AUDIT AND RELEASE — TEMPLATE

**Preconditions:** Phase 16 PASS.

**Tasks:** re-run `pytest`, `ruff`, frontend tests, E2E; verify all manifests; walk the traceability matrix (every row has file, test, evidence, status); repository cleanliness; confirm no secrets or oversized files tracked; produce `docs/v2/release_checklist.md`; **do not commit or tag unless explicitly authorized in this phase**.

**Final success criteria (each needs evidence pointer or an explicit open gap):** provenance documented; ingestion handles multi-provider uploads; leakage controls tested; forecasting with calibrated intervals; detection with materiality and benchmark validation; attribution with abstention and decoy/held-out evaluation; plain-language explanations validated; ablations with variance; fresh-holdout evaluation once; real vs synthetic separated; multi-tenant secure backend; accessible non-scientist UI; feedback loop governed; limitations documented; reproducible by another person.

---

# PART E — OPEN DECISIONS (answer before the phase that needs them)

- **D1 (before Phase 1):** Amend rule G3 to allow product-runtime inference and light CPU-only per-tenant fitting, keeping research training in Colab? Default: YES.
- **D2 (before Phase 11):** Frontend/backend stack. Default: Next.js + FastAPI, Streamlit frozen as research console. Alternative: polish Streamlit (faster, weaker for multi-user auth, upload UX, and enterprise trust).
- **D3:** Deployment target (local Docker Compose only, or a named cloud).
- **D4 (before Phase 2):** Any real, consenting company or personal cloud-billing data available for validation? Default: none.
- **D5:** Provider scope at launch. Default: FOCUS plus AWS CUR, Azure cost export, GCP billing export.
- **D6 (before Phase 2):** Fresh holdout strategy. Default: new sources and new generator seeds, never used in development.
- **D7:** Authentication. Default: OIDC-ready JWT, demo user in dev mode.
- **D8:** Deadline, team size, and primary audience (academic evaluators, customers, or both). Controls how much of Phases 11–14 is built versus specified.
