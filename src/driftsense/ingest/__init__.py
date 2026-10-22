"""DriftSense Ingestion Engine.

Provides multi-cloud billing format detection, canonical schema adapters,
and robust data ingestion for FOCUS, AWS, Azure, and GCP.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import pandas as pd

from driftsense.ingest.adapters_aws_cur import adapt_aws_cur_data
from driftsense.ingest.adapters_azure import adapt_azure_data
from driftsense.ingest.adapters_focus import adapt_focus_data
from driftsense.ingest.adapters_gcp import adapt_gcp_data
from driftsense.ingest.canonical import (
    CANONICAL_COLUMNS,
    REQUIRED_CANONICAL_COLUMNS,
    enforce_canonical_types,
)
from driftsense.ingest.detect_format import FormatDetectionResult, detect_format
from driftsense.ingest.mapping import ColumnMappingResult, build_column_mapping

logger = logging.getLogger(__name__)


ADAPTER_REGISTRY = {
    "FOCUS": adapt_focus_data,
    "AWS_CUR": adapt_aws_cur_data,
    "AZURE_COST": adapt_azure_data,
    "GCP_BILLING": adapt_gcp_data,
}


def ingest_file(
    file_path: str | Path,
    provider: str = "auto",
    tenant_id: str = "00000000-0000-0000-0000-000000000000",
    default_currency: str = "USD",
    handle_refunds: str = "include",  # 'include', 'exclude', 'zero_clamp'
    dedup: str = "drop",             # 'drop', 'keep'
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Ingest arbitrary cloud billing file into canonical FOCUS format.

    Args:
        file_path: Path to raw CSV / Parquet billing export.
        provider: Target provider ('auto', 'FOCUS', 'AWS_CUR', 'AZURE_COST', 'GCP_BILLING').
        tenant_id: UUID tenant identifier.
        default_currency: Default ISO currency code.
        handle_refunds: Policy for negative cost entries.
        dedup: Policy for exact duplicate rows.

    Returns:
        tuple[pd.DataFrame, dict[str, Any]]: Cleaned canonical DataFrame and ingestion metadata.
    """
    path = Path(file_path)
    if not path.is_file():
        raise FileNotFoundError(f"Billing file not found: {path}")

    # 1. Format Detection
    detection: FormatDetectionResult = detect_format(path)
    detected_provider = detection.provider
    if provider != "auto":
        resolved_provider = provider.upper()
    else:
        resolved_provider = detected_provider

    logger.info(
        "Detected format for '%s': provider=%s, version=%s, confidence=%.2f",
        path.name,
        detection.provider,
        detection.version,
        detection.confidence,
    )

    # 2. Read DataFrame with detected encoding and delimiter
    if path.suffix.lower() in [".parquet", ".pq"]:
        df_raw = pd.read_parquet(path)
    else:
        df_raw = pd.read_csv(
            path,
            delimiter=detection.delimiter,
            encoding=detection.encoding,
            low_memory=False,
        )

    if df_raw.empty:
        raise ValueError(f"Billing file is empty (0 records): {path}")

    # 3. Apply Adapter
    unmapped_columns: list[str] = []
    suggestions: dict[str, tuple[str, float]] = {}

    if resolved_provider in ADAPTER_REGISTRY:
        adapter_fn = ADAPTER_REGISTRY[resolved_provider]
        df_canonical = adapter_fn(
            df_raw,
            tenant_id=tenant_id,
            default_currency=default_currency,
            handle_refunds=handle_refunds,
        )
    else:
        # Fallback to column mapping engine
        mapping_result: ColumnMappingResult = build_column_mapping(list(df_raw.columns))
        unmapped_columns = mapping_result.unmapped_columns
        suggestions = mapping_result.suggestions

        df_mapped = df_raw.rename(columns=mapping_result.canonical_map)
        df_canonical = enforce_canonical_types(
            df_mapped,
            tenant_id=tenant_id,
            default_currency=default_currency,
        )

    # 4. Deduplication
    initial_rows = len(df_canonical)
    dropped_duplicates = 0
    if dedup == "drop":
        dedup_keys = [
            c for c in ["ChargePeriodStart", "ServiceName", "ResourceId", "SubAccountId"]
            if c in df_canonical.columns
        ]
        if dedup_keys:
            df_canonical = df_canonical.drop_duplicates(subset=dedup_keys, keep="first").copy()
            dropped_duplicates = initial_rows - len(df_canonical)

    meta = {
        "file_name": path.name,
        "resolved_provider": resolved_provider,
        "detected_provider": detection.provider,
        "detected_version": detection.version,
        "detection_confidence": detection.confidence,
        "raw_rows": initial_rows,
        "canonical_rows": len(df_canonical),
        "dropped_duplicates": dropped_duplicates,
        "unmapped_columns": unmapped_columns,
        "mapping_suggestions": suggestions,
    }

    return df_canonical, meta


__all__ = [
    "CANONICAL_COLUMNS",
    "REQUIRED_CANONICAL_COLUMNS",
    "FormatDetectionResult",
    "adapt_aws_cur_data",
    "adapt_azure_data",
    "adapt_focus_data",
    "adapt_gcp_data",
    "build_column_mapping",
    "detect_format",
    "enforce_canonical_types",
    "ingest_file",
]
