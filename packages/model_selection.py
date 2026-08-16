"""Evaluate collected monthly test runs in the database and promote the best model.

Finds the test run with the best metrics (highest R2, lowest RMSE) for the
target month, copies it to the production predictions table, and archives
the test runs in PostgreSQL.
"""

import os
import pandas as pd
from datetime import datetime


def select_and_promote(framework: str, target_date: datetime) -> bool:
    """Find the best run for the target month in database and write it to production predictions.

    :param framework: AutoML framework name ('automl' or 'autosklearn').
    :type framework: str
    :param target_date: Evaluation target date.
    :type target_date: datetime.datetime
    :return: True if a run was successfully promoted, False otherwise.
    :rtype: bool
    """
    from .common import get_db_engine, save_prediction
    import sqlalchemy as sa
    engine = get_db_engine()

    # Query test runs for target framework, year and month from active table
    query = sa.text(
        "SELECT year, month, run_timestamp, prediction, model, r2, rmse, mae "
        "FROM test_runs "
        "WHERE framework = :framework AND year = :year AND month = :month"
    )
    with engine.connect() as conn:
        res = conn.execute(
            query,
            {"framework": framework, "year": target_date.year, "month": target_date.month}
        )
        rows = res.fetchall()

    if not rows:
        print(f"[{framework}] No test runs found in database for {target_date.strftime('%B %Y')}. Nothing to promote.")
        return False

    # Construct a DataFrame for easy sorting
    df = pd.DataFrame(
        rows,
        columns=["Year", "Month", "Run_Timestamp", "Prediction", "Model", "R2 (%)", "RMSE", "MAE"]
    )

    # Filter to only include runs from the most recent run date (to select the best model of the latest execution)
    df["Run_Date"] = pd.to_datetime(df["Run_Timestamp"]).dt.date
    latest_date = df["Run_Date"].max()
    df_latest = df[df["Run_Date"] == latest_date]

    # Sort to find the best model:
    # 1. R2 (%) descending (highest first)
    # 2. RMSE ascending (lowest first)
    # 3. MAE ascending (lowest first)
    df_sorted = df_latest.sort_values(
        by=["R2 (%)", "RMSE", "MAE"],
        ascending=[False, True, True]
    )

    best_run = df_sorted.iloc[0]
    print(f"\n[{framework}] Selected best run from {len(df_latest)} test runs (of latest date {latest_date}) in database for {target_date.strftime('%B %Y')}:")
    print(f"  Timestamp:  {best_run['Run_Timestamp']}")
    print(f"  Model:      {best_run['Model']}")
    print(f"  Prediction: {int(best_run['Prediction']):,}")
    print(f"  R² Score:   {best_run['R2 (%)']}%")
    print(f"  RMSE:       {best_run['RMSE']:,}")
    print(f"  MAE:        {best_run['MAE']:,}")

    # Promote to production predictions table
    save_prediction(
        target_date=target_date,
        prediction=float(best_run["Prediction"]),
        best_model=str(best_run["Model"]),
        framework=framework,
        r2=float(best_run["R2 (%)"]) if pd.notna(best_run["R2 (%)"]) else None,
        rmse=float(best_run["RMSE"]) if pd.notna(best_run["RMSE"]) else None,
        mae=float(best_run["MAE"]) if pd.notna(best_run["MAE"]) else None,
        overwrite=True
    )
    return True


