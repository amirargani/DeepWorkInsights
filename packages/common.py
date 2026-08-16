"""Common utilities shared by automl.py and autosklearn.py.

Provides centralized data loading, feature engineering, and prediction
persistence helpers used by both forecasting pipelines.
"""

import os
import math
import warnings
import numpy as np
import pandas as pd
import sqlalchemy as sa
from pathlib import Path
from datetime import datetime
from . import fetch_data

# Suppress non-critical warnings from pandas, numpy and sklearn during runtime
warnings.filterwarnings("ignore")

# How many rows of the leaderboard are printed to the console
TOP_MODELS_TO_SHOW = 10



_DB_ENGINE = None

def get_db_engine():
    """Create a database engine with smart host detection, connectivity testing, and fallback caching."""
    global _DB_ENGINE
    if _DB_ENGINE is not None:
        return _DB_ENGINE

    db_host = os.environ.get("POSTGRES_HOST")
    if db_host:
        _DB_ENGINE = sa.create_engine(f"postgresql://admin:admin@{db_host}:5432/airflow")
        return _DB_ENGINE

    # Try connecting to postgres container host first if inside Docker
    if os.path.exists("/.dockerenv"):
        try:
            engine = sa.create_engine("postgresql://admin:admin@postgres:5432/airflow", pool_pre_ping=True)
            with engine.connect() as conn:
                pass
            _DB_ENGINE = engine
            return _DB_ENGINE
        except Exception:
            pass

    # Try connecting to localhost postgres
    try:
        engine = sa.create_engine("postgresql://admin:admin@localhost:5432/airflow", pool_pre_ping=True)
        with engine.connect() as conn:
            pass
        _DB_ENGINE = engine
        return _DB_ENGINE
    except Exception:
        pass

    # Fallback to local SQLite file database for offline/standalone execution
    sqlite_path = Path("/tmp/deepwork_fallback.db")
    _DB_ENGINE = sa.create_engine(f"sqlite:///{sqlite_path}")
    return _DB_ENGINE


