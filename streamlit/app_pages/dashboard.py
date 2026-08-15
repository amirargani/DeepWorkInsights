from datetime import datetime
import numpy as np
import pandas as pd
import streamlit as st

from packages.dashboard_data import (
    TRANSLATIONS,
    check_dag_running,
    load_dashboard_data,
)
from ui import (
    clean_model_name,
    render_database_browser,
    render_forecast_error_chart,
    render_historical_timeline_area_chart,
    render_historical_timeline_chart,
    render_kpi_cards,
    render_model_performance_viewer,
    render_seasonality_chart,
    render_yoy_change_chart,
)


def render_dashboard(lang=None):
    if lang is None:
        lang = st.session_state.get("language", "EN")
    t = TRANSLATIONS[lang]

    # Sync selected table with query parameters
    if "table" in st.query_params:
        st.session_state.selected_table = st.query_params["table"]
    else:
        st.session_state.selected_table = "unemployment_raw"
        st.query_params["table"] = "unemployment_raw"

    st.markdown(
        "Monitor German monthly unemployment rates and compare model forecasts from H2O AutoML and Auto-sklearn."
    )

    # Load data via packages.dashboard_data module
    try:
        df_raw, df_pred, df_pred_all, df_runs, df_archive = load_dashboard_data()
    except Exception as e:
        st.error(f"Error connecting to PostgreSQL database: {e}")
        st.stop()

    # Calculate stable dataframe hashes to optimize chart re-renders
    raw_hash = int(pd.util.hash_pandas_object(df_raw).sum())
    pred_hash = (
        int(pd.util.hash_pandas_object(df_pred).sum()) if not df_pred.empty else 0
    )
    pred_all_hash = (
        int(pd.util.hash_pandas_object(df_pred_all).sum())
        if not df_pred_all.empty
        else 0
    )
    runs_hash = (
        int(pd.util.hash_pandas_object(df_runs).sum()) if not df_runs.empty else 0
    )
    archive_hash = (
        int(pd.util.hash_pandas_object(df_archive).sum())
        if not df_archive.empty
        else 0
    )

    # Check if there is an active model training / forecast DAG execution run
    is_running = check_dag_running()

    if is_running:
        st.markdown(
            f"""
            <div style="background-color: rgba(59, 130, 246, 0.1); border: 1px solid rgba(59, 130, 246, 0.3); padding: 0.75rem 1rem; border-radius: 0.5rem; margin-bottom: 1.5rem; display: flex; align-items: center; gap: 0.75rem; animation: pulse 2s infinite ease-in-out;">
                <span style="font-size: 1.25rem;">⚡</span>
                <div>
                    <strong style="color: #93C5FD;">{t['running_banner_title']}</strong><br/>
                    <span style="color: #BFDBFE; font-size: 0.85em; opacity: 0.9;">{t['running_banner_desc']}</span>
                </div>
            </div>
            <style>
                @keyframes pulse {{
                    0% {{ opacity: 0.75; }}
                    50% {{ opacity: 1; }}
                    100% {{ opacity: 0.75; }}
                }}
            </style>
            """,
            unsafe_allow_html=True,
        )

    if df_raw.empty:
        st.warning(
            "No historical data found in database. Run the fetch pipeline first."
        )
        st.stop()

    # ─── KPI Cards Row ────────────────────────────────────────────────────────────
    df_actual = df_raw.dropna(subset=["unemployment"])
    if not df_actual.empty:
        latest_raw = df_actual.iloc[-1]
        latest_raw_val = int(latest_raw["unemployment"])
        latest_raw_date = f"{t['month_names'][latest_raw['Date'].month]} {latest_raw['Date'].year}"
    else:
        latest_raw_val = 0
        latest_raw_date = "N/A"

    latest_automl = (
        df_pred[df_pred["framework"] == "automl"].iloc[-1]
        if not df_pred.empty and "automl" in df_pred["framework"].values
        else None
    )
    latest_autosklearn = (
        df_pred[df_pred["framework"] == "autosklearn"].iloc[-1]
        if not df_pred.empty and "autosklearn" in df_pred["framework"].values
        else None
    )

    render_kpi_cards(
        latest_raw_val, latest_raw_date, latest_automl, latest_autosklearn, t
    )

    st.write("")

    # ─── Inline Period Filter (No Sidebar) ───
    st.markdown(f"### {t['period_label']}")
    filter_options = [
        t["curr_to_new"],
        t["last_1_yr"],
        t["last_3_yr"],
        t["last_5_yr"],
        t["all_time"],
    ]
    selected_option = st.selectbox(
        t["period_label"], filter_options, index=0, label_visibility="collapsed"
    )

    if selected_option == t["curr_to_new"]:
        time_filter = "Current Year"
    elif selected_option == t["last_1_yr"]:
        time_filter = "Last 1 Year"
    elif selected_option == t["last_3_yr"]:
        time_filter = "Last 3 Years"
    elif selected_option == t["last_5_yr"]:
        time_filter = "Last 5 Years"
    else:
        time_filter = "All Time"

    now = datetime.now()
    if time_filter == "Current Year":
        cutoff = pd.to_datetime(f"{now.year}-01-01")
        chart_title = t["title_curr_to_new"]
    elif time_filter == "Last 1 Year":
        cutoff = pd.to_datetime(f"{now.year - 1}-{now.month:02d}-01")
        chart_title = t["title_last_1_yr"]
    elif time_filter == "Last 3 Years":
        cutoff = pd.to_datetime(f"{now.year - 3}-{now.month:02d}-01")
        chart_title = t["title_last_3_yr"]
    elif time_filter == "Last 5 Years":
        cutoff = pd.to_datetime(f"{now.year - 5}-{now.month:02d}-01")
        chart_title = t["title_last_5_yr"]
    else:
        cutoff = df_raw["Date"].min()
        chart_title = t["title_all_time"]

    df_raw_filtered = df_raw[df_raw["Date"] >= cutoff]
    df_pred_filtered = (
        df_pred[df_pred["Date"] >= cutoff]
        if not df_pred.empty
        else pd.DataFrame()
    )

    # ─── Visualizations Section ───
    st.write("")
    st.markdown(f"### {t['vis_section']}")

    # 1. Unemployment History & Forecasts (Full Width)
    with st.container(border=True):
        st.subheader(chart_title)
        render_historical_timeline_chart(
            df_raw_filtered,
            df_pred_filtered,
            time_filter,
            lang,
            t,
            raw_hash,
            pred_hash,
        )

    st.write("")

    # 2. Historical Monthly Unemployment Timeline (Full Width Area Chart)
    with st.container(border=True):
        st.subheader(t["historical_timeline"])
        render_historical_timeline_area_chart(df_raw, t, raw_hash, lang)

    st.write("")

    # 3. Seasonality Analysis (Full Width)
    with st.container(border=True):
        current_year = int(df_raw.dropna(subset=["unemployment"])["year"].max())
        start_year = int(df_raw["year"].min())
        prev_year = current_year - 1
        language_code = st.session_state.get("language", "EN")

        if language_code == "DE":
            seasonality_title = f"Saisonalitätsanalyse: Historische Verteilung ({start_year} - {prev_year}) vs. Aktuelles Jahr {current_year}"
        else:
            seasonality_title = f"Seasonality Analysis: Historical Distribution ({start_year} - {prev_year}) vs. Current Year {current_year}"

        st.subheader(seasonality_title)
        render_seasonality_chart(df_raw, df_pred, lang, t, raw_hash, pred_hash)

    st.write("")

    # 4. Historical Forecast Error (Full Width)
    if not df_archive.empty:
        with st.container(border=True):
            st.subheader(t["forecast_error"])
            render_forecast_error_chart(
                df_archive, df_raw, lang, t, archive_hash, raw_hash
            )

    st.write("")

    # 5. Year-over-Year (YoY) Change Analysis (Full Width)
    with st.container(border=True):
        st.subheader(t["yoy_change"])
        render_yoy_change_chart(df_raw, cutoff, time_filter, lang, t, raw_hash)

    st.write("")

    # ─── Database & Evaluation Logs Browser ───
    st.markdown(f"### {t['db_browser_title']}")

    metric_cols = st.columns(4)
    with metric_cols[0]:
        with st.container(border=True):
            st.metric(t["raw_records_label"], len(df_raw))
    with metric_cols[1]:
        with st.container(border=True):
            st.metric(t["promoted_label"], len(df_pred_all))
    with metric_cols[2]:
        with st.container(border=True):
            st.metric(t["active_runs_label"], len(df_runs))
    with metric_cols[3]:
        with st.container(border=True):
            st.metric(t["archived_logs_label"], len(df_archive))

    st.write("")

    # Render Database Browser Fragment
    render_database_browser(df_raw, df_pred_all, df_runs, df_archive, t)


if __name__ == "__main__":
    st.title("Forecasting Dashboard")
    render_dashboard()
