"""autosklearn_forecast.py
Auto-sklearn-based forecast pipeline for German monthly unemployment.

This module trains an Auto-sklearn ensemble (when available) to predict the
next month's unemployment figure. It also includes transparent sklearn
baselines (polynomial regression and a fixed set of sklearn regressors) so
that leaderboard entries remain interpretable even if Auto-sklearn finds
unexpected pipelines.

Install notes: pip install auto-sklearn pandas numpy scikit-learn
"""

import os # used for os.devnull to suppress Auto-sklearn output during fit
import math # used for sqrt in RMSE calculation
import numpy as np # Used for array handling and numerical operations
import pandas as pd # Used for DataFrame handling and CSV I/O
import warnings # Used to suppress non-critical warnings from pandas, numpy and sklearn during runtime
from contextlib import redirect_stdout, redirect_stderr # Used to suppress Auto-sklearn output during fit
from datetime import datetime # Used for date handling and timestamping predictions
from pathlib import Path # Used for type hinting and file path handling

from sklearn.ensemble import ( # Used for explicit sklearn baselines and to identify ensemble member types in the leaderboard
    AdaBoostRegressor,
    ExtraTreesRegressor,
    GradientBoostingRegressor,
    RandomForestRegressor,
)
from sklearn.impute import SimpleImputer # Used for mean imputation of any remaining NaNs in the feature matrices
from sklearn.linear_model import ElasticNet, Lasso, LinearRegression, Ridge, SGDRegressor # Used for explicit sklearn baselines and the polynomial regression pipeline
from sklearn.metrics import mean_squared_error, r2_score # Used for evaluation metrics (RMSE and R²) on the hold-out test set
from sklearn.pipeline import Pipeline # Used to build the polynomial regression pipeline with feature expansion and scaling
from sklearn.preprocessing import PolynomialFeatures, StandardScaler # Used for polynomial feature expansion and scaling in the polynomial regression pipeline
from sklearn.neighbors import KNeighborsRegressor
from sklearn.svm import SVR
from sklearn.tree import DecisionTreeRegressor

# Suppress non-critical warnings from pandas, numpy and sklearn during runtime
warnings.filterwarnings("ignore")

# Import common functions from shared module
from forecast_common import (
    load_data,
    merge_past_predictions,
    engineer_features,
    build_target_row,
    save_prediction,
    get_feature_columns,
    TOP_MODELS_TO_SHOW,
    PREDICTIONS_FILE_AUTOSKLEARN,
    write_unified_outputs,
)

# Use the Auto-sklearn-specific predictions file
PREDICTIONS_FILE = PREDICTIONS_FILE_AUTOSKLEARN

MAX_AUTOML_RUNTIME = 120    # total seconds Auto-sklearn is allowed to train
MAX_SINGLE_RUN = 30         # max seconds per individual model run
ENSEMBLE_SIZE = 10          # number of models combined in the final ensemble


# Evaluate a simple polynomial regression pipeline as a transparent baseline.
def eval_polynomial_regression(
    X_train: np.ndarray,
    y_train: np.ndarray,
    X_test: np.ndarray,
    y_test: np.ndarray,
    X_target: np.ndarray,
    degree: int = 2,
) -> tuple[dict, float]:
    """Train a Polynomial Regression (degree 2) pipeline and return its metrics and prediction.

    Serves as a transparent baseline model alongside the Auto-sklearn ensemble.
    Pipeline: PolynomialFeatures → StandardScaler → LinearRegression.
    StandardScaler is required because polynomial expansion produces large feature
    values that can destabilise the least-squares solver without normalisation.

    Args:
        X_train:  Feature matrix for training.
        y_train:  Target values for training.
        X_test:   Feature matrix for hold-out evaluation.
        y_test:   Ground-truth values for hold-out evaluation.
        X_target: Single-row feature matrix for the month to forecast.
        degree:   Polynomial degree; defaults to 2 (quadratic interactions).

    Returns:
        A tuple of (metrics dict, scalar prediction) where metrics contains
        Model, R2 (%), RMSE, and MAE keys.
    """
    # Step 1: expand raw features into polynomial interaction terms
    # Step 2: scale to zero-mean/unit-variance so large polynomial values don't dominate
    # Step 3: fit ordinary least squares on the scaled polynomial feature space
    poly_pipeline = Pipeline([
        ("poly", PolynomialFeatures(degree=degree, include_bias=False)),
        ("scaler", StandardScaler()),
        ("lr", LinearRegression()),
    ])
    poly_pipeline.fit(X_train, y_train)

    # Evaluate on the hold-out test set
    y_pred = poly_pipeline.predict(X_test)
    r2 = r2_score(y_test, y_pred) * 100
    rmse = int(round(math.sqrt(mean_squared_error(y_test, y_pred))))
    mae = int(round(float(np.mean(np.abs(y_test - y_pred)))))

    # Forecast for the actual target month
    prediction = float(poly_pipeline.predict(X_target)[0])

    metrics = { # round R² to 2 decimal places for readability; RMSE and MAE are rounded to integers
        "Model": f"PolynomialRegression (deg {degree})",
        "R2 (%)": round(r2, 2),
        "RMSE": rmse,
        "MAE": mae,
    }
    return metrics, prediction


