"""H2O AutoML-based forecast pipeline for German monthly unemployment.

This module trains an H2O AutoML pipeline (when available) to predict the
next month's unemployment figure. If H2O or Java is not available the
script falls back to a small set of sklearn regressors that mimic H2O's
main families. Predictions are saved so future runs can re-use prior
forecasts as training rows (self-improvement loop).
"""

import os
import math
import warnings
import pandas as pd
from datetime import datetime
from pathlib import Path
from sklearn.ensemble import (
    ExtraTreesRegressor,
    GradientBoostingRegressor,
    RandomForestRegressor,
)
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

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

# Suppress non-critical warnings from pandas, numpy and h2o during runtime
warnings.filterwarnings("ignore")
# Specifically suppress the H2O multi-threading/polars warning by matching the text
warnings.filterwarnings("ignore", message=".*Converting H2O frame to pandas dataframe using single-thread.*")

# Maximum total wall-clock seconds H2O AutoML is allowed to search for models
MAX_AUTOML_RUNTIME = 120


def _run_sklearn_fallback(
    df_train: pd.DataFrame,
    feature_cols: list,
    target_row: pd.DataFrame,
    target_date: datetime,
    overwrite: bool,
) -> None:
    """Train sklearn equivalents of the H2O model families as a fallback.

    Used when Java or the h2o package is unavailable on the host machine.
    Mirrors the four main model families H2O AutoML would consider:
    GradientBoosting (≈ GBM), RandomForest, ExtraTrees (≈ RF variant),
    Ridge (≈ GLM). Results are ranked by R² and the best model wins.

    :param df_train: Processed training dataset.
    :type df_train: pandas.DataFrame
    :param feature_cols: List of features to use in model training.
    :type feature_cols: list
    :param target_row: Single-row DataFrame containing features for target month.
    :type target_row: pandas.DataFrame
    :param target_date: Target month date object.
    :type target_date: datetime.datetime
    :param overwrite: Whether to overwrite an existing entry for the same month.
    :type overwrite: bool
    """
    print("\n  Falling back to sklearn equivalents of H2O model families.")

    X_all = df_train[feature_cols].values
    y_all = df_train["Unemployment"].values

    split = max(1, int(len(X_all) * 0.8))
    X_tr, X_te = X_all[:split], X_all[split:]
    y_tr, y_te = y_all[:split], y_all[split:]

    imputer = SimpleImputer(strategy="mean")
    X_tr = imputer.fit_transform(X_tr)
    X_te = imputer.transform(X_te)
    X_tgt = imputer.transform(target_row[feature_cols].values)

    candidates = {
        "GradientBoosting (GBM)": GradientBoostingRegressor(
            n_estimators=500, max_depth=4, learning_rate=0.05, random_state=42
        ),
        "RandomForest": RandomForestRegressor(
            n_estimators=500, random_state=42, n_jobs=-1
        ),
        "ExtraTrees": ExtraTreesRegressor(
            n_estimators=500, random_state=42, n_jobs=-1
        ),
        "Ridge": Ridge(alpha=1.0),
    }

    rows = []
    for name, model in candidates.items():
        model.fit(X_tr, y_tr)
        y_pred = model.predict(X_te)
        r2 = round(r2_score(y_te, y_pred) * 100, 2)
        rmse = int(round(math.sqrt(mean_squared_error(y_te, y_pred))))
        mae = int(round(float(mean_absolute_error(y_te, y_pred))))
        pred = int(round(float(model.predict(X_tgt)[0])))
        rows.append({"Model": name, "R2 (%)": r2, "RMSE": rmse, "MAE": mae, "Prediction": pred})

    lb = pd.DataFrame(rows).sort_values("R2 (%)", ascending=False).reset_index(drop=True)
    best = lb.iloc[0]

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
        "automl",
        r2=best["R2 (%)"],
        rmse=best["RMSE"],
        mae=best["MAE"],
        overwrite=overwrite,
    )


def run() -> None:
    """Main entry point: load data, train AutoML, forecast current month.

    Tries H2O AutoML first (requires Java 11+ and the h2o package).
    Falls back to sklearn equivalents of the same model families when Java
    or h2o is unavailable on the current machine.
    """
    print("=" * 60)
    print("  DeepWorkInsights – H2O AutoML Unemployment Forecast")
    print("=" * 60)

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
        print(
            f"\nActual data for {target_date.strftime('%B %Y')} already exists "
            f"(value: {df_raw[df_raw['Date'] == target_date]['Unemployment'].values[0]:,}). "
            "No forecast needed."
        )
        return

    df_raw = merge_past_predictions(df_raw, "automl", target_date)

    df_feat = engineer_features(df_raw)
    feature_cols = get_feature_columns()

    df_train = df_feat.dropna(subset=feature_cols).copy()
    print(f"Training rows after feature engineering: {len(df_train)}")

    target_row = build_target_row(df_feat, target_date)

    try:
        import h2o
        from h2o.automl import H2OAutoML

        print("\nInitialising H2O ...")
        h2o.init(max_mem_size="2g", verbose=False)

        train_h2o = h2o.H2OFrame(df_train[feature_cols + ["Unemployment"]])
        target_h2o = h2o.H2OFrame(target_row[feature_cols])

        print(f"\nRunning H2O AutoML (max runtime: {MAX_AUTOML_RUNTIME}s) ...")
        aml = H2OAutoML(
            max_runtime_secs=MAX_AUTOML_RUNTIME,
            seed=42,
            sort_metric="RMSE",
            verbosity=None,
        )
        aml.train(x=feature_cols, y="Unemployment", training_frame=train_h2o)

        lb = aml.leaderboard.as_data_frame()
        lb["RMSE"] = lb["rmse"].round(0).astype(int)
        lb["R2 (%)"] = float("nan")
        best_r2 = float("nan")

        if "r2" in lb.columns:
            lb["R2 (%)"] = (lb["r2"] * 100).round(2)
            display_cols = ["model_id", "R2 (%)", "RMSE", "mae"]
            best_r2 = lb.iloc[0]["R2 (%)"]
        else:
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

        print("\n--- Model Leaderboard (Top {}) ---".format(TOP_MODELS_TO_SHOW))
        print(
            lb[display_cols]
            .head(TOP_MODELS_TO_SHOW)
            .rename(columns={"model_id": "Model", "mae": "MAE"})
            .to_string(index=False)
        )

        prediction = aml.leader.predict(target_h2o).as_data_frame().iloc[0, 0]
        best_rmse = lb.iloc[0]["RMSE"]
        best_id = lb.iloc[0]["model_id"]

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
            "automl",
            r2=best_r2,
            rmse=best_rmse,
            mae=best_mae,
            overwrite=overwrite,
        )

    except (ImportError, Exception) as exc:
        if isinstance(exc, ImportError):
            print("    [SKIP] h2o package not installed.")
        else:
            print(f"    [SKIP] H2O could not be started: {exc.__class__.__name__}")
            print("           Make sure Java (JDK 11+) is installed, or run inside Docker.")
        _run_sklearn_fallback(df_train, feature_cols, target_row, target_date, overwrite)

    finally:
        try:
            import h2o as _h2o
            _h2o.cluster().shutdown(prompt=False)
        except Exception:
            pass


if __name__ == "__main__":
    run()
