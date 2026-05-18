"""forecast_common.py
Common utilities shared by automl_forecast.py and autosklearn_forecast.py.

Provides centralized data loading, feature engineering, and prediction
persistence helpers used by both forecasting pipelines.
"""

import math # Used for sine/cosine calculations in cyclical encoding
import warnings # Used for suppressing non-critical warnings during runtime
import numpy as np # Used for numerical operations and handling NaN values
import pandas as pd # Used for data manipulation and analysis
from pathlib import Path # Used for handling file paths in a platform-independent way
from datetime import datetime # Used for working with dates and timestamps
import fetch_data_to_csv # Used to ensure data is updated before loading
# Suppress non-critical warnings from pandas, numpy and sklearn during runtime
warnings.filterwarnings("ignore")

# Path to the official BA monthly unemployment data (source of truth)
DATA_FILE = Path("files/unemployment_germany.csv")

# Path where forecasts are saved for self-improvement on future runs
PREDICTIONS_FILE_AUTOML = Path("files/automl_predictions.csv")
PREDICTIONS_FILE_AUTOSKLEARN = Path("files/autosklearn_predictions.csv")

# How many rows of the leaderboard are printed to the console
TOP_MODELS_TO_SHOW = 10


# List of feature column names used in model training (must match engineer_features output)
def load_data() -> pd.DataFrame:
    """Load the source CSV and return a complete gap-free monthly timeline.

    Handles potential chronological gaps in historical BA data by reindexing
    to a continuous monthly grid and interpolating internal missing months,
    guaranteeing mathematically correct step sizes for time-series features.
    """
    # Ensure the latest data is downloaded and the CSV is updated
    try:
        fetch_data_to_csv.main()
    except Exception as exc:
        print(f"  [WARNING] Could not update source data from BA website ({exc.__class__.__name__}).")
        if DATA_FILE.exists():
            print("            Falling back to existing local CSV file.")
        else:
            print("            No local CSV file found. Cannot proceed.")
            raise exc

    df = pd.read_csv(DATA_FILE, encoding="utf-8-sig")

    # Remove any leading/trailing whitespace from column names
    df.columns = df.columns.str.strip()

    # Create a proper datetime column so the frame can be sorted chronologically
    df["Date"] = pd.to_datetime(
        df["Year"].astype(str) + "-" + df["Month"].astype(str).str.zfill(2) + "-01"
    )
    df = df.sort_values("Date").reset_index(drop=True)

    # Find the first and last dates where we have actual official values
    df_with_val = df.dropna(subset=["Unemployment"])
    if df_with_val.empty:
        raise ValueError("No valid unemployment data found in the CSV!")

    min_date = df_with_val["Date"].min()
    max_date = df_with_val["Date"].max()

    # Filter df to only include the range from min_date to max_date
    df = df[(df["Date"] >= min_date) & (df["Date"] <= max_date)].copy()

    # Reindex to a complete monthly grid to detect and fill any internal chronological gaps
    full_range = pd.date_range(start=min_date, end=max_date, freq="MS")
    df = df.set_index("Date").reindex(full_range).reset_index().rename(columns={"index": "Date"})

    # Update Year and Month columns for any newly inserted rows from the index
    df["Year"] = df["Date"].dt.year
    df["Month"] = df["Date"].dt.month

    # Check if there are any internal missing values (gaps) to interpolate
    gaps_count = df["Unemployment"].isna().sum()
    if gaps_count > 0:
        print(f"  [WARNING] Found {gaps_count} internal missing month(s) in historical data.")
        # Linearly interpolate missing unemployment figures to keep step sizes mathematically correct
        df["Unemployment"] = df["Unemployment"].interpolate(method="linear")
        # Round back to integers since unemployment figures are whole numbers
        df["Unemployment"] = df["Unemployment"].round().astype(int)
        print("            Internal gaps successfully interpolated.")
    else:
        # Cast to int: official BA figures are whole numbers
        df["Unemployment"] = df["Unemployment"].astype(int)

    return df