def init_db() -> None:
    """Initialize database tables and automatically migrate existing CSV files if empty."""
    engine = get_db_engine()
    metadata = sa.MetaData()

    # Raw monthly BA unemployment data
    unemployment_raw = sa.Table(
        "unemployment_raw",
        metadata,
        sa.Column("year", sa.Integer, primary_key=True),
        sa.Column("month", sa.String(2), primary_key=True),
        sa.Column("unemployment", sa.Integer, nullable=True),
    )

    # Promoted predictions
    predictions = sa.Table(
        "predictions",
        metadata,
        sa.Column("framework", sa.String(20), primary_key=True),
        sa.Column("year", sa.Integer, primary_key=True),
        sa.Column("month", sa.Integer, primary_key=True),
        sa.Column("target_date", sa.Date, nullable=False),
        sa.Column("prediction", sa.Integer, nullable=False),
        sa.Column("model", sa.String(255), nullable=False),
        sa.Column("run_timestamp", sa.DateTime, nullable=False),
        sa.Column("r2", sa.Float, nullable=True),
        sa.Column("rmse", sa.Float, nullable=True),
        sa.Column("mae", sa.Float, nullable=True),
    )

    # Active test runs
    test_runs = sa.Table(
        "test_runs",
        metadata,
        sa.Column("framework", sa.String(20), primary_key=True),
        sa.Column("year", sa.Integer, primary_key=True),
        sa.Column("month", sa.Integer, primary_key=True),
        sa.Column("run_timestamp", sa.DateTime, primary_key=True),
        sa.Column("prediction", sa.Integer, nullable=False),
        sa.Column("model", sa.String(255), nullable=False),
        sa.Column("r2", sa.Float, nullable=True),
        sa.Column("rmse", sa.Float, nullable=True),
        sa.Column("mae", sa.Float, nullable=True),
    )

    # Archived test runs
    test_runs_archive = sa.Table(
        "test_runs_archive",
        metadata,
        sa.Column("framework", sa.String(20), primary_key=True),
        sa.Column("year", sa.Integer, primary_key=True),
        sa.Column("month", sa.Integer, primary_key=True),
        sa.Column("run_timestamp", sa.DateTime, primary_key=True),
        sa.Column("prediction", sa.Integer, nullable=False),
        sa.Column("model", sa.String(255), nullable=False),
        sa.Column("r2", sa.Float, nullable=True),
        sa.Column("rmse", sa.Float, nullable=True),
        sa.Column("mae", sa.Float, nullable=True),
    )

    metadata.create_all(engine)
    print("Database tables initialized.")

    # ── Automatic Migration ──────────────────────────────────────────────────
    csv_raw_path = Path("files/unemployment_germany.csv")
    with engine.connect() as conn:
        res = conn.execute(sa.text("SELECT COUNT(*) FROM unemployment_raw"))
        raw_count = res.scalar()
        if raw_count == 0 and csv_raw_path.exists():
            print(f"Migrating raw data from {csv_raw_path} to database table 'unemployment_raw'...")
            df_raw = pd.read_csv(csv_raw_path, encoding="utf-8-sig")
            df_raw.columns = df_raw.columns.str.strip()
            df_raw["Month"] = df_raw["Month"].astype(str).str.zfill(2)
            df_raw = df_raw.replace({np.nan: None})
            
            for _, row in df_raw.iterrows():
                unemp = int(row["Unemployment"]) if row["Unemployment"] is not None else None
                conn.execute(
                    unemployment_raw.insert().values(
                        year=int(row["Year"]),
                        month=row["Month"],
                        unemployment=unemp
                    )
                )
            conn.commit()
            print("Raw data successfully migrated.")
            try:
                csv_raw_path.unlink()
                print(f"Removed migrated file {csv_raw_path}")
            except Exception as e:
                print(f"[WARNING] Could not delete {csv_raw_path}: {e}")

    # Predictions migration
    migrate_csv_predictions(Path("files/automl_predictions.csv"), "automl", engine, predictions)
    migrate_csv_predictions(Path("files/autosklearn_predictions.csv"), "autosklearn", engine, predictions)

    # Test runs migration
    migrate_csv_test_runs(Path("files/automl_test_runs.csv"), "automl", engine, test_runs)
    migrate_csv_test_runs(Path("files/autosklearn_test_runs.csv"), "autosklearn", engine, test_runs)


def migrate_csv_predictions(csv_path: Path, framework: str, engine, predictions_table) -> None:
    """Migrate historical predictions from CSV to PostgreSQL table."""
    if not csv_path.exists():
        return
        
    with engine.connect() as conn:
        res = conn.execute(sa.text(f"SELECT COUNT(*) FROM predictions WHERE framework = '{framework}'"))
        count = res.scalar()
        if count == 0:
            print(f"Migrating {framework} predictions from {csv_path} to database...")
            df = pd.read_csv(csv_path, encoding="utf-8-sig")
            df = df.replace({np.nan: None})
            
            for _, row in df.iterrows():
                date_obj = pd.to_datetime(row["Date"]).date()
                timestamp_obj = pd.to_datetime(row["Run_Timestamp"])
                r2_val = float(row["R2 (%)"]) if row.get("R2 (%)") is not None else None
                rmse_val = float(row["RMSE"]) if row.get("RMSE") is not None else None
                mae_val = float(row["MAE"]) if row.get("MAE") is not None else None
                
                conn.execute(
                    predictions_table.insert().values(
                        framework=framework,
                        year=int(row["Year"]),
                        month=int(row["Month"]),
                        target_date=date_obj,
                        prediction=int(row["Prediction"]),
                        model=str(row["Model"]),
                        run_timestamp=timestamp_obj,
                        r2=r2_val,
                        rmse=rmse_val,
                        mae=mae_val
                    )
                )
            conn.commit()
            print(f"{framework} predictions successfully migrated.")
            try:
                csv_path.unlink()
                print(f"Removed migrated file {csv_path}")
            except Exception as e:
                print(f"[WARNING] Could not delete {csv_path}: {e}")