def archive_test_runs(
    framework: str = None,
    target_date: datetime = None,
    max_active_per_framework: int = 5,
) -> None:
    """Move test runs matching prior months and runs exceeding max_active_per_framework to archive.

    Keeps up to max_active_per_framework active test runs per framework in test_runs,
    and moves all older test runs into test_runs_archive.

    :param framework: Framework name ('automl', 'autosklearn', or None for all).
    :type framework: str, optional
    :param target_date: Target date object for prior month filtering, optional.
    :type target_date: datetime.datetime, optional
    :param max_active_per_framework: Maximum active runs to retain in test_runs per framework.
    :type max_active_per_framework: int
    """
    from .common import get_db_engine
    import sqlalchemy as sa
    engine = get_db_engine()

    frameworks = [framework] if framework else ["automl", "autosklearn"]

    with engine.connect() as conn:
        for fw in frameworks:
            # 1. Archive runs from prior target months if target_date is specified
            if target_date is not None:
                copy_prior_query = sa.text(
                    "INSERT INTO test_runs_archive (framework, year, month, run_timestamp, prediction, model, r2, rmse, mae) "
                    "SELECT framework, year, month, run_timestamp, prediction, model, r2, rmse, mae "
                    "FROM test_runs "
                    "WHERE framework = :framework AND (year < :year OR (year = :year AND month < :month))"
                )
                delete_prior_query = sa.text(
                    "DELETE FROM test_runs "
                    "WHERE framework = :framework AND (year < :year OR (year = :year AND month < :month))"
                )
                conn.execute(
                    copy_prior_query, 
                    {"framework": fw, "year": target_date.year, "month": target_date.month}
                )
                conn.execute(
                    delete_prior_query, 
                    {"framework": fw, "year": target_date.year, "month": target_date.month}
                )

            # 2. Archive runs from prior execution dates (date < latest_date) or excess runs for latest date
            runs = conn.execute(
                sa.text(
                    "SELECT year, month, run_timestamp FROM test_runs "
                    "WHERE framework = :framework "
                    "ORDER BY run_timestamp DESC"
                ),
                {"framework": fw}
            ).fetchall()

            if runs:
                latest_date = pd.to_datetime(runs[0][2]).date()
                excess_runs = []
                current_date_count = 0

                for r in runs:
                    r_date = pd.to_datetime(r[2]).date()
                    if r_date < latest_date:
                        # Prior execution date run -> Move to archive
                        excess_runs.append(r)
                    else:
                        # Current latest execution date run
                        current_date_count += 1
                        if current_date_count > max_active_per_framework:
                            excess_runs.append(r)

                for r in excess_runs:
                    conn.execute(
                        sa.text(
                            "INSERT INTO test_runs_archive (framework, year, month, run_timestamp, prediction, model, r2, rmse, mae) "
                            "SELECT framework, year, month, run_timestamp, prediction, model, r2, rmse, mae "
                            "FROM test_runs "
                            "WHERE framework = :framework AND year = :year AND month = :month AND run_timestamp = :ts"
                        ),
                        {"framework": fw, "year": r[0], "month": r[1], "ts": r[2]}
                    )
                    conn.execute(
                        sa.text(
                            "DELETE FROM test_runs "
                            "WHERE framework = :framework AND year = :year AND month = :month AND run_timestamp = :ts"
                        ),
                        {"framework": fw, "year": r[0], "month": r[1], "ts": r[2]}
                    )

        conn.commit()

    fw_str = framework if framework else "all frameworks"
    print(f"[{fw_str}] Archived test runs successfully (active test_runs capped at {max_active_per_framework}).")


def main() -> None:
    """Main execution point for model selection."""
    print("=" * 60)
    print("  DeepWorkInsights – Best Model Selection & Promotion")
    print("=" * 60)

    # Parse target date from environment variable
    target_date_str = os.environ.get("TARGET_DATE")
    if target_date_str:
        try:
            target_date = datetime.strptime(target_date_str, "%Y-%m-%d")
        except ValueError:
            target_date = datetime.strptime(target_date_str, "%Y-%m-%d %H:%M:%S")
    else:
        now = datetime.now()
        target_date = datetime(now.year, now.month, now.day)

    print(f"Target month: {target_date.strftime('%B %Y')}\n")

    # Select and promote H2O AutoML
    automl_promoted = select_and_promote(
        "automl",
        target_date
    )

    # Select and promote Auto-sklearn
    autosklearn_promoted = select_and_promote(
        "autosklearn",
        target_date
    )

    if automl_promoted or autosklearn_promoted:
        # Archive the test runs in DB so we start fresh next month
        if automl_promoted:
            archive_test_runs("automl", target_date)
        if autosklearn_promoted:
            archive_test_runs("autosklearn", target_date)
        print("\nPromotion complete. Test runs successfully archived in database.")
    else:
        print("\nNo best models could be promoted (no test runs found for this month).")


# Execute model promotion pipeline when module is run as a CLI command
if __name__ == "__main__":
    main()
