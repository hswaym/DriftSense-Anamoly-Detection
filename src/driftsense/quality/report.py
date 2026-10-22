"""Data quality report generator emitting JSON and Markdown summaries."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from driftsense.quality.score import QualityScoreResult, calculate_quality_score


def generate_quality_report(
    df: pd.DataFrame,
    dataset_name: str = "Billing Dataset",
    output_json: str | Path | None = None,
    output_md: str | Path | None = None,
) -> dict[str, Any]:
    """Generate comprehensive quality report in JSON and Markdown formats."""
    result: QualityScoreResult = calculate_quality_score(df)

    report_dict: dict[str, Any] = {
        "dataset_name": dataset_name,
        "total_rows": result.total_rows,
        "quality_score": result.score,
        "grade": result.grade,
        "total_deductions": result.total_deductions,
        "summary": result.summary,
        "deductions": [
            {
                "category": d.category,
                "points_deducted": d.points_deducted,
                "reason": d.plain_language_reason,
                "actionable_fix": d.actionable_fix,
                "metrics": d.metrics,
            }
            for d in result.deductions
        ],
    }

    if output_json:
        p_json = Path(output_json)
        p_json.parent.mkdir(parents=True, exist_ok=True)
        p_json.write_text(json.dumps(report_dict, indent=2), encoding="utf-8")

    if output_md:
        p_md = Path(output_md)
        p_md.parent.mkdir(parents=True, exist_ok=True)
        md_text = _format_markdown_report(report_dict)
        p_md.write_text(md_text, encoding="utf-8")

    return report_dict


def _format_markdown_report(report: dict[str, Any]) -> str:
    """Format dictionary into human-readable Markdown report."""
    md = [
        f"# Data Quality Report: {report['dataset_name']}\n",
        f"**Quality Score:** {report['quality_score']}/100 (**Grade: {report['grade']}**)  ",
        f"**Total Records Evaluated:** {report['total_rows']:,}  ",
        f"**Status Summary:** {report['summary']}\n",
        "---",
        "## Quality Assessment Breakdown\n",
    ]

    if not report["deductions"]:
        md.append("✅ **No quality defects detected.** Dataset is fully compliant with FOCUS v2 standards.\n")
    else:
        md.append("| Category | Points Deducted | Plain-Language Reason | Actionable Remediation |")
        md.append("|---|---|---|---|")
        for d in report["deductions"]:
            cat = d["category"].replace("_", " ").title()
            md.append(f"| **{cat}** | -{d['points_deducted']} | {d['reason']} | {d['actionable_fix']} |")
        md.append("\n")

    return "\n".join(md)
