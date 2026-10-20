# DriftSense — Final Report: Chapter 4. Methodology & Architectural Framework

DriftSense employs a modular, four-pillar machine learning architecture designed to transform noisy raw billing feeds into actionable, explainable operational alerts.

---

## 4.1 Pillar I: Counterfactual Expected-Cost Forecasting

### 4.1.1 Formulation
Let $Y_{s,t}$ denote the observed `EffectiveCost` for cloud service $s$ at hour $t$. The counterfactual expected cost $\hat{Y}_{s,t}$ is modeled as:
$$\hat{Y}_{s,t} = E[Y_{s,t} \mid \mathcal{F}_{t-1}]$$
where $\mathcal{F}_{t-1}$ represents the filtration of all available historical cost, usage, and calendar information up to time $t-1$.

### 4.1.2 Feature Space Engineering
The chronological feature pipeline (`FeaturePipeline`) generates 48 distinct feature dimensions partitioned into three families:
1. **Cost Autoregression**: Lags ($t-1, t-2, t-24, t-168$), rolling statistics (mean, standard deviation, min, max over 6h, 24h, and 168h windows), and first-order differences ($t-1 - t-2$, $t - t-24$).
2. **Resource Consumption (Usage Coupling)**: Parallel lags and rolling windows over `ConsumedQuantity`. As demonstrated in ablation experiments, usage signals provide crucial leading indicators for cost spikes.
3. **Calendar & Seasonality**: Sine/cosine cyclic encodings for hour-of-day ($[0, 23]$), day-of-week ($[0, 6]$), and weekend binary indicators.

### 4.1.3 Models Evaluated
* **Seasonal Naive ($s=24$)**: $\hat{Y}_t = Y_{t-24}$
* **Moving Average ($w=24$)**: $\hat{Y}_t = \frac{1}{24}\sum_{i=1}^{24} Y_{t-i}$
* **Exponential Smoothing**: Holt-Winters exponential moving average ($\alpha=0.25$)
* **Champion GBDT (XGBoost)**: Gradient boosted regression trees with depth 5, 60 estimators, learning rate 0.08, and feature fraction 0.85, trained with early stopping on validation loss.

---

## 4.2 Pillar II: Dual-Track Anomaly Detection

### 4.2.1 Counterfactual Residual Formulation
Rather than monitoring raw spend, DriftSense calculates the model residual:
$$e_{s,t} = Y_{s,t} - \hat{Y}_{s,t}$$

When normal diurnal traffic scales up, $\hat{Y}_{s,t}$ scales commensurately, holding $e_{s,t} \approx 0$. If an unexpected runaway job triggers, $Y_{s,t} \gg \hat{Y}_{s,t}$, causing a sharp residual spike.

### 4.2.2 Champion Rolling Threshold Detector
The anomaly score and alert threshold are computed across a trailing sliding window ($w=24\text{h}$):
$$\mu_{\text{res}}(t) = \frac{1}{w}\sum_{i=1}^{w} e_{t-i}, \quad \sigma_{\text{res}}(t) = \sqrt{\frac{1}{w}\sum_{i=1}^{w} (e_{t-i} - \mu_{\text{res}}(t))^2}$$
An alert is raised if:
$$e_t > \mu_{\text{res}}(t) + k \cdot \sigma_{\text{res}}(t), \quad \text{where } k = 3.0$$

### 4.2.3 Dual-Track Evaluation Methodology
To prevent metric gaming, DriftSense evaluates detection across two distinct tracks:
1. **Real Clean Track**: Evaluated strictly on unmodified, real clean billing data. Because real data contains no verified faults, all triggered alerts are audited as potential false positives, measuring the empirical **False Positive Rate (FPR)** across weekday vs. weekend regimes.
2. **Synthetic Ground Truth Track**: Evaluated on traces with injected faults, computing point-level metrics (Precision, Recall, F1) and continuous **Event-Level Metrics** (Event Recall, Event F1, and Detection Delay).

---

## 4.3 Pillar III: Probabilistic Root-Cause Attribution Engine

When an anomaly is confirmed at time $t_{\text{alert}}$, the attribution engine inspects a pool of timestamped operational events $\mathcal{E}$ occurring within a lookback window $\tau_{\text{lookback}} = 6\text{h}$.

### 4.3.1 Temporal Decay Proximity Kernel
Each candidate event $E_i = (\text{event\_type}, t_i, \text{service})$ is scored using an exponential half-life decay function based on the temporal distance $\Delta t = t_{\text{alert}} - t_i$:
$$S(E_i) = \mathbb{I}_{(\text{service}_i = \text{service}_{\text{alert}})} \cdot \exp\left(-\frac{\Delta t}{\lambda}\right)$$
where $\lambda = \frac{t_{\text{half-life}}}{\ln(2)} = \frac{2.0}{\ln(2)} \approx 2.885$ hours.

### 4.3.2 Ranking & Evaluation
Events are ranked by score $S(E_i)$ in descending order. Performance is benchmarked against:
* **Random Baseline**: Uniform random permutation of event categories.
* **Class Prior Baseline**: Frequency-based ranking according to historical event occurrence rates.
* **Metrics**: Top-1 Accuracy, Top-2 Accuracy, Top-3 Accuracy, and Mean Reciprocal Rank (MRR).

---

## 4.4 Pillar IV: Model Explainability & FinOps Governance (XAI)

### 4.4.1 TreeSHAP Mathematical Additivity
To provide interpretable feature contributions for the XGBoost forecaster, DriftSense implements TreeSHAP (`driftsense.explain.shap_explainer`). The system guarantees local efficiency (exact additivity):
$$f(x) = \phi_0 + \sum_{j=1}^{M} \phi_j(x)$$
where $\phi_0 = E[f(x)]$ is the base expected model prediction and $\phi_j(x)$ is the Shapley attribution of feature $j$. Every execution verifies that $\left| f(x) - \left(\phi_0 + \sum \phi_j\right) \right| < 0.002$.

### 4.4.2 Non-Causal Natural Language Governance
To prevent false liability claims in engineering post-mortems, DriftSense synthesizes FinOps audit narratives using strict non-causal rules (`driftsense.explain.narrative`). Output text is validated by an automated scanner ensuring:
* Rejection of causal verbs ("caused by", "triggered by", "resulted in").
* Strict adoption of probabilistic phrasing ("likely associated with", "statistical feature evidence indicates", "coincident operational event").
