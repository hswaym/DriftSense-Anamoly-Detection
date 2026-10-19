"""Time-Series Forecast & Anomaly Detection View for DriftSense Dashboard."""

from __future__ import annotations

import numpy as np
import pandas as pd
import streamlit as st


def render_forecast_anomalies(
    detections_df: pd.DataFrame,
    track: str = "Real Track (Uncorrupted)",
) -> None:
    """Render the time-series forecasting and anomaly exploration view."""
    st.subheader("Time-Series Cost Forecasting & Dynamic Anomaly Alerts")
    st.markdown(
        """
        Interactive inspection of hourly cloud spend across services. 
        Residuals $e(t) = y(t) - \\hat{y}(t)$ are monitored via the champion 
        <strong>Rolling Dynamic Threshold</strong> detector ($w=24\\text{h}, k=3.0\\sigma$) to flag anomalous cost jumps.
        """,
        unsafe_allow_html=True,
    )

    if detections_df.empty:
        st.warning("⚠️ No detections data available to display.")
        return

    is_synth = "synthetic" in track.lower()
    actual_col = "cost_actual_synth" if is_synth else "cost_actual_clean"
    residual_col = "residual_synth" if is_synth else "residual_clean"
    alert_col = (
        "alert_synth_rolling_threshold" if is_synth else "alert_clean_rolling_threshold"
    )

    # Service selector
    all_services = sorted(detections_df["ServiceName"].unique())
    selected_service = st.selectbox(
        "Select Cloud Service to Inspect:",
        options=["All Services Combined"] + all_services,
        index=0,
    )

    if selected_service == "All Services Combined":
        df_sub = (
            detections_df.groupby("ChargePeriodStart")[
                [actual_col, residual_col, alert_col]
            ]
            .agg({actual_col: "sum", residual_col: "sum", alert_col: "max"})
            .reset_index()
        )
    else:
        df_sub = detections_df[detections_df["ServiceName"] == selected_service].copy()

    df_sub = df_sub.sort_values("ChargePeriodStart")
    df_sub["expected_cost"] = np.maximum(0.0, df_sub[actual_col] - df_sub[residual_col])

    # Summary metrics for current selection
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("Total Observed Spend", f"${df_sub[actual_col].sum():,.2f}")
    with c2:
        st.metric("Mean Hourly Spend", f"${df_sub[actual_col].mean():,.2f}")
    with c3:
        st.metric("Peak Hourly Spend", f"${df_sub[actual_col].max():,.2f}")
    with c4:
        n_alerts = int(df_sub[alert_col].sum())
        st.metric(
            "Triggered Alarms",
            f"{n_alerts} hours",
            delta=f"{n_alerts / len(df_sub) * 100:.1f}% of window",
        )

    st.markdown("### Spend vs. Expected Baseline Over Time")

    # Chart 1: Actual vs Expected
    chart_data = df_sub.set_index("ChargePeriodStart")[
        [actual_col, "expected_cost"]
    ].copy()
    chart_data.columns = ["Observed Actual ($)", "Expected Cost Baseline ($)"]
    st.line_chart(chart_data)

    # Chart 2: Residuals & Threshold Alerts
    st.markdown(
        "### Residual Error $e(t) = y(t) - \\hat{y}(t)$ & Triggered Control Limits"
    )
    res_data = df_sub.set_index("ChargePeriodStart")[[residual_col]].copy()
    res_data.columns = ["Residual Error ($)"]
    st.area_chart(res_data, color="#F59E0B")

    # Table of Anomalous Incidents
    anomaly_rows = df_sub[df_sub[alert_col] == 1].copy()
    st.markdown(f"### Detected Anomaly Points ({len(anomaly_rows)} occurrences)")
    if not anomaly_rows.empty:
        table_cols = ["ChargePeriodStart", actual_col, "expected_cost", residual_col]
        if "ServiceName" in anomaly_rows.columns:
            table_cols.insert(1, "ServiceName")

        display_tbl = anomaly_rows[table_cols].copy()
        display_tbl.columns = [
            "Timestamp (UTC)",
            *(["Service"] if "ServiceName" in anomaly_rows.columns else []),
            "Observed Cost ($)",
            "Expected Baseline ($)",
            "Cost Discrepancy ($)",
        ]
        st.dataframe(display_tbl, hide_index=True, use_container_width=True)
    else:
        st.info(
            "✅ No anomaly threshold excursions detected for this service during this window."
        )
