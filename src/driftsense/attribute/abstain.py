"""Abstention rules and confidence calibration for DriftSense attribution.

Implements Layer 4:
- When evidence is weak, ambiguous, or pure noise, the engine abstains and reports
  "Not enough evidence" rather than guessing hallucinated root causes.
- Maps continuous scores to calibrated probabilities and confidence tiers
  (High >= 0.75, Medium >= 0.45, Low < 0.45).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class AbstentionConfig:
    """Thresholds for selective abstention."""

    min_confidence: float = 0.30  # Absolute minimum top probability required to predict
    min_margin: float = 0.06      # Minimum separation between top-1 and top-2 candidate
    ambiguity_threshold: float = 0.55  # Margin rule applies when top score is below this
    min_evidence_items: int = 1   # Must have at least 1 piece of supporting evidence


class ConfidenceCalibrator:
    """Calibrates raw candidate scores into well-behaved posterior probabilities."""

    def __init__(self, temperature: float = 1.0) -> None:
        self.temperature = max(1e-2, temperature)
        self.is_fitted = False
        self._a = 1.0
        self._b = 0.0

    def fit(self, val_scores: np.ndarray, val_is_correct: np.ndarray) -> ConfidenceCalibrator:
        """Fit simple Platt scaling / logistic calibration on validation predictions."""
        if len(val_scores) < 10:
            self.is_fitted = True
            return self

        # Fit logistic regression: P(correct | score) = 1 / (1 + exp(-(a * score + b)))
        try:
            from scipy.optimize import minimize

            def loss(params: np.ndarray) -> float:
                a, b = params
                logits = a * val_scores + b
                # Numerical stability with logaddexp
                # -log P = log(1 + exp(-logits)) for positive, log(1 + exp(logits)) for negative
                eps = 1e-7
                probs = 1.0 / (1.0 + np.exp(-np.clip(logits, -15, 15)))
                probs = np.clip(probs, eps, 1.0 - eps)
                bce = -np.mean(val_is_correct * np.log(probs) + (1 - val_is_correct) * np.log(1 - probs))
                return float(bce)

            res = minimize(loss, x0=np.array([2.0, -1.0]), method="L-BFGS-B")
            if res.success:
                self._a, self._b = float(res.x[0]), float(res.x[1])
                self.is_fitted = True
        except Exception as e:
            logger.warning(f"Failed to fit calibrator: {e}. Using identity calibration.")
            self.is_fitted = True

        return self

    def calibrate(self, raw_score: float) -> float:
        """Map raw score to calibrated probability in [0.0, 1.0]."""
        if not self.is_fitted:
            # Fallback: simple sigmoid clipping
            return float(np.clip(raw_score, 0.0, 1.0))

        logit = self._a * raw_score + self._b
        prob = 1.0 / (1.0 + np.exp(-np.clip(logit, -15, 15)))
        return float(np.clip(prob, 0.0, 1.0))

    def get_tier(self, score: float) -> str:
        """Assign confidence tier based on calibrated score."""
        if score >= 0.75:
            return "High"
        elif score >= 0.45:
            return "Medium"
        else:
            return "Low"


class AbstentionFilter:
    """Evaluates whether attribution should abstain due to weak or ambiguous evidence."""

    def __init__(self, config: AbstentionConfig | None = None) -> None:
        self.config = config or AbstentionConfig()
        self.calibrator = ConfidenceCalibrator()

    def evaluate(
        self,
        ranked_scores: list[tuple[str, float]],
        num_evidence_items: int = 0,
    ) -> tuple[bool, str]:
        """Determine whether to abstain.

        Returns:
            Tuple of (should_abstain: bool, reason_description: str)
        """
        if not ranked_scores:
            return True, "No candidate causes evaluated"

        if num_evidence_items < self.config.min_evidence_items:
            return True, "No supporting dimensional or event evidence found"

        top_cause, top_score = ranked_scores[0]

        # 1. Low absolute confidence
        if top_score < self.config.min_confidence:
            return True, f"Top confidence score ({top_score:.2f}) is below threshold ({self.config.min_confidence:.2f})"

        # 2. Ambiguity check (margin between top-1 and top-2)
        if len(ranked_scores) > 1 and top_score < self.config.ambiguity_threshold:
            second_cause, second_score = ranked_scores[1]
            margin = top_score - second_score
            if margin < self.config.min_margin:
                return True, (
                    f"Ambiguous evidence between '{top_cause}' ({top_score:.2f}) and "
                    f"'{second_cause}' ({second_score:.2f}); margin ({margin:.2f}) < {self.config.min_margin:.2f}"
                )

        return False, "Evidence is sufficient"
