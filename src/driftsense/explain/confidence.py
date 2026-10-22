"""Calibrated confidence label derivation for DriftSense v2 (Phase 9).

CRITICAL REQUIREMENT (Phase 9):
    Confidence labels MUST be derived from calibrated scores, posterior margins,
    and structured evidence coverage — NEVER from raw SHAP value magnitudes.
    Raw SHAP represents model feature contribution in units of cost ($), not
    classification probability or evidence calibration.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class ConfidenceAssessment:
    """Assessment of confidence in an attribution or anomaly explanation."""

    tier: str  # "High", "Medium", "Low"
    calibrated_score: float  # [0.0, 1.0]
    margin: float  # Top-1 vs Top-2 probability margin
    evidence_count: int
    rationale: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "tier": self.tier,
            "calibrated_score": round(self.calibrated_score, 4),
            "margin": round(self.margin, 4),
            "evidence_count": self.evidence_count,
            "rationale": self.rationale,
        }


class CalibratedConfidenceScorer:
    """Scores explanation confidence using calibrated model posteriors and evidence counts."""

    def __init__(
        self,
        high_threshold: float = 0.75,
        medium_threshold: float = 0.45,
        min_margin_for_high: float = 0.15,
    ) -> None:
        self.high_threshold = high_threshold
        self.medium_threshold = medium_threshold
        self.min_margin_for_high = min_margin_for_high

    def assess_confidence(
        self,
        calibrated_score: float,
        margin: float = 0.0,
        evidence_count: int = 1,
        is_abstained: bool = False,
    ) -> ConfidenceAssessment:
        """Derive confidence tier from calibrated scores.

        Args:
            calibrated_score: Calibrated posterior probability in [0.0, 1.0].
            margin: Difference between top-1 and top-2 posterior probabilities.
            evidence_count: Number of independent supporting evidence items.
            is_abstained: True if the model abstained due to ambiguity.

        Returns:
            ConfidenceAssessment with tier in {"High", "Medium", "Low"}.
        """
        if not (0.0 <= calibrated_score <= 1.0):
            raise ValueError(
                f"calibrated_score must be in [0.0, 1.0], got {calibrated_score}. "
                "Ensure scores are calibrated probabilities, not uncalibrated logits or raw SHAP values."
            )

        if is_abstained:
            return ConfidenceAssessment(
                tier="Low",
                calibrated_score=calibrated_score,
                margin=margin,
                evidence_count=evidence_count,
                rationale="Model abstained: insufficient or conflicting operational evidence.",
            )

        if (
            calibrated_score >= self.high_threshold
            and margin >= self.min_margin_for_high
            and evidence_count >= 1
        ):
            tier = "High"
            rationale = (
                f"Strong calibrated probability ({calibrated_score*100:.1f}%) "
                f"with clear top-rank separation (margin: {margin*100:.1f}%) "
                f"and {evidence_count} supporting evidence item(s)."
            )
        elif calibrated_score >= self.medium_threshold:
            tier = "Medium"
            rationale = (
                f"Moderate calibrated probability ({calibrated_score*100:.1f}%) "
                f"or close competitor causes (margin: {margin*100:.1f}%)."
            )
        else:
            tier = "Low"
            rationale = (
                f"Low calibrated probability ({calibrated_score*100:.1f}%); "
                "multiple plausible explanations exist."
            )

        return ConfidenceAssessment(
            tier=tier,
            calibrated_score=calibrated_score,
            margin=margin,
            evidence_count=evidence_count,
            rationale=rationale,
        )

    def guard_against_raw_shap(self, raw_shap_values: Any) -> None:
        """Explicit guard ensuring raw SHAP values are never passed as confidence scores."""
        raise TypeError(
            "Phase 9 Invariant Violation: Attempted to derive confidence label from raw SHAP values. "
            "Confidence must be derived strictly from calibrated posterior scores."
        )
