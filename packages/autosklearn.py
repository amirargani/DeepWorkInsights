"""Auto-sklearn-based forecast pipeline for German monthly unemployment.

This module trains an Auto-sklearn ensemble (when available) to predict the
next month's unemployment figure. It also includes transparent sklearn
baselines (polynomial regression and a fixed set of sklearn regressors) so
that leaderboard entries remain interpretable even if Auto-sklearn finds
unexpected pipelines.
"""

import os
import math
import numpy as np
import pandas as pd
import warnings
from contextlib import redirect_stdout, redirect_stderr
from datetime import datetime
from pathlib import Path

from sklearn.ensemble import (
    AdaBoostRegressor,
    ExtraTreesRegressor,
    GradientBoostingRegressor,
    RandomForestRegressor,
)
from sklearn.impute import SimpleImputer
from sklearn.linear_model import ElasticNet, Lasso, LinearRegression, Ridge, SGDRegressor
from sklearn.metrics import mean_squared_error, r2_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import PolynomialFeatures, StandardScaler
from sklearn.neighbors import KNeighborsRegressor
from sklearn.svm import SVR
from sklearn.tree import DecisionTreeRegressor

# Suppress non-critical warnings from pandas, numpy and sklearn during runtime
warnings.filterwarnings("ignore")

# Import common functions from shared module
from .common import (
    load_data,
    merge_past_predictions,
    engineer_features,
    build_target_row,
    save_prediction,
    get_feature_columns,
    TOP_MODELS_TO_SHOW,
)

MAX_AUTOML_RUNTIME = 120    # total seconds Auto-sklearn is allowed to train
MAX_SINGLE_RUN = 30         # max seconds per individual model run
ENSEMBLE_SIZE = 10          # number of models combined in the final ensemble


def eval_polynomial_regression(
    X_train: np.ndarray,
    y_train: np.ndarray,
    X_test: np.ndarray,
    y_test: np.ndarray,
    X_target: np.ndarray,
    degree: int = 2,
) -> tuple[dict, float]:
    """Train a Polynomial Regression pipeline and return its metrics and prediction.

    Serves as a transparent baseline model alongside the Auto-sklearn ensemble.
    Pipeline: PolynomialFeatures → StandardScaler → LinearRegression.

    :param X_train: Feature matrix for training.
    :type X_train: numpy.ndarray
    :param y_train: Target values for training.
    :type y_train: numpy.ndarray
    :param X_test: Feature matrix for hold-out evaluation.
    :type X_test: numpy.ndarray
    :param y_test: Ground-truth values for hold-out evaluation.
    :type y_test: numpy.ndarray
    :param X_target: Single-row feature matrix for the month to forecast.
    :type X_target: numpy.ndarray
    :param degree: Polynomial degree; defaults to 2.
    :type degree: int
    :return: A tuple of (metrics dict, scalar prediction).
    :rtype: tuple[dict, float]
    """
    poly_pipeline = Pipeline([
        ("poly", PolynomialFeatures(degree=degree, include_bias=False)),
        ("scaler", StandardScaler()),
        ("lr", LinearRegression()),
    ])
    poly_pipeline.fit(X_train, y_train)

    y_pred = poly_pipeline.predict(X_test)
    r2 = r2_score(y_test, y_pred) * 100
    rmse = int(round(math.sqrt(mean_squared_error(y_test, y_pred))))
    mae = int(round(float(np.mean(np.abs(y_test - y_pred)))))

    prediction = float(poly_pipeline.predict(X_target)[0])

    metrics = {
        "Model": f"PolynomialRegression (deg {degree})",
        "R2 (%)": round(r2, 2),
        "RMSE": rmse,
        "MAE": mae,
    }
    return metrics, prediction


