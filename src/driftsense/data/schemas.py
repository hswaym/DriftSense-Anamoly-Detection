"""Canonical schema specifications and column metadata for DriftSense datasets."""

from __future__ import annotations

# Core FOCUS columns essential for modeling
FOCUS_CORE_COLUMNS: list[str] = [
    "ChargePeriodStart",
    "ChargePeriodEnd",
    "ServiceName",
    "EffectiveCost",
    "BilledCost",
    "ConsumedQuantity",
    "ConsumedUnit",
    "BillingCurrency",
]

# Standard FOCUS 1.0 / 1.3 column types mapping
FOCUS_SCHEMA: dict[str, str] = {
    "AvailabilityZone": "string",
    "BilledCost": "float64",
    "BillingAccountId": "string",
    "BillingAccountName": "string",
    "BillingCurrency": "string",
    "BillingPeriodEnd": "string",
    "BillingPeriodStart": "string",
    "ChargeCategory": "string",
    "ChargeClass": "string",
    "ChargeDescription": "string",
    "ChargeFrequency": "string",
    "ChargePeriodEnd": "string",
    "ChargePeriodStart": "string",
    "CommitmentDiscountCategory": "string",
    "CommitmentDiscountId": "string",
    "CommitmentDiscountName": "string",
    "CommitmentDiscountStatus": "string",
    "CommitmentDiscountType": "string",
    "ConsumedQuantity": "float64",
    "ConsumedUnit": "string",
    "ContractedCost": "float64",
    "ContractedUnitPrice": "float64",
    "EffectiveCost": "float64",
    "InvoiceIssuerName": "string",
    "ListCost": "float64",
    "ListUnitPrice": "float64",
    "PricingCategory": "string",
    "PricingQuantity": "float64",
    "PricingUnit": "string",
    "ProviderName": "string",
    "PublisherName": "string",
    "RegionId": "string",
    "RegionName": "string",
    "ResourceId": "string",
    "ResourceName": "string",
    "ResourceType": "string",
    "ServiceCategory": "string",
    "Id": "string",
    "ServiceName": "string",
    "SkuId": "string",
    "SkuPriceId": "string",
    "SubAccountId": "string",
    "SubAccountName": "string",
    "Tags": "string",
}

EVENT_SCHEMA: dict[str, str] = {
    "event_id": "string",
    "ts_start": "string",
    "ts_end": "string",
    "service_id": "string",
    "event_type": "string",
    "event_source": "string",
    "is_synthetic": "bool",
    "metadata_json": "string",
}

ANOMALY_LABEL_SCHEMA: dict[str, str] = {
    "label_id": "string",
    "service_id": "string",
    "onset_timestamp": "string",
    "offset_timestamp": "string",
    "primary_cause": "string",
    "contributing_causes": "string",
    "is_synthetic": "bool",
    "severity_score": "float64",
    "verification_src": "string",
}
