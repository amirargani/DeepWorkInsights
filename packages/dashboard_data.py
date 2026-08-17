"""Backend data loader module for the forecasting dashboard.

Provides cached data fetching for raw historical BA data, promoted predictions,
active model test runs, and test log archives from PostgreSQL, as well as DAG status checks.
"""

import os
import sys
import pandas as pd
import sqlalchemy as sa
import streamlit as st

from packages.common import get_db_engine, init_db

# Bilingual Translation Dictionary for Forecasting Dashboard
DASHBOARD_TRANSLATIONS = {
    "EN": {
        "period_label": "Historical Period",
        "curr_to_new": "Current Year to New Year",
        "last_1_yr": "Last 1 Year",
        "last_3_yr": "Last 3 Years",
        "last_5_yr": "Last 5 Years",
        "all_time": "All Time",
        "title_curr_to_new": "Unemployment: Current Year to New Year",
        "title_last_1_yr": "Unemployment: Last 1 Year",
        "title_last_3_yr": "Unemployment: Last 3 Years",
        "title_last_5_yr": "Unemployment: Last 5 Years",
        "title_all_time": "Unemployment: Full History (Since 2005)",
        "date_label": "Date",
        "vis_section": "Forecast Visualizations & Performance Analysis",
        "actual_label": "Latest Actual (BA)",
        "automl_label": "H2O AutoML Forecast",
        "autosklearn_label": "Auto-sklearn Forecast",
        "refers_to": "Refers to:",
        "target": "Target:",
        "official_data": "Official Federal Employment Agency data",
        "no_pred_avail": "No prediction available.",
        "forecast_start": "Forecast Start (Aug 2026)",
        "forecast_horizon": "Forecast Horizon",
        "y_axis_title": "Unemployment Count",
        "historical_timeline": "Historical Timeline: Monthly Unemployment",
        "seasonality_analysis": "Seasonality Analysis: Monthly Unemployment Distribution (2005 - 2026)",
        "forecast_error": "Historical Forecast Error (%) on Past Months (Residuals)",
        "yoy_change": "Year-over-Year (YoY) Change in Unemployment (%)",
        "yoy_plot_title": "Year-over-Year (YoY) Percentage Change in Monthly Unemployment",
        "db_browser_title": "Database & Evaluation Logs Browser",
        "y_axis_ticks": ["0", "1M", "2M", "3M", "4M", "5M"],
        "actual_name": "Actual (BA)",
        "automl_name": "H2O AutoML Forecast",
        "autosklearn_name": "Auto-sklearn Forecast",
        "unemployed_label": "Unemployed",
        "month_axis_label": "Month",
        "unemployment_count_label": "Unemployment Count",
        "actual_y_name": "Actuals (BA)",
        "automl_y_name": "H2O AutoML Forecast",
        "autosklearn_y_name": "Auto-sklearn Forecast",
        "target_date_label": "Target Date",
        "pred_error_label": "Prediction Error (%)",
        "perfect_forecast": "Perfect Forecast",
        "yoy_change_label": "YoY Change (%)",
        "raw_records_label": "Raw History Records",
        "promoted_label": "Promoted Predictions",
        "active_runs_label": "Active Test Runs",
        "archived_logs_label": "Archived Test Logs",
        "no_promoted_models": "No promoted models found in predictions table.",
        "no_active_runs": "No active testing runs found in test_runs table.",
        "no_archived_logs": "No testing logs recorded in test_runs_archive table.",
        "model_prefix": "Model",
        "compare_runs_title": "Active Test Runs Performance Comparison",
        "month_names": {
            1: "Jan",
            2: "Feb",
            3: "Mar",
            4: "Apr",
            5: "May",
            6: "Jun",
            7: "Jul",
            8: "Aug",
            9: "Sep",
            10: "Oct",
            11: "Nov",
            12: "Dec",
        },
        "running_banner_title": "Model Training & Forecast Pipeline in Progress...",
        "running_banner_desc": "The models are currently retraining in the background. The dashboard will automatically update and display the latest results once complete.",
    },
    "DE": {
        "period_label": "Historischer Zeitraum",
        "curr_to_new": "Aktuelles Jahr bis neues Jahr",
        "last_1_yr": "Letztes 1 Jahr",
        "last_3_yr": "Letzte 3 Jahre",
        "last_5_yr": "Letzte 5 Jahre",
        "all_time": "Gesamter Verlauf",
        "title_curr_to_new": "Arbeitslosigkeit: Aktuelles Jahr bis neues Jahr",
        "title_last_1_yr": "Arbeitslosigkeit: Letztes 1 Jahr",
        "title_last_3_yr": "Arbeitslosigkeit: Letzte 3 Jahre",
        "title_last_5_yr": "Arbeitslosigkeit: Letzte 5 Jahre",
        "title_all_time": "Arbeitslosigkeit: Gesamter Verlauf (seit 2005)",
        "date_label": "Datum",
        "vis_section": "Prognose-Visualisierungen & Performance-Analyse",
        "actual_label": "Aktueller Ist-Wert (BA)",
        "automl_label": "H2O AutoML Prognose",
        "autosklearn_label": "Auto-sklearn Prognose",
        "refers_to": "Bezieht sich auf:",
        "target": "Zielmonat:",
        "official_data": "Offizielle Daten der Bundesagentur für Arbeit",
        "no_pred_avail": "Keine Prognose verfügbar.",
        "forecast_start": "Prognose-Start (Aug 2026)",
        "forecast_horizon": "Prognose-Horizont",
        "y_axis_title": "Arbeitslosenzahl",
        "historical_timeline": "Historischer Verlauf: Monatliche Arbeitslosigkeit",
        "seasonality_analysis": "Saisonalitätsanalyse: Monatliche Arbeitslosenverteilung (2005 - 2026)",
        "forecast_error": "Historischer Prognosefehler (%) der vergangenen Monate (Residuen)",
        "yoy_change": "Vorjahresvergleich (YoY) Veränderung der Arbeitslosigkeit (%)",
        "yoy_plot_title": "Prozentuale Vorjahresveränderung (YoY) der monatlichen Arbeitslosigkeit",
        "db_browser_title": "Datenbank- & Evaluierungs-Protokoll-Browser",
        "y_axis_ticks": ["0", "1 Mio.", "2 Mio.", "3 Mio.", "4 Mio.", "5 Mio."],
        "actual_name": "Ist-Wert (BA)",
        "automl_name": "H2O AutoML Prognose",
        "autosklearn_name": "Auto-sklearn Prognose",
        "unemployed_label": "Arbeitslose",
        "month_axis_label": "Monat",
        "unemployment_count_label": "Arbeitslosenzahl",
        "actual_y_name": "Ist-Werte (BA)",
        "automl_y_name": "H2O AutoML Prognose",
        "autosklearn_y_name": "Auto-sklearn Prognose",
        "target_date_label": "Zielmonat",
        "pred_error_label": "Prognosefehler (%)",
        "perfect_forecast": "Perfekte Prognose",
        "yoy_change_label": "YoY Veränderung (%)",
        "raw_records_label": "Verlaufshistorie-Datensätze",
        "promoted_label": "Freigegebene Prognosen",
        "active_runs_label": "Aktive Testläufe",
        "archived_logs_label": "Archivierte Testberichte",
        "no_promoted_models": "Keine freigegebenen Modelle in der Tabelle predictions gefunden.",
        "no_active_runs": "Keine aktiven Testläufe in der Tabelle test_runs gefunden.",
        "no_archived_logs": "Keine Testberichte in der Tabelle test_runs_archive aufgezeichnet.",
        "model_prefix": "Modell",
        "compare_runs_title": "Performance-Vergleich der aktiven Testläufe",
        "month_names": {
            1: "Jan",
            2: "Feb",
            3: "Mär",
            4: "Apr",
            5: "Mai",
            6: "Jun",
            7: "Jul",
            8: "Aug",
            9: "Sep",
            10: "Okt",
            11: "Nov",
            12: "Dez",
        },
        "running_banner_title": "Modelltraining & Vorhersage läuft im Hintergrund...",
        "running_banner_desc": "Die Modelle werden aktuell neu trainiert. Das Dashboard aktualisiert sich automatisch bei Fertigstellung und zeigt die neuesten Vorhersagen.",
    },
}

