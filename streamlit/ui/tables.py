import pandas as pd
import streamlit as st


def clean_model_name(name: str) -> str:
    """Abbreviates long model names for cleaner UI presentation."""
    if not name:
        return "Unknown"
    if "StackedEnsemble" in name:
        return "StackedEnsemble"
    if "DeepLearning" in name:
        return "DeepLearning"
    if "XGBoost" in name:
        return "XGBoost"
    if "GBM" in name:
        return "GBM"
    if "DRF" in name:
        return "DRF"
    if "GLM" in name:
        return "GLM"
    if len(name) > 25:
        return name[:22] + "..."
    return name


def render_model_performance_viewer(df: pd.DataFrame, title: str, selectbox_key: str):
    """Renders formatted dataframe viewer for active or archived model evaluation test runs."""
    t = st.session_state.get("t_dict", {})
    no_runs_msg = (
        t.get("no_active_runs", "No active testing runs found.")
        if "active" in selectbox_key
        else t.get("no_archived_logs", "No testing logs recorded.")
    )

    if df.empty:
        st.info(no_runs_msg)
        return

    df_renamed = df.rename(
        columns={
            "framework": "Framework",
            "year": "Year",
            "month": "Month",
            "run_timestamp": "RunTimestamp",
            "prediction": "Prediction",
            "model": "Model",
            "r2": "R2",
            "rmse": "RMSE",
            "mae": "MAE",
        }
    )

    # Abbreviate Model Name
    df_renamed["Model"] = df_renamed["Model"].map(clean_model_name)

    # Split Timestamp into Date and Time (localized to Europe/Berlin)
    run_dt = pd.to_datetime(df_renamed["RunTimestamp"])
    if not run_dt.empty:
        if run_dt.dt.tz is None:
            run_dt = run_dt.dt.tz_localize("UTC")
        run_dt = run_dt.dt.tz_convert("Europe/Berlin")
    df_renamed["Date"] = run_dt.dt.strftime("%Y-%m-%d").fillna("N/A")
    df_renamed["Time"] = run_dt.dt.strftime("%H:%M:%S").fillna("N/A")

    st.dataframe(
        df_renamed[
            [
                "Framework",
                "Year",
                "Month",
                "Date",
                "Time",
                "Prediction",
                "Model",
                "R2",
                "RMSE",
                "MAE",
            ]
        ].style.format(
            {
                "Year": "{:.0f}",
                "Month": "{:.0f}",
                "Prediction": "{:,}",
                "R2": lambda x: f"{x:.2f}%" if pd.notna(x) else "N/A",
                "RMSE": lambda x: f"{int(x):,}" if pd.notna(x) else "N/A",
                "MAE": lambda x: f"{int(x):,}" if pd.notna(x) else "N/A",
            }
        ),
        use_container_width=True,
        hide_index=True,
    )


def render_database_browser(df_raw, df_pred_all, df_runs, df_archive, t):
    """Renders all database tables and evaluation logs sequentially (hintereinander)."""
    st.session_state["t_dict"] = t

    # 1. Raw History Records
    with st.container(border=True):
        st.subheader(t["raw_records_label"])
        if not df_raw.empty:
            df_raw_renamed = df_raw.rename(
                columns={
                    "year": "Year",
                    "month": "Month",
                    "unemployment": "Unemployment",
                }
            )
            st.dataframe(
                df_raw_renamed.sort_values("Date", ascending=False)[
                    ["Year", "Month", "Unemployment"]
                ].style.format(
                    {
                        "Unemployment": lambda x: (
                            f"{int(x):,}" if pd.notna(x) else "None"
                        ),
                        "Year": "{:.0f}",
                    }
                ),
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.info("No raw history records available.")

    st.write("")

    # 2. Promoted Predictions
    with st.container(border=True):
        st.subheader(t["promoted_label"])
        if not df_pred_all.empty:
            df_pred_all_renamed = df_pred_all.rename(
                columns={
                    "framework": "Framework",
                    "year": "Year",
                    "month": "Month",
                    "target_date": "TargetDate",
                    "prediction": "Prediction",
                    "model": "Model",
                    "run_timestamp": "RunTimestamp",
                    "r2": "R2",
                    "rmse": "RMSE",
                    "mae": "MAE",
                }
            )
            df_pred_all_renamed["Model"] = df_pred_all_renamed["Model"].map(
                clean_model_name
            )
            run_dt = pd.to_datetime(df_pred_all_renamed["RunTimestamp"])
            if not run_dt.empty:
                if run_dt.dt.tz is None:
                    run_dt = run_dt.dt.tz_localize("UTC")
                run_dt = run_dt.dt.tz_convert("Europe/Berlin")
            df_pred_all_renamed["Date"] = run_dt.dt.strftime("%Y-%m-%d").fillna("N/A")
            df_pred_all_renamed["Time"] = run_dt.dt.strftime("%H:%M:%S").fillna("N/A")

            st.dataframe(
                df_pred_all_renamed[
                    [
                        "Framework",
                        "Year",
                        "Month",
                        "TargetDate",
                        "Prediction",
                        "Model",
                        "Date",
                        "Time",
                        "R2",
                        "RMSE",
                        "MAE",
                    ]
                ].style.format(
                    {
                        "Year": "{:.0f}",
                        "Month": "{:.0f}",
                        "Prediction": "{:,}",
                        "R2": lambda x: f"{x:.2f}%" if pd.notna(x) else "N/A",
                        "RMSE": lambda x: f"{int(x):,}" if pd.notna(x) else "N/A",
                        "MAE": lambda x: f"{int(x):,}" if pd.notna(x) else "N/A",
                    }
                ),
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.info(t["no_promoted_models"])

    st.write("")

    # 3. Active Test Runs
    with st.container(border=True):
        st.subheader(t["active_runs_label"])
        render_model_performance_viewer(
            df_runs, t["compare_runs_title"], "active_runs_metric_select"
        )

    st.write("")

    # 4. Archived Test Logs
    with st.container(border=True):
        st.subheader(t["archived_logs_label"])
        render_model_performance_viewer(
            df_archive, t["compare_runs_title"], "archived_runs_metric_select"
        )
