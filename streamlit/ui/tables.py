"""Table rendering and database browser UI component module.

Provides functions to format and render Streamlit dataframes for raw history,
promoted predictions, active test runs, and test log archives with German/English localization.
"""

import pandas as pd
import streamlit as st
from ui.formatters import format_date, format_number, format_percent


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


def get_column_header(col: str, lang: str = "EN") -> str:
    """Returns localized column header name for tables."""
    headers = {
        "EN": {
            "Framework": "Framework",
            "Year": "Year",
            "Month": "Month",
            "TargetDate": "Target Date",
            "Prediction": "Prediction",
            "Model": "Model",
            "Date": "Date",
            "Time": "Time",
            "R2": "R²",
            "RMSE": "RMSE",
            "MAE": "MAE",
            "Unemployment": "Unemployment",
        },
        "DE": {
            "Framework": "Framework",
            "Year": "Jahr",
            "Month": "Monat",
            "TargetDate": "Ziel-Datum",
            "Prediction": "Vorhersage",
            "Model": "Modell",
            "Date": "Datum",
            "Time": "Uhrzeit",
            "R2": "R²",
            "RMSE": "RMSE",
            "MAE": "MAE",
            "Unemployment": "Arbeitslose",
        },
    }
    return headers.get(lang, headers["EN"]).get(col, col)


def render_model_performance_viewer(
    df: pd.DataFrame, title: str, selectbox_key: str, lang: str = "EN"
):
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

    date_fmt = "%d.%m.%Y" if lang == "DE" else "%Y-%m-%d"
    df_renamed["Date"] = run_dt.dt.strftime(date_fmt).fillna("N/A")
    df_renamed["Time"] = run_dt.dt.strftime("%H:%M:%S").fillna("N/A")

    # Rename columns to localized headers
    col_order = [
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

    col_rename_map = {col: get_column_header(col, lang) for col in col_order}
    df_display = df_renamed[col_order].rename(columns=col_rename_map)

    # Localized formatting map
    year_hdr = get_column_header("Year", lang)
    month_hdr = get_column_header("Month", lang)
    pred_hdr = get_column_header("Prediction", lang)
    r2_hdr = get_column_header("R2", lang)
    rmse_hdr = get_column_header("RMSE", lang)
    mae_hdr = get_column_header("MAE", lang)

    st.dataframe(
        df_display.style.format(
            {
                year_hdr: "{:.0f}",
                month_hdr: "{:.0f}",
                pred_hdr: lambda x: format_number(x, lang),
                r2_hdr: lambda x: format_percent(x, lang) if pd.notna(x) else "N/A",
                rmse_hdr: lambda x: format_number(x, lang) if pd.notna(x) else "N/A",
                mae_hdr: lambda x: format_number(x, lang) if pd.notna(x) else "N/A",
            }
        ),
        use_container_width=True,
        hide_index=True,
    )


def render_database_browser(df_raw, df_pred_all, df_runs, df_archive, t, lang: str = "EN"):
    """Renders all database tables and evaluation logs sequentially."""
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
            col_order_raw = ["Year", "Month", "Unemployment"]
            raw_rename_map = {c: get_column_header(c, lang) for c in col_order_raw}
            df_raw_display = df_raw_renamed.sort_values("Date", ascending=False)[
                col_order_raw
            ].rename(columns=raw_rename_map)

            year_hdr = get_column_header("Year", lang)
            unemp_hdr = get_column_header("Unemployment", lang)

            st.dataframe(
                df_raw_display.style.format(
                    {
                        unemp_hdr: lambda x: (
                            format_number(x, lang) if pd.notna(x) else "None"
                        ),
                        year_hdr: "{:.0f}",
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

            date_fmt = "%d.%m.%Y" if lang == "DE" else "%Y-%m-%d"
            df_pred_all_renamed["Date"] = run_dt.dt.strftime(date_fmt).fillna("N/A")
            df_pred_all_renamed["Time"] = run_dt.dt.strftime("%H:%M:%S").fillna("N/A")
            df_pred_all_renamed["TargetDate"] = df_pred_all_renamed["TargetDate"].apply(
                lambda x: format_date(x, lang)
            )

            col_order_pred = [
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
            pred_rename_map = {c: get_column_header(c, lang) for c in col_order_pred}
            df_pred_display = df_pred_all_renamed[col_order_pred].rename(
                columns=pred_rename_map
            )

            year_hdr = get_column_header("Year", lang)
            month_hdr = get_column_header("Month", lang)
            pred_hdr = get_column_header("Prediction", lang)
            r2_hdr = get_column_header("R2", lang)
            rmse_hdr = get_column_header("RMSE", lang)
            mae_hdr = get_column_header("MAE", lang)

            st.dataframe(
                df_pred_display.style.format(
                    {
                        year_hdr: "{:.0f}",
                        month_hdr: "{:.0f}",
                        pred_hdr: lambda x: format_number(x, lang),
                        r2_hdr: lambda x: format_percent(x, lang) if pd.notna(x) else "N/A",
                        rmse_hdr: lambda x: format_number(x, lang) if pd.notna(x) else "N/A",
                        mae_hdr: lambda x: format_number(x, lang) if pd.notna(x) else "N/A",
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
            df_runs, t["compare_runs_title"], "active_runs_metric_select", lang
        )

    st.write("")

    # 4. Archived Test Logs
    with st.container(border=True):
        st.subheader(t["archived_logs_label"])
        render_model_performance_viewer(
            df_archive, t["compare_runs_title"], "archived_runs_metric_select", lang
        )
