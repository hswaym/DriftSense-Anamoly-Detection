"""Multi-layer attribution engine for DriftSense v2.

Integrates:
- Layer 1: Driver & Price-Volume-Mix Decomposition (always available on billing)
- Layer 2: Event Proximity Decay Kernel (optional operational events)
- Layer 3: Learned Ranker (trained on synthetic labels only)
- Layer 4: Abstention & Confidence Calibration (outputs "Not enough evidence" on pure noise)
- Layer 5: Structured Evidence Objects per reason
"""

from __future__ import annotations

import logging
from typing import Any

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier

from driftsense.attribute.abstain import (
    AbstentionConfig,
    AbstentionFilter,
    ConfidenceCalibrator,
)
from driftsense.attribute.base import CANONICAL_TAXONOMY, BaseAttributor
from driftsense.attribute.decompose import DriverDecomposer
from driftsense.attribute.events_kernel import EventEvidenceMatcher, EventKernelConfig
from driftsense.attribute.evidence import (
    AttributionReason,
    AttributionResult,
    EvidenceItem,
)

logger = logging.getLogger(__name__)


class MultiLayerAttributor(BaseAttributor):
    """Production root-cause attributor integrating decomposition, event kernels, and ML."""

    def __init__(
        self,
        name: str = "MultiLayerAttributor",
        taxonomy: list[str] | None = None,
        event_kernel_config: EventKernelConfig | None = None,
        abstention_config: AbstentionConfig | None = None,
        enable_learned_ranker: bool = True,
        enable_abstention: bool = True,
        config: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(name=name, taxonomy=taxonomy or list(CANONICAL_TAXONOMY), config=config)
        self.event_matcher = EventEvidenceMatcher(event_kernel_config or EventKernelConfig())
        self.abstention_filter = AbstentionFilter(abstention_config or AbstentionConfig())
        self.driver_decomposer = DriverDecomposer()
        self.enable_learned_ranker = enable_learned_ranker
        self.enable_abstention = enable_abstention
        self.calibrator = ConfidenceCalibrator()

        self.classifier: HistGradientBoostingClassifier | None = None
        self.class_priors: dict[str, float] = {c: 1.0 / len(self.taxonomy) for c in self.taxonomy}

    def _extract_feature_vector(
        self,
        incident: dict[str, Any],
        events: list[dict[str, Any]],
    ) -> np.ndarray:
        """Extract tabular feature vector from incident and nearby events."""
        inc_ts = incident.get("timestamp") or incident.get("StartTime") or incident.get("ChargePeriodStart")
        inc_svc = incident.get("service") or incident.get("ServiceName")

        event_scores, evidence_items = self.event_matcher.match_events(
            incident_time=inc_ts,
            incident_service=inc_svc,
            events=events,
        )

        # Feature layout:
        # [0..N-1]: Event kernel score per taxonomy cause
        # [N]: Total matching events count
        # [N+1]: Max event kernel weight
        # [N+2]: Has exact service match (0 or 1)
        # [N+3]: Mean time delta hours
        vec = []
        for cause in self.taxonomy:
            vec.append(event_scores.get(cause, 0.0))

        vec.append(float(len(evidence_items)))

        if evidence_items:
            max_weight = max(e.percentage_share for e in evidence_items)
            has_match = any(e.details.get("match_status") == "EXACT_SERVICE_MATCH" for e in evidence_items)
            deltas = [e.time_overlap_hours for e in evidence_items if e.time_overlap_hours is not None]
            mean_delta = float(np.mean(deltas)) if deltas else 0.0
            vec.extend([max_weight, 1.0 if has_match else 0.0, mean_delta])
        else:
            vec.extend([0.0, 0.0, 0.0])

        return np.array(vec, dtype=float)

    def fit(
        self,
        incidents: list[dict[str, Any]] | pd.DataFrame,
        events: list[dict[str, Any]] | pd.DataFrame,
        telemetry_df: pd.DataFrame | None = None,
    ) -> MultiLayerAttributor:
        """Train empirical class priors and learned ranking model on historical incidents."""
        if isinstance(incidents, pd.DataFrame):
            incident_list = incidents.to_dict(orient="records")
        else:
            incident_list = list(incidents)

        if isinstance(events, pd.DataFrame):
            event_list = events.to_dict(orient="records")
        else:
            event_list = list(events)

        if not incident_list:
            self.is_fitted = True
            return self

        # 1. Empirical class priors
        cause_counts: dict[str, int] = {}
        for inc in incident_list:
            c = inc.get("primary_cause", inc.get("cause"))
            if c:
                cause_counts[c] = cause_counts.get(c, 0) + 1

        tot_inc = len(incident_list)
        for c in self.taxonomy:
            self.class_priors[c] = (cause_counts.get(c, 0) + 1) / (tot_inc + len(self.taxonomy))

        # 2. Train HistGradientBoostingClassifier if enabled and sufficient diverse incidents
        if self.enable_learned_ranker and len(incident_list) >= 15:
            X_list = []
            y_list = []
            valid_causes = set(self.taxonomy)

            for inc in incident_list:
                c = inc.get("primary_cause", inc.get("cause"))
                if c in valid_causes:
                    X_list.append(self._extract_feature_vector(inc, event_list))
                    y_list.append(c)

            if len(set(y_list)) >= 2:
                X = np.vstack(X_list)
                y = np.array(y_list)

                clf = HistGradientBoostingClassifier(
                    max_iter=100,
                    learning_rate=0.08,
                    max_depth=5,
                    random_state=42,
                )
                clf.fit(X, y)
                self.classifier = clf

        self.is_fitted = True
        return self

    def rank(
        self,
        incident: dict[str, Any],
        nearby_events: list[dict[str, Any]],
        telemetry: dict[str, Any] | None = None,
    ) -> list[tuple[str, float]]:
        """Return ranked list of (cause, confidence_score) tuples sorted descending."""
        inc_ts = incident.get("timestamp") or incident.get("StartTime") or incident.get("ChargePeriodStart")
        inc_svc = incident.get("service") or incident.get("ServiceName")

        # Layer 2: Event proximity kernel scores
        event_scores, _evidence_items = self.event_matcher.match_events(
            incident_time=inc_ts,
            incident_service=inc_svc,
            events=nearby_events,
        )

        combined_scores: dict[str, float] = {}

        # Layer 3: Learned ranker if available and active
        if self.classifier is not None and hasattr(self.classifier, "predict_proba"):
            feat = self._extract_feature_vector(incident, nearby_events).reshape(1, -1)
            probs = self.classifier.predict_proba(feat)[0]
            classes = list(self.classifier.classes_)
            clf_scores = dict(zip(classes, probs))
        else:
            clf_scores = {}

        # Fuse priors, event kernel, and ML classifier
        for cause in self.taxonomy:
            prior = self.class_priors.get(cause, 0.05)
            ev_score = event_scores.get(cause, 0.0)
            ml_score = clf_scores.get(cause, 0.0)

            # Blending: if strong event evidence exists, event evidence leads;
            # otherwise ML classifier and priors govern
            if ev_score > 0.1:
                score = 0.55 * ev_score + 0.35 * ml_score + 0.10 * prior
            elif ml_score > 0.0:
                score = 0.70 * ml_score + 0.30 * prior
            else:
                score = prior

            combined_scores[cause] = float(score)

        # Normalize to probability distribution
        total = sum(combined_scores.values())
        if total > 0:
            norm_scores = [(c, s / total) for c, s in combined_scores.items()]
        else:
            norm_scores = [(c, 1.0 / len(self.taxonomy)) for c in self.taxonomy]

        norm_scores.sort(key=lambda x: x[1], reverse=True)
        return norm_scores

    def attribute_incident(
        self,
        incident: dict[str, Any],
        nearby_events: list[dict[str, Any]],
        baseline_df: pd.DataFrame | None = None,
        actual_df: pd.DataFrame | None = None,
    ) -> AttributionResult:
        """Perform comprehensive multi-layer attribution with full evidence trace."""
        inc_id = str(incident.get("incident_id", incident.get("id", "inc_0")))
        inc_ts = str(incident.get("timestamp") or incident.get("StartTime") or incident.get("ChargePeriodStart", ""))
        inc_svc = incident.get("service") or incident.get("ServiceName")

        # 1. Event proximity evaluation
        _, event_evidence = self.event_matcher.match_events(
            incident_time=inc_ts,
            incident_service=inc_svc,
            events=nearby_events,
        )

        # 2. Driver & PVM decomposition (if billing data provided)
        decomp_data: dict[str, Any] = {}
        pvm_data: dict[str, Any] | None = None
        dim_evidence: list[EvidenceItem] = []

        if baseline_df is not None and actual_df is not None and not baseline_df.empty and not actual_df.empty:
            decomp = self.driver_decomposer.decompose(baseline_df, actual_df)
            decomp_data = decomp.get("dimensions", {})
            pvm_data = decomp.get("price_volume_mix")

            # Extract top dimension evidence
            for dim, items in decomp_data.items():
                if items:
                    top_item = items[0]
                    dim_evidence.append(
                        EvidenceItem(
                            evidence_type="DIMENSION_DECOMPOSITION",
                            dimension=dim,
                            key=top_item["key"],
                            dollar_impact=top_item["delta_cost"],
                            percentage_share=top_item["percentage_share"],
                            details=top_item,
                        )
                    )

        all_evidence = event_evidence + dim_evidence

        # 3. Candidate ranking
        ranked_scores = self.rank(incident, nearby_events)

        # 4. Layer 4 Abstention check
        should_abstain = False
        if self.enable_abstention:
            should_abstain, _abstain_reason = self.abstention_filter.evaluate(
                ranked_scores=ranked_scores,
                num_evidence_items=len(all_evidence),
            )

        # 5. Build AttributionReason objects
        reasons: list[AttributionReason] = []
        dollar_impact = float(incident.get("excess_spend", incident.get("delta_cost", 0.0)))

        for cause, score in ranked_scores:
            calibrated_prob = self.calibrator.calibrate(score)
            tier = self.abstention_filter.calibrator.get_tier(calibrated_prob)

            # Match evidence items associated with this cause
            cause_evidence = [
                e for e in all_evidence
                if e.details.get("mapped_cause") == cause
                or e.evidence_type == "DIMENSION_DECOMPOSITION"
            ]

            summary = (
                f"Candidate reason '{cause}' is associated with {score:.1%} evidence weight "
                f"across {len(cause_evidence)} supporting observations."
            )

            reasons.append(
                AttributionReason(
                    cause=cause,
                    confidence_score=float(score),
                    confidence_tier=tier,
                    dollar_impact=dollar_impact,
                    percentage_share=float(score),
                    supporting_evidence=cause_evidence,
                    summary=summary,
                )
            )

        return AttributionResult(
            incident_id=inc_id,
            timestamp=inc_ts,
            service=inc_svc,
            is_abstained=should_abstain,
            reasons=reasons,
            decomposition=decomp_data,
            price_volume_mix=pvm_data,
        )

    def predict_top_k(
        self,
        incidents: list[dict[str, Any]] | pd.DataFrame,
        events: list[dict[str, Any]] | pd.DataFrame,
        telemetry_df: pd.DataFrame | None = None,
        k: int = 3,
    ) -> list[list[str]]:
        """Generate top-k predicted causes for each incident (supporting abstention)."""
        if isinstance(incidents, pd.DataFrame):
            incident_list = incidents.to_dict(orient="records")
        else:
            incident_list = list(incidents)

        if isinstance(events, pd.DataFrame):
            event_list = events.to_dict(orient="records")
        else:
            event_list = list(events)

        results: list[list[str]] = []
        for inc in incident_list:
            res = self.attribute_incident(inc, event_list)
            if res.is_abstained:
                results.append(["NOT_ENOUGH_EVIDENCE"])
            else:
                top_k = [r.cause for r in res.reasons[:k]]
                results.append(top_k if top_k else ["NOT_ENOUGH_EVIDENCE"])

        return results

    def _get_model_state(self) -> dict[str, Any]:
        """Extract internal state for serialization."""
        return {
            "class_priors": self.class_priors,
            "classifier": self.classifier,
            "enable_learned_ranker": self.enable_learned_ranker,
            "enable_abstention": self.enable_abstention,
            "calibrator_a": self.calibrator._a,
            "calibrator_b": self.calibrator._b,
            "calibrator_fitted": self.calibrator.is_fitted,
        }

    def _set_model_state(self, state: dict[str, Any]) -> None:
        """Restore internal state from serialization."""
        self.class_priors = state.get("class_priors", {c: 1.0 / len(self.taxonomy) for c in self.taxonomy})
        self.classifier = state.get("classifier")
        self.enable_learned_ranker = state.get("enable_learned_ranker", True)
        self.enable_abstention = state.get("enable_abstention", True)
        self.calibrator._a = state.get("calibrator_a", 1.0)
        self.calibrator._b = state.get("calibrator_b", 0.0)
        self.calibrator.is_fitted = state.get("calibrator_fitted", False)