def migrate_csv_test_runs(csv_path: Path, framework: str, engine, test_runs_table) -> None:
    """Migrate temporary test runs from CSV to PostgreSQL table."""
    if not csv_path.exists():
        return
        
    with engine.connect() as conn:
        res = conn.execute(sa.text(f"SELECT COUNT(*) FROM test_runs WHERE framework = '{framework}'"))
        count = res.scalar()
        if count == 0:
            print(f"Migrating {framework} test runs from {csv_path} to database...")
            df = pd.read_csv(csv_path, encoding="utf-8-sig")
            df = df.replace({np.nan: None})
            
            for _, row in df.iterrows():
                timestamp_obj = pd.to_datetime(row["Run_Timestamp"])
                r2_val = float(row["R2 (%)"]) if row.get("R2 (%)") is not None else None
                rmse_val = float(row["RMSE"]) if row.get("RMSE") is not None else None
                mae_val = float(row["MAE"]) if row.get("MAE") is not None else None
                
                conn.execute(
                    test_runs_table.insert().values(
                        framework=framework,
                        year=int(row["Year"]),
                        month=int(row["Month"]),
                        run_timestamp=timestamp_obj,
                        prediction=int(row["Prediction"]),
                        model=str(row["Model"]),
                        r2=r2_val,
                        rmse=rmse_val,
                        mae=mae_val
                    )
                )
            conn.commit()
            print(f"{framework} test runs successfully migrated.")
            try:
                csv_path.unlink()
                print(f"Removed migrated file {csv_path}")
            except Exception as e:
                print(f"[WARNING] Could not delete {csv_path}: {e}")


def load_data() -> pd.DataFrame:
    """Load the source data from PostgreSQL and return a complete gap-free monthly timeline.

    Handles potential chronological gaps in historical BA data by reindexing
    to a continuous monthly grid and interpolating internal missing months,
    guaranteeing mathematically correct step sizes for time-series features.

    :return: Cleaned monthly timeline DataFrame.
    :rtype: pandas.DataFrame
    """
    init_db()
    try:
        fetch_data.main()
    except SystemExit as exc:
        if exc.code == 10:
            print("  No new data on BA website. Proceeding with existing database records.")
        else:
            raise exc
    except Exception as exc:
        print(f"  [WARNING] Could not update source data from BA website ({exc.__class__.__name__}).")
        print("            Falling back to existing database records.")

    engine = get_db_engine()
    df = pd.read_sql("SELECT year as \"Year\", month as \"Month\", unemployment as \"Unemployment\" FROM unemployment_raw", engine)
    
    df["Month"] = df["Month"].astype(str).str.zfill(2)
    df["Date"] = pd.to_datetime(
        df["Year"].astype(str) + "-" + df["Month"] + "-01"
    )
    df = df.sort_values("Date").reset_index(drop=True)

    df_with_val = df.dropna(subset=["Unemployment"])
    if df_with_val.empty:
        raise ValueError("No valid unemployment data found in the database table!")

    min_date = df_with_val["Date"].min()
    max_date = df_with_val["Date"].max()

    df = df[(df["Date"] >= min_date) & (df["Date"] <= max_date)].copy()

    full_range = pd.date_range(start=min_date, end=max_date, freq="MS")
    df = df.set_index("Date").reindex(full_range).reset_index().rename(columns={"index": "Date"})

    df["Year"] = df["Date"].dt.year
    df["Month"] = df["Date"].dt.month

    gaps_count = df["Unemployment"].isna().sum()
    if gaps_count > 0:
        print(f"  [WARNING] Found {gaps_count} internal missing month(s) in historical data.")
        df["Unemployment"] = df["Unemployment"].interpolate(method="linear")
        df["Unemployment"] = df["Unemployment"].round().astype(int)
        print("            Internal gaps successfully interpolated.")
    else:
        df["Unemployment"] = df["Unemployment"].astype(int)

    return df