# Merge past predictions into the training data to allow the model to learn from its own forecasts over time (self-improvement loop)
def merge_past_predictions(df: pd.DataFrame, predictions_file: Path, target_date: datetime) -> pd.DataFrame:
    """Merge previously saved predictions as actual values where gaps exist.

    Any month that was forecast in a prior run but still has no official value
    in the source CSV is added to the training frame so the model can learn from
    cumulative predictions over time. Only predictions for months strictly before
    the target_date are merged to avoid feature leakage and mismatched target rows.

    Self-improvement loop:
      run 1  →  forecast May  →  saved to predictions_file
      run 2  →  May forecast merged as training row  →  model trained on more data
      run N  →  increasingly accurate as more forecasts accumulate
    """
    # Nothing to merge if no prior predictions exist yet
    if not predictions_file.exists():
        return df

    pred = pd.read_csv(predictions_file, encoding="utf-8-sig") # load the predictions file which contains past forecasts with their target dates and predicted values
    pred["Date"] = pd.to_datetime(pred["Date"]) # convert the Date column to datetime for proper merging and comparison with the training data's Date column

    # Build a set of dates already in the official data for fast lookup
    existing_dates = set(df["Date"])
    new_rows = []

    for _, row in pred.iterrows(): # iterate over each past prediction, and if its target date is not already in the official data, add it as a new row with the predicted value as the Unemployment figure so the model can learn from it in future runs
        # Only add a prediction if it is strictly before the target month and the official value is still missing
        row_month_start = pd.to_datetime(f"{row['Date'].year}-{row['Date'].month:02d}-01")
        target_month_start = pd.to_datetime(f"{target_date.year}-{target_date.month:02d}-01")
        if row_month_start < target_month_start and row_month_start not in existing_dates:
            new_rows.append(
                {
                    "Year": row["Date"].year,
                    "Month": row["Date"].month,
                    "Unemployment": round(row["Prediction"]),  # rounded integer
                    "Date": row_month_start,
                }
            )

    if new_rows: # if there are any new rows to add, append them to the training data and re-sort by date so the time order is preserved for feature engineering
        # Append the new rows and re-sort so the time order is preserved
        df = pd.concat([df, pd.DataFrame(new_rows)], ignore_index=True)
        df = df.sort_values("Date").reset_index(drop=True)
        print(f"  {len(new_rows)} past prediction(s) merged into training data.")

    return df


# Feature engineering: create time-based and lag features from the Unemployment column and calendar metadata to give the model more signals to learn from. All features are derived from existing data, no external sources needed.
def engineer_features(df: pd.DataFrame) -> pd.DataFrame:
    """Add time-based and lag features for model training.

    All features are derived from the Unemployment column and the calendar
    position of each row. No external data sources are needed.

    Feature rationale:
      - TimeIndex    : gives the model an explicit sense of overall trend direction
      - Month_sin/cos: encodes the 12-month seasonal cycle without ordinal bias
      - Lag1-6       : captures short-term autocorrelation (last 1–6 months)
      - Lag12        : captures the same-month effect from the previous year
      - Rolling3/6   : smoothed recent trend used as a stable signal
      - MoM_Change   : velocity of change (first derivative, monthly)
      - YoY_Change   : velocity of change vs. same month one year ago
    """
    df = df.copy()

    # Sequential integer index: row 1 = oldest data point, row N = most recent
    df["TimeIndex"] = range(1, len(df) + 1)

    # Sine/cosine encoding converts month (1–12) into two continuous values
    # so the model sees that December and January are adjacent, not far apart
    df["Month_sin"] = np.sin(2 * math.pi * df["Month"] / 12)
    df["Month_cos"] = np.cos(2 * math.pi * df["Month"] / 12)

    # Lag features: unemployment N months ago (shift by N rows)
    df["Lag1"] = df["Unemployment"].shift(1)    # one month ago
    df["Lag2"] = df["Unemployment"].shift(2)    # two months ago
    df["Lag3"] = df["Unemployment"].shift(3)    # three months ago
    df["Lag6"] = df["Unemployment"].shift(6)    # six months ago
    df["Lag12"] = df["Unemployment"].shift(12)  # same month last year

    # Rolling means are computed on the already-shifted series so there is no
    # data leakage: the current month's value is never included in its own mean
    df["Rolling3"] = df["Unemployment"].shift(1).rolling(3).mean()
    df["Rolling6"] = df["Unemployment"].shift(1).rolling(6).mean()

    # First-order differences to give the model a sense of momentum
    df["MoM_Change"] = df["Unemployment"].shift(1) - df["Unemployment"].shift(2)
    df["YoY_Change"] = df["Unemployment"].shift(1) - df["Unemployment"].shift(13)

    return df


