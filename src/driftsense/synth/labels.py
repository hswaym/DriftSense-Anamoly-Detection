"""Ground truth fault label definitions and isolation contracts.

Ensures ground truth labels are physically segregated from feature pipelines
to eliminate target leakage and evaluation contamination.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd

FORBIDDEN_FEATURE_NAMES = {
    "is_anomaly",
    "incident_id",
    "fault_family",
    "ground_truth_event_id",
    "true_cause_list",
    "magnitude_multiplier",
    "is_synthetic",
    "onset_shape",
    "clean_cost",
    "clean_quantity",
}


@dataclass
class GroundTruthIncident:
    """Formal record of an injected or labeled cost anomaly incident."""
    incident_id: str
    scenario_id: str
    service_name: str
    sub_account_id: str
    fault_family: str
    start_time: str  # ISO-8601 UTC
    end_time: str    # ISO-8601 UTC
    duration_hours: int
    magnitude_multiplier: float
    onset_shape: str  # 'abrupt', 'gradual_linear', 'gradual_exponential', 'step'
    is_synthetic: bool = True
    true_cause_list: list[str] = field(default_factory=list)
    ground_truth_event_id: str | None = None
    is_confounded: bool = False
    has_decoy: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


def labels_to_dataframe(labels: list[GroundTruthIncident]) -> pd.DataFrame:
    """Convert list of ground truth incidents to DataFrame."""
    if not labels:
        return pd.DataFrame(
            columns=[
                "incident_id",
                "scenario_id",
                "service_name",
                "sub_account_id",
                "fault_family",
                "start_time",
                "end_time",
                "duration_hours",
                "magnitude_multiplier",
                "onset_shape",
                "is_synthetic",
                "true_cause_list",
                "ground_truth_event_id",
                "is_confounded",
                "has_decoy",
            ]
        )
    return pd.DataFrame([asdict(lbl) for lbl in labels])


def save_labels_csv(labels: list[GroundTruthIncident], output_path: str | Path) -> None:
    """Save ground truth incident labels to standalone CSV."""
    p = Path(output_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    df = labels_to_dataframe(labels)
    df.to_csv(p, index=False)


def verify_label_isolation(feature_columns: list[str]) -> bool:
    """Verify that feature columns contain zero ground truth labels or leakage columns.

    Raises:
        ValueError: If any ground truth label column is found in feature columns.
    """
    intersection = set(feature_columns).intersection(FORBIDDEN_FEATURE_NAMES)
    if intersection:
        raise ValueError(
            f"CRITICAL TARGET LEAKAGE: Ground-truth label column(s) {sorted(intersection)} "
            "detected in feature matrix! Ground truth must live in a strictly separate table."
        )
    return True
