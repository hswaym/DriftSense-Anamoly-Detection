"""Unit tests for Scenario Generator v2, fault injection, decoys, and label isolation (Phase 4)."""

import pandas as pd
import pytest

from driftsense.runtime.config import load_config
from driftsense.synth.decoys import DecoyGenerator
from driftsense.synth.injector import (
    DEV_FAULT_FAMILIES,
    HOLDOUT_RESERVED_FAULT_FAMILIES,
    CalibratedFaultInjector,
)
from driftsense.synth.labels import (
    FORBIDDEN_FEATURE_NAMES,
    verify_label_isolation,
)
from driftsense.synth.scenarios import ScenarioOrchestrator


def make_clean_test_df(n: int = 100) -> pd.DataFrame:
    """Generate clean synthetic DataFrame for testing."""
    dates_start = pd.date_range("2024-09-01 00:00:00", periods=n, freq="h", tz="UTC")
    dates_end = dates_start + pd.Timedelta(hours=1)
    return pd.DataFrame({
        "record_id": [f"rec_{i}" for i in range(n)],
        "tenant_id": ["00000000-0000-0000-0000-000000000000"] * n,
        "ChargePeriodStart": dates_start,
        "ChargePeriodEnd": dates_end,
        "ServiceName": ["AmazonEC2"] * n,
        "SubAccountId": ["acc-1"] * n,
        "ResourceId": [f"res-{i}" for i in range(n)],
        "ConsumedQuantity": [10.0] * n,
        "ConsumedUnit": ["Hrs"] * n,
        "BilledCost": [20.0] * n,
        "EffectiveCost": [20.0] * n,
        "Currency": ["USD"] * n,
        "Tags": ['{"Environment": "Prod"}'] * n,
    })


def test_injector_onset_magnitude_and_duration():
    """Verify A4.1: Fault injector onset shapes, magnitudes, and durations match configuration."""
    df = make_clean_test_df(50)
    injector = CalibratedFaultInjector(seed=42)

    # 1. Test abrupt usage_spike (Volume + Cost increase)
    df_inj, label, event = injector.inject_incident(
        df=df,
        service_name="AmazonEC2",
        start_idx=10,
        duration_hours=5,
        fault_family="usage_spike",
        magnitude=2.5,
        onset_shape="abrupt",
    )

    assert label.fault_family == "usage_spike"
    assert label.duration_hours == 5
    assert label.magnitude_multiplier == 2.5
    assert label.onset_shape == "abrupt"
    assert event["event_type"] == "usage_spike"

    # Injected range: indices 10 through 14
    for i in range(10, 15):
        assert df_inj.loc[i, "ConsumedQuantity"] == 25.0  # 10.0 * 2.5
        assert df_inj.loc[i, "EffectiveCost"] == 50.0      # 20.0 * 2.5

    # Non-injected points must be completely unperturbed
    assert df_inj.loc[9, "ConsumedQuantity"] == 10.0
    assert df_inj.loc[15, "ConsumedQuantity"] == 10.0

    # 2. Test rate_price_change (Cost increases, but ConsumedQuantity is UNCHANGED)
    df_rate, _label_rate, _ = injector.inject_incident(
        df=df,
        service_name="AmazonEC2",
        start_idx=20,
        duration_hours=4,
        fault_family="rate_price_change",
        magnitude=3.0,
        onset_shape="abrupt",
    )

    for i in range(20, 24):
        assert df_rate.loc[i, "ConsumedQuantity"] == 10.0  # Quantity unchanged!
        assert df_rate.loc[i, "EffectiveCost"] == 60.0     # 20.0 * 3.0

    # 3. Test gradual_linear onset curve
    df_grad, _label_grad, _ = injector.inject_incident(
        df=df,
        service_name="AmazonEC2",
        start_idx=30,
        duration_hours=4,
        fault_family="gradual_ramp_drift",
        magnitude=2.0,
        onset_shape="gradual_linear",
    )
    # Step 0: 1.0 + (2.0-1.0)*1/4 = 1.25 -> Cost: 20 * 1.25 = 25.0
    # Step 3: 1.0 + (2.0-1.0)*4/4 = 2.00 -> Cost: 20 * 2.00 = 40.0
    assert df_grad.loc[30, "EffectiveCost"] == 25.0
    assert df_grad.loc[33, "EffectiveCost"] == 40.0