# Build a ranked leaderboard from the Auto-sklearn ensemble members by evaluating each member individually on the hold-out test set. This provides transparency into which specific pipelines Auto-sklearn found that performed well, and allows us to compare them against explicit sklearn baselines.
def build_leaderboard(
    automl, X_test: np.ndarray, y_test: np.ndarray) -> pd.DataFrame:
    """Build a ranked leaderboard from the Auto-sklearn ensemble members.

    Each model in the final ensemble is evaluated individually on the test set.
    Results are sorted by R² descending so the best model appears first.
    """
    rows = []

    # Iterate over each model in the Auto-sklearn ensemble and evaluate it on the test set
    for pipeline in automl.get_models_with_weights():

        try:
            y_pred = pipeline.predict(X_test)
            r2 = r2_score(y_test, y_pred)
            rmse = math.sqrt(mean_squared_error(y_test, y_pred))
            mae = float(np.mean(np.abs(y_test - y_pred)))

            # auto-sklearn wraps the actual regressor in a RegressorChoice step;
            # unwrap .choice to get the real estimator's class name
            estimator = pipeline.steps[-1][1]
            if hasattr(estimator, "choice"):
                model_name = type(estimator.choice).__name__
            else:
                model_name = type(estimator).__name__

            rows.append(
                {
                    "Model": model_name,
                    "R2 (%)": round(r2 * 100, 2),
                    "RMSE": int(round(rmse)),
                    "MAE": int(round(mae)),
                }
            )
        except Exception:
            continue

    df_lb = pd.DataFrame(rows)
    if df_lb.empty:
        return df_lb

    return df_lb.sort_values("R2 (%)", ascending=False).reset_index(drop=True) # sort by R² descending so the best model appears first


# Train a fixed set of sklearn regressors and score them on the hold-out set as transparent baselines alongside the Auto-sklearn ensemble.
def build_sklearn_candidates(
    X_train: np.ndarray,
    y_train: np.ndarray,
    X_test: np.ndarray,
    y_test: np.ndarray,
) -> pd.DataFrame:
    """Train a fixed set of sklearn regressors and score them on the hold-out set.

    These act as transparent baselines alongside the Auto-sklearn ensemble so
    the leaderboard always has well-understood reference points regardless of
    what auto-sklearn discovered in its time budget.
    """
    candidates = {
        "RandomForestRegressor":    RandomForestRegressor(n_estimators=500, random_state=42, n_jobs=-1),
        "ExtraTreesRegressor":      ExtraTreesRegressor(n_estimators=500, random_state=42, n_jobs=-1),
        "GradientBoostingRegressor":GradientBoostingRegressor(n_estimators=300, max_depth=4,
                                                               learning_rate=0.05, random_state=42),
        "AdaBoostRegressor":        AdaBoostRegressor(n_estimators=300, random_state=42),
        "DecisionTreeRegressor":    DecisionTreeRegressor(max_depth=5, random_state=42),
        "KNeighborsRegressor":      Pipeline([("scaler", StandardScaler()), ("knn", KNeighborsRegressor(n_neighbors=5))]),
        "SVR":                      Pipeline([("scaler", StandardScaler()), ("svr", SVR(C=1000.0, epsilon=0.1))]),
        "SGDRegressor":             Pipeline([("scaler", StandardScaler()), ("sgd", SGDRegressor(max_iter=1000, tol=1e-3, random_state=42))]),
        "Lasso":                    Lasso(alpha=1.0, max_iter=10000),
        "Ridge":                    Ridge(alpha=1.0),
        "ElasticNet":               ElasticNet(alpha=1.0, max_iter=10000),
    }

    rows = [] # list to hold leaderboard rows for each candidate model
    for name, model in candidates.items(): # fit each candidate model and evaluate on the hold-out test set; add results to the leaderboard rows
        try:
            model.fit(X_train, y_train)
            y_pred = model.predict(X_test)
            r2   = round(r2_score(y_test, y_pred) * 100, 2)
            rmse = int(round(math.sqrt(mean_squared_error(y_test, y_pred))))
            mae  = int(round(float(np.mean(np.abs(y_test - y_pred)))))
            rows.append({"Model": name, "R2 (%)": r2, "RMSE": rmse, "MAE": mae})
        except Exception:
            continue

    return pd.DataFrame(rows)





