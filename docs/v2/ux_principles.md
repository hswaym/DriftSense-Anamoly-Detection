# DriftSense v2 — User Experience (UX) Principles & Design System

**Document Version:** 2.0.0  
**Status:** Approved Design Specification  
**Audience:** Product Managers, Frontend Engineers, Designers, and Evaluators.

---

## 1. Executive Vision: Actionable Clarity for Non-Scientists

DriftSense v2 bridges advanced statistical time-series forecasting with everyday FinOps and engineering decision-making. 

### Core UX Tenet:
> **"A non-scientist must be able to understand and act on every screen within 10 seconds, while an ML engineer or FinOps auditor can inspect every mathematical proof behind a single click."**

---

## 2. The Four Pillars of DriftSense UX

### 2.1 Plain-Language by Default
All user interfaces, alert cards, notifications, and tooltips prioritize clear, human-understandable business concepts.
* Never present mathematical jargon (such as "TreeSHAP Local Additivity", "Conformal Quantile Deviation", or "Residual Z-score") in default user views.
* Substitute business metrics: "Gap between expected and actual spend", "What pushed spend up or down", "Sensitivity setting".

### 2.2 Progressive Disclosure: The "Expert Details" Toggle
Every analytic card, incident view, and chart provides a standardized **"Expert Details"** drawer/toggle.
* **Default View (Closed):**
  * Business impact: Total dollars unexpected ($\Delta \$ = \$1,420$).
  * Plain-language summary: "Compute spend jumped by 38% starting Tuesday 14:00 UTC."
  * Correlated timeline: "Deployment `v4.12.0` occurred 45 minutes prior to the increase."
  * Confidence badge: `Likely Associated` (High Confidence).
  * Action button: "Open Deployment Runbook" / "Mark False Alarm".
* **Expert View (Toggled Open):**
  * Full interactive decomposition chart (Volume vs. Price vs. Mix).
  * Conformal prediction bounds with non-conformity score ($\alpha = 0.10$).
  * SHAP feature contribution waterfall table with exact floating-point values.
  * Temporal decay attribution weights and candidate decoy comparison.
  * Raw FOCUS record identifiers and exportable JSON payload.

### 2.3 Strict Non-Causal Visual Language
To preserve scientific integrity and prevent false certitude:
* **Forbidden Copy:** Never use words such as *"caused by"*, *"triggered by"*, or *"resulted from"*.
* **Permitted Association Copy:**
  * *"Likely associated with..."*
  * *"Evidence points toward..."*
  * *"Temporally correlated with..."*
  * *"Spend increase coincides with..."*
* **Abstention State:** When candidate events score below confidence thresholds, the UI clearly displays:
  > **"Unusual spend detected, but no clear operational change is strongly associated. Showing top background factors."**

### 2.4 Decision-Centric Information Hierarchy
Every screen answers four questions in sequential order:
1. **What is happening?** (Current spend vs. expected baseline).
2. **How much does it matter?** (Dollar magnitude and percentage shift).
3. **What changed around the same time?** (Correlated deployments, config changes, scaling events).
4. **What should I do next?** (Recommended verification steps, alert routing, feedback).

---

## 3. Confidence Visual Language & Color Palette

Confidence is communicated using calibrated, accessible visual cues rather than raw percentages.

| Visual Level | Label | UI Badge Color | Visual Icon | Meaning to User |
|---|---|---|---|---|
| **High** | Strong Association | Emerald Green (`#059669`) | Checkmark Shield | Multiple independent signals (time, service, tag) align. |
| **Moderate**| Plausible Association | Amber Yellow (`#D97706`) | Information Circle | Temporally close, but service or tag match is indirect. |
| **Low / Noise** | Weak Evidence | Slate Grey (`#64748B`) | Question Mark Circle | Coincidence likely; other unmeasured factors may dominate. |
| **Abstained**| Inconclusive | Purple / Indigo (`#6366F1`) | Scale Balance | Model abstained; requires manual engineering review. |

---

## 4. Accessibility & Inclusivity Standards (WCAG 2.1 AA)

All web components must strictly comply with **WCAG 2.1 Level AA** standards:
1. **Color Independence:** Color is never the sole indicator of state or severity. Badges and alerts must combine color, distinct icons, and text labels.
2. **Contrast Ratios:**
   * Normal text ($\le 18\text{pt}$): Minimum contrast ratio of **4.5:1** against background.
   * Large text ($\ge 18\text{pt}$ or bold $\ge 14\text{pt}$): Minimum contrast ratio of **3.0:1**.
   * UI components and graphical objects: Minimum contrast ratio of **3.0:1**.
3. **Keyboard Navigation & Focus Management:**
   * All interactive controls (toggles, filters, drill-downs) must be reachable via `Tab` and actionable via `Enter` or `Space`.
   * Clear focus rings (`2px solid #2563EB` with `2px offset`) must remain visible.
4. **Screen Reader Optimization:**
   * All time-series charts provide an accessible HTML data-table fallback via `aria-describedby`.
   * Live alerts utilize `role="status"` with `aria-live="polite"` to announce new incoming anomalies without interrupting active navigation.