def test_decoys_have_zero_cost_effect_and_ratio():
    """Verify A4.2: Decoy events have ZERO effect on costs and exceed the 3:1 ratio."""
    df = make_clean_test_df(50)
    orchestrator = ScenarioOrchestrator(seed=42, is_holdout=False, decoy_to_fault_ratio=3.0)

    _df_injected, df_events, _df_labels, manifest = orchestrator.generate_scenario(
        df_clean=df,
        scenario_name="test_decoy_scenario",
    )

    # 1. Decoy ratio
    n_faults = manifest["total_faults_injected"]
    manifest["total_events_generated"]
    assert n_faults > 0
    assert manifest["decoy_to_fault_ratio"] >= 3.0

    # 2. Verify all decoy events explicitly declare is_decoy=True
    decoys = df_events[df_events["is_decoy"] == True]
    assert len(decoys) >= n_faults * 3

    # 3. Verify DecoyGenerator standalone has zero cost impact
    decoy_gen = DecoyGenerator(seed=101)
    decoy_events = decoy_gen.generate_decoys_for_timeline(
        time_series=df["ChargePeriodStart"],
        service_names=["AmazonEC2"],
        sub_account_ids=["acc-1"],
        n_faults=5,
    )
    assert len(decoy_events) >= 15
    for d in decoy_events:
        assert d.details["cost_impact"] == 0.0
        assert -45 <= d.jitter_minutes <= 45


def test_label_isolation_contract():
    """Verify A4.3: Ground-truth labels are strictly segregated from feature matrices."""
    df = make_clean_test_df(50)
    orchestrator = ScenarioOrchestrator(seed=42, is_holdout=False)

    df_injected, _df_events, df_labels, _ = orchestrator.generate_scenario(df_clean=df)

    # Injected DataFrame must have ONLY standard billing columns; NO label columns!
    for forbidden in FORBIDDEN_FEATURE_NAMES:
        assert forbidden not in df_injected.columns, f"Leaked label column: {forbidden}"

    # Labels table must contain the incident records
    assert not df_labels.empty
    assert "incident_id" in df_labels.columns
    assert "fault_family" in df_labels.columns
    assert "magnitude_multiplier" in df_labels.columns

    # Verify validator raises if leak occurs
    with pytest.raises(ValueError, match="CRITICAL TARGET LEAKAGE"):
        verify_label_isolation(["ChargePeriodStart", "EffectiveCost", "is_anomaly"])


def test_holdout_reserved_families_never_appear_in_dev_configs():
    """Verify A4.4: Holdout-reserved fault families NEVER appear in development configs."""
    # 1. Verify code constants
    overlap = set(DEV_FAULT_FAMILIES).intersection(set(HOLDOUT_RESERVED_FAULT_FAMILIES))
    assert len(overlap) == 0, f"Contaminated fault families: {overlap}"

    # 2. Verify configs/synth_dev.yaml
    dev_cfg, _ = load_config("configs/synth_dev.yaml")
    dev_allowed = dev_cfg["scenario"]["allowed_fault_families"]
    for reserved in HOLDOUT_RESERVED_FAULT_FAMILIES:
        assert reserved not in dev_allowed, (
            f"LEAVE-FAMILY-OUT CONTAMINATION: Holdout-reserved family '{reserved}' "
            "found in dev config!"
        )

    # 3. Verify configs/synth_holdout.yaml
    holdout_cfg, _ = load_config("configs/synth_holdout.yaml")
    holdout_allowed = holdout_cfg["scenario"]["allowed_fault_families"]
    for reserved in HOLDOUT_RESERVED_FAULT_FAMILIES:
        assert reserved in holdout_allowed, (
            f"Missing holdout-reserved family '{reserved}' in holdout config!"
        )
    for dev_fam in DEV_FAULT_FAMILIES:
        assert dev_fam not in holdout_allowed, (
            f"Dev family '{dev_fam}' found in holdout config!"
        )
