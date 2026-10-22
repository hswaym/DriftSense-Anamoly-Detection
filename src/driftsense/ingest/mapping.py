"""Column mapping engine with intelligent suggestion routing.

Maps arbitrary cloud billing headers to canonical FOCUS fields.
Ensures unknown columns are routed to mapping suggestions with confidence scores
and never silently discarded.
"""

from __future__ import annotations

import difflib
import re
from dataclasses import dataclass, field

from driftsense.ingest.canonical import CANONICAL_COLUMNS


@dataclass
class ColumnMappingResult:
    """Result of mapping columns to canonical schema."""
    canonical_map: dict[str, str]  # raw_col -> canonical_col
    unmapped_columns: list[str] = field(default_factory=list)
    suggestions: dict[str, tuple[str, float]] = field(default_factory=dict)  # raw_col -> (suggested_col, confidence)
    dropped_internal_columns: list[str] = field(default_factory=list)


# Synonyms dictionary for heuristic matching
SYNONYM_RULES: dict[str, list[str]] = {
    "ChargePeriodStart": [
        "start_time", "starttime", "usage_start", "usagestartdate",
        "date", "billing_start", "charge_start", "from_date", "interval_start"
    ],
    "ChargePeriodEnd": [
        "end_time", "endtime", "usage_end", "usageenddate",
        "billing_end", "charge_end", "to_date", "interval_end"
    ],
    "BilledCost": [
        "cost", "billed_cost", "unblended_cost", "unblendedcost",
        "amount", "invoice_amount", "pretax_cost", "total_cost", "cost_amount"
    ],
    "EffectiveCost": [
        "effective_cost", "net_cost", "amortized_cost", "netunblendedcost",
        "discounted_cost", "actual_cost"
    ],
    "ListCost": [
        "list_cost", "retail_cost", "ondemand_cost", "original_cost"
    ],
    "ConsumedQuantity": [
        "quantity", "usage_quantity", "usage_amount", "consumed_units",
        "usage", "usageamount", "consumed_quantity"
    ],
    "ConsumedUnit": [
        "unit", "unit_of_measure", "pricing_unit", "usage_unit", "unitofmeasure"
    ],
    "ServiceName": [
        "service", "service_name", "product_name", "product_code",
        "servicecode", "meter_category", "service_description"
    ],
    "SubAccountId": [
        "account_id", "subscription_id", "project_id", "account",
        "subaccount_id", "usage_account_id", "linked_account_id"
    ],
    "SubAccountName": [
        "account_name", "subscription_name", "project_name", "subaccount_name"
    ],
    "ResourceId": [
        "resource_id", "resource_arn", "instance_id", "resource_name", "arn"
    ],
    "RegionId": [
        "region", "region_id", "location", "resource_location", "availability_zone"
    ],
    "ChargeCategory": [
        "charge_type", "line_item_type", "category", "item_type", "charge_category"
    ],
    "Currency": [
        "currency", "billing_currency", "currency_code", "unit_currency"
    ],
    "Tags": [
        "tags", "labels", "resource_tags", "tag_list", "custom_tags"
    ],
}


def clean_col_name(name: str) -> str:
    """Normalize column name for matching."""
    return re.sub(r"[^a-zA-Z0-9]", "", name).lower()


def build_column_mapping(
    raw_columns: list[str],
    provider_explicit_map: dict[str, str] | None = None,
    fuzzy_threshold: float = 0.65,
) -> ColumnMappingResult:
    """Build column mapping for incoming raw headers."""
    canonical_map: dict[str, str] = {}
    unmapped: list[str] = []
    suggestions: dict[str, tuple[str, float]] = {}

    assigned_canonical: set[str] = set()

    # 1. Apply explicit provider mapping first
    if provider_explicit_map:
        for raw_col, canon_col in provider_explicit_map.items():
            if raw_col in raw_columns and canon_col in CANONICAL_COLUMNS:
                canonical_map[raw_col] = canon_col
                assigned_canonical.add(canon_col)

    # 2. Match exact case or cleaned names to canonical columns
    for raw_col in raw_columns:
        if raw_col in canonical_map:
            continue

        # Exact match
        if raw_col in CANONICAL_COLUMNS and raw_col not in assigned_canonical:
            canonical_map[raw_col] = raw_col
            assigned_canonical.add(raw_col)
            continue

        cleaned = clean_col_name(raw_col)

        # Check cleaned match
        matched_canon = None
        for canon in CANONICAL_COLUMNS:
            if canon in assigned_canonical:
                continue
            if clean_col_name(canon) == cleaned:
                matched_canon = canon
                break

        if matched_canon:
            canonical_map[raw_col] = matched_canon
            assigned_canonical.add(matched_canon)
            continue

        # Check synonym rules
        synonym_match = None
        for canon, synonyms in SYNONYM_RULES.items():
            if canon in assigned_canonical:
                continue
            if any(clean_col_name(s) == cleaned for s in synonyms):
                synonym_match = canon
                break

        if synonym_match:
            canonical_map[raw_col] = synonym_match
            assigned_canonical.add(synonym_match)
            continue

        # 3. Fuzzy match to suggest candidate
        best_match = None
        best_score = 0.0
        for canon in CANONICAL_COLUMNS:
            score = difflib.SequenceMatcher(None, cleaned, clean_col_name(canon)).ratio()
            # Also check against synonyms
            for s in SYNONYM_RULES.get(canon, []):
                syn_score = difflib.SequenceMatcher(None, cleaned, clean_col_name(s)).ratio()
                score = max(score, syn_score)

            if score > best_score:
                best_score = score
                best_match = canon

        if best_match and best_score >= fuzzy_threshold:
            suggestions[raw_col] = (best_match, round(best_score, 3))
        unmapped.append(raw_col)

    return ColumnMappingResult(
        canonical_map=canonical_map,
        unmapped_columns=unmapped,
        suggestions=suggestions,
    )
