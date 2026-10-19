"""Root-Cause Attribution & Incident Analysis View for DriftSense Dashboard."""

from __future__ import annotations

import pandas as pd
import streamlit as st


def render_attribution(attributions_df: pd.DataFrame) -> None:
    """Render the root-cause attribution view adhering strictly to non-causal terminology."""
    st.subheader("Root-Cause Attribution & Audit Evidence Analysis")
    st.markdown(
        """
        Investigate operational incidents and evaluate **likely associated causes** aligned 
        with cloud infrastructure events (deployments, autoscaling surges, configuration changes).
        <br>
        <em>All model scores represent <strong>model evidence</strong> and statistical precedence, 
        not physical proof of causation.</em>
        """,
        unsafe_allow_html=True,
    )

    if attributions_df.empty:
        st.warning("⚠️ No incident attribution records available.")
        return

    # Incident Selector
    incident_options = attributions_df["incident_id"].tolist()
    selected_id = st.selectbox(
        "Select Cost Anomaly Incident to Investigate:",
        options=incident_options,
        format_func=lambda x: (
            f"{x} — {attributions_df.loc[attributions_df['incident_id'] == x, 'service_name'].iloc[0]} ({str(attributions_df.loc[attributions_df['incident_id'] == x, 'start_timestamp'].iloc[0])[:19]})"
        ),
    )

    incident_row = attributions_df[attributions_df["incident_id"] == selected_id].iloc[
        0
    ]

    # Incident Overview Cards
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown(
            f"**Impacted Cloud Service:**<br>`{incident_row['service_name']}`",
            unsafe_allow_html=True,
        )
    with c2:
        st.markdown(
            f"**Incident Onset Time:**<br>`{str(incident_row['start_timestamp'])[:19]} UTC`",
            unsafe_allow_html=True,
        )
    with c3:
        st.markdown(
            f"**Validation Ground-Truth Cause:**<br><span style='color: #38BDF8; font-weight: 700;'>{incident_row.get('primary_cause_true', 'N/A')}</span>",
            unsafe_allow_html=True,
        )

    st.markdown("---")
    st.markdown("### Model Evidence for Likely Associated Causes")

    col_corr, col_xgb, col_prior = st.columns(3)

    with col_corr:
        st.markdown(
            """
            <div style="background: #1E293B; padding: 16px; border-radius: 8px; border-left: 4px solid #38BDF8;">
                <h4 style="margin: 0 0 12px 0; color: #F8FAFC;">Temporal Precedence Champion</h4>
                <p style="font-size: 12px; color: #94A3B8; margin-bottom: 8px;">Exponential decay across operational event timeline</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.markdown(f"**Rank 1 (Primary):** `{incident_row['correlation_top1']}`")
        st.markdown(f"**Rank 2:** `{incident_row['correlation_top2']}`")
        st.markdown(f"**Rank 3:** `{incident_row['correlation_top3']}`")

    with col_xgb:
        st.markdown(
            """
            <div style="background: #1E293B; padding: 16px; border-radius: 8px; border-left: 4px solid #10B981;">
                <h4 style="margin: 0 0 12px 0; color: #F8FAFC;">Multi-Modal XGBoost Ranker</h4>
                <p style="font-size: 12px; color: #94A3B8; margin-bottom: 8px;">Joint telemetry jump and event metadata classification</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.markdown(f"**Rank 1 (Primary):** `{incident_row['xgb_attributor_top1']}`")
        st.markdown(f"**Rank 2:** `{incident_row['xgb_attributor_top2']}`")
        st.markdown(f"**Rank 3:** `{incident_row['xgb_attributor_top3']}`")

    with col_prior:
        st.markdown(
            """
            <div style="background: #1E293B; padding: 16px; border-radius: 8px; border-left: 4px solid #64748B;">
                <h4 style="margin: 0 0 12px 0; color: #F8FAFC;">Empirical Class Prior Baseline</h4>
                <p style="font-size: 12px; color: #94A3B8; margin-bottom: 8px;">Static historical frequency without event telemetry</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.markdown(f"**Rank 1 (Primary):** `{incident_row['prior_baseline_top1']}`")
        st.markdown(f"**Rank 2:** `{incident_row['prior_baseline_top2']}`")
        st.markdown(f"**Rank 3:** `{incident_row['prior_baseline_top3']}`")

    st.markdown("<br>", unsafe_allow_html=True)

    # Decoy Rejection Verification Box
    st.info(
        "💡 **Decoy Rejection & Precedence Invariant:** The Temporal Correlation attributor uses a 3.0h lookback window "
        "with a 1.0h exponential half-life decay. Concurrent benign operations (e.g. background maintenance or routine batch jobs) "
        "are successfully rejected in favor of the temporally contiguous operational trigger."
    )

    # Full Attributions Summary Table
    st.markdown("### Complete Validation Incident Portfolio")
    summary_cols = [
        "incident_id",
        "service_name",
        "start_timestamp",
        "primary_cause_true",
        "correlation_top1",
        "xgb_attributor_top1",
    ]
    summary_view = attributions_df[summary_cols].copy()
    summary_view.columns = [
        "Incident ID",
        "Service",
        "Onset Timestamp",
        "True Cause",
        "Precedence Rank-1",
        "XGBoost Rank-1",
    ]
    st.dataframe(summary_view, hide_index=True, use_container_width=True)