def merge_past_predictions(df: pd.DataFrame, framework: str, target_date: datetime) -> pd.DataFrame:
    """Merge previously saved predictions from database as actual values where gaps exist.

    Any month that was forecast in a prior run but still has no official value
    in the database is added to the training frame so the model can learn from
    cumulative predictions over time. Only predictions for months strictly before
    the target_date are merged to avoid feature leakage and mismatched target rows.

    :param df: Training data DataFrame.
    :type df: pandas.DataFrame
    :param framework: AutoML framework name ('automl' or 'autosklearn').
    :type framework: str
    :param target_date: The date of the current run's target month.
    :type target_date: datetime.datetime
    :return: DataFrame with merged past predictions.
    :rtype: pandas.DataFrame
    """
    engine = get_db_engine()
    query = sa.text("SELECT target_date, prediction FROM predictions WHERE framework = :framework")
    
    with engine.connect() as conn:
        res = conn.execute(query, {"framework": framework})
        rows = res.fetchall()

    if not rows:
        return df

    existing_dates = set(df["Date"])
    new_rows = []

    for row in rows:
        row_date = pd.to_datetime(row[0])
        row_month_start = pd.to_datetime(f"{row_date.year}-{row_date.month:02d}-01")
        target_month_start = pd.to_datetime(f"{target_date.year}-{target_date.month:02d}-01")
        if row_month_start < target_month_start and row_month_start not in existing_dates:
            new_rows.append(
                {
                    "Year": row_date.year,
                    "Month": row_date.month,
                    "Unemployment": round(row[1]),
                    "Date": row_month_start,
                }
            )

    if new_rows:
        df = pd.concat([df, pd.DataFrame(new_rows)], ignore_index=True)
        df = df.sort_values("Date").reset_index(drop=True)
        print(f"  {len(new_rows)} past prediction(s) merged into training data from database.")

    return df


def engineer_features(df: pd.DataFrame) -> pd.DataFrame:
    """Add time-based and lag features for model training.

    All features are derived from the Unemployment column and the calendar
    position of each row. No external data sources are needed.

    :param df: Input DataFrame with 'Unemployment' column.
    :type df: pandas.DataFrame
    :return: DataFrame with engineered features.
    :rtype: pandas.DataFrame
    """
    df = df.copy()

    df["TimeIndex"] = range(1, len(df) + 1)

    df["Month_sin"] = np.sin(2 * math.pi * df["Month"] / 12)
    df["Month_cos"] = np.cos(2 * math.pi * df["Month"] / 12)

    df["Lag1"] = df["Unemployment"].shift(1)
    df["Lag2"] = df["Unemployment"].shift(2)
    df["Lag3"] = df["Unemployment"].shift(3)
    df["Lag6"] = df["Unemployment"].shift(6)
    df["Lag12"] = df["Unemployment"].shift(12)

    df["Rolling3"] = df["Unemployment"].shift(1).rolling(3).mean()
    df["Rolling6"] = df["Unemployment"].shift(1).rolling(6).mean()

    df["MoM_Change"] = df["Unemployment"].shift(1) - df["Unemployment"].shift(2)
    df["YoY_Change"] = df["Unemployment"].shift(1) - df["Unemployment"].shift(13)

    return df


def build_target_row(df: pd.DataFrame, target_date: datetime) -> pd.DataFrame:
    """Construct a single feature row for the month to be predicted.

    Uses the most recent known values in df to populate all lag and rolling
    features as if the target month were the next row in the time series.

    :param df: Training DataFrame containing recent history.
    :type df: pandas.DataFrame
    :param target_date: The month to forecast.
    :type target_date: datetime.datetime
    :return: Single-row DataFrame containing all feature columns for the target month.
    :rtype: pandas.DataFrame
    """
    last = df.iloc[-1]

    row = {
        "Year": target_date.year,
        "Month": target_date.month,
        "TimeIndex": last["TimeIndex"] + 1,
        "Month_sin": math.sin(2 * math.pi * target_date.month / 12),
        "Month_cos": math.cos(2 * math.pi * target_date.month / 12),
        "Lag1": last["Unemployment"],
        "Lag2": df.iloc[-2]["Unemployment"] if len(df) >= 2 else np.nan,
        "Lag3": df.iloc[-3]["Unemployment"] if len(df) >= 3 else np.nan,
        "Lag6": df.iloc[-6]["Unemployment"] if len(df) >= 6 else np.nan,
        "Lag12": df[df["Month"] == target_date.month].iloc[-1]["Unemployment"]
        if len(df[df["Month"] == target_date.month]) > 0
        else np.nan,
        "Rolling3": df["Unemployment"].iloc[-3:].mean(),
        "Rolling6": df["Unemployment"].iloc[-6:].mean(),
        "MoM_Change": df.iloc[-1]["Unemployment"] - df.iloc[-2]["Unemployment"]
        if len(df) >= 2
        else np.nan,
        "YoY_Change": df.iloc[-1]["Unemployment"] - df.iloc[-13]["Unemployment"]
        if len(df) >= 13
        else np.nan,
    }
    return pd.DataFrame([row])


