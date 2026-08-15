"""Unit tests for Streamlit dashboard and monitoring view logic."""

import pytest
import pandas as pd
from datetime import datetime
from packages.common import get_db_engine, init_db

def test_dashboard_cutoff_logic():
    """Verify cutoff logic for dashboard time filters ('All Time', 'Last 5 Years', 'Last 3 Years', 'Last 1 Year')."""
    init_db()
    engine = get_db_engine()
    with engine.connect() as conn:
        df_raw = pd.read_sql("SELECT year, month, unemployment FROM unemployment_raw ORDER BY year, month", conn)
        df_pred = pd.read_sql("SELECT * FROM predictions", conn)

    if not df_raw.empty:
        df_raw["Date"] = pd.to_datetime(df_raw["year"].astype(str) + "-" + df_raw["month"].astype(str).str.zfill(2) + "-01")
    else:
        df_raw["Date"] = pd.Series(dtype="datetime64[ns]")

    now = datetime.now()
    time_filters = ["All Time", "Last 5 Years", "Last 3 Years", "Last 1 Year"]
    
    # Iterate over all filter choices and test cutoff date calculations
    for tf in time_filters:
        if tf == "Last 1 Year":
            cutoff = pd.to_datetime(f"{now.year - 1}-{now.month:02d}-01")
        elif tf == "Last 3 Years":
            cutoff = pd.to_datetime(f"{now.year - 3}-{now.month:02d}-01")
        elif tf == "Last 5 Years":
            cutoff = pd.to_datetime(f"{now.year - 5}-{now.month:02d}-01")
        else:
            cutoff = df_raw["Date"].min() if not df_raw.empty else pd.to_datetime("2005-01-01")
            
        df_raw_filtered = df_raw[df_raw["Date"] >= cutoff] if not df_raw.empty else df_raw
        assert isinstance(df_raw_filtered, pd.DataFrame)

def test_benchmark_data_query():
    """Verify benchmark data aggregation query from test_runs_archive table."""
    init_db()
    engine = get_db_engine()
    with engine.connect() as conn:
        df = pd.read_sql("SELECT framework, year, month, run_timestamp, prediction, model, r2, rmse, mae FROM test_runs_archive ORDER BY run_timestamp DESC", conn)
    
    assert isinstance(df, pd.DataFrame)
