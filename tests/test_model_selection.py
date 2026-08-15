"""Unit tests for model evaluation, promotion, and test run archival logic."""

from unittest.mock import patch
import sqlalchemy as sa
import pandas as pd
from datetime import datetime
from packages.model_selection import select_and_promote, archive_test_runs


@patch('packages.common.get_db_engine')
def test_select_and_promote(mock_engine):
    """Verify that select_and_promote correctly selects the best model run and promotes it."""
    # Use SQLite in-memory database for isolated testing
    test_engine = sa.create_engine("sqlite:///:memory:")
    mock_engine.return_value = test_engine

    # Create the required tables in sqlite
    metadata = sa.MetaData()
    test_runs = sa.Table(
        "test_runs",
        metadata,
        sa.Column("framework", sa.String(20)),
        sa.Column("year", sa.Integer),
        sa.Column("month", sa.Integer),
        sa.Column("run_timestamp", sa.DateTime),
        sa.Column("prediction", sa.Integer),
        sa.Column("model", sa.String(255)),
        sa.Column("r2", sa.Float),
        sa.Column("rmse", sa.Float),
        sa.Column("mae", sa.Float),
    )
    predictions = sa.Table(
        "predictions",
        metadata,
        sa.Column("framework", sa.String(20)),
        sa.Column("year", sa.Integer),
        sa.Column("month", sa.Integer),
        sa.Column("target_date", sa.Date),
        sa.Column("prediction", sa.Integer),
        sa.Column("model", sa.String(255)),
        sa.Column("run_timestamp", sa.DateTime),
        sa.Column("r2", sa.Float),
        sa.Column("rmse", sa.Float),
        sa.Column("mae", sa.Float),
    )
    test_runs_archive = sa.Table(
        "test_runs_archive",
        metadata,
        sa.Column("framework", sa.String(20)),
        sa.Column("year", sa.Integer),
        sa.Column("month", sa.Integer),
        sa.Column("run_timestamp", sa.DateTime),
        sa.Column("prediction", sa.Integer),
        sa.Column("model", sa.String(255)),
        sa.Column("r2", sa.Float),
        sa.Column("rmse", sa.Float),
        sa.Column("mae", sa.Float),
    )
    metadata.create_all(test_engine)

    # Insert mock test runs:
    # Run 1: R2 90%, RMSE 60000
    # Run 2: R2 95%, RMSE 50000 (Best)
    # Run 3: R2 95%, RMSE 55000 (Worse RMSE)
    with test_engine.connect() as conn:
        conn.execute(
            test_runs.insert().values([
                {
                    "framework": "automl",
                    "year": 2026,
                    "month": 8,
                    "run_timestamp": datetime(2026, 8, 12, 10, 0),
                    "prediction": 3000000,
                    "model": "ModelA",
                    "r2": 90.0,
                    "rmse": 60000.0,
                    "mae": 40000.0,
                },
                {
                    "framework": "automl",
                    "year": 2026,
                    "month": 8,
                    "run_timestamp": datetime(2026, 8, 12, 11, 0),
                    "prediction": 3050000,
                    "model": "ModelB",
                    "r2": 95.0,
                    "rmse": 50000.0,
                    "mae": 38000.0,
                },
                {
                    "framework": "automl",
                    "year": 2026,
                    "month": 8,
                    "run_timestamp": datetime(2026, 8, 12, 12, 0),
                    "prediction": 3020000,
                    "model": "ModelC",
                    "r2": 95.0,
                    "rmse": 55000.0,
                    "mae": 39000.0,
                },
            ])
        )
        conn.commit()

    # Run selection
    promoted = select_and_promote("automl", datetime(2026, 8, 1))

    assert promoted is True

    # Check predictions table contains promoted best run (ModelB)
    with test_engine.connect() as conn:
        res = conn.execute(sa.text("SELECT model, prediction, r2, rmse FROM predictions")).fetchone()
        assert res is not None
        assert res[0] == "ModelB"  # Best model selected
        assert res[1] == 3050000
        assert res[2] == 95.0
        assert res[3] == 50000.0


@patch('packages.common.get_db_engine')
def test_archive_test_runs(mock_engine):
    """Verify that archive_test_runs copies active runs to archive table and clears active table."""
    test_engine = sa.create_engine("sqlite:///:memory:")
    mock_engine.return_value = test_engine

    metadata = sa.MetaData()
    test_runs = sa.Table(
        "test_runs",
        metadata,
        sa.Column("framework", sa.String(20)),
        sa.Column("year", sa.Integer),
        sa.Column("month", sa.Integer),
        sa.Column("run_timestamp", sa.DateTime),
        sa.Column("prediction", sa.Integer),
        sa.Column("model", sa.String(255)),
        sa.Column("r2", sa.Float),
        sa.Column("rmse", sa.Float),
        sa.Column("mae", sa.Float),
    )
    test_runs_archive = sa.Table(
        "test_runs_archive",
        metadata,
        sa.Column("framework", sa.String(20)),
        sa.Column("year", sa.Integer),
        sa.Column("month", sa.Integer),
        sa.Column("run_timestamp", sa.DateTime),
        sa.Column("prediction", sa.Integer),
        sa.Column("model", sa.String(255)),
        sa.Column("r2", sa.Float),
        sa.Column("rmse", sa.Float),
        sa.Column("mae", sa.Float),
    )
    metadata.create_all(test_engine)

    # Insert mock test runs for target month and another month
    with test_engine.connect() as conn:
        conn.execute(
            test_runs.insert().values([
                {
                    "framework": "automl",
                    "year": 2026,
                    "month": 8,
                    "run_timestamp": datetime(2020, 8, 12, 10, 0),
                    "prediction": 3000000,
                    "model": "ModelA",
                    "r2": 90.0,
                    "rmse": 60000.0,
                    "mae": 40000.0,
                },
                {
                    "framework": "automl",
                    "year": 2026,
                    "month": 9,
                    "run_timestamp": datetime(2020, 9, 12, 10, 0),
                    "prediction": 3100000,
                    "model": "ModelD",
                    "r2": 92.0,
                    "rmse": 58000.0,
                    "mae": 39000.0,
                },
            ])
        )
        conn.commit()

    # Archive August runs (by running pipeline for September)
    archive_test_runs("automl", datetime(2026, 9, 1))

    # Verify active test runs (August run should be deleted, September run remains)
    with test_engine.connect() as conn:
        active = conn.execute(sa.text("SELECT month, model FROM test_runs")).fetchall()
        assert len(active) == 1
        assert active[0][0] == 9
        assert active[0][1] == "ModelD"

        # Verify archive table (August run should be copied)
        archived = conn.execute(sa.text("SELECT month, model FROM test_runs_archive")).fetchall()
        assert len(archived) == 1
        assert archived[0][0] == 8
        assert archived[0][1] == "ModelA"
