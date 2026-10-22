"""Plain-language explanation synthesizer for DriftSense v2 (Phase 9).

Produces auditable, non-causal narratives for finance managers and audit engineers:
- What happened (dollar & percent vs expected)
- Where (service, subaccount, region)
- When (onset timestamp, duration)
- Likely reasons with calibrated confidence labels
- Suggested next checks (generic, non-prescriptive)
- What we are not sure about (known unknowns)
- Technical TreeSHAP attributions sequestered behind expert details
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from driftsense.explain.confidence import CalibratedConfidenceScorer
from driftsense.explain.faithfulness import (
    check_plain_language_readability,
    verify_narrative_faithfulness,
)
from driftsense.explain.narrative_templates import render_narrative_template_v2
from driftsense.explain.shap_layer import InstanceExplanation
from driftsense.explain.validator import validate_non_causal_text

logger = logging.getLogger(__name__)


@dataclass
class PlainLanguageExplanation:
    """Fully validated plain-language explanation record."""

    prediction_id: str
    model_id: str
    service_name: str
    timestamp: str
    actual_cost: float
    expected_cost: float
    deviation_cost: float
    percentage_deviation: float
    top_cause: str
    confidence_tier: str
    narrative_markdown: str
    evidence_refs: list[str] = field(default_factory=list)
    expert_details: dict[str, Any] = field(default_factory=dict)
    is_faithful: bool = True
    is_readable: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "prediction_id": self.prediction_id,
            "model_id": self.model_id,
            "service_name": self.service_name,
            "timestamp": self.timestamp,
            "actual_cost": round(self.actual_cost, 2),
            "expected_cost": round(self.expected_cost, 2),
            "deviation_cost": round(self.deviation_cost, 2),
            "percentage_deviation": round(self.percentage_deviation, 2),
            "top_cause": self.top_cause,
            "confidence_tier": self.confidence_tier,
            "evidence_refs": self.evidence_refs,
            "expert_details": self.expert_details,
            "is_faithful": self.is_faithful,
            "is_readable": self.is_readable,
            "narrative_markdown": self.narrative_markdown,
        }


class PlainLanguageSynthesizer:
    """Synthesizes, validates, and audits plain-language FinOps narratives."""

    def __init__(
        self,
        confidence_scorer: CalibratedConfidenceScorer | None = None,
    ) -> None:
        self.confidence_scorer = confidence_scorer or CalibratedConfidenceScorer()

    def generate_explanation(
        self,
        prediction_id: str,
        service_name: str,
        timestamp: str,
        actual_cost: float,
        expected_cost: float,
        sub_account_id: str = "Unspecified Account",
        region_id: str = "Global / Multi-Region",
        duration_hours: float | None = None,
        ranked_causes: list[dict[str, Any]] | None = None,
        instance_shap: InstanceExplanation | None = None,
        evidence_refs: list[str] | None = None,
    ) -> PlainLanguageExplanation:
        """Synthesize an audited plain-language explanation adhering to A9.1-A9.4."""
        delta = actual_cost - expected_cost
        pct = (delta / expected_cost * 100.0) if expected_cost > 0 else 0.0

        # Assess calibrated confidence for top cause
        ranked_reasons: list[dict[str, Any]] = []
        top_cause = "UNKNOWN_CAUSE"
        top_conf = "Medium"

        if ranked_causes:
            for idx, c in enumerate(ranked_causes):
                cause_name = c.get("cause") or c.get("primary_cause", "UNKNOWN_CAUSE")
                score = float(c.get("probability", c.get("score", 0.5)))
                margin = float(c.get("margin", 0.0))
                ev_cnt = int(c.get("evidence_count", 1))
                is_abst = bool(c.get("is_abstained", False))

                assessment = self.confidence_scorer.assess_confidence(
                    calibrated_score=score,
                    margin=margin,
                    evidence_count=ev_cnt,
                    is_abstained=is_abst,
                )

                if idx == 0:
                    top_cause = cause_name
                    top_conf = assessment.tier

                ranked_reasons.append(
                    {
                        "cause": cause_name,
                        "confidence": assessment.tier,
                        "rationale": c.get("rationale") or assessment.rationale,
                        "percentage_share": float(c.get("percentage_share", 0.0)),
                    }
                )

        # Build expert details payload
        expert_payload = {}
        if instance_shap:
            expert_payload = {
                "prediction_id": prediction_id,
                "model_id": instance_shap.model_id,
                "additivity_verified": instance_shap.additivity_verified,
                "additivity_error": instance_shap.additivity_error,
                "base_value": instance_shap.base_value,
                "model_output": instance_shap.model_output,
                "top_drivers": instance_shap.top_positive_drivers[:5],
            }

        # Render versioned narrative
        narrative_md = render_narrative_template_v2(
            service_name=service_name,
            timestamp=timestamp,
            actual_cost=actual_cost,
            expected_cost=expected_cost,
            sub_account_id=sub_account_id,
            region_id=region_id,
            duration_hours=duration_hours,
            ranked_reasons=ranked_reasons,
            expert_details=expert_payload,
        )

        # A9.3: Validate non-causal copy
        validate_non_causal_text(narrative_md)

        # A9.2: Verify numerical faithfulness
        faithfulness_res = verify_narrative_faithfulness(
            narrative_text=narrative_md,
            ground_values={
                "actual_cost": actual_cost,
                "expected_cost": expected_cost,
                "timestamp": timestamp,
            },
        )

        # A9.4: Check executive readability
        readability_res = check_plain_language_readability(narrative_md)

        return PlainLanguageExplanation(
            prediction_id=prediction_id,
            model_id=instance_shap.model_id if instance_shap else "DefaultModel",
            service_name=service_name,
            timestamp=timestamp,
            actual_cost=actual_cost,
            expected_cost=expected_cost,
            deviation_cost=delta,
            percentage_deviation=pct,
            top_cause=top_cause,
            confidence_tier=top_conf,
            narrative_markdown=narrative_md,
            evidence_refs=evidence_refs or [],
            expert_details=expert_payload,
            is_faithful=faithfulness_res["is_faithful"],
            is_readable=readability_res["is_compliant"],
        )
