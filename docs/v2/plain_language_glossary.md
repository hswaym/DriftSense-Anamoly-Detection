# DriftSense v2 — Plain-Language Glossary & Terminology Mapping

**Document Version:** 2.0.0  
**Status:** Approved Specification  
**Audience:** All engineers, copywriters, product designers, and automated linter validators.

---

## 1. Overview & Non-Causal Language Invariant

DriftSense v2 strictly differentiates between **statistical correlation** and **causal proof**. 

### The Non-Causal Policy:
> **Automated Rule:** No user-facing text, narrative string, notification, email summary, or frontend component shall ever state that an event *"caused"*, *"triggered"*, or *"resulted in"* a cost increase or anomaly.

All automated text generators and UI code are validated against this invariant in CI via `tests/test_non_causal_language.py`.

---

## 2. Core Terminology Mapping Table

The following table provides the mandatory translation from internal statistical concepts to external user-facing interfaces.

| Technical Term (Internal / Code) | User-Facing Term (UI & Reports) | Description & User Context |
|---|---|---|
| **Residual** | **Gap between expected and actual spend** | The dollar difference between what the baseline predicted and what was recorded on the cloud bill. |
| **Anomaly** | **Unusual spend** | A period where spending broke significantly outside expected historical or operational bounds. |
| **Z-score / Detection Threshold** | **Sensitivity setting** (Low / Balanced / High) | User-adjustable controls that determine how large a spend deviation must be before triggering an alert. |
| **SHAP Value / Local Contribution** | **What pushed spend up or down** | The relative contribution of individual factors (e.g., usage volume, time of day, active accounts) to the cost increase. |
| **Attribution Score** | **How strongly the evidence points to this reason** | A normalized confidence metric indicating temporal and contextual alignment between a spend jump and a system change. |
| **Counterfactual Forecast** | **What we expected you to spend** | The baseline projection of spend under normal operational patterns. |
| **False Positive Rate (FPR) / Precision** | **How often alerts are worth your time** | Operational alert reliability (e.g., "9 out of 10 alerts represent actionable cost drift"). |
| **Operational Event** | **Change (deployment, scaling, config)** | An observable engineering action such as a code deploy, auto-scale adjustment, or infrastructure modification. |
| **Volume-Price-Mix (VPM)** | **Spend breakdown (Usage vs. Price vs. Service Mix)** | Explaining whether a bill jumped because teams used more resources, because unit rates rose, or because usage shifted to more expensive services. |
| **Split-Conformal Prediction Interval** | **Expected spend range** | A statistically verified upper and lower boundary representing normal spending variability. |
| **Abstention Gate** | **Inconclusive evidence** | The system's intentional choice to say "we don't have enough clear evidence to highlight a specific change" rather than guessing. |
| **Contemporaneous Feature** | **Real-time measurement** | A variable measured at the exact same hour as the cost being evaluated (strictly isolated between Mode A and Mode B). |

---

## 3. Forbidden vs. Permitted Phrasing Guide

To assist copywriters and prompt engineers, the following phrasing alternatives must be followed:

### 3.1 Prohibited Phrasings (Violates Scientific Rigor)
* ❌ *"Deployment v2.4 caused your EC2 bill to double."*
* ❌ *"The auto-scaling rule triggered this $5,000 cost spike."*
* ❌ *"This anomaly resulted from unattached EBS volumes."*
* ❌ *"Root cause identified: RDS misconfiguration."*

### 3.2 Required Alternative Phrasings (Scientifically Accurate & Helpful)
*  *"Deployment v2.4 is likely associated with the EC2 spend increase (occurred 30 minutes prior)."*
*  *"The auto-scaling adjustment coincides with elevated spend."*
*  *"Evidence strongly points to unattached EBS volumes as the primary driver."*
*  *"Top correlated change: RDS configuration update (Confidence: High)."*
*  *"Unusual spend detected; no matching deployment found (Abstained on root cause)."*

---

## 4. Automated Non-Causal Linter Specification

The DriftSense automated test suite validates all generated narratives using the following regex ban-list:

```python
FORBIDDEN_CAUSAL_PATTERNS = [
    r"\bcaused\s+by\b",
    r"\bcaused\s+the\b",
    r"\bwas\s+caused\b",
    r"\btriggered\s+by\b",
    r"\btriggered\s+this\b",
    r"\bresulted\s+from\b",
    r"\bresulted\s+in\b",
    r"\broot\s+cause\s+is\b",
    r"\bdefinite\s+cause\b",
]
```

Any narrative string matching any of these expressions will fail unit testing and block deployment.
