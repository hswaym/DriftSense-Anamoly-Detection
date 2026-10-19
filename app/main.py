"""DriftSense — Executive FinOps Streamlit Application (Phase 11).

Specification: FinOps FOCUS 1.0 / 1.3
Requirements:
- Reads exported artifacts only. No model training in the app.
- Non-causal phrasing strictly enforced: 'likely associated causes', scores labelled 'model evidence'.
- No hardcoded absolute paths.
- Robust handling of missing or corrupt runs without tracebacks.
"""

from __future__ import annotations

import streamlit as st

from app.loaders import (
    get_default_runs_dir,
    load_ablation_data,
    load_attributions_data,
    load_detections_data,
    load_explainability_data,
    load_pipeline_state,
)
from app.views.ablations import render_ablations
from app.views.attribution import render_attribution
from app.views.explainability import render_explainability
from app.views.forecast_anomalies import render_forecast_anomalies
from app.views.overview import render_overview

# Page configuration
st.set_page_config(
    page_title="DriftSense | FinOps Cost Anomaly Control Center",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom executive CSS
st.markdown(
    """
    <style>
    /* Dark Executive Theme Styling */
    .stApp {
        background-color: #0B0F19;
        color: #E2E8F0;
    }
    div[data-testid="stSidebar"] {
        background-color: #0F172A;
        border-right: 1px solid #1E293B;
    }
    div[data-testid="stMetricValue"] {
        font-size: 26px !important;
        font-weight: 700 !important;
        color: #38BDF8 !important;
    }
    div[data-testid="stMetricLabel"] {
        font-size: 13px !important;
        color: #94A3B8 !important;
        font-weight: 500 !important;
    }
    div.stDataFrame {
        border-radius: 8px;
        overflow: hidden;
        border: 1px solid #334155;
    }
    hr {
        border-color: #334155 !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


def main() -> None:
    """Main dashboard application entry point."""
    runs_dir = get_default_runs_dir()
    state = load_pipeline_state(runs_dir)

    # Sidebar Navigation
    st.sidebar.markdown(
        """
        <div style="padding: 10px 0 20px 0;">
            <h2 style="color: #38BDF8; margin: 0; font-size: 22px;">⚡ DriftSense</h2>
            <span style="color: #94A3B8; font-size: 12px; font-weight: 600;">FOCUS 1.0 FINOPS CONTROL CENTER</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.sidebar.markdown("### 🎛️ Evaluation Track")
    track = st.sidebar.radio(
        "Select Dataset Track:",
        options=[
            "Real Track (Uncorrupted)",
            "Synthetic Validation Track (Calibrated Injections)",
        ],
        index=0,
        help="Real Track evaluates operational baseline noise. Synthetic Track validates ground-truth detection and attribution recall.",
    )

    st.sidebar.markdown("### 🧭 Navigation")
    view_selection = st.sidebar.radio(
        "Select Control Panel:",
        options=[
            "🏢 Executive Overview",
            "📈 Time-Series & Anomaly Explorer",
            "🔍 Root-Cause Attribution",
            "💡 TreeSHAP Explainability",
            "🔬 Controlled Ablations",
        ],
        index=0,
    )

    st.sidebar.markdown("---")
    st.sidebar.markdown("### 📦 Active Verified Runs")
    available_runs = state.get("runs", [])
    if available_runs:
        st.sidebar.caption(
            f"Detected **{len(available_runs)}** verified run folders in `runs/`."
        )
        latest_run = available_runs[0]
        st.sidebar.markdown(
            f"""
            <div style="font-size: 11px; color: #94A3B8;">
                Latest: <code>{latest_run["run_id"]}</code><br>
                Stage: <strong>{latest_run["stage"]}</strong><br>
                Commit: <code>{latest_run["git_commit"]}</code>
            </div>
            """,
            unsafe_allow_html=True,
        )
    else:
        st.sidebar.warning("No runs detected in runs/ directory.")

    st.sidebar.markdown("---")
    st.sidebar.caption("DriftSense v1.0.0 | FinOps Foundation FOCUS 1.0 Specification")

    # Load artifacts according to active phase runs
    p7_dir = state.get("phase_7_run")
    p8_dir = state.get("phase_8_run")
    p9_dir = state.get("phase_9_run")
    p10_dir = state.get("phase_10_run")

    detections_df, _det_err = load_detections_data(p7_dir)
    attributions_df, _attr_err = load_attributions_data(p8_dir)
    imp_df, exp_metrics, narratives, _exp_err = load_explainability_data(p9_dir)
    ablation_summary_df, abl_metrics, notes, _abl_err = load_ablation_data(p10_dir)

    # Route to selected view
    if view_selection == "🏢 Executive Overview":
        render_overview(
            detections_df=detections_df,
            attributions_df=attributions_df,
            pipeline_state=state,
            track=track,
        )
    elif view_selection == "📈 Time-Series & Anomaly Explorer":
        render_forecast_anomalies(
            detections_df=detections_df,
            track=track,
        )
    elif view_selection == "🔍 Root-Cause Attribution":
        render_attribution(attributions_df=attributions_df)
    elif view_selection == "💡 TreeSHAP Explainability":
        render_explainability(
            importance_df=imp_df,
            metrics=exp_metrics,
            narratives=narratives,
        )
    elif view_selection == "🔬 Controlled Ablations":
        render_ablations(
            ablation_summary_df=ablation_summary_df,
            metrics=abl_metrics,
            notes=notes,
        )


if __name__ == "__main__":
    main()