def build_leaderboard(
    automl, X_test: np.ndarray, y_test: np.ndarray
) -> pd.DataFrame:
    """Build a ranked leaderboard from the Auto-sklearn ensemble members.

    Each model in the final ensemble is evaluated individually on the test set.
    Results are sorted by R² descending so the best model appears first.

    :param automl: Fitted AutoSklearnRegressor object.
    :type automl: autosklearn.regression.AutoSklearnRegressor
    :param X_test: Test features.
    :type X_test: numpy.ndarray
    :param y_test: Test labels.
    :type y_test: numpy.ndarray
    :return: Ranked leaderboard DataFrame.
    :rtype: pandas.DataFrame
    """
    rows = []

    for pipeline in automl.get_models_with_weights():
        try:
            y_pred = pipeline.predict(X_test)
            r2 = r2_score(y_test, y_pred)
            rmse = math.sqrt(mean_squared_error(y_test, y_pred))
            mae = float(np.mean(np.abs(y_test - y_pred)))

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

    return df_lb.sort_values("R2 (%)", ascending=False).reset_index(drop=True)


def build_sklearn_candidates(
    X_train: np.ndarray,
    y_train: np.ndarray,
    X_test: np.ndarray,
    y_test: np.ndarray,
) -> pd.DataFrame:
    """Train a fixed set of sklearn regressors and score them on the hold-out set.

    These act as transparent baselines alongside the Auto-sklearn ensemble.

    :param X_train: Training features.
    :type X_train: numpy.ndarray
    :param y_train: Training labels.
    :type y_train: numpy.ndarray
    :param X_test: Test features.
    :type X_test: numpy.ndarray
    :param y_test: Test labels.
    :type y_test: numpy.ndarray
    :return: Leaderboard DataFrame of candidates.
    :rtype: pandas.DataFrame
    """
    candidates = {
        "RandomForestRegressor": RandomForestRegressor(n_estimators=500, random_state=42, n_jobs=-1),
        "ExtraTreesRegressor": ExtraTreesRegressor(n_estimators=500, random_state=42, n_jobs=-1),
        "GradientBoostingRegressor": GradientBoostingRegressor(n_estimators=300, max_depth=4,
                                                               learning_rate=0.05, random_state=42),
        "AdaBoostRegressor": AdaBoostRegressor(n_estimators=300, random_state=42),
        "DecisionTreeRegressor": DecisionTreeRegressor(max_depth=5, random_state=42),
        "KNeighborsRegressor": Pipeline([("scaler", StandardScaler()), ("knn", KNeighborsRegressor(n_neighbors=5))]),
        "SVR": Pipeline([("scaler", StandardScaler()), ("svr", SVR(C=1000.0, epsilon=0.1))]),
        "SGDRegressor": Pipeline([("scaler", StandardScaler()), ("sgd", SGDRegressor(max_iter=1000, tol=1e-3, random_state=42))]),
        "Lasso": Lasso(alpha=1.0, max_iter=10000),
        "Ridge": Ridge(alpha=1.0),
        "ElasticNet": ElasticNet(alpha=1.0, max_iter=10000),
    }

    rows = []
    for name, model in candidates.items():
        try:
            model.fit(X_train, y_train)
            y_pred = model.predict(X_test)
            r2 = round(r2_score(y_test, y_pred) * 100, 2)
            rmse = int(round(math.sqrt(mean_squared_error(y_test, y_pred))))
            mae = int(round(float(np.mean(np.abs(y_test - y_pred)))))
            rows.append({"Model": name, "R2 (%)": r2, "RMSE": rmse, "MAE": mae})
        except Exception:
            continue

    return pd.DataFrame(rows)


