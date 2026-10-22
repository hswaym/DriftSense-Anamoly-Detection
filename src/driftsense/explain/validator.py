"""Non-causal copy validator for DriftSense v2 (Phase 9).

CRITICAL NON-CAUSAL WORDING INVARIANT (A9.2 & A9.3):
    Narratives explain statistical associations, feature contributions, and
    temporal coincidences. They NEVER use causal-proof wording or certainty
    assertions such as 'caused by', 'triggered by', 'resulted from', 'due to',
    'proves that', 'is responsible for', or 'definitive cause'.
"""

from __future__ import annotations

import re
from typing import Any

# Mandatory non-causal disclaimer appended to all FinOps narrative reports
DISCLAIMER_TEXT = (
    "NOTE: Statistical feature attributions indicate correlation and model feature weighting, "
    "not verified physical causation. Operational verification with engineering logs is recommended."
)

# Extended forbidden phrases and regex patterns that assert certainty or definitive causality
FORBIDDEN_CAUSAL_PATTERNS = [
    r"\bcaused by\b",
    r"\btriggered by\b",
    r"\bresulted from\b",
    r"\bdue to\b",
    r"\bproves that\b",
    r"\bis the cause\b",
    r"\bwas the cause\b",
    r"\bis responsible for\b",
    r"\bwas responsible for\b",
    r"\bdefinitive cause\b",
    r"\bproven cause\b",
    r"\bconclusively attributable\b",
    r"\bundeniably caused\b",
]

_COMPILED_FORBIDDEN = [
    re.compile(pattern, re.IGNORECASE) for pattern in FORBIDDEN_CAUSAL_PATTERNS
]


def find_forbidden_phrases(text: str) -> list[str]:
    """Find all instances of forbidden causal-certainty wording in text."""
    matches = []
    for pattern in _COMPILED_FORBIDDEN:
        found = pattern.findall(text)
        if found:
            matches.extend(found)
    return sorted(set(matches))


def validate_non_causal_text(text: str) -> None:
    """Validate that text does not contain forbidden causal-proof or certainty wording.

    Raises:
        ValueError: If any forbidden phrase is found (A9.3 invariant).
    """
    forbidden = find_forbidden_phrases(text)
    if forbidden:
        joined = ", ".join(f"'{p}'" for p in forbidden)
        raise ValueError(
            f"A9.3 Non-Causal Wording Violation: Found forbidden certainty/causal phrase(s) {joined} in text:\n{text}"
        )


def validate_all_templates(templates: dict[str, Any]) -> None:
    """Validate that all registered templates strictly adhere to non-causal rules.

    Iterates through template strings or template generators in a dictionary.
    """
    for tmpl in templates.values():
        if isinstance(tmpl, str):
            validate_non_causal_text(tmpl)
        elif hasattr(tmpl, "template_str") and isinstance(tmpl.template_str, str):
            validate_non_causal_text(tmpl.template_str)
