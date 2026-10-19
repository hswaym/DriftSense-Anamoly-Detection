"""Pytest fixtures for DriftSense test suite.

Provides a tiny synthetic fixture (20 rows) strictly conforming to FOCUS 1.0/1.3.
"""

from __future__ import annotations

import pandas as pd
import pytest


@pytest.fixture
def tiny_focus_dataframe() -> pd.DataFrame:
    """Generate a tiny synthetic FOCUS dataframe (20 rows, 2 services)."""
    rows = []
    # 10 hourly rows for Amazon Elastic Compute Cloud
    for i in range(10):
        start_hour = f"2024-09-18 {i:02d}:00:00"
        end_hour = f"2024-09-18 {i + 1:02d}:00:00"
        rows.append(
            {
                "Id": 1000 + i,
                "ProviderName": "AWS",
                "BillingAccountId": "123456789012",
                "BillingAccountName": "TestAccount",
                "SubAccountId": "987654321098",
                "SubAccountName": "TestProject",
                "BillingPeriodStart": "2024-09-01 00:00:00",
                "BillingPeriodEnd": "2024-10-01 00:00:00",
                "ChargePeriodStart": start_hour,
                "ChargePeriodEnd": end_hour,
                "BillingCurrency": "USD",
                "ChargeCategory": "Usage",
                "ChargeFrequency": "Usage-Based",
                "ChargeDescription": "Linux/UNIX (Amazon EC2, m5.large)",
                "ServiceCategory": "Compute",
                "ServiceName": "Amazon Elastic Compute Cloud",
                "RegionId": "us-west-2",
                "RegionName": "US West (Oregon)",
                "ResourceId": "i-0123456789abcdef0",
                "ConsumedQuantity": 1.0,
                "ConsumedUnit": "Hours",
                "PricingQuantity": 1.0,
                "PricingUnit": "Hours",
                "BilledCost": 0.096,
                "EffectiveCost": 0.096,
                "ContractedCost": 0.096,
                "ListCost": 0.096,
                "ContractedUnitPrice": 0.096,
                "ListUnitPrice": 0.096,
                "Tags": '{"env": "test"}',
            }
        )

    # 10 hourly rows for Elastic Load Balancing
    for i in range(10):
        start_hour = f"2024-09-18 {i:02d}:00:00"
        end_hour = f"2024-09-18 {i + 1:02d}:00:00"
        rows.append(
            {
                "Id": 2000 + i,
                "ProviderName": "AWS",
                "BillingAccountId": "123456789012",
                "BillingAccountName": "TestAccount",
                "SubAccountId": "987654321098",
                "SubAccountName": "TestProject",
                "BillingPeriodStart": "2024-09-01 00:00:00",
                "BillingPeriodEnd": "2024-10-01 00:00:00",
                "ChargePeriodStart": start_hour,
                "ChargePeriodEnd": end_hour,
                "BillingCurrency": "USD",
                "ChargeCategory": "Usage",
                "ChargeFrequency": "Usage-Based",
                "ChargeDescription": "Application Load Balancer",
                "ServiceCategory": "Networking",
                "ServiceName": "Elastic Load Balancing",
                "RegionId": "us-west-2",
                "RegionName": "US West (Oregon)",
                "ResourceId": "arn:aws:elasticloadbalancing:us-west-2:app/alb-1",
                "ConsumedQuantity": 0.5,
                "ConsumedUnit": "LCU-Hours",
                "PricingQuantity": 0.5,
                "PricingUnit": "LCU-Hours",
                "BilledCost": 0.004,
                "EffectiveCost": 0.004,
                "ContractedCost": 0.004,
                "ListCost": 0.004,
                "ContractedUnitPrice": 0.008,
                "ListUnitPrice": 0.008,
                "Tags": '{"env": "test"}',
            }
        )

    return pd.DataFrame(rows)


@pytest.fixture
def tiny_focus_csv(tmp_path, tiny_focus_dataframe: pd.DataFrame):
    """Save tiny synthetic dataframe to a temporary CSV file."""
    csv_file = tmp_path / "tiny_focus_sample.csv"
    tiny_focus_dataframe.to_csv(csv_file, index=False)
    return csv_file
