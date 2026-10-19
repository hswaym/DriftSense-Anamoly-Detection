"""Unit tests for synthetic fault and event injection engine."""

from __future__ import annotations

import pandas as pd

from driftsense.synth.injector import SyntheticInjector


def test_injector_single_and_decoy_scenarios(
    tiny_focus_dataframe: pd.DataFrame,
) -> None:
    """Verify synthetic injector produces calibrated anomalies and decoy events."""
    injector = SyntheticInjector(
        seed=42,
        injection_rate=0.2,
        min_duration_hours=2,
        max_duration_hours=3,
        multiplier_range=(1.5, 2.5),
        sigma_range=(2.0, 4.0),
    )

    df_inj, labels, events = injector.inject(
        tiny_focus_dataframe,
        cost_col="EffectiveCost",
        service_col="ServiceName",
        time_col="ChargePeriodStart",
    )

    # Assert injected rows have elevated cost
    assert "is_anomaly" in df_inj.columns
    assert "EffectiveCost_clean" in df_inj.columns
    assert df_inj["is_anomaly"].sum() > 0

    anom_rows = df_inj[df_inj["is_anomaly"] == 1]
    assert (anom_rows["EffectiveCost"] > anom_rows["EffectiveCost_clean"]).all()

    # Assert decoy events are present
    decoy_events = [
        e for e in events if "decoy" in str(e.get("metadata_json", "")).lower()
    ]
    assert len(decoy_events) > 0
    for d in decoy_events:
        assert d["is_synthetic"] is True

    # Assert labels adhere to Contract 6
    assert len(labels) > 0
    for lbl in labels:
        assert lbl["is_synthetic"] is True
        assert lbl["primary_cause"] is not None
        assert lbl["severity_score"] > 0.0
