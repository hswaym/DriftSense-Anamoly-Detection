"""Unit tests for deterministic Data Quality Score (0–100) with hand-computed cases (Acceptance A3.3)."""

import pandas as pd

from driftsense.quality.report import generate_quality_report
from driftsense.quality.score import calculate_quality_score


def make_clean_df(n: int = 100) -> pd.DataFrame:
    """Generate a clean, defect-free synthetic DataFrame."""
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
        "BilledCost": [15.0] * n,
        "EffectiveCost": [14.0] * n,
        "Currency": ["USD"] * n,
        "Tags": ['{"Environment": "Prod"}'] * n,
    })


def test_quality_score_clean_dataset():
    """Case 1: Clean dataset achieves 100.0 / 100 (Grade A) with zero deductions."""
    df = make_clean_df(100)
    result = calculate_quality_score(df)
    assert result.score == 100.0
    assert result.grade == "A"
    assert result.total_deductions == 0.0
    assert len(result.deductions) == 0


def test_quality_score_hand_computed_duplicates():
    """Case 2: 10 duplicate rows out of 100.

    dup_ratio = 10/100 = 0.10
    deduction = min(15.0, round(0.10 * 150, 1)) = 15.0
    Expected Score: 100.0 - 15.0 = 85.0 (Grade B)
    """
    df = make_clean_df(100)
    # Replicate first 10 rows
    df_dup = pd.concat([df, df.head(10)], ignore_index=True)
    # Total rows = 110, duplicate count = 10 -> dup_ratio = 10/110 = 0.090909
    # Hand-calc: 0.090909 * 150 = 13.636 -> 13.6 pts
    result = calculate_quality_score(df_dup)
    assert result.total_rows == 110
    dedup = next(d for d in result.deductions if d.category == "duplicates")
    assert dedup.points_deducted == 13.6
    assert result.score == 86.4
    assert result.grade == "B"


def test_quality_score_hand_computed_missing_days():
    """Case 3: Date range spans 5 days (120 hours), but middle 2 days are skipped.

    missing_days = 2
    deduction = min(20.0, 2 * 2.0) = 4.0 pts
    Expected Score: 100.0 - 4.0 = 96.0 (Grade A)
    """
    # Day 1 (24h) and Day 4-5 (48h) -> Day 2 and Day 3 missing
    day1 = pd.date_range("2024-09-01 00:00:00", periods=24, freq="h", tz="UTC")
    day4_5 = pd.date_range("2024-09-04 00:00:00", periods=48, freq="h", tz="UTC")
    all_dates = day1.append(day4_5)
    n = len(all_dates)

    df = pd.DataFrame({
        "ChargePeriodStart": all_dates,
        "ChargePeriodEnd": all_dates + pd.Timedelta(hours=1),
        "ServiceName": ["AmazonEC2"] * n,
        "SubAccountId": ["acc-1"] * n,
        "ResourceId": [f"res-{i}" for i in range(n)],
        "ConsumedQuantity": [1.0] * n,
        "ConsumedUnit": ["Hrs"] * n,
        "BilledCost": [1.0] * n,
        "EffectiveCost": [1.0] * n,
        "Currency": ["USD"] * n,
        "Tags": ['{"Env": "Prod"}'] * n,
    })

    result = calculate_quality_score(df)
    miss_ded = next(d for d in result.deductions if d.category == "missing_days")
    assert miss_ded.points_deducted == 4.0
    # Also timestamp gap will be flagged, check missing days deduction specifically
    assert miss_ded.metrics["missing_days_count"] == 2


def test_quality_score_hand_computed_untagged():
    """Case 4: 40 rows out of 100 lack tags.

    untagged_ratio = 40/100 = 0.40
    deduction = min(15.0, round(0.40 * 15.0, 1)) = 6.0 pts
    Expected Score: 100.0 - 6.0 = 94.0 (Grade A)
    """
    df = make_clean_df(100)
    df.loc[:39, "Tags"] = "{}"

    result = calculate_quality_score(df)
    tag_ded = next(d for d in result.deductions if d.category == "untagged_share")
    assert tag_ded.points_deducted == 6.0
    assert result.score == 94.0
    assert result.grade == "A"


def test_quality_score_hand_computed_unit_conflicts():
    """Case 5: Service 'AmazonEC2' has 2 conflicting units ('Hrs' and 'vCPU-Hours').

    conflict_services = 1
    deduction = min(20.0, 1 * 10.0) = 10.0 pts
    Expected Score: 100.0 - 10.0 = 90.0 (Grade A)
    """
    df = make_clean_df(100)
    # Inject second unit for AmazonEC2
    df.loc[:49, "ConsumedUnit"] = "vCPU-Hours"

    result = calculate_quality_score(df)
    unit_ded = next(d for d in result.deductions if d.category == "unit_conflicts")
    assert unit_ded.points_deducted == 10.0
    assert result.score == 90.0
    assert result.grade == "A"


def test_quality_score_hand_computed_multi_currency():
    """Case 6: Dataset mixes USD and EUR.

    deduction = flat 15.0 pts
    Expected Score: 100.0 - 15.0 = 85.0 (Grade B)
    """
    df = make_clean_df(100)
    df.loc[50:, "Currency"] = "EUR"

    result = calculate_quality_score(df)
    curr_ded = next(d for d in result.deductions if d.category == "multi_currency")
    assert curr_ded.points_deducted == 15.0
    assert result.score == 85.0
    assert result.grade == "B"


def test_generate_quality_report_output(tmp_path):
    """Verify JSON and Markdown report generation with plain-language reasons."""
    df = make_clean_df(50)
    # Add a deduction (untagged)
    df.loc[:19, "Tags"] = "{}"  # 20/50 = 40% untagged -> -6.0 pts

    json_path = tmp_path / "report.json"
    md_path = tmp_path / "report.md"

    report = generate_quality_report(
        df=df,
        dataset_name="TestDataset",
        output_json=json_path,
        output_md=md_path,
    )

    assert json_path.exists()
    assert md_path.exists()
    assert report["quality_score"] == 94.0
    assert report["grade"] == "A"

    md_content = md_path.read_text(encoding="utf-8")
    assert "Untagged Share" in md_content
    assert "-6.0" in md_content
