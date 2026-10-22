"""Production runtime inference engine for DriftSense v2 (Phase 11).

Loads exported champion models and executes lightweight, CPU-optimized inference
on uploaded billing telemetry:
1. Ingests and validates multi-provider billing CSVs/Parquet
2. Executes clean & canonical aggregation (1h grain)
3. Computes rolling & lag features
4. Generates nominal spend forecast & residuals
5. Evaluates adaptive anomaly detector (with minimum dollar materiality floor)
6. Performs multi-layer root-cause attribution (with selective abstention)
7. Synthesizes plain-language executive narratives with TreeSHAP expert details
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from driftsense.attribute.ranker import MultiLayerAttributor
from driftsense.data.aggregate import aggregate_to_canonical_grain
from driftsense.data.clean import clean_focus_data
from driftsense.detect.rolling_threshold import RollingThresholdDetector
from driftsense.explain.plain_language import PlainLanguageSynthesizer
from driftsense.explain.shap_layer import TreeSHAPLayer
from driftsense.features.builder import FeaturePipeline
from driftsense.forecast.xgb import XGBoostForecaster

logger = logging.getLogger(__name__)


@dataclass
class AnomalyRecord:
    """Structured detected anomaly ready for API delivery."""

    anomaly_id: str
    service_name: str
    timestamp: str
    actual_cost: float
    expected_cost: float
    deviation_cost: float
    percentage_deviation: float
    severity: str  # "Critical", "High", "Medium", "Low"
    top_cause: str
    confidence_tier: str
    narrative_markdown: str
    status: str = "New"
    user_feedback: str | None = None
    feedback_notes: str | None = None
    evidence_refs: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "anomaly_id": self.anomaly_id,
            "service_name": self.service_name,
            "timestamp": self.timestamp,
            "actual_cost": round(self.actual_cost, 2),
            "expected_cost": round(self.expected_cost, 2),
            "deviation_cost": round(self.deviation_cost, 2),
            "percentage_deviation": round(self.percentage_deviation, 2),
            "severity": self.severity,
            "top_cause": self.top_cause,
            "confidence_tier": self.confidence_tier,
            "narrative_markdown": self.narrative_markdown,
            "status": self.status,
            "user_feedback": self.user_feedback,
            "feedback_notes": self.feedback_notes,
            "evidence_refs": self.evidence_refs,
        }


@dataclass
class InferenceResult:
    """Comprehensive pipeline execution output."""

    analysis_id: str
    tenant_id: str
    total_spend: float
    expected_spend: float
    dollars_at_risk: float
    total_anomalies: int
    anomalies: list[AnomalyRecord]
    metadata: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "analysis_id": self.analysis_id,
            "tenant_id": self.tenant_id,
            "total_spend": round(self.total_spend, 2),
            "expected_spend": round(self.expected_spend, 2),
            "dollars_at_risk": round(self.dollars_at_risk, 2),
            "total_anomalies": self.total_anomalies,
            "anomalies": [a.to_dict() for a in self.anomalies],
            "metadata": self.metadata,
        }


class RuntimeInferenceEngine:
    """Production inference engine loading exported artifacts for tenant analysis."""

    def __init__(
        self,
        forecaster: XGBoostForecaster | None = None,
        detector: RollingThresholdDetector | None = None,
        attributor: MultiLayerAttributor | None = None,
        min_materiality_dollars: float = 10.0,
        min_materiality_pct: float = 15.0,
    ) -> None:
        self.forecaster = forecaster
        self.detector = detector or RollingThresholdDetector(window=24, threshold=3.0)
        self.attributor = attributor or MultiLayerAttributor()
        self.min_materiality_dollars = min_materiality_dollars
        self.min_materiality_pct = min_materiality_pct
        self.synthesizer = PlainLanguageSynthesizer()

    def run_pipeline(
        self,
        raw_df: pd.DataFrame,
        analysis_id: str,
        tenant_id: str = "tenant_default",
        events: list[dict[str, Any]] | None = None,
        column_mapping: dict[str, str] | None = None,
    ) -> InferenceResult:
        """Run full end-to-end inference on user-uploaded dataset."""
        df = raw_df.copy()
        if column_mapping:
            df = df.rename(columns=column_mapping)

        # 1. Clean & Canonical Aggregate
        df_clean, _ = clean_focus_data(df)
        df_agg, _ = aggregate_to_canonical_grain(df_clean, grain="1h")

        cost_col = "EffectiveCost"
        time_col = "ChargePeriodStart"
        svc_col = "ServiceName"

        # 2. Extract Features
        pipeline = FeaturePipeline()
        features_df = pipeline.fit_transform(df_agg)

        # 3. Forecast Baseline Spend
        if self.forecaster is None or not getattr(self.forecaster, "is_fitted", False):
            # Lightweight fitting on tenant baseline if no pretrained model passed
            self.forecaster = XGBoostForecaster(n_estimators=30, max_depth=4, seed=42)
            self.forecaster.fit(features_df, target_col=cost_col, time_col=time_col, service_col=svc_col)

        preds = self.forecaster.predict(features_df)
        residuals = features_df[cost_col].to_numpy(dtype=float) - preds
        features_df["predicted_cost"] = preds
        features_df["residual"] = residuals

        # 4. Anomaly Detection with Materiality Filtering
        df_res = pd.DataFrame({
            "residual": residuals,
            svc_col: features_df[svc_col].values,
            time_col: features_df[time_col].values,
        })
        if not getattr(self.detector, "is_fitted", False):
            self.detector.fit(df_res, residual_col="residual", service_col=svc_col, time_col=time_col)

        flags = self.detector.predict(df_res)
        features_df["is_flagged"] = flags

        # 5. Extract Anomaly Records
        feature_cols = getattr(self.forecaster, "feature_names_", getattr(self.forecaster, "feature_cols_", []))
        tree_layer = TreeSHAPLayer(self.forecaster.model_, feature_names=feature_cols, atol=0.05)

        anomalies: list[AnomalyRecord] = []
        dollars_at_risk = 0.0

        flagged_indices = features_df[features_df["is_flagged"] == 1].index

        for idx in flagged_indices:
            row = features_df.loc[idx]
            actual = float(row[cost_col])
            expected = float(row["predicted_cost"])
            delta = actual - expected
            pct_delta = (delta / max(0.01, expected) * 100.0)

            # Materiality Filter: suppress small-dollar noise
            if delta < self.min_materiality_dollars or pct_delta < self.min_materiality_pct:
                continue

            dollars_at_risk += delta

            # Severity tiering
            if delta > 500.0 or pct_delta > 100.0:
                severity = "Critical"
            elif delta > 150.0 or pct_delta > 50.0:
                severity = "High"
            elif delta > 50.0 or pct_delta > 25.0:
                severity = "Medium"
            else:
                severity = "Low"

            anom_id = f"anom_{analysis_id[:8]}_{idx}"
            svc_name = str(row[svc_col])
            ts = str(row[time_col])

            # Layered Attribution
            nearby = [e for e in (events or []) if e.get("service") == svc_name or e.get("service_id") == svc_name]
            attr_res = self.attributor.attribute_incident(
                incident={"service": svc_name, "timestamp": ts, "cost_delta": delta},
                nearby_events=nearby,
            )

            # Instance TreeSHAP explanation
            inst_shap = tree_layer.explain_instance(
                row[feature_cols],
                prediction_id=anom_id,
                top_k=4,
            )

            ranked_reasons = [
                {
                    "cause": getattr(r, "cause", getattr(r, "cause_category", "UNKNOWN")),
                    "confidence": getattr(r, "confidence_tier", "Medium"),
                    "percentage_share": getattr(r, "percentage_share", 0.0),
                    "rationale": getattr(r, "summary", getattr(r, "plain_language_summary", "")),
                }
                for r in attr_res.reasons
            ]

            plain_exp = self.synthesizer.generate_explanation(
                prediction_id=anom_id,
                service_name=svc_name,
                timestamp=ts,
                actual_cost=actual,
                expected_cost=expected,
                ranked_causes=ranked_reasons,
                instance_shap=inst_shap,
                evidence_refs=[e.key for r in attr_res.reasons for e in r.supporting_evidence],
            )

            anomalies.append(
                AnomalyRecord(
                    anomaly_id=anom_id,
                    service_name=svc_name,
                    timestamp=ts,
                    actual_cost=actual,
                    expected_cost=expected,
                    deviation_cost=delta,
                    percentage_deviation=pct_delta,
                    severity=severity,
                    top_cause=attr_res.top_cause,
                    confidence_tier=getattr(plain_exp, "confidence_tier", (attr_res.reasons[0].confidence_tier if attr_res.reasons else "Medium")),
                    narrative_markdown=plain_exp.narrative_markdown,
                    evidence_refs=plain_exp.evidence_refs,
                )
            )

        total_actual = float(features_df[cost_col].sum())
        total_expected = float(features_df["predicted_cost"].sum())

        return InferenceResult(
            analysis_id=analysis_id,
            tenant_id=tenant_id,
            total_spend=total_actual,
            expected_spend=total_expected,
            dollars_at_risk=dollars_at_risk,
            total_anomalies=len(anomalies),
            anomalies=anomalies,
            metadata={
                "row_count": len(features_df),
                "services_count": features_df[svc_col].nunique(),
                "time_start": str(features_df[time_col].min()),
                "time_end": str(features_df[time_col].max()),
                "materiality_floor_dollars": self.min_materiality_dollars,
            },
        )
