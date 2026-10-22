"""Versioned, non-causal executive narrative templates for DriftSense v2 (Phase 9).

Provides structured plain-language reporting for finance managers and audit
engineers, cleanly separating executive takeaways from technical TreeSHAP details.
"""

from __future__ import annotations

from typing import Any

from driftsense.explain.validator import DISCLAIMER_TEXT, validate_non_causal_text

TEMPLATE_VERSION = "2.0.0"

# Generic, non-prescriptive investigative checks mapped to taxonomy causes
SUGGESTED_NEXT_CHECKS = {
    "DEPLOYMENT_DEFECT": [
        "Review recent CI/CD deployment pipelines, build releases, and container image rollouts.",
        "Check application error rates and memory usage immediately following the latest deployment window.",
        "Verify whether any rollback or hotfix was scheduled for this service.",
    ],
    "AUTOSCALING_OVERPROVISION": [
        "Inspect autoscaling policy min/max thresholds and horizontal pod autoscaler (HPA) metrics.",
        "Check whether instance types or node pool sizes were scaled up during off-peak hours.",
        "Review CPU/Memory target utilization metrics relative to provisioned capacity.",
    ],
    "CONFIG_MODIFICATION": [
        "Audit cloud infrastructure audit logs (e.g. CloudTrail / Audit Logs) for recent configuration changes.",
        "Verify changes in provisioned IOPS, storage tier configurations, or network routing rules.",
        "Confirm whether automated terraform or infrastructure-as-code updates were recently applied.",
    ],
    "EXTERNAL_TRAFFIC_SURGE": [
        "Inspect ingress API gateway request volume, CDN cache hit ratios, and public bandwidth.",
        "Check marketing schedules or external promotional events coincident with the surge.",
        "Examine client IP distribution to assess whether traffic is legitimate or automated scraping.",
    ],
    "ORPHANED_STORAGE_ACCUMULATION": [
        "Audit detached EBS volumes, unattached static IPs, and unreferenced snapshot archives.",
        "Check S3/Blob lifecycle rules for non-current version deletion or Glacier transitioning.",
        "Review multi-part upload buckets for incomplete or dangling chunks.",
    ],
    "RUNAWAY_BATCH_PROCESS": [
        "Inspect cron schedules, batch worker queues, and ETL pipeline execution logs.",
        "Verify whether retry loops or unhandled exceptions caused runaway re-executions.",
        "Review duration and concurrency graphs of background data processing jobs.",
    ],
    "DEFAULT": [
        "Inspect service-level billing detail reports for unexpected line-item quantity increases.",
        "Review cloud monitoring dashboards for sudden CPU, storage, or network departures.",
        "Cross-reference recent operational change tickets with the timing of the cost surge.",
    ],
}

KNOWN_UNKNOWNS_ITEMS = [
    "External third-party SaaS fees and marketplace charges outside standard FOCUS billing are not reflected in this analysis.",
    "Granular application-level request payloads and internal code traces are unobserved in cloud telemetry.",
    "Contractual custom credit adjustments and end-of-quarter volume discounts may lag up to 48 hours in cloud billing exports.",
]


