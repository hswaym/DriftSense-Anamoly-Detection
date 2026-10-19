"""End-to-end integration test verifying the complete DriftSense pipeline.

Covers the sequential execution of:
  validate -> clean -> features -> forecast -> detect -> attribute -> explain
using synthetic FOCUS fixtures without any test set data leakage.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from driftsense.cli import main


@pytest.fixture
def multi_day_focus_data(tmp_path: Path) -> Path:
    """Generate a 10-day synthetic FOCUS dataset (240 hours per service)."""
    dates = pd.date_range("2024-09-01 00:00:00", periods=240, freq="h", tz="UTC")
    rows = []
    rng = np.random.RandomState(42)

    services = [
        ("Amazon Elastic Compute Cloud", "Compute", "Hours", 0.096),
        ("Amazon Relational Database Service", "Database", "Hours", 0.150),
    ]

    for svc_name, svc_cat, unit, rate in services:
        for idx, dt in enumerate(dates):
            # Diurnal usage pattern
            usage = 5.0 + 3.0 * np.sin(2 * np.pi * dt.hour / 24) + rng.normal(0, 0.2)
            cost = max(0.01, usage * rate)
            rows.append(
                {
                    "Id": f"{svc_cat[:2]}_{idx}",
                    "ProviderName": "AWS",
                    "BillingAccountId": "123456789012",
                    "BillingAccountName": "IntegrationAccount",
                    "SubAccountId": "987654321098",
                    "SubAccountName": "IntegrationProject",
                    "BillingPeriodStart": "2024-09-01 00:00:00",
                    "BillingPeriodEnd": "2024-10-01 00:00:00",
                    "ChargePeriodStart": dt.strftime("%Y-%m-%d %H:%M:%S"),
                    "ChargePeriodEnd": (dt + pd.Timedelta(hours=1)).strftime(
                        "%Y-%m-%d %H:%M:%S"
                    ),
                    "BillingCurrency": "USD",
                    "ChargeCategory": "Usage",
                    "ChargeFrequency": "Usage-Based",
                    "ChargeDescription": f"{svc_name} standard tier",
                    "ServiceCategory": svc_cat,
                    "ServiceName": svc_name,
                    "RegionId": "us-west-2",
                    "RegionName": "US West (Oregon)",
                    "ResourceId": f"res_{svc_cat.lower()}_{idx % 3}",
                    "ConsumedQuantity": usage,
                    "ConsumedUnit": unit,
                    "PricingQuantity": usage,
                    "PricingUnit": unit,
                    "BilledCost": cost,
                    "EffectiveCost": cost,
                    "ContractedCost": cost,
                    "ListCost": cost * 1.1,
                    "ContractedUnitPrice": rate,
                    "ListUnitPrice": rate * 1.1,
                    "Tags": '{"env": "test"}',
                }
            )

    csv_path = tmp_path / "raw_focus_10d.csv"
    pd.DataFrame(rows).to_csv(csv_path, index=False)
    return csv_path


def test_e2e_pipeline_on_fixtures(multi_day_focus_data: Path, tmp_path: Path):
    """Execute end-to-end CLI workflow from validation to explainability."""
    work_dir = tmp_path / "e2e_run"
    work_dir.mkdir()

    # 1. Validate
    val_report = work_dir / "quality_report.json"
    rc_val = main(
        [
            "validate",
            "--data",
            str(multi_day_focus_data),
            "--report-out",
            str(val_report),
        ]
    )
    assert rc_val == 0
    assert val_report.is_file()
    with open(val_report, encoding="utf-8") as f:
        rep_data = json.load(f)
    assert rep_data["status"] == "PASSED"

    # 2. Clean & Aggregate
    cleaned_csv = work_dir / "focus_cleaned.csv"
    clean_log = work_dir / "clean_log.json"
    agg_csv = work_dir / "focus_agg_1h.csv"
    rc_clean = main(
        [
            "clean",
            "--input",
            str(multi_day_focus_data),
            "--output",
            str(cleaned_csv),
            "--log-out",
            str(clean_log),
            "--aggregate",
            "--grain",
            "1h",
            "--agg-output",
            str(agg_csv),
        ]
    )
    assert rc_clean == 0
    assert cleaned_csv.is_file()
    assert agg_csv.is_file()

    # 3. Features & Splits
    feats_csv = work_dir / "focus_features_1h.csv"
    splits_dir = work_dir / "splits"
    rc_feats = main(
        [
            "features",
            "--input",
            str(agg_csv),
            "--output",
            str(feats_csv),
            "--splits-dir",
            str(splits_dir),
        ]
    )
    assert rc_feats == 0
    assert (splits_dir / "train_features.csv").is_file()
    assert (splits_dir / "val_features.csv").is_file()
    assert (splits_dir / "test_features.csv").is_file()

    train_split = splits_dir / "train_features.csv"
    val_split = splits_dir / "val_features.csv"

    # 4. Forecast
    fc_models = work_dir / "forecast_models"
    fc_metrics = work_dir / "forecast_metrics.json"
    fc_preds = work_dir / "forecast_preds.csv"
    rc_fc = main(
        [
            "forecast",
            "--train",
            str(train_split),
            "--val",
            str(val_split),
            "--models-dir",
            str(fc_models),
            "--metrics-out",
            str(fc_metrics),
            "--predictions-out",
            str(fc_preds),
        ]
    )
    assert rc_fc == 0
    assert fc_metrics.is_file()
    assert fc_preds.is_file()

    # 5. Detect
    det_models = work_dir / "detect_models"
    det_metrics = work_dir / "detect_metrics.json"
    det_preds = work_dir / "detect_preds.csv"
    rc_det = main(
        [
            "detect",
            "--train",
            str(train_split),
            "--val",
            str(val_split),
            "--detectors-dir",
            str(det_models),
            "--metrics-out",
            str(det_metrics),
            "--predictions-out",
            str(det_preds),
        ]
    )
    assert rc_det == 0
    assert det_metrics.is_file()
    assert det_preds.is_file()

    # 6. Attribute
    attr_models = work_dir / "attr_models"
    attr_metrics = work_dir / "attr_metrics.json"
    attr_preds = work_dir / "attr_preds.csv"
    rc_attr = main(
        [
            "attribute",
            "--train",
            str(train_split),
            "--val",
            str(val_split),
            "--attributors-dir",
            str(attr_models),
            "--metrics-out",
            str(attr_metrics),
            "--predictions-out",
            str(attr_preds),
        ]
    )
    assert rc_attr == 0
    assert attr_metrics.is_file()
    assert attr_preds.is_file()

    # 7. Explain
    exp_metrics = work_dir / "explain_metrics.json"
    rc_exp = main(
        [
            "explain",
            "--val",
            str(val_split),
            "--model",
            str(fc_models / "xgboost.joblib"),
            "--metrics-out",
            str(exp_metrics),
        ]
    )
    assert rc_exp == 0
    assert exp_metrics.is_file()