TRANSLATIONS = DASHBOARD_TRANSLATIONS


@st.cache_data(ttl="55s")
def load_dashboard_data():
    """Fetch raw history, predictions, active test runs, and archives from PostgreSQL DB."""
    init_db()
    engine = get_db_engine()

    with engine.connect() as conn:
        try:
            res = conn.execute(sa.text("SELECT COUNT(*) FROM unemployment_raw"))
            raw_count = res.scalar()
        except Exception:
            raw_count = 0

    if raw_count == 0:
        from packages import fetch_data

        try:
            fetch_data.main()
        except Exception as exc:
            print(f"Error fetching data on dashboard load: {exc}")

    with engine.connect() as conn:
        df_raw = pd.read_sql(
            "SELECT year, month, unemployment FROM unemployment_raw ORDER BY year, month",
            conn,
        )
        df_pred_all = pd.read_sql(
            "SELECT * FROM predictions ORDER BY run_timestamp DESC", conn
        )
        df_runs = pd.read_sql(
            "SELECT * FROM test_runs ORDER BY run_timestamp DESC", conn
        )
        df_archive = pd.read_sql(
            "SELECT * FROM test_runs_archive ORDER BY run_timestamp DESC", conn
        )

    # Process raw data
    df_raw["Date"] = pd.to_datetime(
        df_raw["year"].astype(str)
        + "-"
        + df_raw["month"].astype(str).str.zfill(2)
        + "-01"
    )
    df_raw = df_raw.sort_values("Date").reset_index(drop=True)

    # Process predictions (needs chronological sort for charts)
    df_pred_chrono = df_pred_all.copy()
    if not df_pred_chrono.empty:
        df_pred_chrono["Date"] = pd.to_datetime(df_pred_chrono["target_date"])
        df_pred_chrono = df_pred_chrono.sort_values("Date").reset_index(
            drop=True
        )

    return df_raw, df_pred_chrono, df_pred_all, df_runs, df_archive


def check_dag_running() -> bool:
    """Checks if the unemployment_forecast DAG is currently running or queued in PostgreSQL."""
    try:
        engine = get_db_engine()
        with engine.connect() as conn:
            df_dag_state = pd.read_sql(
                "SELECT state FROM dag_run WHERE dag_id = 'unemployment_forecast' ORDER BY execution_date DESC LIMIT 1",
                conn,
            )
            if not df_dag_state.empty:
                return df_dag_state.iloc[0]["state"] in ["running", "queued"]
    except Exception:
        pass
    return False
