"""Format detection engine for multi-cloud billing files.

Detects cloud provider formats (FOCUS, AWS CUR, Azure Cost Management, GCP Billing)
and FOCUS specification versions (1.0 through 1.4).
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path


@dataclass
class FormatDetectionResult:
    """Result of billing format detection."""
    provider: str  # 'FOCUS', 'AWS_CUR', 'AZURE_COST', 'GCP_BILLING', 'UNKNOWN'
    version: str   # '1.0', '1.1', '1.2', '1.3', '1.4', 'CUR_2.0', 'EXPORT_V1', 'UNKNOWN'
    confidence: float
    delimiter: str
    encoding: str
    header_columns: list[str]
    sample_row_count: int


# Characteristic signature columns
FOCUS_SIGNATURE_COLS = {
    "ChargePeriodStart",
    "ChargePeriodEnd",
    "BilledCost",
    "EffectiveCost",
    "ConsumedQuantity",
    "ConsumedUnit",
    "ServiceName",
    "ProviderName",
}

AWS_CUR_SIGNATURE_COLS = {
    "lineItem/UnblendedCost",
    "lineItem/LineItemDescription",
    "lineItem/UsageAmount",
    "lineItem/UsageStartDate",
    "pricing/unit",
    "product/servicecode",
}

AZURE_SIGNATURE_COLS = {
    "CostInBillingCurrency",
    "UsageQuantity",
    "MeterCategory",
    "SubscriptionId",
    "ResourceLocation",
    "Date",
}

GCP_SIGNATURE_COLS = {
    "cost",
    "usage_start_time",
    "usage_end_time",
    "service.description",
    "project.id",
    "usage.amount",
}


def detect_file_encoding_and_delimiter(
    file_path: str | Path,
    sample_bytes: int = 65536,
) -> tuple[str, str]:
    """Detect file character encoding and CSV delimiter.

    Raises:
        ValueError: If file encoding is invalid or delimiter cannot be deduced.
    """
    path = Path(file_path)
    if not path.is_file():
        raise FileNotFoundError(f"File not found: {path}")

    raw_data = path.read_bytes()[:sample_bytes]
    if not raw_data:
        raise ValueError(f"File is completely empty: {path}")

    # 1. Detect encoding
    detected_encoding = "utf-8"
    encodings_to_try = ["utf-8-sig", "utf-8", "latin-1", "cp1252"]
    valid = False
    sample_text = ""

    for enc in encodings_to_try:
        try:
            sample_text = raw_data.decode(enc)
            # If utf-8 decoded successfully without null bytes
            if "\x00" in sample_text:
                continue
            detected_encoding = enc
            valid = True
            break
        except (UnicodeDecodeError, UnicodeError):
            continue

    if not valid:
        raise ValueError(
            f"Failed to decode '{path}' with standard encodings (utf-8, latin-1). "
            "Please check file encoding."
        )

    # 2. Detect delimiter
    first_line = sample_text.splitlines()[0] if sample_text.splitlines() else ""
    if not first_line:
        raise ValueError(f"File '{path}' does not contain any header line.")

    # Check common delimiters
    delimiter_counts = {
        ",": first_line.count(","),
        "\t": first_line.count("\t"),
        ";": first_line.count(";"),
        "|": first_line.count("|"),
    }
    sorted_delims = sorted(delimiter_counts.items(), key=lambda x: x[1], reverse=True)
    best_delim, count = sorted_delims[0]
    if count == 0:
        # Fallback to csv Sniffer
        try:
            sniffer = csv.Sniffer()
            dialect = sniffer.sniff(sample_text[:4096])
            best_delim = dialect.delimiter
        except Exception:
            best_delim = ","

    return detected_encoding, best_delim


def detect_format(file_path: str | Path) -> FormatDetectionResult:
    """Analyze headers and sample records to determine billing provider and schema version."""
    path = Path(file_path)
    encoding, delimiter = detect_file_encoding_and_delimiter(path)

    # Read first 10 lines
    lines: list[str] = []
    with open(path, "r", encoding=encoding, errors="replace") as f:
        reader = csv.reader(f, delimiter=delimiter)
        try:
            headers = next(reader)
        except StopIteration:
            raise ValueError(f"File '{path}' has no header row.")
        for _ in range(9):
            try:
                lines.append(next(reader))
            except StopIteration:
                break

    # Clean headers (strip BOM, whitespace, quotes)
    clean_headers = [h.strip().strip('"').strip("'") for h in headers]
    if not clean_headers or all(h == "" for h in clean_headers):
        raise ValueError(f"File '{path}' has an empty or invalid header row.")

    # Duplicate header check
    if len(clean_headers) != len(set(clean_headers)):
        dups = [h for h in clean_headers if clean_headers.count(h) > 1]
        raise ValueError(
            f"File '{path}' contains duplicate column names in header: {set(dups)}. "
            "Headers must be unique."
        )

    header_set = set(clean_headers)

    # 1. Test FOCUS
    focus_matches = header_set.intersection(FOCUS_SIGNATURE_COLS)
    if len(focus_matches) >= 4:
        # Determine FOCUS version
        version = "1.0"
        if "ContractedUnitPrice" in header_set or "CommitmentDiscountCategory" in header_set:
            version = "1.1"
        if "BillingPeriodStart" in header_set and "ListUnitPrice" in header_set:
            version = "1.2"
        if "SkuPriceId" in header_set or "PricingCategory" in header_set:
            version = "1.3"
        if "CapacityReservationId" in header_set:
            version = "1.4"
        confidence = min(1.0, len(focus_matches) / len(FOCUS_SIGNATURE_COLS) + 0.3)
        return FormatDetectionResult(
            provider="FOCUS",
            version=version,
            confidence=confidence,
            delimiter=delimiter,
            encoding=encoding,
            header_columns=clean_headers,
            sample_row_count=len(lines),
        )

    # 2. Test AWS CUR
    aws_matches = [h for h in clean_headers if any(sig in h for sig in AWS_CUR_SIGNATURE_COLS)]
    if len(aws_matches) >= 3 or any("lineItem/" in h for h in clean_headers):
        return FormatDetectionResult(
            provider="AWS_CUR",
            version="CUR_2.0" if any("resourceTags/" in h for h in clean_headers) else "CUR_1.0",
            confidence=min(1.0, len(aws_matches) / len(AWS_CUR_SIGNATURE_COLS) + 0.4),
            delimiter=delimiter,
            encoding=encoding,
            header_columns=clean_headers,
            sample_row_count=len(lines),
        )

    # 3. Test Azure Cost Management
    azure_matches = header_set.intersection(AZURE_SIGNATURE_COLS)
    if len(azure_matches) >= 3 or "CostInBillingCurrency" in header_set:
        return FormatDetectionResult(
            provider="AZURE_COST",
            version="EXPORT_V1",
            confidence=min(1.0, len(azure_matches) / len(AZURE_SIGNATURE_COLS) + 0.4),
            delimiter=delimiter,
            encoding=encoding,
            header_columns=clean_headers,
            sample_row_count=len(lines),
        )

    # 4. Test GCP Billing
    gcp_matches = [h for h in clean_headers if any(sig in h for sig in GCP_SIGNATURE_COLS)]
    if len(gcp_matches) >= 3 or ("cost" in header_set and "usage_start_time" in header_set):
        return FormatDetectionResult(
            provider="GCP_BILLING",
            version="EXPORT_V1",
            confidence=min(1.0, len(gcp_matches) / len(GCP_SIGNATURE_COLS) + 0.4),
            delimiter=delimiter,
            encoding=encoding,
            header_columns=clean_headers,
            sample_row_count=len(lines),
        )

    # Unknown
    return FormatDetectionResult(
        provider="UNKNOWN",
        version="UNKNOWN",
        confidence=0.0,
        delimiter=delimiter,
        encoding=encoding,
        header_columns=clean_headers,
        sample_row_count=len(lines),
    )
