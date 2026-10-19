"""Plain-text natural language narrative synthesis for FinOps explanations.

CRITICAL NON-CAUSAL WORDING INVARIANT (A9.2 & G6):
    Narratives explain statistical associations and model feature contributions.
    They NEVER use causal-proof wording such as 'caused by', 'proves that',
    'responsible for', or 'definitive cause'.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

# Mandatory non-causal disclaimer appended to all FinOps narrative reports
DISCLAIMER_TEXT = (
    "NOTE: Statistical feature attributions indicate correlation and model feature weighting, "
    "not verified physical causation. Operational verification with engineering logs is recommended."
)

# Forbidden phrases that imply definitive causality
FORBIDDEN_CAUSAL_PHRASES = [
    "caused by",
    "proves that",
    "is the cause",
    "is responsible for",
    "was responsible for",
    "definitive cause",
    "proven cause",
]


def validate_non_causal_text(text: str) -> None:
    """Validate that explanation text does not contain forbidden causal-proof wording.

    Raises:
        ValueError: If any forbidden phrase is found.
    """
    lower = text.lower()
    for phrase in FORBIDDEN_CAUSAL_PHRASES:
        if phrase in lower:
            raise ValueError(
                f"A9.2 Non-Causal Wording Violation: Found forbidden causal phrase '{phrase}' in text: {text}"
            )


def synthesize_cost_narrative(
    service_name: str,
    timestamp: str,
    actual_cost: float,
    expected_cost: float,
    top_positive_drivers: list[tuple[str, float]],
    coincident_events: list[dict[str, Any]] | None = None,
    attributed_cause: str | None = None,
) -> str:
    """Generate a structured, non-causal executive narrative explaining an anomaly.

    Args:
        service_name: Cloud service name (e.g. 'AmazonEC2').
        timestamp: Time of the anomalous observation.
        actual_cost: Observed cost ($).
        expected_cost: Model predicted expected cost ($).
        top_positive_drivers: Top positive feature names and SHAP values.
        coincident_events: Operational events detected within the incident window.
        attributed_cause: Top ranked cause from the attribution engine.

    Returns:
        Structured markdown narrative adhering strictly to A9.2.
    """
    delta = actual_cost - expected_cost
    pct_increase = (delta / expected_cost * 100.0) if expected_cost > 0 else 0.0

    lines = []
    lines.append(f"### Cost Anomaly Explanation: {service_name}")
    lines.append(f"**Period:** `{timestamp}`")
    lines.append(
        f"**Cost Deviation:** Observed `${actual_cost:,.2f}` vs expected `${expected_cost:,.2f}` "
        f"(deviation: `+${delta:,.2f}`, `{pct_increase:+.1f}%`)."
    )

    # Statistical Drivers Section
    if top_positive_drivers:
        lines.append("\n**Top Statistical Cost Drivers (TreeSHAP Attribution):**")
        total_pos = sum(v for _, v in top_positive_drivers if v > 0)
        for rank, (feat, val) in enumerate(top_positive_drivers[:4], 1):
            contrib_pct = (val / total_pos * 100.0) if total_pos > 0 else 0.0
            clean_feat = feat.replace("_", " ").title()
            lines.append(
                f"- **{rank}. {clean_feat}**: Associated with `+${val:,.2f}` deviation ({contrib_pct:.1f}% of positive attribution)."
            )

    # Operational Context & Coincident Events
    if coincident_events:
        lines.append("\n**Coincident Operational Activity:**")
        for ev in coincident_events[:3]:
            ev_type = ev.get("event_type", ev.get("type", "EVENT"))
            ev_time = ev.get("timestamp", ev.get("start_timestamp", ""))
            ev_svc = ev.get("service_id", ev.get("service_name", service_name))
            lines.append(
                f"- Coincident `{ev_type}` observed on `{ev_svc}` at `{ev_time}`."
            )

    # Attribution Candidate
    if attributed_cause:
        lines.append(
            f"\n**Attribution Assessment:** Operational signals are strongly correlated with `{attributed_cause}`."
        )

    # Mandatory Disclaimer
    lines.append(f"\n> [!NOTE]\n> {DISCLAIMER_TEXT}")

    narrative = "\n".join(lines)
    validate_non_causal_text(narrative)
    return narrative