# When forecasting the current month, we need to construct a single feature row that represents the target month as if it were the next row in the time series. This function builds that row using the most recent known data to populate all lag and rolling features, allowing the model to make a prediction for the current month even though it has no official value yet.
def build_target_row(df: pd.DataFrame, target_date: datetime) -> pd.DataFrame:
    """Construct a single feature row for the month to be predicted.

    Uses the most recent known values in df to populate all lag and rolling
    features as if the target month were the next row in the time series.
    Falls back to NaN for features that require more history than is available.
    """
    last = df.iloc[-1]  # most recent known data point

    row = {
        # Calendar metadata for the target month
        "Year": target_date.year,
        "Month": target_date.month,

        # TimeIndex for the new row is one step beyond the last known index
        "TimeIndex": last["TimeIndex"] + 1,

        # Cyclical encoding for the target month
        "Month_sin": math.sin(2 * math.pi * target_date.month / 12),
        "Month_cos": math.cos(2 * math.pi * target_date.month / 12),

        # Lag1: the most recently confirmed unemployment figure
        "Lag1": last["Unemployment"],

        # Lag2/3/6: second, third, and sixth most recent figures (guard against short history)
        "Lag2": df.iloc[-2]["Unemployment"] if len(df) >= 2 else np.nan,
        "Lag3": df.iloc[-3]["Unemployment"] if len(df) >= 3 else np.nan,
        "Lag6": df.iloc[-6]["Unemployment"] if len(df) >= 6 else np.nan,

        # Lag12: last occurrence of the same calendar month (year-over-year anchor)
        "Lag12": df[df["Month"] == target_date.month].iloc[-1]["Unemployment"]
        if len(df[df["Month"] == target_date.month]) > 0
        else np.nan,

        # Rolling averages over the last 3 and 6 known months
        "Rolling3": df["Unemployment"].iloc[-3:].mean(),
        "Rolling6": df["Unemployment"].iloc[-6:].mean(),

        # Month-over-month momentum: most recent change
        "MoM_Change": df.iloc[-1]["Unemployment"] - df.iloc[-2]["Unemployment"]
        if len(df) >= 2
        else np.nan,

        # Year-over-year momentum: change vs. 13 months ago
        "YoY_Change": df.iloc[-1]["Unemployment"] - df.iloc[-13]["Unemployment"]
        if len(df) >= 13
        else np.nan,
    }
    return pd.DataFrame([row])



