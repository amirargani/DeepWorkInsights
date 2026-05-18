"""automl_forecast.py
H2O AutoML-based forecast pipeline for German monthly unemployment.

This module trains an H2O AutoML pipeline (when available) to predict the
next month's unemployment figure. If H2O or Java is not available the
script falls back to a small set of sklearn regressors that mimic H2O's
main families. Predictions are saved so future runs can re-use prior
forecasts as training rows (self-improvement loop).

Source data: files/unemployment_germany.csv
Predictions file: files/automl_predictions.csv
"""

import math # Used for sqrt in RMSE calculation
import warnings # Used for runtime warning suppression
import pandas as pd # Used for data manipulation
from datetime import datetime # Used for date handling
from sklearn.ensemble import ( # sklearn regressors for H2O fallback
    ExtraTreesRegressor,
    GradientBoostingRegressor,
    RandomForestRegressor,
)
from sklearn.impute import SimpleImputer # Used for handling any NaNs in the feature matrix
from sklearn.linear_model import Ridge # Used for linear regression with L2 regularization (H2O GLM fallback)
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score # Used for model evaluation in the sklearn fallback

# Import common functions from shared module
from forecast_common import (
    load_data,
    merge_past_predictions,
    engineer_features,
    build_target_row,
    save_prediction,
    get_feature_columns,
    TOP_MODELS_TO_SHOW,
    PREDICTIONS_FILE_AUTOML,
    write_unified_outputs,
)

# Suppress non-critical warnings from pandas, numpy and h2o during runtime
warnings.filterwarnings("ignore")
# Specifically suppress the H2O multi-threading/polars warning by matching the text
warnings.filterwarnings("ignore", message=".*Converting H2O frame to pandas dataframe using single-thread.*")

# Maximum total wall-clock seconds H2O AutoML is allowed to search for models
MAX_AUTOML_RUNTIME = 120

# Use the AutoML-specific predictions file
PREDICTIONS_FILE = PREDICTIONS_FILE_AUTOML

# When H2O AutoML is unavailable, this function trains a small set of sklearn
# regressors that mimic the main H2O model families (GBM, RF, GLM) and ranks
# them by R² to select the best one for prediction and display.
def _run_sklearn_fallback(
    df_train: pd.DataFrame,
    feature_cols: list,
    target_row: pd.DataFrame,
    target_date: datetime,
) -> None:
    """Train sklearn equivalents of the H2O model families as a fallback.

    Used when Java or the h2o package is unavailable on the host machine.
    Mirrors the four main model families H2O AutoML would consider:
    GradientBoosting (≈ GBM), RandomForest, ExtraTrees (≈ RF variant),
    Ridge (≈ GLM).  Results are ranked by R² and the best model wins.
    """
    print("\n  Falling back to sklearn equivalents of H2O model families.")

    X_all = df_train[feature_cols].values # feature matrix for training (after engineering and NaN row drop)
    y_all = df_train["Unemployment"].values # target vector for training

    split = max(1, int(len(X_all) * 0.8)) # 80/20 train/test split (at least 1 row in test set)
    X_tr, X_te = X_all[:split], X_all[split:] # split feature matrix into training and testing sets
    y_tr, y_te = y_all[:split], y_all[split:] # split target vector into training and testing sets

    imputer = SimpleImputer(strategy="mean") # imputer to handle any NaNs in the feature matrix (should be none after row drop, but just in case)
    X_tr  = imputer.fit_transform(X_tr) # fit imputer on training features and transform
    X_te  = imputer.transform(X_te) # transform test features with the same imputer (using training set statistics)
    X_tgt = imputer.transform(target_row[feature_cols].values) # transform the single target row's features with the same imputer

    # Define the candidate models to train, mimicking H2O's main families. Hyperparameters are chosen to be reasonable defaults that allow for some complexity without overfitting on a small dataset.
    candidates = {
        "GradientBoosting (GBM)": GradientBoostingRegressor( # a powerful ensemble model that often performs well on tabular data, similar to H2O's GBM
            n_estimators=500, max_depth=4, learning_rate=0.05, random_state=42
        ),
        "RandomForest": RandomForestRegressor( # a strong all-around ensemble model that often performs well with minimal tuning
            n_estimators=500, random_state=42, n_jobs=-1
        ),
        "ExtraTrees": ExtraTreesRegressor( # a more randomized RF variant that can sometimes outperform standard RFs
            n_estimators=500, random_state=42, n_jobs=-1
        ),
        "Ridge": Ridge(alpha=1.0), # linear regression with L2 regularization as a GLM fallback
    }

    rows = [] # list to hold leaderboard rows for display and selection of the best model
    for name, model in candidates.items(): # iterate over candidate models
        model.fit(X_tr, y_tr) # fit the model on the training data
        y_pred = model.predict(X_te) # predict on the test set to evaluate performance
        r2   = round(r2_score(y_te, y_pred) * 100, 2) # calculate R² and convert to percentage for display
        rmse = int(round(math.sqrt(mean_squared_error(y_te, y_pred)))) # calculate RMSE and round to nearest integer for display
        mae  = int(round(float(mean_absolute_error(y_te, y_pred)))) # calculate MAE and round to nearest integer for display
        pred = int(round(float(model.predict(X_tgt)[0]))) # predict the target month and round to nearest integer for display
        rows.append({"Model": name, "R2 (%)": r2, "RMSE": rmse, "MAE": mae, # append the results to the leaderboard list
                     "Prediction": pred})

    lb   = pd.DataFrame(rows).sort_values("R2 (%)", ascending=False).reset_index(drop=True) # create a DataFrame from the results and sort by R² in descending order to rank the models
    best = lb.iloc[0] # select the best model (the one with the highest R²) for display and saving the prediction

    # Display the leaderboard and the best model's prediction in a clear format
    print("\n--- Model Leaderboard (Top {}) ---".format(TOP_MODELS_TO_SHOW))
    print(lb[["Model", "R2 (%)", "RMSE", "MAE", "Prediction"]].head(TOP_MODELS_TO_SHOW).to_string(index=False))

    print("\n" + "=" * 60)
    print(f"  Forecast for {target_date.strftime('%B %Y')}")
    print(f"  Predicted unemployment: {best['Prediction']:,}")
    print(f"  Best model:             {best['Model']}")
    print(f"  R²:                     {best['R2 (%)']:.2f} %")
    print(f"  RMSE:                   {best['RMSE']:,}")
    print("=" * 60)

    save_prediction(
        target_date,
        best["Prediction"],
        best["Model"],
        PREDICTIONS_FILE,
        r2=best["R2 (%)"],
        rmse=best["RMSE"],
        mae=best["MAE"],
    ) # save the best model's prediction to the predictions file for future use and self-improvement

