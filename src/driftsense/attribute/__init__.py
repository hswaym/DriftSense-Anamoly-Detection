"""DriftSense root-cause attribution package."""

from __future__ import annotations

from driftsense.attribute.abstain import (
    AbstentionConfig,
    AbstentionFilter,
    ConfidenceCalibrator,
)
from driftsense.attribute.base import CANONICAL_TAXONOMY, BaseAttributor
from driftsense.attribute.correlation import TemporalCorrelationAttributor
from driftsense.attribute.decompose import DriverDecomposer
from driftsense.attribute.dimension_rank import DimensionContribution, DimensionRanker
from driftsense.attribute.events_kernel import EventEvidenceMatcher, EventKernelConfig
from driftsense.attribute.evidence import (
    AttributionReason,
    AttributionResult,
    EvidenceItem,
)
from driftsense.attribute.price_volume_mix import (
    PriceVolumeMixDecomposer,
    PriceVolumeMixItem,
    PriceVolumeMixResult,
)
from driftsense.attribute.prior_baseline import ClassPriorAttributor
from driftsense.attribute.random_baseline import RandomAttributor
from driftsense.attribute.ranker import MultiLayerAttributor
from driftsense.attribute.xgb_attributor import XGBoostAttributor

__all__ = [
    "CANONICAL_TAXONOMY",
    "AbstentionConfig",
    "AbstentionFilter",
    "AttributionReason",
    "AttributionResult",
    "BaseAttributor",
    "ClassPriorAttributor",
    "ConfidenceCalibrator",
    "DimensionContribution",
    "DimensionRanker",
    "DriverDecomposer",
    "EventEvidenceMatcher",
    "EventKernelConfig",
    "EvidenceItem",
    "MultiLayerAttributor",
    "PriceVolumeMixDecomposer",
    "PriceVolumeMixItem",
    "PriceVolumeMixResult",
    "RandomAttributor",
    "TemporalCorrelationAttributor",
    "XGBoostAttributor",
]