def save_prediction(
    target_date: datetime,
    prediction: float,
    best_model: str,
    framework: str,
    r2: float = None,
    rmse: float = None,
    mae: float = None,
    overwrite: bool = True,
) -> None:
    """Persist prediction results.

    If overwrite=True (production), it is saved in the PostgreSQL database 'predictions' table.
    If overwrite=False (testing), it is saved in the database 'test_runs' table.

    :param target_date: Forecast target month.
    :type target_date: datetime.datetime
    :param prediction: Predicted unemployment count.
    :type prediction: float
    :param best_model: Name of the model that generated the prediction.
    :type best_model: str
    :param framework: AutoML framework name ('automl' or 'autosklearn').
    :type framework: str
    :param r2: Model R² score.
    :type r2: float, optional
    :param rmse: Model Root Mean Squared Error.
    :type rmse: float, optional
    :param mae: Model Mean Absolute Error.
    :type mae: float, optional
    :param overwrite: Whether to write to predictions table (True) or test runs table (False).
    :type overwrite: bool
    """
    engine = get_db_engine()
    if not overwrite:
        # Save to database table 'test_runs'
        with engine.connect() as conn:
            insert_query = sa.text(
                "INSERT INTO test_runs (framework, year, month, run_timestamp, prediction, model, r2, rmse, mae) "
                "VALUES (:framework, :year, :month, :run_timestamp, :prediction, :model, :r2, :rmse, :mae)"
            )
            conn.execute(
                insert_query,
                {
                    "framework": framework,
                    "year": target_date.year,
                    "month": target_date.month,
                    "run_timestamp": datetime.now(),
                    "prediction": int(round(prediction)),
                    "model": best_model,
                    "r2": float(r2) if r2 is not None else None,
                    "rmse": float(rmse) if rmse is not None else None,
                    "mae": float(mae) if mae is not None else None
                }
            )
            conn.commit()
        print(f"Test run prediction saved to database table 'test_runs' for {framework}")
        try:
            from .model_selection import archive_test_runs
            archive_test_runs(framework=framework)
        except Exception as err:
            print(f"[WARNING] Could not run test run archival: {err}")
        return

    # Production mode: Save to PostgreSQL database predictions table
    with engine.connect() as conn:
        delete_query = sa.text(
            "DELETE FROM predictions WHERE framework = :framework AND year = :year AND month = :month"
        )
        conn.execute(
            delete_query,
            {"framework": framework, "year": target_date.year, "month": target_date.month}
        )
        
        insert_query = sa.text(
            "INSERT INTO predictions (framework, year, month, target_date, prediction, model, run_timestamp, r2, rmse, mae) "
            "VALUES (:framework, :year, :month, :target_date, :prediction, :model, :run_timestamp, :r2, :rmse, :mae)"
        )
        conn.execute(
            insert_query,
            {
                "framework": framework,
                "year": target_date.year,
                "month": target_date.month,
                "target_date": target_date.date(),
                "prediction": int(round(prediction)),
                "model": best_model,
                "run_timestamp": datetime.now(),
                "r2": float(r2) if r2 is not None else None,
                "rmse": float(rmse) if rmse is not None else None,
                "mae": float(mae) if mae is not None else None
            }
        )
        conn.commit()
    print(f"Production prediction saved to database table 'predictions' for {framework}")





def get_feature_columns() -> list:
    """Return the list of feature column names used in model training.

    :return: List of feature names.
    :rtype: list

    >>> cols = get_feature_columns()
    >>> "Year" in cols and "Month" in cols
    True
    """
    return [
        "Year", "Month", "TimeIndex",
        "Month_sin", "Month_cos",
        "Lag1", "Lag2", "Lag3", "Lag6", "Lag12",
        "Rolling3", "Rolling6",
        "MoM_Change", "YoY_Change",
    ]
