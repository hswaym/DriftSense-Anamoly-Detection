"""Synthetic scenario generator package for DriftSense v2."""

from __future__ import annotations

from driftsense.synth.calibrate import (
    CalibrationProfile,
    ServiceCalibrationStats,
    calibrate_from_dataframe,
    load_calibration_profile,
    save_calibration_profile,
)
from driftsense.synth.confounders import ConfounderGenerator
from driftsense.synth.decoys import DecoyEvent, DecoyGenerator
from driftsense.synth.injector import (
    ALL_FAULT_FAMILIES,
    DEV_FAULT_FAMILIES,
    HOLDOUT_RESERVED_FAULT_FAMILIES,
    CalibratedFaultInjector,
)
from driftsense.synth.labels import (
    GroundTruthIncident,
    labels_to_dataframe,
    save_labels_csv,
    verify_label_isolation,
)
from driftsense.synth.scenarios import ScenarioOrchestrator

__all__ = [
    "ALL_FAULT_FAMILIES",
    "DEV_FAULT_FAMILIES",
    "HOLDOUT_RESERVED_FAULT_FAMILIES",
    "CalibratedFaultInjector",
    "CalibrationProfile",
    "ConfounderGenerator",
    "DecoyEvent",
    "DecoyGenerator",
    "GroundTruthIncident",
    "ScenarioOrchestrator",
    "ServiceCalibrationStats",
    "calibrate_from_dataframe",
    "labels_to_dataframe",
    "load_calibration_profile",
    "save_calibration_profile",
    "save_labels_csv",
    "verify_label_isolation",
]