# Main entry point: load data, train Auto-sklearn, forecast current month, and build leaderboard.
def run() -> None:
    """Main entry point: load data, train Auto-sklearn, forecast current month.

    Execution flow:
      1.  Determine the current calendar month as the forecast target.
      2.  Load official BA data and merge any prior Auto-sklearn predictions.
      3.  Skip if the official value for this month is already available.
      4.  Engineer time-series features from the historical unemployment series.
      5.  Chronological 80/20 train–test split; impute remaining NaNs.
      6.  Train Auto-sklearn ensemble (all sklearn regressors, time-boxed).
      7.  Predict the target month with the trained ensemble.
      8.  Build a ranked leaderboard from ensemble members.
      9.  Train Polynomial Regression as a transparent baseline and add to leaderboard.
      10. Save the forecast to CSV for the self-improvement loop.
    """
    # Defer import so the module can be syntax-checked without auto-sklearn installed
    import autosklearn.regression  # type: ignore # noqa: PLC0415

    print("=" * 62)
    print("  DeepWorkInsights – Auto-sklearn Unemployment Forecast")
    print("=" * 62)

    # Step 1: determine the target month (dynamically based on the current run date)
    now = datetime.now()
    target_date = datetime(now.year, now.month, now.day)
    print(f"\nTarget month: {target_date.strftime('%B %Y')}")

    # Step 2: load official data
    print("\nLoading data ...")
    df_raw = load_data()

    # Step 3: skip forecast if the official value already exists in the source data
    last_known = df_raw["Date"].max()
    if last_known >= target_date:
        actual = df_raw[df_raw["Date"] == target_date]["Unemployment"].values[0]
        print(
            f"\nActual data for {target_date.strftime('%B %Y')} already exists "
            f"(value: {actual:,}). No forecast needed."
        )
        return

    # Merge any prior forecasts as training rows
    df_raw = merge_past_predictions(df_raw, PREDICTIONS_FILE, target_date)

    # Step 4: engineer features and define the feature column list
    df_feat = engineer_features(df_raw)
    feature_cols = get_feature_columns()

    # Step 5: drop any rows with NaN in features (affects the first ~12 rows)
    df_train = df_feat.dropna(subset=feature_cols).copy()
    print(f"Training rows after feature engineering: {len(df_train)}")

    X_all = df_train[feature_cols].values
    y_all = df_train["Unemployment"].values

    # Chronological 80/20 train–test split for leaderboard evaluation
    # Use the most recent 20 % of rows as a hold-out test set for leaderboard scoring
    split = max(1, int(len(X_all) * 0.8))
    X_train, X_test = X_all[:split], X_all[split:]
    y_train, y_test = y_all[:split], y_all[split:]

    # Impute any remaining NaNs with the column mean (safety measure for edge rows)
    imputer = SimpleImputer(strategy="mean")
    X_train = imputer.fit_transform(X_train)
    X_test = imputer.transform(X_test)

    # Build the prediction row for the target month using the fitted imputer
    target_row = build_target_row(df_feat, target_date)
    X_target = imputer.transform(target_row[feature_cols].values)

    # Step 6: train Auto-sklearn with the configured time and ensemble constraints
    print(
        f"\nRunning Auto-sklearn (max runtime: {MAX_AUTOML_RUNTIME}s, "
        f"ensemble size: {ENSEMBLE_SIZE}) ..."
    )
    # Note: Auto-sklearn will automatically try a wide variety of regression algorithms
    # (including all the sklearn regressors we use as explicit baselines) and combine the best-performing ones into an ensemble. The time limits ensure we get a result within a reasonable timeframe while still allowing for some exploration of the model space.
    automl = autosklearn.regression.AutoSklearnRegressor(
        #max_models=20, # Optional: limit the total number of models tried to keep the ensemble more interpretable (commented out to allow full exploration within the time budget)
        time_left_for_this_task=MAX_AUTOML_RUNTIME,
        per_run_time_limit=MAX_SINGLE_RUN,  # cap each individual model trial
        ensemble_size=ENSEMBLE_SIZE,
        seed=42,                            # fixed seed for reproducible results
        memory_limit=4096,                  # memory cap in MB per process
        n_jobs=-1,                          # use all available CPU cores
    )
    # Suppress Auto-sklearn stdout/stderr during fit, including the
    # Client-EnsembleBuilder warnings printed in Docker builds.
    with open(os.devnull, "w") as devnull:
        with redirect_stdout(devnull), redirect_stderr(devnull):
            automl.fit(X_train, y_train)

    # Step 7: predict the target month using the full Auto-sklearn ensemble
    prediction = float(automl.predict(X_target)[0])

    # Step 8: build leaderboard — auto-sklearn ensemble members + explicit sklearn candidates
    leaderboard = build_leaderboard(automl, X_test, y_test)
    sklearn_lb  = build_sklearn_candidates(X_train, y_train, X_test, y_test)

    # Step 9: evaluate Polynomial Regression (deg 2) and add it to the leaderboard
    poly_metrics, _ = eval_polynomial_regression(
        X_train, y_train, X_test, y_test, X_target, degree=2
    )
    poly_row = pd.DataFrame([poly_metrics])

    # Merge all entries, remove exact-name duplicates (keep first / highest R²)
    leaderboard = pd.concat(
        [lb for lb in [leaderboard, sklearn_lb, poly_row] if not lb.empty],
        ignore_index=True,
    )
    leaderboard = (
        leaderboard
        .sort_values("R2 (%)", ascending=False)
        .drop_duplicates(subset="Model", keep="first")
        .reset_index(drop=True)
    )

    print(f"\n--- Model Leaderboard (Top {TOP_MODELS_TO_SHOW}) ---")
    if not leaderboard.empty:
        print(
            leaderboard.head(TOP_MODELS_TO_SHOW).to_string(index=False)
        )
        # Best model is the one with the highest R² on the hold-out test set
        best_model_name = leaderboard.iloc[0]["Model"]
        best_r2 = leaderboard.iloc[0]["R2 (%)"]
        best_rmse = leaderboard.iloc[0]["RMSE"]
        best_mae = leaderboard.iloc[0]["MAE"]
    else:
        # Fallback: evaluate the full ensemble directly if leaderboard construction failed
        y_pred_test = automl.predict(X_test)
        best_r2 = round(r2_score(y_test, y_pred_test) * 100, 2)
        best_rmse = int(round(math.sqrt(mean_squared_error(y_test, y_pred_test))))
        best_mae = int(round(float(np.mean(np.abs(y_test - y_pred_test)))))
        best_model_name = "AutoSklearn Ensemble"
        print(f"  Ensemble  R2: {best_r2} %  RMSE: {best_rmse:,}")

    # Print the final forecast summary
    print("\n" + "=" * 62)
    print(f"  Forecast for {target_date.strftime('%B %Y')}")
    print(f"  Predicted unemployment: {int(round(prediction)):,}")
    print(f"  Best model:             {best_model_name}")
    print(f"  R²:                     {best_r2:.2f} %")
    print(f"  RMSE:                   {best_rmse:,}")
    print("=" * 62)

    # Step 10: persist the forecast to CSV (replaces any previous entry for the same month)
    save_prediction(
        target_date,
        prediction,
        best_model_name,
        PREDICTIONS_FILE,
        r2=best_r2,
        rmse=best_rmse,
        mae=best_mae,
    )
    write_unified_outputs(target_date)


# Run the script only when executed directly (not when imported as a module)
if __name__ == "__main__":
    run()
