# DriftSense v2 — Scenario Generator Design Specification

**Document Version:** 2.0.0  
**Phase:** Phase 4 (Scenario Generator v2 — Realistic Faults, Decoys, Confounders)  
**Status:** Approved Scientific Specification  

---

## 1. Executive Motivation: Beyond Naive Injections

In DriftSense v1, the forensic audit identified severe evaluation deficiencies:
1. **Hypothesis H3 (Attribution Circularity):** Candidate operational events matched the injected fault episodes 1:1, leading to an artificially inflated 97.87% Top-1 attribution score.
2. **Hypothesis H4 (Easy Detection Setting):** Faults were large, deterministic step functions ($>2\times$ spend) with zero detection delay, masking model performance on gradual drift and subtle anomalies.
3. **Hypothesis H2 (Usage Conditioning Blind Spot):** Contemporaneous usage was used to predict cost, completely blinding the system to volume runaways.

DriftSense v2 replaces naive injection with a calibrated, adversarial scenario generator modeled on real cloud architecture dynamics.

---

## 2. The 15 Calibrated Cloud Fault Families

Each fault family implements explicit physics governing whether the perturbation impacts **Usage Volume** ($Q_t$), **Effective Price** ($P_t$), or **Allocation Metadata**:

| ID | Fault Family Name | Target Dimension | Physical Mechanism | Partition Role |
|---|---|---|---|---|
| **F-01** | `usage_spike` | Volume ($Q_t$) | Sudden surge in API traffic or user transactions ($Q_t \uparrow, P_t = \text{const}$). | **Dev / Val** |
| **F-02** | `gradual_ramp_drift` | Volume or Cost | Slow linear/exponential memory or container leak over 12–48h. | **Dev / Val** |
| **F-03** | `level_shift` | Baseline Shift | Permanent upward step function in continuous spending floor. | **Holdout Reserved** |
| **F-04** | `rate_price_change` | Price ($P_t$) | Rate card surge or on-demand price shift ($P_t \uparrow, Q_t = \text{const}$). | **Dev / Val** |
| **F-05** | `new_service_appearance` | Topology Shift | Previously unobserved service suddenly begins generating spend. | **Dev / Val** |
| **F-06** | `region_migration` | Geography Shift | Spend migrates abruptly from Region A (e.g. `us-east-1`) to Region B (`eu-west-1`). | **Holdout Reserved** |
| **F-07** | `untagged_spend_growth` | Metadata Drift | Infrastructure deployed without mandatory allocation tags. | **Holdout Reserved** |
| **F-08** | `commitment_discount_expiry` | Price ($P_t$) | Reserved Instance or Savings Plan expires; effective rate reverts to On-Demand. | **Holdout Reserved** |
| **F-09** | `data_transfer_surge` | Volume ($Q_t$) | Heavy cross-AZ or cross-region network egress spike. | **Dev / Val** |
| **F-10** | `credit_refund_artifact` | Negative Cost | Accounting credit expiration or sudden adjustment artifact. | **Holdout Reserved** |
| **F-11** | `month_end_seasonality_shift` | Calendar Multiplier | Cyclic month-end financial closing batch processing. | **Dev / Val** |
| **F-12** | `autoscaling_overprovision` | Volume Floor | Flawed min-instance scaling policy preventing nighttime cooldown. | **Dev / Val** |
| **F-13** | `runaway_batch` | Volume ($Q_t$) | Un-terminated recursive worker process or zombie container loop. | **Dev / Val** |
| **F-14** | `deployment_defect` | Volume & Rate | Algorithmic regression causing high CPU consumption post-release. | **Dev / Val** |
| **F-15** | `config_change` | Rate Card ($P_t$) | Accidental resize of database instance tier or provisioned IOPS. | **Dev / Val** |

---

## 3. Mathematical Onset Profiles

To test detector sensitivity and detection delay, perturbations follow four parametric curves:

### 3.1 Abrupt Surge
$$m(t) = M \quad \forall t \in [t_{\text{start}}, t_{\text{end}}]$$

### 3.2 Gradual Linear Ramp
$$m(t) = 1.0 + (M - 1.0) \times \frac{t - t_{\text{start}} + 1}{t_{\text{end}} - t_{\text{start}} + 1}$$

### 3.3 Gradual Exponential Ramp
$$m(t) = 1.0 + (M - 1.0) \times \frac{e^{\frac{t - t_{\text{start}}}{t_{\text{end}} - t_{\text{start}}}} - 1.0}{e - 1.0}$$

### 3.4 Sustained Step Level-Shift
$$m(t) = M \quad \forall t \ge t_{\text{start}}$$

Where $M$ is the target magnitude multiplier drawn from calibrated distributions:
* **Subtle Tier:** $1.10 \le M \le 1.25$ (Low signal-to-noise ratio)
* **Moderate Tier:** $1.30 \le M \le 2.00$ (Standard operational incidents)
* **Severe Tier:** $2.50 \le M \le 5.00$ (Catastrophic architectural runaways)

---

## 4. Candidate Event Pool & Decoy Mechanics

To prevent circular attribution, candidate operational events must reflect real-world enterprise noise:

### 4.1 The $\ge 3:1$ Decoy Invariant
For every real causal event injected, the `DecoyGenerator` injects $\ge 3$ benign operational changes into the candidate pool.
* **Zero Cost Impact:** Decoys modify zero billing rows (`cost_impact = 0.0`).
* **Temporal Jitter:** Event timestamps $t_e$ are subjected to stochastic jitter:
  $$t_e = t_0 + \epsilon, \quad \epsilon \sim \text{Uniform}(-45\text{m}, +45\text{m})$$
* **Decoy Archetypes:** Routine weekly OS patching, automated canary deployments, scheduled RDS backups, clean dependency bumps.

### 4.2 Confounder Synthesis
* **Unattributed Cost Surges:** Organic viral user traffic increases spend by $1.8\times$ with **ZERO** operational events in the audit log, testing whether the attribution engine correctly abstains.
* **Silent Major Changes:** A major database partition migration occurs with **ZERO** cost variation, testing whether the engine avoids false correlation.

---

## 5. Leave-Family-Out Partitioning Schedule

To guarantee out-of-distribution evaluation validity, the 15 fault families are partitioned across splits:
1. **Development & Validation Partition (`configs/synth_dev.yaml`):** 10 families used for model training, tuning, and threshold selection.
2. **Quarantined Fresh Holdout Partition (`configs/synth_holdout.yaml`):** 5 families reserved exclusively for Phase 15 holdout evaluation.

**Strict Anti-Leakage Rule:** No model evaluated in Phase 15 will have observed the holdout-reserved families during training.