def render_narrative_template_v2(
    service_name: str,
    timestamp: str,
    actual_cost: float,
    expected_cost: float,
    sub_account_id: str = "Unspecified Account",
    region_id: str = "Global / Multi-Region",
    duration_hours: float | None = None,
    ranked_reasons: list[dict[str, Any]] | None = None,
    suggested_checks: list[str] | None = None,
    known_unknowns: list[str] | None = None,
    expert_details: dict[str, Any] | None = None,
) -> str:
    """Render a fully structured, non-causal plain-language executive narrative.

    Structure:
    1. Executive Summary & Cost Deviation (What happened)
    2. Dimensions of Impact (Where: service, subaccount, region)
    3. Temporal Scope (When)
    4. Correlated Drivers & Operational Signals (Likely reasons with confidence)
    5. Suggested Next Investigative Steps (Generic & non-prescriptive)
    6. Known Unknowns (Explicit boundary of analysis)
    7. Expert Details (Collapsible TreeSHAP attributions & additivity check)
    8. Non-Causal Regulatory Disclaimer

    All output is automatically verified by the non-causal copy validator.
    """
    delta = actual_cost - expected_cost
    pct_increase = (delta / expected_cost * 100.0) if expected_cost > 0 else 0.0

    lines: list[str] = []

    # 1. Header & What Happened
    lines.append(f"# Executive Cost Anomaly Brief: {service_name}")
    lines.append(f"*Template Version: {TEMPLATE_VERSION}* | *Observation Period: `{timestamp}`*\n")

    lines.append("## 1. What Happened")
    lines.append(
        f"Observed cloud spend reached **${actual_cost:,.2f}**, departing from the expected baseline "
        f"of **${expected_cost:,.2f}**. This represents an unexpected deviation of "
        f"**+${delta:,.2f}** (**{pct_increase:+.1f}%** relative to baseline expectation)."
    )

    # 2. Where (Dimensions of Impact)
    lines.append("\n## 2. Where")
    lines.append(f"- **Primary Service:** `{service_name}`")
    lines.append(f"- **Billing Sub-Account:** `{sub_account_id}`")
    lines.append(f"- **Operating Region:** `{region_id}`")

    # 3. When (Temporal Scope)
    lines.append("\n## 3. When")
    lines.append(f"- **Onset Timestamp:** `{timestamp}`")
    if duration_hours is not None:
        lines.append(f"- **Estimated Anomaly Window:** `{duration_hours:.1f} hours`")
    else:
        lines.append("- **Estimated Anomaly Window:** `Single observation period (1h grain)`")

    # 4. Likely Reasons & Operational Signals
    lines.append("\n## 4. Likely Correlated Reasons")
    if ranked_reasons:
        for idx, reason in enumerate(ranked_reasons[:3], 1):
            cause = reason.get("cause", "UNKNOWN_CAUSE")
            conf = reason.get("confidence", "Medium")
            rationale = reason.get("rationale", "")
            share = reason.get("percentage_share", 0.0)
            share_text = f" (~{share*100:.1f}% share)" if share > 0 else ""
            lines.append(f"### {idx}. {cause.replace('_', ' ').title()}{share_text}")
            lines.append(f"- **Confidence Assessment:** `{conf}`")
            if rationale:
                lines.append(f"- **Statistical Evidence:** {rationale}")
    else:
        lines.append("- No operational change events were correlated within the observation window.")

    # 5. Suggested Next Checks (Generic & Non-Prescriptive)
    lines.append("\n## 5. Suggested Investigative Next Steps")
    checks = suggested_checks
    if not checks and ranked_reasons:
        top_cause = ranked_reasons[0].get("cause", "DEFAULT")
        checks = SUGGESTED_NEXT_CHECKS.get(top_cause, SUGGESTED_NEXT_CHECKS["DEFAULT"])
    elif not checks:
        checks = SUGGESTED_NEXT_CHECKS["DEFAULT"]

    for check in checks:
        lines.append(f"- [ ] {check}")

    # 6. What We Are Not Sure About (Known Unknowns)
    lines.append("\n## 6. What We Are Not Sure About (Known Unknowns)")
    unknowns = known_unknowns or KNOWN_UNKNOWNS_ITEMS
    for item in unknowns:
        lines.append(f"- {item}")

    # 7. Expert Details (TreeSHAP Attributions & Diagnostics)
    if expert_details:
        lines.append("\n## 7. Expert Details & Model Feature Attributions")
        lines.append("<details>")
        lines.append("<summary>Click to expand technical TreeSHAP attributions and diagnostic checks</summary>\n")

        pred_id = expert_details.get("prediction_id", "unspecified")
        model_id = expert_details.get("model_id", "XGBoostForecaster")
        additivity_ok = expert_details.get("additivity_verified", True)
        additivity_err = expert_details.get("additivity_error", 0.0)

        lines.append(f"- **Prediction ID:** `{pred_id}`")
        lines.append(f"- **Forecasting Model:** `{model_id}`")
        lines.append(f"- **TreeSHAP Additivity Verified (A9.1):** `{additivity_ok}` (error: `{additivity_err:.2e}`)")

        top_drivers = expert_details.get("top_drivers", [])
        if top_drivers:
            lines.append("\n**Top Local Feature Attributions (TreeSHAP $\\phi_j$):**")
            lines.append("| Rank | Feature Name | SHAP Value ($) | Relative Impact |")
            lines.append("| :--- | :--- | :--- | :--- |")
            total_val = sum(abs(v) for _, v in top_drivers)
            for r, (feat, val) in enumerate(top_drivers, 1):
                rel = (abs(val) / total_val * 100.0) if total_val > 0 else 0.0
                lines.append(f"| {r} | `{feat}` | `${val:+,.2f}` | {rel:.1f}% |")

        lines.append("\n</details>")

    # 8. Mandatory Non-Causal Disclaimer
    lines.append(f"\n> [!NOTE]\n> {DISCLAIMER_TEXT}")

    rendered = "\n".join(lines)

    # Strict A9.3 Validation
    validate_non_causal_text(rendered)
    return rendered