# Main entry point of the script: loads data, trains AutoML (or sklearn fallback), and forecasts the current month.
def run() -> None:
    """Main entry point: load data, train AutoML, forecast current month.

    Tries H2O AutoML first (requires Java 11+ and the h2o package).
    Falls back to sklearn equivalents of the same model families when Java
    or h2o is unavailable on the current machine.
    """
    print("=" * 60)
    print("  DeepWorkInsights – H2O AutoML Unemployment Forecast")
    print("=" * 60)

    # Target is dynamically determined based on the current run date
    now = datetime.now()
    target_date = datetime(now.year, now.month, now.day)
    print(f"\nTarget month: {target_date.strftime('%B %Y')}")

    # Step 1: load official data
    print("\nLoading data ...")
    df_raw = load_data()

    # Skip forecasting if the official value for this month already exists
    last_known = df_raw["Date"].max()
    if last_known >= target_date:
        print(
            f"\nActual data for {target_date.strftime('%B %Y')} already exists "
            f"(value: {df_raw[df_raw['Date'] == target_date]['Unemployment'].values[0]:,}). "
            "No forecast needed."
        )
        return

    # Step 1.5: Optionally extend the training data with past predictions
    df_raw = merge_past_predictions(df_raw, PREDICTIONS_FILE, target_date)

    # Step 2: engineer all features and define the feature column list
    df_feat = engineer_features(df_raw)
    feature_cols = get_feature_columns()

    # Remove early rows where lag/rolling features are NaN (insufficient history)
    df_train = df_feat.dropna(subset=feature_cols).copy()
    print(f"Training rows after feature engineering: {len(df_train)}")

    # Step 3: build the single-row feature vector for the month to predict
    target_row = build_target_row(df_feat, target_date)

    # Step 4: try H2O AutoML; fall back to sklearn if Java / h2o is absent
    try:
        import h2o
        from h2o.automl import H2OAutoML

        print("\nInitialising H2O ...")
        h2o.init(verbose=False)

        # Convert pandas DataFrames to H2O's internal frame format
        train_h2o  = h2o.H2OFrame(df_train[feature_cols + ["Unemployment"]])
        target_h2o = h2o.H2OFrame(target_row[feature_cols])

        # Step 5: run AutoML — H2O trains all model families within the time budget
        print(f"\nRunning H2O AutoML (max runtime: {MAX_AUTOML_RUNTIME}s) ...")
        aml = H2OAutoML( # initialize AutoML with the specified parameters: max runtime, random seed for reproducibility, sorting metric (RMSE), and verbosity level
            #max_models=20, # Optional: limit the total number of models tried to keep the leaderboard more interpretable (commented out to allow full exploration within the time budget)
            max_runtime_secs=MAX_AUTOML_RUNTIME,
            seed=42,
            sort_metric="RMSE",
            verbosity=None,
        )
        aml.train(x=feature_cols, y="Unemployment", training_frame=train_h2o) # train AutoML on the training data with the specified features and target

        # Step 6: extract the leaderboard (H2O returns a leaderboard frame)
        lb = aml.leaderboard.as_data_frame()
        lb["RMSE"] = lb["rmse"].round(0).astype(int)
        lb["R2 (%)"] = float("nan")
        best_r2 = float("nan")

        if "r2" in lb.columns: # if H2O's leaderboard includes R², use it directly for display and ranking
            lb["R2 (%)"] = (lb["r2"] * 100).round(2)
            display_cols = ["model_id", "R2 (%)", "RMSE", "mae"]
            best_r2 = lb.iloc[0]["R2 (%)"]
        else: # if R² is not included in the leaderboard, fetch it for the top models
            display_cols = ["model_id", "R2 (%)", "RMSE", "mae"]
            print("\n    [NOTICE] H2O leaderboard omitted r2; fetching R² for top models.")
            for idx in range(min(TOP_MODELS_TO_SHOW, len(lb))):
                try:
                    m = h2o.get_model(lb.iloc[idx]["model_id"])
                    perf = m.model_performance(xval=True)
                    r2_val = perf.r2() if perf is not None else None
                    
                    if r2_val is None or str(r2_val).lower() == 'nan':
                        perf = m.model_performance(train=True)
                        r2_val = perf.r2() if perf is not None else None
                        
                    if r2_val is None or str(r2_val).lower() == 'nan':
                        train_preds = m.predict(train_h2o).as_data_frame().iloc[:, 0].astype(float)
                        r2_val = r2_score(df_train["Unemployment"].values, train_preds)
                        
                    lb.loc[idx, "R2 (%)"] = round(r2_val * 100, 2)
                except Exception:
                    pass
            best_r2 = lb.iloc[0]["R2 (%)"]

        # Display the leaderboard and the best model's prediction in a clear format
        print("\n--- Model Leaderboard (Top {}) ---".format(TOP_MODELS_TO_SHOW))
        print(
            lb[display_cols]
            .head(TOP_MODELS_TO_SHOW)
            .rename(columns={"model_id": "Model", "mae": "MAE"})
            .to_string(index=False)
        )

        # Step 7: predict with the leader
        prediction = aml.leader.predict(target_h2o).as_data_frame().iloc[0, 0]
        best_rmse = lb.iloc[0]["RMSE"]
        best_id   = lb.iloc[0]["model_id"]

        # Display the best model's prediction and performance metrics in a clear format
        print("\n" + "=" * 60)
        print(f"  Forecast for {target_date.strftime('%B %Y')}")
        print(f"  Predicted unemployment: {int(round(prediction)):,}")
        print(f"  Best model:             {best_id}")
        print(f"  R²:                     {best_r2:.2f} %")
        print(f"  RMSE:                   {best_rmse:,}")
        print("=" * 60)

        best_mae = int(round(float(lb.iloc[0]["mae"]))) if "mae" in lb.columns else None
        save_prediction(
            target_date,
            prediction,
            best_id,
            PREDICTIONS_FILE,
            r2=best_r2,
            rmse=best_rmse,
            mae=best_mae,
        ) # save the best model's prediction to the predictions file for future use and self-improvement

    except (ImportError, Exception) as exc: # catch both ImportError for missing h2o and any other exceptions that may occur during H2O initialization or training (like Java-related issues)
        if isinstance(exc, ImportError):
            print("    [SKIP] h2o package not installed.")
        else:
            print(f"    [SKIP] H2O could not be started: {exc.__class__.__name__}")
            print("           Make sure Java (JDK 11+) is installed, or run inside Docker.")
        _run_sklearn_fallback(df_train, feature_cols, target_row, target_date)

    finally: # attempt to shut down H2O if it was started, to free up resources (especially important in environments like Jupyter notebooks)
        try:
            import h2o as _h2o
            _h2o.cluster().shutdown(prompt=False)
        except Exception:
            pass

    write_unified_outputs(target_date)

# Run the script only when executed directly (not when imported as a module)
if __name__ == "__main__":
    run()