def run() -> None:
    """Main entry point: load data, train Auto-sklearn, forecast current month.

    :raises ImportError: If auto-sklearn is not installed.
    """
    import autosklearn.regression  # type: ignore # noqa: PLC0415

    print("=" * 62)
    print("  DeepWorkInsights – Auto-sklearn Unemployment Forecast")
    print("=" * 62)

    # Check for execution mode and target date from environment variables
    mode = os.environ.get("DEEPWORK_MODE", "prod").lower()
    target_date_str = os.environ.get("TARGET_DATE")
    if target_date_str:
        try:
            target_date = datetime.strptime(target_date_str, "%Y-%m-%d")
        except ValueError:
            target_date = datetime.strptime(target_date_str, "%Y-%m-%d %H:%M:%S")
    else:
        now = datetime.now()
        target_date = datetime(now.year, now.month, now.day)

    if mode == "test":
        overwrite = False
        print(f"\n[RUNNING IN TEST MODE] Target month: {target_date.strftime('%B %Y')}")
    else:
        overwrite = True
        print(f"\nTarget month: {target_date.strftime('%B %Y')}")

    print("\nLoading data ...")
    df_raw = load_data()

    last_known = df_raw["Date"].max()
    if last_known >= target_date:
        actual = df_raw[df_raw["Date"] == target_date]["Unemployment"].values[0]
        print(
            f"\nActual data for {target_date.strftime('%B %Y')} already exists "
            f"(value: {actual:,}). No forecast needed."
        )
        return

    df_raw = merge_past_predictions(df_raw, "autosklearn", target_date)

    df_feat = engineer_features(df_raw)
    feature_cols = get_feature_columns()

    df_train = df_feat.dropna(subset=feature_cols).copy()
    print(f"Training rows after feature engineering: {len(df_train)}")

    X_all = df_train[feature_cols].values
    y_all = df_train["Unemployment"].values

    split = max(1, int(len(X_all) * 0.8))
    X_train, X_test = X_all[:split], X_all[split:]
    y_train, y_test = y_all[:split], y_all[split:]

    imputer = SimpleImputer(strategy="mean")
    X_train = imputer.fit_transform(X_train)
    X_test = imputer.transform(X_test)

    target_row = build_target_row(df_feat, target_date)
    X_target = imputer.transform(target_row[feature_cols].values)

    print(
        f"\nRunning Auto-sklearn (max runtime: {MAX_AUTOML_RUNTIME}s, "
        f"ensemble size: {ENSEMBLE_SIZE}) ..."
    )
    automl = autosklearn.regression.AutoSklearnRegressor(
        time_left_for_this_task=MAX_AUTOML_RUNTIME,
        per_run_time_limit=MAX_SINGLE_RUN,
        ensemble_size=ENSEMBLE_SIZE,
        seed=42,
        memory_limit=4096,
        n_jobs=-1,
    )
    with open(os.devnull, "w") as devnull:
        with redirect_stdout(devnull), redirect_stderr(devnull):
            automl.fit(X_train, y_train)

    prediction = float(automl.predict(X_target)[0])

    leaderboard = build_leaderboard(automl, X_test, y_test)
    sklearn_lb = build_sklearn_candidates(X_train, y_train, X_test, y_test)

    poly_metrics, _ = eval_polynomial_regression(
        X_train, y_train, X_test, y_test, X_target, degree=2
    )
    poly_row = pd.DataFrame([poly_metrics])

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
        best_model_name = leaderboard.iloc[0]["Model"]
        best_r2 = leaderboard.iloc[0]["R2 (%)"]
        best_rmse = leaderboard.iloc[0]["RMSE"]
        best_mae = leaderboard.iloc[0]["MAE"]
    else:
        y_pred_test = automl.predict(X_test)
        best_r2 = round(r2_score(y_test, y_pred_test) * 100, 2)
        best_rmse = int(round(math.sqrt(mean_squared_error(y_test, y_pred_test))))
        best_mae = int(round(float(np.mean(np.abs(y_test - y_pred_test)))))
        best_model_name = "AutoSklearn Ensemble"
        print(f"  Ensemble  R2: {best_r2} %  RMSE: {best_rmse:,}")

    print("\n" + "=" * 62)
    print(f"  Forecast for {target_date.strftime('%B %Y')}")
    print(f"  Predicted unemployment: {int(round(prediction)):,}")
    print(f"  Best model:             {best_model_name}")
    print(f"  R²:                     {best_r2:.2f} %")
    print(f"  RMSE:                   {best_rmse:,}")
    print("=" * 62)

    save_prediction(
        target_date,
        prediction,
        best_model_name,
        "autosklearn",
        r2=best_r2,
        rmse=best_rmse,
        mae=best_mae,
        overwrite=overwrite,
    )


# Execute Auto-sklearn pipeline when module is run as a CLI command
if __name__ == "__main__":
    run()