# After forecasting the current month, we want to save the prediction to a CSV file that serves as a cumulative log of all forecasts made over time. This allows us to track our model's predictions, compare them against eventual official values, and also feed them back into the training data for self-improvement on future runs.
def save_prediction(
    target_date: datetime,
    prediction: float,
    best_model: str,
    predictions_file: Path,
    r2: float = None,
    rmse: float = None,
    mae: float = None,
) -> None:
    """Append the current forecast to the predictions CSV.

    If a forecast for the same month already exists it is replaced so only the
    latest run's result is stored. The file is created automatically if it
    does not exist yet.
    """
    row = {
        "Date": target_date.strftime("%Y-%m-%d"),
        "Year": target_date.year,
        "Month": target_date.month,
        "Prediction": round(prediction),          # whole-number forecast
        "Model": best_model,                      # best-performing model name
        "Run_Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    if r2 is not None:
        row["R2 (%)"] = r2
    if rmse is not None:
        row["RMSE"] = rmse
    if mae is not None:
        row["MAE"] = mae

    # Build a one-row DataFrame for the new entry
    new_entry = pd.DataFrame([row])

    # Create the files directory if it does not exist
    predictions_file.parent.mkdir(parents=True, exist_ok=True)

    if predictions_file.exists():
        existing = pd.read_csv(predictions_file, encoding="utf-8-sig")
        existing["Date"] = pd.to_datetime(existing["Date"])

        # Remove any stale forecast for the same target month before appending
        # so each month always holds only the most recent forecast
        existing = existing[
            ~((existing["Year"] == target_date.year) & (existing["Month"] == target_date.month))
        ]
        combined = pd.concat([existing, new_entry], ignore_index=True)
    else:
        # First run — the new entry is the entire file
        combined = new_entry

    combined.to_csv(predictions_file, index=False, encoding="utf-8-sig")
    print(f"Prediction saved to {predictions_file}")


def write_unified_outputs(target_date: datetime) -> None:
    """Combine automl and autosklearn predictions and write a unified CSV.

    Allows easy comparison and downstream analysis of both AutoML forecasts.
    """
    automl_exists = PREDICTIONS_FILE_AUTOML.exists()
    autosklearn_exists = PREDICTIONS_FILE_AUTOSKLEARN.exists()

    if not automl_exists and not autosklearn_exists:
        return

    dfs = []
    if automl_exists:
        df_aml = pd.read_csv(PREDICTIONS_FILE_AUTOML, encoding="utf-8-sig")
        df_aml = df_aml.rename(columns={
            "Prediction": "Prediction_AutoML",
            "Model": "Model_AutoML",
            "R2 (%)": "R2_AutoML (%)",
            "RMSE": "RMSE_AutoML",
            "MAE": "MAE_AutoML",
            "Run_Timestamp": "Run_Timestamp_AutoML"
        })
        dfs.append(df_aml)

    if autosklearn_exists:
        df_ask = pd.read_csv(PREDICTIONS_FILE_AUTOSKLEARN, encoding="utf-8-sig")
        df_ask = df_ask.rename(columns={
            "Prediction": "Prediction_AutoSklearn",
            "Model": "Model_AutoSklearn",
            "R2 (%)": "R2_AutoSklearn (%)",
            "RMSE": "RMSE_AutoSklearn",
            "MAE": "MAE_AutoSklearn",
            "Run_Timestamp": "Run_Timestamp_AutoSklearn"
        })
        dfs.append(df_ask)

    if len(dfs) == 1:
        unified = dfs[0]
    else:
        # Merge on Date, Year, Month
        unified = pd.merge(dfs[0], dfs[1], on=["Date", "Year", "Month"], how="outer")

    UNIFIED_FILE = Path("files/unified_predictions.csv")
    unified.to_csv(UNIFIED_FILE, index=False, encoding="utf-8-sig")
    print(f"Unified predictions saved to {UNIFIED_FILE}")

    # Also write a beautiful Markdown version for easy comparison
    md_lines = [
        "# Unified Unemployment Predictions\n",
        "This file is automatically generated after each forecasting run. It provides a side-by-side comparison of **H2O AutoML** and **Auto-sklearn** predictions.\n",
    ]
    
    # Sort unified descending by Date so the latest run is at the top of the file
    unified_sorted = unified.sort_values("Date", ascending=False)
    
    for _, row in unified_sorted.iterrows():
        # Target month name formatting (e.g., "May 2026")
        target_month_dt = pd.to_datetime(f"{int(row['Year'])}-{int(row['Month']):02d}-01")
        month_name = target_month_dt.strftime("%B %Y")
        run_date_str = str(row["Date"])[:10]
        
        md_lines.append(f"## Forecast Comparison for {month_name} (Run Date: {run_date_str})\n")
        md_lines.append("| Metric | H2O AutoML | Auto-sklearn |")
        md_lines.append("|---|---|---|")
        
        # Predicted Unemployment
        aml_pred = f"**{int(row['Prediction_AutoML']):,}**" if "Prediction_AutoML" in row and pd.notna(row["Prediction_AutoML"]) else "N/A"
        ask_pred = f"**{int(row['Prediction_AutoSklearn']):,}**" if "Prediction_AutoSklearn" in row and pd.notna(row["Prediction_AutoSklearn"]) else "N/A"
        md_lines.append(f"| **Predicted Unemployment** | {aml_pred} | {ask_pred} |")
        
        # Best Model
        if "Model_AutoML" in row and pd.notna(row["Model_AutoML"]):
            full_model_name = str(row["Model_AutoML"])
            if "StackedEnsemble" in full_model_name:
                aml_model = "`StackedEnsemble`"
            elif "GBM" in full_model_name:
                aml_model = "`GBM`"
            elif "XGBoost" in full_model_name:
                aml_model = "`XGBoost`"
            elif "DeepLearning" in full_model_name:
                aml_model = "`DeepLearning`"
            else:
                aml_model = f"`{full_model_name}`"
        else:
            aml_model = "N/A"
            
        ask_model = f"`{row['Model_AutoSklearn']}`" if "Model_AutoSklearn" in row and pd.notna(row["Model_AutoSklearn"]) else "N/A"
        md_lines.append(f"| **Best Model** | {aml_model} | {ask_model} |")
        
        # R2 Score
        if "R2_AutoML (%)" in row and pd.notna(row["R2_AutoML (%)"]):
            aml_r2 = f"`{row['R2_AutoML (%)']:.2f} %`" if isinstance(row["R2_AutoML (%)"], float) else f"`{row['R2_AutoML (%)']} %`"
        else:
            aml_r2 = "N/A"
            
        if "R2_AutoSklearn (%)" in row and pd.notna(row["R2_AutoSklearn (%)"]):
            ask_r2 = f"`{row['R2_AutoSklearn (%)']:.2f} %`" if isinstance(row["R2_AutoSklearn (%)"], float) else f"`{row['R2_AutoSklearn (%)']} %`"
        else:
            ask_r2 = "N/A"
        md_lines.append(f"| **R² Score** | {aml_r2} | {ask_r2} |")
        
        # RMSE
        aml_rmse = f"`{int(row['RMSE_AutoML']):,}`" if "RMSE_AutoML" in row and pd.notna(row["RMSE_AutoML"]) else "N/A"
        ask_rmse = f"`{int(row['RMSE_AutoSklearn']):,}`" if "RMSE_AutoSklearn" in row and pd.notna(row["RMSE_AutoSklearn"]) else "N/A"
        md_lines.append(f"| **RMSE** | {aml_rmse} | {ask_rmse} |")
        
        # MAE
        aml_mae = f"`{int(row['MAE_AutoML']):,}`" if "MAE_AutoML" in row and pd.notna(row["MAE_AutoML"]) else "N/A"
        ask_mae = f"`{int(row['MAE_AutoSklearn']):,}`" if "MAE_AutoSklearn" in row and pd.notna(row["MAE_AutoSklearn"]) else "N/A"
        md_lines.append(f"| **MAE** | {aml_mae} | {ask_mae} |")
        
        md_lines.append("\n---\n")
        
    UNIFIED_MD = Path("files/unified_predictions.md")
    with open(UNIFIED_MD, "w", encoding="utf-8") as f:
        f.write("\n".join(md_lines) + "\n")
    print(f"Unified Markdown table saved to {UNIFIED_MD}")


# List of feature column names used in model training (must match engineer_features output)
def get_feature_columns() -> list:
    """Return the list of feature column names used in model training."""
    return [
        "Year", "Month", "TimeIndex",
        "Month_sin", "Month_cos",
        "Lag1", "Lag2", "Lag3", "Lag6", "Lag12",
        "Rolling3", "Rolling6",
        "MoM_Change", "YoY_Change",
    ]
