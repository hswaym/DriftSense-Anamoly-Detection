"""Structured evidence and reason representations for DriftSense attribution.

Ensures that every attribution prediction is supported by concrete, inspectable data points:
- Dimension decomposition contributions (dollar share, percentage share, explanatory power)
- Price / Volume / Mix decomposition effects (rate vs volume vs interaction)
- Event proximity matches (service match, timestamp delta, kernel weight)
- Telemetry anomalies (usage surges, rate changes)

Also defines AttributionReason and AttributionResult.
Per Principle C6 and UX rules: narrative copy avoids forbidden causal verbs.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class EvidenceItem:
    """Individual data point supporting an attribution reason."""

    evidence_type: str  # e.g., "DIMENSION_DECOMPOSITION", "PRICE_VOLUME_MIX", "EVENT_PROXIMITY", "TELEMETRY_ANOMALY"
    dimension: str  # e.g., "ServiceName", "SubAccountId", "RegionId", "UsageType", "OperationalEvent"
    key: str  # e.g., "AmazonEC2", "us-east-1", "deploy-commit-abc"
    dollar_impact: float = 0.0
    percentage_share: float = 0.0  # 0.0 to 1.0 (or percentage of total delta)
    time_overlap_hours: float | None = None
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert evidence item to dictionary."""
        return asdict(self)


@dataclass
class AttributionReason:
    """A ranked candidate cause with supporting evidence and confidence calibration."""

    cause: str
    confidence_score: float  # Bounded in [0.0, 1.0]
    confidence_tier: str  # "High", "Medium", "Low"
    dollar_impact: float = 0.0
    percentage_share: float = 0.0
    supporting_evidence: list[EvidenceItem] = field(default_factory=list)
    summary: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Convert reason to dictionary."""
        d = asdict(self)
        d["supporting_evidence"] = [e.to_dict() if hasattr(e, "to_dict") else e for e in self.supporting_evidence]
        return d


@dataclass
class AttributionResult:
    """Full attribution evaluation result for an incident."""

    incident_id: str
    timestamp: str | None = None
    service: str | None = None
    is_abstained: bool = False
    reasons: list[AttributionReason] = field(default_factory=list)
    decomposition: dict[str, Any] = field(default_factory=dict)
    price_volume_mix: dict[str, Any] | None = None

    @property
    def top_cause(self) -> str:
        """Return top predicted cause, or NOT_ENOUGH_EVIDENCE if abstained or empty."""
        if self.is_abstained or not self.reasons:
            return "NOT_ENOUGH_EVIDENCE"
        return self.reasons[0].cause

    @property
    def top_confidence(self) -> float:
        """Return confidence score of top reason, or 0.0 if empty."""
        if not self.reasons:
            return 0.0
        return self.reasons[0].confidence_score

    def to_dict(self) -> dict[str, Any]:
        """Convert result to dictionary."""
        return {
            "incident_id": self.incident_id,
            "timestamp": self.timestamp,
            "service": self.service,
            "is_abstained": self.is_abstained,
            "top_cause": self.top_cause,
            "top_confidence": self.top_confidence,
            "reasons": [r.to_dict() for r in self.reasons],
            "decomposition": self.decomposition,
            "price_volume_mix": self.price_volume_mix,
        }
