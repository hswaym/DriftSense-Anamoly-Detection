"""Unit tests for cause attributors and ranking baselines."""

from __future__ import annotations

import pandas as pd
import pytest

from driftsense.attribute.base import BaseAttributor
from driftsense.attribute.correlation import TemporalCorrelationAttributor
from driftsense.attribute.prior_baseline import ClassPriorAttributor
from driftsense.attribute.random_baseline import RandomAttributor
from driftsense.attribute.xgb_attributor import XGBoostAttributor


@pytest.fixture
def synthetic_attribution_data() -> tuple[list[dict], list[dict]]:
    """Generate paired incident labels and operational events for attribution testing."""
    incidents = []
    events = []

    causes = [
        "DEPLOYMENT_DEFECT",
        "AUTOSCALING_OVERPROVISION",
        "CONFIG_MODIFICATION",
        "EXTERNAL_TRAFFIC_SURGE",
    ]

    base_date = pd.Timestamp("2024-09-01 00:00:00", tz="UTC")
    for i in range(20):
        c = causes[i % len(causes)]
        onset = base_date + pd.Timedelta(hours=i * 4)

        incidents.append(
            {
                "label_id": f"lbl_{i}",
                "service_id": "Amazon Elastic Compute Cloud",
                "onset_timestamp": onset.isoformat(),
                "offset_timestamp": (onset + pd.Timedelta(hours=2)).isoformat(),
                "primary_cause": c,
                "severity_score": 2.5,
            }
        )

        # Causal event 30m prior
        events.append(
            {
                "event_id": f"evt_{i}",
                "service_id": "Amazon Elastic Compute Cloud",
                "ts_start": (onset - pd.Timedelta(minutes=30)).isoformat(),
                "ts_end": (onset + pd.Timedelta(minutes=30)).isoformat(),
                "event_type": c,
                "metadata_json": "{}",
            }
        )

        # Decoy event 15m prior
        events.append(
            {
                "event_id": f"decoy_{i}",
                "service_id": "Amazon Elastic Compute Cloud",
                "ts_start": (onset - pd.Timedelta(minutes=15)).isoformat(),
                "ts_end": (onset + pd.Timedelta(minutes=45)).isoformat(),
                "event_type": "DEPLOYMENT_DEFECT",
                "metadata_json": '{"is_decoy": true}',
            }
        )

    return incidents, events


@pytest.mark.parametrize(
    "attributor_cls, kwargs",
    [
        (RandomAttributor, {"seed": 42}),
        (ClassPriorAttributor, {}),
        (TemporalCorrelationAttributor, {"lookback_hours": 3.0}),
        (XGBoostAttributor, {"n_estimators": 10, "max_depth": 2, "seed": 42}),
    ],
)
def test_unfitted_attributor_raises(
    attributor_cls: type[BaseAttributor],
    kwargs: dict,
    synthetic_attribution_data: tuple[list[dict], list[dict]],
) -> None:
    """Verify calling rank or predict before fit raises RuntimeError."""
    incidents, events = synthetic_attribution_data
    attributor = attributor_cls(**kwargs)
    assert not attributor.is_fitted
    with pytest.raises(RuntimeError):
        attributor.rank(incidents[0], events)


@pytest.mark.parametrize(
    "attributor_cls, kwargs",
    [
        (RandomAttributor, {"seed": 42}),
        (ClassPriorAttributor, {}),
        (TemporalCorrelationAttributor, {"lookback_hours": 3.0}),
        (XGBoostAttributor, {"n_estimators": 10, "max_depth": 2, "seed": 42}),
    ],
)
def test_fit_rank_predict_and_persistence(
    attributor_cls: type[BaseAttributor],
    kwargs: dict,
    synthetic_attribution_data: tuple[list[dict], list[dict]],
    tmp_path,
) -> None:
    """Verify fit, rank, predict_top_k, save, and load roundtrip."""
    incidents, events = synthetic_attribution_data
    attributor = attributor_cls(**kwargs)

    # Fit attributor
    fitted = attributor.fit(incidents, events)
    assert fitted.is_fitted
    assert attributor.training_timestamp_utc is not None
    assert len(attributor.config_hash) == 64

    # Rank single incident
    ranked = attributor.rank(incidents[0], events)
    assert len(ranked) == len(attributor.taxonomy)
    assert all(isinstance(c, str) and isinstance(s, float) for c, s in ranked)

    # Predict top-k
    top3_before = attributor.predict_top_k(incidents[:5], events, k=3)
    assert len(top3_before) == 5
    assert len(top3_before[0]) == 3

    # Save attributor
    save_file = tmp_path / f"{attributor.name}.joblib"
    saved_path = attributor.save(save_file)
    assert saved_path.exists()

    # Load attributor
    loaded = attributor_cls.load(saved_path)
    assert loaded.is_fitted
    assert loaded.name == attributor.name
    assert loaded.config_hash == attributor.config_hash

    # Predict with loaded attributor
    top3_after = loaded.predict_top_k(incidents[:5], events, k=3)
    assert top3_before == top3_after


def test_correlation_and_xgb_beat_random(
    synthetic_attribution_data: tuple[list[dict], list[dict]],
) -> None:
    """Verify ML and heuristic attributors outperform random baseline (A8.2)."""
    incidents, events = synthetic_attribution_data

    # Split into train (first 12) and val (last 8)
    train_inc, val_inc = incidents[:12], incidents[12:]
    train_evt, val_evt = events[:24], events[24:]

    # Random baseline
    rand_att = RandomAttributor(seed=42).fit(train_inc, train_evt)
    rand_preds = rand_att.predict_top_k(val_inc, val_evt, k=1)
    rand_acc = sum(
        p[0] == inc["primary_cause"] for p, inc in zip(rand_preds, val_inc)
    ) / len(val_inc)

    # Temporal correlation attributor
    corr_att = TemporalCorrelationAttributor(lookback_hours=2.0).fit(
        train_inc, train_evt
    )
    corr_preds = corr_att.predict_top_k(val_inc, val_evt, k=1)
    corr_acc = sum(
        p[0] == inc["primary_cause"] for p, inc in zip(corr_preds, val_inc)
    ) / len(val_inc)

    # XGBoost attributor
    xgb_att = XGBoostAttributor(n_estimators=20, max_depth=3, seed=42).fit(
        train_inc, train_evt
    )
    xgb_preds = xgb_att.predict_top_k(val_inc, val_evt, k=1)
    xgb_acc = sum(
        p[0] == inc["primary_cause"] for p, inc in zip(xgb_preds, val_inc)
    ) / len(val_inc)

    # Correlation and XGBoost must beat random guessing
    assert corr_acc > rand_acc, (
        f"Correlation acc ({corr_acc}) should beat random ({rand_acc})"
    )
    assert xgb_acc > rand_acc, (
        f"XGBoost acc ({xgb_acc}) should beat random ({rand_acc})"
    )
